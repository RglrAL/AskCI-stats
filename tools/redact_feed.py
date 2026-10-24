#!/usr/bin/env python3
"""Redact an AskCI QA feed export so it can be kept and shared without citizens' text.

Classifies each turn's outcome from the response text (rules below, versioned), then drops
the free-text columns (User Query, Assistant Response, Report Subject, Report Description)
and writes every other column unchanged plus three derived ones: Outcome, Partial and
Outcome Rules. Nothing of the text itself survives.

Outcome rules, applied in order, first match wins (after mapping curly apostrophes to
straight ones; the admin-app spec's published patterns use straight apostrophes while the
feed mostly uses U+2019, which is why its printed not-found pattern under-counts):
  Error          empty response and 0 ms
  Cited answer   at least one citation URL
  Not found      "couldn't find", "no specific information", "does not (currently) provide" ...
  Clarification  "could you clarify", "what you mean", "more detail", "which scheme/payment"
  Out of scope   refusal phrases, else the feed's Flagged = Yes (after Greeting)
  Greeting       "hello"/"hi" opening, "how can I help", "glad to help" ...
  Uncited answer anything else
Partial = a Cited answer whose text also matches the not-found pattern.

Two more derived columns, both read from the query text before it is dropped:
  Starter Prompt  the matched chip text when a first turn's normalised query (lower case,
                  trimmed, trailing punctuation removed, spaces collapsed) equals one of the
                  configured chips; blank otherwise. The chip text is configuration, not citizen text
  Query Script    Unicode script of the first letter: Latin, Cyrillic, Arabic, CJK, Devanagari,
                  Other, or None when the query has no letter. A script, not a language.
  Response Words  word count of the response (a number; the text itself is dropped)
  Outcome Rule    the id of the phrase that decided the outcome (nf.couldnt_find, cl.more_detail, cited,
                  cited.partial.nf.no_specific_info, oos.flagged, uncited, err.empty ...): no text
  Style Version and Answer Lines / Hedges / Apologies / Signposts / Questions / Links: counts of list lines,
                  hedging words, apologies, signposting verbs, question marks and links in the answer (the
                  wording fingerprint, brief §53). The output still contains per-turn
rows, so it stays out of git (.gitignore covers qa-feed*.csv); only the daily aggregates
produced by make_usage.py go into the dashboard.

Usage:
    python3 tools/redact_feed.py qa-feed_20261008.csv              # writes qa-feed-redacted_20261008.csv beside it
    python3 tools/redact_feed.py qa-feed_*.csv --out-dir ~/feeds   # several files, output elsewhere
"""
import argparse, csv, json, os, sys
from datetime import datetime

import re

DROP = ["User Query", "Assistant Response", "Report Subject", "Report Description"]
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

OUTCOME_RULES_VERSION = "2026.10.23-2"
# Each pattern is a list of (rule id, alternative), joined in order; the named group that matched says which phrase
# decided the outcome (brief §53). 2026.10.23-2 (brief §60) checked the rules against the system prompts of 28 Aug 2026
# and added the phrases the prompts prescribe that the feed shows: the fixed no-results sentence (nf.template, listed
# first so it wins over the shorter phrase inside it), two out-of-scope wordings and two refusals (Out of scope family),
# and a greeting form. The outcomes of 2026.10.08-1 change on about 20 rows in 145,000 (greetings previously flagged).
RULES = {
    "not_found": [("nf.template", r"couldn't find specific information about this topic in the citizens information content available to me"),
                  ("nf.couldnt_find", r"couldn't find"), ("nf.could_not_find", r"could not find"), ("nf.wasnt_able", r"wasn't able to find"),
                  ("nf.unable_to_find", r"unable to find"), ("nf.no_specific_info", r"no specific information"), ("nf.not_find_specific", r"not find specific"),
                  ("nf.dont_have_info", r"don't have (specific )?information"), ("nf.does_not_provide", r"does not (currently )?(provide|have)")],
    "clarification": [("cl.could_you", r"could you (please )?(clarify|tell me|let me know)"), ("cl.what_you_mean", r"what you mean"),
                      ("cl.more_detail", r"more detail"), ("cl.which_scheme", r"which (scheme|payment)")],
    "out_of_scope": [("oos.specialise", r"specialise in providing information"), ("oos.specialize", r"specialize in providing information"),
                     ("oos.cant_help_topic", r"can't help with that (particular )?topic"), ("oos.not_able_topic", r"not able to help with that topic"),
                     ("oos.outside_scope", r"outside (the )?scope"), ("oos.not_covered", r"isn't covered by the information i can provide"),
                     ("oos.public_services", r"information about irish public services and entitlements"),
                     ("oos.cannot_assist", r"cannot assist with that request"), ("oos.internal_guidelines", r"cannot discuss my internal guidelines")],
    "greeting": [("gr.hello", r"^(hello|hi)\b"), ("gr.how_can_i_help", r"how can i help"), ("gr.what_would_you_like", r"what would you like information about"), ("gr.welcome", r"you're welcome"), ("gr.glad_to_help", r"glad to help"),
                 ("gr.glad_to_hear", r"glad to hear"), ("gr.glad_you", r"glad you"), ("gr.glad_i_could", r"glad i could")],
}
GID = lambda rid: rid.replace(".", "__")
RX = {k: re.compile("|".join(f"(?P<{GID(rid)}>{alt})" for rid, alt in v), re.I) for k, v in RULES.items()}


