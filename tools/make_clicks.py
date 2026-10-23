#!/usr/bin/env python3
"""Turn GA4 click-through exports into the dashboard's two click files.

Input: GA4 Exploration CSV exports of page views on citizensinformation.ie whose URL carries
AskCI's citation tags (utm_medium=chatbot&utm_campaign=citation). Each export has '#' comment
lines (one of them the YYYYMMDD-YYYYMMDD range), a two-row header (device groups, then
Date, Page location, Views, Total users, Sessions per group and for Totals), a Grand total row,
then one row per day and page. Export them unsampled (one or two months at a time; the shield
icon must read 100% of data).

Outputs (aggregate counts and public page URLs only):
  ga4/clicks-daily.csv        Date, Source, Views, Sessions, Mobile, Desktop, Tablet, OtherDevice
  ga4/clicks-pages-daily.csv  Date, URL, Source, Views

Source, from utm_source: embed (askci-embed, the pop-up on citizensinformation.ie; the feed's
Modal), app (askci-app, the standalone site; the feed's Web), other (anything else, e.g. the
early 'askci' tag). URLs are normalised as make_usage.py's norm_url does, so they join to
citations-monthly.csv. A click-through is a page view, reloads included.

Refuses to write anything if an export doesn't add up: device views must sum to the totals on
every row, rows must sum to the Grand total, no day/page may appear in two exports, and the
exports' ranges must be continuous.

Usage:
    python3 tools/make_clicks.py                                   # ga4/Ask-ci-click-throughs*.csv
    python3 tools/make_clicks.py ga4/export-a.csv ga4/export-b.csv
"""
import csv, glob, os, re, sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_usage import norm_url   # one URL normalisation for cited and clicked pages

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = {"askci-embed": "embed", "askci-app": "app"}
DEVICES = ["mobile", "desktop", "tablet"]   # any other GA4 device category (e.g. smart tv) goes to OtherDevice


def read_export(path):
    """Return (range_from, range_to, rows); rows are (date, url, views, sessions, {device: views})."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.reader(fh))
    rng = next((re.search(r"(\d{8})-(\d{8})", r[0]).groups() for r in raw
                if r and r[0].startswith("#") and re.search(r"\d{8}-\d{8}", r[0])), None)
    body = [r for r in raw if r and not r[0].startswith("#") and any(c.strip() for c in r)]
    groups, names = body[0], body[1]
    def cols(group):
        return {names[i]: i for i, g in enumerate(groups) if g == group}
    tot = cols("Totals")
    if not {"Views", "Sessions"} <= set(tot):
        sys.exit(f"{path}: no Totals Views/Sessions columns")
    dev = {g: cols(g)["Views"] for g in dict.fromkeys(groups) if g not in ("", "Device category", "Totals") and "Views" in cols(g)}
    grand = next((r for r in body if r[-1:] == ["Grand total"]), None)
    rows, bad = [], 0
    for r in body[2:]:
        if not r[0].isdigit():
            continue
        v = int(r[tot["Views"]] or 0)
        dv = {(d if d in DEVICES else "other"): 0 for d in dev}
        for d, i in dev.items(): dv[d if d in DEVICES else "other"] += int(r[i] or 0)
        if sum(dv.values()) != v:
            bad += 1
        rows.append((datetime.strptime(r[0], "%Y%m%d").date(), r[1], v, int(r[tot["Sessions"]] or 0), dv))
    if bad:
        sys.exit(f"{path}: device views do not sum to the totals on {bad} row(s)")
    if grand and sum(x[2] for x in rows) != int(grand[tot["Views"]] or 0):
        sys.exit(f"{path}: rows sum to {sum(x[2] for x in rows)} views but the Grand total is {grand[tot['Views']]}")
    if not rng:
        sys.exit(f"{path}: no YYYYMMDD-YYYYMMDD range line in the header")
    return datetime.strptime(rng[0], "%Y%m%d").date(), datetime.strptime(rng[1], "%Y%m%d").date(), rows


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(REPO, "ga4", "Ask-ci-click-throughs*.csv")))
    if not files:
        sys.exit("no click-through exports found (ga4/Ask-ci-click-throughs*.csv)")
    exports = sorted((read_export(f) + (f,) for f in files), key=lambda e: e[0])
    for a, b in zip(exports, exports[1:]):
        if (b[0] - a[1]).days != 1:
            sys.exit(f"exports are not continuous: {os.path.basename(a[3])} ends {a[1]}, {os.path.basename(b[3])} starts {b[0]}")
    daily = defaultdict(lambda: defaultdict(int))     # (date, source) -> counters
    pages = defaultdict(int)                          # (date, url, source) -> views
    seen = set()
    for _, _, rows, f in exports:
        for d, url, v, s, dv in rows:
            if (d, url) in seen:
                sys.exit(f"{os.path.basename(f)}: {d} {url} also appears in another export")
            seen.add((d, url))
            m = re.search(r"[?&]utm_source=([^&#]*)", url)
            src = SOURCES.get(m.group(1).lower() if m else "", "other")
            c = daily[(d, src)]
            c["views"] += v; c["sessions"] += s
            for k in DEVICES + ["other"]: c[k] += dv.get(k, 0)
            nu = norm_url(url)
            if nu: pages[(d, nu, src)] += v
    out = os.path.join(REPO, "ga4")
    with open(os.path.join(out, "clicks-daily.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["Date", "Source", "Views", "Sessions", "Mobile", "Desktop", "Tablet", "OtherDevice"])
        for (d, src), c in sorted(daily.items()):
            w.writerow([d.isoformat(), src, c["views"], c["sessions"], c["mobile"], c["desktop"], c["tablet"], c["other"]])
    with open(os.path.join(out, "clicks-pages-daily.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["Date", "URL", "Source", "Views"])
        for (d, u, src), v in sorted(pages.items()):
            if v: w.writerow([d.isoformat(), u, src, v])
    tv = sum(c["views"] for c in daily.values())
    by = defaultdict(int)
    for (_, src), c in daily.items(): by[src] += c["views"]
    print(f"{len(files)} export(s), {exports[0][0]} to {exports[-1][1]}: {tv} click-throughs "
          f"({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}), {len({u for _, u, _ in pages})} pages")
    print(f"wrote ga4/clicks-daily.csv ({len(daily)} rows) and ga4/clicks-pages-daily.csv ({sum(1 for v in pages.values() if v)} rows)")


if __name__ == "__main__":
    main()
