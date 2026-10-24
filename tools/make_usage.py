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
                         AnswerWords, AnswerWordsTurns, CitedWords, CitedWordsTurns
                                                                   answer length: words summed over turns with a word count,
                                                                   all answers and cited answers (needs Response Words)
                         VoiceTurns, VoiceSessions                 only when the export has an input-mode column
  usage-hours.csv      Date, Hour, Turns, Sessions   (hour of day, Irish time)
  script-outcomes-daily.csv  Date, Script, Turns, Scored, Cited, NotFound, Clarification — outcome by the alphabet
                       the question starts in (needs Query Script and Outcome); a script, not a language
  categories.csv       Category, Citations, Month    (current dashboard contract; display names)
  categories-daily.csv Date, Category, Citations     (slugs, by day)
  conversations-daily.csv   by conversation start day: Started, Mature, Turns1..Turns9, Turns10plus, MatureTurns,
                            Span0to1, Span2to5, Span6to15, Span16to60, SpanOver60 (mature multi-turn, minutes),
                            ChipUse, TypedUse (mature conversations with at least one such turn), and per first
                            outcome First<Outcome>, First<Outcome>Single, First<Outcome>Turns (mature), then (mature):
                            ReachedCited (at least one cited answer); per setback answer P in NF (not found),
                            Clar (clarification), Err (error): PTurns, PLaterCited (a later turn in the same
                            conversation got a cited answer, not necessarily to the same question), PEnded (it was
                            the last turn), PNextTyped/PNextChip/PNextNew/PNextOther (type of the next question);
                            WithTopic, MultiTopic (2+ topics in sequence), TopicReturn (a topic comes back);
                            TypedTopicBoth, TypedTopicSwitched, ChipTopicBoth, ChipTopicSwitched, NewTopicBoth,
                            NewTopicSwitched: follow-up turns where this turn and the one before both carry a
                            topic, and how many changed topic, by question type (brief §53 step 6);
                            ClarThenClar: clarification answers followed by another clarification (brief §63);
                            Gap0to1..GapOver60 (minutes between consecutive questions)
  category-outcomes-daily.csv  Date, Category (attributed slug or unknown), Turns, Cited, NotFound, Clarification,
                            Error, OutOfScope, Greeting, Uncited, Scored, OrganicFirstTurns, DislikesOnCited
  citations-monthly.csv     Month, URL (normalised), Citations, Category (known slug or blank)
  journeys-monthly.csv      Month, From, To, Conversations (consecutive category steps, mature conversations)
  starter-prompts-monthly.csv  Month, Prompt, Count, Cited, FollowedByTyped, FollowedBySuggested
  outcome-rules-daily.csv   Date, Rule, Turns: the id of the phrase that decided each outcome (needs feeds redacted
                            with Outcome Rule, brief §53)
  pages-cited.csv           URL, FirstCited, LastCited, Citations, Answers, Partial, Dislikes, LastMod,
                            FirstCitedAfterLastMod, AnswersAfterLastMod (one row per cited page, all data; brief §62)
  question-intent-daily.csv Date, Intent, Chip (0 typed, 1 starter prompt, 2 suggested follow-up), Turns, outcomes, Partial,
                            Year, Euro, YesNo, Situation, WithTopic, SituationCited, SituationNotFound, SituationPartial,
                            NamedCited, NamedNotFound, NamedClarification (brief §66, §71)
  asked-pages-monthly.csv   Month, URL, Category, Asked, CitedSame, CitedSameCategory, CitedOther, NotFound, Clarification,
                            Other, CitedUnderHub, Hub: the page a typed question named and what the answer did; pages
                            asked under 5 times a month left out (brief §66, §71)
  answer-signposts-monthly.csv     Month, Org, Category, Turns, outcomes, Partial: organisations the answer names
                                   (redact_feed.py ORGS; (any) / (external) / (none)), by the turn's category and (all) (brief §75)
  answer-templates-daily.csv       Date, Template, Turns, outcomes, Partial: the bot's fixed-wording templates
                                   (redact_feed.py TEMPLATES) per day; "(none)" = answers carrying none (brief §75)
  question-topics-monthly.csv      Month, Category, Topic, Turns, outcomes, Partial: the lexicon's topic layer on typed
                                   questions; rows under 5 turns left out (brief §75)
  question-categories-monthly.csv  Month, Category, Source, Turns, outcomes, Partial: typed questions by category and by
                                   how the turn entered it (cited / page / topic; "(none)" / none is the residue); the sum
                                   over sources is the broad cut (brief §75)
  question-intent-category-monthly.csv  Month, Category, Intent, Turns, outcomes, Partial: typed questions, broad cut;
                                   rows under 5 turns left out (brief §75)
  question-topics-daily.csv Date, Category, Turns, outcomes, Partial: the category the question named, for turns whose
                            answer carried no topic (brief §66)
  citations-intent-monthly.csv Month, URL, Intent, Answers, Partial: the question's intent per cited page, typed questions
                            (brief §73); rows under 5 answers left out
  asked-pages-weekly.csv    Week, URL, Asked, CitedIt, NotFound, Partial: pages named 30+ times in a month, by week (§73)
  intent-journeys-monthly.csv  Month, From, To, Turns: consecutive turns' intents in mature conversations, END after the
                            last (brief §69)
  setback-intents-monthly.csv  Month, Setback (NF | Clar), Intent, Turns, Ended, SameIntentNext, OtherIntentNext (brief §69)
  safety-daily.csv          Date, Flag, Turns, Cited, NotFound, Clarification, Error, OutOfScope, Greeting, Uncited: turns
                            flagged by redact_feed.py (identifiers typed in, injection phrasings, off-topic and
                            crisis themes) and their outcomes (brief §65)
  answer-style-daily.csv    Date, Outcome, Turns, Words, Lines, Hedges, Apologies, Signposts, Questions, Links, Openers,
                            Invitations, Absolutes, Emphasis, Nested, External, Freshness, Signoff (style 2026.10.23-2),
                            WithLines..WithLinks: the wording fingerprint summed per day and outcome
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
    python3 tools/make_usage.py qa-feed-redacted_*.csv --out-dir .          # write all the aggregate files
    python3 tools/make_usage.py qa-feed-redacted_*.csv --compare .          # compare with existing files, write nothing
    python3 tools/make_usage.py qa-feed_*.csv -o usage.csv                  # usage.csv only (old behaviour)
