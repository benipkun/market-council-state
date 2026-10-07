# Market Council house strategy (version 1, PAPER). It borrows concepts that hedge funds use and
# keeps only the ones a small long-only account can run: equal risk across asset classes, a trend
# rule, a volatility cap, and a seven-point scorecard for single shares. This file back-tests the
# rules, works out what the strategy would hold today and writes state/strategy.json. It places no
# orders and does not change the decision cards; it runs on paper until Ben says otherwise.
import math
import os
import re
import time

import numpy as np

import engine as E
import lab

VERSION = "1.0"
COST = 0.0025
TREND, VOLDAYS, WARM = 200, 60, 252
CORE_TARGET = {1: 0.06, 2: 0.08, 3: 0.10, 4: 0.12, 5: 0.15}
EDGE_MAX = 0.30
EDGE_PASS = 5
# ticker, plain name, income left out of the price series (estimate), EU-listed equivalent
CORE = [("SPY", "US shares", ("flat", 0.018), "CSPX or VUAA"),
        ("EFA", "Shares outside the US", ("flat", 0.028), "EXUS or IWDA (world)"),
        ("IEF", "US Treasuries 7-10 years", ("yield", "US10Y"), "IBTM or CBU0"),
        ("GLD", "Gold", ("flat", 0.0), "IGLN or SGLN")]
SAFE = ("SHY", "Short US Treasuries (the parking place)", ("yield", "US2Y"), "IBTS or IBTA")
SHARES = (0, 1)                                            # which core columns are shares
TILT = {1: 0.0, 2: 0.15, 3: 0.30, 4: 0.50, 5: 0.70}        # extra weight moved towards shares, by risk level
MARGIN = 0.8                                               # a candidate's worst fall must stay within this share of the maximum loss
BASES = {"equal": "Give each of the four the same money.",
         "rp": "Give each of the four the same share of the risk, not the same money: the calmer an asset has been over 60 days, the more of it.",
         "tilt": "Start from equal risk for the four, then move %s of the money towards the two share funds, because your risk level allows it."}


def rules_for(base, trend, tgt, tilt, note):
    r = [{"rule": "Spread the core over four different things: US shares, shares outside the US, government bonds and gold.",
          "from": "All-weather thinking: hold assets that do well in different climates (growth, recession, inflation)."},
         {"rule": BASES[base] % E.pc(tilt, 0) if base == "tilt" else BASES[base],
          "from": "Risk parity, without the borrowing that funds add on top." if base != "equal" else "Plain diversification."}]
    if trend:
        r.append({"rule": "At each month end, hold an asset only if its price is above its 200-day average. Otherwise its share waits in short Treasuries.",
                  "from": "Trend following, the core rule of managed-futures funds."})
    r.append({"rule": "If the mix's estimated volatility is above %s a year (the cap for your risk level), shrink everything in proportion and park the rest." % E.pc(tgt, 0),
              "from": "Volatility targeting."})
    r.append({"rule": "Single shares get at most %s in total, and only those passing at least %d of 7 checks, always including an upward trend." % (E.pc(EDGE_MAX, 0), EDGE_PASS),
              "from": "Value, quality, momentum, insider buying, well-known holders and earnings drift, used as one scorecard."})
    r.append({"rule": "Size every share by the loss you accept if its stop is hit, never by conviction, and never above the one-company limit.",
              "from": "Risk limits as multi-manager funds apply them to each bet."})
    r.append({"rule": "Change the mix once a month, not in between, unless the doomsday protocol says otherwise.",
              "from": "Low turnover: costs are the one certain number in any strategy."})
    for i, x in enumerate(r):
        x["n"] = i + 1
    return r, note

