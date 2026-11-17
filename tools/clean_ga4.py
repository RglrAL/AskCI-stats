#!/usr/bin/env python3
"""Clean website analytics exports before they are committed (brief §108, handoff 9b).

Google Analytics records whatever address a browser reports, so a raw export can carry a local file path, an IP
address, markup or an email address inside a "page path", and per-click tracking IDs in a query string. The repo is
public, so only plain site addresses are kept:

  ga4/categories-and-views.csv   a path is kept when it is a plain address under /en/ or /ga/ (segments of letters,
                                 digits, dots, underscores and hyphens), lowercased, with rows that then coincide
                                 summed. Every other path is summed into one "(other paths)" row per month. The page
                                 reads /en/ paths only, lowercased: at the first clean 0.015% of /en/ views were folded
                                 (addresses with spaces, brackets or markup), no site section by more than 0.06%.
  ga4/Ask-ci-click-throughs*.csv the page location keeps only the utm_source, utm_medium and utm_campaign parameters
                                 (per-click IDs such as fbclid are dropped); a location that is not then a plain
                                 citizensinformation.ie address becomes "(other paths)". Rows that coincide are summed,
                                 column by column (the users column is then an upper bound).

Prints counts only, never a path.

Usage:
    python3 tools/clean_ga4.py                  # clean every tracked export in data/ga4/ in place
    python3 tools/clean_ga4.py FILE ...         # clean these
    python3 tools/clean_ga4.py --check [FILE …] # exit 1 if any file would change (the hook and the deploy run this)
"""
import argparse, csv, glob, io, os, re, sys
from urllib.parse import urlsplit, parse_qsl, urlencode

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GA4 = os.path.join(REPO, 'data', 'ga4')
OTHER = '(other paths)'
PLAIN_PATH = re.compile(r'^/(?:en|ga)(?:/[a-z0-9][a-z0-9._-]*)*/?$')
SITE = 'https://www.citizensinformation.ie'
KEEP_PARAMS = ('utm_source', 'utm_medium', 'utm_campaign')
PATH_COL = 'Page path and screen class'


def plain_path(p):
    p = (p or '').strip().lower()
    return p if PLAIN_PATH.match(p) else None


def num(v):
    try: x = float(str(v).replace(',', ''))
    except ValueError: return 0
    return int(x) if x == int(x) else x


def clean_views(text):
    """categories-and-views.csv: (new text, rows folded, rows merged). A version without its header row (one past
    version, 8 Oct 2026) is read with the standard columns and written back without one."""
    headerless = PATH_COL not in text.split('\n', 1)[0]
    if headerless: text = 'Year,Month,' + PATH_COL + ',Views\n' + text
    rdr = csv.DictReader(io.StringIO(text, newline='')); cols = rdr.fieldnames
    out, order, folded, n = {}, [], 0, 0
    for r in rdr:
        n += 1
        p = plain_path(r[PATH_COL])
        if p is None: folded += 1; p = OTHER
        k = (r['Year'], r['Month'], p)
        if k not in out: out[k] = {**r, PATH_COL: p, 'Views': 0}; order.append(k)
        out[k]['Views'] += num(r['Views'])
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\n'); w.writeheader()
    for k in order: w.writerow(out[k])
    new = buf.getvalue()
    return (new.split('\n', 1)[1] if headerless else new), folded, n - len(order)


def clean_location(u):
    s = urlsplit(u.strip())
    if f'{s.scheme}://{s.netloc}'.lower() != SITE or not PLAIN_PATH.match(s.path.lower()): return None
    q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k in KEEP_PARAMS]
    return SITE + s.path.lower() + ('?' + urlencode(q) if q else '')


def clean_clicks(text):
    """Ask-ci-click-throughs export: header lines kept as they are; (new text, rows changed, rows merged)."""
    trail = text[len(text.rstrip('\n')):]   # the export's trailing blank lines, put back as they were
    lines = text.rstrip('\n').split('\n')
    head = 0
    while head < len(lines) and not re.match(r'^\d{8},', lines[head]): head += 1
    rows = list(csv.reader(lines[head:]))
    out, order, changed, n = {}, [], 0, 0
    for r in rows:
        if not r or not re.fullmatch(r'\d{8}', r[0]):   # blank lines and the totals row are kept as they are
            order.append(('tail', len(order))); out[order[-1]] = r; continue
        n += 1
        loc = clean_location(r[1])
        if loc is None: loc = OTHER
        if loc != r[1]: changed += 1
        k = (r[0], loc)
        if k not in out: out[k] = [r[0], loc] + [0] * (len(r) - 2); order.append(k)
        out[k][2:] = [a + num(b) for a, b in zip(out[k][2:], r[2:])]
    buf = io.StringIO(newline='')
    w = csv.writer(buf, lineterminator='\n')
    for k in order: w.writerow(out[k])
    body = buf.getvalue()
    new = '\n'.join(lines[:head]) + ('\n' if head else '') + body.rstrip('\n') + trail
    return new, changed, n - sum(1 for k in order if k[0] != 'tail')


def clean(path):
    with open(path, encoding='utf-8-sig', newline='') as f: text = f.read()
    name = os.path.basename(path)
    if name == 'categories-and-views.csv': return text, *clean_views(text)
    if name.startswith('Ask-ci-click-throughs'): return text, *clean_clicks(text)
    return text, text, 0, 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*')
    ap.add_argument('--check', action='store_true', help='report only; exit 1 if any file would change')
    a = ap.parse_args()
    files = a.files or sorted([os.path.join(GA4, 'categories-and-views.csv')] + glob.glob(os.path.join(GA4, 'Ask-ci-click-throughs*.csv')))
    dirty = 0
    for p in files:
        if not os.path.exists(p): continue
        old, new, changed, merged = clean(p)
        rel = os.path.relpath(p, REPO)
        if new == old: print(f'{rel}: clean'); continue
        dirty += 1
        if a.check:
            print(f'{rel}: {changed} row(s) with a non-site path or tracking parameter. Run: python3 tools/clean_ga4.py "{rel}"', file=sys.stderr)
        else:
            with open(p, 'w', encoding='utf-8', newline='') as f: f.write(new)
            print(f'{rel}: {changed} row(s) folded or stripped, {merged} merged')
    return 1 if (a.check and dirty) else 0


if __name__ == '__main__':
    sys.exit(main())
