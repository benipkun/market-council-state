# Market Council daily brief.
# Reads the repo's JSON records and writes brief/index.html: one static page with no scripts,
# so it opens the same in any phone browser. The repo is public, so it never shows balances.
# Every section is built separately; a broken or missing file only blanks its own section.
import datetime
import html
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "brief", "index.html")
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SIG = {"rumor": "Rumor", "confirmed_news": "News", "mispricing_undervalued": "Undervalued",
       "mispricing_overvalued": "Overvalued", "technical": "Technical"}
MIS = ("mispricing_undervalued", "mispricing_overvalued")
UTC = datetime.timezone.utc


def load(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def obj(v):
    return v if isinstance(v, dict) else {}


def arr(v):
    return v if isinstance(v, list) else []


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def usd(v, dp=2, signed=False):
    x = num(v)
    if x is None:
        return "&mdash;"
    sign = "&minus;" if x < 0 else ("+" if signed and x > 0 else "")
    return sign + "$" + "{:,.{p}f}".format(abs(x), p=dp)


def pct(v):
    x = num(v)
    if x is None:
        return "&mdash;"
    return ("&minus;" if x < 0 else "+") + "{:.1f}%".format(abs(x))


def parse(ts):
    s = str(ts or "")
    for fmt, n in (("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%dT%H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.datetime.strptime(s[:n], fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def last_sunday(year, month):
    d = datetime.date(year + (month == 12), month % 12 + 1, 1) - datetime.timedelta(days=1)
    while d.weekday() != 6:
        d -= datetime.timedelta(days=1)
    return d


def budapest(dt):
    one = datetime.time(1, 0)
    start = datetime.datetime.combine(last_sunday(dt.year, 3), one).replace(tzinfo=UTC)
    end = datetime.datetime.combine(last_sunday(dt.year, 10), one).replace(tzinfo=UTC)
    return dt + datetime.timedelta(hours=2 if start <= dt < end else 1)


def when(ts):
    dt = parse(ts)
    if dt is None:
        return "&mdash;"
    b = budapest(dt)
    return "{} {} {}, {:02d}:{:02d}".format(DAY[b.weekday()], b.day, MON[b.month - 1], b.hour, b.minute)


def day(ts):
    dt = parse(ts)
    if dt is None:
        return e(ts)
    if len(str(ts)) > 10:
        dt = budapest(dt)
    return "{} {}".format(dt.day, MON[dt.month - 1])


def ago(ts, now):
    dt = parse(ts)
    if dt is None:
        return "never"
    m = int((now - dt).total_seconds() // 60)
    if m < 60:
        return "{} min ago".format(max(m, 0))
    if m < 48 * 60:
        return "{} h ago".format(m // 60)
    return "{} days ago".format(m // 1440)


def days_until(date_str, today):
    dt = parse(date_str)
    return None if dt is None else (dt.date() - today).days


def tag(text, cls=""):
    return '<span class="tag {}">{}</span>'.format(cls, e(text))


def tile(label, value, sub, cls=""):
    return ('<div class="tile"><div class="tl">{}</div><div class="tv mono {}">{}</div>'
            '<div class="ts">{}</div></div>').format(label, cls, value, sub)


def nice(raw):
    if raw <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(raw))
    m = raw / p
    return (1 if m <= 1 else 2 if m <= 2 else 5 if m <= 5 else 10) * p


def chart(series):
    pts = []
    for p in arr(series):
        p = obj(p)
        pts.append((p.get("date"), num(p.get("pl_usd")) or 0.0, num(p.get("spy_pl_usd")) or 0.0))
    if len(pts) < 2:
        return '<p class="note">The chart starts once there are two days of data.</p>'
    w, h, left, right, top, bottom = 340, 190, 46, 52, 12, 22
    vals = [0.0] + [a for _, a, _ in pts] + [b for _, _, b in pts]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    step = nice((hi - lo) / 4)
    lo, hi = math.floor(lo / step) * step, math.ceil(hi / step) * step
    n = len(pts)

    def x(i):
        return left + (w - left - right) * i / (n - 1)

    def y(v):
        return top + (h - top - bottom) * (1 - (v - lo) / (hi - lo))

    out = ['<svg viewBox="0 0 {} {}" role="img" aria-label="Practice picks versus SPY, cumulative dollars">'.format(w, h)]
    for k in range(int(round((hi - lo) / step)) + 1):
        v = lo + k * step
        yy = y(v)
        out.append('<line class="gl{}" x1="{}" x2="{}" y1="{:.1f}" y2="{:.1f}"/>'.format(
            " z" if abs(v) < step / 1000 else "", left, w - right, yy, yy))
        out.append('<text class="ax" x="{}" y="{:.1f}" dy="3.5" text-anchor="end">{}</text>'.format(left - 6, yy, usd(v, 0)))
    out.append('<text class="ax" x="{}" y="{}">{}</text>'.format(left, h - 5, day(pts[0][0])))
    out.append('<text class="ax" x="{}" y="{}" text-anchor="end">{}</text>'.format(w - right, h - 5, day(pts[-1][0])))
    for idx, var in ((2, "--s2"), (1, "--s1")):
        d = " ".join("{}{:.1f} {:.1f}".format("L" if i else "M", x(i), y(p[idx])) for i, p in enumerate(pts))
        out.append('<path d="{}" fill="none" style="stroke:var({})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'.format(d, var))
    ya, yb, xe = y(pts[-1][1]), y(pts[-1][2]), x(n - 1)
    out.append('<circle cx="{:.1f}" cy="{:.1f}" r="4" style="fill:var(--s2);stroke:var(--sf)" stroke-width="2"/>'.format(xe, yb))
    out.append('<circle cx="{:.1f}" cy="{:.1f}" r="4" style="fill:var(--s1);stroke:var(--sf)" stroke-width="2"/>'.format(xe, ya))
    if abs(ya - yb) >= 14:
        out.append('<text class="lbl" x="{:.1f}" y="{:.1f}" dy="4">Picks</text>'.format(xe + 8, ya))
        out.append('<text class="lbl dim" x="{:.1f}" y="{:.1f}" dy="4">SPY</text>'.format(xe + 8, yb))
    out.append("</svg>")
    rows = "".join('<tr><td>{}</td><td class="r">{}</td><td class="r">{}</td></tr>'.format(
        day(d), usd(a, 2, True), usd(b, 2, True)) for d, a, b in reversed(pts))
    legend = ('<div class="legend"><span><i style="background:var(--s1)"></i>Picks (practice money)</span>'
              '<span><i style="background:var(--s2)"></i>SPY, same money</span></div>')
    table = ('<details><summary>Show the daily numbers</summary><div class="tw"><table><thead><tr><th>Day</th>'
             '<th class="r">Picks</th><th class="r">SPY</th></tr></thead><tbody>{}</tbody></table></div></details>').format(rows)
    return legend + '<div class="chart">' + "".join(out) + "</div>" + table


def pick_card(p, tech):
    p = obj(p)
    t = obj(tech.get(p.get("ticker")))
    ps = obj(p.get("position_suggestion"))
    lean = p.get("lean") or "neutral"
    sig = p.get("signal_type")
    tags = tag(lean, "bull" if lean == "bullish" else "bear" if lean == "bearish" else "")
    if sig:
        tags += tag(SIG.get(sig, sig))
    if t.get("region") == "EU":
        tags += tag("EU", "eu")
    if p.get("severity") is not None:
        tags += tag("sev {}".format(p.get("severity")))
    price = '<span class="px mono">{}</span>'.format(usd(t.get("price"))) if num(t.get("price")) is not None else ""
    size = ""
    if ps.get("tier") not in (None, "none") and (num(ps.get("suggested_size_usd")) or 0) > 0:
        size = '<div class="size"><b class="mono">{}</b> {} size</div>'.format(usd(ps.get("suggested_size_usd")), e(ps.get("tier")))
    elif ps:
        size = '<div class="size none">No size suggested &middot; watch only</div>'
    body = ""
    text = p.get("why") or p.get("brief")
    if text:
        body += "<p>{}</p>".format(e(text))
    if p.get("bull_case") or p.get("bear_case"):
        body += ('<div class="cases"><div class="case bull"><h4>Bull case</h4><p>{}</p></div>'
                 '<div class="case bear"><h4>Bear case</h4><p>{}</p></div></div>').format(
            e(p.get("bull_case") or "-"), e(p.get("bear_case") or "-"))
    questions = arr(obj(p.get("advisor_questions")).get("questions"))
    if questions:
        body += '<p class="q"><b>Question to ask yourself:</b> {}</p>'.format(e(questions[0]))
    return '<div class="pick"><div class="pt"><span class="tk">{}</span>{}{}</div>{}{}</div>'.format(
        e(p.get("ticker")), tags, price, size, body)


def main():
    now = datetime.datetime.now(UTC)
    today = budapest(now).date()
    dig = obj(load("digests/latest.json"))
    hist = obj(load("digests/history.json"))
    paper = obj(load("state/paper.json"))
    theses = obj(load("state/theses.json"))
    status = obj(load("state/status.json"))
    fx = obj(load("state/fx.json"))
    research = obj(load("research/index.json"))
    tech = obj(dig.get("technicals"))
    picks = [obj(p) for p in arr(dig.get("picks"))]
    news = [p for p in picks if p.get("signal_type") not in MIS]
    mis = [p for p in picks if p.get("signal_type") in MIS]
    issues = [str(x) for x in arr(status.get("data_issues"))]
    th = next((obj(x) for x in arr(theses.get("theses")) if obj(x).get("status") != "done"), None)
    totals = obj(paper.get("totals"))
    sections = []

    # 1. At a glance
    diff = num(totals.get("diff_usd"))
    dec = obj(load("state/decisions.json"))
    desk = obj(dec.get("desk"))
    open_cards = [obj(c) for c in arr(dec.get("cards")) if obj(c).get("status") == "open"]
    live = [c for c in open_cards if not c.get("greyed")]
    grey = [c for c in open_cards if c.get("greyed")]
    near = [obj(x) for x in arr(desk.get("near"))][:3]
    glance = tile("On your decision desk", str(len(live)),
                  "waiting for your yes or no" if live else "closest candidates are listed below", "up" if live else "")
    glance += tile("New picks this cycle", str(len(picks)), "{} news, {} mispriced".format(len(news), len(mis)))
    glance += tile("Practice picks vs SPY", usd(diff, 2, True) if diff is not None else "&mdash;",
                   "ahead of the index" if (diff or 0) >= 0 else "behind the index",
                   "up" if (diff or 0) >= 0 else "dn")
    if th:
        d_open = days_until(th.get("catalyst_date"), today)
        glance += tile(e(th.get("title") or "Idea"), "{} days".format(d_open) if d_open is not None and d_open >= 0 else "&mdash;",
                       "{} {}".format(e(th.get("ticker")), usd(obj(th.get("quote")).get("price"))))
    glance += tile("Data", "OK" if not issues else "{} issue{}".format(len(issues), "" if len(issues) == 1 else "s"),
                   "all sources working" if not issues else "see System health", "up" if not issues else "wn")
    sections.append(("glance", "At a glance", '<div class="tiles">{}</div>'.format(glance), ""))

    # Decision desk: standing ideas from every source. A card stays until it is answered or expires,
    # so this section is not empty just because nothing new crossed a line this hour.
    if dec:
        body = ""
        for c in live:
            levels = ""
            if num(c.get("entry")) is not None and num(c.get("stop")) is not None and num(c.get("take_profit")) is not None:
                levels = '<p class="note">Entry about {} &middot; stop-loss {} &middot; take-profit {} &middot; estimates</p>'.format(
                    usd(c.get("entry")), usd(c.get("stop")), usd(c.get("take_profit")))
            body += '<div class="pick"><div class="pt"><span class="tk">{}</span>{}</div><p>{}</p>{}<p class="note">Valid until {}</p></div>'.format(
                e(c.get("ticker") or str(c.get("kind") or "card").upper()), tag(c.get("source") or c.get("kind") or "card"),
                e(c.get("title_plain") or c.get("title")), levels, day(c.get("expires")))
        if not live:
            body += '<p class="empty">No card passes every gate right now. The closest candidates, and what each still needs:</p>'
        if near and not live:
            rows = ""
            for x in near:
                needs = "; ".join(str(obj(m).get("needs")) for m in arr(x.get("missing")) if obj(m).get("needs"))
                rows += '<div class="kv"><span><b>{}</b><br>{}</span><span class="r">{} of {} checks<br><span class="note">needs {}</span></span></div>'.format(
                    e(x.get("t")), e(x.get("name")), e(x.get("score")), e(x.get("of") or 7), e(needs or "more data"))
            body += '<div class="box">{}</div>'.format(rows)
        if grey:
            body += '<p class="note">{} more idea{} shown in the app as not worth it at small sizes, because fees would take the gain.</p>'.format(
                len(grey), "" if len(grey) == 1 else "s")
        hours = None
        made = parse(dec.get("as_of"))
        if made is not None:
            hours = (now - made).total_seconds() / 3600
        body += '<p class="note">Desk refreshed {}{}. <a href="../">Open the app</a> to see sizes, fees and funding, and to answer. Nothing is bought or sold for you.</p>'.format(
            ago(dec.get("as_of"), now), " &middot; <b>stale</b>" if hours is not None and hours > 36 else "")
        sections.append(("desk", "Decision desk", body, ""))

    # 2 and 3. Picks
    if news:
        body = "".join(pick_card(p, tech) for p in news)
    else:
        body = '<p class="empty">Nothing news-driven cleared the bar this cycle. That is the normal state.</p>'
    sections.append(("attention", "Needs attention", body, ""))
    body = "".join(pick_card(p, tech) for p in mis) if mis else '<p class="empty">No valuation gap cleared the bar this cycle.</p>'
    sections.append(("mispriced", "Mispriced", body, ""))

    # 4. Idea tracker
    if th:
        q = obj(th.get("quote"))
        d_open = days_until(th.get("catalyst_date"), today)
        d_check = days_until(th.get("check_in"), today)
        body = '<div class="prh"><span class="tk">{}</span><span class="mono big2">{}</span>{}</div>'.format(
            e(th.get("ticker")), usd(q.get("price")),
            ' <span class="mono {}">{}</span>'.format("up" if (num(q.get("change_pct")) or 0) >= 0 else "dn", pct(q.get("change_pct"))) if num(q.get("change_pct")) is not None else "")
        body += '<p class="note">Price {} &middot; {}</p>'.format(ago(q.get("at"), now), e(q.get("source") or "no source"))
        body += "<p>{}</p>".format(e(th.get("idea")))
        body += '<div class="tiles">{}{}</div>'.format(
            tile("Opening day", "{} days".format(d_open) if d_open is not None and d_open >= 0 else "&mdash;", day(th.get("catalyst_date"))),
            tile("Your check-in", "{} days".format(d_check) if d_check is not None and d_check >= 0 else "&mdash;", day(th.get("check_in"))))
        rows = ""
        for f in arr(th.get("films")):
            f = obj(f)
            if num(f.get("actual_opening_usd")) is not None:
                line = "opened with " + usd(f.get("actual_opening_usd"), 0)
            elif num(f.get("tracking_usd_low")) is not None:
                line = "tracking " + usd(f.get("tracking_usd_low"), 0) + (" to " + usd(f.get("tracking_usd_high"), 0) if num(f.get("tracking_usd_high")) else "")
            else:
                line = "no tracking numbers yet"
            rows += '<div class="kv"><span><b>{}</b><br>{}</span><span class="r">{}{}<br><span class="note">{}</span></span></div>'.format(
                e(f.get("title")), e(f.get("studio")), tag("moved", "bear") + " " if f.get("date_status") == "moved" else "",
                day(f.get("release_date")), line)
        body += '<div class="box">{}</div>'.format(rows)
        flags = sorted((obj(x) for x in arr(th.get("red_flags"))), key=lambda x: str(x.get("date")), reverse=True)
        body += "<h3>Red flags</h3>"
        body += "".join('<div class="ev"><div class="d">{}</div><div>{}<div class="note">{} &middot; {}</div></div></div>'.format(
            day(x.get("date")), e(x.get("headline")), e(x.get("kind")), e(x.get("source"))) for x in flags[:4]) or '<p class="empty">None found so far.</p>'
        facts = [obj(x) for x in arr(th.get("log"))][:6]
        if facts:
            body += "<h3>Latest facts</h3>" + "".join('<div class="ev"><div class="d">{}</div><div>{}<div class="note">{}</div></div></div>'.format(
                day(x.get("date")), e(x.get("text")), e(x.get("source"))) for x in facts)
        body += '<p class="note">Facts collected for your idea, not a recommendation.</p>'
        sections.append(("idea", e(th.get("title") or "Idea tracker"), body, ""))

    # 5. Practice portfolio
    if totals:
        hit = num(totals.get("hit_rate"))
        body = '<div class="tiles">{}{}{}{}</div>'.format(
            tile("Picks", usd(totals.get("pl_usd"), 2, True), "{} positions, {} open".format(e(totals.get("positions") or 0), e(totals.get("open") or 0)),
                 "up" if (num(totals.get("pl_usd")) or 0) >= 0 else "dn"),
            tile("SPY, same money", usd(totals.get("spy_pl_usd"), 2, True), "the do-nothing alternative",
                 "up" if (num(totals.get("spy_pl_usd")) or 0) >= 0 else "dn"),
            tile("Picks minus SPY", usd(diff, 2, True), "ahead" if (diff or 0) >= 0 else "behind", "up" if (diff or 0) >= 0 else "dn"),
            tile("Hit rate", "{:.0f}%".format(hit * 100) if hit is not None else "&mdash;",
                 "{} of {} closed made money".format(e(totals.get("closed_wins") or 0), e(totals.get("closed"))) if totals.get("closed") else "none closed yet"))
        body += chart(paper.get("series"))
        rows = "".join(
            '<tr><td><b>{}</b></td><td>{}</td><td>{}</td><td class="r">{}</td><td class="r {}">{}</td><td class="r">{}</td><td>{}</td></tr>'.format(
                e(r.get("ticker")), day(r.get("flagged_at")), e(r.get("direction")), usd(r.get("notional_usd")),
                "up" if (num(r.get("pl_usd")) or 0) >= 0 else "dn", usd(r.get("pl_usd"), 2, True), usd(r.get("spy_pl_usd"), 2, True),
                "closed" if r.get("status") == "closed" else "day {} of 20".format(e(r.get("days_held") or 0)))
            for r in sorted((obj(x) for x in arr(paper.get("positions"))), key=lambda x: str(x.get("flagged_at")), reverse=True))
        if rows:
            body += ('<div class="tw"><table><thead><tr><th>Ticker</th><th>Flagged</th><th>Side</th><th class="r">Money</th>'
                     '<th class="r">Pick P/L</th><th class="r">SPY P/L</th><th>Status</th></tr></thead><tbody>{}</tbody></table></div>').format(rows)
        body += ('<p class="note">Every bullish pick is a practice buy and every bearish pick a practice short, held 20 trading days; '
                 'the same money goes into SPY at the same moment. Before costs.</p>')
        sections.append(("practice", "Do the picks beat the index?", body, ""))

    # 6. Watchlist
    rows = ""
    for k in sorted(tech, key=lambda s: (obj(tech[s]).get("region") == "EU", s)):
        t = obj(tech[k])
        p, s50 = num(t.get("price")), num(t.get("sma50"))
        rel = (p - s50) / s50 * 100 if p is not None and s50 else None
        rows += '<tr><td><b>{}</b>{}</td><td class="r mono">{}</td><td class="r {}">{}</td><td class="r">{}</td><td>{}</td></tr>'.format(
            e(k), " " + tag("EU", "eu") if t.get("region") == "EU" else "", usd(p),
            "" if rel is None else ("up" if rel >= 0 else "dn"), pct(rel),
            "{:.0f}".format(num(t.get("rsi14"))) if num(t.get("rsi14")) is not None else "&mdash;",
            day(t.get("next_earnings_date")) if t.get("next_earnings_date") else "&mdash;")
    if rows:
        body = ('<div class="tw"><table><thead><tr><th>Ticker</th><th class="r">Price</th><th class="r">vs 50-day</th>'
                '<th class="r">RSI</th><th>Earnings</th></tr></thead><tbody>{}</tbody></table></div>'
                '<p class="note">RSI under 30 is often called oversold, over 70 overbought.</p>').format(rows)
        sections.append(("watch", "Watchlist", body, ""))

    # 7. Headlines
    scrap = sorted((obj(x) for x in arr(dig.get("scrap"))), key=lambda x: str(x.get("first_seen")), reverse=True)[:12]
    if scrap:
        body = "".join('<div class="ev"><div class="d">{}</div><div><b>{}</b> {}</div></div>'.format(
            day(x.get("first_seen")), e(x.get("ticker")), e(x.get("headline"))) for x in scrap)
        sections.append(("news", "Latest headlines", body, ""))

    # 8. Research notes
    notes = [obj(x) for x in arr(research.get("notes"))]
    notes = [x for x in notes if str(x.get("url") or "").startswith("research/") and str(x.get("url")).endswith(".html")
             and all(c.isalnum() or c in "/._-" for c in str(x.get("url")))]
    if notes:
        body = "".join('<a class="note-link" href="../{}"><b>{}</b> {}<br><span class="note">{} &middot; {}</span></a>'.format(
            e(x.get("url")), e(x.get("ticker")), e(x.get("title")), day(x.get("date")), e(x.get("summary"))) for x in
            sorted(notes, key=lambda x: str(x.get("date")), reverse=True))
        sections.append(("research", "Research notes", body, ""))

    # 9. System health
    loop = obj(status.get("loop"))
    rates = arr(fx.get("rates"))
    last_rate = obj(rates[-1]) if rates else {}
    rows = '<div class="kv"><span>Market pipeline</span><span>{}</span></div>'.format(ago(dig.get("as_of"), now))
    rows += '<div class="kv"><span>Bookkeeping</span><span>{}</span></div>'.format(ago(status.get("books_ran_at"), now))
    rows += '<div class="kv"><span>Trade inbox self-test</span><span class="{}">{}</span></div>'.format(
        "up" if loop.get("ok") else "dn" if loop.get("ok") is False else "", "passed" if loop.get("ok") else "failed" if loop.get("ok") is False else "not checked yet")
    rows += '<div class="kv"><span>Exchange rate</span><span>{} Ft per $ &middot; {} {}</span></div>'.format(
        "{:.2f}".format(num(last_rate.get("usd_huf"))) if num(last_rate.get("usd_huf")) else "&mdash;", e(last_rate.get("source")), day(last_rate.get("date")))
    body = '<div class="box">{}</div>'.format(rows)
    if issues:
        body += "<h3>Data problems right now</h3><ul>" + "".join("<li>{}</li>".format(e(x)) for x in issues) + "</ul>"
        if any("Twelve Data" in x for x in issues):
            body += '<p class="fix"><b>Fix:</b> on claude.ai open Settings, then Connectors, then Twelve Data, and connect it again.</p>'
    else:
        body += '<p class="empty">No data problems reported.</p>'
    sections.append(("health", "System health", body, ""))

    nav = "".join('<a href="#{}">{}</a>'.format(sid, title) for sid, title, _, _ in sections)
    secs = "".join('<section id="{}" class="{}"><h2><span class="n">{}</span>{}</h2>{}</section>'.format(
        sid, cls, i + 1, title, body) for i, (sid, title, body, cls) in enumerate(sections))
    page = TEMPLATE.replace("@UPDATED@", when(now.isoformat())).replace("@PIPE@", when(dig.get("as_of")))
    page = page.replace("@NAV@", nav).replace("@SECTIONS@", secs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(page)
    print("wrote", OUT, len(page), "bytes,", len(sections), "sections")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'">
<meta name="theme-color" content="#060a13">
<link rel="icon" href="../icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<title>Market Council brief</title>
<style>
:root{--bg:#0d0f15;--sf:#161a23;--sf2:#1d222c;--bd:#2a3140;--tx:#e9ebf0;--dim:#8f96a6;--ac:#6ea8fe;--acs:#18243b;
--up:#3fb98c;--ups:#12281f;--dn:#e0715f;--dns:#2a1714;--wn:#d9a441;--wns:#2b2210;--grid:#232a37;--s1:#3987e5;--s2:#d95926;color-scheme:dark}
@media (prefers-color-scheme: light){
:root{--bg:#f5f6f8;--sf:#ffffff;--sf2:#edeff3;--bd:#d8dbe2;--tx:#15181e;--dim:#5d6373;--ac:#2557c7;--acs:#e4ecfc;
--up:#17794f;--ups:#dcefe5;--dn:#b0402d;--dns:#f8e5e1;--wn:#8a6314;--wns:#f6ecd6;--grid:#e6e8ee;--s1:#2a78d6;--s2:#eb6834;color-scheme:light}
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
a{color:var(--ac)}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.dn{color:var(--dn)}.wn{color:var(--wn)}
header{max-width:760px;margin:0 auto;padding:calc(10px + env(safe-area-inset-top)) 16px 14px}
.back{display:inline-flex;align-items:center;min-height:40px;font-size:13.5px;font-weight:700;text-decoration:none}
h1{font-size:25px;line-height:1.2;margin:4px 0 4px;letter-spacing:-.02em}
.sub{font-size:12.5px;color:var(--dim)}
nav{position:sticky;top:0;z-index:5;background:var(--bg);border-top:1px solid var(--bd);border-bottom:1px solid var(--bd)}
nav div{max-width:760px;margin:0 auto;display:flex;gap:6px;overflow-x:auto;padding:8px 16px;scrollbar-width:none}
nav div::-webkit-scrollbar{display:none}
nav a{flex:none;font-size:12.5px;font-weight:700;padding:7px 12px;border-radius:99px;background:var(--sf2);color:var(--dim);text-decoration:none;white-space:nowrap}
main{max-width:760px;margin:0 auto;padding:14px 16px calc(36px + env(safe-area-inset-bottom))}
section{background:var(--sf);border:1px solid var(--bd);border-radius:14px;padding:16px;margin-bottom:14px;scroll-margin-top:62px}
h2{display:flex;align-items:center;gap:10px;font-size:17px;line-height:1.25;margin:0 0 12px;letter-spacing:-.01em}
h3{font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--dim);margin:16px 0 6px}
h4{margin:0 0 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.n{flex:none;width:26px;height:26px;border-radius:8px;background:var(--acs);color:var(--ac);font-size:13px;font-weight:800;
display:inline-flex;align-items:center;justify-content:center}
p{margin:0 0 10px}
.note{font-size:12px;color:var(--dim)}
.empty{color:var(--dim);margin:0}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:9px}
@media (min-width:640px){.tiles{grid-template-columns:repeat(4,1fr)}}
.tile{background:var(--sf2);border-radius:11px;padding:11px 12px}
.tl{font-size:10.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--dim)}
.tv{font-size:20px;font-weight:800;margin-top:3px;letter-spacing:-.02em}
.ts{font-size:11.5px;color:var(--dim);margin-top:1px}
.pick{border:1px solid var(--bd);border-left:3px solid var(--ac);border-radius:12px;padding:12px 13px;margin-bottom:10px}
.pick:last-child{margin-bottom:0}
.pick p{font-size:14px;margin:8px 0 0}
.pt{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tk{font-weight:800;font-size:16px}
.px{margin-left:auto;font-weight:700}
.tag{font-size:9.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;padding:3px 6px;border-radius:5px;background:var(--sf2);color:var(--dim)}
.tag.bull{background:var(--ups);color:var(--up)}
.tag.bear{background:var(--dns);color:var(--dn)}
.tag.eu{background:var(--acs);color:var(--ac)}
.size{margin-top:9px;padding:8px 10px;border-radius:8px;background:var(--ups);font-size:13px}
.size b{font-size:18px;color:var(--up)}
.size.none{background:var(--sf2);color:var(--dim)}
.cases{display:grid;grid-template-columns:1fr;gap:8px;margin-top:9px}
@media (min-width:560px){.cases{grid-template-columns:1fr 1fr}}
.case{border-radius:9px;padding:9px 10px}
.case p{font-size:13px;margin:0}
.case.bull{background:var(--ups)}.case.bull h4{color:var(--up)}
.case.bear{background:var(--dns)}.case.bear h4{color:var(--dn)}
.q{font-size:13px;color:var(--dim)}
.prh{display:flex;align-items:baseline;gap:10px}
.big2{font-size:22px;font-weight:800}
.box{border:1px solid var(--bd);border-radius:11px;padding:4px 12px;margin-top:10px}
.kv{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--bd);font-size:14px}
.kv:first-child{border-top:0}
.kv>span:first-child{color:var(--dim)}
.kv b{color:var(--tx)}
.r{text-align:right}
.ev{display:flex;gap:12px;padding:9px 0;border-top:1px solid var(--bd);font-size:14px}
.ev:first-child,h3+.ev{border-top:0}
.ev .d{flex:none;width:52px;font-size:12px;font-weight:800;color:var(--dim);padding-top:2px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:14px 0 4px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{display:inline-block;width:14px;height:2px;border-radius:1px}
.chart svg{display:block;width:100%;height:auto}
.gl{stroke:var(--grid);stroke-width:1}.gl.z{stroke:var(--bd)}
.ax{fill:var(--dim);font-size:10.5px}
.lbl{fill:var(--tx);font-size:11.5px;font-weight:700}.lbl.dim{fill:var(--dim)}
details{margin:6px 0 10px}
summary{cursor:pointer;font-size:12.5px;font-weight:700;color:var(--ac);min-height:34px;display:flex;align-items:center}
.tw{overflow-x:auto;border:1px solid var(--bd);border-radius:10px;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);padding:7px 9px;border-bottom:1px solid var(--bd);white-space:nowrap}
td{padding:7px 9px;border-bottom:1px solid var(--bd);white-space:nowrap}
tr:last-child td{border-bottom:0}
ul{margin:0;padding-left:18px}
li{margin-bottom:6px}
.fix{margin-top:10px;padding:10px 12px;border-radius:10px;background:var(--wns);font-size:13.5px}
.note-link{display:block;padding:11px 12px;border:1px solid var(--bd);border-radius:11px;margin-bottom:8px;text-decoration:none;color:var(--tx)}
footer{font-size:11.5px;color:var(--dim);line-height:1.6;padding:2px 4px 0}
:root{--bg:#060a13;--sf:#0a101c;--sf2:#111a2b;--bd:#22304a;--tx:#e6edf7;--dim:#8d9bb5;--ac:#7cc4ff;--acs:#0f2238;--up:#3ddc97;--ups:#0b2a1f;--dn:#ff6b6b;--dns:#33141a;--wn:#f0b429;--wns:#2b2208;--grid:#16203a;--s1:#4aa3ff;--s2:#f2a541;color-scheme:dark}
body{font:13px/1.55 ui-monospace,"SF Mono","Cascadia Mono","Roboto Mono",Menlo,Consolas,monospace;font-variant-numeric:tabular-nums;background-image:linear-gradient(rgba(124,196,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(124,196,255,.05) 1px,transparent 1px);background-size:28px 28px}
section,.tile,.pick,.tag,.size,.case,.box,.tw,.fix,.note-link,nav a,.n{border-radius:3px}
section{background:rgba(10,16,28,.9)}
h1{text-transform:uppercase;letter-spacing:.12em;font-size:16px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em}
nav{background:rgba(6,10,19,.96)}
nav a{text-transform:uppercase;letter-spacing:.06em;font-size:11px;border:1px solid var(--bd);background:var(--sf)}
.size{background:var(--sf2)}
</style>
</head>
<body>
<header>
<a class="back" href="../#today">&larr; Open the app</a>
<h1>Market Council brief</h1>
<div class="sub">Updated @UPDATED@ Budapest time &middot; market data from @PIPE@</div>
</header>
<nav aria-label="Sections"><div>@NAV@</div></nav>
<main>
@SECTIONS@
<footer>
<p>Rebuilt automatically each weekday morning, midday and evening. Your balances are not on this page because it is public;
they are in the app's Portfolio tab. Facts and mechanical rules, not personal financial advice.</p>
</footer>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    main()
