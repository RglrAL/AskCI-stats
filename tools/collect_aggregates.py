#!/usr/bin/env python3
"""Copy the aggregate CSVs from a review folder into the repo root, never a feed (brief §75).

make_usage.py --out-dir writes its aggregates beside the redacted feeds in a review folder under exports/. This copies
every *.csv there except the feeds (qa-feed*) into the repo root, where the dashboard and the audit read them, and prints
what changed: new files, changed files, unchanged. Counts only; it never opens a feed.

Usage:
    python3 tools/collect_aggregates.py exports/askci-export-2026-10-24-topics
"""
import filecmp, os, shutil, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    src = sys.argv[1]
    new, changed, same = [], [], []
    for name in sorted(os.listdir(src)):
        if not name.endswith(".csv") or "qa-feed" in name or name.startswith("labell"): continue
        s, d = os.path.join(src, name), os.path.join(REPO, name)
        if not os.path.exists(d): new.append(name)
        elif filecmp.cmp(s, d, shallow=False): same.append(name); continue
        else: changed.append(name)
        shutil.copyfile(s, d)
    print(f"from {src}: {len(new)} new ({', '.join(new) or '-'}); {len(changed)} changed ({', '.join(changed) or '-'}); {len(same)} unchanged")


if __name__ == "__main__":
    main()
