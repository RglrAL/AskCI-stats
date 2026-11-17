#!/usr/bin/env python3
"""Rewrite the flagged file versions in the git history (brief §108, handoff 9a). The analyst runs this, never a session.

Every version tools/history_scan.py flags is rewritten in place rather than removed, so the history keeps its shape and
the Ask bar test's frozen data commit still has its files:
  costs.csv, data/costs.csv              the same redaction as tools/redact_costs.py (subscription segment, resource names)
  ga4/, data/ga4/categories-and-views    the same clean as tools/clean_ga4.py (plain site addresses, the rest summed)
A flagged version of any other path stops the run: it needs a decision, not a guess.

  --dry-run   reads each flagged version from this repository (or --repo), applies the rewrite in memory and scans the
              result with the same rules; prints counts only. Safe to run anywhere.
  (no flag)   runs git-filter-repo in --repo, which must be a fresh mirror clone. Needs: pip install git-filter-repo

The full procedure, with the force-push and what to ask GitHub, is in the brief, §108.
"""
import argparse, csv, io, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import redact_costs as RC, clean_ga4 as CG, history_scan as HS  # noqa: E402


def redact_cost(data):
    text = data.decode('utf-8-sig') if data[:3] == b'\xef\xbb\xbf' else data.decode('latin-1')
    rdr = csv.DictReader(io.StringIO(text, newline='')); rows = list(rdr); cols = rdr.fieldnames or []
    rid = next(c for c in cols if c.strip().lower() == 'resourceid')
    RC.redact_rows(rows, rid)
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\n'); w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode('utf-8')


def clean_views(data):
    return CG.clean_views(data.decode('utf-8-sig'))[0].encode('utf-8')


def rewriter(path):
    if os.path.basename(path) == 'costs.csv': return redact_cost
    if path.endswith('ga4/categories-and-views.csv'): return clean_views
    return None


def load_flags(path):
    flags = {}
    for line in open(path, encoding='utf-8'):
        sha, kinds, p = line.rstrip('\n').split('\t', 2)
        flags[sha] = (kinds, p)
    return flags


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--blobs', required=True, help='the list from tools/history_scan.py --blobs')
    ap.add_argument('--repo', default=REPO, help='the repository (for the real run: a fresh mirror clone)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    flags = load_flags(a.blobs)
    unknown = sorted({p for _, p in flags.values() if rewriter(p) is None})
    if unknown:
        sys.exit(f'{len(unknown)} flagged path(s) have no rewrite rule: {", ".join(unknown)}. Decide what to do with them first.')
    HS.TARGET[0] = a.repo

    if a.dry_run:
        still = 0
        for sha, (kinds, p) in flags.items():
            new = rewriter(p)(HS.git('cat-file', 'blob', sha))
            left = HS.scan(p, new)
            if left: still += 1; print(f'  {p}: still flagged after the rewrite: ' + ', '.join(f'{k} {n}' for k, n in sorted(left.items())))
        print(f'dry run: {len(flags)} flagged versions; {len(flags) - still} clean after the rewrite, {still} not')
        return 1 if still else 0

    if os.path.abspath(a.repo) == REPO:
        sys.exit('refusing to rewrite the working repository: run it in a fresh mirror clone (see brief §108)')
    import git_filter_repo as fr
    todo = {sha.encode(): rewriter(p) for sha, (_, p) in flags.items()}
    done = [0]

    def blob_cb(blob, _meta):
        f = todo.get(blob.original_id)
        if f: blob.data = f(blob.data); done[0] += 1

    os.chdir(a.repo)
    fr.RepoFilter(fr.FilteringOptions.parse_args(['--force']), blob_callback=blob_cb).run()
    print(f'rewrote {done[0]} of {len(todo)} flagged versions; commit map at {os.path.join(a.repo, "filter-repo", "commit-map")}')
    return 0 if done[0] == len(todo) else 1


if __name__ == '__main__':
    sys.exit(main())
