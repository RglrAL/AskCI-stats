#!/usr/bin/env python3
"""Audit the dashboard's data files: tallies, cross-file consistency and sanity checks.

Recounts the daily figures from the redacted QA feed with its own code (deliberately not
make_usage.py's), then checks every aggregate against that recount and against each other,
and checks costs.csv, the GA4 exports, the click-through exports and events.json.
Run it after copying a feed refresh into the dashboard and before committing.

Usage:
    python3 tools/audit_data.py                                   # newest exports/askci-export-*/ folder
    python3 tools/audit_data.py exports/askci-export-2026-10-23   # a given review folder
    python3 tools/audit_data.py --files-only                      # no feed (the publish workflow): the schema,
                                                                  # cross-file and sanity checks, not the recount

Exit status 1 when any check fails. WARN lines are things to look at, not failures.
"""
import subprocess, csv, glob, os, sys, json, re, io, collections as C
from datetime import datetime, date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_ONLY = '--files-only' in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith('--')]
if FILES_ONLY:
    FEED = []   # the feed never leaves the analyst's machine; the published files are checked against each other
else:
    _dirs = _args or sorted(glob.glob(REPO + '/exports/askci-export-*/'), key=os.path.getmtime)[-1:]
    if not _dirs: sys.exit('no redacted feed folder: pass one, e.g. exports/askci-export-2026-10-23 (or --files-only)')
    FEED = sorted(glob.glob(os.path.join(_dirs[0], 'qa-feed-redacted_*.csv')))
    if not FEED: sys.exit(f'no qa-feed-redacted_*.csv in {_dirs[0]}')
csv.field_size_limit(2**31 - 1)
FAIL = []; WARN = []; OK = []
def check(name, cond, detail=''):
    (OK if cond else FAIL).append(f'{name}' + (f' — {detail}' if detail and not cond else ''))
def warn(name, detail): WARN.append(f'{name} — {detail}')
def rd(p): return list(csv.DictReader(open(f'{REPO}/{p}', encoding='utf-8-sig')))
I = lambda x: int(x or 0)

# ── 0. Schema: every file the dashboard reads has the columns it reads ────────
# A file uploaded in the wrong shape (a three-column usage.csv once replaced the full one) stops here, with
# the missing columns named, before any check can crash on it.
SCHEMA = {
    'usage.csv': 'Date Questions Sessions Answered Unanswered Flagged NewTopic UserFollowup SuggestedFollowup ModalTurns WebTurns OtherTurns ModalSessions WebSessions Citations LatencyP50ms LatencyP90ms LatencyP99ms Likes Dislikes DislikesOnCited StarterPromptFirstTurns OrganicFirstTurns ScriptLatin ScriptCyrillic ScriptArabic ScriptCJK ScriptDevanagari ScriptOther ScriptNone LatUnder10s Lat10to20s Lat20to30s LatOver30s Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial Scored OutcomeRules ModalCited ModalNotFound ModalScored WebCited WebNotFound WebScored AnswerWords AnswerWordsTurns CitedWords CitedWordsTurns',
    'script-outcomes-daily.csv': 'Date Script Turns Scored Cited NotFound Clarification',
    'usage-hours.csv': 'Date Hour Turns Sessions NotFound Errors Timed LatencySumMs',
    'conversations-daily.csv': 'Date Started Mature Turns1 Turns10plus MatureTurns Span0to1 Span2to5 Span6to15 Span16to60 SpanOver60 ChipUse ReachedCited NFTurns NFLaterCited',
    'category-outcomes-daily.csv': 'Date Category Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Scored OrganicFirstTurns',
    'categories-daily.csv': 'Date Category Citations',
    'categories.csv': 'Month Citations',
    'citations-monthly.csv': 'Month URL Citations Answers Partial Dislikes',
    'pages-cited.csv': 'URL FirstCited LastCited Citations Answers Partial Dislikes LastMod FirstCitedAfterLastMod AnswersAfterLastMod',
    'safety-daily.csv': 'Date Flag Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited',
    'question-intent-daily.csv': 'Date Intent Chip Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial Year Euro YesNo Situation WithTopic SituationCited SituationNotFound SituationPartial NamedCited NamedNotFound NamedClarification',
    'asked-pages-monthly.csv': 'Month URL Category Asked CitedSame CitedSameCategory CitedOther NotFound Clarification Other CitedUnderHub Hub',
    'question-topics-daily.csv': 'Date Category Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'intent-journeys-monthly.csv': 'Month From To Turns',
    'citations-intent-monthly.csv': 'Month URL Intent Answers Partial',
    'asked-pages-weekly.csv': 'Week URL Asked CitedIt NotFound Partial',
    'question-topics-monthly.csv': 'Month Category Topic Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'question-categories-monthly.csv': 'Month Category Source Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'question-intent-category-monthly.csv': 'Month Category Intent Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'content-gaps.csv': 'kind page category intent evidence asks rate priority team period rules_version lexicon_version built',
    'answer-templates-daily.csv': 'Date Template Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'answer-signposts-monthly.csv': 'Month Org Category Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'answer-figures-monthly.csv': 'Month URL Answers Partial Figures Matched Unmatched Unverifiable',
    'question-situation-monthly.csv': 'Month Category Flag Turns Cited NotFound Clarification Error OutOfScope Greeting Uncited Partial',
    'clarification-asks-monthly.csv': 'Month Asks Given Turns',
    'answer-personalisation-monthly.csv': 'Month SituationGiven Personalised Answers',
    'setback-intents-monthly.csv': 'Month Setback Intent Turns Ended SameIntentNext OtherIntentNext',
    'repeat-questions-monthly.csv': 'Month Turns FirstTurns StarterFirstTurns DistinctFirstTurnTexts TextsAskedTwicePlus FirstTurnsOnRepeatedTexts Top10 Top25 Top50 Top100 Top250 SuggestedClicks DistinctSuggestedTexts SuggestedTop25',
    'journeys-monthly.csv': 'From To Conversations',
    'starter-prompts-monthly.csv': 'Month Count Cited FollowedByTyped FollowedBySuggested Partial NotFound Clarification Disliked Words TimedTurns ResponseMsSum Mature EndedThere',
    'latency-buckets-daily.csv': 'Date Kind Turns LatencySumMs',
    'costs.csv': 'UsageDate Cost Currency ResourceId',
    'ga4/clicks-daily.csv': 'Date Source Views Sessions Mobile Desktop Tablet OtherDevice',
    'ga4/clicks-pages-daily.csv': 'Date URL Source Views',
    'outcome-rules-daily.csv': 'Date Rule Turns',
    'answer-style-daily.csv': 'Date Outcome Turns Words Lines Hedges Apologies Signposts Questions Links',
    'answer-next-daily.csv': 'Date Class Answers Ended Rephrased NextTyped NextChip NextNew Within1m NextCited Disliked',
}
for f, cols in SCHEMA.items():
    if not os.path.exists(f'{REPO}/{f}'): FAIL.append(f'schema: {f} is missing'); continue
    have = set(next(csv.reader(open(f'{REPO}/{f}', encoding='utf-8-sig')), []))
    miss = [c for c in cols.split() if c not in have]
    check(f'schema: {f} has the columns the dashboard reads', not miss, 'missing ' + ', '.join(miss[:8]) + (' …' if len(miss) > 8 else ''))
