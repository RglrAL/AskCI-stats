#!/usr/bin/env python3
"""Generate the dashboard's daily aggregate files from AskCI QA feed exports (raw or redacted).

Outputs (all daily counts; nothing per-turn and no text crosses into the dashboard):

  usage.csv            Date, Questions, Sessions, then optional columns the dashboard may use:
                         Answered, Unanswered, Flagged            legacy outcome split (see below)
                         Likes, Dislikes, DislikesOnCited             feedback (always; the feed carries Feedback)
                         StarterPromptFirstTurns, OrganicFirstTurns  only when the redacted feed carries Starter Prompt
                         ScriptLatin, ScriptCyrillic, ScriptArabic, ScriptCJK, ScriptDevanagari, ScriptOther, ScriptNone
                                                                   only when the redacted feed carries Query Script
                         Cited, NotFound, Clarification, Error, OutOfScope, Greeting, Uncited, Partial, Scored, OutcomeRules
                         ModalCited, ModalNotFound, ModalScored, WebCited, WebNotFound, WebScored,
                         NewTopicCited, NewTopicNotFound, NewTopicScored, UserFollowupCited, UserFollowupNotFound,
                         UserFollowupScored, SuggestedCited, SuggestedNotFound, SuggestedScored
                                                                   outcome by source and by question type (with the taxonomy)
                         LatencyP99ms, LatUnder10s, Lat10to20s, Lat20to30s, LatOver30s
                                                                   latency p99 and bands, positive values only
                                                                   outcome taxonomy, only when the redacted feed carries an
                                                                   Outcome column (tools/redact_feed.py writes it)
                         NewTopic, UserFollowup, SuggestedFollowup  question types
                         ModalTurns, WebTurns, OtherTurns, ModalSessions, WebSessions  by source
                         Citations                                 cited URLs
                         LatencyP50ms, LatencyP90ms                response time, positive values only
                         VoiceTurns, VoiceSessions                 only when the export has an input-mode column
  usage-hours.csv      Date, Hour, Turns, Sessions   (hour of day, Irish time)
  categories.csv       Category, Citations, Month    (current dashboard contract; display names)
  categories-daily.csv Date, Category, Citations     (slugs, by day)
  conversations-daily.csv   by conversation start day: Started, Mature, Turns1..Turns9, Turns10plus, MatureTurns,
                            Span0to1, Span2to5, Span6to15, Span16to60, SpanOver60 (mature multi-turn, minutes),
                            ChipUse, TypedUse (mature conversations with at least one such turn), and per first
                            outcome First<Outcome>, First<Outcome>Single, First<Outcome>Turns (mature)
  category-outcomes-daily.csv  Date, Category (attributed slug or unknown), Turns, Cited, NotFound, Clarification,
                            Error, OutOfScope, Greeting, Uncited, Scored, OrganicFirstTurns, DislikesOnCited
  citations-monthly.csv     Month, URL (normalised), Citations, Category (known slug or blank)
  journeys-monthly.csv      Month, From, To, Conversations (consecutive category steps, mature conversations)
  starter-prompts-monthly.csv  Month, Prompt, Count, Cited, FollowedByTyped, FollowedBySuggested
  latency-buckets-daily.csv  Date, Kind (words | citations), Bucket, Turns, LatencySumMs — response time by
                            response length and by citation count (needs Response Words from the redaction)
  category-outcomes-daily.csv also carries Organic<Outcome> columns: organic first turns by their outcome.
  usage-hours.csv also carries NotFound, Errors, Timed and LatencySumMs per hour slot.

Conversation rules (admin-app spec): a conversation starts on the day of its first turn; it is
mature when its first turn is at least 24 hours before the latest timestamp in the data, so
depth metrics are computed only on mature conversations. Attributed category: a turn's own
primary cited category, else the most frequent among the other turns of its conversation,
else unknown (failed turns carry no category of their own, so category failure rates are
lower bounds).

Definitions:
  Questions   turns received (one feed row each)
  Sessions    conversations started (distinct Conversation ID with Turn # == 1)
  Answered    turns with at least one citation URL
  Flagged     turns with Flagged == Yes (these carry no citations)
  Unanswered  turns with no citation and not flagged
  Outcomes    from the redacted feed's Outcome column (seven classes, rules versioned in redact_feed.py);
              Partial = cited answers that also match the not-found pattern; Scored = turns excluding
              Greeting, Error and Out of scope, the denominator for quality rates
  Categories  one hit per distinct category per turn, from the Categories column (or, if blank,
              from the /en/<category>/ segment of the cited URLs). From April 2026 the feed's
              Categories column is already distinct per turn, so this equals the hand-maintained
              categories.csv (within 5%). Before April the column repeated a category once per
              citation, and the old file counted those repeats, which inflated Jan–Mar by roughly
              40%. `--category-rule tokens` reproduces that old counting if continuity matters.

Rows repeated across input files (same Conversation ID and Turn #, as happens on the boundary
day of two exports) are counted once.

Feed timestamps are Irish local time (Europe/Dublin, confirmed 8 Oct 2026), so days and hours
here are Irish. The feed files themselves stay out of git.

Usage:
    python3 tools/make_usage.py qa-feed-redacted_*.csv --out-dir .          # write the four files
    python3 tools/make_usage.py qa-feed-redacted_*.csv --compare .          # compare with existing files, write nothing
    python3 tools/make_usage.py qa-feed_*.csv -o usage.csv                  # usage.csv only (old behaviour)
"""
import argparse, csv, os, re, sys
from collections import defaultdict
from datetime import datetime

