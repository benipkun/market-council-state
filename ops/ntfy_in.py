# Moves new messages from Ben's private ntfy "ask" channel into inbox/queue/ for the Trade Inbox.
# Run by .github/workflows/listen.yml with the file of ntfy JSON lines as its only argument.
# Each message becomes one queue file whose single line is "ask: <text>"; the Trade Inbox treats
# messages from this channel as questions only, never as money commands.
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINCE = os.path.join(ROOT, "inbox", "ntfy_since.txt")
QUEUE = os.path.join(ROOT, "inbox", "queue")
NL = chr(10)


def main(path):
    last = None
    count = 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(m, dict) or m.get("event") != "message":
                continue
            last = m.get("id") or last
            text = " ".join(str(m.get("message") or "").split())[:1000]
            if not text:
                continue
            when = datetime.datetime.fromtimestamp(int(m.get("time") or 0), datetime.timezone.utc)
            safe_id = "".join(c for c in str(m.get("id") or "") if c.isalnum())[:16]
            os.makedirs(QUEUE, exist_ok=True)
            name = "{}-ntfy-{}.md".format(when.strftime("%Y%m%dT%H%M%SZ"), safe_id)
            with open(os.path.join(QUEUE, name), "w", encoding="utf-8") as out:
                out.write("ask: " + text + NL)
            count += 1
    if last:
        with open(SINCE, "w", encoding="utf-8") as f:
            f.write(str(last) + NL)
    print("new messages:", count)


if __name__ == "__main__":
    main(sys.argv[1])
