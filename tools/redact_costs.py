#!/usr/bin/env python3
"""Redact the Azure subscription ID from an Azure Cost Management export before it is committed.

The repo and its GitHub Pages site are public, and the dashboard fetches costs.csv from the site,
so the committed file is the published file. Every ResourceId starts /subscriptions/<id>/...;
this rewrites that segment to /subscriptions/redacted/ and changes nothing else. The dashboard
reads only the resource group and the resource name from ResourceId, and every row gets the same
replacement, so totals, scopes and de-duplication are unaffected.

Usage:
    python3 tools/redact_costs.py costs.csv            # rewrite in place
    python3 tools/redact_costs.py export.csv -o costs.csv
    python3 tools/redact_costs.py costs.csv --check    # exit 1 if any subscription ID remains

The pre-commit hook in tools/hooks runs --check on a staged costs.csv. Enable it once per clone:
    git config core.hooksPath tools/hooks
"""
import argparse, re, sys

SUB_RE = re.compile(r'/subscriptions/(?!redacted/)[^/,"]+/', re.I)
PLACEHOLDER = '/subscriptions/redacted/'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('-o', '--out', help='write here instead of rewriting FILE in place')
    ap.add_argument('--check', action='store_true', help='report only; exit 1 if any subscription ID remains')
    a = ap.parse_args()

    # Bytes in, bytes out: keeps the export's encoding and line endings exactly as they were.
    with open(a.file, 'rb') as f:
        text = f.read().decode('latin-1')
    found = len(SUB_RE.findall(text))

    if a.check:
        if found:
            print(f'{a.file}: {found} row(s) still carry an Azure subscription ID. '
                  f'Run: python3 tools/redact_costs.py {a.file}', file=sys.stderr)
            return 1
        return 0

    out = a.out or a.file
    with open(out, 'wb') as f:
        f.write(SUB_RE.sub(PLACEHOLDER, text).encode('latin-1'))
    print(f'{out}: redacted {found} subscription ID occurrence(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