TS_FORMAT = "%b %d, %Y %H:%M"   # e.g. "Jun 06, 2026 19:50"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
CAT_NAME = {  # feed slug -> display name used by the existing categories.csv (later months' spelling)
    "social-welfare": "Social Welfare", "money-and-tax": "Money & Tax", "employment": "Employment",
    "moving-country": "Moving Country", "housing": "Housing", "travel-and-recreation": "Travel and Recreation",
    "birth-family-relationships": "Family and Relationships", "health": "Health", "returning-to-ireland": "RTI",
    "education": "Education", "justice": "Justice", "consumer": "Consumer", "death": "Death", "about": "About",
    "government-in-ireland": "Government in Ireland", "environment": "Environment",
}
URL_RE = re.compile(r'https?://[^\s,;|"]+')
MATURITY_HOURS = 24
OUTCOMES = ["Cited answer", "Not found", "Clarification", "Error", "Out of scope", "Greeting", "Uncited answer"]
OUT_KEY = {"Cited answer": "Cited", "Not found": "NotFound", "Clarification": "Clarification", "Error": "Error",
           "Out of scope": "OutOfScope", "Greeting": "Greeting", "Uncited answer": "Uncited"}


def norm_url(u):
    u = u.strip().rstrip(".,;)")
    m = re.match(r"^(https?)://([^/?#]+)([^?#]*)", u, re.I)
    if not m:
        return None
    host = m.group(2).lower()
    if host == "citizensinformation.ie":
        host = "www.citizensinformation.ie"
    path = m.group(3).rstrip("/") or "/"
    return f"https://{host}{path}"
# Category from a cited URL: citizensinformation.ie only, /en/<slug>/ or the old-site /<slug>/ with
# underscores; the slug must be a known category or the hit is dropped (and counted).
CAT_SEG_RE = re.compile(r'^https?://(?:www\.)?citizensinformation\.ie/(?:en/)?([^/?#]+)')
KNOWN_SLUGS = set(CAT_NAME) | {"my-situation"}


def url_slug(u):
    m = CAT_SEG_RE.match(u)
    if not m:
        return None
    slug = m.group(1).lower().replace("_", "-")
    return slug if slug in KNOWN_SLUGS else None
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def pct(sorted_vals, p):
    if not sorted_vals:
        return ""
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100 * len(sorted_vals) + 0.5)) - 1))
    return sorted_vals[k]


def find_col(fields, pattern):
    rx = re.compile(pattern, re.I)
    return next((c for c in fields if rx.search(c)), None)


CATEGORY_RULE = "distinct"   # or "tokens": every Categories entry, repeats included, no URL fallback (old file's rule)


