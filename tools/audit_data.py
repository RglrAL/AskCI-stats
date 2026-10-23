#!/usr/bin/env python3
"""Audit the dashboard's data files: tallies, cross-file consistency and sanity checks.

Recounts the daily figures from the redacted QA feed with its own code (deliberately not
make_usage.py's), then checks every aggregate against that recount and against each other,
and checks costs.csv, the GA4 exports, the click-through exports and events.json.
Run it after copying a feed refresh into the dashboard and before committing.

Usage:
    python3 tools/audit_data.py                                   # newest exports/askci-export-*/ folder
    python3 tools/audit_data.py exports/askci-export-2026-10-23   # a given review folder

Exit status 1 when any check fails. WARN lines are things to look at, not failures.
"""
import csv, glob, os, sys, json, re, collections as C
from datetime import datetime, date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dirs = sys.argv[1:] or sorted(glob.glob(REPO + '/exports/askci-export-*/'), key=os.path.getmtime)[-1:]
if not _dirs: sys.exit('no redacted feed folder: pass one, e.g. exports/askci-export-2026-10-23')
FEED = sorted(glob.glob(os.path.join(_dirs[0], 'qa-feed-redacted_*.csv')))
if not FEED: sys.exit(f'no qa-feed-redacted_*.csv in {_dirs[0]}')
csv.field_size_limit(2**31 - 1)
FAIL = []; WARN = []; OK = []
def check(name, cond, detail=''):
    (OK if cond else FAIL).append(f'{name}' + (f' — {detail}' if detail and not cond else ''))
def warn(name, detail): WARN.append(f'{name} — {detail}')
def rd(p): return list(csv.DictReader(open(f'{REPO}/{p}', encoding='utf-8-sig')))
I = lambda x: int(x or 0)

# ── 1. Independent recount from the redacted feed ─────────────────────────────
seen = set(); T = []
LAST = max(r['Date'] for r in csv.DictReader(open(REPO + '/usage.csv')))   # the feed's partial export day is not in usage.csv
for f in FEED:
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        k = (r['Conversation ID'], r['Turn #'].strip())
        if k in seen: continue
        seen.add(k)
        t = datetime.strptime(r['Timestamp'].strip(), '%b %d, %Y %H:%M')
        if t.date().isoformat() > LAST: continue
        T.append((r, t))
day = C.defaultdict(C.Counter); conv1 = C.defaultdict(set); hrs = C.defaultdict(C.Counter)
convs = C.defaultdict(list); starter_vals = C.Counter()
for r, t in T:
    d = t.date().isoformat(); c = day[d]; first = r['Turn #'].strip() == '1'
    urls = re.findall(r'https?://[^\s,;|"]+', r['Citations'] or '')
    c['Questions'] += 1; c['Citations'] += len(urls)
    if first: conv1[d].add(r['Conversation ID'])
    o = r['Outcome'].strip(); c['o:' + o] += 1
    src = r['Source'].strip(); c['src:' + src] += 1
    c['qt:' + r['Question Type'].strip()] += 1
    c['fb:' + r['Feedback'].strip().lower()] += 1
    if first: starter_vals['chip' if r['Starter Prompt'].strip() else 'blank'] += 1
    hrs[(d, t.hour)]['turns'] += 1
    convs[r['Conversation ID']].append((int(r['Turn #']), t))
print(f'feed recount: {len(T)} turns, {len(convs)} conversations, {len(day)} days {min(day)}..{max(day)}')

