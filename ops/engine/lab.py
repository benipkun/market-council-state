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
    for key, fn in (("backtests", lambda: backtests(tickers + ["SPY"], spy)), ("doomsday", lambda: doomsday(spy, E.read_cache("SHY"))),
                    ("spreading", lambda: spreading(spy)), ("signals", lambda: signals(tickers, spy, requests_from_answers()))):
        try:
            out[key] = fn()
        except Exception as e:
            out[key] = {"status": "failed", "error": str(e)[:200]}
    E.wj("state/lab.json", out)
    b, s, d = out.get("backtests") or {}, out.get("signals") or {}, out.get("doomsday") or {}
    print("lab ok:", len(b.get("rows") or []), "backtests,", s.get("tested"), "signal tests,", len(s.get("passed") or []), "passed, doomsday", d.get("status"))


if __name__ == "__main__":
    main()
