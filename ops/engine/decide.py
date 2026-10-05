# Market Council decision desk: decision cards, the rebalance plan, timed plans, hold projections,
# the doomsday steps, the morning check and the paper book. Everything here is worked out from
# written rules and the engine's numbers. It prepares order tickets for Ben to place himself; it has
# no connection that could place an order. Answers arrive as small files in answers/ written by the
# app; they are read as data only.
import datetime
import json
import math
import os
import re
import traceback
import urllib.request

import numpy as np

import engine as E

QUICK = os.environ.get("MC_QUICK") == "1"
COST = 0.0025
TRANCHES = 3
TRANCHE_DAYS = 30
SNOOZE_DAYS = 14
CARD_DAYS = 7
MIN_ORDER = 5.0
BUY_MARGIN = 0.20
Z80 = 1.2816
APP = "https://benipkun.github.io/market-council-state/"
LEVELS = ["Normal", "Watch", "Defensive", "Doomsday"]
KEEP = {"Normal": 1.0, "Watch": 1.0, "Defensive": 0.6, "Doomsday": 0.3}


def r2(x, n=2):
    return E.rd(x, n)


def day(s):
    return datetime.date.fromisoformat(str(s)[:10])


def txt(s, n=160):
    return re.sub(r"[^\x20-\x7e]", "", str(s or "")).strip()[:n]


def usd(x):
    return "$%s" % ("{:,.2f}".format(abs(float(x))))


def pc(x, n=0):
    return ("%." + str(n) + "f%%") % (100.0 * float(x))


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ---------------------------------------------------------------- answers written by the app
def read_answers():
    try:
        names = sorted(os.listdir(os.path.join(E.ROOT, "answers")))
    except Exception:
        names = []
    out = []
    for n in names[-600:]:
        if not n.endswith(".json"):
            continue
        a = E.rj("answers/" + n, None)
        if not isinstance(a, dict) or str(a.get("kind")) not in ("decision", "morning", "plan", "plan_stop"):
            continue
        at = str(a.get("at") or "")
        if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at):
            m = re.match(r"(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)", n)
            at = ("%s-%s-%sT%s:%s:%sZ" % m.groups()) if m else E.now_iso()
        a["at"] = at
        a["id"] = txt(a.get("id"), 60)
        if a["id"] and re.fullmatch(r"[A-Za-z0-9:_.-]+", a["id"]):
            out.append(a)
    return out


# ---------------------------------------------------------------- the portfolio as the engine sees it
def positions(snap, quant):
    nav = float(snap.get("nav") or 0)
    assets, risk = quant.get("assets") or {}, {p.get("t"): p for p in (quant.get("health") or {}).get("positions") or []}
    out = []
    for p in snap.get("positions") or []:
        t, mv = p.get("ticker"), float(p.get("market_value") or 0)
        if not t or mv <= 0:
            continue
        a = assets.get(t) or {}
        px = float(a.get("last") or p.get("last_price") or 0)
        qty = float(p["qty"]) if p.get("qty") else (mv / px if px else None)
        cost = float(p["cost_basis"]) if p.get("cost_basis") else None
        out.append({"t": t, "mv": mv, "w": mv / nav if nav else 0.0, "px": px, "qty": qty, "cost": cost, "cls": a.get("cls") or "Equity",
                    "name": a.get("name") or t, "vol": a.get("vol_1y"), "vol20": a.get("vol_20d"), "mu": a.get("mu_est"),
                    "pl": (mv / cost - 1) if cost else None, "risk_share": (risk.get(t) or {}).get("risk_share")})
    return out


def port_vol(weights, quant):
    c, assets = quant.get("corr") or {}, quant.get("assets") or {}
    tk, m = c.get("tickers") or [], c.get("m") or []
    ts = [t for t in weights if t in tk and weights[t] > 0 and (assets.get(t) or {}).get("vol_1y")]
    if not ts:
        return None
    ws = np.array([weights[t] * assets[t]["vol_1y"] for t in ts])
    R = np.array([[m[tk.index(a)][tk.index(b)] for b in ts] for a in ts], dtype=float)
    return float(math.sqrt(max(0.0, ws @ R @ ws)))


# ---------------------------------------------------------------- item 14: the rebalance plan
def rebalance(pos, quant, lim, nav, uni, ix):
    cap, fund_cap, min_cash = lim["stock_cap"], E.FUND_CAP, lim["min_cash"]
    cur = {p["t"]: p["w"] for p in pos}
    tgt = {p["t"]: min(p["w"], cap if p["cls"] == "Equity" else fund_cap) for p in pos}
    free = 1.0 - sum(tgt.values()) - min_cash
    wide = (quant.get("opt") or {}).get("wide") or {}
    tw = dict(zip(wide.get("tickers") or [], ((wide.get("methods") or {}).get("target") or {}).get("w") or []))
    funds = {t: x for t, x in tw.items() if t not in cur and x and x > 0.005}
    if not funds:
        rows = sorted((quant.get("additions") or {}).get("rows") or [], key=lambda r: r.get("d10") or 0)[:3]
        funds = {r["t"]: 1.0 for r in rows if r.get("t") and r["t"] not in cur}
    alloc, left, pool = {}, max(0.0, free), dict(funds)
    while pool and left > 1e-6:
        tot = sum(pool.values())
        capped = [t for t in pool if left * pool[t] / tot > fund_cap + 1e-9]
        if not capped:
            for t in pool:
                alloc[t] = left * pool[t] / tot
            left = 0.0
            break
        for t in capped:
            alloc[t] = fund_cap
            left -= fund_cap
            del pool[t]
    tgt.update(alloc)
    needed = any(cur[t] - tgt[t] > 0.02 for t in cur)
    assets, meta = quant.get("assets") or {}, uni.get("assets") or {}
    rows = []
    for t in sorted(tgt, key=lambda k: (k not in cur, -cur.get(k, 0.0), -tgt[k])):
        a = assets.get(t) or {}
        rows.append({"t": t, "name": a.get("name") or (meta.get(t) or {}).get("name") or t, "cls": a.get("cls"), "now": r2(cur.get(t, 0.0), 4),
                     "target": r2(tgt[t], 4), "change_usd": r2((tgt[t] - cur.get(t, 0.0)) * nav), "eu": (meta.get(t) or {}).get("eu")})
    cash_now = max(0.0, 1.0 - sum(cur.values()))
    before, after = port_vol(cur, quant), port_vol(tgt, quant)
    turnover = sum(abs(tgt[t] - cur.get(t, 0.0)) for t in tgt) * nav
    return {"needed": bool(needed), "rows": rows, "cur": cur, "tgt": tgt, "cash_now": r2(cash_now, 4), "cash_target": r2(max(0.0, 1.0 - sum(tgt.values())), 4),
            "vol_before": r2(before, 4), "vol_after": r2(after, 4), "target_vol": lim.get("target_vol"), "largest_before": r2(max(cur.values()) if cur else 0, 4),
            "largest_after": r2(max(tgt.values()) if tgt else 0, 4), "turnover_usd": r2(turnover), "cost_usd": r2(turnover * COST), "tranches": TRANCHES,
            "method": "Every position above its limit (%s for one company, %s for one fund) is cut to the limit; positions under their limit are "
                      "left alone; %s is kept as cash; the money released goes into the funds the engine's target-volatility mix uses, in the "
                      "same proportions. Done in %d parts about a month apart. Volatility is worked out from the last 252 trading days of "
                      "prices and is an estimate." % (pc(cap), pc(fund_cap), pc(min_cash), TRANCHES),
            "note": "Fund tickers are US-listed stand-ins. In the EU buy the equivalent listed here if your broker offers it; check its cost first."}


