# Market Council testing lab: the backtester, the signals lab and the back-test of the doomsday
# protocol. History tests only: it reads saved price files and public series, writes state/lab.json
# and never places orders. Every figure is price-only (no dividends) unless a line says otherwise.
import datetime
import math
import os
import re
import time

import numpy as np

import engine as E

COST = 0.0025        # assumed cost of each trade (spread plus fees), charged on the amount traded
WARM = 252           # trading days needed before a rule can give its first signal
SHARE = {0: 1.0, 1: 1.0, 2: 0.6, 3: 0.3}     # share kept in equities at each stress level
LEVEL = ["Normal", "Watch", "Defensive", "Doomsday"]
CALM_DAYS = 10
SERIES = [("WTI oil", "@CL.1", False), ("Brent oil", "@LCO.1", False), ("Gold", "@GC.1", False), ("Copper", "@HG.1", False),
          ("Natural gas", "@NG.1", False), ("Wheat", "@W.1", False), ("US 10-year yield", "US10Y", True), ("US 2-year yield", "US2Y", True),
          ("US dollar index", ".DXY", False), ("VIX (expected S&P 500 volatility)", ".VIX", False), ("Euro in dollars", "EUR=", False),
          ("Bitcoin", "BTC.CM=", False), ("Dollar in forint", "HUF=", False)]
RULES = [("hold", "Buy and hold", "Hold the share the whole time."),
         ("trend200", "200-day trend", "Hold only while the price is above its 200-day average; otherwise cash."),
         ("cross", "50/200 cross", "Hold only while the 50-day average is above the 200-day average; otherwise cash."),
         ("mom", "12-month momentum", "Hold only while the price is above its level 12 months earlier; otherwise cash."),
         ("dip", "Buy the dip", "Buy when the 14-day RSI falls under 30; sell when it rises over 55."),
         ("stop", "15% trailing stop", "Hold; sell after a 15% fall from the highest price since buying; buy back above the 50-day average.")]


def r4(x, n=4):
    return E.rd(x, n)


def arr(rows):
    return [d for d, v in rows], np.array([v for d, v in rows], dtype=float)


def sma(px, n):
    out = np.full(len(px), np.nan)
    if len(px) >= n:
        c = np.cumsum(np.insert(px, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def rsi(px, n=14):
    out = np.full(len(px), np.nan)
    d = np.diff(px)
    if len(d) <= n:
        return out
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d) + 1):
        if i > n:
            au, ad = (au * (n - 1) + up[i - 1]) / n, (ad * (n - 1) + dn[i - 1]) / n
        out[i] = 100.0 if ad == 0 else 100.0 - 100.0 / (1.0 + au / ad)
    return out


def signal(rule, px):
    n = len(px)
    s = np.zeros(n)
    with np.errstate(invalid="ignore"):
        if rule == "hold":
            s[:] = 1.0
        elif rule == "trend200":
            s = np.where(px > sma(px, 200), 1.0, 0.0)
        elif rule == "cross":
            s = np.where(sma(px, 50) > sma(px, 200), 1.0, 0.0)
        elif rule == "mom":
            s[252:] = (px[252:] > px[:-252]).astype(float)
        elif rule == "dip":
            r, on = rsi(px), 0.0
            for i in range(n):
                if not np.isnan(r[i]):
                    if on == 0.0 and r[i] < 30:
                        on = 1.0
                    elif on == 1.0 and r[i] > 55:
                        on = 0.0
                s[i] = on
        elif rule == "stop":
            m, on, hi = sma(px, 50), 0.0, 0.0
            for i in range(n):
                if on == 1.0:
                    hi = max(hi, px[i])
                    if px[i] <= hi * 0.85:
                        on = 0.0
                elif not np.isnan(m[i]) and px[i] > m[i]:
                    on, hi = 1.0, px[i]
                s[i] = on
    return s