# ── 2. usage.csv against the recount and its own identities ──────────────────
U = {r['Date']: r for r in rd('usage.csv')}
days = sorted(U)
d0, d1 = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
check('usage: one row per day, no gaps', len(days) == (d1 - d0).days + 1 and len(set(days)) == len(days), f'{len(days)} rows for {(d1-d0).days+1} days')
check('usage: same days as feed', set(days) == set(day), f'{set(days) ^ set(day)}')
OC = {'Cited': 'Cited answer', 'NotFound': 'Not found', 'Clarification': 'Clarification', 'Error': 'Error', 'OutOfScope': 'Out of scope', 'Greeting': 'Greeting', 'Uncited': 'Uncited answer'}
mism = C.Counter()
for d in days:
    u, c = U[d], day[d]
    for col, v in [('Questions', c['Questions']), ('Sessions', len(conv1[d])), ('Citations', c['Citations']),
                   ('ModalTurns', c['src:Modal']), ('WebTurns', c['src:Web']),
                   ('NewTopic', c['qt:new_topic']), ('UserFollowup', c['qt:user_followup']), ('SuggestedFollowup', c['qt:suggested_followup']),
                   ('Likes', c['fb:like']), ('Dislikes', c['fb:dislike'])] + [(k, c['o:' + v]) for k, v in OC.items()]:
        if I(u[col]) != v: mism[col] += 1
    q = I(u['Questions'])
    ident = {
        'outcomes sum to Questions': sum(I(u[k]) for k in OC) == q,
        'Scored = Q - Greeting - Error - OutOfScope': I(u['Scored']) == q - I(u['Greeting']) - I(u['Error']) - I(u['OutOfScope']),
        'Modal+Web+Other = Q': I(u['ModalTurns']) + I(u['WebTurns']) + I(u['OtherTurns']) == q,
        'Answered+Unanswered+Flagged = Q': I(u['Answered']) + I(u['Unanswered']) + I(u['Flagged']) == q,
        'question types <= Q': I(u['NewTopic']) + I(u['UserFollowup']) + I(u['SuggestedFollowup']) <= q,
        'scripts sum to Q': sum(I(u['Script' + s]) for s in ['Latin', 'Cyrillic', 'Arabic', 'CJK', 'Devanagari', 'Other', 'None']) == q,
        'ModalSessions+WebSessions <= Sessions': I(u['ModalSessions']) + I(u['WebSessions']) <= I(u['Sessions']),
        'Sessions <= Questions': I(u['Sessions']) <= q,
        'Starter+Organic first turns = Sessions': I(u['StarterPromptFirstTurns']) + I(u['OrganicFirstTurns']) == I(u['Sessions']),
        'Modal+Web cited <= Cited': I(u['ModalCited']) + I(u['WebCited']) <= I(u['Cited']),
        'Modal+Web scored <= Scored': I(u['ModalScored']) + I(u['WebScored']) <= I(u['Scored']),
        'Partial <= Cited': I(u['Partial']) <= I(u['Cited']),
        'DislikesOnCited <= Dislikes': I(u['DislikesOnCited']) <= I(u['Dislikes']),
        'latency p50 <= p90 <= p99': I(u['LatencyP50ms']) <= I(u['LatencyP90ms']) <= I(u['LatencyP99ms']),
        'latency bands <= Q': sum(I(u[k]) for k in ['LatUnder10s', 'Lat10to20s', 'Lat20to30s', 'LatOver30s']) <= q,
    }
    for k, ok in ident.items():
        if not ok: mism['identity: ' + k] += 1
for col in ['Questions', 'Sessions', 'Citations', 'ModalTurns', 'WebTurns', 'NewTopic', 'UserFollowup', 'SuggestedFollowup', 'Likes', 'Dislikes'] + list(OC):
    check(f'usage.{col} matches feed recount on every day', mism[col] == 0, f'{mism[col]} days differ')
for k in [k for k in mism if k.startswith('identity')] + [f'identity: {k}' for k in ident if f'identity: {k}' not in mism]:
    check(f'usage {k[10:]}', mism[k] == 0, f'fails on {mism[k]} days')
print('first-turn Starter Prompt values in feed:', dict(starter_vals), '| usage StarterPromptFirstTurns total:', sum(I(U[d]['StarterPromptFirstTurns']) for d in days))

# ── 3. usage-hours.csv ───────────────────────────────────────────────────────
H = rd('usage-hours.csv'); hd = C.Counter(); hs = C.Counter(); bad_h = 0
for r in H:
    hd[r['Date']] += I(r['Turns']); hs[r['Date']] += I(r['Sessions'])
    if not 0 <= I(r['Hour']) <= 23 or I(r['Timed']) > I(r['Turns']) or I(r['NotFound']) + I(r['Errors']) > I(r['Turns']): bad_h += 1
    if I(r['Turns']) != hrs[(r['Date'], I(r['Hour']))]['turns']: bad_h += 1
check('hours: turns per day = usage.Questions', all(hd[d] == I(U[d]['Questions']) for d in days), str([d for d in days if hd[d] != I(U[d]['Questions'])][:5]))
check('hours: sessions per day = usage.Sessions', all(hs[d] == I(U[d]['Sessions']) for d in days))
check('hours: rows valid and match feed per hour', bad_h == 0, f'{bad_h} bad rows')
hn = C.Counter(); he = C.Counter()
for r in H: hn[r['Date']] += I(r['NotFound']); he[r['Date']] += I(r['Errors'])
check('hours: NotFound/Errors per day = usage', all(hn[d] == I(U[d]['NotFound']) and he[d] == I(U[d]['Error']) for d in days))
timed = C.Counter()
for r in H: timed[r['Date']] += I(r['Timed'])
check('hours: Timed per day = latency bands total', all(timed[d] == sum(I(U[d][k]) for k in ['LatUnder10s', 'Lat10to20s', 'Lat20to30s', 'LatOver30s']) for d in days))