def tranche_orders(plan, pos, nav, frac, quant, uni):
    by = {p["t"]: p for p in pos}
    assets, meta = quant.get("assets") or {}, uni.get("assets") or {}
    orders = []
    for t, target in plan["tgt"].items():
        gap = (target - plan["cur"].get(t, 0.0)) * nav * frac
        if abs(gap) < MIN_ORDER:
            continue
        px = float((assets.get(t) or {}).get("last") or (by.get(t) or {}).get("px") or 0)
        if px <= 0:
            continue
        side = "sell" if gap < 0 else "buy"
        o = {"side": side, "ticker": t, "name": (assets.get(t) or {}).get("name") or t, "usd": r2(abs(gap)), "pct_nav": r2(abs(gap) / nav, 4),
             "ref_price": r2(px, 4), "limit": r2(px * (0.995 if side == "sell" else 1.005)), "qty": r2(abs(gap) / px, 4), "eu": (meta.get(t) or {}).get("eu")}
        p = by.get(t)
        if side == "sell" and p and p.get("pl") is not None:
            g = abs(gap) * (1 - 1 / (1 + p["pl"]))
            o["tax_note"] = ("Sold above cost: a gain of about %s to report (estimate)." if g > 0 else "Sold below cost: a loss of about %s, so no gain to tax on this sale (estimate).") % usd(g)
            o["tax_plain"] = "Sold above cost: there is a gain to report (estimate)." if g > 0 else "Sold below cost, so no gain to tax on this sale (estimate)."
        orders.append(o)
    orders.sort(key=lambda o: (o["side"] != "sell", -o["usd"]))
    return orders


# ---------------------------------------------------------------- item 13: decision cards
def council_verdict(council, t):
    v = [x for x in (council or {}).get("verdicts") or [] if x.get("ticker") == t]
    return v[-1].get("verdict") if v else None


def screen(ix, pos, quant, lim, nav, cash, council, now):
    held = {p["t"]: p for p in pos}
    assets, rows, cards = quant.get("assets") or {}, [], []
    for c in (ix or {}).get("cards") or []:
        t = c.get("t")
        a, w = assets.get(t) or {}, (held.get(t) or {}).get("w", 0.0)
        fair, mos, px = c.get("fair"), c.get("mos"), a.get("last")
        row = {"t": t, "held": t in held, "price": px, "fair": fair, "mos": mos, "result": "no card"}
        v = council_verdict(council, t)
        if fair is None or mos is None or not px:
            row["why"] = "no own fair value per share to compare the price with"
        elif mos < BUY_MARGIN:
            row["why"] = "price is %s our fair value of %s; a buy card needs it at least %s below" % (
                (pc(-mos) + " above") if mos < 0 else (pc(mos) + " below"), usd(fair), pc(BUY_MARGIN))
        elif v == "fails":
            row["why"] = "cheap enough on our numbers, but the Councillor's challenge says the case fails"
        elif w >= lim["stock_cap"]:
            row["why"] = "cheap enough, but the position is already at the %s limit for one company" % pc(lim["stock_cap"])
        else:
            stop_pct = max(0.05, 2 * float(a.get("vol_20d") or a.get("vol_1y") or 0.3) / math.sqrt(252) * math.sqrt(10))
            size = min(lim["risk_per_trade"] * nav / stop_pct, (lim["stock_cap"] - w) * nav, max(0.0, cash - lim["min_cash"] * nav))
            if size < MIN_ORDER:
                row["why"] = "passes the buy rules (price %s below our fair value), but there is no free cash above the %s reserve" % (pc(mos), pc(lim["min_cash"]))
                row["result"] = "would buy with cash"
            else:
                limit = px * 1.005
                tp = min(float(fair), limit * (1 + 2 * stop_pct))
                row["result"], row["why"] = "buy card", "price %s below our fair value" % pc(mos)
                cards.append({"key": "BUY:" + t, "kind": "buy", "ticker": t, "title": "Buy %s of %s" % (usd(size), t),
                              "title_plain": "Buy %s: %s of the portfolio" % (t, pc(size / nav, 1)),
                              "orders": [{"side": "buy", "ticker": t, "name": a.get("name") or t, "usd": r2(size), "pct_nav": r2(size / nav, 4), "ref_price": r2(px, 4),
                                          "limit": r2(limit), "qty": r2(size / limit, 4), "stop": r2(limit * (1 - stop_pct)), "take_profit": r2(tp), "stop_pct": r2(stop_pct, 4)}],
                              "why": ["Price %s is %s below our own fair value of %s (five-year cash-flow estimate)." % (usd(px), pc(mos), usd(fair)),
                                      "Analysts' average target: %s." % (usd(c["target"]) if c.get("target") else "not available"),
                                      "Councillor: %s." % (v or "no verdict yet")],
                              "against": ["The fair value is an estimate that moves a lot with the discount rate; see the sensitivity table on the card.",
                                          {"t": "If the stop at %s is hit the loss is about %s, which is %s of the portfolio." % (usd(limit * (1 - stop_pct)), usd(size * stop_pct), pc(size * stop_pct / nav, 1)),
                                           "plain": "If the stop at %s is hit the loss is %s of the portfolio." % (usd(limit * (1 - stop_pct)), pc(size * stop_pct / nav, 1))}],
                              "method": "Size = risk per trade (%s of the portfolio) divided by the stop distance (twice the 20-day volatility over ten days, at least 5%%), "
                                        "capped by the one-company limit and by free cash. Take-profit = the lower of our fair value and twice the stop distance." % pc(lim["risk_per_trade"], 2)})
        rows.append(row)
    return rows, cards


