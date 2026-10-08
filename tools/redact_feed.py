#!/usr/bin/env python3
"""Redact an AskCI QA feed export so it can be kept and shared without citizens' text.

Drops the free-text columns (User Query, Assistant Response, Report Subject, Report
Description) and writes every other column unchanged. The output still contains per-turn
rows, so it stays out of git (.gitignore covers qa-feed*.csv); only the daily aggregates
produced by make_usage.py go into the dashboard.

Usage:
    python3 tools/redact_feed.py qa-feed_20261008.csv              # writes qa-feed-redacted_20261008.csv beside it
    python3 tools/redact_feed.py qa-feed_*.csv --out-dir ~/feeds   # several files, output elsewhere
"""
import argparse, csv, os, sys

DROP = ["User Query", "Assistant Response", "Report Subject", "Report Description"]
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def out_name(path, out_dir):
    base = os.path.basename(path)
    base = base.replace("qa-feed_", "qa-feed-redacted_", 1) if base.startswith("qa-feed_") else "redacted_" + base
    return os.path.join(out_dir or os.path.dirname(path) or ".", base)


def redact(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as fi, open(dst, "w", encoding="utf-8", newline="") as fo:
        r = csv.DictReader(fi)
        keep = [c for c in r.fieldnames if c not in DROP]
        dropped = [c for c in r.fieldnames if c in DROP]
        w = csv.DictWriter(fo, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        n = 0
        for row in r:
            w.writerow(row)
            n += 1
    return n, keep, dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out-dir", help="directory for the redacted files (default: beside each input)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output file")
    a = ap.parse_args()
    for f in a.files:
        dst = out_name(f, a.out_dir)
        if os.path.abspath(dst) == os.path.abspath(f):
            sys.exit(f"refusing to overwrite the input: {f}")
        if os.path.exists(dst) and not a.force:
            sys.exit(f"{dst} exists; pass --force to overwrite")
        n, keep, dropped = redact(f, dst)
        missing = [c for c in DROP if c not in dropped]
        print(f"{f}: {n} rows -> {dst}")
        print(f"  dropped: {', '.join(dropped) or 'nothing'}" + (f"  (not present: {', '.join(missing)})" if missing else ""))
        print(f"  kept:    {', '.join(keep)}")


if __name__ == "__main__":
    main()
