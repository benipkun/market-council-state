# Market Council research engine: one research card per ticker (news, analysts, filings, earnings,
# insiders, big holders) and a five-year cash-flow valuation with every assumption shown.
# Free public sources only (Nasdaq, OpenInsider, Dataroma). It prepares numbers; it places no orders.
import datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request

NL = chr(10)
ROOT = os.environ.get("MC_ROOT", ".")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HEAD = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}
NQ = "https://api.nasdaq.com/api/"
ERP = 0.05
TERMINAL_G = 0.025
TAX = 0.21


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(d=None):
    return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def rj(rel, default=None):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def wtext(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def wj(rel, obj):
    wtext(rel, json.dumps(obj, separators=(",", ":"), ensure_ascii=True) + NL)


def get(url, as_json=True):
    req = urllib.request.Request(url, headers=HEAD)
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = resp.read(1500000).decode("utf-8", "replace")
    time.sleep(0.35)
    return json.loads(body) if as_json else body


def nq(path):
    try:
        return (get(NQ + path) or {}).get("data")
    except Exception:
        return None


def num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).replace("$", "").replace(",", "").replace("%", "").strip()
    if t in ("", "--", "N/A", "NA"):
        return None
    try:
        return float(t)
    except Exception:
        return None


def r(x, n=4):
    return None if x is None else round(float(x), n)


def mdy(s):
    try:
        m, d, y = str(s).split("/")
        return "%04d-%02d-%02d" % (int(y), int(m), int(d))
    except Exception:
        return None


def table(t):
    out = {}
    if not t:
        return out, []
    heads = [v for k, v in (t.get("headers") or {}).items()][1:]
    for row in t.get("rows") or []:
        vals = list(row.values())
        if vals and vals[0]:
            out[str(vals[0]).strip()] = [num(v) for v in vals[1:]]
    return out, [mdy(h) for h in heads]