def short_ideas(ix, pos, quant, lim, nav):
    # item 6: a short is only ever a card when the profile allows it; the safeguards are part of the card itself
    assets, held, ideas, cards = quant.get("assets") or {}, set(p["t"] for p in pos), [], []
    for c in (ix or {}).get("cards") or []:
        t, fair, mos = c.get("t"), c.get("fair"), c.get("mos")
        a = assets.get(t) or {}
        px = a.get("last")
        rows = E.read_cache(t)
        if t in held or fair is None or mos is None or not px or mos > -0.30 or len(rows) < 200:
            continue
        m200 = float(np.mean([v for d, v in rows[-200:]]))
        if px >= m200:
            continue
        stop_pct = max(0.08, 2 * float(a.get("vol_20d") or a.get("vol_1y") or 0.4) / math.sqrt(252) * math.sqrt(10))
        size = min(lim["risk_per_trade"] * nav / stop_pct, lim["stock_cap"] / 2 * nav)
        entry, stop = px * 0.995, px * 0.995 * (1 + stop_pct)
        target = max(float(fair), entry * (1 - 2 * stop_pct))
        ideas.append({"t": t, "price": r2(px), "fair": r2(fair), "above_fair": r2(-mos, 4), "avg_200d": r2(m200), "stop": r2(stop), "stop_pct": r2(stop_pct, 4),
                      "why": "price %s above our fair value of %s and under its 200-day average of %s" % (pc(-mos), usd(fair), usd(m200))})
        if lim.get("shorts") and size >= MIN_ORDER:
            cards.append({"key": "SHORT:" + t, "kind": "short", "ticker": t, "title": "Short %s of %s" % (usd(size), t), "title_plain": "Short %s: %s of the portfolio" % (t, pc(size / nav, 1)),
                          "orders": [{"side": "short", "ticker": t, "name": a.get("name") or t, "usd": r2(size), "pct_nav": r2(size / nav, 4), "ref_price": r2(px, 4), "limit": r2(entry),
                                      "qty": r2(size / entry, 4), "stop": r2(stop), "take_profit": r2(target), "stop_pct": r2(stop_pct, 4)}],
                          "why": ["Price %s is %s above our own fair value of %s (estimate) and under its 200-day average of %s." % (usd(px), pc(-mos), usd(fair), usd(m200))],
                          "against": ["A short can lose more than the amount sold: the loss has no ceiling if the price keeps rising.",
                                      "Borrow cost: no free source gives it, so read the fee your broker shows before placing. At an assumed 3% a year (estimate) three months cost about 0.75% of the position.",
                                      {"t": "The stop at %s is mandatory: place it as a buy-stop together with the order. If it is hit the loss is about %s (%s of the portfolio)." % (usd(stop), usd(size * stop_pct), pc(size * stop_pct / nav, 1)),
                                       "plain": "The stop at %s is mandatory: place it as a buy-stop together with the order. If it is hit the loss is %s of the portfolio." % (usd(stop), pc(size * stop_pct / nav, 1))},
                                      "Dividends paid while you are short are charged to you, and the broker can close the position if the shares are recalled."],
                          "method": "Raised only when the price is at least 30%% above our own fair value and under its 200-day average. Size = risk per trade (%s of the portfolio) "
                                    "divided by the stop distance (twice the 20-day volatility over ten days, at least 8%%), capped at half the one-company limit." % pc(lim["risk_per_trade"], 2)})
    return {"allowed": bool(lim.get("shorts")), "ideas": ideas,
            "safeguards": ["Shown only when the risk profile switches short selling on and the risk level is 4 or 5.", "Every short card states that the loss has no ceiling.",
                           "Every short card carries a stop that must be placed with the order.", "Every short card states the borrow cost, or says plainly that it must be read from the broker.",
                           "Size is capped at half the one-company limit."],
            "rule": "A share qualifies when its price is at least 30% above our own fair value and it trades under its 200-day average."}, cards


def sell_cards(pos, prof, nav):
    out, ml = [], float(prof.get("max_loss_pct") or 25) / 100.0
    for p in pos:
        if p.get("pl") is not None and p["pl"] <= -ml:
            out.append({"key": "SELL:" + p["t"], "kind": "sell", "ticker": p["t"], "title": "Sell %s: it has lost more than your maximum loss" % p["t"],
                        "orders": [{"side": "sell", "ticker": p["t"], "name": p["name"], "usd": r2(p["mv"]), "pct_nav": r2(p["mv"] / nav, 4), "ref_price": r2(p["px"], 4),
                                    "limit": r2(p["px"] * 0.995), "qty": r2(p["qty"], 4) if p.get("qty") else None}],
                        "why": ["%s is %s below what you paid; your profile's maximum loss is %s." % (p["t"], pc(-p["pl"]), pc(ml))],
                        "against": ["Selling after a fall locks the loss in; the rule exists so that one position cannot keep falling without a decision."],
                        "method": "Loss = market value / cost - 1, from the books. Trigger = the maximum loss in the risk profile."})
    return out


