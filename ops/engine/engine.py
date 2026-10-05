# Market Council calculation engine, part 1: risk, diversification and portfolio health.
# Plain arithmetic on published prices. It prepares numbers; it never places orders.
import datetime
import json
import math
import os
import subprocess
import time
import urllib.parse
import urllib.request

import numpy as np
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import linprog, minimize
from scipy.spatial.distance import squareform

NL = chr(10)
ROOT = os.environ.get("MC_ROOT", ".")
CACHE = os.environ.get("MC_CACHE", os.path.join(ROOT, ".cache", "prices"))
OFFLINE = os.environ.get("MC_OFFLINE") == "1"
KEY12 = os.environ.get("TWELVE_DATA_KEY", "")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SEC_UA = "Market Council personal research benipkun@users.noreply.github.com"
WINDOW = 252
ERP = 0.05
FUND_CAP = 0.35
LEVELS = {
    1: {"label": "Cautious", "stock_cap": 0.10, "risk_per_trade": 0.005, "target_vol": 0.08, "min_cash": 0.10},
    2: {"label": "Careful", "stock_cap": 0.15, "risk_per_trade": 0.0075, "target_vol": 0.11, "min_cash": 0.07},
    3: {"label": "Balanced", "stock_cap": 0.20, "risk_per_trade": 0.01, "target_vol": 0.15, "min_cash": 0.05},
    4: {"label": "Growth", "stock_cap": 0.30, "risk_per_trade": 0.015, "target_vol": 0.20, "min_cash": 0.03},
    5: {"label": "Aggressive", "stock_cap": 0.40, "risk_per_trade": 0.02, "target_vol": 0.28, "min_cash": 0.02},
}
DEFAULT_PROFILE = {"id": "ben", "name": "Ben", "risk_level": 3, "horizon_years": 5, "max_loss_pct": 25, "allow_shorts": False}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rj(rel, default=None):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def wj(rel, obj):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=True) + NL)


def rd(x, n=4):
    if x is None:
        return None
    try:
        x = float(x)
    except Exception:
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, n)


def pc(x, n=1):
    return ("%." + str(n) + "f%%") % (100.0 * x)


# ---------------------------------------------------------------- prices
def http_json(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_yahoo(sym, start):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + "?period1=" + str(int(start)) + "&period2=" + str(int(time.time()) + 86400)
           + "&interval=1d&events=div%2Csplit")
    res = http_json(url)["chart"]["result"][0]
    off = int((res.get("meta") or {}).get("gmtoffset") or 0)
    ts = res.get("timestamp") or []
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    out = {}
    for i in range(len(ts)):
        if adj[i] is None:
            continue
        d = datetime.datetime.fromtimestamp(ts[i] + off, datetime.timezone.utc).strftime("%Y-%m-%d")
        out[d] = float(adj[i])
    return sorted(out.items())


def fetch_twelve(sym):
    url = ("https://api.twelvedata.com/time_series?symbol=" + urllib.parse.quote(sym)
           + "&interval=1day&outputsize=5000&order=ASC&adjust=all&apikey=" + KEY12)
    time.sleep(8)
    vals = http_json(url).get("values") or []
    return sorted((v["datetime"][:10], float(v["close"])) for v in vals)


def fetch_cnbc(sym, start):
    a = datetime.datetime.fromtimestamp(start, datetime.timezone.utc).strftime("%Y%m%d") + "000000"
    b = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d") + "235959"
    url = "https://ts-api.cnbc.com/harmony/app/bars/" + urllib.parse.quote(sym) + "/1D/" + a + "/" + b + "/adjusted/EST5EDT.json"
    bars = (http_json(url).get("barData") or {}).get("priceBars") or []
    out = {}
    for x in bars:
        t = str(x.get("tradeTime") or "")
        if len(t) >= 8 and x.get("close") not in (None, ""):
            out[t[:4] + "-" + t[4:6] + "-" + t[6:8]] = float(x["close"])
    return sorted(out.items())


def fetch_cboe(sym):
    url = "https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/" + urllib.parse.quote(sym) + ".json"
    data = http_json(url).get("data") or []
    return sorted((x["date"], float(x["close"])) for x in data if x.get("date") and x.get("close"))


def fetch_yields(syms):
    url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols="
           + "%7C".join(urllib.parse.quote(s) for s in syms)
           + "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1")
    q = (http_json(url).get("FormattedQuoteResult") or {}).get("FormattedQuote") or []
    if isinstance(q, dict):
        q = [q]
    out = {}
    for x in q:
        y = str(x.get("dividendyield") or "").replace("%", "").strip()
        try:
            out[x.get("symbol")] = float(y) / 100.0
        except Exception:
            pass
    return out


# Price sources are tried in this order; one that fails for two symbols in a row is skipped for the rest of the run.
DEAD = {}
LAST_ERR = {}
ADJ = {}