def aggregate(files, skip_days=frozenset()):
    D = defaultdict(lambda: defaultdict(int))        # date -> counter name -> n
    sess = defaultdict(lambda: defaultdict(set))     # date -> set name -> conversation ids
    lat = defaultdict(list)                          # date -> latencies
    hours = defaultdict(lambda: defaultdict(int))    # (date, hour) -> turns
    hour_sess = defaultdict(set)                     # (date, hour) -> conversation ids (turn 1)
    cats = defaultdict(lambda: defaultdict(int))     # date -> slug -> hits
    bad = 0; has_voice = False; cat_dropped = 0; has_outcome = False; rules = set(); has_starter = False; has_script = False
    recs = []                                        # per-turn minimal records for the conversation pass (no text)
    cites_m = defaultdict(int)                       # (month, url) -> citations
    latb = defaultdict(lambda: defaultdict(int))     # (date, kind, bucket) -> turns, latsum
    has_words = False
    seen = set(); dupes = 0   # exports taken on different days overlap on their boundary day
    for f in files:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            r = csv.DictReader(fh)
            voice_col = find_col(r.fieldnames, r"input.?mode|modality")
            has_voice = has_voice or bool(voice_col)
            outcome_col = "Outcome" if "Outcome" in r.fieldnames else None
            has_outcome = has_outcome or bool(outcome_col)
            has_starter = has_starter or ("Starter Prompt" in r.fieldnames)
            has_script = has_script or ("Query Script" in r.fieldnames)
            has_words = has_words or ("Response Words" in r.fieldnames)
            for row in r:
                key = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)
                ts = (row.get("Timestamp") or "").strip()
                try:
                    t = datetime.strptime(ts, TS_FORMAT)
                except ValueError:
                    bad += 1
                    continue
                d = t.date(); conv = row.get("Conversation ID") or ""
                if d in skip_days:
                    continue
                first = (row.get("Turn #") or "").strip() == "1"
                c = D[d]; c["turns"] += 1
                if first: sess[d]["all"].add(conv)
                hours[(d, t.hour)]["turns"] += 1
                if first: hour_sess[(d, t.hour)].add(conv)
                # outcome
                urls = URL_RE.findall(row.get("Citations") or "")
                flagged = (row.get("Flagged") or "").strip().lower() == "yes"
                if urls: c["answered"] += 1
                elif flagged: c["flagged"] += 1
                else: c["unanswered"] += 1
                c["citations"] += len(urls)
                fb = (row.get("Feedback") or "").strip().lower()
                if fb == "like": c["likes"] += 1
                elif fb == "dislike":
                    c["dislikes"] += 1
                    if (row.get("Outcome") or "").strip() == "Cited answer": c["dislikes_cited"] += 1
                if first and "Starter Prompt" in row:
                    c["starter" if (row.get("Starter Prompt") or "").strip().lower() == "yes" else "organic"] += 1
                if "Query Script" in row: c["script:" + ((row.get("Query Script") or "").strip() or "None")] += 1
                if outcome_col:
                    o = (row.get("Outcome") or "").strip()
                    c["o:" + o] += 1
                    if (row.get("Partial") or "").strip().lower() == "yes": c["o:partial"] += 1
                    scored = o not in ("Greeting", "Error", "Out of scope")
                    if scored: c["o:scored"] += 1
                    srcg = (row.get("Source") or "").strip().lower()
                    for grp in (srcg if srcg in ("modal", "web") else None, {"new_topic": "new_topic", "user_followup": "user_followup", "suggested_followup": "suggested"}.get((row.get("Question Type") or "").strip())):
                        if not grp: continue
                        if scored: c[f"x:{grp}:scored"] += 1
                        if o == "Cited answer": c[f"x:{grp}:cited"] += 1
                        elif o == "Not found": c[f"x:{grp}:notfound"] += 1
                    rules.add((row.get("Outcome Rules") or "").strip())
                # question type
                qt = (row.get("Question Type") or "").strip()
                if qt == "new_topic": c["new_topic"] += 1
                elif qt == "user_followup": c["user_followup"] += 1
                elif qt == "suggested_followup": c["suggested_followup"] += 1
                # source
                src = (row.get("Source") or "").strip().lower()
                key = "modal" if src == "modal" else "web" if src == "web" else "other"
                c[key + "_turns"] += 1
                if first and key != "other": sess[d][key].add(conv)
                # latency
                try:
                    ms = int(float(row.get("Response Time (ms)") or ""))
                    if ms > 0:
                        lat[d].append(ms)
                        c["lat:" + ("u10" if ms < 10000 else "10_20" if ms < 20000 else "20_30" if ms < 30000 else "o30")] += 1
                except ValueError:
                    pass
                # voice
                if voice_col and "voice" in (row.get(voice_col) or "").lower():
                    c["voice_turns"] += 1
                    if first: sess[d]["voice"].add(conv)
                # per-turn record for the conversation pass
                o_rec = (row.get("Outcome") or "").strip() if outcome_col else ""
                own = next((x.strip() for x in (row.get("Categories") or "").split(",") if x.strip()), "")
                if not own and urls: own = next((url_slug(u) for u in urls if url_slug(u)), "") or ""
                try: tn = int((row.get("Turn #") or "0").strip() or 0)
                except ValueError: tn = 0
                recs.append((conv, tn, t, d, o_rec, own, (row.get("Question Type") or "").strip(),
                             fb == "dislike" and o_rec == "Cited answer", (row.get("Starter Prompt") or "").strip() if has_starter else "",
                             (row.get("Source") or "").strip()))
                for u in urls:
                    nu = norm_url(u)
                    if nu: cites_m[(d.strftime("%Y-%m"), nu)] += 1
                # latency by response length and by citation count (positive response times only)
                if has_words:
                    try: ms3 = int(float(row.get("Response Time (ms)") or ""))
                    except ValueError: ms3 = 0
                    if ms3 > 0:
                        w = int(row.get("Response Words") or 0)
                        wb = "0-50" if w <= 50 else "51-100" if w <= 100 else "101-150" if w <= 150 else "151-200" if w <= 200 else "201-300" if w <= 300 else "301+"
                        nc = len(urls); cb = str(nc) if nc < 6 else "6+"
                        for kind, b in (("words", wb), ("citations", cb)):
                            e = latb[(d, kind, b)]; e["turns"] += 1; e["latsum"] += ms3
                # hour-slot detail for the heat-map toggle
                hv = hours[(d, t.hour)]
                if o_rec == "Not found": hv["notfound"] += 1
                if o_rec == "Error": hv["errors"] += 1
                try:
                    ms2 = int(float(row.get("Response Time (ms)") or ""))
                    if ms2 > 0: hv["timed"] += 1; hv["latsum"] += ms2
                except ValueError:
                    pass
                # categories: one hit per distinct category per turn
                toks = [s.strip() for s in (row.get("Categories") or "").split(",") if s.strip()]
                if CATEGORY_RULE == "tokens":          # old file's rule: column entries only, repeats included, no URL fallback
                    for s in toks: cats[d][s] += 1
                else:
                    if not toks and urls:
                        slugs = [url_slug(u) for u in urls]
                        cat_dropped += sum(1 for x in slugs if x is None)
                        toks = [x for x in slugs if x]
                    for s in set(toks): cats[d][s] += 1
    return D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped, has_outcome, rules, has_starter, has_script, recs, cites_m, latb