def settle(prev_cards, answers, ledger, now):
    today = day(now)
    cards = [dict(c) for c in prev_cards or []]
    ans = {a["id"]: a for a in answers if a.get("kind") == "decision" and a.get("answer") in ("yes", "no")}
    trades = [e for e in (ledger or {}).get("entries") or [] if e.get("status") == "applied" and e.get("ticker") and e.get("action") in ("buy", "sell")]
    for c in cards:
        a = ans.get(c["id"])
        if a and c["status"] == "open":
            c["status"] = "approved" if a["answer"] == "yes" else "declined"
            c["answered_at"], c["note"] = a["at"], txt(a.get("note"), 200) or None
        if c["status"] == "approved":
            want = set((o["ticker"], o["side"]) for o in c.get("orders") or [])
            got = set((e["ticker"], e["action"]) for e in trades if str(e.get("at") or "") >= str(c.get("answered_at") or ""))
            if want and (want & got):
                c["status"], c["done_at"] = "done", now
                c["logged"] = "%d of %d orders logged in the books" % (len(want & got), len(want))
            elif (today - day(c.get("answered_at") or c["created"])).days > 10:
                c["status"], c["closed_at"], c["closed_why"] = "lapsed", now, "approved, but no matching trade was logged within 10 days"
    return cards


def merge_cards(cards, wanted, now):
    today = day(now)
    live = {}
    for c in cards:
        if c["status"] in ("open", "approved"):
            live[c["key"]] = c
    keys = set(w["key"] for w in wanted)
    for c in cards:
        if c["status"] == "open" and c["key"] not in keys:
            c["status"], c["closed_at"] = "withdrawn", now
            c["closed_why"] = "the numbers that raised it no longer hold"
        elif c["status"] == "open" and day(c["expires"]) < today:
            c["status"], c["closed_at"], c["closed_why"] = "expired", now, "no answer within %d days" % CARD_DAYS
    for w in wanted:
        old = live.get(w["key"])
        if old and old["status"] == "approved":
            continue
        if old and old["status"] == "open":
            for k in ("title", "title_plain", "orders", "why", "against", "method", "effect", "part"):
                if k in w:
                    old[k] = w[k]
            old["refreshed"] = now
            continue
        last_no = [c for c in cards if c["key"] == w["key"] and c["status"] == "declined"]
        if last_no and (today - day(last_no[-1].get("answered_at") or last_no[-1]["created"])).days < SNOOZE_DAYS:
            continue
        n = len([c for c in cards if c["created"][:10] == now[:10]]) + 1
        c = dict(w)
        c.update({"id": "%s%s-%d" % (w["kind"][0].upper(), now[:10].replace("-", ""), n), "created": now, "status": "open",
                  "expires": (today + datetime.timedelta(days=CARD_DAYS)).isoformat(), "estimate": True})
        cards.append(c)
    return cards[-40:]


# ---------------------------------------------------------------- item 16: what holding should look like
def first_buy(ledger, t):
    b = [e for e in (ledger or {}).get("entries") or [] if e.get("ticker") == t and e.get("action") == "buy" and e.get("status") == "applied" and e.get("price")]
    if not b:
        return None
    b.sort(key=lambda e: str(e.get("at")))
    q = sum(float(e.get("qty") or 0) for e in b)
    px = (sum(float(e.get("qty") or 0) * float(e["price"]) for e in b) / q) if q else float(b[0]["price"])
    return {"date": str(b[0]["at"])[:10], "price": px}


def band(s, mu, sig, years):
    drift = (mu - sig * sig / 2) * years
    return [r2(s * math.exp(drift - Z80 * sig * math.sqrt(years))), r2(s * math.exp(drift)), r2(s * math.exp(drift + Z80 * sig * math.sqrt(years)))]


def holds(pos, quant, ix, digest, ledger, prof):
    ml = float(prof.get("max_loss_pct") or 25) / 100.0
    cards = {c.get("t"): c for c in (ix or {}).get("cards") or []}
    tech = (digest or {}).get("technicals") or {}
    out = {}
    for p in pos:
        t, s, mu, sig = p["t"], p["px"], p.get("mu"), p.get("vol")
        if not s or mu is None or not sig:
            out[t] = {"status": "no projection", "why": "no price history for this position"}
            continue
        rows = E.read_cache(t)
        px = [v for d, v in rows]
        h = {"price": r2(s), "range": [{"months": m, "low": band(s, mu, sig, m / 12.0)[0], "mid": band(s, mu, sig, m / 12.0)[1], "high": band(s, mu, sig, m / 12.0)[2]} for m in (1, 3, 12)],
             "mu": mu, "vol": sig, "levels": [], "triggers": []}
        cost_ps = (s / (1 + p["pl"])) if p.get("pl") is not None else None
        if cost_ps:
            h["levels"].append({"name": "Your average cost", "price": r2(cost_ps)})
            h["levels"].append({"name": "Maximum-loss line (%s below cost)" % pc(ml), "price": r2(cost_ps * (1 - ml))})
            h["triggers"].append("Below %s the position has lost more than your maximum loss and a sell card is raised." % usd(cost_ps * (1 - ml)))
        if len(px) >= 200:
            h["levels"].append({"name": "200-day average", "price": r2(float(np.mean(px[-200:])))})
        c = cards.get(t) or {}
        if c.get("fair"):
            h["levels"].append({"name": "Our fair value (estimate)", "price": r2(c["fair"])})
        if c.get("target"):
            h["levels"].append({"name": "Analysts' average target", "price": r2(c["target"])})
        ne = (tech.get(t) or {}).get("next_earnings_date")
        if ne:
            h["next_earnings"] = ne
            h["triggers"].append("Results on %s: the earnings review is redone and the valuation re-run with the new figures." % ne)
        h["triggers"].append("Above %s of the portfolio a trim goes into the rebalance plan." % pc(E.LEVELS[int(prof.get("risk_level") or 3)]["stock_cap"]))
        fb = first_buy(ledger, t)
        if fb and fb["price"] > 0:
            n = len([1 for d, v in rows if d > fb["date"]])
            if n >= 1:
                yrs = n / 252.0
                z = (math.log(s / fb["price"]) - (mu - sig * sig / 2) * yrs) / (sig * math.sqrt(yrs))
                lo, mid, hi = band(fb["price"], mu, sig, yrs)
                h["since_buy"] = {"date": fb["date"], "price": r2(fb["price"]), "days": n, "expected_low": lo, "expected_mid": mid, "expected_high": hi, "z": r2(z)}
                h["status"] = "inside the expected range" if abs(z) <= Z80 else ("below the expected range" if z < 0 else "above the expected range")
        if "status" not in h:
            h["status"] = "purchase date not in the books, so the path since buying cannot be checked"
        h["method"] = ("Range: four times out of five the price should end inside it if the last year's volatility (%s) continues. Centre: the engine's "
                       "return estimate (%s a year), which is an estimate, not a forecast." % (pc(sig), pc(mu, 1)))
        out[t] = h
    return out