def chain(start):
    c = [("Yahoo Finance", lambda s: fetch_yahoo(s, start), True)]
    if KEY12:
        c.append(("Twelve Data", fetch_twelve, True))
    c.append(("CNBC", lambda s: fetch_cnbc(s, start), False))
    c.append(("Cboe", fetch_cboe, False))
    return c


def cache_path(sym):
    return os.path.join(CACHE, sym.replace("^", "_") + ".csv")


def read_cache(sym):
    try:
        with open(cache_path(sym), encoding="utf-8") as f:
            rows = []
            for line in f.read().split(NL):
                if "," in line:
                    d, v = line.split(",")[:2]
                    rows.append((d, float(v)))
            return rows
    except Exception:
        return []


def load_prices(sym, long_history, log):
    rows, src, err = [], None, None
    if not OFFLINE:
        start = 946684800 if long_history else time.time() - 5 * 366 * 86400
        for name, fn, adj in chain(start):
            if DEAD.get(name, 0) >= 2:
                continue
            try:
                got = fn(sym)
                if len(got) < 30:
                    raise ValueError("only " + str(len(got)) + " rows")
                rows, src = got, name
                ADJ[sym] = adj
                DEAD[name] = 0
                break
            except Exception as e:
                err = name + ": " + str(e)[:80]
                DEAD[name] = DEAD.get(name, 0) + 1
                LAST_ERR[name] = str(e)[:120]
    if len(rows) >= 30:
        os.makedirs(CACHE, exist_ok=True)
        with open(cache_path(sym), "w", encoding="utf-8", newline="") as f:
            f.write(NL.join(d + "," + ("%.4f" % v) for d, v in rows) + NL)
    else:
        rows = read_cache(sym)
        src = "saved copy" if rows else None
    log[sym] = {"source": src, "rows": len(rows), "through": rows[-1][0] if rows else None, "error": err if src != "Yahoo Finance" else None}
    return rows


# ---------------------------------------------------------------- statistics
def sym_stats(rows):
    dates = [d for d, v in rows]
    px = np.array([v for d, v in rows], dtype=float)
    out = {"last": rd(px[-1], 4), "last_date": dates[-1]}
    for k, n in (("1D", 1), ("1W", 5), ("1M", 21), ("3M", 63), ("1Y", 252)):
        out["ret_" + k] = rd(px[-1] / px[-1 - n] - 1) if len(px) > n else None
    prior = [v for d, v in rows if d[:4] < dates[-1][:4]]
    out["ret_YTD"] = rd(px[-1] / prior[-1] - 1) if prior else None
    r = px[1:] / px[:-1] - 1
    r1 = r[-WINDOW:]
    out["vol_1y"] = rd(np.std(r1, ddof=1) * math.sqrt(252)) if len(r1) > 60 else None
    out["vol_20d"] = rd(np.std(r[-20:], ddof=1) * math.sqrt(252)) if len(r) > 20 else None
    win = px[-WINDOW:]
    out["mdd_1y"] = rd(np.min(win / np.maximum.accumulate(win) - 1))
    out["from_high_1y"] = rd(win[-1] / np.max(win) - 1)
    out["hist_5y"] = rd(np.mean(r[-1260:]) * 252) if len(r) > 250 else None
    return out


def frame(prices, syms, days):
    common = None
    for s in syms:
        ds = set(d for d, v in prices[s])
        common = ds if common is None else (common & ds)
    dates = sorted(common)[-(days + 1):]
    maps = [dict(prices[s]) for s in syms]
    P = np.array([[m[d] for m in maps] for d in dates], dtype=float)
    return dates[1:], P[1:] / P[:-1] - 1


def cov_of(R):
    S = np.cov(R, rowvar=False) * 252
    S = np.atleast_2d(S)
    return 0.9 * S + 0.1 * np.diag(np.diag(S))


def max_drawdown(r):
    eq = np.cumprod(1 + r)
    return float(np.min(eq / np.maximum.accumulate(eq) - 1))


def worst_window(r, n):
    if len(r) < n:
        return None
    eq = np.concatenate([[1.0], np.cumprod(1 + r)])
    return float(np.min(eq[n:] / eq[:-n] - 1))


def cvar95(r):
    k = max(1, int(math.floor(0.05 * len(r))))
    return float(np.mean(np.sort(r)[:k]))


# ---------------------------------------------------------------- optimisers (long only, fully invested)
def clean(w):
    w = np.clip(np.array(w, dtype=float), 0, None)
    w[w < 0.0005] = 0
    return w / w.sum() if w.sum() > 0 else w


def start_point(ub):
    ub = np.array(ub, dtype=float)
    return ub / ub.sum()