def rule_of(m):
    """The rule id of the alternative that matched (the leftmost match, first alternative at that place)."""
    return next(k.replace("__", ".") for k, v in m.groupdict().items() if v is not None)


# Wording fingerprint (brief §53): counts read from the answer text, which is then dropped. Not outcome rules: a shift
# in these on a date with no model change is the trace of a prompt change.
# 2026.10.23-2 adds counts for forms the system prompts of 28 Aug 2026 prescribe or forbid (brief §60), so that a model
# reading the same prompt more literally shows up here: a sign-off line linking the homepage, a continuity opener on
# follow-ups, invitation phrases, a bare "Yes." or "No.", heading or bold markup, nested list lines, an "(external)"
# link marker and the "remain in effect" freshness form. Counts only; the names say what is counted, not why.
STYLE_VERSION = "2026.10.23-2"
STYLE = {
    "Answer Lines": re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+", re.M),
    "Answer Hedges": re.compile(r"\b(?:may|might|generally|usually|typically|depends? on|depending on|in some cases|not always)\b", re.I),
    "Answer Apologies": re.compile(r"\b(?:sorry|apologi[sz]e|unfortunately)\b", re.I),
    "Answer Signposts": re.compile(r"\b(?:contact|get in touch|phone|call|ring|visit|speak to|talk to)\b", re.I),
    "Answer Questions": re.compile(r"\?"),
    "Answer Links": re.compile(r"https?://"),
    "Answer Openers": re.compile(r"^(?:building on that|in that case|continuing from your earlier question)", re.I),
    "Answer Invitations": re.compile(r"feel free to ask|let me know if you need|don't hesitate to ask", re.I),
    "Answer Absolutes": re.compile(r"(?:^|[.!?]\s+)(?:yes|no)\.", re.I | re.M),
    "Answer Emphasis": re.compile(r"^#{1,6}\s|\*\*", re.M),
    "Answer Nested": re.compile(r"^\s{2,}(?:[-*\u2022]|\d+[.)])\s+", re.M),
    "Answer External": re.compile(r"\(external\)", re.I),
    "Answer Freshness": re.compile(r"remains? in effect", re.I),
}
SIGNOFF = re.compile(r"citizensinformation\.ie", re.I)   # Answer Signoff: 1 if the last non-empty line links the site

# Safety counts (brief §53 step 10, §65): flags read from the question before it is dropped. Each is 1 or blank in the
# redacted feed; the identifier itself is never kept. Identifiers: a PPS number (7 digits then 1 or 2 letters), an Irish
# or international phone number, an email address, an IBAN, a 16-digit card number. Injection: the usual override
# phrasings. Themes: a few off-topic kinds the scope rules name (creative writing, code, sport, entertainment, weather)
# and crisis language, so that what AskCI answers to it can be counted. Counts only; names say what is matched.
SAFETY_VERSION = "2026.10.24-1"
SAFETY = {
    "Query PPS": re.compile(r"(?<![\dA-Za-z])\d{7}[A-Za-z]{1,2}(?![\dA-Za-z])"),
    "Query Phone": re.compile(r"(?<!\d)(?:\+353|00353|0)\s?(?:[1-9]\d{0,2})[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)"),
    "Query Email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "Query IBAN": re.compile(r"\bIE\d{2}\s?[A-Z]{4}(?:\s?\d{4}){3}\s?\d{2}\b", re.I),
    "Query Card": re.compile(r"(?<!\d)(?:\d{4}[\s-]?){3}\d{4}(?!\d)"),
    "Query Injection": re.compile(r"ignore (?:all |any )?(?:of )?(?:the |your |my )?(?:previous|prior|above|earlier) (?:instructions|rules|prompts?)|system prompt|you are now|pretend (?:to be|you are|that you)|jailbreak|developer mode|\bDAN\b|reveal your (?:prompt|instructions|rules)|forget (?:your|all|the) (?:rules|instructions)|what are your (?:rules|instructions)|repeat (?:your|the) (?:system|initial) (?:prompt|instructions)", re.I),
}
THEMES = [("creative", re.compile(r"\b(?:write|tell|compose|make up|sing)\b.{0,30}\b(?:poem|joke|story|song|rap|limerick|haiku|essay for school)\b|\b(?:a poem|a joke|a story) about\b", re.I)),
          ("code", re.compile(r"\b(?:python|javascript|java|sql|html|css|bash|excel formula|regex)\b.{0,30}\b(?:code|script|function|query|formula|program)\b|\bwrite (?:me )?(?:some )?code\b", re.I)),
          ("sport", re.compile(r"\b(?:premier league|champions league|all-ireland|gaa (?:match|final)|who won the (?:match|game|final)|football (?:score|result)s?|rugby (?:score|result)s?)\b", re.I)),
          ("entertainment", re.compile(r"\b(?:netflix|movie|film|tv show|series to watch|taylor swift|song lyrics|eurovision|celebrity)\b", re.I)),
          ("weather", re.compile(r"\b(?:weather (?:today|tomorrow|forecast|this week)|will it rain|forecast for)\b", re.I)),
          ("crisis", re.compile(r"\b(?:suicid\w*|kill (?:myself|me)|end (?:my|it all|my life)|self[- ]harm|want to die|don'?t want to (?:live|be here)|overdos\w*)\b", re.I))]