def run(px, sig, start, other=None):
    # the position decided at one day's close is held over the next day; cost is charged on every change
    r = px[start + 1:] / px[start:-1] - 1
    pos = sig[start:-1]
    turn = np.abs(np.diff(np.insert(pos, 0, 0.0)))
    net = pos * r - turn * COST
    if other is not None:
        net = net + (1 - pos) * other[start:]
    return np.cumprod(1 + net), int(np.sum(turn > 0)), float(np.mean(pos))


def stats(eq):
    full = np.insert(eq, 0, 1.0)
    r = full[1:] / full[:-1] - 1
    yrs = len(eq) / 252.0
    cagr = full[-1] ** (1 / yrs) - 1 if full[-1] > 0 and yrs > 0 else None
    w12 = None
    if len(full) > 252:
        w12 = float(np.min(full[252:] / full[:-252] - 1))
    return {"total": r4(full[-1] - 1), "cagr": r4(cagr), "vol": r4(np.std(r, ddof=1) * math.sqrt(252)),
            "mdd": r4(np.min(full / np.maximum.accumulate(full) - 1)), "worst_12m": r4(w12)}


def sample(eq, n=60):
    full = np.insert(eq, 0, 1.0)
    idx = np.unique(np.linspace(0, len(full) - 1, min(n, len(full))).astype(int))
    return idx, [round(float(full[i]), 4) for i in idx]


def align(a, b):
    db = dict(b)
    da = [(d, v) for d, v in a if d in db]
    return da, [(d, db[d]) for d, v in da]


# ---------------------------------------------------------------- item 12: rules against the S&P 500 fund
def backtests(tickers, spy):
    rows, curves, span = [], {}, {}
    for t in tickers:
        a, b = align(E.read_cache(t), spy)
        if len(a) < WARM + 260:
            continue
        dates, px = arr(a)
        spx = arr(b)[1]
        seq, _, _ = run(spx, np.ones(len(spx)), WARM)
        sst, half = stats(seq), len(seq) // 2
        idx, sc = sample(seq)
        curves[t] = {"dates": [dates[WARM + int(i)] for i in idx], "spy": sc}
        span[t] = {"from": dates[WARM], "to": dates[-1], "days": len(seq)}
        hold_total = None
        for rid, name, _ in RULES:
            eq, trades, inm = run(px, signal(rid, px), WARM)
            st = stats(eq)
            if rid == "hold":
                hold_total = st["total"]
            h1 = (eq[half - 1] - 1) - (seq[half - 1] - 1)
            h2 = (eq[-1] / eq[half - 1] - 1) - (seq[-1] / seq[half - 1] - 1)
            vs = st["total"] - sst["total"]
            if vs > 0 and h1 > 0 and h2 > 0:
                verdict = "beat the S&P 500 fund in both halves of the test"
            elif vs > 0:
                verdict = "ahead overall but in only one half of the test, so not reliable"
            else:
                verdict = "did not beat the S&P 500 fund"
            row = {"t": t, "rule": rid, "trades": trades, "time_in": r4(inm, 3), "spy_total": sst["total"], "spy_mdd": sst["mdd"],
                   "vs_spy": r4(vs), "vs_hold": r4(st["total"] - hold_total) if hold_total is not None else None,
                   "h1_vs_spy": r4(h1), "h2_vs_spy": r4(h2), "beats": bool(vs > 0 and h1 > 0 and h2 > 0), "verdict": verdict}
            row.update(st)
            rows.append(row)
            curves[t][rid] = sample(eq)[1]
    timed = [r for r in rows if r["rule"] != "hold"]
    return {"cost_per_trade": COST, "warm_up_days": WARM, "rules": [{"id": a, "name": b, "rule": c} for a, b, c in RULES],
            "rows": rows, "curves": curves, "span": span,
            "summary": {"tests": len(timed), "beat_both_halves": len([r for r in timed if r["beats"]]),
                        "beat_overall": len([r for r in timed if r["vs_spy"] > 0]),
                        "beat_own_hold": len([r for r in timed if (r["vs_hold"] or 0) > 0])},
            "method": "Each rule decides at the close and holds over the next day. Every change of position costs %.2f%% of the amount traded. "
                      "Out of the market the money earns nothing. The S&P 500 fund is bought once and held over the same days. "
                      "Prices are split-adjusted without dividends on both sides. The test is cut in two halves; a rule counts as beating "
                      "the fund only if it is ahead in both." % (100 * COST),
            "limits": ["The tickers are today's holdings and watchlist, chosen with hindsight.",
                       "About four years of data is one market period; a rule that worked in it may not work in the next.",
                       "Dividends are left out on both sides, which slightly flatters rules that sit in cash."]}