def solve_minvar(S, ub):
    res = minimize(lambda w: float(w @ S @ w), start_point(ub), jac=lambda w: 2 * (S @ w), method="SLSQP",
                   bounds=[(0.0, u) for u in ub], constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
                   options={"maxiter": 800, "ftol": 1e-12})
    return clean(res.x)


def solve_tangency(mu, S, rf, ub):
    def neg(w):
        return -((w @ mu) - rf) / math.sqrt(max(float(w @ S @ w), 1e-12))
    best, best_v = None, None
    n = len(ub)
    starts = [start_point(ub)]
    for i in range(n):
        x = np.array(ub, dtype=float) * 0.02
        x[i] = min(ub[i], 1.0)
        starts.append(x / x.sum() if x.sum() <= 1 else x / x.sum())
    for x0 in starts:
        x0 = np.minimum(x0, ub)
        x0 = x0 + (1 - x0.sum()) * start_point(np.array(ub) - x0 + 1e-9) if x0.sum() < 1 else x0 / x0.sum()
        res = minimize(neg, x0, method="SLSQP", bounds=[(0.0, u) for u in ub],
                       constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}], options={"maxiter": 800, "ftol": 1e-12})
        if res.success and (best_v is None or res.fun < best_v):
            best, best_v = res.x, res.fun
    return clean(best if best is not None else start_point(ub))


def solve_target(mu, S, ub, target_vol):
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "ineq", "fun": lambda w: target_vol * target_vol - float(w @ S @ w)}]
    x0 = solve_minvar(S, ub)
    if math.sqrt(float(x0 @ S @ x0)) > target_vol:
        return x0, False
    res = minimize(lambda w: -float(w @ mu), x0, method="SLSQP", bounds=[(0.0, u) for u in ub], constraints=cons,
                   options={"maxiter": 800, "ftol": 1e-12})
    return clean(res.x if res.success else x0), True


def cluster_var(S, idx):
    sub = S[np.ix_(idx, idx)]
    iv = 1.0 / np.diag(sub)
    iv = iv / iv.sum()
    return float(iv @ sub @ iv)


def solve_hrp(S):
    n = len(S)
    if n < 3:
        iv = 1.0 / np.diag(S)
        return iv / iv.sum()
    sd = np.sqrt(np.diag(S))
    C = S / np.outer(sd, sd)
    D = np.sqrt(np.clip(0.5 * (1 - C), 0, 1))
    np.fill_diagonal(D, 0)
    order = [int(i) for i in leaves_list(linkage(squareform(D, checks=False), method="single"))]
    w = np.ones(n)
    clusters = [order]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) < 2:
                continue
            h = len(c) // 2
            a, b = c[:h], c[h:]
            va, vb = cluster_var(S, a), cluster_var(S, b)
            alpha = 1 - va / (va + vb)
            for i in a:
                w[i] *= alpha
            for i in b:
                w[i] *= 1 - alpha
            nxt += [a, b]
        clusters = nxt
    return w / w.sum()


def solve_mincvar(R, ub, beta=0.95):
    T, n = R.shape
    c = np.concatenate([np.zeros(n), [1.0], np.ones(T) / ((1 - beta) * T)])
    A = np.hstack([-R, -np.ones((T, 1)), -np.eye(T)])
    Aeq = np.concatenate([np.ones(n), [0.0], np.zeros(T)]).reshape(1, -1)
    bounds = [(0.0, float(u)) for u in ub] + [(None, None)] + [(0.0, None)] * T
    res = linprog(c, A_ub=A, b_ub=np.zeros(T), A_eq=Aeq, b_eq=[1.0], bounds=bounds, method="highs")
    return clean(res.x[:n]) if res.success else start_point(ub)


def describe(w, mu, S, R, rf):
    vol = math.sqrt(max(float(w @ S @ w), 0.0))
    ret = float(w @ mu)
    pr = R @ w
    return {"w": [rd(x, 4) for x in w], "vol": rd(vol), "ret": rd(ret), "sharpe": rd((ret - rf) / vol, 2) if vol > 0 else None,
            "cvar": rd(cvar95(pr)), "mdd": rd(max_drawdown(pr))}


def optimise(tickers, cur, mu, S, R, rf, ub, target_vol):
    out = {"tickers": tickers, "cap": [rd(u, 2) for u in ub], "mu": [rd(x) for x in mu], "methods": {}}
    out["methods"]["current"] = describe(np.array(cur), mu, S, R, rf)
    out["methods"]["minvar"] = describe(solve_minvar(S, ub), mu, S, R, rf)
    out["methods"]["hrp"] = describe(solve_hrp(S), mu, S, R, rf)
    out["methods"]["tangency"] = describe(solve_tangency(mu, S, rf, ub), mu, S, R, rf)
    out["methods"]["mincvar"] = describe(solve_mincvar(R, ub), mu, S, R, rf)
    wt, ok = solve_target(mu, S, ub, target_vol)
    d = describe(wt, mu, S, R, rf)
    d["reachable"] = ok
    out["methods"]["target"] = d
    return out