# ── 4. conversations-daily.csv ───────────────────────────────────────────────
CV = {r['Date']: r for r in rd('conversations-daily.csv')}
check('conversations: one row per day', set(CV) == set(days), f'{set(CV) ^ set(days)}')
starts = C.Counter(min(x)[1].date().isoformat() for x in convs.values())
check('conversations: Started = recount (by first-turn day)', all(I(CV[d]['Started']) == starts[d] for d in CV), str([(d, CV[d]['Started'], starts[d]) for d in CV if I(CV[d]['Started']) != starts[d]][:5]))
dd = [(d, CV[d]['Started'], U[d]['Sessions']) for d in CV if I(CV[d]['Started']) != I(U[d]['Sessions'])]
if dd: warn('conversations.Started vs usage.Sessions', f'{len(dd)} days differ, e.g. {dd[:3]} (Started counts every conversation by its first row; Sessions needs a Turn # 1 row)')
bad_c = 0
for d, r in CV.items():
    lens = sum(I(r[f'Turns{i}']) for i in range(1, 10)) + I(r['Turns10plus'])
    spans = sum(I(r[k]) for k in ['Span0to1', 'Span2to5', 'Span6to15', 'Span16to60', 'SpanOver60'])
    first = sum(I(r['First' + k]) for k in OC)
    if lens != I(r['Mature']) or I(r['Mature']) > I(r['Started']) or spans > I(r['Mature']) - I(r['Turns1']) or first > I(r['Mature']): bad_c += 1
check('conversations: length histogram = Mature, spans and first outcomes within Mature', bad_c == 0, f'{bad_c} days')
immature = [d for d in CV if I(CV[d]['Mature']) < I(CV[d]['Started'])]
check('conversations: only the last day(s) immature', all(d >= days[-2] for d in immature), str(immature[:5]))

# ── 5. category files ────────────────────────────────────────────────────────
CD = rd('categories-daily.csv'); CM = rd('categories.csv'); CO = rd('category-outcomes-daily.csv')
mon = C.Counter()
for r in CD: mon[(int(r['Date'][5:7]), )] += I(r['Citations'])
mon2 = C.Counter()
MN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
for r in CM: mon2[(MN.index(r['Month']) + 1, )] += I(r['Citations'])
check('categories.csv monthly totals = categories-daily', mon == mon2, f'{mon} vs {mon2}')
cdd = C.Counter()
for r in CD: cdd[r['Date']] += 1
check('categories-daily: no category hits on days without cited turns', all(I(U[d]['Cited']) > 0 for d in cdd))
cot = C.Counter(); coo = C.defaultdict(C.Counter); bad_co = 0
for r in CO:
    cot[r['Date']] += I(r['Turns'])
    for k in OC: coo[r['Date']][k] += I(r[k])
    if sum(I(r[k]) for k in OC) != I(r['Turns']): bad_co += 1
check('category-outcomes: turns per day = usage.Questions', all(cot[d] == I(U[d]['Questions']) for d in days), str([d for d in days if cot[d] != I(U[d]['Questions'])][:5]))
check('category-outcomes: outcomes per day = usage outcomes', all(coo[d][k] == I(U[d][k]) for d in days for k in OC))
check('category-outcomes: outcomes sum to Turns on every row', bad_co == 0, f'{bad_co} rows')
unk = sum(I(r['Turns']) for r in CO if r['Category'] == 'unknown'); tot = sum(cot.values())
warn('category-outcomes: unknown category share', f'{unk/tot:.1%} of turns have no attributable category (expected: failed turns carry no category)')

# ── 6. citations, starter prompts, latency buckets, journeys ─────────────────
CI = rd('citations-monthly.csv'); cm = C.Counter()
for r in CI: cm[r['Month']] += I(r['Citations'])
um = C.Counter()
for d in days: um[d[:7]] += I(U[d]['Citations'])
diff = {m: (cm[m], um[m]) for m in um if cm[m] != um[m]}
check('citations-monthly totals = usage.Citations by month', not diff, str(diff))
if diff: pass
SP = rd('starter-prompts-monthly.csv'); spm = C.Counter()
for r in SP:
    spm[r['Month']] += I(r['Count'])
    if I(r['Cited']) > I(r['Count']) or I(r['FollowedByTyped']) + I(r['FollowedBySuggested']) > I(r['Count']): check('starter prompts: row bounds', False, str(r))