def goal(plan, nav, fx, pvol, pmu, now):
    g = (plan or {}).get("goal") or {}
    rates = (fx or {}).get("rates") or []
    if not g.get("amount_huf") or not g.get("by") or not rates or not pvol:
        return None
    rate = float(rates[-1].get("usd_huf") or 0)
    t = day(now)
    months = (int(g["by"][:4]) - t.year) * 12 + int(g["by"][5:7]) - t.month
    if months <= 0 or rate <= 0:
        return None
    yrs, v0, need = months / 12.0, nav * rate, float(g["amount_huf"])
    drift = (pmu - pvol * pvol / 2) * yrs
    z = (math.log(need / v0) - drift) / (pvol * math.sqrt(yrs))
    rm = (1 + pmu) ** (1 / 12.0) - 1
    fv = ((1 + rm) ** months - 1) / rm if rm > 0 else months
    return {"amount_huf": need, "by": g["by"], "months": months, "usd_huf": r2(rate), "rate_date": rates[-1].get("date"), "value_now_huf": r2(v0, 0),
            "chance_without_adding": r2(1 - phi(z), 4), "middle_outcome_huf": r2(v0 * math.exp(drift), 0),
            "monthly_needed_huf": r2(max(0.0, (need - v0 * (1 + pmu) ** yrs) / fv), 0), "return_assumed": r2(pmu, 4), "vol_assumed": r2(pvol, 4),
            "method": "Today's value in forint, grown at the engine's return estimate with the portfolio's volatility; the monthly amount is what "
                      "closes the gap at that same return. An estimate, sensitive to the return assumed."}


# ---------------------------------------------------------------- item 17: what the doomsday protocol means for these holdings
def doom_steps(pos, quant, lim, nav, uni, lab):
    st = quant.get("stress") or {}
    eq = [p for p in pos if p["cls"] in ("Equity", "Equity fund")]
    total = sum(p["mv"] for p in eq)
    meta = uni.get("assets") or {}
    safe = "%s (EU: %s) or %s (EU: %s)" % ("SHY", (meta.get("SHY") or {}).get("eu") or "short government bond fund", "BIL", (meta.get("BIL") or {}).get("eu") or "Treasury-bill fund")
    steps = {"Normal": {"keep": 1.0, "sell": [], "text": "Nothing to sell. Normal rules apply."},
             "Watch": {"keep": 1.0, "sell": [], "text": "Nothing to sell. No new purchases of single companies; timed plans into broad funds continue."}}
    for lv in ("Defensive", "Doomsday"):
        need, sells, left = total * (1 - KEEP[lv]), [], {p["t"]: p["mv"] for p in eq}
        order = sorted(eq, key=lambda p: (-(p["w"] - lim["stock_cap"]), -(p.get("risk_share") or 0)))
        for p in order:
            over = max(0.0, (p["w"] - lim["stock_cap"]) * nav)
            x = min(need, over, left[p["t"]])
            if x >= 1:
                sells.append({"t": p["t"], "usd": r2(x), "share_of_position": r2(x / p["mv"], 4), "why": "above the one-company limit"})
                left[p["t"]] -= x
                need -= x
        if need >= 1:
            rs = sum((p.get("risk_share") or 0) for p in order) or 1.0
            for p in order:
                x = min(left[p["t"]], need * ((p.get("risk_share") or 0) / rs) if rs else 0)
                if x >= 1:
                    hit = [s for s in sells if s["t"] == p["t"]]
                    if hit:
                        hit[0]["usd"] = r2(hit[0]["usd"] + x)
                        hit[0]["share_of_position"] = r2(hit[0]["usd"] / p["mv"], 4)
                        hit[0]["why"] += ", then by its share of the portfolio's swings"
                    else:
                        sells.append({"t": p["t"], "usd": r2(x), "share_of_position": r2(x / p["mv"], 4), "why": "by its share of the portfolio's swings"})
        steps[lv] = {"keep": KEEP[lv], "sell": sells, "total_usd": r2(sum(s["usd"] for s in sells)),
                     "text": "Bring shares and share funds down to %s of what they are now. Sell in this order; move the money into %s." % (pc(KEEP[lv]), safe)}
    d = (lab or {}).get("doomsday") or {}
    return {"level": st.get("level"), "as_of": st.get("as_of"), "steps": steps, "safe": safe,
            "return_rule": "Step back up one level only after ten trading days in a row at a calmer level, buying back the same amounts.",
            "today": steps.get(st.get("level") or "Normal", {}).get("text"),
            "backtest": {k: d.get(k) for k in ("status", "from", "to", "years", "hold", "protocol", "trend200", "verdict", "safe_asset")} if d else None}


# ---------------------------------------------------------------- item 15: timed plans
def add_months(d, k):
    m = d.month - 1 + k
    y, m = d.year + m // 12, m % 12 + 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return datetime.date(y, m, min(d.day, last))