CONCEPTS = [
    {"name": "Trend following", "who": "Managed-futures funds", "use": "yes",
     "idea": "What has been rising for months tends to keep rising for a while, and the same for falling. Hold what is above its long average; step aside from what is below.",
     "evidence": "Moskowitz, Ooi and Pedersen (2012); Faber (2007).", "ours": "Rule 3 of the core."},
    {"name": "Risk parity", "who": "All-weather style funds", "use": "yes",
     "idea": "Size positions so each brings the same risk. Bonds then get more money than shares. Funds borrow to lift the return; we do not.",
     "evidence": "Widely documented; the unborrowed version gives smaller swings and a lower return.", "ours": "Rule 2 of the core."},
    {"name": "Volatility targeting", "who": "Systematic funds of every kind", "use": "yes",
     "idea": "Cut exposure when markets turn violent. Violent markets have not paid enough extra to justify staying fully in.",
     "evidence": "Moreira and Muir (2017).", "ours": "Rule 4 of the core."},
    {"name": "Value with a margin of safety", "who": "Fundamental long-term funds", "use": "yes",
     "idea": "Buy only well below your own estimate of what the business is worth.",
     "evidence": "Asness, Moskowitz and Pedersen (2013).", "ours": "Scorecard check, using our own cash-flow valuation."},
    {"name": "Momentum between shares", "who": "Quant equity funds", "use": "yes",
     "idea": "Shares that beat the market over the past year (leaving out the latest month) tend to keep beating it for some months.",
     "evidence": "Jegadeesh and Titman (1993).", "ours": "Scorecard check."},
    {"name": "Quality", "who": "Quant and fundamental funds", "use": "yes",
     "idea": "Profitable, steady businesses have earned more than their risk suggests.",
     "evidence": "Asness, Frazzini and Pedersen (Quality minus junk).", "ours": "Scorecard check (operating margin)."},
    {"name": "Insider purchases", "who": "Event and fundamental funds", "use": "yes",
     "idea": "Executives buying their own shares in the open market with their own money is informative; their sales say little.",
     "evidence": "Lakonishok and Lee (2001).", "ours": "Scorecard check, from Form 4 filings."},
    {"name": "Copying well-known investors", "who": "Anyone reading 13F filings", "use": "partly",
     "idea": "Follow the large, slow positions of chosen long-term managers. The filings are up to 45 days late, so it only works for patient holders.",
     "evidence": "Mixed; works best for concentrated, low-turnover managers.", "ours": "Scorecard check, never a reason on its own."},
    {"name": "Earnings drift", "who": "Quant equity funds", "use": "yes",
     "idea": "After a clear earnings surprise the price tends to keep drifting the same way for weeks.",
     "evidence": "Bernard and Thomas (1989).", "ours": "Scorecard check."},
    {"name": "Hard risk limits per bet", "who": "Multi-manager funds", "use": "yes",
     "idea": "Every bet has a loss limit and a size cap; risk is cut after losses; many unrelated bets beat a few big ones.",
     "evidence": "Industry practice rather than a paper.", "ours": "Rule 6, the maximum-loss line, the position caps and the correlation table."},
    {"name": "Long/short and market-neutral", "who": "Equity hedge funds", "use": "not now",
     "idea": "Own the best shares, sell short the worst, and earn the gap whatever the market does.",
     "evidence": "Works only with cheap borrowing and tight risk control.", "ours": "Needs short selling, which your broker and profile do not allow. The lowest scores are an avoid list instead."},
    {"name": "Global macro", "who": "Macro funds", "use": "partly",
     "idea": "Large views on interest rates, currencies and commodities, usually through futures.",
     "evidence": "Depends on the manager, not on a rule.", "ours": "The trend rule across asset classes is the systematic part. Judgement bets are left out."},
    {"name": "Merger arbitrage", "who": "Event-driven funds", "use": "not now",
     "idea": "Buy a company after a takeover is announced and earn the gap to the deal price. Small steady gains, a large loss when a deal breaks.",
     "evidence": "Mitchell and Pulvino (2001).", "ours": "Needs many deals at once to be safe. Could be added later as a watch list of announced deals."},
    {"name": "Statistical arbitrage", "who": "High-turnover quant funds", "use": "no",
     "idea": "Thousands of tiny, short-lived price gaps traded with borrowed money at almost no cost.",
     "evidence": "The edge is in speed, scale and cost.", "ours": "Out of reach: our costs per trade are larger than the gaps."},
    {"name": "Carry and selling volatility", "who": "Macro and volatility funds", "use": "no",
     "idea": "Collect a steady yield or option premium and accept a rare, sudden large loss.",
     "evidence": "Steady until it is not.", "ours": "Needs derivatives and borrowing. The only carry we take is the yield on short Treasuries."},
    {"name": "Tail hedging", "who": "Crash-protection funds", "use": "not now",
     "idea": "Pay a small regular cost for options that pay off hugely in a crash.",
     "evidence": "Costly in normal years by design.", "ours": "Needs options. Bonds, gold, the trend rule and the doomsday protocol stand in for it."},
    {"name": "Sizing by edge (Kelly)", "who": "Quant traders", "use": "partly",
     "idea": "Bet more when the edge is larger and the outcome surer; in practice only a fraction, because the edge is never known exactly.",
     "evidence": "Thorp's work on the Kelly criterion.", "ours": "Our sizing is the cautious relative: a fixed small loss per idea."}]


