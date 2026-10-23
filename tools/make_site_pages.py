#!/usr/bin/env python3
"""Turn a saved citizensinformation.ie sitemap into site-pages.csv, the site's own page list.

The dashboard uses it to check cited and clicked addresses against pages that exist: how many of the
site's English information pages AskCI has cited, and which cited addresses are not on the list (topic
index pages are listed; old or moved addresses are not).

Save the sitemap first (this script makes no network calls), e.g. in a browser or with
    curl -A "Mozilla/5.0" -o sitemap.xml https://www.citizensinformation.ie/sitemap.xml
then:
    python3 tools/make_site_pages.py sitemap.xml            # writes site-pages.csv in the repo root

Columns: URL (normalised as make_usage.py's norm_url does), Language (en, ga or other), Kind (information
for pages three or more levels below /en/ or /ga/, index for topic and section pages above that; an
approximation by address depth), LastMod (from the sitemap), ListedOn (the date this file was made).
"""
import csv, os, re, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_usage import norm_url

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 tools/make_site_pages.py sitemap.xml")
    xml = open(sys.argv[1], encoding="utf-8").read()
    entries = re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]*)</lastmod>)?", xml)
    if not entries:
        sys.exit(f"{sys.argv[1]}: no <url><loc> entries; is this the sitemap?")
    rows, seen = [], set()
    for loc, lastmod in entries:
        u = norm_url(loc)
        if not u or u.lower() in seen:
            continue
        seen.add(u.lower())
        m = re.match(r"^https://www\.citizensinformation\.ie/(en|ga)(/.*)?$", u, re.I)
        lang = m.group(1).lower() if m else "other"
        depth = len([p for p in (m.group(2) or "").split("/") if p]) if m else 0
        rows.append([u, lang, "information" if depth >= 3 else "index", lastmod.strip(), date.today().isoformat()])
    with open(os.path.join(REPO, "site-pages.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["URL", "Language", "Kind", "LastMod", "ListedOn"]); w.writerows(sorted(rows))
    en_info = sum(1 for r in rows if r[1] == "en" and r[2] == "information")
    print(f"wrote site-pages.csv: {len(rows)} pages, {en_info} English information pages")


if __name__ == "__main__":
    main()