if FAIL:   # the checks below index these columns; stop with the schema failures rather than a traceback
    print('=== FAIL ({}) ==='.format(len(FAIL))); [print('  ✗', x) for x in FAIL]; sys.exit(1)

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
    convs[r['Conversation ID']].append((int(r['Turn #']), t, r['Outcome'].strip()))
if FEED: print(f'feed recount: {len(T)} turns, {len(convs)} conversations, {len(day)} days {min(day)}..{max(day)}')
else: print('--files-only: no feed recount; schema, cross-file and sanity checks only')

# ── 2. usage.csv against the recount and its own identities ──────────────────
U = {r['Date']: r for r in rd('usage.csv')}
days = sorted(U)
d0, d1 = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
check('usage: one row per day, no gaps', len(days) == (d1 - d0).days + 1 and len(set(days)) == len(days), f'{len(days)} rows for {(d1-d0).days+1} days')
if FEED: check('usage: same days as feed', set(days) == set(day), f'{set(days) ^ set(day)}')
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
        'answer-length counts within answers': I(u['AnswerWordsTurns']) <= q and I(u['CitedWordsTurns']) <= I(u['Cited']),
        'latency bands <= Q': sum(I(u[k]) for k in ['LatUnder10s', 'Lat10to20s', 'Lat20to30s', 'LatOver30s']) <= q,
    }
    for k, ok in ident.items():
        if not ok: mism['identity: ' + k] += 1
for col in (['Questions', 'Sessions', 'Citations', 'ModalTurns', 'WebTurns', 'NewTopic', 'UserFollowup', 'SuggestedFollowup', 'Likes', 'Dislikes'] + list(OC) if FEED else []):
    check(f'usage.{col} matches feed recount on every day', mism[col] == 0, f'{mism[col]} days differ')
for k in [k for k in mism if k.startswith('identity')] + [f'identity: {k}' for k in ident if f'identity: {k}' not in mism]:
    check(f'usage {k[10:]}', mism[k] == 0, f'fails on {mism[k]} days')
if FEED: print('first-turn Starter Prompt values in feed:', dict(starter_vals), '| usage StarterPromptFirstTurns total:', sum(I(U[d]['StarterPromptFirstTurns']) for d in days))

# ── 3. usage-hours.csv ───────────────────────────────────────────────────────
H = rd('usage-hours.csv'); hd = C.Counter(); hs = C.Counter(); bad_h = 0
for r in H:
    hd[r['Date']] += I(r['Turns']); hs[r['Date']] += I(r['Sessions'])
    if not 0 <= I(r['Hour']) <= 23 or I(r['Timed']) > I(r['Turns']) or I(r['NotFound']) + I(r['Errors']) > I(r['Turns']): bad_h += 1
    if FEED and I(r['Turns']) != hrs[(r['Date'], I(r['Hour']))]['turns']: bad_h += 1
check('hours: turns per day = usage.Questions', all(hd[d] == I(U[d]['Questions']) for d in days), str([d for d in days if hd[d] != I(U[d]['Questions'])][:5]))
check('hours: sessions per day = usage.Sessions', all(hs[d] == I(U[d]['Sessions']) for d in days))
check('hours: rows valid' + (' and match feed per hour' if FEED else ''), bad_h == 0, f'{bad_h} bad rows')
hn = C.Counter(); he = C.Counter()
for r in H: hn[r['Date']] += I(r['NotFound']); he[r['Date']] += I(r['Errors'])
check('hours: NotFound/Errors per day = usage', all(hn[d] == I(U[d]['NotFound']) and he[d] == I(U[d]['Error']) for d in days))
timed = C.Counter()
for r in H: timed[r['Date']] += I(r['Timed'])
check('hours: Timed per day = latency bands total', all(timed[d] == sum(I(U[d][k]) for k in ['LatUnder10s', 'Lat10to20s', 'Lat20to30s', 'LatOver30s']) for d in days))

# ── 3b. script-outcomes-daily.csv ─────────────────────────────────────────────
SO = rd('script-outcomes-daily.csv'); sot = C.Counter(); soc = C.Counter(); bad_so = 0
for r in SO:
    sot[r['Date']] += I(r['Turns']); soc[r['Date']] += I(r['Cited'])
    if I(r['Cited']) + I(r['NotFound']) + I(r['Clarification']) > I(r['Scored']) or I(r['Scored']) > I(r['Turns']): bad_so += 1
check('script outcomes: turns per day = usage.Questions', all(sot[d] == I(U[d]['Questions']) for d in days), str([d for d in days if sot[d] != I(U[d]['Questions'])][:5]))
check('script outcomes: cited per day = usage.Cited', all(soc[d] == I(U[d]['Cited']) for d in days))
check('script outcomes: rows within bounds (cited + not found + clarification <= scored <= turns)', bad_so == 0, f'{bad_so} rows')
for sc in ['Latin', 'Cyrillic', 'Arabic', 'CJK', 'Devanagari', 'Other', 'None']:
    if not all(sum(I(r['Turns']) for r in SO if r['Date'] == d and r['Script'] == sc) == I(U[d]['Script' + sc]) for d in days[-7:]):
        check(f'script outcomes: {sc} turns = usage.Script{sc} (last 7 days)', False)