def timed_plans(answers, ledger, now, tranche):
    today, plans, stopped = day(now), [], set(a["id"] for a in answers if a.get("kind") == "plan_stop")
    said = {a["id"]: a for a in answers if a.get("kind") == "morning"}
    buys = [e for e in (ledger or {}).get("entries") or [] if e.get("action") == "buy" and e.get("status") == "applied"]
    for a in answers:
        if a.get("kind") != "plan":
            continue
        t = txt(a.get("ticker"), 12).upper()
        try:
            amt, times, start = float(a.get("usd")), int(a.get("times") or 1), day(a.get("start") or a["at"])
        except Exception:
            continue
        every = a.get("every") if a.get("every") in ("week", "2weeks", "month") else "month"
        if not re.fullmatch(r"[A-Z0-9.]{1,12}", t) or not (1 <= amt <= 100000) or not (1 <= times <= 120):
            continue
        parts, done, skipped, due = [], 0, 0, None
        for k in range(times):
            d = add_months(start, k) if every == "month" else start + datetime.timedelta(days=(7 if every == "week" else 14) * k)
            qid = "plan:%s:%d" % (a["id"], k + 1)
            logged = any(e.get("ticker") == t and -2 <= (day(e.get("at")) - d).days <= 5 for e in buys)
            s = said.get(qid, {}).get("answer")
            state = "done" if (logged or s == "yes") else ("skipped" if s == "no" else ("due" if d <= today else "upcoming"))
            done += state == "done"
            skipped += state == "skipped"
            if state == "due" and due is None:
                due = {"id": qid, "n": k + 1, "date": d.isoformat()}
            parts.append({"n": k + 1, "date": d.isoformat(), "state": state})
        nxt = [x for x in parts if x["state"] in ("due", "upcoming")]
        status = "stopped" if a["id"] in stopped else ("finished" if not nxt else "active")
        plans.append({"id": a["id"], "ticker": t, "usd": r2(amt), "every": every, "start": start.isoformat(), "times": times, "done": int(done),
                      "skipped": int(skipped), "next": nxt[0]["date"] if nxt and status == "active" else None, "due": due if status == "active" else None,
                      "status": status, "note": txt(a.get("note"), 120) or None, "total_usd": r2(amt * times), "parts": parts[:24]})
    if tranche:
        plans.insert(0, tranche)
    return plans


# ---------------------------------------------------------------- item 19: the paper book
def close_on(rows, d):
    for x, v in rows:
        if x >= d:
            return x, v
    return None


def paper(book, cards, pos, snap, now):
    spy = E.read_cache("SPY")
    if not spy:
        return book or {}
    last = spy[-1][0]
    if not (book or {}).get("start"):
        book = {"start": {"date": last, "cash": r2(float(snap.get("cash") or 0)), "nav": r2(float(snap.get("nav") or 0)), "spy": spy[-1][1],
                          "qty": {p["t"]: r2(p["qty"], 6) for p in pos if p.get("qty")}}, "trades": [], "cards_done": []}
    start = book["start"]
    cache = {}

    def px(t):
        if t not in cache:
            cache[t] = E.read_cache(t)
        return cache[t]

    def state_at(upto):
        q, cash = dict(start["qty"]), float(start["cash"])
        for tr in book["trades"]:
            if upto is None or tr["date"] <= upto:
                q[tr["t"]] = q.get(tr["t"], 0.0) + (tr["qty"] if tr["side"] == "buy" else -tr["qty"])
                cash += -tr["usd"] if tr["side"] == "buy" else tr["usd"] * (1 - COST)
        return q, cash
    for c in cards:
        if c["id"] in book["cards_done"] or c["status"] == "withdrawn" or not c.get("orders"):
            continue
        d0 = max(c["created"][:10], start["date"])
        first = close_on(spy, d0)
        if not first or (first[0] == start["date"] and c["created"][:10] > start["date"]):
            continue
        q, cash = state_at(None)
        for o in sorted(c["orders"], key=lambda o: o["side"] != "sell"):
            if o["side"] not in ("buy", "sell"):
                continue
            hit = close_on(px(o["ticker"]), first[0])
            if not hit or hit[0] != first[0]:
                continue
            p = hit[1]
            amt = min(float(o["usd"]), q.get(o["ticker"], 0.0) * p) if o["side"] == "sell" else min(float(o["usd"]), cash)
            if amt < 1:
                continue
            n = amt / p if o["side"] == "sell" else amt * (1 - COST) / p
            book["trades"].append({"date": first[0], "card": c["id"], "t": o["ticker"], "side": o["side"], "usd": r2(amt), "price": r2(p, 4), "qty": r2(n, 6)})
            q[o["ticker"]] = q.get(o["ticker"], 0.0) + (n if o["side"] == "buy" else -n)
            cash += -amt if o["side"] == "buy" else amt * (1 - COST)
        book["cards_done"].append(c["id"])
    hist, lastpx, dmap = [], {}, {}

    def val(qty, d):
        tot = 0.0
        for t, n in qty.items():
            if t not in dmap:
                dmap[t] = dict(px(t))
                lastpx[t] = ([v for x, v in px(t) if x <= start["date"]] or [0.0])[-1]
            lastpx[t] = dmap[t].get(d, lastpx[t])
            tot += n * lastpx[t]
        return tot
    for d, s in spy:
        if d < start["date"]:
            continue
        q, cash = state_at(d)
        hist.append({"date": d, "paper": r2(cash + val(q, d)), "frozen": r2(float(start["cash"]) + val(start["qty"], d)), "spy": r2(float(start["nav"]) * s / float(start["spy"]))})
    base = hist[0] if hist else None
    book["history"] = hist[-400:]
    if base and hist:
        e = hist[-1]
        book["summary"] = {"since": start["date"], "to": e["date"], "days": len(hist) - 1, "paper": r2(e["paper"] / base["paper"] - 1, 4), "frozen": r2(e["frozen"] / base["frozen"] - 1, 4),
                           "spy": r2(e["spy"] / base["spy"] - 1, 4), "trades": len(book["trades"]), "cards_followed": len(book["cards_done"])}
    for tr in book["trades"]:
        rows = px(tr["t"])
        if rows:
            tr["now"], tr["move"] = r2(rows[-1][1], 4), r2(rows[-1][1] / tr["price"] - 1, 4)
    book["as_of"] = now
    book["rules"] = ("PAPER, not real money. The book starts as a copy of the real holdings. It follows every decision card at the first close after the card is "
                     "raised, whatever answer you give, paying %.2f%% per trade. 'Frozen' is the same starting holdings never traded; the S&P 500 fund line "
                     "is the starting value put into the fund. Funds are priced by their US-listed stand-ins." % (100 * COST))
    return book