og = C.Counter()
for r in CO: og[r['Date'][:7]] += I(r['OrganicFirstTurns'])
sm = C.Counter()
for d in days: sm[d[:7]] += I(U[d]['Sessions'])
usm = C.Counter()
for d in days: usm[d[:7]] += I(U[d]['StarterPromptFirstTurns'])
check('usage.StarterPromptFirstTurns by month = starter-prompts-monthly', usm == spm, str({m: (usm[m], spm[m]) for m in set(usm) | set(spm) if usm[m] != spm[m]}))
check('usage.StarterPromptFirstTurns total = feed first turns with a chip', sum(usm.values()) == starter_vals['chip'], f"{sum(usm.values())} vs {starter_vals['chip']}")
check('starter + organic first turns = conversations by month (category-outcomes)', all(spm[m] + og[m] == sm[m] for m in sm), str({m: (spm[m], og[m], sm[m]) for m in sm if spm[m] + og[m] != sm[m]}))
LB = rd('latency-buckets-daily.csv'); lb = C.defaultdict(C.Counter)
for r in LB: lb[(r['Date'], r['Kind'])]['t'] += I(r['Turns']); lb[(r['Date'], r['Kind'])]['s'] += I(r['LatencySumMs'])
check('latency buckets: words and citations kinds agree on turns and ms each day', all(lb[(d, 'words')] == lb[(d, 'citations')] for d in days))
check('latency buckets: turns per day = hours.Timed', all(lb[(d, 'words')]['t'] == timed[d] for d in days))
JR = rd('journeys-monthly.csv')
check('journeys: no self-transitions, positive counts', all(r['From'] != r['To'] and I(r['Conversations']) > 0 for r in JR))

# ── 7. costs.csv ─────────────────────────────────────────────────────────────
CS = rd('costs.csv')
cdates = sorted({datetime.strptime(r['UsageDate'], '%d/%m/%Y').date() for r in CS})
check('costs: no subscription ID', not any('/subscriptions/redacted/' not in r['ResourceId'] for r in CS))
check('costs: one currency (GBP)', {r['Currency'] for r in CS} == {'GBP'}, str({r['Currency'] for r in CS}))
gaps = [cdates[i] for i in range(1, len(cdates)) if (cdates[i] - cdates[i-1]).days != 1]
check('costs: no missing days', not gaps, str(gaps[:5]))
full = C.Counter(tuple(r.values()) for r in CS)
check('costs: no fully identical rows', all(v == 1 for v in full.values()), f'{sum(v - 1 for v in full.values() if v > 1)} repeated')
tot_aug = sum(float(r['Cost']) for r in CS if datetime.strptime(r['UsageDate'], '%d/%m/%Y').date() <= date(2026, 8, 17))
tot = sum(float(r['Cost']) for r in CS)
print(f'costs: {len(CS)} rows, {cdates[0]}..{cdates[-1]}, total £{tot:,.2f}; 1 Jan-17 Aug £{tot_aug:,.2f} (brief\'s frozen file: £4,537.71, before later billing settled)')
neg = [r for r in CS if float(r['Cost']) < 0]
if neg: warn('costs: negative rows', f'{len(neg)} (credits/refunds; accepted by design)')

# ── 8. GA4 files ─────────────────────────────────────────────────────────────
for fn in ['session-and-users', 'searches-and-sessions']:
    G = rd(f'ga4/{fn}.csv'); gd = sorted(r['Date'] for r in G if r['Date'].isdigit())
    gdd = [datetime.strptime(x, '%Y%m%d').date() for x in gd]
    check(f'ga4/{fn}: no missing or repeated days', len(set(gd)) == len(gd) and (gdd[-1] - gdd[0]).days + 1 == len(gd), f'{len(gd)} rows {gd[0]}..{gd[-1]}')
