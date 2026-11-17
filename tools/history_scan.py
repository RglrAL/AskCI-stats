#!/usr/bin/env python3
"""Scan every file version in the git history for material that must not be public (brief §108, handoff 9a).

Reports by path and count only, never the matched text:
  subscription   an Azure subscription segment with a real ID (/subscriptions/<guid>/)
  resource-name  a cost export whose ResourceId still carries a real resource name (tools/redact_costs.py --check)
  email          an email address (GitHub's noreply addresses are allowed)
  ip             an IPv4 address (loopback and 0.0.0.0 allowed)
  local-path     a local file path (/Users/…, C:\\Users\\…, file:)
  html-path      a website analytics path holding markup (data/ga4/, ga4/)
  feed-header    a CSV whose header carries a feed text column

Usage:
    python3 tools/history_scan.py               # every version of every file, reachable from any ref
    python3 tools/history_scan.py --head        # the current tree only; exit 1 on any finding (the deploy runs this)
    python3 tools/history_scan.py --blobs OUT   # also write "blob-id <tab> kind,kind <tab> path" for the rewrite plan
    python3 tools/history_scan.py --repo DIR    # scan another clone (the mirror the rewrite runs in)
"""
import argparse, csv, io, os, re, subprocess, sys, collections as C

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import redact_costs as RC  # noqa: E402

SUB = re.compile(rb'/subscriptions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
EMAIL = re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
EMAIL_OK = re.compile(rb'@users\.noreply\.github\.com$|@anthropic\.com$|@example\.(?:com|org)$', re.I)
IP = re.compile(rb'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
IP_OK = {b'127.0.0.1', b'0.0.0.0'}
LOCAL = re.compile(rb'/Users/[A-Za-z]|[Cc]:\\\\?Users|file:/')
MARKUP = re.compile(rb'[<>]')
FEED_COLS = [('User' + ' Query').encode(), ('Assistant' + ' Response').encode()]
# Files that name the patterns or the feed columns to look for them, not data: skipped for local-path and feed-header
SELF = {'tools/history_scan.py', 'tools/hooks/guard_feed_text.py', 'tools/hooks/test_guard.py'}


TARGET = [REPO]   # the repository scanned: this one, or --repo (a mirror clone for the rewrite, brief §108)


def git(*a, inp=None):
    return subprocess.run(['git', '-C', TARGET[0], *a], input=inp, capture_output=True, check=True).stdout


def ga4_path(p):
    return p.startswith(('data/ga4/', 'ga4/')) and p.endswith('.csv')


def scan(path, data):
    """{kind: count} for one file version."""
    if b'\0' in data[:8000]: return {}
    k = C.Counter()
    k['subscription'] = len(SUB.findall(data))
    k['email'] = sum(1 for m in EMAIL.findall(data) if not EMAIL_OK.search(m))
    k['ip'] = sum(1 for m in IP.findall(data) if m not in IP_OK and all(int(x) < 256 for x in m.split(b'.')))
    if path not in SELF:
        k['local-path'] = len(LOCAL.findall(data))
    if ga4_path(path):
        k['html-path'] = sum(1 for line in data.splitlines() if MARKUP.search(line))
    if path.endswith('.csv'):
        head = data.split(b'\n', 1)[0]
        if path not in SELF and any(c in head for c in FEED_COLS): k['feed-header'] = 1
        if b'ResourceId' in head:
            text = data.decode('utf-8-sig', errors='replace')
            rows = list(csv.DictReader(io.StringIO(text, newline='')))
            k['resource-name'] = sum(1 for r in rows if (r.get('ResourceId') or '') and
                                     not RC.LABEL_RE.match((r['ResourceId'] or '').rstrip('/').rsplit('/', 1)[-1]))
    return {a: n for a, n in k.items() if n}


def blobs(head_only):
    """(blob-id, path) for every file version: the current tree, or every object reachable from any ref."""
    if head_only:
        for line in git('ls-tree', '-r', 'HEAD').decode().splitlines():
            meta, path = line.split('\t', 1)
            if meta.split()[1] == 'blob': yield meta.split()[2], path
        return
    seen = set()
    for line in git('rev-list', '--all', '--objects').decode().splitlines():
        sha, _, path = line.partition(' ')
        if path and sha not in seen: seen.add(sha); yield sha, path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--head', action='store_true', help='the current tree only; exit 1 on any finding')
    ap.add_argument('--blobs', help='write the flagged blob IDs, kinds and paths here (no matched text)')
    ap.add_argument('--repo', help='scan this repository instead (a mirror clone works)')
    a = ap.parse_args()
    if a.repo: TARGET[0] = a.repo

    pairs = [(s, p) for s, p in blobs(a.head)]
    by_path = C.defaultdict(lambda: {'versions': 0, 'flagged': 0, 'kinds': C.Counter()})
    flagged = []
    for sha, path in pairs:
        if not path.endswith(('.csv', '.json', '.md', '.html', '.py', '.yml', '.txt', '.js', '.sh')) and '.' in os.path.basename(path):
            continue
        try: data = git('cat-file', 'blob', sha)
        except subprocess.CalledProcessError: continue
        e = by_path[path]; e['versions'] += 1
        found = scan(path, data)
        if found:
            e['flagged'] += 1; e['kinds'].update(found); flagged.append((sha, ','.join(sorted(found)), path))
    hits = {p: e for p, e in by_path.items() if e['flagged']}
    where = 'current tree' if a.head else 'history (all refs)'
    print(f'{where}: {len(pairs)} file versions, {len(by_path)} paths scanned; {len(flagged)} versions in {len(hits)} paths flagged')
    for p, e in sorted(hits.items()):
        print(f"  {p}: {e['flagged']} of {e['versions']} versions · " + ', '.join(f'{k} {n}' for k, n in sorted(e['kinds'].items())))
    if a.blobs:
        with open(a.blobs, 'w', encoding='utf-8') as f:
            for row in flagged: f.write('\t'.join(row) + '\n')
        print(f'{len(flagged)} blob IDs written to {a.blobs}')
    return 1 if (a.head and flagged) else 0


if __name__ == '__main__':
    sys.exit(main())