# ---------------------------------------------------------------- market stress level
def stress_level(from_high, vs200, rv20):
    if from_high <= -0.20:
        return "Doomsday"
    if from_high <= -0.10 or (vs200 < 0 and rv20 >= 0.25):
        return "Defensive"
    if from_high <= -0.05 or vs200 < 0 or rv20 >= 0.20:
        return "Watch"
    return "Normal"


def stress_now(rows):
    px = np.array([v for d, v in rows], dtype=float)
    r = px[1:] / px[:-1] - 1
    from_high = px[-1] / np.max(px[-WINDOW:]) - 1
    vs200 = px[-1] / np.mean(px[-200:]) - 1
    rv20 = np.std(r[-20:], ddof=1) * math.sqrt(252)
    return {"level": stress_level(from_high, vs200, rv20), "as_of": rows[-1][0], "spy_from_high": rd(from_high),
            "spy_vs_200d": rd(vs200), "spy_vol_20d": rd(rv20),
            "rules": ["Doomsday: S&P 500 fund 20% or more below its 12-month high",
                      "Defensive: 10% or more below the high, or below its 200-day average with 20-day volatility of 25% or more",
                      "Watch: 5% or more below the high, or below the 200-day average, or 20-day volatility of 20% or more",
                      "Normal: none of the above"]}


# ---------------------------------------------------------------- value history from the repository's own records
def git(args):
    return subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True, timeout=120).stdout


def nav_history(prev):
    days = dict((d["date"], d) for d in (prev or {}).get("days", []))
    try:
        log = git(["log", "--format=%H %cI", "--", "treasury/snapshot.json"])
    except Exception:
        log = ""
    last = {}
    for line in log.split(NL):
        parts = line.strip().split(" ")
        if len(parts) < 2:
            continue
        try:
            d = datetime.datetime.fromisoformat(parts[1]).astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            continue
        if d not in last:
            last[d] = parts[0]
    newest = max(last) if last else None
    for d, sha in last.items():
        if d in days and d != newest:
            continue
        try:
            s = json.loads(git(["show", sha + ":treasury/snapshot.json"]))
            days[d] = {"date": d, "nav": rd(s.get("nav"), 2), "cash": rd(s.get("cash"), 2),
                       "pos": dict((p["ticker"], rd(p.get("market_value"), 2)) for p in s.get("positions", []))}
        except Exception:
            pass
    # weekend snapshots are test artefacts from setup (markets are closed), so they are left out
    keep = [k for k in sorted(days) if days[k].get("nav") and datetime.date.fromisoformat(k).weekday() < 5]
    return {"days": [days[k] for k in keep], "method": "last treasury snapshot of each weekday, read from the repository history"}


def nav_ranges(days, ledger):
    if len(days) < 2:
        return {}
    flows = {}
    for e in (ledger or {}).get("entries", []):
        if e.get("status") != "applied" or e.get("undone_by") or e.get("action") not in ("deposit", "withdraw"):
            continue
        amt = float(e.get("usd") or 0) * (1 if e.get("action") == "deposit" else -1)
        ed = str(e.get("at", ""))[:10]
        tgt = [d["date"] for d in days if d["date"] >= ed]
        if tgt and ed > days[0]["date"]:
            flows[tgt[0]] = flows.get(tgt[0], 0.0) + amt
    n = len(days)

    def span(i0):
        tw, gain, fl = 1.0, 0.0, 0.0
        for i in range(i0 + 1, n):
            f = flows.get(days[i]["date"], 0.0)
            prev = days[i - 1]["nav"]
            tw *= (days[i]["nav"] - f) / prev if prev else 1.0
            gain += days[i]["nav"] - prev - f
            fl += f
        return {"from": days[i0]["date"], "usd": rd(gain, 2), "pct": rd(tw - 1), "flows": rd(fl, 2)}
    out = {"1D": span(n - 2), "1W": span(max(0, n - 6)), "1M": span(max(0, n - 22)), "ALL": span(0)}
    y0 = 0
    for i, d in enumerate(days):
        if d["date"][:4] < days[-1]["date"][:4]:
            y0 = i
    out["YTD"] = span(y0)
    return out


# ---------------------------------------------------------------- health check
def exposure(rows, key):
    acc = {}
    for r in rows:
        acc[r[key]] = acc.get(r[key], 0.0) + r["w"]
    return [[k, rd(v)] for k, v in sorted(acc.items(), key=lambda kv: -kv[1])]