# What people ask (brief §66): an intent class by rule, form flags, and the scheme the question names, from
# question-lexicon.json (the site's page slugs plus aliases; tools/make_lexicon.py). Read from the question before it is
# dropped; what leaves is the class name, the flags, the matched page address and its category. INTENT_VERSION covers
# the rules below; the lexicon carries its own version.
INTENT_VERSION = "2026.10.24-2"
# One derivation version (brief §75) bundles the lexicon's topic layer, the response rules and the template list; it is
# checked against the lexicon's derivation_version at run time. Changelog, one line per bump:
#   2026.10.24-1  topic layer (housing, 20 topics), Query Topic and Category Source columns
#   2026.10.24-2  fixed-wording templates (TEMPLATES below), Answer Templates column
#   2026.10.24-3  organisations the answer signposts to (ORGS below), Answer Orgs column
#   2026.10.24-4  figures quoted in the answer checked against dated snapshots of the cited pages, four Answer Figures columns
#   2026.10.24-5  topic tables for social welfare, employment, money and tax, moving country and health (47 topics; lexicon 2026.10.24-5)
DERIVATION_VERSION = "2026.10.24-5"

# Figures quoted (brief §75, response layer 2): euro amounts, percentages and years in the answer, checked against the
# text of every page the answer cites as that page was when the answer was given (tools/fetch_pages.py keeps a snapshot
# per page and LastMod under exports/site-text). Three results per figure: matched (the number appears on a usable
# snapshot of a cited page), unverifiable (a cited page's LastMod is after the answer date, so the page has changed since,
# or there is no snapshot, or the answer cites nothing), unmatched (every cited page was checkable and none carries it).
# Forms are normalised (€232 / 232 / €232.00 / 232 euro). An upper bound on error until the labelling sheet's
# figure-match column calibrates it; the word "accuracy" is not used.
FIG_EURO = re.compile(r"€\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?(?:euro|eur)\b", re.I)
FIG_PCT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
FIG_YEAR = re.compile(r"\b(20[12]\d)\b")
FIG_BARE = re.compile(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)(?![\d.])")
FIG_URL = re.compile(r"https?://[^\s<>\"')\]]+")
SNAP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports", "site-text")
_SNAPS = {}


def canon_num(s):
    s = s.replace(",", "")
    if "." in s: s = s.rstrip("0").rstrip(".")
    return s.lstrip("0") or "0"


def figures_of(text, bare=False):
    """{(kind, canonical number)} for euro (e), percent (p) and year (y) figures; with bare=True also every plain number (n)."""
    t = (text or "").replace("€", "€")
    out = {("e", canon_num(a or b)) for a, b in FIG_EURO.findall(t)}
    out |= {("p", canon_num(x)) for x in FIG_PCT.findall(t)}
    out |= {("y", x) for x in FIG_YEAR.findall(t)}
    if bare: out |= {("n", canon_num(x)) for x in FIG_BARE.findall(t)}
    return out


def _snap_key(u):
    import hashlib
    m = re.match(r"^(https?)://([^/?#]+)([^?#]*)", u.strip().rstrip(".,;)"), re.I)
    if not m: return None
    host = m.group(2).lower(); host = "www.citizensinformation.ie" if host == "citizensinformation.ie" else host
    return hashlib.sha1(f"https://{host}{m.group(3).rstrip('/') or '/'}".encode()).hexdigest()[:16]


def _snapshots(key):
    """[(lastmod, figure set)] for a page, oldest first; loaded once per key."""
    if key not in _SNAPS:
        lst = []
        try:
            for f in sorted(os.listdir(SNAP_DIR)):
                if f.startswith(key + "__") and f.endswith(".txt"):
                    lm = f[len(key) + 2:-4]
                    with open(os.path.join(SNAP_DIR, f), encoding="utf-8") as fh: lst.append((lm, figures_of(fh.read(), bare=True)))
        except OSError: pass
        _SNAPS[key] = lst
    return _SNAPS[key]


def check_figures(answer, citations, day):
    """(figures, matched, unmatched, unverifiable) for one answer on one day (ISO date)."""
    figs = figures_of(answer)
    if not figs: return 0, 0, 0, 0
    pages = {k for k in (_snap_key(u) for u in FIG_URL.findall(citations or "")) if k}
    snaps = []; unverifiable = not pages
    for k in pages:
        usable = [s for lm, s in _snapshots(k) if lm != "unknown" and lm <= day]
        if usable: snaps.append(usable[-1])
        else: unverifiable = True
    m = u = v = 0
    for f in figs:
        if any(f in s or ("n", f[1]) in s for s in snaps): m += 1
        elif unverifiable: v += 1
        else: u += 1
    return len(figs), m, u, v