def conversation_pass(recs):
    """Group turns by conversation; return the four conversation-level aggregates."""
    from collections import Counter
    convs = defaultdict(list)
    for r in recs: convs[r[0]].append(r)
    fresh = max((r[2] for r in recs), default=None)
    cd = defaultdict(lambda: defaultdict(int))       # start date -> counters
    co = defaultdict(lambda: defaultdict(int))       # (date, attributed category) -> counters
    jm = defaultdict(int)                            # (month, from, to) -> conversations
    sp = defaultdict(lambda: defaultdict(int))       # (month, prompt) -> counters
    stats = {"convs": 0, "mature": 0, "multi_step": 0, "return": 0, "recovered": 0, "nf_total": 0, "fu_1h": 0, "fu_24h": 0, "fu": 0}
    for cid, turns in convs.items():
        turns.sort(key=lambda r: (r[1], r[2]))
        first = turns[0]; start = first[3]; n = len(turns)
        mature = fresh is not None and (fresh - first[2]).total_seconds() >= MATURITY_HOURS * 3600
        stats["convs"] += 1; stats["mature"] += int(mature)
        c = cd[start]; c["started"] += 1
        # attributed category per turn: own, else most frequent own category among the other turns
        owns = Counter(r[5] for r in turns if r[5])
        for r in turns:
            own = r[5]
            if not own:
                others = Counter(x[5] for x in turns if x is not r and x[5])
                own = others.most_common(1)[0][0] if others else ""
                if r[4] == "Not found":
                    stats["nf_total"] += 1
                    if own: stats["recovered"] += 1
            key = (r[3], own or "unknown"); k = co[key]
            k["turns"] += 1
            if r[4]: k["o:" + r[4]] += 1
            if r[4] and r[4] not in ("Greeting", "Error", "Out of scope"): k["scored"] += 1
            if r[1] == 1 and not r[8]:
                k["organic"] += 1
                if r[4]: k["org:" + r[4]] += 1
            if r[7]: k["dislikes_cited"] += 1
        # follow-up gaps (fixture diagnostic)
        for a, b in zip(turns, turns[1:]):
            gap = (b[2] - a[2]).total_seconds(); stats["fu"] += 1
            if gap <= 3600: stats["fu_1h"] += 1
            if gap <= 86400: stats["fu_24h"] += 1
        # starter prompt (first turns), with what followed
        if first[8]:
            p = sp[(start.strftime("%Y-%m"), first[8])]; p["count"] += 1
            if first[4] == "Cited answer": p["cited"] += 1
            if n > 1:
                qt2 = turns[1][6]
                if qt2 == "user_followup": p["typed2"] += 1
                elif qt2 == "suggested_followup": p["suggested2"] += 1
        if not mature:
            continue
        c["mature"] += 1; c["mature_turns"] += n
        c["t" + (str(n) if n < 10 else "10plus")] += 1
        if n > 1:
            span = (turns[-1][2] - first[2]).total_seconds() / 60
            c["span_" + ("0_1" if span <= 1 else "2_5" if span <= 5 else "6_15" if span <= 15 else "16_60" if span <= 60 else "over60")] += 1
        if any(r[6] == "suggested_followup" for r in turns): c["chip_use"] += 1
        if any(r[6] == "user_followup" for r in turns): c["typed_use"] += 1
        fo = OUT_KEY.get(first[4])
        if fo:
            c["f:" + fo] += 1; c["f:" + fo + ":turns"] += n
            if n == 1: c["f:" + fo + ":single"] += 1
        # category journeys: consecutive distinct primary categories over category-bearing turns
        seq = []
        for r in turns:
            if r[5] and (not seq or seq[-1] != r[5]): seq.append(r[5])
        if len(seq) >= 2:
            stats["multi_step"] += 1
            if len(set(seq)) < len(seq): stats["return"] += 1
            m = start.strftime("%Y-%m")
            for a, b in zip(seq, seq[1:]): jm[(m, a, b)] += 1
    return cd, co, jm, sp, stats