# ── 3c. outcome rule ids and the wording fingerprint (brief §53) ──────────────
# Every turn carries exactly one rule id, and the rule's family must agree with the outcome counted in usage.csv.
RU = rd('outcome-rules-daily.csv'); rt = C.Counter(); fam = C.defaultdict(C.Counter)
for r in RU:
    n = I(r['Turns']); rt[r['Date']] += n; k = r['Rule']
    f = 'Cited' if k == 'cited' or k.startswith('cited.partial.') else 'NotFound' if k.startswith('nf.') else 'Clarification' if k.startswith('cl.') else 'OutOfScope' if k.startswith('oos.') else 'Greeting' if k.startswith('gr.') else 'Error' if k.startswith('err.') else 'Uncited'
    fam[r['Date']][f] += n
    if k.startswith('cited.partial.'): fam[r['Date']]['Partial'] += n
check('outcome rules: turns per day = usage.Questions', all(rt[d] == I(U[d]['Questions']) for d in days), str([d for d in days if rt[d] != I(U[d]['Questions'])][:5]))
check('outcome rules: each family per day = its usage.csv outcome count', all(fam[d][f] == I(U[d][f]) for d in days for f in ('Cited', 'NotFound', 'Clarification', 'OutOfScope', 'Greeting', 'Error', 'Uncited', 'Partial')),
      str([(d, f) for d in days for f in ('Cited', 'NotFound', 'Clarification', 'Partial') if fam[d][f] != I(U[d][f])][:5]))
ST = rd('answer-style-daily.csv'); stt = C.Counter()
for r in ST: stt[r['Date']] += I(r['Turns'])
check('answer style: turns per day = usage.Questions', all(stt[d] == I(U[d]['Questions']) for d in days))
check('answer style: no "with" count above its outcome\'s turns', all(I(r['With' + k]) <= I(r['Turns']) for r in ST for k in ('Lines', 'Hedges', 'Apologies', 'Signposts', 'Questions', 'Links') + (('Openers', 'Invitations', 'Absolutes', 'Emphasis', 'Nested', 'External', 'Freshness', 'Signoff') if 'WithSignoff' in ST[0] else ())))

# ── 3d. what people do next (tools/next_step.py, brief §53 step 3) ───────────
# Mature conversations only, so Answers per day can only be at or under usage.Questions; an answer either ended the
# conversation or had a next question, and every "next" count is bounded by the answers that had one.
NX = rd('answer-next-daily.csv'); nxt = C.Counter(); bad_nx = 0
for r in NX:
    n, e = I(r['Answers']), I(r['Ended']); nxt[r['Date']] += n
    if r['Class'] not in ('cited', 'partial', 'notfound', 'clarification'): bad_nx += 1
    if e > n or I(r['NextTyped']) + I(r['NextChip']) + I(r['NextNew']) > n - e or I(r['Disliked']) > n: bad_nx += 1
    if any(I(r[k]) > n - e for k in ('Rephrased', 'Within1m', 'NextCited')): bad_nx += 1
check('answer next: known classes, Ended within Answers, every next count within Answers − Ended', bad_nx == 0, f'{bad_nx} rows')
check('answer next: answers per day <= usage.Questions', all(nxt[d] <= I(U[d]['Questions']) for d in nxt if d in U), str([d for d in nxt if d in U and nxt[d] > I(U[d]['Questions'])][:5]))

# ── 4. conversations-daily.csv ───────────────────────────────────────────────
CV = {r['Date']: r for r in rd('conversations-daily.csv')}
check('conversations: one row per day', set(CV) == set(days), f'{set(CV) ^ set(days)}')
starts = C.Counter(min(x)[1].date().isoformat() for x in convs.values())
if FEED: check('conversations: Started = recount (by first-turn day)', all(I(CV[d]['Started']) == starts[d] for d in CV), str([(d, CV[d]['Started'], starts[d]) for d in CV if I(CV[d]['Started']) != starts[d]][:5]))
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
if 'ClarThenClar' in next(iter(CV.values())):
    check('conversations: ClarThenClar <= ClarTurns - ClarEnded', all(I(r['ClarThenClar']) <= I(r['ClarTurns']) - I(r['ClarEnded']) for r in CV.values()))
if 'TypedTopicBoth' in next(iter(CV.values())):
    check('conversations: topic switches within the pairs that carry a topic, pairs within mature turns − mature', all(
        I(r[t + 'TopicSwitched']) <= I(r[t + 'TopicBoth']) for r in CV.values() for t in ('Typed', 'Chip', 'New'))
        and all(sum(I(r[t + 'TopicBoth']) for t in ('Typed', 'Chip', 'New')) <= I(r['MatureTurns']) - I(r['Mature']) for r in CV.values()))