# ------------------------------------------------------------ valuation (item 8)
def dcf(tk, fin, price, shares, beta, rf, meta):
    if not fin:
        return {"status": "not valued", "reason": "no financial statements from the source"}
    if meta.get("sector") == "Financials":
        return {"status": "not valued", "reason": "a cash-flow model does not fit a lender; its value depends on its loan book"}
    if meta.get("cls", "Equity") != "Equity":
        return {"status": "not valued", "reason": "funds are not valued this way"}
    inc, years = table(fin.get("incomeStatementTable"))
    bal, _ = table(fin.get("balanceSheetTable"))
    cf, _ = table(fin.get("cashFlowTable"))

    def g(tbl, key, i=0):
        v = tbl.get(key) or []
        return v[i] if len(v) > i and v[i] is not None else None
    rev = [x for x in (inc.get("Total Revenue") or []) if x]
    ebit0, rev0 = g(inc, "Operating Income"), g(inc, "Total Revenue")
    if len(rev) < 3 or not rev0 or ebit0 is None or not price or not shares:
        return {"status": "not valued", "reason": "too little history, or price or share count missing"}
    foreign = meta.get("country") not in (None, "United States")
    cagr = (rev[0] / rev[-1]) ** (1.0 / (len(rev) - 1)) - 1
    g1 = min(0.25, max(0.02, cagr))
    margin = ebit0 / rev0
    margins = [a / b for a, b in zip(inc.get("Operating Income") or [], inc.get("Total Revenue") or []) if a is not None and b]
    capex = abs(g(cf, "Capital Expenditures") or 0.0) / rev0
    da = abs(g(cf, "Depreciation") or 0.0) / rev0
    rec0, rec1, rev1 = g(bal, "Net Receivables"), g(bal, "Net Receivables", 1), g(inc, "Total Revenue", 1)
    nwc = 0.05
    if rec0 is not None and rec1 is not None and rev1 and rev0 != rev1:
        nwc = min(0.25, max(0.0, (rec0 - rec1) / (rev0 - rev1)))
    wacc = min(0.12, max(0.07, rf + (beta if beta is not None else 1.0) * ERP))
    debt = (g(bal, "Long-Term Debt") or 0.0) + (g(bal, "Short-Term Debt / Current Portion of Long-Term Debt") or 0.0)
    cash = (g(bal, "Cash and Cash Equivalents") or 0.0) + (g(bal, "Short-Term Investments") or 0.0)
    A = {"growth_start": r(g1), "growth_end": r(TERMINAL_G + 0.015), "ebit_margin": r(margin), "tax_rate": TAX, "capex_pct_revenue": r(capex),
         "da_pct_revenue": r(da), "working_capital_pct_of_growth": r(nwc), "wacc": r(wacc), "terminal_growth": TERMINAL_G,
         "net_debt": r(debt - cash, 0), "shares": r(shares, 0), "base_revenue": r(rev0, 0), "units": "thousands, as reported by the source"}

    def run(a):
        rows, prev, pv = [], a["base_revenue"], 0.0
        for y in range(1, 6):
            gr = a["growth_start"] + (a["growth_end"] - a["growth_start"]) * (y - 1) / 4.0
            rv = prev * (1 + gr)
            ebit = rv * a["ebit_margin"]
            tax = max(0.0, ebit) * a["tax_rate"]
            fcf = ebit - tax + rv * a["da_pct_revenue"] - rv * a["capex_pct_revenue"] - (rv - prev) * a["working_capital_pct_of_growth"]
            pv += fcf / (1 + a["wacc"]) ** y
            rows.append({"year": y, "growth": r(gr), "revenue": r(rv, 0), "ebit": r(ebit, 0), "tax": r(tax, 0),
                         "capex": r(rv * a["capex_pct_revenue"], 0), "working_capital": r((rv - prev) * a["working_capital_pct_of_growth"], 0), "fcf": r(fcf, 0)})
            prev = rv
        tv = rows[-1]["fcf"] * (1 + a["terminal_growth"]) / (a["wacc"] - a["terminal_growth"])
        ev = pv + tv / (1 + a["wacc"]) ** 5
        eq = ev - a["net_debt"]
        return rows, tv, ev, eq / a["shares"] if a["shares"] else None
    rows, tv, ev, fair = run(A)
    if fair is None or fair <= 0:
        return {"status": "not meaningful", "as_of": iso(), "assumptions": A,
                "reason": "At today's operating margin (%.1f%%) the forecast cash flows do not cover the net debt, so the model gives no positive value. That says the business must improve its margins for the shares to be worth anything on cash flow; it is not a price target." % (100 * margin)}
    sens = []
    for dw in (-0.01, 0.0, 0.01):
        line = []
        for dg in (-0.005, 0.0, 0.005):
            b = dict(A)
            b["wacc"], b["terminal_growth"] = A["wacc"] + dw, A["terminal_growth"] + dg
            line.append(r(run(b)[3], 2))
        sens.append(line)
    risks = []
    ni, tx = g(inc, "Net Income"), g(inc, "Income Tax")
    if ni and tx is not None and tx < 0:
        risks.append("Reported profit includes a tax gain of %s; price-to-earnings and earnings-based fair values overstate the business. This model uses operating profit taxed at %d%% instead." % (("$%.1fbn" % (-tx / 1e6)) if -tx >= 1e6 else ("$%.0fm" % (-tx / 1e3)), int(TAX * 100)))
    if any(m < 0 for m in margins):
        risks.append("Operating profit was negative in at least one of the last %d years, so the margin assumption has a short record." % len(margins))
    if tv / (1 + A["wacc"]) ** 5 > 0.75 * ev:
        risks.append("More than three quarters of the value sits in the years after the forecast; small changes in growth or discount rate move it a lot (see the sensitivity table).")
    if g1 >= 0.15:
        risks.append("The model starts from %.0f%% growth because that is the recent pace; it may not last." % (100 * g1))
    if foreign:
        risks.append("Foreign company: the statements may be in another currency than the share price, so the per-share comparison is not shown.")
    out = {"status": "valued", "as_of": iso(), "statement_years": years, "assumptions": A, "forecast": rows, "terminal_value": r(tv, 0),
           "enterprise_value": r(ev, 0), "fair_value_per_share": None if foreign else r(fair * 1000.0 / 1000.0, 2), "price": r(price, 2),
           "margin_of_safety": None if foreign or not fair or fair <= 0 else r(1 - price / fair),
           "sensitivity": {"wacc": [r(A["wacc"] - 0.01), r(A["wacc"]), r(A["wacc"] + 0.01)], "terminal_growth": [r(TERMINAL_G - 0.005), TERMINAL_G, r(TERMINAL_G + 0.005)], "fair_value": None if foreign else sens},
           "risks": risks,
           "method": "Five years of free cash flow = operating profit less tax, plus depreciation, less capital spending and working capital; then a terminal value; discounted at the stated rate; less net debt; divided by shares. Every input is listed under assumptions and is an estimate.",
           "source": "Nasdaq company financials (annual), share count from Nasdaq market value / price"}
    lines = ["Market Council valuation," + tk, "Assumption,Value"] + [k + "," + str(v) for k, v in A.items()]
    lines += ["", "Year,Growth,Revenue,EBIT,Tax,Capex,Working capital,Free cash flow"]
    lines += [",".join(str(x[k]) for k in ("year", "growth", "revenue", "ebit", "tax", "capex", "working_capital", "fcf")) for x in rows]
    lines += ["", "Terminal value," + str(out["terminal_value"]), "Enterprise value," + str(out["enterprise_value"]), "Fair value per share," + str(out["fair_value_per_share"]), "Price," + str(out["price"])]
    wtext("research/cards/" + tk + "-valuation.csv", NL.join(lines) + NL)
    return out


