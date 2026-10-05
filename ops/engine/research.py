# Market Council research engine, step 0: find out which free public sources answer from GitHub's servers.
# It only reads public pages and writes state/probe.json; the research tools are built on what answers.
import datetime
import json
import os
import urllib.request

NL = chr(10)
ROOT = os.environ.get("MC_ROOT", ".")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HEAD = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}
NQ = "https://api.nasdaq.com/api/"
SOURCES = [
    ["nasdaq quote", NQ + "quote/UBER/info?assetclass=stocks"],
    ["nasdaq financials", NQ + "company/UBER/financials?frequency=1"],
    ["nasdaq financials adr", NQ + "company/NVO/financials?frequency=1"],
    ["nasdaq insider trades", NQ + "company/UBER/insider-trades?limit=10&type=ALL&sortColumn=lastDate&sortOrder=DESC"],
    ["nasdaq institutional holders", NQ + "company/UBER/institutional-holdings?limit=10&type=TOTAL&sortColumn=marketValue&sortOrder=DESC"],
    ["nasdaq price target", NQ + "analyst/UBER/targetprice"],
    ["nasdaq ratings", NQ + "analyst/UBER/ratings"],
    ["nasdaq earnings surprise", NQ + "company/UBER/earnings-surprise"],
    ["nasdaq earnings forecast", NQ + "analyst/UBER/earnings-forecast"],
    ["nasdaq sec filings", NQ + "company/UBER/sec-filings?limit=5&sortColumn=filed&sortOrder=desc"],
    ["nasdaq news", NQ + "news/topic/articlebysymbol?q=uber%7Cstocks&offset=0&limit=5&fallback=true"],
    ["nasdaq dividends", NQ + "quote/TLT/dividends?assetclass=etf"],
    ["nasdaq history", NQ + "quote/UBER/historical?assetclass=stocks&fromdate=2026-09-01&todate=2026-10-05&limit=40"],
    ["cnbc quote", "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=UBER&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1"],
    ["sec edgar submissions", "https://data.sec.gov/submissions/CIK0001543151.json"],
    ["sec edgar feed", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001543151&type=4&dateb=&owner=include&count=10&output=atom"],
    ["openinsider", "http://openinsider.com/screener?s=UBER&fd=180&cnt=20"],
    ["dataroma", "https://www.dataroma.com/m/stock.php?sym=UBER"],
    ["capitol trades", "https://bff.capitoltrades.com/trades?page=1&pageSize=10"],
    ["house disclosures index", "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip"],
    ["senate trades dataset", "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"],
    ["treasury bill rates", "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_bill_rates&field_tdr_date_value=2026&page&_format=csv"],
    ["fred 10-year yield", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2026-08-01"],
    ["stooq", "https://stooq.com/q/d/l/?s=uber.us&i=d"],
]


def probe(url):
    out = {"ok": False}
    try:
        req = urllib.request.Request(url, headers=HEAD if "sec.gov" not in url else {"User-Agent": "Market Council personal research benipkun@users.noreply.github.com"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(400000)
            out["http"] = resp.status
            out["bytes"] = len(body)
            text = body[:600].decode("utf-8", "replace")
            out["start"] = " ".join(text.split())[:220]
            out["ok"] = resp.status == 200 and len(body) > 200
    except Exception as e:
        out["error"] = str(e)[:140]
    return out


def main():
    res = {"as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": {}}
    for name, url in SOURCES:
        res["sources"][name] = probe(url)
    path = os.path.join(ROOT, "state", "probe.json")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(res, indent=1) + NL)
    print("probe:", ", ".join(k for k, v in res["sources"].items() if v["ok"]))


if __name__ == "__main__":
    main()