# conversation outcomes: identities, then an independent recount of ReachedCited and NFLaterCited
if 'ReachedCited' in next(iter(CV.values())):
    bad_o = 0
    for d, r in CV.items():
        for p in ('NF', 'Clar', 'Err'):
            t = I(r[p + 'Turns'])
            if I(r[p + 'LaterCited']) + I(r[p + 'Ended']) > t or sum(I(r[p + 'Next' + k]) for k in ('Typed', 'Chip', 'New', 'Other')) + I(r[p + 'Ended']) != t: bad_o += 1
        if I(r['ReachedCited']) > I(r['Mature']) or I(r['MultiTopic']) > I(r['WithTopic']) or I(r['TopicReturn']) > I(r['MultiTopic']) or I(r['WithTopic']) > I(r['Mature']): bad_o += 1
        if sum(I(r[k]) for k in ('Gap0to1', 'Gap2to5', 'Gap6to15', 'Gap16to60', 'GapOver60')) != I(r['MatureTurns']) - I(r['Mature']): bad_o += 1
    check('conversations: setback, topic and gap columns add up on every day', bad_o == 0, f'{bad_o} day/field failures')
    if FEED:
        fresh = max(t for v in convs.values() for _, t, _ in v)
        rc = C.Counter(); nf = C.Counter(); nfl = C.Counter()
        for v in convs.values():
            v = sorted(v); start = v[0][1]
            if (fresh - start).total_seconds() < 24 * 3600: continue
            d = start.date().isoformat()
            if any(o == 'Cited answer' for _, _, o in v): rc[d] += 1
            for i, (_, _, o) in enumerate(v):
                if o == 'Not found':
                    nf[d] += 1
                    if i < len(v) - 1 and any(x[2] == 'Cited answer' for x in v[i + 1:]): nfl[d] += 1
        check('conversations.ReachedCited matches feed recount on every day', all(I(CV[d]['ReachedCited']) == rc[d] for d in CV), str([(d, CV[d]['ReachedCited'], rc[d]) for d in CV if I(CV[d]['ReachedCited']) != rc[d]][:5]))
        check('conversations.NFTurns and NFLaterCited match feed recount on every day', all(I(CV[d]['NFTurns']) == nf[d] and I(CV[d]['NFLaterCited']) == nfl[d] for d in CV))

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
    if 'EndedThere' in r and (I(r['Partial']) > I(r['Cited']) or I(r['Cited']) + I(r['NotFound']) + I(r['Clarification']) > I(r['Count']) or I(r['EndedThere']) > I(r['Mature']) or I(r['Mature']) > I(r['Count']) or I(r['TimedTurns']) > I(r['Count'])):
        check('starter prompts: scorecard bounds (Partial <= Cited, outcomes <= Count, EndedThere <= Mature <= Count)', False, str(r['Month']) + ' ' + str(r['Prompt'])[:40])
og = C.Counter()
for r in CO: og[r['Date'][:7]] += I(r['OrganicFirstTurns'])
sm = C.Counter()
for d in days: sm[d[:7]] += I(U[d]['Sessions'])
usm = C.Counter()
for d in days: usm[d[:7]] += I(U[d]['StarterPromptFirstTurns'])
check('usage.StarterPromptFirstTurns by month = starter-prompts-monthly', usm == spm, str({m: (usm[m], spm[m]) for m in set(usm) | set(spm) if usm[m] != spm[m]}))
if FEED: check('usage.StarterPromptFirstTurns total = feed first turns with a chip', sum(usm.values()) == starter_vals['chip'], f"{sum(usm.values())} vs {starter_vals['chip']}")
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

raw_total = sum(v for _, _, v in rows)
if os.path.exists(REPO + '/ga4/clicks-daily.csv'):
    CK = rd('ga4/clicks-daily.csv'); CP = rd('ga4/clicks-pages-daily.csv')
    check('clicks-daily total = raw exports total', sum(I(r['Views']) for r in CK) == raw_total, f"{sum(I(r['Views']) for r in CK)} vs {raw_total}")
    check('clicks-pages-daily total = raw exports total', sum(I(r['Views']) for r in CP) == raw_total)
    by_d = C.Counter(); by_p = C.Counter()
    for r in CK: by_d[(r['Date'], r['Source'])] += I(r['Views'])
    for r in CP: by_p[(r['Date'], r['Source'])] += I(r['Views'])
    check('clicks-daily and clicks-pages-daily agree by day and source', by_d == by_p)
    check('clicks-daily devices sum to views on every row', all(I(r['Mobile']) + I(r['Desktop']) + I(r['Tablet']) + I(r.get('OtherDevice')) == I(r['Views']) for r in CK))
    # Join rate: a click-through follows a citation, so almost every clicked page should be a cited page that month.
    cited = {(r['Month'], r['URL']) for r in CI}
    jv = C.Counter()
    for r in CP: jv['in' if (r['Date'][:7], r['URL']) in cited else 'out'] += I(r['Views'])
    jr = jv['in'] / max(1, jv['in'] + jv['out'])
    check('clicked pages match cited pages (same month) for at least 99% of click-throughs', jr >= 0.99, f'{jr:.2%}')
    stale = max(r['Date'] for r in CK) < max(x[0] for x in rows)[:4] + '-' + max(x[0] for x in rows)[4:6] + '-' + max(x[0] for x in rows)[6:]
    check('clicks files are up to date with the raw exports (re-run tools/make_clicks.py)', not stale)
else:
    warn('clicks', 'ga4/clicks-daily.csv missing: run tools/make_clicks.py')

# Page join (Usage › Pages): citations to citizensinformation.ie must land on pages that have site-view data.
nu = lambda u: re.sub(r'[?#].*$', '', u.strip().lower()).rstrip('/')
PV = {nu('https://www.citizensinformation.ie' + r['Page path and screen class']) for r in rd('ga4/categories-and-views.csv') if r['Page path and screen class'].startswith('/en/')}
ci_tot = sum(I(r['Citations']) for r in CI if 'citizensinformation.ie' in r['URL'])
ci_in = sum(I(r['Citations']) for r in CI if 'citizensinformation.ie' in r['URL'] and nu(r['URL']) in PV)
check('citations to CI pages that join a page with site views (Usage › Pages) at least 98%', ci_tot and ci_in / ci_tot >= 0.98, f'{ci_in / max(1, ci_tot):.2%}')

# ── 8b. first-turn errors, chip and typed (brief §64) ─────────────────────────
if 'StarterPromptErrors' in U[days[0]]:
    check('first-turn errors: StarterPromptErrors <= StarterPromptFirstTurns, OrganicFirstErrors <= OrganicFirstTurns, both <= Error', all(
        I(U[d]['StarterPromptErrors']) <= I(U[d]['StarterPromptFirstTurns']) and I(U[d]['OrganicFirstErrors']) <= I(U[d]['OrganicFirstTurns'])
        and I(U[d]['StarterPromptErrors']) + I(U[d]['OrganicFirstErrors']) <= I(U[d]['Error']) for d in days))

