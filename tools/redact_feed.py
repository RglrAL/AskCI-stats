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
import argparse, csv, os, sys

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
                                                          "Outcome Rule", "Style Version"] + list(STYLE) + ["Answer Signoff"]
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
            if row["Starter Prompt"]: counts["(starter prompt)"] = counts.get("(starter prompt)", 0) + 1
            w.writerow(row)
            n += 1
    return n, keep, dropped, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out-dir", help="directory for the redacted files (default: beside each input)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output file")
    a = ap.parse_args()
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