def health_check(pos, cash_w, lim, prof, pvol, stress_loss, avg_corr):
    F = []

    def add(fid, level, score, title, value, limit, detail, method):
        F.append({"id": fid, "level": level, "score": rd(score, 2), "title": title, "value": rd(value), "limit": rd(limit),
                  "detail": detail, "method": method})
    cap = lim["stock_cap"]
    for p in pos:
        if p["cls"] == "Equity" and p["w"] > cap:
            add("stock:" + p["t"], "high" if p["w"] > 2 * cap else "medium", p["w"] / cap,
                p["t"] + " is " + pc(p["w"]) + " of the portfolio", p["w"], cap,
                "Your profile allows " + pc(cap, 0) + " in one company. This is " + pc(p["w"] - cap) + " of the portfolio over that line.",
                "weight = position value / total value")
        if p.get("risk_share") is not None and p["risk_share"] > 0.5:
            add("risk:" + p["t"], "high" if p["risk_share"] > 0.75 else "medium", p["risk_share"] / 0.5,
                p["t"] + " causes " + pc(p["risk_share"], 0) + " of the portfolio's swings", p["risk_share"], 0.5,
                "Share of portfolio variance that comes from this position over the last " + str(WINDOW) + " trading days.",
                "risk share = weight x (covariance x weights) / portfolio variance")
    for key, lab, thr in (("sector", "sector", 0.40), ("theme", "theme", 0.30), ("country", "country", 0.85)):
        for name, v in exposure(pos, key):
            if v > thr and name != "Cash":
                add(key + ":" + name, "medium" if key != "country" else "low", v / thr, pc(v, 0) + " sits in one " + lab + ": " + name, v, thr,
                    "More than " + pc(thr, 0) + " in one " + lab + " means one piece of " + lab + " news moves most of the portfolio.",
                    "sum of weights by " + lab)
    foreign = sum(p["w"] for p in pos)
    if foreign > 0.5:
        add("currency:HUF", "low", foreign, pc(foreign, 0) + " of the portfolio is in foreign currency", foreign, 0.5,
            "You spend in forints. A 10% move in the dollar or euro against the forint moves the portfolio about " + pc(0.1 * foreign) + " in forint terms.",
            "share of value not held in HUF")
    if cash_w < lim["min_cash"]:
        add("cash", "medium", lim["min_cash"] / max(cash_w, 0.005), "Cash is " + pc(cash_w) + " of the portfolio", cash_w, lim["min_cash"],
            "Your profile keeps a " + pc(lim["min_cash"], 0) + " buffer so a new idea or a bad month does not force a sale.", "cash / total value")
    if pvol is not None and pvol > lim["target_vol"]:
        add("vol", "high" if pvol > 1.5 * lim["target_vol"] else "medium", pvol / lim["target_vol"],
            "Volatility is about " + pc(pvol, 0) + " a year", pvol, lim["target_vol"],
            "Your profile (level " + str(prof["risk_level"]) + ", " + lim["label"] + ") targets about " + pc(lim["target_vol"], 0) + " a year.",
            "standard deviation of daily returns at today's weights x square root of 252")
    ml = float(prof["max_loss_pct"]) / 100.0
    if stress_loss is not None and -stress_loss > ml:
        add("stress", "high", -stress_loss / ml, "Worst 12 months at these weights: " + pc(stress_loss, 0), stress_loss, -ml,
            "Holding today's weights through the last five years, the worst 12-month stretch lost this much. You set " + pc(ml, 0) + " as the most you accept. Estimate from history, not a forecast.",
            "minimum 252-day return of the constant-weight portfolio over 5 years of daily prices")
    eq = [p for p in pos if p["cls"] == "Equity"]
    if 0 < len(eq) < 8:
        add("count", "low", 8.0 / len(eq) / 4, str(len(eq)) + " holdings", len(eq), 8,
            "With fewer than about 8 holdings that move differently, company news outweighs everything else.", "count of positions")
    if avg_corr is not None and avg_corr > 0.6:
        add("corr", "medium", avg_corr / 0.6, "Holdings move together (average correlation " + ("%.2f" % avg_corr) + ")", avg_corr, 0.6,
            "Above 0.6 the positions behave like one bet.", "mean pairwise correlation of daily returns")
    F.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["level"]], -(f["score"] or 0)))
    score = 100
    for f in F:
        score -= {"high": 25, "medium": 10, "low": 4}[f["level"]]
    return {"score": max(0, score), "findings": F,
            "score_method": "100 minus 25 for each high finding, 10 for each medium, 4 for each low"}