G = {r['Date']: r for r in rd('ga4/session-and-users.csv') if r['Date'].isdigit()}
check('ga4: users <= sessions every day', all(I(r['Total users']) <= I(r['Sessions']) for r in G.values()))
last = max(G); med = sorted(I(r['Sessions']) for r in G.values())[len(G) // 2]
if I(G[last]['Sessions']) < 0.25 * med: warn('ga4: last day partial', f'{last} has {G[last]["Sessions"]} sessions vs median {med}: exclude it from comparisons')

# ── 9. click-throughs ────────────────────────────────────────────────────────
rows = []
for f in sorted(glob.glob(REPO + '/ga4/Ask-ci-click-throughs *.csv')):
    R = [r for r in csv.reader(open(f, encoding='utf-8-sig')) if r and not r[0].startswith('#')]
    hdr0, hdr1 = R[0], R[1]
    tot_i = [i for i, x in enumerate(hdr0) if x == 'Totals']
    dev = {}
    for i, x in enumerate(hdr0):
        if x not in ('', 'Device category', 'Totals'): dev.setdefault(x, []).append(i)
    gt = next(r for r in R if r[-1:] == ['Grand total'])
    data = [r for r in R if r[0].isdigit()]
    bad = [r[0] for r in data if sum(I(r[ix[0]]) for ix in dev.values()) != I(r[tot_i[0]])]
    check(f'{f.split("/")[-1]}: device views sum to totals on every row', not bad, f'{len(bad)} rows')
    check(f'{f.split("/")[-1]}: rows sum to grand total', sum(I(r[tot_i[0]]) for r in data) == I(gt[tot_i[0]]))
    rng = re.search(r'(\d{8})-(\d{8})', open(f).read(400)).groups()
    check(f'{f.split("/")[-1]}: rows within stated range {rng}', all(rng[0] <= r[0] <= rng[1] for r in data))
    rows += [(r[0], r[1], I(r[tot_i[0]])) for r in data]
    print(f'  {f.split("/")[-1]}: range {rng}, {len(data)} rows')
check('click-throughs: no page/day in two files', len(rows) == len({(a, b) for a, b, _ in rows}))
ranges = sorted(re.search(r'(\d{8})-(\d{8})', open(f).read(400)).groups() for f in glob.glob(REPO + '/ga4/Ask-ci-click-throughs *.csv'))
cont = all((datetime.strptime(ranges[i+1][0], '%Y%m%d') - datetime.strptime(ranges[i][1], '%Y%m%d')).days == 1 for i in range(len(ranges) - 1))
check('click-throughs: files cover a continuous range', cont, str(ranges))
nonutm = [u for _, u, _ in rows if 'utm_medium=chatbot' not in u or 'utm_campaign=citation' not in u]
check('click-throughs: every URL carries the AskCI citation UTMs', not nonutm, str(nonutm[:3]))
nonci = [u for _, u, _ in rows if not u.startswith('https://www.citizensinformation.ie/')]
check('click-throughs: every URL is on www.citizensinformation.ie', not nonci, str(nonci[:3]))
ctr = C.Counter()
for d, u, v in rows:
    if d <= days[-1]: ctr[d] += v
hi = [(d, ctr[d], U[d]['Cited']) for d in days if I(U[d]['Cited']) >= 50 and ctr[d] / I(U[d]['Cited']) > 0.15]
check('click-throughs never exceed 15% of cited answers on a day (sanity)', not hi, str(hi[:5]))

# ── 10. events.json ──────────────────────────────────────────────────────────
E = json.load(open(REPO + '/events.json'))['events']
check('events.json: valid statuses and kinds', all(e['status'] in ('confirmed', 'candidate', 'rejected') and e['kind'] in ('model', 'launch', 'chips', 'observed change', 'other') for e in E))
launch = [e for e in E if e['kind'] == 'launch' and e['status'] == 'confirmed']
print('confirmed launch events:', [(e['start'], e['title']) for e in launch])

# ── 11. Sanity: outliers ─────────────────────────────────────────────────────
for d in days:
    u = U[d]; q = I(u['Questions'])
    prev = [I(U[x]['Questions']) for x in days if (date.fromisoformat(d) - date.fromisoformat(x)).days in (7, 14, 21, 28)]   # same weekday
    if prev and q > 0:
        med = sorted(prev)[len(prev) // 2]
        if med and (q > 2.5 * med or q < 0.25 * med): warn('volume outlier', f'{d} {date.fromisoformat(d):%a}: {q} questions vs {med} median of the previous four {date.fromisoformat(d):%a}s')
    if q >= 50 and I(u['Error']) / q > 0.05: warn('error spike', f'{d}: {u["Error"]} errors of {q} turns ({I(u["Error"])/q:.0%})')
    if I(u['Scored']) >= 50 and I(u['Cited']) / I(u['Scored']) < 0.75: warn('low cited rate', f'{d}: {I(u["Cited"])/I(u["Scored"]):.0%} of scored turns cited')

print('\n=== FAIL ({}) ==='.format(len(FAIL))); [print('  ✗', x) for x in FAIL]
print('=== WARN ({}) ==='.format(len(WARN))); [print('  !', x) for x in WARN]
print('=== PASS ({}) ==='.format(len(OK))); [print('  ✓', x) for x in OK]
sys.exit(1 if FAIL else 0)
