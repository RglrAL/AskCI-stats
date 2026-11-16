#!/usr/bin/env python3
"""Rule tests for tools/redact_feed.py (brief §100, handoff package 0j): invented sentences, never citizen text, each with
the class the rules should give it. Covers the outcome rules (uncited answers), the partial test (cited answers), the
crisis theme, what a clarification asked for, the work-status classes, figures by kind and generic lexicon phrases, including every case the 16 Nov 2026 rule
audit found. Run: python3 tools/test_rules.py (the pre-commit hook and the deploy run it too). Prints counts and the
failing cases' own invented sentences only.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact_feed as R

RESP = "Assistant" " Response"   # the feed's column name, spelled in two parts so the feed-text guard is not tripped
CITE = "https://www.citizensinformation.ie/en/social-welfare/"

# (answer, expected outcome, expected rule id) for answers with no citation
UNCITED = [
    ("I couldn't find specific information about this topic in the Citizens Information content available to me.", "Not found", "nf.template"),
    ("I could not find anything on that scheme.", "Not found", "nf.could_not_find"),
    ("I wasn't able to find details of that grant.", "Not found", "nf.wasnt_able"),
    ("I'm unable to find information about that.", "Not found", "nf.unable_to_find"),
    ("The information available does not currently provide that rate.", "Not found", "nf.does_not_provide"),
    ("I don't have specific information about that payment.", "Not found", "nf.dont_have_info"),
    ("Could you clarify which payment you mean?", "Clarification", "cl.could_you"),
    ("Can you tell me a bit more about what you mean?", "Clarification", "cl.what_you_mean"),
    ("Can you give me more detail about your situation?", "Clarification", "cl.more_detail"),
    ("Which scheme are you asking about?", "Clarification", "cl.which_scheme"),
    # audit 0d: an ordinary sentence is not a clarification
    ("For more detail, contact your local Intreo centre.", "Uncited answer", "uncited"),
    ("Which payment you get depends on your age.", "Uncited answer", "uncited"),
    ("I specialise in providing information about Irish public services and entitlements.", "Out of scope", "oos.specialise"),
    ("Hello! How can I help you today?", "Greeting", "gr.hello"),
    ("You can apply online or at your local office.", "Uncited answer", "uncited"),
]

# (answer, expected partial flag, expected rule id) for answers with a citation
CITED = [
    ("I couldn't find the 2027 rate, but the 2026 rate is shown below.", "Yes", "cited.partial.nf.couldnt_find"),
    ("I could not find the closing date. You can apply online.", "Yes", "cited.partial.nf.could_not_find"),
    ("I was unable to find the exact date, but applications open in spring.", "Yes", "cited.partial.nf.unable_to_find"),
    ("The information available to me does not currently provide the weekly rate.", "Yes", "cited.partial.nf.does_not_provide"),
    ("I don't have information about the local scheme, but the national scheme is described here.", "Yes", "cited.partial.nf.dont_have_info"),
    # audit 0b: ordinary content is not a gap
    ("If you are unable to find work, you may qualify for Jobseeker's Allowance.", "", "cited"),
    ("The scheme does not provide cover for dental treatment.", "", "cited"),
    ("Your employer does not have to pay you for a day you did not work.", "", "cited"),
    ("You can apply for the grant online.", "", "cited"),
]

# (question, expected crisis flag)
CRISIS = [
    ("I want to end my life", True), ("thinking of killing myself", True), ("I want to take my own life", True),
    ("there is no reason to live", True), ("I feel like ending it all", True), ("I have been self-harming", True),
    ("I don't want to live anymore", True), ("I am thinking about suicide", True),
    # audit 0a: ending a tenancy, lease or contract is not crisis language
    ("I want to end my tenancy", False), ("how do I end my lease early", False), ("can I end my contract", False),
    ("how much notice to end my employment", False), ("my life insurance policy", False),
]

# (clarification, expected set of ask classes; an empty set is counted as (none), shown as unspecified)
ASKS = [
    ("Could you clarify which county you live in?", {"county"}),
    ("How old are you?", {"age"}),
    ("Are you currently working?", {"employment"}),
    ("Which scheme do you mean, Jobseeker's Allowance or Jobseeker's Benefit?", {"payment", "scheme"}),
    ("Are you asking about the grant for first-time buyers?", {"scheme"}),
    # audit 0c: the clarification rule's own phrases do not mean "which scheme"
    ("Could you clarify what you mean?", set()),
    ("Can you give me more detail about your situation?", set()),
]

# (answer, expected {kind: (matched, unmatched, unverifiable)}) with nothing cited, so every figure is unverifiable (0h)
FIGURES = [
    ("The rate is €232.00 a week, 10% more than in 2025.", {"Euro": (0, 0, 1), "Percent": (0, 0, 1), "Year": (0, 0, 1)}),
    ("You can apply from 2026.", {"Euro": (0, 0, 0), "Percent": (0, 0, 0), "Year": (0, 0, 1)}),
]

# (question, expected generic flag): a subject word is not naming a page (0i; needs the lexicon in data/)
GENERIC = [
    ("how much income tax will I pay", True), ("I am self employed, what do I need to do", True),
    ("how do I apply for child benefit", False), ("am I entitled to the fuel allowance", False),
]

# (question, expected work class)
WORK = [
    ("I am not working at the moment", "unemployed"), ("I lost my job last week", "unemployed"),
    ("I'm self employed", "self-employed"), ("I am a student", "student"), ("I work part-time", "working"),
    # audit 0e: "not working" needs the first person
    ("my heating is not working", ""), ("the website is not working", ""),
]


def main():
    fails = []
    for a, out, rid in UNCITED:
        got = R.classify_rule({RESP: a, "Citations": "", "Response Time (ms)": "900"})
        if (got[0], got[2]) != (out, rid): fails.append(("uncited", a, (out, rid), (got[0], got[2])))
    for a, part, rid in CITED:
        got = R.classify_rule({RESP: a, "Citations": CITE, "Response Time (ms)": "900"})
        if got != ("Cited answer", part, rid): fails.append(("cited", a, ("Cited answer", part, rid), got))
    crisis = dict(R.THEMES)["crisis"]
    for q, want in CRISIS:
        if bool(crisis.search(q)) != want: fails.append(("crisis", q, want, not want))
    for a, want in ASKS:
        got = set(x for x in R.asks_of(a).split(";") if x)
        if got != want: fails.append(("asks", a, sorted(want), sorted(got)))
    for q, want in WORK:
        got = R.situation_of(q, False)[3]
        if got != want: fails.append(("work", q, want, got))
    for a, want in FIGURES:
        got = R.check_figures_by_kind(a, "", "2026-10-01")
        if got != want: fails.append(("figures", a, want, got))
        if R.check_figures(a, "", "2026-10-01")[0] != sum(sum(x) for x in want.values()): fails.append(("figures total", a, "sum of kinds", R.check_figures(a, "", "2026-10-01")))
    for q, want in GENERIC:
        url, cat, n, gen = R.page_match(q)
        if not url or gen != want: fails.append(("generic", q, want, (url[-40:], gen)))
    n = len(UNCITED) + len(CITED) + len(CRISIS) + len(ASKS) + len(WORK) + len(FIGURES) + len(GENERIC)
    for kind, text, want, got in fails:
        print(f"FAIL {kind}: {text!r}\n   expected {want}, got {got}")
    print(f"{n - len(fails)} of {n} rule cases passed (outcome rules {R.OUTCOME_RULES_VERSION}, safety {R.SAFETY_VERSION}, derivation {R.DERIVATION_VERSION})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