def conversation_rows(cd):
    cols = ["Date", "Started", "Mature"] + [f"Turns{i}" for i in range(1, 10)] + ["Turns10plus", "MatureTurns",
            "Span0to1", "Span2to5", "Span6to15", "Span16to60", "SpanOver60", "ChipUse", "TypedUse"]
    for o in OUTCOMES: cols += [f"First{OUT_KEY[o]}", f"First{OUT_KEY[o]}Single", f"First{OUT_KEY[o]}Turns"]
    out = []
    for d in sorted(cd):
        c = cd[d]
        row = [d.isoformat(), c["started"], c["mature"]] + [c["t" + str(i)] for i in range(1, 10)] + [c["t10plus"], c["mature_turns"],
               c["span_0_1"], c["span_2_5"], c["span_6_15"], c["span_16_60"], c["span_over60"], c["chip_use"], c["typed_use"]]
        for o in OUTCOMES:
            k = OUT_KEY[o]; row += [c["f:" + k], c["f:" + k + ":single"], c["f:" + k + ":turns"]]
        out.append(row)
    return cols, out


def category_outcome_rows(co):
    cols = ["Date", "Category", "Turns"] + [OUT_KEY[o] for o in OUTCOMES] + ["Scored", "OrganicFirstTurns", "DislikesOnCited"] + ["Organic" + OUT_KEY[o] for o in OUTCOMES]
    out = []
    for (d, cat) in sorted(co, key=lambda k: (k[0], k[1])):
        k = co[(d, cat)]
        out.append([d.isoformat(), cat, k["turns"]] + [k["o:" + o] for o in OUTCOMES] + [k["scored"], k["organic"], k["dislikes_cited"]] + [k["org:" + o] for o in OUTCOMES])
    return cols, out


