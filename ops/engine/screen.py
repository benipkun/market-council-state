# Market Council wide screen. Once a day it runs the seven-check scorecard over a few hundred large,
# liquid US-listed shares (US companies and European companies with a US listing), in three stages
# so the small free sources are not hammered: prices for all, company statements for the ones in an
# upward trend, insider and holder data only for the finalists. It writes state/screen.json; the
# research engine then builds full cards for the best few. It reads public pages only and places no
# orders.
import datetime
import json
import math
import os
import re
import time
import urllib.request

import numpy as np

import engine as E
import research as RS
import strategy as ST

EUROPE = ("United Kingdom", "Netherlands", "Switzerland", "Ireland", "France", "Germany", "Italy", "Spain", "Luxembourg", "Denmark", "Sweden", "Finland",
          "Belgium", "Norway")
N_US, N_EU = 240, 60          # universe size: the largest by market value
STATEMENTS_MAX = 160          # statements are fetched for at most this many shares in an upward trend
FINALISTS = 40                # insider and holder pages are fetched only for these
ADD_MAX = 10                  # at most this many are handed to the research engine for a full card
BUDGET = 19 * 60              # seconds; the run stops adding work after this (the job itself is cut off at 25 minutes)
SECTOR = {"Finance": "Financials"}


def fetch(url, cap=9000000):
    req = urllib.request.Request(url, headers=RS.HEAD)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read(cap).decode("utf-8", "replace"))