# ---------------------------------------------------------------- item 18: the morning check
def morning(prev, cards, plans, snap, quant, holds_, smart, answers, now):
    today = day(now)
    said = {a["id"]: a for a in answers if a.get("kind") in ("morning", "decision")}
    qs = []
    for c in cards:
        if c["status"] == "open":
            qs.append({"id": c["id"], "kind": "decision", "text": c["title"] + "?", "text_plain": (c.get("title_plain") or c["title"]) + "?",
                       "detail": (c.get("why") or [""])[0], "yes": "Approve", "no": "Decline"})
    for p in plans:
        if p.get("due") and p.get("kind") != "rebalance":
            qs.append({"id": p["due"]["id"], "kind": "morning", "text": "Timed plan: buy %s of %s (part %d of %d), due %s. Placed?" % (usd(p["usd"]), p["ticker"], p["due"]["n"], p["times"], p["due"]["date"]),
                       "text_plain": "Timed plan: buy %s (part %d of %d), due %s. Placed?" % (p["ticker"], p["due"]["n"], p["times"], p["due"]["date"]),
                       "detail": "Yes marks this part done; log the trade so the books match. No skips this part.", "yes": "Placed", "no": "Skip"})
    asof = str(snap.get("as_of") or "")[:10]
    if asof:
        qid = "books:" + asof
        qs.append({"id": qid, "kind": "morning", "text": "Any trade since the books were last updated (%s) that is not logged yet?" % asof,
                   "detail": "Yes opens the trade log. No confirms the books are complete.", "yes": "Yes, log it", "no": "No, complete"})
    for q in qs:
        a = said.get(q["id"])
        if a and a.get("answer") in ("yes", "no"):
            q["answer"], q["answered_at"] = a["answer"], a["at"]
    waiting = [q for q in qs if not q.get("answer")]
    lines = []
    st = quant.get("stress") or {}
    lines.append("Stress level %s." % str(st.get("level") or "unknown").upper())
    d1 = ((quant.get("portfolio") or {}).get("ret_at_todays_weights") or {}).get("1D")
    if d1 is not None:
        lines.append("Portfolio %s%s on the last trading day." % ("+" if d1 >= 0 else "-", pc(abs(d1), 1)))
    for t, h in (holds_ or {}).items():
        ne = h.get("next_earnings")
        if ne and 0 <= (day(ne) - today).days <= 14:
            lines.append("%s reports on %s." % (t, ne))
    n = len((smart or {}).get("alerts") or [])
    if n:
        lines.append("%d insider alert%s." % (n, "" if n == 1 else "s"))
    out = {"date": today.isoformat(), "questions": qs, "waiting": len(waiting), "summary": lines, "sent_date": (prev or {}).get("sent_date"), "sent_note": (prev or {}).get("sent_note")}
    hour = int(now[11:13])
    if out["sent_date"] != today.isoformat() and today.weekday() < 5 and hour >= 5 and not QUICK:
        topic = os.environ.get("NTFY_OUT")
        head = ("%d question%s need%s your yes or no. " % (len(waiting), "" if len(waiting) == 1 else "s", "s" if len(waiting) == 1 else "")) if waiting else "Nothing needs a decision. "
        body = {"topic": topic, "title": "Morning check", "message": head + " ".join(lines), "click": APP + "#today", "tags": ["sunrise"]}
        if not topic or E.OFFLINE:
            out["sent_note"] = "not sent: no phone channel in this run"
        else:
            try:
                req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    ok = r.status == 200
                out["sent_date"], out["sent_note"] = (today.isoformat(), "sent " + now) if ok else (out["sent_date"], "not delivered")
            except Exception as e:
                out["sent_note"] = "not delivered: " + str(e)[:80]
        out["message"] = body["message"]
    return out