# ---------------------------------------------------------------- item 17: the doomsday protocol on history
def levels(px):
    n = len(px)
    r = px[1:] / px[:-1] - 1
    m200 = sma(px, 200)
    raw = np.zeros(n, dtype=int)
    for i in range(WARM, n):
        fh = px[i] / np.max(px[i - WARM + 1:i + 1]) - 1
        rv = float(np.std(r[i - 20:i], ddof=1) * math.sqrt(252))
        raw[i] = LEVEL.index(E.stress_level(fh, px[i] / m200[i] - 1, rv))
    act, cur, calm = np.zeros(n, dtype=int), 0, 0
    for i in range(n):
        if raw[i] > cur:
            cur, calm = raw[i], 0
        elif raw[i] < cur:
            calm += 1
            if calm >= CALM_DAYS:
                cur, calm = cur - 1, 0
        else:
            calm = 0
        act[i] = cur
    return raw, act


def doomsday(spy, safe):
    a, b = align(spy, safe) if len(safe) > 600 else (spy, [])
    use_safe = len(a) > 2000
    if not use_safe:
        a = spy
    dates, px = arr(a)
    if len(px) < WARM + 500:
        return {"status": "not enough history", "rows": len(px)}
    other = None
    if use_safe:
        sp = arr(b)[1]
        other = sp[1:] / sp[:-1] - 1
    raw, act = levels(px)
    w = np.array([SHARE[int(x)] for x in act])
    with np.errstate(invalid="ignore"):
        trend = np.where(px > sma(px, 200), 1.0, 0.3)
    hold = np.ones(len(px))

    def go(sig):
        r = px[WARM + 1:] / px[WARM:-1] - 1
        pos = sig[WARM:-1]
        turn = np.abs(np.diff(np.insert(pos, 0, pos[0])))
        net = pos * r - turn * COST + ((1 - pos) * other[WARM:] if other is not None else 0.0)
        return np.cumprod(1 + net), int(np.sum(turn > 0))
    eh, _ = go(hold)
    ep, sw = go(w)
    et, st_ = go(trend)
    d2 = dates[WARM:]
    fh, fp = np.insert(eh, 0, 1.0), np.insert(ep, 0, 1.0)
    dd = fh / np.maximum.accumulate(fh) - 1
    free, eps = np.ones(len(dd), dtype=bool), []
    for _ in range(6):
        k = int(np.argmin(np.where(free, dd, 0.0)))
        if dd[k] > -0.10 or not free[k]:
            break
        p = k
        while p > 0 and dd[p] < 0:
            p -= 1
        q = k
        while q < len(dd) - 1 and dd[q] < 0:
            q += 1
        eps.append({"peak": d2[p], "low": d2[k], "back": d2[q] if dd[q] >= 0 else None, "hold_fall": r4(dd[k]),
                    "protocol_fall": r4(float(np.min(fp[p:k + 1] / fp[p] - 1))),
                    "protocol_at_recovery": r4(fp[q] / fp[p] - 1), "hold_at_recovery": r4(fh[q] / fh[p] - 1)})
        free[p:q + 1] = False
    eps.sort(key=lambda x: x["peak"])
    changes = [{"date": dates[i], "to": LEVEL[int(act[i])]} for i in range(WARM + 1, len(act)) if act[i] != act[i - 1]]
    share = [r4(float(np.mean(act[WARM:] == i)), 3) for i in range(4)]
    idx, hc = sample(eh, 90)
    out = {"status": "ok", "from": d2[0], "to": d2[-1], "years": round(len(eh) / 252.0, 1),
           "safe_asset": "short US Treasuries (SHY)" if use_safe else "cash earning nothing",
           "equity_share": {LEVEL[i]: SHARE[i] for i in range(4)}, "calm_days": CALM_DAYS, "cost_per_trade": COST,
           "hold": stats(eh), "protocol": dict(stats(ep), switches=sw), "trend200": dict(stats(et), switches=st_),
           "time_at_level": {LEVEL[i]: share[i] for i in range(4)}, "level_now": LEVEL[int(act[-1])], "raw_level_now": LEVEL[int(raw[-1])],
           "episodes": eps, "changes": changes[-8:], "changes_total": len(changes),
           "curve": {"dates": [d2[int(i)] for i in idx], "hold": hc, "protocol": sample(ep, 90)[1], "trend200": sample(et, 90)[1]},
           "method": "Each day the S&P 500 fund is given a stress level from its fall below the 12-month high, its 200-day average and its "
                     "20-day volatility. The protocol keeps %d%% in the fund at Defensive and %d%% at Doomsday, moves the rest to the safe "
                     "asset, and steps back one level only after %d trading days in a row at a calmer level. Each switch costs %.2f%% of "
                     "the amount moved. Compared with holding the fund throughout and with a plain 200-day rule (30%% in the fund below "
                     "the average)." % (int(100 * SHARE[2]), int(100 * SHARE[3]), CALM_DAYS, 100 * COST)}
    p, h = out["protocol"], out["hold"]
    out["verdict"] = ("Over %s years the protocol %s the worst fall from %s to %s and ended %s holding throughout (%s a year against %s)." % (
        out["years"], "cut" if p["mdd"] > h["mdd"] else "did not cut", E.pc(abs(h["mdd"]), 0), E.pc(abs(p["mdd"]), 0),
        "ahead of" if p["total"] > h["total"] else "behind", E.pc(p["cagr"]), E.pc(h["cagr"])))
    return out