def fnum(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def universe():
    rows = ((fetch(RS.NQ + "screener/stocks?tableonly=true&limit=25&offset=0&download=true") or {}).get("data") or {}).get("rows") or []
    out = []
    for r in rows:
        sym = str(r.get("symbol") or "").strip()
        cap, px, vol, country = fnum(r.get("marketCap")), fnum(r.get("lastsale")), fnum(r.get("volume")), str(r.get("country") or "")
        region = "US" if country == "United States" else ("Europe" if country in EUROPE else None)
        if not re.fullmatch(r"[A-Z]{1,5}", sym) or not region or not cap or not px or not vol or cap < 5e9 or px < 5 or px * vol < 2e7:
            continue
        name = re.sub(r"\s+(Common Stock|Class [A-Z] .*|American Depositary .*|Ordinary Shares.*|ADS.*|Inc\. Common.*)$", "", str(r.get("name") or sym)).strip()[:60]
        out.append({"t": sym, "name": name, "cap": cap, "px": px, "country": country, "region": region, "sector": str(r.get("sector") or "")})
    out.sort(key=lambda x: -x["cap"])
    seen, uniq = set(), []
    for x in out:
        key = re.sub("[^a-z]", "", x["name"].lower())[:9]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(x)
    return [x for x in uniq if x["region"] == "US"][:N_US] + [x for x in uniq if x["region"] == "Europe"][:N_EU], len(rows), len(out)


def beta_of(px, spy):
    n = min(len(px), len(spy), 253)
    if n < 120:
        return None
    a, b = np.array(px[-n:], dtype=float), np.array(spy[-n:], dtype=float)
    ra, rb = a[1:] / a[:-1] - 1, b[1:] / b[:-1] - 1
    v = float(np.var(rb))
    return float(np.cov(ra, rb)[0, 1] / v) if v > 0 else None


def main():
    t0 = time.time()
    quant, snap = E.rj("state/quant.json", {}) or {}, E.rj("treasury/snapshot.json", {}) or {}
    rf = (quant.get("opt") or {}).get("rf") or 0.04
    uni = E.rj("ops/engine/universe.json", {}) or {}
    mine = set([p.get("ticker") for p in snap.get("positions", [])] + [k.get("ticker") for k in (E.rj("state/known_companies.json", {}) or {}).get("tickers", [])]
               + [x.get("ticker") for x in (E.rj("state/theses.json", {}) or {}).get("theses", [])] + list(uni.get("candidates", [])) + ["SPY", "BIL"])
    out = {"as_of": E.now_iso(), "status": "ok", "limits": [], "errors": {}}
    funnel = {}
    try:
        names, listed, eligible = universe()
    except Exception as e:
        out.update({"status": "no universe", "errors": {"universe": str(e)[:160]}})
        E.wj("state/screen.json", out)
        print("screen: the share list did not load:", str(e)[:120])
        return
    funnel.update({"listed": listed, "large_and_liquid": eligible, "screened": len(names)})
    spy_rows = E.read_cache("SPY")
    if len(spy_rows) < 300:
        try:
            spy_rows = E.fetch_cnbc("SPY", time.time() - 800 * 86400)
        except Exception:
            spy_rows = []
    spy = [v for d, v in spy_rows]
    spy_mom = (spy[-22] / spy[-253] - 1) if len(spy) > 260 else 0.0

    # stage A: two years of prices for every share; trend and momentum need nothing else
    stage, misses = [], 0
    for x in names:
        if time.time() - t0 > BUDGET * 0.45 or misses >= 12:
            out["limits"].append("Prices: stopped after %d of %d shares (%s)." % (len(stage), len(names), "the price source stopped answering" if misses >= 12 else "time budget"))
            break
        try:
            rows = E.fetch_cnbc(x["t"], time.time() - 800 * 86400)
            misses = 0
        except Exception as e:
            misses += 1
            out["errors"]["prices"] = str(e)[:120]
            continue
        time.sleep(0.15)
        if len(rows) < 270:
            continue
        if x["t"] not in mine:
            os.makedirs(E.CACHE, exist_ok=True)
            with open(E.cache_path(x["t"]), "w", encoding="utf-8", newline="") as f:
                f.write(E.NL.join(d + "," + ("%.4f" % v) for d, v in rows) + E.NL)
        px = [v for d, v in rows]
        x.update({"pxs": px, "last": px[-1], "mom": px[-22] / px[-253] - 1, "trend": bool(px[-1] > float(np.mean(px[-200:])))})
        stage.append(x)
    funnel["with_prices"] = len(stage)
    up = sorted([x for x in stage if x["trend"]], key=lambda z: -z["mom"])
    funnel["upward_trend"] = len(up)
    if len(up) > STATEMENTS_MAX:
        out["limits"].append("Statements: fetched for the %d strongest of %d shares in an upward trend, to keep the run short." % (STATEMENTS_MAX, len(up)))
    up = up[:STATEMENTS_MAX]

    # stage B: statements and the last earnings report, for the shares in an upward trend
    done, misses = [], 0
    for x in up:
        if time.time() - t0 > BUDGET * 0.85 or misses >= 10:
            out["limits"].append("Statements: stopped after %d of %d shares (%s)." % (len(done), len(up), "the statement source stopped answering" if misses >= 10 else "time budget"))
            break
        fin = RS.nq("company/" + x["t"] + "/financials?frequency=1")
        es = ((RS.nq("company/" + x["t"] + "/earnings-surprise") or {}).get("earningsSurpriseTable") or {}).get("rows") or []
        misses = misses + 1 if (fin is None and not es) else 0
        meta = {"name": x["name"], "sector": SECTOR.get(x["sector"], x["sector"]), "country": x["country"], "cls": "Equity"}
        x["beta"] = beta_of(x["pxs"], spy)
        try:
            v = RS.dcf(x["t"], fin, x["last"], x["cap"] / x["last"] / 1000.0, x["beta"], rf, meta)
        except Exception as e:
            v = {"status": "not valued", "reason": str(e)[:80]}
        x["fair"], x["mos"] = v.get("fair_value_per_share"), v.get("margin_of_safety")
        x["em"] = (v.get("assumptions") or {}).get("ebit_margin")
        x["rv"] = None
        if es:
            rep = RS.mdy(es[0].get("dateReported"))
            x["rv"] = {"surprise_pct": RS.num(es[0].get("percentageSurprise")), "move_5d": RS.price_move(x["t"], rep or "", 5), "reported": rep}
        x["part"] = ST.score_checks(x["mos"], x["fair"], x["em"], x["pxs"], spy_mom, None, None, x["rv"])
        done.append(x)
    funnel["with_statements"] = len(done)
    finalists = sorted([x for x in done if x["part"]["score"] >= 3], key=lambda z: (-z["part"]["score"], -z["mom"]))
    funnel["three_of_five_or_better"] = len(finalists)
    if len(finalists) > FINALISTS:
        out["limits"].append("Insiders and holders: looked up for the best %d of %d, because those two sites are small and block heavy use." % (FINALISTS, len(finalists)))
    finalists = finalists[:FINALISTS]

    # stage C: insider trades and well-known holders, for the finalists only
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    rows = []
    for x in finalists:
        ins, kh = None, None
        if time.time() - t0 < BUDGET:
            if x["region"] == "US":
                oi = RS.openinsider(x["t"])
                if oi is not None:
                    buys = [z for z in oi if z["type"].startswith("P") and z["traded"] >= cut]
                    sells = [z for z in oi if z["type"].startswith("S") and z["traded"] >= cut]
                    ins = {"open_market_buys_90d": len(buys), "open_market_sales_90d": len(sells), "buy_value_90d": sum(z["value"] or 0 for z in buys),
                           "sale_value_90d": sum(abs(z["value"] or 0) for z in sells)}
            kh = RS.dataroma(x["t"], 1)
            time.sleep(0.6)
        r = ST.score_checks(x["mos"], x["fair"], x["em"], x["pxs"], spy_mom, ins, kh, x["rv"])
        r.update({"t": x["t"], "name": x["name"], "region": x["region"], "country": x["country"], "sector": x["sector"], "cap_bn": round(x["cap"] / 1e9, 1),
                  "price": round(x["last"], 2), "momentum": round(x["mom"], 4), "on_watchlist": x["t"] in mine,
                  "beta": round(x["beta"], 3) if x.get("beta") is not None else None})
        rows.append(r)
    rows.sort(key=lambda z: (-z["score"], -z["momentum"]))
    funnel["fully_scored"] = len(rows)
    funnel["qualify"] = len([z for z in rows if z["qualifies"]])
    fails = {}
    for z in rows:
        for c in z["checks"]:
            if c["pass"] is not True:
                fails[c["id"]] = fails.get(c["id"], 0) + 1
    added = [{"t": z["t"], "name": z["name"], "sector": z["sector"], "country": z["country"], "region": z["region"], "score": z["score"], "beta": z.get("beta"),
              "why": "passes " + ", ".join(c["id"] for c in z["checks"] if c["pass"])} for z in rows if z["score"] >= 4 and z["trend_ok"] and not z["on_watchlist"]][:ADD_MAX]
    funnel["handed_to_research"] = len(added)
    out["limits"] += ["European companies are covered only through their US listings. They file no US insider forms and their statements give no per-share value here, so they can pass five checks at most.",
                      "The list is the %d largest US and %d largest European names by market value that trade at least 20 million dollars a day; smaller companies are not screened." % (N_US, N_EU)]
    out.update({"funnel": funnel, "fails_by_check": fails, "rows": rows[:FINALISTS], "added": added, "runtime_s": int(time.time() - t0),
                "method": "Stage 1: two years of daily prices for every share on the list (trend and momentum). Stage 2: company statements and the last earnings report for "
                          "the shares above their 200-day average (value, quality, earnings drift). Stage 3: insider trades and well-known holders for those passing at "
                          "least three of the first five checks. A share qualifies with five of seven, and the trend check must be one of them.",
                "sources": "Nasdaq (share list, statements, earnings), CNBC (prices), OpenInsider (insider trades), Dataroma (well-known holders)."})
    E.wj("state/screen.json", out)
    print("screen ok: %d screened, %d with prices, %d in an upward trend, %d with statements, %d fully scored, %d qualify, %d handed on, %ds" % (
        len(names), funnel["with_prices"], funnel["upward_trend"], funnel["with_statements"], len(rows), funnel["qualify"], len(added), out["runtime_s"]))


if __name__ == "__main__":
    main()
