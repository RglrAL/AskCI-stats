#!/usr/bin/env python3
"""Cited addresses that are not on the site (brief §96): cited-not-found.csv, for the page's Data status watch and the
era scorecard line.

    python3 tools/make_not_found_pages.py

Reads the page fetcher's log (exports/site-text/index.csv: every fetch of a cited page, with its HTTP status) and
pages-cited.csv (each cited address with its first and last citation date and its citations). An address whose most
recent fetch returned 404 is "not on the site": it is written with its citation dates and count, the day it was last
checked, and whether a fetch of it ever succeeded (1: the page existed once and has gone; 0: never found). Public
addresses and counts only. The page states what was found, not why.
"""
import csv, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")   # the published files the page reads (brief §97)
sys.path.insert(0, os.path.join(REPO, "tools"))
from fetch_pages import norm_url

IDX = os.path.join(REPO, "exports", "site-text", "index.csv")
OUT = os.path.join(DATA, "cited-not-found.csv")


def main():
    if not os.path.exists(IDX): sys.exit(f"no fetch log at {os.path.relpath(IDX, REPO)}: run tools/fetch_pages.py first")
    latest, ever = {}, set()
    with open(IDX, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            u = r["url"]
            if r["file"]: ever.add(u)
            if u not in latest or r["fetched"] >= latest[u]["fetched"]: latest[u] = r
    gone = {u: r for u, r in latest.items() if r["status"] == "http 404"}
    rows = []
    with open(os.path.join(DATA, "pages-cited.csv"), encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            u = norm_url(r["URL"])
            if u in gone:
                rows.append({"URL": r["URL"], "FirstCited": r["FirstCited"], "LastCited": r["LastCited"], "Citations": r["Citations"],
                             "Checked": gone[u]["fetched"], "EverFetched": int(u in ever)})
    rows.sort(key=lambda r: (-int(r["Citations"] or 0), r["URL"]))
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["URL", "FirstCited", "LastCited", "Citations", "Checked", "EverFetched"]); w.writeheader(); w.writerows(rows)
    cites = sum(int(r["Citations"] or 0) for r in rows)
    print(f"wrote cited-not-found.csv: {len(rows)} cited addresses not on the site ({sum(r['EverFetched'] for r in rows)} found once, since gone), "
          f"{cites} citations; last cited {max((r['LastCited'] for r in rows), default='—')}")


if __name__ == "__main__":
    main()