# ── 9a. pages-cited.csv against citations-monthly.csv (brief §62) ─────────────
CM = rd('citations-monthly.csv'); PC = rd('pages-cited.csv')
check('citations-monthly: Partial <= Answers <= Citations on every row', all(I(r['Partial']) <= I(r['Answers']) <= I(r['Citations']) for r in CM))
check('pages-cited: citations and answers sum to citations-monthly', sum(I(r['Citations']) for r in PC) == sum(I(r['Citations']) for r in CM) and sum(I(r['Answers']) for r in PC) == sum(I(r['Answers']) for r in CM),
      f"{sum(I(r['Citations']) for r in PC)} vs {sum(I(r['Citations']) for r in CM)}")
check('pages-cited: one row per URL, FirstCited <= LastCited, first-after-LastMod on or after LastMod', len({r['URL'] for r in PC}) == len(PC)
      and all(r['FirstCited'] <= r['LastCited'] for r in PC) and all((not r['FirstCitedAfterLastMod']) or r['FirstCitedAfterLastMod'] >= r['LastMod'] for r in PC))

# ── 9a0. what people ask (brief §66): intents sum to the day's turns; asked pages add up; question topics only where the answer had none
QI = rd('question-intent-daily.csv'); qit = C.Counter()
for r in QI: qit[r['Date']] += I(r['Turns'])
check('question intent: turns per day = usage.Questions', all(qit[d] == I(U[d]['Questions']) for d in days), str([(d, qit[d], U[d]['Questions']) for d in days if qit[d] != I(U[d]['Questions'])][:3]))
check('question intent: outcomes sum to Turns, flags and WithTopic within Turns', all(sum(I(r[k]) for k in ('Cited', 'NotFound', 'Clarification', 'Error', 'OutOfScope', 'Greeting', 'Uncited')) == I(r['Turns'])
      and all(I(r[k]) <= I(r['Turns']) for k in ('Partial', 'Year', 'Euro', 'YesNo', 'Situation', 'WithTopic')) and I(r['SituationCited']) + I(r['SituationNotFound']) <= I(r['Situation'])
      and I(r['NamedCited']) + I(r['NamedNotFound']) + I(r['NamedClarification']) <= I(r['WithTopic']) and r['Chip'] in ('0', '1', '2') for r in QI))
AP = rd('asked-pages-monthly.csv')
check('asked pages: the seven outcome columns sum to Asked, and Asked >= 5 on every row', all(sum(I(r[k]) for k in ('CitedSame', 'CitedUnderHub', 'CitedSameCategory', 'CitedOther', 'NotFound', 'Clarification', 'Other')) == I(r['Asked']) and I(r['Asked']) >= 5 for r in AP))
QT = rd('question-topics-daily.csv'); qtt = C.Counter()
for r in QT: qtt[r['Date']] += I(r['Turns'])
# (category-outcomes recovers a topic for some of these turns from other turns in the conversation, so its 'unknown'
#  row is smaller than this; the bound that holds is the day's turns)
check('question topics: per day no more turns than usage.Questions, outcomes sum to Turns', all(qtt[d] <= I(U[d]['Questions']) for d in qtt if d in U)
      and all(sum(I(r[k]) for k in ('Cited', 'NotFound', 'Clarification', 'Error', 'OutOfScope', 'Greeting', 'Uncited')) == I(r['Turns']) for r in QT))

CI2 = rd('citations-intent-monthly.csv'); AW = rd('asked-pages-weekly.csv')
check('citations by intent: Partial <= Answers, Answers >= 5 on every row', all(I(r['Partial']) <= I(r['Answers']) and I(r['Answers']) >= 5 for r in CI2))
check('asked pages weekly: CitedIt + NotFound <= Asked and Partial <= Asked - NotFound on every row (partial counts every cited answer, not only hits)', all(I(r['CitedIt']) + I(r['NotFound']) <= I(r['Asked']) and I(r['Partial']) <= I(r['Asked']) - I(r['NotFound']) for r in AW))
awm = C.Counter(); apm = C.Counter()
for r in AW: awm[(r['Week'][:7], r['URL'])] += I(r['Asked'])
check('asked pages weekly: a page in the weekly file was named 30+ times in some month', all(any(I(x['Asked']) >= 30 for x in AP if x['URL'] == u) for u in {r['URL'] for r in AW}))
# the topic layer (brief §75): three monthly files from the broad category cut, and the register's topic rows
OUT7 = ('Cited', 'NotFound', 'Clarification', 'Error', 'OutOfScope', 'Greeting', 'Uncited')
QTM = rd('question-topics-monthly.csv'); QCM = rd('question-categories-monthly.csv'); QIC = rd('question-intent-category-monthly.csv')
LEXT = {}
try:
    import json as _j
    _lx = _j.load(open(f'{REPO}/question-lexicon.json', encoding='utf-8')); LEXT = {t: c for c, tops in (_lx.get('topics') or {}).items() for t in tops}
    check('lexicon: derivation_version present and every topic has 1+ keywords of 2+ characters (gp, 1g, lpt are real)', bool(_lx.get('derivation_version'))
          and all(spec.get('keywords') and all(len(k) >= 2 for k in spec['keywords']) for tops in (_lx.get('topics') or {}).values() for spec in tops.values()))
except (OSError, ValueError): check('lexicon: readable', False)
for name, F, extra in (('question topics monthly', QTM, lambda r: r['Topic'] in LEXT and LEXT[r['Topic']] == r['Category'] and I(r['Turns']) >= 5),
                       ('question categories monthly', QCM, lambda r: r['Source'] in ('cited', 'page', 'topic', 'none') and (r['Source'] == 'none') == (r['Category'] == '(none)')),
                       ('question intent by category', QIC, lambda r: I(r['Turns']) >= 5)):
    check(f'{name}: outcomes sum to Turns, Partial <= Cited, and the row rule holds', all(sum(I(r[k]) for k in OUT7) == I(r['Turns']) and I(r['Partial']) <= I(r['Cited']) and extra(r) for r in F),
          str([(r['Month'], r.get('Category'), r.get('Topic') or r.get('Source') or r.get('Intent')) for r in F if not (sum(I(r[k]) for k in OUT7) == I(r['Turns']) and I(r['Partial']) <= I(r['Cited']) and extra(r))][:3]))