# ---------------------------------------------------------------- how spreading purchases has compared with buying at once
def spreading(spy):
    dates, px = arr(spy)
    if len(px) < 252 * 3:
        return None
    wins, gaps, n = 0, [], 0
    for s in range(0, len(px) - 252, 21):
        lump = px[s + 252] / px[s]
        parts = np.mean([px[s + 252] / px[s + 21 * k] for k in range(6)])
        gaps.append(lump - parts)
        wins += 1 if lump > parts else 0
        n += 1
    return {"from": dates[0], "to": dates[-1], "starts": n, "lump_ahead_share": r4(wins / n, 3), "average_gap": r4(float(np.mean(gaps))),
            "worst_gap": r4(float(np.min(gaps))), "best_gap": r4(float(np.max(gaps))),
            "method": "S&P 500 fund, every monthly starting point: all the money in on day one against six equal monthly parts, "
                      "both valued twelve months after the start. Price only."}


# ---------------------------------------------------------------- item 11: does an outside series lead a share price?
def outside(sym):
    path = os.path.join(E.CACHE, "x_" + re.sub("[^A-Za-z0-9]", "_", sym) + ".csv")
    rows = []
    if not E.OFFLINE:
        try:
            rows = E.fetch_cnbc(sym, time.time() - 5 * 366 * 86400)
            if len(rows) > 200:
                os.makedirs(E.CACHE, exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(E.NL.join(d + "," + ("%.6f" % v) for d, v in rows) + E.NL)
            time.sleep(0.3)
        except Exception:
            rows = []
    if len(rows) <= 200:
        try:
            with open(path, encoding="utf-8") as f:
                rows = [(x.split(",")[0], float(x.split(",")[1])) for x in f.read().split(E.NL) if "," in x]
        except Exception:
            rows = []
    return rows


def weekly(rows):
    out = {}
    for d, v in rows:
        y, w, _ = datetime.date.fromisoformat(d).isocalendar()
        out[(y, w)] = v
    return out


def tstat(x, y):
    n = len(x)
    if n < 20 or np.std(x) == 0 or np.std(y) == 0:
        return 0.0, 0.0
    r = float(np.corrcoef(x, y)[0, 1])
    return r, r * math.sqrt((n - 2) / max(1e-9, 1 - r * r))


def signals(tickers, spy, extra):
    wspy = weekly(spy)
    series, rows, same, missing = list(SERIES), [], [], []
    for x in extra:
        if x[1] not in [s[1] for s in series]:
            series.append(x)
    stock = {}
    for t in tickers:
        wk = weekly(E.read_cache(t))
        if len(wk) > 150:
            stock[t] = wk
    for name, sym, is_rate in series:
        ws = weekly(outside(sym))
        if len(ws) < 150:
            missing.append(name)
            continue
        for t, wk in stock.items():
            keys = sorted(k for k in wk if k in ws and k in wspy)
            if len(keys) < 150:
                continue
            xs = np.array([ws[k] for k in keys])
            st = np.array([wk[k] for k in keys])
            sp = np.array([wspy[k] for k in keys])
            dx = (xs[1:] - xs[:-1]) if is_rate else (xs[1:] / xs[:-1] - 1)
            ex = (st[1:] / st[:-1] - 1) - (sp[1:] / sp[:-1] - 1)
            r0, t0 = tstat(dx, ex)
            same.append({"series": name, "t": t, "r": r4(r0, 3), "tstat": r4(t0, 2)})
            for lag in (1, 2, 3, 4):
                x, y = dx[:-lag], ex[lag:]
                h = len(x) // 2
                ra, ta = tstat(x, y)
                r1, t1 = tstat(x[:h], y[:h])
                r2, t2 = tstat(x[h:], y[h:])
                holds = abs(t1) >= 2 and abs(t2) >= 2 and (t1 > 0) == (t2 > 0)
                slope = float(np.cov(x, y)[0, 1] / np.var(x, ddof=1)) if np.var(x) > 0 else 0.0
                rows.append({"series": name, "symbol": sym, "t": t, "lag_weeks": lag, "weeks": len(x), "r_all": r4(ra, 3), "t_all": r4(ta, 2),
                             "r_first": r4(r1, 3), "t_first": r4(t1, 2), "r_second": r4(r2, 3), "t_second": r4(t2, 2), "holds": bool(holds),
                             "effect": r4(slope * float(np.std(x, ddof=1))), "unit": "points" if is_rate else "percent",
                             "strength": r4(min(abs(t1), abs(t2)) if (t1 > 0) == (t2 > 0) else 0.0, 2)})
    rows.sort(key=lambda z: -z["strength"])
    same.sort(key=lambda z: -abs(z["tstat"]))
    tested = len(rows)
    return {"tested": tested, "expected_by_chance": r4(tested * 0.0455 * 0.0455 * 0.5, 2), "passed": [z for z in rows if z["holds"]],
            "closest": rows[:12], "same_week": same[:8], "series": [{"name": a, "symbol": b} for a, b, c in series], "missing": missing,
            "tickers": sorted(stock.keys()),
            "method": "Weekly changes in each outside series against the share's return minus the S&P 500 fund's return one to four weeks "
                      "later. The history is cut in two: a lead counts only if it is clear (t-statistic of 2 or more) in the first half "
                      "and shows up again with the same sign and strength in the second half. With this many tests, about the stated "
                      "number would pass by luck alone.",
            "limits": ["Passing this test shows a pattern in about five years of history, not a cause.",
                       "A lead that everyone can see tends to disappear once it is traded on.",
                       "Weekly data hides anything faster than a week."]}


# ---------------------------------------------------------------- frequent trading: short-term rules judged trade by trade, after real fees
FEE_PCT = 0.0025      # broker's commission on the order value
FEE_MIN = 1.12        # broker's minimum fee per trade in dollars (one euro, estimate)
SLOTS = 4             # the trading sleeve holds at most four trades at once, a quarter of the sleeve each
TRULES = [("pullback", "Pullback in an uptrend", "Buy when the price is above its 200-day average and the 2-day RSI falls under 10. Sell at a close above the 5-day average, after 10 trading days, or 8% under the entry."),
          ("dip", "Deep dip", "Buy when the 14-day RSI falls under 30. Sell when it rises over 55, after 30 trading days, or 12% under the entry."),
          ("breakout", "Breakout", "Buy at a new 55-day closing high above the 200-day average. Sell at a close under the lowest close of the previous 20 days."),
          ("three_down", "Three down days", "Buy after three lower closes in a row above the 200-day average. Sell at the first higher close or after 5 trading days.")]
NOT_TRADED = ("SHY", "IEF", "TLT", "LQD", "TIP", "BNDX", "BIL")


def trades_for(rule, px):
    n, out, i = len(px), [], 200
    m200, m5, r2, r14 = sma(px, 200), sma(px, 5), rsi(px, 2), rsi(px, 14)
    with np.errstate(invalid="ignore"):
        while i < n:
            if rule == "pullback":
                enter = px[i] > m200[i] and r2[i] < 10
            elif rule == "dip":
                enter = r14[i] < 30
            elif rule == "breakout":
                enter = px[i] > m200[i] and px[i] >= np.max(px[i - 54:i + 1])
            else:
                enter = px[i] > m200[i] and px[i] < px[i - 1] < px[i - 2] < px[i - 3]
            if not enter:
                i += 1
                continue
            e, j, done = i, i + 1, None
            while j < n:
                held = j - e
                if rule == "pullback":
                    ex = px[j] > m5[j] or held >= 10 or px[j] <= px[e] * 0.92
                elif rule == "dip":
                    ex = r14[j] > 55 or held >= 30 or px[j] <= px[e] * 0.88
                elif rule == "breakout":
                    ex = px[j] < np.min(px[j - 20:j])
                else:
                    ex = px[j] > px[j - 1] or held >= 5
                if ex:
                    done = j
                    break
                j += 1
            out.append((e, done if done is not None else n - 1, done is None))
            i = (done if done is not None else n) + 1
    return out


def sleeve(recs, start_usd, pct, min_fee):
    # trades taken in the order they start, at most SLOTS at once, each a quarter of the sleeve's value at that moment
    eq, peak, mdd, busy, taken, fees = float(start_usd), float(start_usd), 0.0, [], 0, 0.0
    events = sorted(recs, key=lambda x: (x["entry"], x["t"]))
    for x in events:
        busy = [b for b in busy if b > x["entry"]]
        if len(busy) >= SLOTS or eq <= 0:
            continue
        stake = eq / SLOTS
        fee = 2 * max(pct * stake, min_fee)
        eq += stake * x["ret"] - fee
        fees += fee
        taken += 1
        busy.append(x["exit"])
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return eq, mdd, taken, fees


def tactical(tickers, spy, prev):
    uni = [t for t in tickers if t not in NOT_TRADED]
    data = {}
    for t in uni:
        rows = E.read_cache(t)[-1260:]
        if len(rows) >= 460:
            data[t] = arr(rows)
    if not data:
        return {"status": "no price history"}
    last = spy[-1][0]
    first = min(d[0][200] for d in data.values())
    mid = sorted(set(x for d in data.values() for x in d[0][200:]))
    mid = mid[len(mid) // 2]
    yrs = max(0.5, (len(spy) and len([1 for d, v in spy if d >= first])) / 252.0)
    go = ((prev or {}).get("tactical") or {}).get("go_live") or last
    rules = []
    for rid, name, text in TRULES:
        recs, open_now, new_today = [], [], []
        for t, (dates, px) in data.items():
            for e, x, is_open in trades_for(rid, px):
                ret = float(px[x] / px[e] - 1)
                if is_open:
                    open_now.append({"t": t, "since": dates[e], "entry": r4(float(px[e]), 2), "last": r4(float(px[x]), 2), "ret": r4(ret), "days": int(x - e)})
                    if dates[e] == last:
                        new_today.append(t)
                else:
                    recs.append({"t": t, "entry": dates[e], "exit": dates[x], "days": int(x - e), "ret": ret})
        cut10 = spy[-10][0] if len(spy) >= 10 else last
        row = {"id": rid, "name": name, "rule": text, "trades": len(recs), "open": sorted(open_now, key=lambda z: z["since"], reverse=True), "new_today": new_today,
               "signals_10d": len([z for z in recs if z["entry"] >= cut10]) + len([z for z in open_now if z["since"] >= cut10])}
        if len(recs) >= 20:
            g = np.array([z["ret"] for z in recs])
            h1 = np.array([z["ret"] for z in recs if z["entry"] < mid] or [0.0])
            h2 = np.array([z["ret"] for z in recs if z["entry"] >= mid] or [0.0])
            wins, losses = float(np.sum(g[g > 0])), float(-np.sum(g[g < 0]))
            cost = 2 * FEE_PCT
            row.update({"win_rate": r4(float(np.mean(g > 0)), 3), "avg_gross": r4(float(np.mean(g))), "avg_net": r4(float(np.mean(g)) - cost),
                        "avg_win": r4(float(np.mean(g[g > 0])) if np.any(g > 0) else 0.0), "avg_loss": r4(float(np.mean(g[g < 0])) if np.any(g < 0) else 0.0),
                        "worst": r4(float(np.min(g))), "median_days": int(np.median([z["days"] for z in recs])), "profit_factor": r4(wins / losses if losses > 0 else None, 2),
                        "h1_net": r4(float(np.mean(h1)) - cost), "h2_net": r4(float(np.mean(h2)) - cost), "h1_trades": int(len(h1)), "h2_trades": int(len(h2)),
                        "per_month": r4(len(recs) / (yrs * 12), 1)})
            row["passes"] = bool(row["h1_net"] > 0 and row["h2_net"] > 0 and len(recs) >= 60)
            row["breakeven_stake"] = r4(2 * FEE_MIN / float(np.mean(g)), 0) if float(np.mean(g)) > 0 else None
            sl = {}
            for key, label, start, pct, mf in (("near_zero", "A broker with no commission: 0.05% a trade for the spread", 1000.0, 0.0005, 0.0),
                                               ("pct_only", "0.25% a trade, no minimum (your broker on trades over 450 dollars)", 1000.0, FEE_PCT, 0.0),
                                               ("usd_200", "Your broker, sleeve of 200 dollars", 200.0, FEE_PCT, FEE_MIN),
                                               ("usd_1000", "Your broker, sleeve of 1,000 dollars", 1000.0, FEE_PCT, FEE_MIN),
                                               ("usd_5000", "Your broker, sleeve of 5,000 dollars", 5000.0, FEE_PCT, FEE_MIN)):
                eq, mdd, taken, fees = sleeve(recs, start, pct, mf)
                sl[key] = {"label": label, "start": start, "end": r4(max(eq, 0.0), 0), "a_year": r4((eq / start) ** (1 / yrs) - 1 if eq > 0 else -1.0),
                           "worst_fall": r4(max(mdd, -1.0)), "trades": taken, "fees": r4(fees, 0)}
            row["sleeve"] = sl
            live = [z for z in recs if z["entry"] > go]
            row["paper"] = {"since": go, "closed": len(live), "sum_net": r4(sum(z["ret"] - cost for z in live)), "open": len([z for z in open_now if z["since"] > go])}
        else:
            row["passes"] = False
        rules.append(row)
    ok = [r for r in rules if r.get("passes")]
    best = max(ok, key=lambda r: r["sleeve"]["near_zero"]["a_year"]) if ok else None
    cash = None
    try:
        y2 = E.read_cache("s_US2Y") or []
        cash = y2[-1][1] / 100.0 if y2 else None
    except Exception:
        cash = None
    verdict = ("%d of the %d short-term rules kept a positive average per trade after a 0.25%% commission in both halves of the test." % (len(ok), len(rules)))
    if best:
        b = best["sleeve"]
        verdict += (" Run as a real sleeve of four trades at a time, the best ('%s') made %s a year at your broker's 0.25%%, %s a year on a 1,000-dollar sleeve once the "
                    "one-euro minimum applies, and %s a year at a broker with no commission." % (
                        best["name"], E.pc(b["pct_only"]["a_year"]), E.pc(b["usd_1000"]["a_year"]), E.pc(b["near_zero"]["a_year"])))
        if cash:
            verdict += " Short Treasuries pay about %s a year for doing nothing." % E.pc(cash)
    else:
        verdict += " None is worth trading for real."
    return {"status": "ok", "from": first, "to": last, "years": round(yrs, 1), "universe": sorted(data.keys()), "go_live": go, "rules": rules, "best": best["id"] if best else None,
            "cash_yield": r4(cash) if cash else None,
            "fee": {"pct": FEE_PCT, "min_usd": FEE_MIN, "slots": SLOTS,
                    "note": "Commission of 0.25% of the order with a minimum of one euro per trade once the plan's free trades are used (broker's published terms as reported in September 2026; check your own plan)."},
            "verdict": verdict,
            "method": "Each rule is applied to daily closes of every share and fund on the list. A trade is bought and sold at the close; the result is counted per trade, "
                      "and the test period is cut in two by date. The sleeve test takes the trades in the order they start, at most four at once, a quarter of the sleeve each, "
                      "and pays the commission or the minimum fee on every buy and sell.",
            "limits": ["Closing prices only: real fills differ, and the rules cannot see what happens inside a day.",
                       "About four years and one list of shares chosen with hindsight; a rule that passed here can stop working.",
                       "No tax, no currency cost and no dividends are included.",
                       "The four rules were written down before the test, but testing four and keeping the best still flatters the winner."]}


def requests_from_answers():
    out = []
    base = os.path.join(E.ROOT, "answers")
    try:
        names = sorted(os.listdir(base))
    except Exception:
        names = []
    for n in names:
        a = E.rj("answers/" + n, None)
        if isinstance(a, dict) and a.get("kind") == "lab":
            sym = str(a.get("symbol") or "").strip().upper()
            if re.fullmatch(r"[A-Z0-9@.=^-]{1,12}", sym):
                out.append((re.sub("[^A-Za-z0-9 ./()%-]", "", str(a.get("name") or sym))[:40] or sym, sym, bool(a.get("is_rate"))))
    return out[-10:]


def main():
    spy = E.read_cache("SPY")
    if len(spy) < WARM + 260:
        print("lab: no S&P 500 fund history")
        return
    held = [p.get("ticker") for p in (E.rj("treasury/snapshot.json", {}) or {}).get("positions", []) if p.get("ticker")]
    cards = [c.get("t") for c in (E.rj("research/cards/index.json", {}) or {}).get("cards", []) if c.get("t")]
    tickers = []
    for t in held + cards:
        if t and t not in tickers and t != "SPY":
            tickers.append(t)
    out = {"as_of": E.now_iso(), "prices_to": spy[-1][0], "price_note": "Split-adjusted closes without dividends."}
    prev = E.rj("state/lab.json", {}) or {}
    funds = [t for t in (E.rj("ops/engine/universe.json", {}) or {}).get("candidates", []) if t not in tickers]
    for key, fn in (("backtests", lambda: backtests(tickers + ["SPY"], spy)), ("doomsday", lambda: doomsday(spy, E.read_cache("SHY"))),
                    ("spreading", lambda: spreading(spy)), ("signals", lambda: signals(tickers, spy, requests_from_answers())),
                    ("tactical", lambda: tactical(tickers + ["SPY"] + funds, spy, prev))):
        try:
            out[key] = fn()
        except Exception as e:
            out[key] = {"status": "failed", "error": str(e)[:200]}
    E.wj("state/lab.json", out)
    b, s, d = out.get("backtests") or {}, out.get("signals") or {}, out.get("doomsday") or {}
    print("lab ok:", len(b.get("rows") or []), "backtests,", s.get("tested"), "signal tests,", len(s.get("passed") or []), "passed, doomsday", d.get("status"))


if __name__ == "__main__":
    main()