"""
import argparse, csv, os, re, sys
from collections import defaultdict
from datetime import datetime, date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:   # hub pages from the lexicon (brief §71): a citation of a page beneath a named hub counts as a hit
    import json as _json
    _lex = _json.load(open(os.path.join(REPO, "question-lexicon.json"), encoding="utf-8"))
    HUBS = {e["path"] for e in _lex["phrases"].values() if e.get("hub") and e.get("url")}
    TOPIC_CAT = {t: c for c, tops in (_lex.get("topics") or {}).items() for t in tops}   # topic -> its category (brief §75)
except (OSError, ValueError, KeyError):
    HUBS = set(); TOPIC_CAT = {}

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
    cites_x = defaultdict(lambda: defaultdict(int))  # (month, url) -> answers citing it, partial answers, dislikes (brief §62)
    pages = {}                                       # url -> first/last citation date and totals (brief §62)
    latb = defaultdict(lambda: defaultdict(int))     # (date, kind, bucket) -> turns, latsum
    has_words = False
    rulesd = defaultdict(int)                        # (date, outcome rule id) -> turns (brief §53)
    style = defaultdict(lambda: defaultdict(int))    # (date, outcome) -> wording fingerprint sums
    tmpl = defaultdict(lambda: defaultdict(int))     # (date, template id or "(none)") -> answers, outcomes (brief §75)
    orgs = defaultdict(lambda: defaultdict(int))     # (month, org id | (any) | (external) | (none), category | (all)) -> answers, outcomes (brief §75)
    safety = defaultdict(lambda: defaultdict(int))   # (date, flag) -> turns and their outcomes (brief §65)
    intent = defaultdict(lambda: defaultdict(int))   # (date, intent, chip) -> turns, outcomes, form flags (brief §66)
    asked = defaultdict(lambda: defaultdict(int))    # (month, page asked about) -> what the answer did (brief §66)
    qtopic = defaultdict(lambda: defaultdict(int))   # (date, question category) -> turns whose answer carried no topic (brief §66)
    cint = defaultdict(lambda: defaultdict(int))     # (month, cited page, question intent) -> answers, partial (brief §73)
    askw = defaultdict(lambda: defaultdict(int))     # (week, page named by a typed question) -> asked, cited it, not found, partial (brief §73)
    qtop = defaultdict(lambda: defaultdict(int))     # (month, category, topic) -> typed turns, outcomes, partial (brief §75)
    qcat = defaultdict(lambda: defaultdict(int))     # (month, category, source) -> typed turns, outcomes, partial: the broad cut (brief §75)
    qic = defaultdict(lambda: defaultdict(int))      # (month, category, intent) -> typed turns, outcomes, partial (brief §75)
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
                    c["starter" if (row.get("Starter Prompt") or "").strip() else "organic"] += 1   # holds the chip text, blank when organic
                    if outcome_col and (row.get("Outcome") or "").strip() == "Error":                 # empty answers on first turns, chip and typed (brief §64)
                        c["starter_err" if (row.get("Starter Prompt") or "").strip() else "organic_err"] += 1
                if "Query Script" in row:
                    sc = (row.get("Query Script") or "").strip() or "None"
                    c["script:" + sc] += 1
                    if outcome_col:   # outcome by script: do questions in other alphabets get cited answers as often?
                        o2 = (row.get("Outcome") or "").strip()
                        c[f"so:{sc}:turns"] += 1
                        if o2 not in ("Greeting", "Error", "Out of scope"): c[f"so:{sc}:scored"] += 1
                        if o2 == "Cited answer": c[f"so:{sc}:cited"] += 1
                        elif o2 == "Not found": c[f"so:{sc}:notfound"] += 1
                        elif o2 == "Clarification": c[f"so:{sc}:clar"] += 1
                # answer length (words), all answers and cited answers
                try: wd = int(row.get("Response Words") or 0)
                except ValueError: wd = 0
                if wd > 0:
                    c["words"] += wd; c["words_n"] += 1
                    if (row.get("Outcome") or "").strip() == "Cited answer": c["cwords"] += wd; c["cwords_n"] += 1
                if "Safety Version" in row and (row.get("Safety Version") or "").strip():
                    o4 = (row.get("Outcome") or "").strip() if outcome_col else ""
                    flags = [k[6:] for k in SAFETY_FLAGS if (row.get(k) or "").strip() == "1"]
                    if (row.get("Query Theme") or "").strip(): flags.append("Theme " + row["Query Theme"].strip())
                    if any(f in ("PPS", "Phone", "Email", "IBAN", "Card") for f in flags): flags.append("Any identifier")
                    for f in flags:
                        e4 = safety[(d, f)]; e4["Turns"] += 1
                        if o4: e4["o:" + o4] += 1
                if outcome_col and (row.get("Outcome Rule") or "").strip():
                    o3 = (row.get("Outcome") or "").strip()
                    rulesd[(d, row["Outcome Rule"].strip())] += 1
                    e = style[(d, o3)]; e["Turns"] += 1
                    if "Answer Templates" in row:   # the bot's fixed wording (brief §75): every template the answer carries, else "(none)"
                        for tid in ((row.get("Answer Templates") or "").split(";") if (row.get("Answer Templates") or "").strip() else ["(none)"]):
                            e9 = tmpl[(d, tid)]; e9["Turns"] += 1; e9["o:" + o3] += 1
                            if (row.get("Partial") or "").strip().lower() == "yes": e9["o:partial"] += 1
                    try: e["Words"] += int(row.get("Response Words") or 0)
                    except ValueError: pass
                    for k in STYLE_COLS:
                        try: v = int(row.get("Answer " + k) or 0)
                        except ValueError: v = 0
                        e[k] += v; e["With" + k] += v > 0
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
                try: ms_rec = int(float(row.get("Response Time (ms)") or 0))
                except ValueError: ms_rec = 0
                recs.append((conv, tn, t, d, o_rec, own, (row.get("Question Type") or "").strip(),
                             fb == "dislike" and o_rec == "Cited answer", (row.get("Starter Prompt") or "").strip() if has_starter else "",
                             (row.get("Source") or "").strip(),
                             (row.get("Partial") or "").strip().lower() == "yes", int(row.get("Response Words") or 0) if str(row.get("Response Words") or "").isdigit() else 0, ms_rec,
                             (row.get("Query Intent") or "").strip()))
                nus = []
                for u in urls:
                    nu = norm_url(u)
                    if nu:
                        cites_m[(d.strftime("%Y-%m"), nu)] += 1
                        if nu not in nus: nus.append(nu)
                is_partial = (row.get("Partial") or "").strip().lower() == "yes"
                for nu in nus:   # once per answer and page
                    x = cites_x[(d.strftime("%Y-%m"), nu)]; x["answers"] += 1
                    if is_partial: x["partial"] += 1
                    if fb == "dislike": x["dislikes"] += 1
                    pg = pages.get(nu)
                    if pg is None: pg = pages[nu] = {"first": d, "last": d, "cites": 0, "answers": 0, "partial": 0, "dislikes": 0, "days": defaultdict(int)}
                    pg["first"] = min(pg["first"], d); pg["last"] = max(pg["last"], d); pg["answers"] += 1; pg["days"][d] += 1
                    if is_partial: pg["partial"] += 1
                    if fb == "dislike": pg["dislikes"] += 1
                for u in urls:
                    nu = norm_url(u)
                    if nu: pages[nu]["cites"] += 1
                # what people ask (brief §66): intent and form from the question, the page it names, and what the answer did
                if (row.get("Intent Version") or "").strip():
                    qi = (row.get("Query Intent") or "other").strip() or "other"; qf = set((row.get("Query Form") or "").split(";")) - {""}
                    # 0 = typed by the person, 1 = a starter prompt, 2 = a model-written suggested follow-up (its text follows the
                    # prompt's own pattern, so it carries an intent by construction and is never counted as typed; brief §71)
                    chip = 1 if (row.get("Starter Prompt") or "").strip() else 2 if (row.get("Question Type") or "").strip() == "suggested_followup" else 0
                    e5 = intent[(d, qi, chip)]; e5["Turns"] += 1
                    if o_rec: e5["o:" + o_rec] += 1
                    if (row.get("Partial") or "").strip().lower() == "yes": e5["o:partial"] += 1
                    for fl in ("year", "euro", "yesno", "situation"): e5["f:" + fl] += fl in qf
                    if "situation" in qf:   # outcomes of personal-situation questions, for the difference in differences (brief §66)
                        if o_rec == "Cited answer": e5["s:cited"] += 1
                        if o_rec == "Not found": e5["s:notfound"] += 1
                        if (row.get("Partial") or "").strip().lower() == "yes": e5["s:partial"] += 1
                    qp = (row.get("Query Page") or "").strip(); qc = (row.get("Query Category") or "").strip()
                    src = (row.get("Category Source") or "").strip()
                    named = qc and src != "topic"   # "named a scheme" keeps its meaning: a page or section the lexicon knows, not a topic (brief §75)
                    if named:
                        e5["WithTopic"] += 1
                        if o_rec == "Cited answer": e5["n:cited"] += 1
                        if o_rec == "Not found": e5["n:notfound"] += 1
                        if o_rec == "Clarification": e5["n:clarification"] += 1
                    if "Answer Orgs" in row:   # organisations the answer signposts to (brief §75): every answer, by the turn's category
                        ids = [x for x in (row.get("Answer Orgs") or "").split(";") if x]
                        keys = ids + (["(any)"] if ids else ["(none)"]) + (["(external)"] if any(not x.startswith("cic.") for x in ids) else [])
                        ocat = own or qc or "(none)"; mo9 = d.strftime("%Y-%m")
                        for oid in keys:
                            for c9 in (ocat, "(all)"):
                                e9 = orgs[(mo9, oid, c9)]; e9["Turns"] += 1
                                if o_rec: e9["o:" + o_rec] += 1
                                if is_partial: e9["o:partial"] += 1
                    if chip == 0:   # the broad category cut and the topic layer (brief §75): typed questions only
                        mo = d.strftime("%Y-%m"); qt = (row.get("Query Topic") or "").strip()
                        # a turn is in a category when the answer cited it (source cited), the question named a page in it
                        # (page) or the question's topic gives it (topic); the question side names the source when both agree
                        cats7 = {}
                        if own: cats7[own] = "cited"
                        if qc: cats7[qc] = src or "page"
                        if not cats7: cats7["(none)"] = "none"   # the residue: no page cited, none named, no topic
                        for c7, s7 in cats7.items():
                            for e7 in (qcat[(mo, c7, s7)], qic[(mo, c7, qi)]):
                                e7["Turns"] += 1
                                if o_rec: e7["o:" + o_rec] += 1
                                if is_partial: e7["o:partial"] += 1
                        if qt:
                            e9 = qtop[(mo, TOPIC_CAT.get(qt, qc), qt)]; e9["Turns"] += 1
                            if o_rec: e9["o:" + o_rec] += 1
                            if is_partial: e9["o:partial"] += 1
                    if chip == 0 and o_rec == "Cited answer":   # the question's intent per cited page (brief §73): which kind of question the page's partials come from
                        for nu in nus:
                            x7 = cint[(d.strftime("%Y-%m"), nu, qi)]; x7["answers"] += 1
                            if is_partial: x7["partial"] += 1
                    if qp and chip == 0:   # pages people name: typed questions only
                        a5 = asked[(d.strftime("%Y-%m"), qp)]; a5["Asked"] += 1; a5["_cat"] = qc
                        qpn = norm_url(qp); hubp = qpn.split("/en/", 1)[1] if "/en/" in qpn else ""
                        wk = (d - timedelta(days=d.weekday())).isoformat(); w7 = askw[(wk, qp)]; w7["asked"] += 1
                        if o_rec == "Cited answer":
                            hit7 = qpn in nus or (hubp and hubp in HUBS and any(("/en/" + hubp + "/") in u for u in nus))
                            if hit7: w7["hit"] += 1
                            if is_partial: w7["partial"] += 1
                        elif o_rec == "Not found": w7["notfound"] += 1
                        if o_rec == "Cited answer":
                            if qpn in nus: a5["CitedSame"] += 1
                            elif hubp and hubp in HUBS and any(("/en/" + hubp + "/") in u for u in nus): a5["CitedUnderHub"] += 1
                            elif any(url_slug(u) == qc for u in nus): a5["CitedSameCategory"] += 1
                            else: a5["CitedOther"] += 1
                        elif o_rec == "Not found": a5["NotFound"] += 1
                        elif o_rec == "Clarification": a5["Clarification"] += 1
                        else: a5["Other"] += 1
                    if named and not own:   # the answer carried no topic; the question named a scheme
                        e6 = qtopic[(d, qc)]; e6["Turns"] += 1
                        if o_rec: e6["o:" + o_rec] += 1
                        if (row.get("Partial") or "").strip().lower() == "yes": e6["o:partial"] += 1
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
    return D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped, has_outcome, rules, has_starter, has_script, recs, (cites_m, cites_x, pages), latb, rulesd, (style, safety, intent, asked, qtopic, cint, askw, qtop, qcat, qic, tmpl, orgs)


STYLE_COLS = ["Lines", "Hedges", "Apologies", "Signposts", "Questions", "Links", "Openers", "Invitations", "Absolutes", "Emphasis", "Nested", "External", "Freshness", "Signoff"]
SAFETY_FLAGS = ["Query PPS", "Query Phone", "Query Email", "Query IBAN", "Query Card", "Query Injection"]


OUT7 = [k for k, _ in [("Cited", "o:Cited answer"), ("NotFound", "o:Not found"), ("Clarification", "o:Clarification"), ("Error", "o:Error"), ("OutOfScope", "o:Out of scope"), ("Greeting", "o:Greeting"), ("Uncited", "o:Uncited answer")]]
OUT7_SRC = ["o:Cited answer", "o:Not found", "o:Clarification", "o:Error", "o:Out of scope", "o:Greeting", "o:Uncited answer"]


def intent_rows(intent):
    """question-intent-daily.csv: per day, intent and whether the turn was a chip: turns, outcomes, partial, the form
    flags (a year, a euro amount, a yes/no form, a personal situation) and turns whose question named a scheme (§66)."""
    cols = ["Date", "Intent", "Chip", "Turns"] + OUT7 + ["Partial", "Year", "Euro", "YesNo", "Situation", "WithTopic", "SituationCited", "SituationNotFound", "SituationPartial", "NamedCited", "NamedNotFound", "NamedClarification"]
    return cols, [[d.isoformat(), i, c, e["Turns"]] + [e[k] for k in OUT7_SRC] + [e["o:partial"], e["f:year"], e["f:euro"], e["f:yesno"], e["f:situation"], e["WithTopic"], e["s:cited"], e["s:notfound"], e["s:partial"], e["n:cited"], e["n:notfound"], e["n:clarification"]]
                  for (d, i, c), e in sorted(intent.items())]


def asked_rows(asked, min_asked=5):
    """asked-pages-monthly.csv: per month and page the question named: how often, and what the answer did: cited that
    page, cited another page in the same category, cited a different category, not found, clarification, other.
    Pages named fewer than min_asked times in a month are left out (small-sample rule, brief §66)."""
    cols = ["Month", "URL", "Category", "Asked", "CitedSame", "CitedSameCategory", "CitedOther", "NotFound", "Clarification", "Other", "CitedUnderHub", "Hub"]
    rows = [[m, u, e["_cat"], e["Asked"], e["CitedSame"], e["CitedSameCategory"], e["CitedOther"], e["NotFound"], e["Clarification"], e["Other"], e["CitedUnderHub"], 1 if (u.split("/en/", 1)[1] if "/en/" in u else "") in HUBS else 0]
            for (m, u), e in asked.items() if e["Asked"] >= min_asked]
    return cols, sorted(rows, key=lambda r: (r[0], -r[3], r[1]))


def intent_journey_rows(ij):
    """intent-journeys-monthly.csv: consecutive turns' intents inside mature conversations, by the month the
    conversation started; To = END after the last turn (brief §69)."""
    return ["Month", "From", "To", "Turns"], [[m, a, b, n] for (m, a, b), n in sorted(ij.items(), key=lambda kv: (kv[0][0], -kv[1]))]


def setback_intent_rows(sb):
    """setback-intents-monthly.csv: after a not-found (NF) or clarification (Clar) answer, by the question's intent:
    the answers, how many were the last turn, how many were followed by the same intent again (a retry) or another
    intent (brief §69)."""
    return ["Month", "Setback", "Intent", "Turns", "Ended", "SameIntentNext", "OtherIntentNext"], \
           [[m, p, i, e["turns"], e["ended"], e["same"], e["other"]] for (m, p, i), e in sorted(sb.items())]


def cint_rows(cint, min_answers=5):
    """citations-intent-monthly.csv: per month, cited page and the question's intent (typed questions): answers citing
    the page and how many also said something was missing. Rows under min_answers left out (brief §73)."""
    cols = ["Month", "URL", "Intent", "Answers", "Partial"]
    return cols, [[m, u, i, e["answers"], e["partial"]] for (m, u, i), e in sorted(cint.items()) if e["answers"] >= min_answers]


def _monthly_rows(coll, key_names, min_turns):
    cols = ["Month"] + key_names + ["Turns"] + OUT7 + ["Partial"]
    return cols, [[m, *ks, e["Turns"]] + [e[k] for k in OUT7_SRC] + [e["o:partial"]] for (m, *ks), e in sorted(coll.items()) if e["Turns"] >= min_turns]


def qtop_rows(qtop, min_turns=5):
    """question-topics-monthly.csv: per month, category and topic from the lexicon's topic layer (typed questions):
    turns, outcomes, partial. Rows under min_turns left out (brief §75)."""
    return _monthly_rows(qtop, ["Category", "Topic"], min_turns)


def qcat_rows(qcat):
    """question-categories-monthly.csv: per month and category, by how the turn entered the category (Source: cited =
    the answer cited a page in it; page = the question named a page in it; topic = the question's topic gives it), typed
    questions: turns, outcomes, partial. The sum over sources is the broad cut the category view uses (brief §75)."""
    return _monthly_rows(qcat, ["Category", "Source"], 1)


def qic_rows(qic, min_turns=5):
    """question-intent-category-monthly.csv: per month, category (broad cut) and intent, typed questions: turns, outcomes,
    partial. Rows under min_turns left out (brief §75)."""
    return _monthly_rows(qic, ["Category", "Intent"], min_turns)


def askw_rows(askw, asked, min_month=30):
    """asked-pages-weekly.csv: per ISO week (Monday) and page, for pages named 30+ times in some month by typed
    questions: asked, answers that cited it (or a page beneath a named hub), not found, and partial (brief §73)."""
    keep = {u for (m, u), e in asked.items() if e["Asked"] >= min_month}
    cols = ["Week", "URL", "Asked", "CitedIt", "NotFound", "Partial"]
    return cols, [[w, u, e["asked"], e["hit"], e["notfound"], e["partial"]] for (w, u), e in sorted(askw.items()) if u in keep]


def qtopic_rows(qtopic):
    """question-topics-daily.csv: per day and category named in the question, for turns whose answer carried no topic
    (the 'unknown' rows of category-outcomes-daily.csv): turns, outcomes and partial (brief §66)."""
    cols = ["Date", "Category", "Turns"] + OUT7 + ["Partial"]
    return cols, [[d.isoformat(), c, e["Turns"]] + [e[k] for k in OUT7_SRC] + [e["o:partial"]] for (d, c), e in sorted(qtopic.items())]


def safety_rows(safety):
    """safety-daily.csv: per day and flag (PPS, Phone, Email, IBAN, Card, Any identifier, Injection, Theme <name>), the
    flagged turns and their outcomes (brief §65). Counts only; the flags are set by redact_feed.py before the text is
    dropped."""
    cols = ["Date", "Flag", "Turns"] + [k for k, _ in OUTCOME_COLS if k not in ("Partial", "Scored")]
    return cols, [[d.isoformat(), f, e["Turns"]] + [e[src] for k, src in OUTCOME_COLS if k not in ("Partial", "Scored")] for (d, f), e in sorted(safety.items())]


def rule_rows(rulesd):
    """outcome-rules-daily.csv: which phrase decided each outcome, per day (no text)."""
    return ["Date", "Rule", "Turns"], [[d.isoformat(), r, n] for (d, r), n in sorted(rulesd.items())]


def tmpl_rows(tmpl):
    """answer-templates-daily.csv: per day and fixed-wording template id (redact_feed.py TEMPLATES; "(none)" for answers
    carrying none): answers and their outcomes. A template that starts or stops on a date with no model event is the
    trace of a prompt change (brief §75)."""
    cols = ["Date", "Template", "Turns"] + OUT7 + ["Partial"]
    return cols, [[d.isoformat(), t, e["Turns"]] + [e[k] for k in OUT7_SRC] + [e["o:partial"]] for (d, t), e in sorted(tmpl.items())]


def orgs_rows(orgs, min_turns=5):
    """answer-signposts-monthly.csv: per month, organisation named in the answer (redact_feed.py ORGS; "(any)" = named
    one or more, "(external)" = named one outside Citizens Information's own channels, "(none)" = named none) and the
    turn's category ("(all)" = every category): answers and their outcomes. Category rows under min_turns left out;
    "(all)" rows always kept (brief §75)."""
    cols = ["Month", "Org", "Category", "Turns"] + OUT7 + ["Partial"]
    return cols, [[m, o, c, e["Turns"]] + [e[k] for k in OUT7_SRC] + [e["o:partial"]] for (m, o, c), e in sorted(orgs.items()) if c == "(all)" or e["Turns"] >= min_turns]


def style_rows(style):
    """answer-style-daily.csv: the wording fingerprint summed per day and outcome; divide by Turns for a mean,
    With<x> by Turns for the share of answers with at least one."""
    cols = ["Date", "Outcome", "Turns", "Words"] + STYLE_COLS + ["With" + k for k in STYLE_COLS]
    return cols, [[d.isoformat(), o] + [e[k] for k in cols[2:]] for (d, o), e in sorted(style.items())]


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
    ij = defaultdict(int)                            # (month, from intent, to intent or END) -> turns (brief §69)
    sb = defaultdict(lambda: defaultdict(int))       # (month, setback outcome, intent) -> what came next (brief §69)
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
            if first[4] == "Cited answer" and first[10]: p["partial"] += 1
            if first[4] == "Not found": p["notfound"] += 1
            if first[4] == "Clarification": p["clarification"] += 1
            if first[7]: p["disliked"] += 1
            p["words"] += first[11]; p["ms"] += first[12]
            if first[12] > 0: p["timed"] += 1
            if mature:
                p["mature"] += 1
                if n == 1: p["ended"] += 1
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
        # what happened after a not-found, clarification or error answer (per answer, not per conversation;
        # a later cited answer may be to a different question, so this never claims the setback was resolved)
        if any(r[4] == "Cited answer" for r in turns): c["reached_cited"] += 1
        for i, r in enumerate(turns):
            p = SETBACK.get(r[4])
            if not p: continue
            c[p + ":turns"] += 1
            if i == n - 1:
                c[p + ":ended"] += 1
                continue
            if r[4] == "Clarification" and turns[i + 1][4] == "Clarification": c["clar_loop"] += 1   # asked to clarify twice running (brief §63)
            if any(x[4] == "Cited answer" for x in turns[i + 1:]): c[p + ":later_cited"] += 1
            c[p + ":next:" + NEXT_TYPE.get(turns[i + 1][6], "other")] += 1
        # pace: minutes between consecutive questions
        for a, b in zip(turns, turns[1:]):
            gap = (b[2] - a[2]).total_seconds() / 60
            c["gap_" + ("0_1" if gap <= 1 else "2_5" if gap <= 5 else "6_15" if gap <= 15 else "16_60" if gap <= 60 else "over60")] += 1
        # intent journeys (brief §69): consecutive turns' intents inside mature conversations, END after the last; and
        # after a not-found or clarification answer, by the question's intent: ended, asked again with the same intent,
        # or moved to another intent
        if any(r[13] for r in turns):
            m = start.strftime("%Y-%m")
            for a, b in zip(turns, turns[1:]): ij[(m, a[13] or "other", b[13] or "other")] += 1
            ij[(m, turns[-1][13] or "other", "END")] += 1
            for i, r in enumerate(turns):
                p = SETBACK.get(r[4])
                if p not in ("NF", "Clar"): continue
                e = sb[(m, p, r[13] or "other")]; e["turns"] += 1
                if i == n - 1: e["ended"] += 1
                elif (turns[i + 1][13] or "other") == (r[13] or "other"): e["same"] += 1
                else: e["other"] += 1
        # category journeys: consecutive distinct primary categories over category-bearing turns
        seq = []
        for r in turns:
            if r[5] and (not seq or seq[-1] != r[5]): seq.append(r[5])
        if seq: c["with_topic"] += 1
        if len(seq) >= 2: c["multi_topic"] += 1
        if len(set(seq)) < len(seq): c["topic_return"] += 1
        # topic drift between consecutive turns, by the question type of the later turn. A topic comes from the
        # cited page, so this is measured only where both turns carry one: mostly two cited answers in a row.
        for a, b in zip(turns, turns[1:]):
            t = NEXT_TYPE.get(b[6])
            if t and a[5] and b[5]:
                c["drift:" + t + ":both"] += 1
                if a[5] != b[5]: c["drift:" + t + ":switched"] += 1
        if len(seq) >= 2:
            stats["multi_step"] += 1
            if len(set(seq)) < len(seq): stats["return"] += 1
            m = start.strftime("%Y-%m")
            for a, b in zip(seq, seq[1:]): jm[(m, a, b)] += 1
    stats["ij"], stats["sb"] = ij, sb
    return cd, co, jm, sp, stats


SETBACK = {"Not found": "NF", "Clarification": "Clar", "Error": "Err"}
NEXT_TYPE = {"user_followup": "Typed", "suggested_followup": "Chip", "new_topic": "New"}
GAP_COLS = [("Gap0to1", "gap_0_1"), ("Gap2to5", "gap_2_5"), ("Gap6to15", "gap_6_15"), ("Gap16to60", "gap_16_60"), ("GapOver60", "gap_over60")]


def conversation_rows(cd):
    cols = ["Date", "Started", "Mature"] + [f"Turns{i}" for i in range(1, 10)] + ["Turns10plus", "MatureTurns",
            "Span0to1", "Span2to5", "Span6to15", "Span16to60", "SpanOver60", "ChipUse", "TypedUse"]
    for o in OUTCOMES: cols += [f"First{OUT_KEY[o]}", f"First{OUT_KEY[o]}Single", f"First{OUT_KEY[o]}Turns"]
    cols += ["ReachedCited"]
    for p in SETBACK.values(): cols += [f"{p}Turns", f"{p}LaterCited", f"{p}Ended", f"{p}NextTyped", f"{p}NextChip", f"{p}NextNew", f"{p}NextOther"]
    cols += ["WithTopic", "MultiTopic", "TopicReturn"] + [k for k, _ in GAP_COLS]
    cols += [f"{t}Topic{k}" for t in ("Typed", "Chip", "New") for k in ("Both", "Switched")] + ["ClarThenClar"]
    out = []
    for d in sorted(cd):
        c = cd[d]
        row = [d.isoformat(), c["started"], c["mature"]] + [c["t" + str(i)] for i in range(1, 10)] + [c["t10plus"], c["mature_turns"],
               c["span_0_1"], c["span_2_5"], c["span_6_15"], c["span_16_60"], c["span_over60"], c["chip_use"], c["typed_use"]]
        for o in OUTCOMES:
            k = OUT_KEY[o]; row += [c["f:" + k], c["f:" + k + ":single"], c["f:" + k + ":turns"]]
        row += [c["reached_cited"]]
        for p in SETBACK.values():
            row += [c[p + ":turns"], c[p + ":later_cited"], c[p + ":ended"]] + [c[p + ":next:" + t] for t in ("Typed", "Chip", "New", "other")]
        row += [c["with_topic"], c["multi_topic"], c["topic_return"]] + [c[k] for _, k in GAP_COLS]
        row += [c[f"drift:{t}:{k}"] for t in ("Typed", "Chip", "New") for k in ("both", "switched")] + [c["clar_loop"]]
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


def citation_rows(cites_m, cites_x):
    """citations-monthly.csv: citations per page and month; Answers = answers citing the page (once each), Partial = of
    those, answers that also say something is missing; Dislikes = disliked answers citing it (brief §62)."""
    rows = sorted(cites_m.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1]))
    return ["Month", "URL", "Citations", "Category", "Answers", "Partial", "Dislikes"], \
           [[m, u, n, url_slug(u) or "", cites_x[(m, u)]["answers"], cites_x[(m, u)]["partial"], cites_x[(m, u)]["dislikes"]] for (m, u), n in rows]


def page_rows(pages, site_pages_csv):
    """pages-cited.csv: one row per cited page over all the data: first and last citation day, citations, answers,
    partial answers and dislikes; and, when site-pages.csv is beside the repo, the page's LastMod, the first day it was
    cited on or after that LastMod and how many answers cited it since. That is the index lag: how long after a page
    changed before AskCI cited the changed page (brief §62, with Budget 2027 as the test case)."""
    mod = {}
    if site_pages_csv and os.path.exists(site_pages_csv):
        with open(site_pages_csv, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                u = (r.get("URL") or "").strip().rstrip("/").lower(); lm = (r.get("LastMod") or "").strip()[:10]
                if u and re.fullmatch(r"\d{4}-\d{2}-\d{2}", lm): mod[u] = lm
    cols = ["URL", "FirstCited", "LastCited", "Citations", "Answers", "Partial", "Dislikes", "LastMod", "FirstCitedAfterLastMod", "AnswersAfterLastMod"]
    out = []
    for u, pg in sorted(pages.items(), key=lambda kv: (-kv[1]["answers"], kv[0])):
        lm = mod.get(u.lower(), "")
        fa = ca = ""
        if lm:
            lmd = date.fromisoformat(lm); after = sorted(d for d in pg["days"] if d >= lmd)
            fa = after[0].isoformat() if after else ""; ca = sum(pg["days"][d] for d in after)
        out.append([u, pg["first"].isoformat(), pg["last"].isoformat(), pg["cites"], pg["answers"], pg["partial"], pg["dislikes"], lm, fa, ca])
    return cols, out


def journey_rows(jm):
    return ["Month", "From", "To", "Conversations"], [[m, a, b, n] for (m, a, b), n in sorted(jm.items(), key=lambda kv: (kv[0][0], -kv[1]))]


def starter_rows(sp):
    """starter-prompts-monthly.csv: each configured chip as a first turn, by month (brief §63): its own outcome
    (Cited, of which Partial; NotFound; Clarification), what followed, dislikes, answer words and response time
    sums, and of the mature conversations it started, how many ended there."""
    try:
        from redact_feed import intent_of   # the chip's own intent, by the same rules as every question (brief §69)
    except ImportError:
        intent_of = lambda q: ("", "")
    return ["Month", "Prompt", "Count", "Cited", "FollowedByTyped", "FollowedBySuggested", "Partial", "NotFound", "Clarification", "Disliked",
            "Words", "TimedTurns", "ResponseMsSum", "Mature", "EndedThere", "Intent"], \
           [[m, p, c["count"], c["cited"], c["typed2"], c["suggested2"], c["partial"], c["notfound"], c["clarification"], c["disliked"],
             c["words"], c["timed"], c["ms"], c["mature"], c["ended"], intent_of(p)[0]] for (m, p), c in sorted(sp.items(), key=lambda kv: (kv[0][0], -kv[1]["count"]))]


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
    if has_starter: cols += ["StarterPromptFirstTurns", "OrganicFirstTurns"] + (["StarterPromptErrors", "OrganicFirstErrors"] if has_outcome else [])
    if has_script: cols += ["Script" + k for k in SCRIPT_COLS]
    cols += ["LatencyP99ms"] + [c for c, _ in LAT_COLS]
    if has_outcome: cols += [c for c, _ in OUTCOME_COLS] + ["OutcomeRules"] + [c for c, _ in CROSS_COLS]
    has_words = any(D[d]["words_n"] for d in D)
    if has_words: cols += ["AnswerWords", "AnswerWordsTurns", "CitedWords", "CitedWordsTurns"]
    out = []
    for d in sorted(D):
        c = D[d]; s = sess[d]; L = sorted(lat[d])
        row = [d.isoformat(), c["turns"], len(s["all"]), c["answered"], c["unanswered"], c["flagged"], c["new_topic"], c["user_followup"],
               c["suggested_followup"], c["modal_turns"], c["web_turns"], c["other_turns"], len(s["modal"]), len(s["web"]), c["citations"],
               pct(L, 50), pct(L, 90)]
        if has_voice: row += [c["voice_turns"], len(s["voice"])]
        row += [c["likes"], c["dislikes"], c["dislikes_cited"]]
        if has_starter: row += [c["starter"], c["organic"]] + ([c["starter_err"], c["organic_err"]] if has_outcome else [])
        if has_script: row += [c["script:" + k] for k in SCRIPT_COLS]
        row += [pct(L, 99)] + [c[k] for _, k in LAT_COLS]
        if has_outcome: row += [c[k] for _, k in OUTCOME_COLS] + [rules] + [c[k] for _, k in CROSS_COLS]
        if has_words: row += [c["words"], c["words_n"], c["cwords"], c["cwords_n"]]
        out.append(row)
    return cols, out


def script_outcome_rows(D):
    rows = [[d.isoformat(), sc, D[d][f"so:{sc}:turns"], D[d][f"so:{sc}:scored"], D[d][f"so:{sc}:cited"], D[d][f"so:{sc}:notfound"], D[d][f"so:{sc}:clar"]]
            for d in sorted(D) for sc in SCRIPT_COLS if D[d][f"so:{sc}:turns"]]
    return ["Date", "Script", "Turns", "Scored", "Cited", "NotFound", "Clarification"], rows


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
        for s, n in sorted(monthly[(y, mo)].items(), key=lambda kv: (-kv[1], kv[0])):
            out.append([CAT_NAME.get(s, s.replace("-", " ").title()), n, MONTHS[mo - 1]])
    daily = [[d.isoformat(), s, n] for d in sorted(cats) for s, n in sorted(cats[d].items(), key=lambda kv: (-kv[1], kv[0]))]   # ties by slug: stable across runs
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
    ap.add_argument("--out-dir", help="write every aggregate file listed above here")
    ap.add_argument("--compare", metavar="DIR", help="compare with the usage.csv and categories.csv in DIR; write nothing")
    ap.add_argument("--keep-partial", action="store_true", help="keep the last day even when it is the export day (partial by default it is dropped)")
    ap.add_argument("--category-rule", choices=["distinct", "tokens"], default="distinct", help="distinct per turn with URL fallback (default), or every Categories entry incl. repeats and no fallback (old file's rule)")
    a = ap.parse_args()
    global CATEGORY_RULE; CATEGORY_RULE = a.category_rule
    # An export taken on day X contains only part of day X; skip those rows unless asked to keep them.
    export_days = {datetime.strptime(m.group(1), "%Y%m%d").date() for m in (re.search(r"(\d{8})_\d{6}", os.path.basename(f)) for f in a.files) if m}
    skip = frozenset() if (a.keep_partial or not export_days) else frozenset({max(export_days)})  # only the newest export's own day is partial
    D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped, has_outcome, rules, has_starter, has_script, recs, (cites_m, cites_x, pages), latb, rulesd, (style, safety, intent, asked, qtopic, cint, askw, qtop, qcat, qic, tmpl, orgs) = aggregate(a.files, skip)
    rules = ", ".join(sorted(r for r in rules if r))
    if skip and any(True for _ in skip): print(f"note: export day(s) {', '.join(str(x) for x in sorted(skip))} skipped as partial (--keep-partial to keep)")
    cd, co, jm, sp, cstats = conversation_pass(recs)
    print(f"conversations: {cstats['convs']} grouped, {cstats['mature']} mature; follow-ups within 1 h {cstats['fu_1h']/max(cstats['fu'],1)*100:.2f}%, within 24 h {cstats['fu_24h']/max(cstats['fu'],1)*100:.2f}%; "
          f"category steps ≥2 in {cstats['multi_step']} conversations, {cstats['return']} with a return; not-found turns attributed a category from other turns {cstats['recovered']} of {cstats['nf_total']}")
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
        if has_script and has_outcome: write(os.path.join(a.out_dir, "script-outcomes-daily.csv"), *script_outcome_rows(D))
        write(os.path.join(a.out_dir, "categories.csv"), ccols, crows)
        write(os.path.join(a.out_dir, "categories-daily.csv"), dcols, drows)
        write(os.path.join(a.out_dir, "conversations-daily.csv"), *conversation_rows(cd))
        write(os.path.join(a.out_dir, "category-outcomes-daily.csv"), *category_outcome_rows(co))
        write(os.path.join(a.out_dir, "citations-monthly.csv"), *citation_rows(cites_m, cites_x))
        write(os.path.join(a.out_dir, "pages-cited.csv"), *page_rows(pages, os.path.join(REPO, "site-pages.csv")))
        write(os.path.join(a.out_dir, "journeys-monthly.csv"), *journey_rows(jm))
        write(os.path.join(a.out_dir, "starter-prompts-monthly.csv"), *starter_rows(sp))
        if latb: write(os.path.join(a.out_dir, "latency-buckets-daily.csv"), *latency_bucket_rows(latb))
        if rulesd:   # needs feeds redacted with Outcome Rule (redact_feed.py from 23 Oct 2026)
            write(os.path.join(a.out_dir, "outcome-rules-daily.csv"), *rule_rows(rulesd))
            write(os.path.join(a.out_dir, "answer-style-daily.csv"), *style_rows(style))
            if tmpl: write(os.path.join(a.out_dir, "answer-templates-daily.csv"), *tmpl_rows(tmpl))
            if orgs: write(os.path.join(a.out_dir, "answer-signposts-monthly.csv"), *orgs_rows(orgs))
        if safety: write(os.path.join(a.out_dir, "safety-daily.csv"), *safety_rows(safety))
        if intent:
            write(os.path.join(a.out_dir, "question-intent-daily.csv"), *intent_rows(intent))
            write(os.path.join(a.out_dir, "asked-pages-monthly.csv"), *asked_rows(asked))
            write(os.path.join(a.out_dir, "question-topics-daily.csv"), *qtopic_rows(qtopic))
            write(os.path.join(a.out_dir, "citations-intent-monthly.csv"), *cint_rows(cint))
            write(os.path.join(a.out_dir, "asked-pages-weekly.csv"), *askw_rows(askw, asked))
            if qcat:   # the topic layer (brief §75): present once the redaction carries Category Source
                write(os.path.join(a.out_dir, "question-topics-monthly.csv"), *qtop_rows(qtop))
                write(os.path.join(a.out_dir, "question-categories-monthly.csv"), *qcat_rows(qcat))
                write(os.path.join(a.out_dir, "question-intent-category-monthly.csv"), *qic_rows(qic))
            if cstats.get("ij"): write(os.path.join(a.out_dir, "intent-journeys-monthly.csv"), *intent_journey_rows(cstats["ij"]))
            if cstats.get("sb"): write(os.path.join(a.out_dir, "setback-intents-monthly.csv"), *setback_intent_rows(cstats["sb"]))
    elif a.out:
        write(a.out, ucols, urows)
    else:
        w = csv.writer(sys.stdout); w.writerow(ucols); w.writerows(urows)


if __name__ == "__main__":
    main()