if QCM:
    qcm = C.Counter(); qim = C.Counter()
    for r in QCM: qcm[r['Month']] += I(r['Turns'])
    for r in QI:
        if r['Chip'] == '0': qim[r['Date'][:7]] += I(r['Turns'])
    # a turn is in one category per source but may be in two categories (the answer's and the question's), so the
    # bound is two typed turns per typed turn; the residue plus the cited-only rows cannot exceed the typed turns
    check('question categories monthly: per month, turns <= 2 x typed turns, and none + cited rows <= typed turns', all(qcm[m] <= 2 * qim[m] for m in qcm)
          and all(sum(I(r['Turns']) for r in QCM if r['Month'] == m and r['Source'] in ('none', 'cited')) <= qim[m] for m in qcm), str([(m, qcm[m], qim[m]) for m in qcm if qcm[m] > 2 * qim[m]][:3]))
    check('question topics monthly: a topic\'s turns in a month <= the topic-or-page turns of its category that month',
          all(I(r['Turns']) <= sum(I(x['Turns']) for x in QCM if x['Month'] == r['Month'] and x['Category'] == r['Category']) for r in QTM))
TMPL = rd('answer-templates-daily.csv')
try: _tj = _j.load(open(f'{REPO}/answer-templates.json', encoding='utf-8')); _tids = {t['id'] for t in _tj['templates']}; _tver = _tj.get('derivation_version', '')
except (OSError, ValueError, KeyError): _tids = set(); _tver = ''
if TMPL:
    tnone = C.Counter()
    for r in TMPL:
        if r['Template'] == '(none)': tnone[r['Date']] += I(r['Turns'])
    check('answer templates: every id is in answer-templates.json, outcomes sum to Turns, and the (none) row never exceeds the day\'s turns',
          all((r['Template'] == '(none)' or r['Template'] in _tids) and sum(I(r[k]) for k in OUT7) == I(r['Turns']) for r in TMPL) and all(tnone[d] <= I(U[d]['Questions']) for d in tnone if d in U),
          str([r['Template'] for r in TMPL if r['Template'] != '(none)' and r['Template'] not in _tids][:3]))
    check('answer templates: derivation version agrees with the lexicon', _tver == _lx.get('derivation_version', ''), f'{_tver} vs {_lx.get("derivation_version", "")}')
ORG = rd('answer-signposts-monthly.csv')
if ORG:
    _oids = {o['id'] for o in _tj.get('organisations', [])} | {'(any)', '(external)', '(none)'}
    allrow = {(r['Month'], r['Org']): I(r['Turns']) for r in ORG if r['Category'] == '(all)'}
    catsum = C.Counter()
    for r in ORG:
        if r['Category'] != '(all)': catsum[(r['Month'], r['Org'])] += I(r['Turns'])
    anyrow = {m: n for (m, o), n in allrow.items() if o == '(any)'}; ext = {m: n for (m, o), n in allrow.items() if o == '(external)'}; none = {m: n for (m, o), n in allrow.items() if o == '(none)'}
    qpm = C.Counter()
    for d, r in U.items(): qpm[d[:7]] += I(r['Questions'])
    check('answer signposts: every org is listed, outcomes sum to Turns, category rows <= the (all) row, (any) + (none) = the month\'s turns, (external) <= (any)',
          all(r['Org'] in _oids and sum(I(r[k]) for k in OUT7) == I(r['Turns']) for r in ORG) and all(catsum[k] <= n for k, n in allrow.items())
          and all(anyrow.get(m, 0) + none.get(m, 0) == qpm[m] for m in anyrow) and all(ext.get(m, 0) <= anyrow.get(m, 0) for m in anyrow),
          str([(m, anyrow.get(m, 0) + none.get(m, 0), qpm[m]) for m in anyrow if anyrow.get(m, 0) + none.get(m, 0) != qpm[m]][:3]))
FIG = rd('answer-figures-monthly.csv')
if FIG:
    fall = {r['Month']: r for r in FIG if r['URL'] == '(all)'}
    check('answer figures: Matched + Unmatched + Unverifiable = Figures, Partial <= Answers, Figures >= Answers, page rows <= the (all) row, Answers <= the month\'s turns',
          all(I(r['Matched']) + I(r['Unmatched']) + I(r['Unverifiable']) == I(r['Figures']) and I(r['Partial']) <= I(r['Answers']) and I(r['Figures']) >= I(r['Answers']) for r in FIG)
          and all(I(r['Answers']) <= I(fall[r['Month']]['Answers']) for r in FIG if r['Month'] in fall) and all(I(r['Answers']) <= sum(I(U[d]['Questions']) for d in U if d[:7] == m) for m, r in fall.items()),
          str([(r['Month'], r['URL'][-40:]) for r in FIG if I(r['Matched']) + I(r['Unmatched']) + I(r['Unverifiable']) != I(r['Figures'])][:3]))
SIT = rd('question-situation-monthly.csv'); ASK = rd('clarification-asks-monthly.csv'); PERS = rd('answer-personalisation-monthly.csv')
if SIT:
    typed_m = C.Counter()
    for r in QI:
        if r['Chip'] == '0': typed_m[r['Date'][:7]] += I(r['Turns'])
    anyno = C.Counter()
    for r in SIT:
        if r['Category'] == '(all)' and r['Flag'] in ('(any situation)', '(no situation)'): anyno[r['Month']] += I(r['Turns'])
    check('question situation: outcomes sum to Turns, flags are of a known kind, no flag exceeds the month\'s typed turns, (any) + (no) = typed turns',
          all(sum(I(r[k]) for k in OUT7) == I(r['Turns']) and re.match(r'^(county:[a-z]+|age:(16-24|25-44|45-65|66\+)|household:(children|partner|alone)|work:[a-z-]+|payment_on|year:20[12]\d|shape:(letter|multi|url)|\(any situation\)|\(no situation\))$', r['Flag']) for r in SIT)
          and all(I(r['Turns']) <= typed_m[r['Month']] for r in SIT) and all(anyno[m] == typed_m[m] for m in anyno),
          str([(r['Month'], r['Flag']) for r in SIT if not re.match(r'^(county:|age:|household:|work:|payment_on|year:|shape:|\(any|\(no)', r['Flag'])][:3] + [(m, anyno[m], typed_m[m]) for m in anyno if anyno[m] != typed_m[m]][:3]))
    clar_m = C.Counter()
    for r in QI:
        if r['Chip'] == '0': clar_m[r['Date'][:7]] += I(r['Clarification'])
    anyn = C.Counter()
    for r in ASK:
        if r['Asks'] in ('(any)', '(none)'): anyn[r['Month']] += I(r['Turns'])
    check('clarification asks: Given is 0/1, (any) + (none) = the month\'s typed clarifications, every class row <= that', all(r['Given'] in ('0', '1') for r in ASK) and all(anyn[m] == clar_m[m] for m in anyn)
          and all(I(r['Turns']) <= clar_m[r['Month']] for r in ASK), str([(m, anyn[m], clar_m[m]) for m in anyn if anyn[m] != clar_m[m]][:3]))
    cited_m = C.Counter()
    for r in QI:
        if r['Chip'] == '0': cited_m[r['Date'][:7]] += I(r['Cited'])
    pm = C.Counter()
    for r in PERS: pm[r['Month']] += I(r['Answers'])
    check('answer personalisation: the four cells sum to the month\'s typed cited answers', all(pm[m] == cited_m[m] for m in pm), str([(m, pm[m], cited_m[m]) for m in pm if pm[m] != cited_m[m]][:3]))