# ------------------------------------------------------------ insiders with both dates (item 10)
def openinsider(tk):
    try:
        html = get("http://openinsider.com/screener?s=" + urllib.parse.quote(tk) + "&fd=365&cnt=40", as_json=False)
    except Exception:
        return None
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 12 and re.match(r"^\d{4}-\d{2}-\d{2}", cells[1]) and re.match(r"^\d{4}-\d{2}-\d{2}$", cells[2]):
            out.append({"filed": cells[1][:10], "traded": cells[2], "insider": cells[4][:60], "title": cells[5][:40], "type": cells[6][:30],
                        "price": num(cells[7]), "shares": num(cells[8]), "value": num(cells[11])})
    return out


def dataroma(tk, tries=2):
    out = None
    for attempt in range(tries):
        try:
            html = get("https://www.dataroma.com/m/stock.php?sym=" + urllib.parse.quote(tk), as_json=False)
        except Exception:
            if attempt + 1 < tries:
                time.sleep(3)
            continue
        out = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) >= 4 and "holdings.php" in row:
                out.append({"investor": cells[1][:70], "pct_of_their_portfolio": num(cells[2]), "recent_activity": cells[3][:40], "shares": num(cells[4]) if len(cells) > 4 else None})
        if out:
            return out[:12]
        if attempt + 1 < tries:
            time.sleep(3)
    return out


def price_move(tk, date, days):
    try:
        rows = [ln.split(",") for ln in open(os.path.join(ROOT, ".cache", "prices", tk + ".csv"), encoding="utf-8").read().split(NL) if "," in ln]
        idx = [i for i, x in enumerate(rows) if x[0] >= date]
        if not idx or idx[0] == 0 or idx[0] + days - 1 >= len(rows):
            return None
        return r(float(rows[idx[0] + days - 1][1]) / float(rows[idx[0] - 1][1]) - 1)
    except Exception:
        return None


