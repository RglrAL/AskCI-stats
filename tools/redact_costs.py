#!/usr/bin/env python3
"""Redact an Azure Cost Management export before it is committed: the subscription ID and the resource names.

The repo and its GitHub Pages site are public, and the dashboard fetches costs.csv from the site, so the committed
file is the published file. Two things in the export identify the production estate and have no analytical value:
the subscription ID in every ResourceId, and the globally unique resource names (a storage account, a search service,
an OpenAI account, Key Vault, Cosmos, container apps, private endpoints). This rewrites the subscription segment to
/subscriptions/redacted/ and the resource name (the last segment of ResourceId) to a role label the dashboard groups
by: service-openai, service-search, service-backend, admin-backend, shared-storage, shared-endpoint-1 … Each distinct
original name maps to one label (numbered where a role has several resources, in sorted order of the original names),
so de-duplication, scopes and totals are unchanged. Resource group, provider type, region, service and meter stay.
A name no rule knows becomes unassigned-N and is counted, never printed.

Usage:
    python3 tools/redact_costs.py costs.csv            # rewrite in place
    python3 tools/redact_costs.py export.csv -o costs.csv
    python3 tools/redact_costs.py costs.csv --check    # exit 1 if a subscription ID or an unredacted name remains

The pre-commit hook in tools/hooks runs --check on a staged costs.csv, and the publish workflow runs the rewrite.
Enable the hook once per clone: git config core.hooksPath tools/hooks
"""
import argparse, csv, io, re, sys, collections as C

SUB_RE = re.compile(r'/subscriptions/(?!redacted/)[^/,"]+/', re.I)
PLACEHOLDER = '/subscriptions/redacted/'
# original resource name pattern -> role label (brief §76 audit finding 1); order matters, first match wins
ROLES = [
    (r'^oai-askci-prod', 'service-openai'), (r'^srch-askci-prod', 'service-search'), (r'^spch-askci-prod', 'service-speech'),
    (r'^askci-backend-prod$', 'service-backend'), (r'^askci-background-prod$', 'service-background'), (r'^askci-frontend-prod$', 'service-frontend'),
    (r'^askci-admin-backend-prod$', 'admin-backend'), (r'^askci-admin-frontend-prod$', 'admin-frontend'),
    (r'^kvaskciprod', 'shared-keyvault'), (r'^acraskciprod', 'shared-registry'), (r'^staskciprod', 'shared-storage'),
    (r'^cosmos-askci-prod', 'shared-cosmos'), (r'^ag-askci-prod', 'shared-actiongroup'), (r'^alert-', 'shared-alert'),
    (r'-pe$|^pe-', 'shared-endpoint'),
]
LABEL_RE = re.compile(r'^(?:service|admin|shared|unassigned)-[a-z]+(?:-\d+)?$')


def role_of(name):
    for pat, label in ROLES:
        if re.search(pat, name, re.I): return label
    return 'unassigned'


def redact_rows(rows, rid_col):
    """Rewrite ResourceId in place: subscription segment, then the last segment to its role label."""
    names = sorted({(r[rid_col] or '').rstrip('/').rsplit('/', 1)[-1] for r in rows if r.get(rid_col)})
    by_role = C.defaultdict(list)
    for n in names:
        if n and not LABEL_RE.match(n): by_role[role_of(n)].append(n)
    label = {}
    for role, ns in by_role.items():
        for i, n in enumerate(sorted(ns), 1): label[n] = role if len(ns) == 1 and role != 'unassigned' else f'{role}-{i}'
    unassigned = sum(1 for n in label if label[n].startswith('unassigned'))
    for r in rows:
        rid = r.get(rid_col) or ''
        if not rid: continue
        rid = SUB_RE.sub(PLACEHOLDER, rid)
        head, _, name = rid.rstrip('/').rpartition('/')
        if name in label: rid = head + '/' + label[name]
        r[rid_col] = rid
    return len(label), unassigned


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('-o', '--out', help='write here instead of rewriting FILE in place')
    ap.add_argument('--check', action='store_true', help='report only; exit 1 if any subscription ID or unredacted resource name remains')
    a = ap.parse_args()

    with open(a.file, 'rb') as f: raw = f.read()
    text = raw.decode('utf-8-sig') if raw[:3] == b'\xef\xbb\xbf' else raw.decode('latin-1')
    rdr = csv.DictReader(io.StringIO(text, newline='')); rows = list(rdr); cols = rdr.fieldnames or []
    rid_col = next((c for c in cols if c.strip().lower() == 'resourceid'), None)
    if not rid_col: sys.exit(f'{a.file}: no ResourceId column')

    subs = sum(1 for r in rows if SUB_RE.search(r.get(rid_col) or ''))
    bad_names = sum(1 for r in rows if (r.get(rid_col) or '') and not LABEL_RE.match((r[rid_col] or '').rstrip('/').rsplit('/', 1)[-1]))
    if a.check:
        if subs or bad_names:
            print(f'{a.file}: {subs} row(s) still carry a subscription ID and {bad_names} row(s) an unredacted resource name. Run: python3 tools/redact_costs.py {a.file}', file=sys.stderr)
            return 1
        return 0

    n, un = redact_rows(rows, rid_col)
    out = a.out or a.file
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\n'); w.writeheader(); w.writerows(rows)
    with open(out, 'w', encoding='utf-8', newline='') as f: f.write(buf.getvalue())
    print(f'{out}: {len(rows)} rows; {subs} subscription segment(s) redacted; {n} resource name(s) mapped to role labels' + (f', {un} of them unassigned (add a rule)' if un else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