# Organisations an answer can signpost to (brief §75, response layer 3): public bodies, helplines and the service's own
# channels, matched by name in the answer text. The ids and counts are published; the measure is whether a not-found or
# partial answer sent the person somewhere, and where. Families: dept (government department), agency (state body),
# local (local authority), ngo (charity or helpline), cic (Citizens Information's own channels), court (courts and
# tribunals). Names are public; tools/answer_templates.py --org-counts prints how often each is named (counts only).
ORGS = [
    ("cic.centre", "cic", r"citizens information (?:centre|center|service|office)s?"),
    ("cic.phone", "cic", r"citizens information phone service|0818 07 4000"),
    ("cic.mabs", "ngo", r"\bmabs\b|money advice and budgeting"),
    ("dept.dsp", "dept", r"department of social protection|\bdsp\b"),
    ("dept.intreo", "agency", r"\bintreo\b"),
    ("dept.revenue", "dept", r"\brevenue\b(?! commissioners)|revenue commissioners|myaccount|\bros\b"),
    ("dept.housing", "dept", r"department of housing"),
    ("dept.justice", "dept", r"department of justice"),
    ("dept.education", "dept", r"department of education"),
    ("dept.enterprise", "dept", r"department of enterprise"),
    ("dept.foreign", "dept", r"department of foreign affairs|passport (?:service|office)"),
    ("agency.hse", "agency", r"\bhse\b|health service executive"),
    ("agency.rtb", "agency", r"\brtb\b|residential tenancies board"),
    ("agency.wrc", "agency", r"\bwrc\b|workplace relations commission"),
    ("agency.isd", "agency", r"immigration service delivery|\bisd\b|\binis\b|irish naturalisation"),
    ("agency.susi", "agency", r"\bsusi\b"),
    ("agency.seai", "agency", r"\bseai\b|sustainable energy authority"),
    ("agency.ndls", "agency", r"\bndls\b|national driver licence service"),
    ("agency.rsa", "agency", r"road safety authority|\brsa\b"),
    ("agency.pensions", "agency", r"pensions authority|pensions council"),
    ("agency.housing_agency", "agency", r"housing agency|land development agency|\blda\b"),
    ("agency.tusla", "agency", r"\btusla\b"),
    ("agency.garda", "agency", r"\bgarda[ií]?\b|garda s[ií]och[aá]na"),
    ("agency.ombudsman", "agency", r"ombudsman"),
    ("agency.ccpc", "agency", r"\bccpc\b|competition and consumer protection"),
    ("agency.dpc", "agency", r"data protection commission"),
    ("agency.legalaid", "agency", r"legal aid board"),
    ("local.authority", "local", r"local authority|county council|city council|local council"),
    ("court.courts", "court", r"courts service|district court|circuit court|high court|small claims"),
    ("ngo.threshold", "ngo", r"\bthreshold\b"),
    ("ngo.flac", "ngo", r"\bflac\b|free legal advice"),
    ("ngo.focus", "ngo", r"focus ireland|simon community|peter mcverry|depaul"),
    ("ngo.womensaid", "ngo", r"women'?s aid|men'?s aid|safe ireland"),
    ("ngo.samaritans", "ngo", r"samaritans|\bpieta\b|text about it|50808"),
    ("ngo.treoir", "ngo", r"\btreoir\b|one family"),
    ("ngo.immigrant", "ngo", r"immigrant council|nasc\b|crosscare|irish refugee council"),
    ("ngo.union", "ngo", r"trade union|\bsiptu\b|\bictu\b"),
    ("ngo.solicitor", "ngo", r"\bsolicitor\b"),
    ("ngo.gp", "ngo", r"\byour gp\b|\ba gp\b|\bdoctor\b"),
]
_ORX = [(oid, fam, re.compile(rx)) for oid, fam, rx in ORGS]


def answer_orgs(a):
    """';'-joined ids of every ORGS entry named in the answer, or ''."""
    t = (a or "").translate(APOS).lower()
    return ";".join(oid for oid, _, rx in _ORX if rx.search(t))