def main():
    now = E.now_iso()
    if not QUICK:
        try:
            import lab
            lab.main()
        except Exception:
            print("lab failed")
            traceback.print_exc()
    quant, snap = E.rj("state/quant.json", None), E.rj("treasury/snapshot.json", {}) or {}
    if not quant or not snap.get("nav"):
        print("decide: no engine numbers or no snapshot")
        return
    uni, ledger = E.rj("ops/engine/universe.json", {}) or {}, E.rj("treasury/ledger.json", {}) or {}
    ix, digest = E.rj("research/cards/index.json", {}) or {}, E.rj("digests/latest.json", {}) or {}
    council, lab_out = E.rj("state/council.json", {}) or {}, E.rj("state/lab.json", {}) or {}
    prev, smart = E.rj("state/decisions.json", {}) or {}, E.rj("state/smart_money.json", {}) or {}
    prof, lim = quant.get("profile") or {}, (quant.get("profile") or {}).get("limits") or E.LEVELS[3]
    nav, cash = float(snap["nav"]), float(snap.get("cash") or 0)
    pos = positions(snap, quant)
    answers = read_answers()

    plan = rebalance(pos, quant, lim, nav, uni, ix)
    old = settle(prev.get("cards") or [], answers, ledger, now)
    done = [c for c in old if c.get("kind") == "rebalance" and c["status"] in ("approved", "done")]
    part = min(TRANCHES, len(done) + 1)
    wanted, tranche = [], None
    due = day(now)
    if done:
        due = day(done[-1].get("answered_at") or done[-1]["created"]) + datetime.timedelta(days=TRANCHE_DAYS)
    if plan["needed"]:
        frac = 1.0 / (TRANCHES - part + 1)
        orders = tranche_orders(plan, pos, nav, frac, quant, uni)
        after = {t: plan["cur"].get(t, 0.0) + (plan["tgt"][t] - plan["cur"].get(t, 0.0)) * frac for t in plan["tgt"]}
        v1 = port_vol(after, quant)
        top = max(pos, key=lambda p: p["w"]) if pos else None
        if orders and due <= day(now):
            sells, buys = [o for o in orders if o["side"] == "sell"], [o for o in orders if o["side"] == "buy"]
            why = []
            if top and top["w"] > lim["stock_cap"]:
                why.append("%s is %s of the portfolio; the %s profile allows %s in one company." % (top["t"], pc(top["w"], 1), prof.get("label") or "risk", pc(lim["stock_cap"])))
                if top.get("risk_share"):
                    why.append("%s causes %s of the portfolio's swings." % (top["t"], pc(top["risk_share"])))
            if plan["vol_before"] and v1 and plan["vol_after"]:
                why.append("Estimated volatility: %s now, %s after this part, %s after all %d parts (target for the profile: %s)." % (
                    pc(plan["vol_before"]), pc(v1), pc(plan["vol_after"]), TRANCHES, pc(lim.get("target_vol") or 0)))
            c = {x.get("t"): x for x in ix.get("cards") or []}.get(top["t"] if top else None) or {}
            if c.get("fair") and c.get("mos") is not None and c["mos"] < 0:
                why.append("Our own valuation puts %s at %s, %s under the price (estimate)." % (top["t"], usd(c["fair"]), pc(-c["mos"])))
            against = [{"t": o["tax_note"], "plain": o["tax_plain"]} for o in sells if o.get("tax_note")]
            if c.get("target") and top and c["target"] > top["px"]:
                against.append("Analysts' average target for %s is %s, %s above the price; trimming gives up part of that if they are right." % (top["t"], usd(c["target"]), pc(c["target"] / top["px"] - 1)))
            against.append({"t": "Costs are assumed at %.2f%% per trade: about %s for this part." % (100 * COST, usd(sum(o["usd"] for o in orders) * COST)),
                            "plain": "Costs are assumed at %.2f%% per trade." % (100 * COST)})
            against.append(plan["note"])
            wanted.append({"key": "REBAL", "kind": "rebalance", "ticker": top["t"] if top else None, "part": part,
                           "title": "Rebalance, part %d of %d: sell %s, buy %d fund%s" % (part, TRANCHES, ", ".join("%s of %s" % (usd(o["usd"]), o["ticker"]) for o in sells) or "nothing",
                                                                                       len(buys), "" if len(buys) == 1 else "s"),
                           "title_plain": "Rebalance, part %d of %d: sell %s, buy %d fund%s" % (part, TRANCHES, ", ".join("%s of the portfolio from %s" % (pc(o["pct_nav"], 1), o["ticker"]) for o in sells) or "nothing",
                                                                                             len(buys), "" if len(buys) == 1 else "s"),
                           "orders": orders, "why": why, "against": against, "method": plan["method"],
                           "effect": {"vol_before": plan["vol_before"], "vol_after_part": r2(v1, 4), "vol_after_all": plan["vol_after"],
                                      "largest_before": plan["largest_before"], "largest_after_part": r2(max(after.values()), 4), "largest_after_all": plan["largest_after"]}})
        tranche = {"id": "rebalance", "kind": "rebalance", "ticker": "portfolio", "every": "month", "times": TRANCHES, "done": len(done), "status": "active",
                   "next": max(due, day(now)).isoformat(), "note": "Rebalance plan: part %d of %d." % (part, TRANCHES)}
    rows, buy = screen(ix, pos, quant, lim, nav, cash, council, now)
    shorts, short_cards = short_ideas(ix, pos, quant, lim, nav)
    wanted += buy + sell_cards(pos, prof, nav) + short_cards
    cards = merge_cards(old, wanted, now)
    for k in ("cur", "tgt"):
        plan.pop(k, None)
    plan["part"], plan["next_part_due"] = part, max(due, day(now)).isoformat() if plan["needed"] else None

    hp = holds(pos, quant, ix, digest, ledger, prof)
    pvol = (quant.get("portfolio") or {}).get("vol_1y")
    pmu = sum(p["w"] * (p.get("mu") or 0.0) for p in pos)
    plans = timed_plans(answers, ledger, now, tranche)
    out = {"as_of": now, "profile": {"label": prof.get("label"), "level": prof.get("risk_level"), "max_loss_pct": prof.get("max_loss_pct"), "limits": lim},
           "cards": cards, "screen": rows, "shorts": shorts, "rebalance": plan, "plans": plans, "holds": hp,
           "portfolio_range": {"months": 12, "low": r2(math.exp((pmu - pvol * pvol / 2) - Z80 * pvol) - 1, 4), "mid": r2(math.exp(pmu - pvol * pvol / 2) - 1, 4),
                               "high": r2(math.exp((pmu - pvol * pvol / 2) + Z80 * pvol) - 1, 4), "mu": r2(pmu, 4), "vol": pvol} if pvol else None,
           "goal": goal(E.rj("state/plan.json", {}), nav, E.rj("state/fx.json", {}), pvol, pmu, now),
           "doomsday": doom_steps(pos, quant, lim, nav, uni, lab_out),
           "spreading": lab_out.get("spreading"),
           "answers": {"read": len(answers), "last": answers[-1]["at"] if answers else None},
           "inputs": {"quant": quant.get("as_of"), "books": snap.get("as_of"), "cards": ix.get("as_of"), "lab": lab_out.get("as_of")},
           "disclaimer": "Worked out from written rules and estimates. Not advice. Nothing here places an order; you place every order yourself."}
    out["morning"] = morning(prev.get("morning"), cards, plans, snap, quant, hp, smart, answers, now)
    E.wj("state/decisions.json", out)
    E.wj("state/paper_book.json", paper(E.rj("state/paper_book.json", None), cards, pos, snap, now))
    print("decide ok:", len([c for c in cards if c["status"] == "open"]), "open cards,", len(plans), "plans,", out["morning"]["waiting"], "questions waiting;", out["morning"].get("sent_note"))


if __name__ == "__main__":
    main()