# ------------------------------------------------------------ one card per ticker (items 7, 9, 10)
def card(tk, meta, quant):
    a = (quant.get("assets") or {}).get(tk, {})
    cls = "etf" if meta.get("cls", "Equity") != "Equity" else "stocks"
    c = {"ticker": tk, "as_of": iso(), "name": meta.get("name") or tk, "sources": []}
    info = nq("quote/" + tk + "/info?assetclass=" + cls) or {}
    prim = info.get("primaryData") or {}
    price = num(prim.get("lastSalePrice")) or a.get("last")
    c["quote"] = {"price": r(price, 2), "change_pct": num(prim.get("percentageChange")), "as_of": prim.get("lastTradeTimestamp"), "source": "Nasdaq"}
    if cls != "stocks":
        c["note"] = "Fund: analyst, insider and valuation sections do not apply."
        return c
    summ = ((nq("quote/" + tk + "/summary?assetclass=stocks") or {}).get("summaryData") or {})
    mcap = num((summ.get("MarketCap") or {}).get("value"))
    shares = mcap / price / 1000.0 if mcap and price else None
    tp = (nq("analyst/" + tk + "/targetprice") or {}).get("consensusOverview") or {}
    rt = nq("analyst/" + tk + "/ratings") or {}
    if tp:
        c["analysts"] = {"rating": rt.get("meanRatingType"), "buy": tp.get("buy"), "hold": tp.get("hold"), "sell": tp.get("sell"), "target_low": tp.get("lowPriceTarget"),
                         "target_mean": tp.get("priceTarget"), "target_high": tp.get("highPriceTarget"),
                         "upside": r(tp["priceTarget"] / price - 1) if tp.get("priceTarget") and price else None,
                         "brokers": len(rt.get("brokerNames") or []), "source": "Nasdaq analyst research", "as_of": iso()[:10]}
    news = (nq("news/topic/articlebysymbol?q=" + tk.lower() + "%7Cstocks&offset=0&limit=6&fallback=false") or {}).get("rows") or []
    c["news"] = [{"title": str(n.get("title"))[:160], "date": str(n.get("created") or n.get("ago") or "")[:24], "publisher": n.get("publisher"),
                  "url": "https://www.nasdaq.com" + str(n.get("url") or "")} for n in news[:6]]
    frows = (nq("company/" + tk + "/sec-filings?limit=40&sortColumn=filed&sortOrder=desc") or {}).get("rows") or []
    if not frows:
        frows = (nq("company/" + tk + "/sec-filings?limit=6&sortColumn=filed&sortOrder=desc") or {}).get("rows") or []
    # company announcements first; insider forms (3, 4, 5, 144) are covered by the smart-money block
    fmain = [x for x in frows if str(x.get("formType") or "").upper().split("/")[0] not in ("3", "4", "5", "144", "CERT")]

    def fwhat(x):
        link = str((x.get("view") or {}).get("htmlLink") or "")
        return (urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("formDescription") or [None])[0]
    c["filings"] = [{"form": x.get("formType"), "what": fwhat(x), "filed": mdy(x.get("filed")), "period": mdy(x.get("period")), "company": x.get("companyName"),
                     "url": ((x.get("view") or {}).get("htmlLink"))} for x in (fmain or frows)[:6]]
    es = ((nq("company/" + tk + "/earnings-surprise") or {}).get("earningsSurpriseTable") or {}).get("rows") or []
    hist = [{"quarter": x.get("fiscalQtrEnd"), "reported": mdy(x.get("dateReported")), "eps": num(x.get("eps")), "consensus": num(x.get("consensusForecast")),
             "surprise_pct": num(x.get("percentageSurprise"))} for x in es[:4]]
    fc = ((nq("analyst/" + tk + "/earnings-forecast") or {}).get("quarterlyForecast") or {}).get("rows") or []
    nxt = [{"quarter": x.get("fiscalEnd"), "consensus_eps": num(x.get("consensusEPSForecast")), "estimates": num(x.get("noOfEstimates")),
            "revisions_up": num(x.get("up")), "revisions_down": num(x.get("down"))} for x in fc[:2]]
    if hist:
        last = hist[0]
        c["earnings"] = {"history": hist, "next": nxt, "source": "Nasdaq earnings",
                         "review": {"quarter": last["quarter"], "reported": last["reported"], "eps": last["eps"], "consensus": last["consensus"], "surprise_pct": last["surprise_pct"],
                                    "move_1d": price_move(tk, last["reported"] or "", 1), "move_5d": price_move(tk, last["reported"] or "", 5),
                                    "beats_in_last_4": len([h for h in hist if (h["surprise_pct"] or 0) > 0]),
                                    "limits": "Numbers only: results against forecasts and the price reaction. The call itself has not been read."}}
    # A source that does not answer in one run must not wipe what it said before: keep the last good copy for up to 100 days and say so.
    oldc = rj("research/cards/" + tk + ".json", {}) or {}
    olds = oldc.get("smart_money") or {}

    def fresh(block):
        at = str((block or {}).get("as_of") or oldc.get("as_of") or "")
        try:
            return (now() - datetime.datetime.strptime(at[:10], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)).days <= 100, at
        except Exception:
            return False, at
    oi, oi_at, oi_kept = openinsider(tk), iso(), False
    if oi is None and (olds.get("insiders") or {}).get("trades"):
        ok, at = fresh(olds["insiders"])
        if ok:
            oi, oi_at, oi_kept = olds["insiders"]["trades"], at, True
    kh, kh_at, kh_kept = dataroma(tk), iso(), False
    if not kh and (olds.get("known_investors") or {}).get("holders"):
        ok, at = fresh(olds["known_investors"])
        if ok:
            kh, kh_at, kh_kept = olds["known_investors"]["holders"], at, True
    inst = nq("company/" + tk + "/institutional-holdings?limit=8&type=TOTAL&sortColumn=marketValue&sortOrder=DESC") or {}
    own = (inst.get("ownershipSummary") or {})
    holders = ((inst.get("holdingsTransactions") or {}).get("table") or {}).get("rows") or []
    cut = (now() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    buys = [x for x in (oi or []) if x["type"].startswith("P") and x["traded"] >= cut]
    sells = [x for x in (oi or []) if x["type"].startswith("S") and x["traded"] >= cut]
    c["smart_money"] = {"insiders": {"trades": (oi or [])[:12], "open_market_buys_90d": len(buys), "open_market_sales_90d": len(sells),
                                     "buy_value_90d": r(sum(x["value"] or 0 for x in buys), 0), "sale_value_90d": r(sum(abs(x["value"] or 0) for x in sells), 0),
                                     "source": "OpenInsider (SEC Form 4): filing date and trade date" if oi is not None else None, "as_of": oi_at, "kept": oi_kept},
                        "institutions": {"held_pct": num((own.get("SharesOutstandingPCT") or {}).get("value")),
                                         "top": [{"holder": h.get("ownerName"), "shares": num(h.get("sharesHeld")), "change": num(h.get("sharesChange")), "as_of": mdy(h.get("date"))} for h in holders[:8]],
                                         "source": "Nasdaq institutional holdings (13F filings, quarterly, up to 45 days late)"},
                        "known_investors": {"holders": kh, "source": "Dataroma (13F filings of well-known investors, quarterly)", "as_of": kh_at, "kept": kh_kept},
                        "politicians": {"status": "not available", "reason": "no free source of congressional trades answers from GitHub's servers"}}
    beta = a.get("beta_1y")
    rf = (quant.get("opt") or {}).get("rf") or 0.04
    c["valuation"] = dcf(tk, nq("company/" + tk + "/financials?frequency=1"), price, shares, beta, rf, meta)
    return c


def main():
    uni = (rj("ops/engine/universe.json", {}) or {}).get("assets", {})
    quant = rj("state/quant.json", {}) or {}
    snap = rj("treasury/snapshot.json", {}) or {}
    tks = []
    for t in [p.get("ticker") for p in snap.get("positions", [])] + [k.get("ticker") for k in (rj("state/known_companies.json", {}) or {}).get("tickers", [])] \
            + [t.get("ticker") for t in (rj("state/theses.json", {}) or {}).get("theses", [])]:
        if t and t not in tks and (uni.get(t, {}).get("cls", "Equity") == "Equity"):
            tks.append(t)
    # the best names from the daily wide screen get a full card too, so the scorecard and the decision desk can use them
    watch, smeta = set(tks), {}
    for a in ((rj("state/screen.json", {}) or {}).get("added") or [])[:10]:
        t = str(a.get("t") or "")
        if re.fullmatch(r"[A-Z]{1,5}", t) and t not in tks:
            tks.append(t)
            smeta[t] = {"name": str(a.get("name") or t)[:60], "sector": "Financials" if a.get("sector") == "Finance" else a.get("sector"),
                        "country": a.get("country") or "United States", "cls": "Equity"}
            # the screen measured this share's beta from a year of prices; use it, so the card values the share the way the screen did
            if isinstance(a.get("beta"), (int, float)) and "beta_1y" not in (quant.setdefault("assets", {}).setdefault(t, {})):
                quant["assets"][t]["beta_1y"] = float(a["beta"])
    index, alerts = [], []
    held = set(p.get("ticker") for p in snap.get("positions", []))
    for t in tks:
        try:
            c = card(t, uni.get(t) or smeta.get(t) or {"name": t}, quant)
        except Exception as e:
            c = {"ticker": t, "as_of": iso(), "error": str(e)[:160]}
        wj("research/cards/" + t + ".json", c)
        v = c.get("valuation") or {}
        sm = (c.get("smart_money") or {}).get("insiders") or {}
        index.append({"t": t, "as_of": c["as_of"], "held": t in held, "source": "watchlist" if t in watch else "wide screen", "name": c.get("name"),
                      "valued": v.get("status") == "valued", "fair": v.get("fair_value_per_share"),
                      "mos": v.get("margin_of_safety"), "rating": (c.get("analysts") or {}).get("rating"), "target": (c.get("analysts") or {}).get("target_mean"),
                      "insider_buys_90d": sm.get("open_market_buys_90d"), "insider_sales_90d": sm.get("open_market_sales_90d"), "error": c.get("error")})
        recent = (now() - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
        for x in (sm.get("trades") or []):
            big = abs(x.get("value") or 0) >= 250000
            if x["filed"] >= recent and big and (x["type"].startswith("P") or (x["type"].startswith("S") and t in held)):
                alerts.append({"id": t + ":" + x["filed"] + ":" + x["insider"][:20], "ticker": t, "what": x["type"], "insider": x["insider"], "title": x["title"],
                               "traded": x["traded"], "filed": x["filed"], "value": x["value"], "held": t in held})
    wj("research/cards/index.json", {"as_of": iso(), "cards": index, "note": "one file per ticker next to this one"})
    wj("state/smart_money.json", {"as_of": iso(), "alerts": alerts,
                                  "rule": "Listed here: an insider's open-market purchase of 250,000 dollars or more in any watched company, or an open-market sale of that size in a company you hold, filed in the last 14 days."})
    print("research ok:", len(index), "cards,", len([i for i in index if i["valued"]]), "valued,", len(alerts), "alerts")


if __name__ == "__main__":
    main()
