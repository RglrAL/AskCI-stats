#!/usr/bin/env python3
"""Dated local snapshots of the public pages the answers cite (brief §75, response layer 2: figures).

For every URL in pages-cited.csv, fetch the page from citizensinformation.ie and keep the text of its <main> element as
exports/site-text/<hash>__<lastmod>.txt, where <lastmod> is the page's LastMod from site-pages.csv (the sitemap) on the
day of the fetch. A page whose LastMod has not changed is not fetched again; a page whose LastMod moved gets a new file
beside the old one, so later checks can read the page as it was. exports/site-text/index.csv lists every snapshot.
Public pages, no feed text; the folder is git-ignored only because it is large.

Usage:
    python3 tools/fetch_pages.py                 # fetch what is missing (cited pages)
    python3 tools/fetch_pages.py --limit 50      # a trial
"""
import argparse, csv, hashlib, html, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "exports", "site-text")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def norm_url(u):
    u = (u or "").strip().rstrip(".,;)")
    m = re.match(r"^(https?)://([^/?#]+)([^?#]*)", u, re.I)
    if not m: return None
    host = m.group(2).lower()
    if host == "citizensinformation.ie": host = "www.citizensinformation.ie"
    path = m.group(3).rstrip("/") or "/"
    return f"https://{host}{path}"


def page_key(u): return hashlib.sha1(norm_url(u).encode()).hexdigest()[:16]


def main_text(page):
    m = re.search(r"<main\b[^>]*>(.*?)</main>", page, re.S | re.I)
    body = m.group(1) if m else page
    body = re.sub(r"<(script|style|nav|footer|aside)\b.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>|</(p|li|h\d|tr|td|th|div|section)>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n\s*\n+", "\n", body)).strip()


def fetch(u):
    """curl, not urllib: this machine's python has no certificate store, and curl has the system's."""
    import subprocess
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "30", "-A", UA, "-H", "Accept: text/html", "-w", "\n%{http_code}", u + "/"], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    if r.returncode or not code.startswith("2"): raise RuntimeError(f"http {code or r.stderr.strip()[:40]}")
    return int(code), body


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.5, help="pause after each fetch, per worker; the site refuses connections when hurried")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lastmod = {}
    with open(os.path.join(REPO, "site-pages.csv"), encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            n = norm_url(r["URL"])
            if n: lastmod[n] = (r.get("LastMod") or "")[:10]
    with open(os.path.join(REPO, "pages-cited.csv"), encoding="utf-8-sig", newline="") as fh:
        urls = [norm_url(r["URL"]) for r in csv.DictReader(fh)]
    urls = [u for u in dict.fromkeys(urls) if u and "citizensinformation.ie" in u]
    todo = []
    for u in urls:
        lm = lastmod.get(u) or "unknown"
        f = os.path.join(OUT, f"{page_key(u)}__{lm}.txt")
        if not os.path.exists(f): todo.append((u, lm, f))
    have = len(urls) - len(todo)
    if a.limit: todo = todo[:a.limit]
    print(f"{len(urls)} cited pages; {have} already snapshotted at their current LastMod; fetching {len(todo)}")
    idx = os.path.join(OUT, "index.csv"); new = not os.path.exists(idx)
    done = [0, 0]

    def one(item):
        u, lm, f = item
        try:
            st, page = fetch(u); txt = main_text(page)
            with open(f, "w", encoding="utf-8") as fh: fh.write(txt)
            done[0] += 1; return (u, lm, os.path.basename(f), date.today().isoformat(), st, len(txt))
        except Exception as e:   # a 404 or a timeout: recorded, not fatal
            done[1] += 1; return (u, lm, "", date.today().isoformat(), str(e)[:60], 0)
        finally:
            time.sleep(a.sleep)

    with open(idx, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["url", "lastmod", "file", "fetched", "status", "chars"])
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, row in enumerate(ex.map(one, todo), 1):
                w.writerow(row)
                if i % 100 == 0: print(f"  {i}/{len(todo)} ({done[1]} failed)", flush=True)
    # one row per url and lastmod in the index: a retry replaces its earlier failure
    with open(idx, encoding="utf-8", newline="") as fh: rows = list(csv.DictReader(fh))
    last = {(r["url"], r["lastmod"]): r for r in rows}
    with open(idx, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["url", "lastmod", "file", "fetched", "status", "chars"]); w.writeheader(); w.writerows(last.values())
    print(f"fetched {done[0]}, failed {done[1]}; {sum(1 for r in last.values() if r['file'])} snapshots in {OUT}")


if __name__ == "__main__":
    main()