def r4(x, n=4):
    return E.rd(x, n)


def hist(sym):
    path = os.path.join(E.CACHE, "s_" + re.sub("[^A-Za-z0-9]", "_", sym) + ".csv")
    rows = []
    if not E.OFFLINE:
        try:
            rows = E.fetch_cnbc(sym, 946684800)
            if len(rows) > 1000:
                os.makedirs(E.CACHE, exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(E.NL.join(d + "," + ("%.4f" % v) for d, v in rows) + E.NL)
            time.sleep(0.3)
        except Exception:
            rows = []
    if len(rows) <= 1000:
        try:
            with open(path, encoding="utf-8") as f:
                rows = [(x.split(",")[0], float(x.split(",")[1])) for x in f.read().split(E.NL) if "," in x]
        except Exception:
            rows = []
    return rows


def build():
    cols = CORE + [SAFE]
    H = {a[0]: dict(hist(a[0])) for a in cols}
    if any(len(H[a[0]]) < 1500 for a in cols):
        return None
    dates = sorted(set.intersection(*[set(H[a[0]]) for a in cols]))
    P = np.array([[H[a[0]][d] for a in cols] for d in dates], dtype=float)
    R = P[1:] / P[:-1] - 1
    inc, missing = np.zeros_like(R), []
    for j, a in enumerate(cols):
        kind, val = a[2]
        if kind == "flat":
            inc[:, j] = val / 252.0
        else:
            ys = hist(val)
            if not ys:
                missing.append(val)
                continue
            k, last = 0, ys[0][1]
            for i, d in enumerate(dates[1:]):
                while k < len(ys) and ys[k][0] <= d:
                    last = ys[k][1]
                    k += 1
                inc[i, j] = max(0.0, last) / 100.0 / 252.0
    return dates[1:], P[1:], R + inc, missing


def target_at(i, P, R, spec):
    n = R.shape[1] - 1
    vd = spec.get("vold", VOLDAYS)
    vol = np.std(R[i - vd + 1:i + 1, :n], axis=0, ddof=1) * math.sqrt(252)
    if spec.get("fixed") is not None:
        tw = np.array(spec["fixed"], dtype=float)
    else:
        tw = (1 / vol) / np.sum(1 / vol)
        if spec.get("tilt"):
            sh = np.array([1.0 / vol[j] if j in SHARES else 0.0 for j in range(n)])
            tw = (1 - spec["tilt"]) * tw + spec["tilt"] * sh / np.sum(sh)
    info = {"rp": tw.copy(), "vol": vol, "on": np.ones(n, dtype=bool), "avg": np.mean(P[i - TREND + 1:i + 1, :n], axis=0), "scale": 1.0, "est_vol": None}
    if spec.get("trend"):
        tr = spec["trend"]
        info["avg"] = np.mean(P[i - tr + 1:i + 1, :n], axis=0)
        info["on"] = P[i, :n] > info["avg"]
        tw = tw * info["on"]
    if spec.get("target"):
        S = np.cov(R[i - vd + 1:i + 1, :n], rowvar=False) * 252
        pv = math.sqrt(max(0.0, float(tw @ S @ tw)))
        info["est_vol"] = pv
        if pv > spec["target"]:
            info["scale"] = spec["target"] / pv
            tw = tw * info["scale"]
    return tw, info


def simulate(dates, P, R, spec):
    T, n = R.shape[0], R.shape[1] - 1
    ends = set(i for i in range(T - 1) if dates[i][:7] != dates[i + 1][:7])
    w, _ = target_at(WARM - 1, P, R, spec)
    ws, val, turn = 1.0 - float(np.sum(w)), 1.0 - COST * 1.0, 0.0
    eq, safe = np.empty(T - WARM), np.empty(T - WARM)
    for i in range(WARM, T):
        g = w * (1 + R[i, :n])
        gs = ws * (1 + R[i, n])
        tot = float(np.sum(g) + gs)
        val *= tot
        w, ws = g / tot, gs / tot
        if i in ends:
            tw, _ = target_at(i, P, R, spec)
            d = float(np.sum(np.abs(tw - w)) + abs((1 - np.sum(tw)) - ws))
            val *= 1 - COST * d
            turn += d
            w, ws = tw, 1.0 - float(np.sum(tw))
        eq[i - WARM], safe[i - WARM] = val, ws
    return eq, safe, turn


def measure(eq, safe_w, turn, rsafe):
    st = lab.stats(eq)
    full = np.insert(eq, 0, 1.0)
    r = full[1:] / full[:-1] - 1
    ex = r - rsafe
    yrs, h = len(eq) / 252.0, len(eq) // 2
    st["sharpe"] = r4(float(np.mean(ex) / np.std(ex, ddof=1) * math.sqrt(252)) if np.std(ex) > 0 else None, 2)
    st["turnover_year"] = r4(turn / yrs, 2)
    st["avg_parked"] = r4(float(np.mean(safe_w)), 3)
    a, b = np.insert(eq[:h], 0, 1.0), eq[h - 1:] / eq[h - 1]
    st["h1_cagr"], st["h2_cagr"] = r4(a[-1] ** (252.0 / h) - 1), r4(b[-1] ** (252.0 / (len(eq) - h)) - 1)
    st["h1_mdd"], st["h2_mdd"] = r4(float(np.min(a / np.maximum.accumulate(a) - 1))), r4(float(np.min(b / np.maximum.accumulate(b) - 1)))
    return st


def backtest(data, tgt, tilt, max_loss, keep, keep_why=None):
    dates, P, R, missing = data
    n = len(CORE)
    rsafe, rows, curves = R[WARM:, n], [], {}

    def run(vid, name, what, spec, extra):
        eq, sw, turn = simulate(dates, P, R, spec)
        m = measure(eq, sw, turn, rsafe)
        m.update({"id": vid, "name": name, "what": what})
        m.update(extra)
        rows.append(m)
        idx, vals = lab.sample(eq, 110)
        curves[vid] = vals
        curves["dates"] = [dates[WARM - 1 + int(i)] for i in idx]
        return m
    run("spy", "S&P 500 fund, held", "All the money in US shares.", {"fixed": [1, 0, 0, 0]}, {"candidate": False})
    run("sixty", "60% shares, 40% bonds", "The classic balanced mix, reset monthly.", {"fixed": [0.6, 0, 0.4, 0]}, {"candidate": False})
    specs = {}
    for base, bname, bwhat in (("equal", "Equal money", "The four assets with the same money in each."), ("rp", "Equal risk", "The four assets with the same risk in each."),
                               ("tilt", "Equal risk, tilted to shares", "Equal risk, then %s of the money moved towards the two share funds." % E.pc(tilt, 0))):
        if base == "tilt" and tilt <= 0:
            continue
        for tr in (False, True):
            spec = {"target": tgt}
            if base == "equal":
                spec["fixed"] = [1.0 / n] * n
            if base == "tilt":
                spec["tilt"] = tilt
            if tr:
                spec["trend"] = TREND
            vid = base + ("_trend" if tr else "")
            specs[vid] = spec
            run(vid, bname + (" + trend rule" if tr else ""), bwhat + (" Each is held only above its 200-day average." if tr else ""), spec,
                {"candidate": True, "base": base, "trend": tr})
    by = {r["id"]: r for r in rows}
    cands = [r for r in rows if r["candidate"]]
    limit = MARGIN * max_loss
    for r in cands:
        r["within_limit"] = bool(abs(r["mdd"]) <= limit)
    ok = [r for r in cands if r["within_limit"]]
    if keep and keep in specs:
        best = by[keep]
        why = ((keep_why or "Chosen at go-live.").split(" Kept since go-live")[0]
               + " Kept since go-live; the choice is made again only when your risk profile or the strategy version changes.")
    elif ok:
        best = max(ok, key=lambda r: r["cagr"])
        why = ("%d of the %d candidates kept their worst fall within %s, which is %s of the %s maximum loss in your profile. Of those, this one made the most."
               % (len(ok), len(cands), E.pc(limit, 0), E.pc(MARGIN, 0), E.pc(max_loss, 0)))
    else:
        best = min(cands, key=lambda r: abs(r["mdd"]))
        why = "No candidate kept its worst fall within %s (%s of your maximum loss), so the one with the smallest fall was taken." % (E.pc(limit, 0), E.pc(MARGIN, 0))
    best["chosen"] = True
    curves["core"] = curves[best["id"]]
    spec = specs[best["id"]]
    pair = by.get(best["base"] + ("" if best["trend"] else "_trend"))
    note = None
    if pair:
        a, b = (pair, best) if best["trend"] else (best, pair)
        note = ("The trend rule on this mix cut the worst fall from %s to %s and changed the yearly return from %s to %s. %s" % (
            E.pc(abs(a["mdd"]), 0), E.pc(abs(b["mdd"]), 0), E.pc(a["cagr"]), E.pc(b["cagr"]),
            "It is part of the strategy." if best["trend"] else "It is left out, because your maximum loss does not need it and it costs return."))
    grid = []
    for vd in (40, 60, 120):
        for k2 in (-1, 0, 1):
            for k3 in (-1, 0, 1):
                s2 = dict(spec)
                s2["vold"] = vd
                if best["trend"]:
                    s2["trend"] = TREND + 50 * k2
                else:
                    s2["target"] = tgt + 0.02 * k2
                if best["base"] == "tilt":
                    s2["tilt"] = max(0.0, tilt + 0.10 * k3)
                elif best["trend"]:
                    s2["target"] = tgt + 0.02 * k3
                elif k3 != 0:
                    continue
                eq, sw, turn = simulate(dates, P, R, s2)
                m = measure(eq, sw, turn, rsafe)
                grid.append((m["cagr"], m["mdd"], m["sharpe"]))
    g = np.array(grid, dtype=float)
    rob = {"runs": len(grid), "cagr": [r4(float(np.min(g[:, 0]))), r4(float(np.median(g[:, 0]))), r4(float(np.max(g[:, 0])))],
           "mdd": [r4(float(np.min(g[:, 1]))), r4(float(np.median(g[:, 1]))), r4(float(np.max(g[:, 1])))],
           "sharpe": [r4(float(np.min(g[:, 2])), 2), r4(float(np.median(g[:, 2])), 2), r4(float(np.max(g[:, 2])), 2)],
           "within_limit_share": r4(float(np.mean(np.abs(g[:, 1]) <= limit)), 3),
           "smaller_fall_than_6040": r4(float(np.mean(g[:, 1] > by["sixty"]["mdd"])), 3),
           "what": "The chosen rules re-run with nearby settings: the volatility window at 40, 60 or 120 days, and the cap, the trend window or the tilt a step lower and higher."}
    c, s, x = best, by["spy"], by["sixty"]
    verdict = ("From %s to %s the house core made %s a year against %s for the S&P 500 fund and %s for 60/40. Its worst fall was %s, against %s and %s." % (
        dates[WARM][:4], dates[-1][:4], E.pc(c["cagr"]), E.pc(s["cagr"]), E.pc(x["cagr"]), E.pc(abs(c["mdd"]), 0), E.pc(abs(s["mdd"]), 0), E.pc(abs(x["mdd"]), 0)))
    return {"from": dates[WARM], "to": dates[-1], "years": round((len(dates) - WARM) / 252.0, 1), "variants": rows, "curve": curves, "robustness": rob,
            "verdict": verdict, "cost_per_trade": COST, "volatility_cap": tgt, "fall_limit": r4(limit),
            "chosen": {"id": best["id"], "name": best["name"], "base": best["base"], "trend": best["trend"], "tilt": tilt if best["base"] == "tilt" else 0.0,
                       "why": why, "trend_note": note, "spec": spec},
            "income_note": "The price files leave out dividends and bond interest, so an estimate is added back: 1.8% a year for US shares, 2.8% for shares "
                           "outside the US, the 10-year Treasury yield for the bond fund and the 2-year yield for short Treasuries." + (
                               " Yield data missing for: " + ", ".join(missing) + "." if missing else ""),
            "method": "Daily prices from CNBC. Decisions at each month end, held to the next; every trade costs %.2f%% of the amount moved. The test starts once all four "
                      "assets and a year of history exist. Six candidate mixes are tested, all with the volatility cap; the one for your profile is picked by a rule "
                      "fixed in advance, then re-run with nearby settings to show the result does not hang on one choice." % (100 * COST),
            "limits": ["A back-test is history, not a promise; these years include a long fall in interest rates that helped bonds for most of the period.",
                       "Picking the best of six candidates flatters the winner a little, even with a rule fixed in advance.",
                       "Dividend and interest income is an estimate, so every yearly figure can be off by a few tenths of a point.",
                       "US-listed funds stand in for the EU-listed ones you would buy; currency moves against the forint are not included.",
                       "The share scorecard cannot be back-tested, because past insider, holder and valuation data were not saved. It is tracked forward on paper from today."]}


def score_checks(mos, fair, em, px, spy_mom, ins, kh, rv, next_results=None):
    # The seven checks, one place for the watchlist and the wide screen. Each failed check also says what would make it pass.
    checks = []

    def add(cid, name, ok, detail, needs):
        checks.append({"id": cid, "name": name, "pass": bool(ok) if ok is not None else None, "detail": detail, "needs": None if ok else needs})
    last = float(px[-1]) if len(px) else None
    add("value", "Price at or below our fair value", (mos >= 0) if mos is not None else None,
        ("price is %s our estimate" % ((E.pc(abs(mos), 0) + " below") if mos >= 0 else (E.pc(abs(mos), 0) + " above"))) if mos is not None else "no per-share estimate",
        ("a price at or under $%.2f, our fair value (%s from here)" % (fair, E.pc(fair / last - 1, 0))) if (fair and last and mos is not None) else
        "a per-share fair value, which the free statements do not give for this company")
    add("quality", "Operating margin of 8% or more", (em >= 0.08) if em is not None else None, ("operating margin %s" % E.pc(em, 1)) if em is not None else "no statements",
        "an operating margin of 8% or more in the next annual results" if em is not None else "company statements from the free source")
    if len(px) > 260:
        mom = px[-22] / px[-253] - 1
        add("momentum", "Beat the S&P 500 fund over 12 months (latest month left out)", mom > spy_mom, "%s against %s for the fund" % (E.pc(mom, 0), E.pc(spy_mom, 0)),
            "to gain about %s on the fund over the 12-month window" % E.pc(max(0.0, spy_mom - mom), 0))
        avg = float(np.mean(px[-200:]))
        add("trend", "Price above its 200-day average", px[-1] > avg, "price %.2f, average %.2f" % (px[-1], avg),
            "a close above $%.2f, its 200-day average (%s from here)" % (avg, E.pc(avg / px[-1] - 1, 0)))
    else:
        add("momentum", "Beat the S&P 500 fund over 12 months (latest month left out)", None, "not enough price history", "a year of price history")
        add("trend", "Price above its 200-day average", None, "not enough price history", "a year of price history")
    ins = ins or {}
    nb, bv, sv = ins.get("open_market_buys_90d"), ins.get("buy_value_90d") or 0, ins.get("sale_value_90d") or 0
    add("insiders", "Insiders bought more than they sold in 90 days", (nb >= 1 and bv > sv) if nb is not None else None,
        ("%d purchases, %d sales" % (nb, ins.get("open_market_sales_90d") or 0)) if nb is not None else "no insider data",
        "an open-market purchase by an insider larger than recent sales" if nb is not None else "insider filings, which foreign companies do not make in the US")
    if kh is not None:
        adds = [h for h in kh if str(h.get("recent_activity") or "").lower().startswith(("add", "buy"))]
        add("holders", "Two or more well-known investors hold it and one added lately", len(kh) >= 2 and len(adds) >= 1, "%d hold it, %d added or bought" % (len(kh), len(adds)),
            "the next quarterly fund filings to show two holders with one adding")
    else:
        add("holders", "Two or more well-known investors hold it and one added lately", None, "no holder data", "an answer from the holdings source")
    rv = rv or {}
    if rv.get("surprise_pct") is not None and rv.get("move_5d") is not None:
        add("drift", "Last results beat forecasts and the price rose over five days", rv["surprise_pct"] > 0 and rv["move_5d"] > 0,
            "surprise %+.0f%%, five-day move %s" % (rv["surprise_pct"], E.pc(rv["move_5d"], 1)),
            ("results on %s that beat forecasts, with a higher price five days later" % next_results) if next_results else
            "the next results to beat forecasts, with a higher price five days later")
    else:
        add("drift", "Last results beat forecasts and the price rose over five days", None, "no earnings data", "an earnings history from the free source")
    score = len([k for k in checks if k["pass"]])
    trend_ok = [k for k in checks if k["id"] == "trend"][0]["pass"] is True
    return {"score": score, "of": len(checks), "known": len([k for k in checks if k["pass"] is not None]), "qualifies": bool(score >= EDGE_PASS and trend_ok),
            "trend_ok": trend_ok, "checks": checks}


def edge_scores(ix, spy_rows, lim, held):
    rows, spy = [], [v for d, v in spy_rows]
    spy_mom = (spy[-22] / spy[-253] - 1) if len(spy) > 260 else 0.0
    tech = (E.rj("digests/latest.json", {}) or {}).get("technicals") or {}
    for c in (ix or {}).get("cards") or []:
        t = c.get("t")
        card = E.rj("research/cards/" + str(t) + ".json", {}) or {}
        px = [v for d, v in E.read_cache(t)]
        sm = card.get("smart_money") or {}
        nxt = (tech.get(t) or {}).get("next_earnings_date")
        r = score_checks(c.get("mos"), c.get("fair"), ((card.get("valuation") or {}).get("assumptions") or {}).get("ebit_margin"), px, spy_mom,
                         sm.get("insiders"), (sm.get("known_investors") or {}).get("holders"), (card.get("earnings") or {}).get("review"), nxt)
        r.update({"t": t, "held": t in held, "name": card.get("name") or t, "price": r4(float(px[-1]), 2) if px else None, "source": c.get("source") or "watchlist",
                  "mos": c.get("mos"), "fair": c.get("fair")})
        rows.append(r)
    rows.sort(key=lambda r: (-r["score"], r["t"]))
    return rows


def main():
    now = E.now_iso()
    quant, snap = E.rj("state/quant.json", {}) or {}, E.rj("treasury/snapshot.json", {}) or {}
    prev = E.rj("state/strategy.json", {}) or {}
    prof = quant.get("profile") or {}
    lim = prof.get("limits") or E.LEVELS[3]
    level = min(5, max(1, int(prof.get("risk_level") or 3)))
    max_loss = float(prof.get("max_loss_pct") or 25) / 100.0
    tgt, tilt = float(lim.get("target_vol") or CORE_TARGET[level]), TILT[level]
    key = "%s|%d|%d" % (VERSION, level, round(100 * max_loss))
    out = {"as_of": now, "version": VERSION, "status": "ok", "paper": True, "name": "House strategy", "concepts": CONCEPTS, "profile_key": key,
           "profile": {"level": level, "label": prof.get("label"), "max_loss": max_loss, "volatility_cap": tgt, "tilt": tilt}}
    data = build()
    if not data:
        out["status"] = "no price history"
        E.wj("state/strategy.json", out)
        print("strategy: no price history")
        return
    dates, P, R, missing = data
    n = len(CORE)
    same = prev.get("profile_key") == key
    bt = backtest(data, tgt, tilt, max_loss, prev.get("chosen_id") if same else None, ((prev.get("backtest") or {}).get("chosen") or {}).get("why"))
    ch = bt["chosen"]
    spec = ch.pop("spec")
    out["backtest"], out["chosen_id"] = bt, ch["id"]
    out["rules"], out["rules_note"] = rules_for(ch["base"], ch["trend"], tgt, tilt, ch.get("trend_note"))
    out["summary"] = ("A core of four asset classes (%s%s) with a volatility cap, plus up to %s in single shares that pass a seven-point scorecard. "
                      "It runs on paper: it changes no decision card until you switch it on." % (
                          {"equal": "equal money", "rp": "equal risk", "tilt": "equal risk, tilted to shares"}[ch["base"]], ", with a trend rule" if ch["trend"] else "", E.pc(EDGE_MAX, 0)))

    # what the rules say today, and what has been in force since the last month end
    ends = [i for i in range(len(dates) - 1) if dates[i][:7] != dates[i + 1][:7]]
    tw_now, info = target_at(len(dates) - 1, P, R, spec)
    tw_force, _ = target_at(ends[-1], P, R, spec)
    held = {p.get("ticker"): float(p.get("pct_nav") or 0) / 100.0 for p in snap.get("positions") or [] if p.get("ticker")}
    ix = E.rj("research/cards/index.json", {}) or {}
    edge = edge_scores(ix, E.read_cache("SPY"), lim, held)
    assets = quant.get("assets") or {}
    picks = []
    for r in edge:
        if r["qualifies"]:
            a = assets.get(r["t"]) or {}
            stop = max(0.05, 2 * float(a.get("vol_20d") or a.get("vol_1y") or 0.3) / math.sqrt(252) * math.sqrt(10))
            picks.append({"t": r["t"], "weight": min(lim["stock_cap"], lim["risk_per_trade"] / stop), "score": r["score"], "stop_pct": stop})
    tot = sum(p["weight"] for p in picks)
    if tot > EDGE_MAX:
        for p in picks:
            p["weight"] *= EDGE_MAX / tot
        tot = EDGE_MAX
    core_part = 1.0 - tot
    out["core"] = {"date": dates[-1], "in_force_since": dates[ends[-1]], "volatility_cap": tgt, "est_vol": r4(info["est_vol"]), "scale": r4(info["scale"]),
                   "trend_rule": bool(ch["trend"]),
                   "assets": [{"t": CORE[j][0], "name": CORE[j][1], "eu": CORE[j][3], "price": r4(float(P[-1, j]), 2), "avg_200d": r4(float(info["avg"][j]), 2),
                               "above_avg": bool(P[-1, j] > info["avg"][j]), "vol_60d": r4(float(info["vol"][j])), "base_weight": r4(float(info["rp"][j])),
                               "weight": r4(float(tw_now[j])), "weight_in_force": r4(float(tw_force[j]))} for j in range(n)],
                   "parked": {"t": SAFE[0], "name": SAFE[1], "eu": SAFE[3], "weight": r4(max(0.0, 1.0 - float(np.sum(tw_now)))),
                              "weight_in_force": r4(max(0.0, 1.0 - float(np.sum(tw_force))))}}
    out["edge"] = {"max": EDGE_MAX, "pass_mark": EDGE_PASS, "rows": edge,
                   "picks": [{"t": p["t"], "weight": r4(p["weight"]), "score": p["score"], "stop_pct": r4(p["stop_pct"])} for p in picks],
                   "note": "A share qualifies with %d of 7 checks passed, and the trend check must be one of them. Checks with no data count as not passed." % EDGE_PASS}
    target = [{"t": CORE[j][0], "name": CORE[j][1], "eu": CORE[j][3], "kind": "core", "weight": r4(float(tw_now[j]) * core_part)} for j in range(n)]
    target += [{"t": p["t"], "name": (assets.get(p["t"]) or {}).get("name") or p["t"], "eu": None, "kind": "share", "weight": r4(p["weight"])} for p in picks]
    target.append({"t": SAFE[0], "name": SAFE[1], "eu": SAFE[3], "kind": "parked", "weight": r4(max(0.0, 1.0 - sum(x["weight"] for x in target)))})
    out["target"] = target
    tmap = {x["t"]: x["weight"] for x in target}
    gap = [{"t": t, "now": r4(w), "target": r4(tmap.get(t, 0.0)), "in_strategy": t in tmap} for t, w in sorted(held.items(), key=lambda kv: -kv[1])]
    gap += [{"t": x["t"], "now": 0.0, "target": x["weight"], "in_strategy": True} for x in target if x["t"] not in held and x["weight"] > 0.001]
    out["holdings_gap"] = gap
    out["outside_strategy"] = r4(sum(w for t, w in held.items() if t not in tmap))

    # forward record: the rules are frozen at go-live, so everything after that date is out of sample
    go = (prev.get("go_live") if same and prev.get("chosen_id") == ch["id"] else None) or dates[-1]
    out["go_live"] = go
    track = {"since": go, "to": dates[-1]}
    d2 = dates[WARM:]
    k = max([i for i, d in enumerate(d2) if d <= go] or [len(d2) - 1])
    for vid, spec2 in (("core", spec), ("spy", {"fixed": [1, 0, 0, 0]}), ("sixty", {"fixed": [0.6, 0, 0.4, 0]})):
        eq, _, _ = simulate(dates, P, R, spec2)
        track[vid] = r4(float(eq[-1] / eq[k] - 1))
    track["days"] = len(d2) - 1 - k
    pb = [h for h in (E.rj("state/paper_book.json", {}) or {}).get("history") or [] if h.get("date") >= go]
    track["your_holdings"] = r4(pb[-1]["frozen"] / pb[0]["frozen"] - 1) if len(pb) >= 2 else None
    out["track"] = track
    E.wj("state/strategy.json", out)
    c = [v for v in bt["variants"] if v.get("chosen")][0]
    print("strategy ok: chosen %s, %s a year, worst fall %s, sharpe %s; %d shares qualify; parked %s" % (
        c["id"], E.pc(c["cagr"]), E.pc(abs(c["mdd"]), 0), c["sharpe"], len(picks), E.pc(out["core"]["parked"]["weight"], 0)))


if __name__ == "__main__":
    main()