# The bot's fixed wording (brief §75, response layer 1): sentences the answering model is told to use, found by
# tools/answer_templates.py --discover (a sentence in 200+ answers and 50+ conversations, so the bot's own words, never
# an echo of one person's). Each answer records every template id it carries; make_usage.py counts them per day. A
# template that starts or stops on a date with no model event is the trace of a prompt change. Matched on the answer
# lower-cased with straight apostrophes and single spaces; links are replaced by <link> first.
TEMPLATES = [
    ("signoff.query", "sign-off", r"thank you for your query\."),
    ("signoff.using", "sign-off", r"thank you for using <link>"),
    ("signoff.visiting", "sign-off", r"thank(?:s| you) for visiting <link>"),
    ("signoff.checking", "sign-off", r"thank(?:s| you) for checking(?: with)? <link>"),
    ("more.uptodate", "read more", r"for the most up.to.date information, please visit"),
    ("more.visit", "read more", r"for (?:more|full|further) (?:information|details|detailed guidance), (?:please )?(?:visit|see)"),
    ("more.readmore", "read more", r"you can read more (?:on|about)"),
    ("more.website", "read more", r"you can read more on the citizens information (?:website|page)"),
    ("guidance.accurate", "signpost", r"to get accurate and up.to.date guidance"),
    ("guidance.centre", "signpost", r"contact your local citizens information centre"),
    ("guidance.phone", "signpost", r"call the citizens information phone service"),
    ("clar.asking_about", "clarification", r"for example, are you asking about:"),
    ("clar.do_you_mean", "clarification", r"for example, do you mean:"),
    ("nf.sorry_template", "no results", r"i'm sorry, i couldn't find specific information about this topic in the citizens information content available to me"),
    ("oos.sources", "out of scope", r"i can provide information from citizens information sources about irish public services and entitlements"),
    ("oos.not_covered", "out of scope", r"that topic isn't covered by the information i can provide"),
    ("greet.assist", "greeting", r"how can i assist you today\?"),
    ("greet.happy", "greeting", r"i'd be happy to help with that\."),
]
_TRX = [(tid, fam, re.compile(rx)) for tid, fam, rx in TEMPLATES]
_TLINK = re.compile(r"\[[^\]]*\]\([^)]*\)|https?://\S+")


def answer_templates(a):
    """';'-joined ids of every TEMPLATES sentence the answer carries, or ''."""
    t = (a or "").translate(APOS).lower().replace("‑", "-")
    t = re.sub(r"\s+", " ", _TLINK.sub("<link>", t))
    return ";".join(tid for tid, _, rx in _TRX if rx.search(t))
INTENT_RULES = [   # in precedence order: the first that matches wins
    ("status", re.compile(r"\b(?:my (?:claim|application|appeal|payment|case|form|request|renewal)\b.{0,40}\b(?:status|approved|decision|delayed|late|not (?:been )?(?:paid|received|processed)|still waiting|how long more|when will (?:i|it))|why (?:haven'?t|hasn'?t|have i not|has my|did my|was my)|(?:where|what) is my (?:payment|money|claim|application)|has my (?:claim|application|payment)|track my|check (?:the )?status|(?:i|we) (?:applied|submitted|sent).{0,30}\b(?:weeks?|months?|days?) ago|my (?:\w+ ){0,2}(?:claim|application|appeal|payment|renewal|form)\b.{0,80}\b(?:ago|still|yet|waiting|heard|no (?:reply|response|update|word)))\b", re.I)),
    ("contact", re.compile(r"\b(?:phone number|contact (?:number|details)|email address|opening hours|open(?:ing)? (?:times?|hours)|where is (?:the|my)? ?(?:nearest|local)|nearest (?:office|centre|center|intreo|cic)|(?:intreo|citizens information) (?:office|centre|center)|how (?:do|can) i (?:contact|reach|ring|call|phone|talk to|speak to)|address (?:of|for) the|who (?:do|can|should) i (?:contact|ring|call|talk to|speak to)|helpline)\b", re.I)),
    ("documents", re.compile(r"\b(?:what (?:documents?|paperwork|proof|id|identification|forms?) (?:do i|will i|are|is|should i)|documents? (?:needed|required|do i need|i need|to bring|to provide)|proof of|supporting documents?|what (?:do i|should i) (?:bring|need to bring|submit|provide|attach|upload))\b", re.I)),
    ("apply", re.compile(r"\b(?:how (?:do|can|to|would|should|does one|do you) (?:i |we |you |one )?(?:apply|claim|register|renew|sign up|enrol|enroll|get (?:a|an|the|my) |request|book|order)|apply (?:for|online)|application (?:form|process|online)|where (?:do|can) i (?:apply|get the form|sign)|(?:apply|register|renew)ing for|fill (?:in|out) the|the form for|sign up for|register (?:for|with)|how (?:do|can) i (?:change|update|switch|transfer|cancel|stop|withdraw|close)|^how (?:do|does|can|could|would|should|to|will|did|is|are) (?:i|we|you|one|a|an|my|the|this|it|someone|anyone)?\b|^how to\b|^(?:what|where|which) (?:do|should|can) (?:i|we) (?:do|go|send|post|bring|take)\b)", re.I)),
    ("rate", re.compile(r"\b(?:how much|what (?:is|are|was|will be) the (?:rate|rates|amount|payment|cost|fee|fees|price|charge|threshold|limit|limits|maximum|minimum|weekly|monthly|increase|cap|allowance|grant amount)|rate of|rates? (?:for|of|in|from)|per (?:week|month|year|hour|day|child)|weekly (?:rate|payment|amount)|how many (?:hours|weeks|days|years|contributions|credits)|what (?:do|will|would) (?:i|we|they) (?:get|receive|be paid)|is it (?:paid|taxed|taxable)|€\s?\d|\d+\s?(?:euro|euros|eur)\b|what percentage|income (?:limit|threshold)s?|means test (?:limit|threshold)|budget 20\d\d|increase[sd]? (?:in|by|to) (?:the )?budget|taxable|taxed|limits?|thresholds?|ceiling|maximum|minimum)\b", re.I)),
    ("eligibility", re.compile(r"\b(?:^(?:can|could|may|would|will|should|does|do|is|are|am) (?:i|we|a|an|my|you|someone|anyone|he|she|they|it|there|this|that|the)\b|am i (?:entitled|eligible|able|allowed|covered|exempt)|(?:can|could|will|would|do|does|may|might|should) (?:i|we|my (?:wife|husband|partner|son|daughter|mother|father|child|parents?|family)|he|she|they|a person|someone|you) (?:get|claim|qualify|receive|be entitled|be eligible|apply|still|keep|continue|work|have|be paid|avail|access|be able)|entitled to|eligib(?:le|ility)|qualify(?:ing)? for|who (?:can|is entitled|qualifies|is eligible|gets)|do i (?:have to|need|qualify)|is (?:there|it possible)|if i (?:am|have|was|were|work|earn|move|leave|get|lose|retire|marry|separate|own|rent)|criteria|conditions? (?:for|to)|what (?:if|happens if|about))\b", re.I)),
    ("timing", re.compile(r"\b(?:how long|when (?:do|does|did|will|can|is|are|should|must)|what (?:date|day|time|age)|(?:closing|due|start|end|payment|pay) dates?|deadline|backdated?|waiting (?:time|list|period)|how (?:soon|often|late|early)|from what age|at what age|until when|(?:this|next|last) (?:week|month|year)|processing time|turnaround|time frame|timeframe|how quickly)\b", re.I)),
    ("statement", re.compile(r"^(?:(?!\b(?:what|how|when|where|who|which|why|can|could|do|does|is|are|am|will|should|would|may)\b).)*\b(?:i am|i'm|im|i have|i've|ive|i was|i want|i need|i would like|i'd like|i work|i live|i get|i earn|i receive|my (?:wife|husband|partner|son|daughter|mother|father|child|children|employer|landlord))\b", re.I)),
    ("definition", re.compile(r"\b(?:what (?:is|are|does|do|was|were) (?:a |an |the )?(?!my\b|i\b|we\b)(?:[a-z0-9'\-]+\s?){1,6}(?:\?|$|mean|means|cover|covers|include|includes|for)|what does .{1,40} (?:mean|stand for|cover|do)|(?:explain|define|meaning of|definition of|difference between|tell me about|information (?:on|about)|info (?:on|about)|about the)\b|^(?:[a-z0-9'\-]+\s?){1,5}$)", re.I)),
]
FORM = {
    "year": re.compile(r"\b20[12]\d\b"),
    "euro": re.compile(r"€\s?\d|\d+\s?(?:euro|euros|eur)\b|\d{1,3}(?:,\d{3})+\b"),
    "yesno": re.compile(r"^(?:is|are|am|can|could|will|would|do|does|did|should|may|might|has|have|was|were)\b", re.I),
}
SITUATION_WORDS = 25   # a personal situation: long, first person, with several conditions
SITUATION_RE = re.compile(r"\b(?:i am|i'm|im|i have|i've|ive|my|we are|we're|i was|i work|i live|i get|i earn|i receive)\b", re.I)
CONDITION_RE = re.compile(r"\b(?:and|but|also|however|although|while|if|since|because|as well|with|without|after|before)\b", re.I)
_LEX = None