# floors on every row that names a class (brief §76, audit finding 2): the totals are the only rows exempt
if SIT: check('question situation: every row naming a county, band, year or shape has 5+ turns, (all) rows included', all(I(r['Turns']) >= 5 or r['Flag'] in ('(any situation)', '(no situation)') for r in SIT),
              str([(r['Month'], r['Category'], r['Flag']) for r in SIT if I(r['Turns']) < 5 and r['Flag'] not in ('(any situation)', '(no situation)')][:3]))
if ORG: check('answer signposts: every row naming an organisation has 5+ turns, (all) rows included', all(I(r['Turns']) >= 5 or r['Org'] in ('(any)', '(external)', '(none)') for r in ORG),
              str([(r['Month'], r['Org'], r['Category']) for r in ORG if I(r['Turns']) < 5 and r['Org'] not in ('(any)', '(external)', '(none)')][:3]))
# the privacy sweep (brief §76, audit findings 1 and 3): the deploy itself checks that no tracked data or text file carries a
# text column, a long free-text cell outside the known prose columns, or an identifier pattern, and that costs.csv carries
# role labels and not resource names. Reports file and rule only, never a value.
try: _tracked = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, cwd=REPO).stdout.split('\n')
except Exception: _tracked = []
_tracked = [f for f in _tracked if f.endswith(('.csv', '.json', '.md')) and not f.startswith('brief/')]
_LONG_OK = {'evidence', 'detail', 'title', 'pattern', 'keywords', '_comment', 'note', 'expected_effect', 'URL', 'url', 'Citations', 'Meter', 'ResourceId'}
_ID_RX = {'pps': re.compile(r'\b\d{7}[A-Za-z]{1,2}\b'), 'email': re.compile(r'[\w.+-]+@[\w-]+\.[a-z]{2,}'), 'iban': re.compile(r'\bIE\d{2}[A-Z]{4}\d{14}\b'),
          'mobile': re.compile(r'\b(?:\+353\s?|0)8[3-9]\s?\d{3}\s?\d{4}\b'), 'resource name': re.compile(r'askci-?prod-?[a-z0-9]{6,}|whl536qf')}
_hits = []
for _f in _tracked:
    try:
        with open(f'{REPO}/{_f}', encoding='utf-8', errors='ignore') as fh: _txt = fh.read()
    except OSError: continue
    if _f.endswith('.csv'):
        _rows = list(csv.reader(io.StringIO(_txt))); _hdr = _rows[0] if _rows else []
        if any(h.strip() in ('User Query', 'Assistant Response') for h in _hdr): _hits.append((_f, 'text column header'))
        for _r in _rows[1:]:
            _long = [(_hdr[i] if i < len(_hdr) else str(i)) for i, c in enumerate(_r) if len(c) > 400 and (_hdr[i] if i < len(_hdr) else '') not in _LONG_OK]
            if _long: _hits.append((_f, 'long cell in ' + _long[0])); break
    for _n, _rx in _ID_RX.items():
        if _rx.search(_txt): _hits.append((_f, _n))
check('privacy sweep: no tracked csv/json/md carries a text column, a long free-text cell outside the known prose columns, an identifier pattern or a production resource name', not _hits, str(sorted(set(_hits))[:6]))
_CO = rd('costs.csv')
check('costs.csv: every ResourceId ends in a role label (service- / admin- / shared-), never a resource name', bool(_CO) and all(re.match(r'^(service|admin|shared)-', (r.get('ResourceId') or '').rstrip('/').rsplit('/', 1)[-1]) for r in _CO if r.get('ResourceId')),
      str(C.Counter((r.get('ResourceId') or '').rstrip('/').rsplit('/', 1)[-1][:12] for r in _CO if r.get('ResourceId') and not re.match(r'^(service|admin|shared)-', (r.get('ResourceId') or '').rstrip('/').rsplit('/', 1)[-1])).most_common(3)))
# VERSIONS.json (brief §76): the manifest the analyst's refresh wrote; its versions must match the files in force and its
# aggregate hashes must match the committed files, so the published aggregates are the ones the feed recount passed.
# Checked in files-only mode (the deploy); during a refresh the recount runs before the manifest is rewritten, so there
# the check would only compare against the previous refresh.
if not FILES_ONLY: print('  (VERSIONS.json is checked in --files-only mode; this recount is what the next manifest records)')
try:
    if not FILES_ONLY: raise StopIteration
    _V = _j.load(open(f'{REPO}/VERSIONS.json', encoding='utf-8'))
    import hashlib as _hl
    _rules_now = next((r.get('OutcomeRules') for r in reversed(rd('usage.csv')) if r.get('OutcomeRules')), '')
    _hash_bad = []
    for _name, _m in (_V.get('aggregates') or {}).items():
        try:
            with open(f'{REPO}/{_name}', 'rb') as fh: _h = _hl.sha256(fh.read()).hexdigest()[:16]
        except OSError: _h = 'missing'
        if _h != _m.get('sha256'): _hash_bad.append(_name)
    check('VERSIONS.json: versions agree with the files (rules, lexicon, derivation) and the recount had no failures',
          _V['versions'].get('outcome_rules') == _rules_now and _V['versions'].get('lexicon') == _lx.get('version') and _V['versions'].get('derivation') == _lx.get('derivation_version') and _V['audit'].get('failed') == 0,
          f"manifest rules {_V['versions'].get('outcome_rules')} vs {_rules_now}; lexicon {_V['versions'].get('lexicon')} vs {_lx.get('version')}; derivation {_V['versions'].get('derivation')} vs {_lx.get('derivation_version')}; failed {_V['audit'].get('failed')}")
    check('VERSIONS.json: every aggregate file is the one the feed recount passed (hashes match)', not _hash_bad, str(_hash_bad[:5]))