# ---------------------------------------------------------------- main
def main():
    started = now_iso()
    uni = rj("ops/engine/universe.json", {}) or {}
    meta = uni.get("assets", {})
    bench = uni.get("benchmark", "SPY")
    cashp = uni.get("cash_proxy", "BIL")
    snap = rj("treasury/snapshot.json", {}) or {}
    ledger = rj("treasury/ledger.json", {}) or {}
    known = [k.get("ticker") for k in (rj("state/known_companies.json", {}) or {}).get("tickers", []) if k.get("ticker")]
    theses = [t.get("ticker") for t in (rj("state/theses.json", {}) or {}).get("theses", []) if t.get("ticker")]
    profs = rj("state/profiles.json", None)
    prof = dict(DEFAULT_PROFILE)
    prof["set"] = False
    if profs and profs.get("people"):
        act = [p for p in profs["people"] if p.get("id") == profs.get("active")] or profs["people"]
        prof.update(act[0])
        prof["set"] = True
    level = int(prof.get("risk_level") or 3)
    level = min(5, max(1, level))
    lim = dict(LEVELS[level])
    lim["shorts"] = bool(prof.get("allow_shorts")) and level >= 4
    hz = float(prof.get("horizon_years") or 5)
    lim["safe_floor"] = 0.40 if hz < 3 else (0.20 if hz < 7 else 0.05)

    held = [p for p in snap.get("positions", []) if p.get("ticker") and (p.get("market_value") or 0) > 0]
    nav = float(snap.get("nav") or 0) or sum(p["market_value"] for p in held) + float(snap.get("cash") or 0)
    cash = float(snap.get("cash") or 0)
    held_t = [p["ticker"] for p in held]
    cands = list(uni.get("candidates", []))
    longs = set(uni.get("long_history", []))
    syms = []
    for s in held_t + known + theses + cands + [bench, cashp]:
        if s and s not in syms:
            syms.append(s)

    plog, prices = {}, {}
    for s in syms:
        rows = load_prices(s, s in longs, plog)
        if len(rows) > WINDOW + 5:
            prices[s] = rows
        if not OFFLINE:
            time.sleep(0.4)
    ok = [s for s in syms if s in prices]
    status = {"as_of": started, "ok": len(ok) >= 2 and bench in prices, "symbols": len(syms), "with_prices": len(ok),
              "by_source": {}, "errors": dict(LAST_ERR)}
    for s in syms:
        k = plog.get(s, {}).get("source") or "none"
        status["by_source"][k] = status["by_source"].get(k, 0) + 1
    wj("state/engine_status.json", status)
    if not status["ok"]:
        print("engine: no usable price history", status)
        raise SystemExit(1)
    plain = [s for s in ok if ADJ.get(s) is False]
    ylds = {}
    if plain and not OFFLINE:
        try:
            ylds = fetch_yields(plain)
        except Exception as e:
            status["errors"]["yields"] = str(e)[:120]
    assets = {}
    unclassified = []
    for s in syms:
        m = dict(meta.get(s) or {"name": s, "cls": "Equity", "sector": "Unclassified", "country": "Unknown", "ccy": "USD", "theme": "Unclassified"})
        if s not in meta:
            unclassified.append(s)
        if s in prices:
            m.update(sym_stats(prices[s]))
            if s in plain:
                m["price_only"] = True
                m["div_yield"] = rd(ylds.get(s))
        assets[s] = m
    out = {"as_of": started, "engine": "1.0", "window_days": WINDOW, "unclassified": unclassified}

    # correlation and covariance on one shared window
    dates, R = frame(prices, ok, WINDOW)
    S = cov_of(R)
    sd = np.sqrt(np.diag(np.cov(R, rowvar=False)))
    C = np.cov(R, rowvar=False) / np.outer(sd, sd)
    ix = dict((s, i) for i, s in enumerate(ok))
    out["corr"] = {"tickers": ok, "m": [[rd(x, 2) for x in row] for row in C], "window_days": len(dates),
                   "from": dates[0], "through": dates[-1], "method": "Pearson correlation of daily returns, adjusted closes"}
    bi = ix.get(bench)
    ca = assets.get(cashp, {})
    rf = (ca.get("ret_1Y") or 0.0) + (ca.get("div_yield") or 0.0) if ca.get("price_only") else (ca.get("ret_1Y") or 0.04)
    if rf <= 0:
        rf = 0.04
    for s in ok:
        i = ix[s]
        beta = float(np.cov(R[:, i], R[:, bi])[0, 1] / np.var(R[:, bi], ddof=1)) if bi is not None else None
        assets[s]["beta_1y"] = rd(beta, 2)
        h = assets[s].get("hist_5y")
        if h is not None and assets[s].get("price_only"):
            h = h + (assets[s].get("div_yield") or 0.0)
        capm = rf + (beta or 0) * ERP
        assets[s]["mu_est"] = rd(min(0.25, max(-0.10, 0.5 * capm + 0.5 * (h if h is not None else capm))))
    out["assets"] = assets

    # the portfolio as it stands
    pos = []
    for p in held:
        t = p["ticker"]
        a = assets.get(t, {})
        cb = p.get("cost_basis")
        pos.append({"t": t, "w": p["market_value"] / nav, "cls": a.get("cls", "Equity"), "sector": a.get("sector", "Unclassified"),
                    "country": a.get("country", "Unknown"), "ccy": a.get("ccy", "USD"), "theme": a.get("theme", "Unclassified"),
                    "pl_pct": rd(p["market_value"] / cb - 1) if cb else None, "has_data": t in ix})
    cash_w = cash / nav if nav else 0
    wv = np.zeros(len(ok))
    for p in pos:
        if p["has_data"]:
            wv[ix[p["t"]]] = p["w"]
    pvar = float(wv @ S @ wv)
    pvol = math.sqrt(pvar) if pvar > 0 else None
    pr = R @ wv
    for p in pos:
        if p["has_data"] and pvar > 0:
            i = ix[p["t"]]
            p["risk_share"] = rd(wv[i] * float(S[i] @ wv) / pvar)
            p["vol_1y"] = assets[p["t"]].get("vol_1y")
            p["beta_1y"] = assets[p["t"]].get("beta_1y")
            p["from_high_1y"] = assets[p["t"]].get("from_high_1y")
        p["w"] = rd(p["w"])
    hs = [p["t"] for p in pos if p["has_data"]]
    stress_loss = None
    if hs:
        d5, R5 = frame(prices, hs, 1260)
        w5 = np.array([wv[ix[t]] for t in hs])
        stress_loss = worst_window(R5 @ w5, 252)
    pairs = [C[ix[a], ix[b]] for i, a in enumerate(hs) for b in hs[i + 1:]]
    avg_corr = float(np.mean(pairs)) if pairs else None
    health = health_check(pos, cash_w, lim, prof, pvol, stress_loss, avg_corr)
    lvl = {"high": 3, "medium": 2, "low": 1}
    for p in pos:
        mine = [f for f in health["findings"] if f["id"].endswith(":" + p["t"])]
        p["flags"] = [f["title"] for f in mine]
        p["severity"] = max([lvl[f["level"]] for f in mine] + [0])
    health["positions"] = sorted(pos, key=lambda p: (-p["severity"], -(p.get("risk_share") or 0), -p["w"]))
    out["health"] = health
    ex_rows = pos + [{"t": "Cash", "w": cash_w, "cls": "Cash", "sector": "Cash", "country": "Cash", "ccy": "USD", "theme": "Cash"}]
    rets = {}
    for k in ("1D", "1W", "1M", "3M", "YTD", "1Y"):
        vals = [(p["w"], assets[p["t"]].get("ret_" + k)) for p in pos if p["has_data"]]
        rets[k] = rd(sum(w * v for w, v in vals if v is not None)) if vals else None
    weights = dict((p["t"], p["w"]) for p in pos)
    weights["CASH"] = rd(cash_w)
    out["portfolio"] = {
        "weights": weights, "vol_1y": rd(pvol), "var95_1d": rd(float(np.percentile(pr, 5))) if hs else None,
        "cvar95_1d": rd(cvar95(pr)) if hs else None, "beta_1y": rd(sum(wv[ix[t]] * (assets[t].get("beta_1y") or 0) for t in hs), 2),
        "mdd_1y": rd(max_drawdown(pr)) if hs else None, "worst_12m_5y": rd(stress_loss), "avg_corr": rd(avg_corr, 2),
        "ret_at_todays_weights": rets,
        "exposure": {"stock": exposure(ex_rows, "t"), "sector": exposure(ex_rows, "sector"), "country": exposure(ex_rows, "country"),
                     "currency": exposure(ex_rows, "ccy"), "theme": exposure(ex_rows, "theme"), "class": exposure(ex_rows, "cls")},
        "method": "weights from the latest treasury snapshot; risk from " + str(len(dates)) + " daily returns through " + dates[-1]}

    # value history from the repository's own snapshots
    hist = nav_history(rj("state/nav_history.json", {"days": []}))
    out["portfolio"]["value_change"] = nav_ranges(hist["days"], ledger)
    out["portfolio"]["value_days"] = len(hist["days"])

    # optimisers
    opt = {"rf": rd(rf), "erp": ERP, "window_days": len(dates),
           "notes": ["Risk inputs: covariance of daily returns over the window, shrunk 10% towards the diagonal.",
                     "Return inputs are estimates: half CAPM (risk-free + beta x 5%), half the 5-year average, limited to -10%..+25%.",
                     "Risk-free rate: last 12 months of the Treasury-bill fund " + cashp + ".",
                     "Long only, fully invested, cash left out. HRP has no weight caps by construction."]}
    if plain:
        opt["notes"].append("Prices for " + str(len(plain)) + " symbols come without dividends (CNBC or Cboe charts): each one's current dividend yield from CNBC's quote page is added to its return estimate, and volatility and correlations use price changes only.")
    inv = sum(p["w"] for p in pos if p["has_data"])
    if len(hs) >= 2 and inv > 0:
        ii = [ix[t] for t in hs]
        opt["held"] = optimise(hs, [wv[i] / inv for i in ii], np.array([assets[t]["mu_est"] for t in hs]), S[np.ix_(ii, ii)],
                               R[:, ii], rf, [1.0] * len(hs), lim["target_vol"])
        wide = hs + [c for c in cands if c in ix and c not in hs]
        jj = [ix[t] for t in wide]
        ub = [lim["stock_cap"] if assets[t].get("cls") == "Equity" else FUND_CAP for t in wide]
        if sum(ub) >= 1.0:
            opt["wide"] = optimise(wide, [wv[j] / inv for j in jj], np.array([assets[t]["mu_est"] for t in wide]), S[np.ix_(jj, jj)],
                                   R[:, jj], rf, ub, lim["target_vol"])
    out["opt"] = opt

    # what adding one more holding does to the swings
    adds = []
    if pvol:
        wi = wv / inv
        base = math.sqrt(float(wi @ S @ wi))
        pri = R @ wi
        for c in ok:
            if c in hs or c == cashp:
                continue
            j = ix[c]
            row = {"t": c, "kind": "candidate" if c in cands else "watchlist", "vol": assets[c].get("vol_1y"),
                   "corr": rd(float(np.corrcoef(pri, R[:, j])[0, 1]), 2)}
            for share in (0.10, 0.20):
                w2 = wi * (1 - share)
                w2[j] += share
                row["d" + str(int(share * 100))] = rd(math.sqrt(float(w2 @ S @ w2)) - base)
            cv = float(wi @ S[:, j])
            den = base * base + S[j, j] - 2 * cv
            x = min(1.0, max(0.0, (base * base - cv) / den)) if den > 0 else 0.0
            w3 = wi * (1 - x)
            w3[j] += x
            row["best_share"] = rd(x, 2)
            row["best_vol"] = rd(math.sqrt(float(w3 @ S @ w3)))
            adds.append(row)
        adds.sort(key=lambda r: r["d10"])
        out["additions"] = {"base_vol": rd(base), "rows": adds,
                            "method": "new volatility after moving 10% or 20% of the invested money, taken evenly from current holdings, into the candidate"}

    if bench in prices:
        out["stress"] = stress_now(prices[bench])
    out["profile"] = {"id": prof.get("id"), "name": prof.get("name"), "set": prof["set"], "risk_level": level, "label": lim["label"],
                      "horizon_years": hz, "max_loss_pct": prof.get("max_loss_pct"), "allow_shorts": bool(prof.get("allow_shorts")), "limits": lim,
                      "levels": LEVELS}
    out["shorts"] = {"allowed": lim["shorts"],
                     "rule": "Short ideas are shown only when the profile says yes and the risk level is 4 or 5. Every short card states the borrow cost, that the loss has no ceiling, and a stop that must be placed with the order."}

    # sources and charts
    src = []
    for name in sorted(k for k in status["by_source"] if k != "none"):
        src.append({"name": name, "use": "daily price history" + ("" if name in ("Yahoo Finance", "Twelve Data", "saved copy") else ", dividends not included"),
                    "ok": status["by_source"][name], "of": len(syms), "through": dates[-1], "status": "stale" if name == "saved copy" else "live",
                    "detail": "last good copy; the live sources did not answer" if name == "saved copy" else ""})
    if status["by_source"].get("none"):
        src.append({"name": "Price history", "use": "daily price history", "status": "down",
                    "detail": "no prices for " + ", ".join(s for s in syms if s not in prices)[:160]})
    out["price_sources"] = status["by_source"]
    if not OFFLINE:
        try:
            j = http_json("https://data.sec.gov/submissions/CIK0001543151.json", SEC_UA)
            src.append({"name": "SEC EDGAR", "use": "company filings, insider trades, fund holdings", "status": "live" if j.get("cik") else "down"})
        except Exception as e:
            src.append({"name": "SEC EDGAR", "use": "company filings, insider trades, fund holdings", "status": "down", "detail": str(e)[:120]})
    src.append({"name": "Twelve Data key for the engine", "use": "backup price history", "status": "live" if KEY12 else "not set"})
    out["sources"] = src
    chart_syms = [s for s in held_t + known + theses + [bench] if s in prices]
    cs = []
    for s in chart_syms:
        if s not in cs:
            cs.append(s)
    cd, _ = frame(prices, cs, WINDOW)
    maps = dict((s, dict(prices[s])) for s in cs)
    wj("state/series.json", {"as_of": started, "dates": cd, "close": dict((s, [rd(maps[s][d], 2) for d in cd]) for s in cs),
                             "note": "adjusted daily closes, one year"})
    wj("state/nav_history.json", hist)
    wj("state/quant.json", out)
    wj("state/engine_status.json", status)
    print("engine ok", started, "symbols", len(ok), "of", len(syms), "level", out.get("stress", {}).get("level"), "health", health["score"])


if __name__ == "__main__":
    main()