def lexicon():
    """question-lexicon.json, loaded once; one regex of every phrase, longest first, so the longest wins at a position."""
    global _LEX
    if _LEX is None:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "question-lexicon.json")
        try:
            j = json.load(open(p, encoding="utf-8"))
            ph = j["phrases"]; keys = sorted(ph, key=lambda k: (-len(k), k))
            # topic layer (brief §75): per topic one regex of its generic keywords; the longest matching keyword wins
            # across topics, and a topic marked general is tried only when no other matched
            topics = []
            for cat, tops in (j.get("topics") or {}).items():
                for name, spec in tops.items():
                    kws = sorted(spec.get("keywords") or [], key=lambda k: (-len(k), k))
                    if kws: topics.append((cat, name, bool(spec.get("general")), re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b")))
            _LEX = {"version": j.get("version", ""), "derivation": j.get("derivation_version", ""), "phrases": ph, "topics": topics,
                    "rx": re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b")}
        except (OSError, ValueError, KeyError):
            _LEX = {"version": "", "derivation": "", "phrases": {}, "topics": [], "rx": None}
    return _LEX


def question_topic(q):
    """(topic, its category) from the lexicon's topic layer, or ('', ''): the topic whose keyword match is longest;
    general topics only when no specific one matched."""
    L = lexicon()
    if not L["topics"]: return "", ""
    nq = norm_words(q).replace("'", "")
    best = None
    for general in (False, True):
        for cat, name, g, rx in L["topics"]:
            if g != general: continue
            for m in rx.finditer(nq):
                if best is None or len(m.group(1)) > best[0]: best = (len(m.group(1)), name, cat)
        if best: return best[1], best[2]
    return "", ""


def norm_words(q):
    q = (q or "").translate(APOS).lower().replace("-", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9'€, ?]+", " ", q)).strip()


GREETING_Q = re.compile(r"^(?:hi|hello|hey|hiya|good (?:morning|afternoon|evening)|thanks?|thank you|ok|okay|yes|no|bye|cheers)\b", re.I)


def intent_of(q):
    """(intent, form flags) for one question: the first INTENT_RULES class that matches, else 'other'. Greetings and
    one-word replies are 'other' whatever the rules say."""
    nq = norm_words(q)
    if not nq: return "other", ""
    intent = "other" if (GREETING_Q.match(nq) and len(nq.split()) <= 4) else next((name for name, rx in INTENT_RULES if rx.search(nq)), "other")
    flags = [k for k, rx in FORM.items() if rx.search(nq)]
    words = nq.split()
    if len(words) >= SITUATION_WORDS and SITUATION_RE.search(nq) and len(CONDITION_RE.findall(nq)) >= 2: flags.append("situation")
    return intent, ";".join(flags)


def topic_of(q):
    """(page url or '', category or '', schemes named) from the longest lexicon phrase the question contains."""
    L = lexicon()
    if not L["rx"]: return "", "", 0
    nq = norm_words(q).replace("'", "")
    hits = [m.group(1) for m in L["rx"].finditer(nq)]
    if not hits: return "", "", 0
    best = max(hits, key=len); e = L["phrases"][best]
    pages = {L["phrases"][h]["path"] for h in hits if L["phrases"][h].get("url")}
    return e.get("url") or "", e.get("category") or "", len(pages)


def safety_flags(q):
    """{column: '1' or ''} for one question; the theme column holds the first matching theme name or ''."""
    q = (q or "").translate(APOS)
    out = {k: ("1" if rx.search(q) else "") for k, rx in SAFETY.items()}
    # a PPS or card match that is really a phone number is one or the other, not both: phone wins when it matched
    if out["Query Phone"] and out["Query Card"]: out["Query Card"] = ""
    out["Query Theme"] = next((name for name, rx in THEMES if rx.search(q)), "")
    return out
URL_RE = re.compile(r'https?://[^\s,;|"]+')

# Starter-prompt chips (AGENT_BRIEF.md, 29 Sep 2026; one added 23 Oct). Matched on first turns only, after
# normalisation. Dates inferred from the feed are candidate "chips" events in events.json.
STARTER_PROMPTS = {
    "what is auto-enrolment", "can i get help with low pay", "how much is maternity benefit",
    "what are the housing assistance payment (hap) limits", "how do i renew my passport",
    "how do i apply for the back to school clothing and footwear allowance",
    "how do i apply for the household benefits package",   # from 14 Oct 2026: found by tools/same_question.py (brief §55)
}
SCRIPTS = [("Latin", re.compile(r"[A-Za-z\u00C0-\u024F]")), ("Cyrillic", re.compile(r"[\u0400-\u04FF]")),
           ("Arabic", re.compile(r"[\u0600-\u06FF]")), ("CJK", re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")),
           ("Devanagari", re.compile(r"[\u0900-\u097F]"))]
LETTER = re.compile(r"[^\W\d_]")


def normalise_query(q):
    q = (q or "").translate(APOS).lower().strip()
    q = re.sub(r"[\s]+", " ", q)
    return re.sub(r"[?.!,;:]+$", "", q).strip()


def query_script(q):
    m = LETTER.search(q or "")
    if not m:
        return "None"
    ch = m.group(0)
    for name, rx in SCRIPTS:
        if rx.match(ch):
            return name
    return "Other"
APOS = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'"})


def classify_rule(row):
    """Return (outcome, partial, rule id) for one feed row. Text is read here and nowhere else."""
    resp = (row.get("Assistant Response") or "").translate(APOS).strip()
    rt = (row.get("Response Time (ms)") or "").strip()
    if resp == "" and rt in ("0", ""):
        return "Error", "", "err.empty"
    cites = len(URL_RE.findall(row.get("Citations") or ""))
    if cites >= 1:
        m = RX["not_found"].search(resp)
        return "Cited answer", ("Yes" if m else ""), ("cited.partial." + rule_of(m) if m else "cited")
    for k, outcome in (("not_found", "Not found"), ("clarification", "Clarification"), ("out_of_scope", "Out of scope"), ("greeting", "Greeting")):
        m = RX[k].search(resp)
        if m:
            return outcome, "", rule_of(m)
    if (row.get("Flagged") or "").strip().lower() == "yes":
        return "Out of scope", "", "oos.flagged"
    return "Uncited answer", "", "uncited"


def classify(row):
    """Return (outcome, partial) for one feed row."""
    return classify_rule(row)[:2]


def style_counts(row):
    resp = (row.get("Assistant Response") or "").translate(APOS)
    out = {k: len(rx.findall(resp)) for k, rx in STYLE.items()}
    lines = [l for l in resp.strip().splitlines() if l.strip()]
    out["Answer Signoff"] = 1 if lines and SIGNOFF.search(lines[-1]) else 0
    return out


def out_name(path, out_dir):
    base = os.path.basename(path)
    base = base.replace("qa-feed_", "qa-feed-redacted_", 1) if base.startswith("qa-feed_") else "redacted_" + base
    return os.path.join(out_dir or os.path.dirname(path) or ".", base)


def redact(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as fi, open(dst, "w", encoding="utf-8", newline="") as fo:
        r = csv.DictReader(fi)
        keep = [c for c in r.fieldnames if c not in DROP] + ["Outcome", "Partial", "Outcome Rules", "Starter Prompt", "Query Script", "Response Words",
                                                          "Outcome Rule", "Style Version"] + list(STYLE) + ["Answer Signoff", "Safety Version"] + list(SAFETY) + ["Query Theme",
                                                          "Intent Version", "Query Intent", "Query Form", "Query Page", "Query Category", "Query Schemes",
                                                          "Derivation Version", "Query Topic", "Category Source", "Answer Templates", "Answer Orgs",
                                                          "Answer Figures", "Answer Figures Matched", "Answer Figures Unmatched", "Answer Figures Unverifiable"]
        dropped = [c for c in r.fieldnames if c in DROP]
        w = csv.DictWriter(fo, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        n = 0; counts = {}
        for row in r:
            o, partial, rule = classify_rule(row)
            counts[o] = counts.get(o, 0) + 1
            if partial: counts["(partial)"] = counts.get("(partial)", 0) + 1
            row["Outcome"], row["Partial"], row["Outcome Rules"] = o, partial, OUTCOME_RULES_VERSION
            q = row.get("User Query") or ""
            nq = normalise_query(q)
            row["Starter Prompt"] = nq if (row.get("Turn #") or "").strip() == "1" and nq in STARTER_PROMPTS else ""
            row["Query Script"] = query_script(q)
            row["Response Words"] = len((row.get("Assistant Response") or "").split())
            row["Outcome Rule"], row["Style Version"] = rule, STYLE_VERSION
            row.update(style_counts(row))
            row["Safety Version"] = SAFETY_VERSION
            row.update(safety_flags(row.get("User Query")))
            row["Intent Version"] = INTENT_VERSION + "+" + lexicon()["version"]
            row["Query Intent"], row["Query Form"] = intent_of(q)
            row["Query Page"], row["Query Category"], row["Query Schemes"] = topic_of(q)
            # topic layer (brief §75): a question naming no page takes its category from its topic; Category Source says which
            row["Derivation Version"] = DERIVATION_VERSION
            row["Answer Templates"] = answer_templates(row.get("Assistant Response"))
            row["Answer Orgs"] = answer_orgs(row.get("Assistant Response"))
            try: day = datetime.strptime((row.get("Timestamp") or "").strip(), "%b %d, %Y %H:%M").date().isoformat()
            except ValueError: day = "9999-12-31"
            row["Answer Figures"], row["Answer Figures Matched"], row["Answer Figures Unmatched"], row["Answer Figures Unverifiable"] = check_figures(row.get("Assistant Response"), row.get("Citations"), day)
            row["Query Topic"], tcat = question_topic(q)
            if row["Query Category"]: row["Category Source"] = "page"
            elif tcat: row["Query Category"], row["Category Source"] = tcat, "topic"
            else: row["Category Source"] = ""
            if row["Starter Prompt"]: counts["(starter prompt)"] = counts.get("(starter prompt)", 0) + 1
            w.writerow(row)
            n += 1
    return n, keep, dropped, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--out-dir", help="directory for the redacted files (default: beside each input)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output file")
    ap.add_argument("--write-templates", metavar="PATH", help="write the TEMPLATES list (id, family, pattern) as JSON for the dashboard, then exit")
    a = ap.parse_args()
    if a.write_templates:
        json.dump({"_comment": "The bot's fixed-wording templates (brief §75): sentences the answering model is told to use, found as sentences in 200+ answers and 50+ conversations. "
                               "redact_feed.py records which an answer carries; make_usage.py counts them per day (answer-templates-daily.csv). Configuration, not citizen text.",
                   "derivation_version": DERIVATION_VERSION, "templates": [{"id": t, "family": f, "pattern": p} for t, f, p in TEMPLATES],
                   "organisations": [{"id": o, "family": f, "pattern": p} for o, f, p in ORGS]},
                  open(a.write_templates, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(a.write_templates, "a").write("\n")
        print(f"wrote {a.write_templates}: {len(TEMPLATES)} templates, {len(ORGS)} organisations, derivation {DERIVATION_VERSION}"); return
    if lexicon()["derivation"] and lexicon()["derivation"] != DERIVATION_VERSION:
        sys.exit(f"derivation version mismatch: redact_feed.py {DERIVATION_VERSION}, question-lexicon.json {lexicon()['derivation']}; bump both together (brief §75)")
    for f in a.files:
        dst = out_name(f, a.out_dir)
        if os.path.abspath(dst) == os.path.abspath(f):
            sys.exit(f"refusing to overwrite the input: {f}")
        if os.path.exists(dst) and not a.force:
            sys.exit(f"{dst} exists; pass --force to overwrite")
        n, keep, dropped, counts = redact(f, dst)
        missing = [c for c in DROP if c not in dropped]
        print(f"{f}: {n} rows -> {dst}")
        print(f"  outcomes (rules {OUTCOME_RULES_VERSION}): " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
        print(f"  dropped: {', '.join(dropped) or 'nothing'}" + (f"  (not present: {', '.join(missing)})" if missing else ""))
        print(f"  kept:    {', '.join(keep)}")


if __name__ == "__main__":
    main()