def latency_bucket_rows(latb):
    return ["Date", "Kind", "Bucket", "Turns", "LatencySumMs"], [[d.isoformat(), kind, b, e["turns"], e["latsum"]] for (d, kind, b), e in sorted(latb.items())]


def citation_rows(cites_m):
    rows = sorted(cites_m.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1]))
    return ["Month", "URL", "Citations", "Category"], [[m, u, n, url_slug(u) or ""] for (m, u), n in rows]


def journey_rows(jm):
    return ["Month", "From", "To", "Conversations"], [[m, a, b, n] for (m, a, b), n in sorted(jm.items(), key=lambda kv: (kv[0][0], -kv[1]))]


def starter_rows(sp):
    return ["Month", "Prompt", "Count", "Cited", "FollowedByTyped", "FollowedBySuggested"], \
           [[m, p, c["count"], c["cited"], c["typed2"], c["suggested2"]] for (m, p), c in sorted(sp.items(), key=lambda kv: (kv[0][0], -kv[1]["count"]))]


OUTCOME_COLS = [("Cited", "o:Cited answer"), ("NotFound", "o:Not found"), ("Clarification", "o:Clarification"), ("Error", "o:Error"),
                ("OutOfScope", "o:Out of scope"), ("Greeting", "o:Greeting"), ("Uncited", "o:Uncited answer"), ("Partial", "o:partial"), ("Scored", "o:scored")]
CROSS_COLS = [(p + k, f"x:{g}:{m}") for p, g in (("Modal", "modal"), ("Web", "web"), ("NewTopic", "new_topic"), ("UserFollowup", "user_followup"), ("Suggested", "suggested"))
              for k, m in (("Cited", "cited"), ("NotFound", "notfound"), ("Scored", "scored"))]
LAT_COLS = [("LatUnder10s", "lat:u10"), ("Lat10to20s", "lat:10_20"), ("Lat20to30s", "lat:20_30"), ("LatOver30s", "lat:o30")]


SCRIPT_COLS = ["Latin", "Cyrillic", "Arabic", "CJK", "Devanagari", "Other", "None"]


def usage_rows(D, sess, lat, has_voice, has_outcome=False, rules="", has_starter=False, has_script=False):
    cols = ["Date", "Questions", "Sessions", "Answered", "Unanswered", "Flagged", "NewTopic", "UserFollowup", "SuggestedFollowup",
            "ModalTurns", "WebTurns", "OtherTurns", "ModalSessions", "WebSessions", "Citations", "LatencyP50ms", "LatencyP90ms"]
    if has_voice: cols += ["VoiceTurns", "VoiceSessions"]
    cols += ["Likes", "Dislikes", "DislikesOnCited"]
    if has_starter: cols += ["StarterPromptFirstTurns", "OrganicFirstTurns"]
    if has_script: cols += ["Script" + k for k in SCRIPT_COLS]
    cols += ["LatencyP99ms"] + [c for c, _ in LAT_COLS]
    if has_outcome: cols += [c for c, _ in OUTCOME_COLS] + ["OutcomeRules"] + [c for c, _ in CROSS_COLS]
    out = []
    for d in sorted(D):
        c = D[d]; s = sess[d]; L = sorted(lat[d])
        row = [d.isoformat(), c["turns"], len(s["all"]), c["answered"], c["unanswered"], c["flagged"], c["new_topic"], c["user_followup"],
               c["suggested_followup"], c["modal_turns"], c["web_turns"], c["other_turns"], len(s["modal"]), len(s["web"]), c["citations"],
               pct(L, 50), pct(L, 90)]
        if has_voice: row += [c["voice_turns"], len(s["voice"])]
        row += [c["likes"], c["dislikes"], c["dislikes_cited"]]
        if has_starter: row += [c["starter"], c["organic"]]
        if has_script: row += [c["script:" + k] for k in SCRIPT_COLS]
        row += [pct(L, 99)] + [c[k] for _, k in LAT_COLS]
        if has_outcome: row += [c[k] for _, k in OUTCOME_COLS] + [rules] + [c[k] for _, k in CROSS_COLS]
        out.append(row)
    return cols, out