except StopIteration: pass
except (OSError, ValueError, KeyError) as e:
    check('VERSIONS.json: present and readable (written by tools/refresh.py)', False, str(e)[:80])
GAPSF = rd('content-gaps.csv')
try: _rc = _j.load(open(f'{REPO}/register-config.json', encoding='utf-8')); _kinds = set(_rc.get('teams', {}))
except (OSError, ValueError): _kinds = set()
check('content gaps: every kind has a team in register-config.json; missing-page and signpost rows carry a topic (not a URL), a category and asks > 0',
      all(r['kind'] in _kinds for r in GAPSF) and all(r['page'] and not r['page'].startswith('http') and r['category'] and I(r['asks']) > 0 for r in GAPSF if r['kind'] in ('missing-page', 'signpost')),
      str([(r['kind'], r['page'][:40]) for r in GAPSF if r['kind'] not in _kinds][:3]))
IJ = rd('intent-journeys-monthly.csv'); SBI = rd('setback-intents-monthly.csv')
ends = C.Counter(r['Month'] for r in IJ for _ in range(I(r['Turns'])) if r['To'] == 'END'); cvm = C.Counter()
for d, r in CV.items(): cvm[d[:7]] += I(r['Mature'])
check('intent journeys: END rows per month = mature conversations started that month', all(ends[m] == cvm[m] for m in cvm if m in ends), str([(m, ends[m], cvm[m]) for m in cvm if m in ends and ends[m] != cvm[m]][:3]))
check('setback intents: Ended + Same + Other = Turns on every row, setback is NF or Clar', all(I(r['Ended']) + I(r['SameIntentNext']) + I(r['OtherIntentNext']) == I(r['Turns']) and r['Setback'] in ('NF', 'Clar') for r in SBI))

# ── 9a1. safety-daily.csv (brief §65) ─────────────────────────────────────────
SF = rd('safety-daily.csv')
check('safety: outcomes sum to Turns on every row, and no flag exceeds the day\'s turns', all(
    sum(I(r[k]) for k in ('Cited', 'NotFound', 'Clarification', 'Error', 'OutOfScope', 'Greeting', 'Uncited')) <= I(r['Turns']) and (r['Date'] not in U or I(r['Turns']) <= I(U[r['Date']]['Questions'])) for r in SF))

# ── 9a2. repeat-questions-monthly.csv against usage.csv (brief §63) ───────────
RQ = {r['Month']: r for r in rd('repeat-questions-monthly.csv')}; um = C.Counter(); usm2 = C.Counter()
for d in days: um[d[:7]] += I(U[d]['Questions']); usm2[d[:7]] += I(U[d]['StarterPromptFirstTurns'])
check('repeat questions: turns per full month = usage.Questions, chips = usage.StarterPromptFirstTurns', all(I(RQ[m]['Turns']) == um[m] and I(RQ[m]['StarterFirstTurns']) == usm2[m] for m in um if m in RQ and m < days[-1][:7]), str([(m, RQ[m]['Turns'], um[m]) for m in um if m in RQ and m < days[-1][:7] and I(RQ[m]['Turns']) != um[m]][:3]))
check('repeat questions: Top10 <= Top25 <= ... <= Top250 <= FirstTurns; StarterFirstTurns <= Top250 + tail', all(I(r['Top10']) <= I(r['Top25']) <= I(r['Top50']) <= I(r['Top100']) <= I(r['Top250']) <= I(r['FirstTurns']) for r in RQ.values()))

# ── 9b. prompts.json and the prompt canary ────────────────────────────────────
# The system prompts stay in the git-ignored review folder; the repo holds a set-level fingerprint only (brief §60).
# No tracked file may carry the canary line that every local prompt file starts with.
if os.path.exists(REPO + '/prompts.json'):
    PJ = json.load(open(REPO + '/prompts.json'))
    check('prompts.json: snapshot date, count and set hash present', bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(PJ.get('snapshot', '')))) and int(PJ.get('prompts', 0)) > 0 and len(str(PJ.get('set_sha256', ''))) == 64)
_can = 'ASKCI-PROMPT-' + 'CANARY'
_tracked = subprocess.run(['git', '-C', REPO, 'ls-files', '-z'], capture_output=True).stdout.decode().split('\0')
_leak = []
for _f in _tracked:
    if not _f or _f.startswith('tools/hooks/') or _f == 'tools/audit_data.py' or _f == 'tools/prompt_fingerprint.py' or _f == 'tools/check_rules_vs_prompts.py': continue
    try:
        if _can in open(REPO + '/' + _f, encoding='utf-8', errors='ignore').read(): _leak.append(_f)
    except (IsADirectoryError, FileNotFoundError): pass
check('prompt canary: no tracked file carries a system-prompt copy', not _leak, ', '.join(_leak[:5]))

# ── 10. events.json ──────────────────────────────────────────────────────────
E = json.load(open(REPO + '/events.json'))['events']
check('events.json: content events carry a page', all(bool(e.get('page')) for e in E if e.get('kind') == 'content'))
check('events.json: valid statuses and kinds', all(e['status'] in ('confirmed', 'candidate', 'rejected') and e['kind'] in ('model', 'prompt', 'launch', 'chips', 'content', 'observed change', 'other') for e in E))
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
