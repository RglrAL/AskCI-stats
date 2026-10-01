#!/usr/bin/env python3
"""Generate usage.csv (Date, Questions, Sessions) from one or more AskCI QA feed exports.

Questions = turns received per day (one row per turn in the feed).
Sessions  = conversations started per day (distinct Conversation ID with Turn # == 1).

Dates are taken in the feed's own timezone, which is unconfirmed; nothing else from
the feed crosses into the dashboard — only these daily aggregates.

Usage:
    python3 tools/make_usage.py qa-feed_*.csv -o usage.csv
    python3 tools/make_usage.py qa-feed_*.csv --compare usage.csv   # check against an existing file, write nothing
"""
import argparse, csv, sys
from collections import defaultdict
from datetime import datetime

TS_FORMAT = "%b %d, %Y %H:%M"   # e.g. "Jun 06, 2026 19:50"


def aggregate(files):
    turns = defaultdict(int)
    first = defaultdict(set)
    bad = 0
    for f in files:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                ts = (row.get("Timestamp") or "").strip()
                try:
                    d = datetime.strptime(ts, TS_FORMAT).date()
                except ValueError:
                    bad += 1
                    continue
                turns[d] += 1
                if (row.get("Turn #") or "").strip() == "1":
                    first[d].add(row.get("Conversation ID"))
    return turns, first, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", help="write usage.csv here")
    ap.add_argument("--compare", help="existing usage.csv to compare against (no write)")
    a = ap.parse_args()
    turns, first, bad = aggregate(a.files)
    if bad:
        print(f"warning: {bad} rows with unreadable Timestamp skipped", file=sys.stderr)
    days = sorted(turns)
    if not days:
        sys.exit("no rows parsed")
    rows = [(d.strftime("%d-%b-%y"), turns[d], len(first[d])) for d in days]
    print(f"{len(days)} days, {days[0]} to {days[-1]}, {sum(turns.values())} turns, {sum(len(v) for v in first.values())} conversations")
    if a.compare:
        existing = {}
        with open(a.compare, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    d = datetime.strptime(r["Date"].replace("Sept", "Sep"), "%d-%b-%y").date()
                except ValueError:
                    continue
                existing[d] = (int(r["Questions"].replace(",", "")), int(r["Sessions"].replace(",", "")))
        for d in days:
            e = existing.get(d)
            print(f"  {d}: feed {turns[d]} turns / {len(first[d])} conv · existing {e[0] if e else '—'} / {e[1] if e else '—'}")
        return
    if a.out:
        with open(a.out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "Questions", "Sessions"])
            w.writerows(rows)
        print(f"wrote {a.out}")
    else:
        for r in rows:
            print(",".join(map(str, r)))


if __name__ == "__main__":
    main()