def hours_rows(hours, hour_sess):
    return ["Date", "Hour", "Turns", "Sessions", "NotFound", "Errors", "Timed", "LatencySumMs"], \
           [[d.isoformat(), h, v["turns"], len(hour_sess[(d, h)]), v["notfound"], v["errors"], v["timed"], v["latsum"]] for (d, h), v in sorted(hours.items())]


def categories_rows(cats):
    monthly = defaultdict(lambda: defaultdict(int)); years = set()
    for d, m in cats.items():
        years.add(d.year)
        for s, n in m.items(): monthly[(d.year, d.month)][s] += n
    if len(years) > 1:
        print(f"warning: categories.csv has no year column and the feed spans {sorted(years)}; the dashboard assumes CONFIG.categories_year", file=sys.stderr)
    out = []
    for (y, mo) in sorted(monthly):
        for s, n in sorted(monthly[(y, mo)].items(), key=lambda kv: -kv[1]):
            out.append([CAT_NAME.get(s, s.replace("-", " ").title()), n, MONTHS[mo - 1]])
    daily = [[d.isoformat(), s, n] for d in sorted(cats) for s, n in sorted(cats[d].items(), key=lambda kv: -kv[1])]
    return (["Category", "Citations", "Month"], out), (["Date", "Category", "Citations"], daily)


def write(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def parse_any_date(s):
    s = s.strip().replace("Sept", "Sep")
    for fmt in ("%Y-%m-%d", "%d-%b-%y", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None


def compare(d, ucols, urows, ccols, crows):
    up = os.path.join(d, "usage.csv"); cp = os.path.join(d, "categories.csv")
    if os.path.exists(up):
        ex = {}
        with open(up, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                dt = parse_any_date(r.get("Date") or "")
                if dt: ex[dt] = (int(r["Questions"].replace(",", "")), int(r["Sessions"].replace(",", "")))
        print(f"\nusage.csv: generated vs {up}")
        tq = tg = sq = sg = 0; shown = 0
        for row in urows:
            dt = datetime.fromisoformat(row[0]).date(); e = ex.get(dt)
            if e: tq += e[0]; sq += e[1]
            tg += row[1]; sg += row[2]
            if shown < 40 or (e and (e[0] != row[1] or e[1] != row[2])):
                mark = "" if (e and e[0] == row[1] and e[1] == row[2]) else "  <-- differs" if e else "  (not in existing)"
                print(f"  {row[0]}: feed {row[1]:5d} turns / {row[2]:5d} conv · existing {e[0] if e else '—':>5} / {e[1] if e else '—':>5}{mark}"); shown += 1
        if tq: print(f"  totals on shared days: feed {tg} / {sg}  existing {tq} / {sq}  ({(tg - tq) / tq * 100:+.1f}% turns, {(sg - sq) / sq * 100:+.1f}% conversations)")
    else:
        print(f"\n{up} not found; usage comparison skipped")
    if os.path.exists(cp):
        ex = defaultdict(int)
        with open(cp, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                name = (r.get("Category") or next(iter(r.values())) or "").strip(); mo = (r.get("Month") or "").strip()
                if name and mo: ex[(mo, name)] += int((r.get("Citations") or "0").replace(",", "") or 0)
        gen = defaultdict(int)
        for name, n, mo in crows: gen[(mo, name)] += n
        print(f"\ncategories.csv: generated vs {cp} (months present in the feed only)")
        for mo in [m for m in MONTHS if any(k[0] == m for k in gen)]:
            g = sum(v for k, v in gen.items() if k[0] == mo); e = sum(v for k, v in ex.items() if k[0] == mo)
            print(f"  {mo}: feed {g} · existing {e}" + (f"  ({(g - e) / e * 100:+.1f}%)" if e else "  (not in existing)"))
            for name in sorted({k[1] for k in gen if k[0] == mo} | {k[1] for k in ex if k[0] == mo}):
                gv, ev = gen.get((mo, name), 0), ex.get((mo, name), 0)
                if gv != ev: print(f"      {name:26s} feed {gv:6d}  existing {ev:6d}")
    else:
        print(f"\n{cp} not found; categories comparison skipped")


def main():
    ap = argparse.ArgumentParser(description="Daily aggregates for the AskCI cost dashboard from QA feed exports.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", help="write usage.csv here (usage only)")
    ap.add_argument("--out-dir", help="write usage.csv, usage-hours.csv, categories.csv and categories-daily.csv here")
    ap.add_argument("--compare", metavar="DIR", help="compare with the usage.csv and categories.csv in DIR; write nothing")
    ap.add_argument("--keep-partial", action="store_true", help="keep the last day even when it is the export day (partial by default it is dropped)")
    ap.add_argument("--category-rule", choices=["distinct", "tokens"], default="distinct", help="distinct per turn with URL fallback (default), or every Categories entry incl. repeats and no fallback (old file's rule)")
    a = ap.parse_args()
    global CATEGORY_RULE; CATEGORY_RULE = a.category_rule
    # An export taken on day X contains only part of day X; skip those rows unless asked to keep them.
    export_days = {datetime.strptime(m.group(1), "%Y%m%d").date() for m in (re.search(r"(\d{8})_\d{6}", os.path.basename(f)) for f in a.files) if m}
    skip = frozenset() if (a.keep_partial or not export_days) else frozenset({max(export_days)})  # only the newest export's own day is partial
    D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped, has_outcome, rules, has_starter, has_script, recs, cites_m, latb = aggregate(a.files, skip)
    rules = ", ".join(sorted(r for r in rules if r))
    if skip and any(True for _ in skip): print(f"note: export day(s) {', '.join(str(x) for x in sorted(skip))} skipped as partial (--keep-partial to keep)")
    cd, co, jm, sp, cstats = conversation_pass(recs)
    print(f"conversations: {cstats['convs']} grouped, {cstats['mature']} mature; follow-ups within 1 h {cstats['fu_1h']/max(cstats['fu'],1)*100:.2f}%, within 24 h {cstats['fu_24h']/max(cstats['fu'],1)*100:.2f}%; "
          f"category steps ≥2 in {cstats['multi_step']} conversations, {cstats['return']} with a return; not-found turns recovering a category {cstats['recovered']} of {cstats['nf_total']}")
    if bad: print(f"warning: {bad} rows with unreadable Timestamp skipped", file=sys.stderr)
    if dupes: print(f"note: {dupes} rows repeated across the input files (same conversation and turn) counted once")
    if cat_dropped: print(f"note: {cat_dropped} cited URLs on rows with a blank Categories column were not citizensinformation.ie category pages; not counted")
    if not D: sys.exit("no rows parsed")
    ucols, urows = usage_rows(D, sess, lat, has_voice, has_outcome, rules, has_starter, has_script)
    hcols, hrows = hours_rows(hours, hour_sess)
    (ccols, crows), (dcols, drows) = categories_rows(cats)
    days = sorted(D)
    print(f"{len(days)} days, {days[0]} to {days[-1]}, {sum(r[1] for r in urows)} turns, {sum(r[2] for r in urows)} conversations"
          + (", input-mode column found (voice columns included)" if has_voice else ", no input-mode column (voice columns omitted)")
          + (f", outcome columns included (rules {rules})" if has_outcome else ", no Outcome column (redact first for the outcome taxonomy)"))
    if a.compare:
        compare(a.compare, ucols, urows, ccols, crows); return
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        write(os.path.join(a.out_dir, "usage.csv"), ucols, urows)
        write(os.path.join(a.out_dir, "usage-hours.csv"), hcols, hrows)
        write(os.path.join(a.out_dir, "categories.csv"), ccols, crows)
        write(os.path.join(a.out_dir, "categories-daily.csv"), dcols, drows)
        write(os.path.join(a.out_dir, "conversations-daily.csv"), *conversation_rows(cd))
        write(os.path.join(a.out_dir, "category-outcomes-daily.csv"), *category_outcome_rows(co))
        write(os.path.join(a.out_dir, "citations-monthly.csv"), *citation_rows(cites_m))
        write(os.path.join(a.out_dir, "journeys-monthly.csv"), *journey_rows(jm))
        write(os.path.join(a.out_dir, "starter-prompts-monthly.csv"), *starter_rows(sp))
        if latb: write(os.path.join(a.out_dir, "latency-buckets-daily.csv"), *latency_bucket_rows(latb))
    elif a.out:
        write(a.out, ucols, urows)
    else:
        w = csv.writer(sys.stdout); w.writerow(ucols); w.writerows(urows)


if __name__ == "__main__":
    main()
