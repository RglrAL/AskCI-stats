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
                  Other, or None when the query has no letter. A script, not a language. The output still contains per-turn
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

OUTCOME_RULES_VERSION = "2026.10.08-1"
RX = {
    "not_found": re.compile(r"couldn't find|could not find|wasn't able to find|unable to find|no specific information|not find specific|don't have (specific )?information|does not (currently )?(provide|have)", re.I),
    "clarification": re.compile(r"could you (please )?(clarify|tell me|let me know)|what you mean|more detail|which (scheme|payment)", re.I),
    "out_of_scope": re.compile(r"specialise in providing information|specialize in providing information|can't help with that (particular )?topic|not able to help with that topic|outside (the )?scope", re.I),
    "greeting": re.compile(r"^(hello|hi)\b|how can i help|you're welcome|glad to help|glad to hear|glad you|glad i could", re.I),
}
URL_RE = re.compile(r'https?://[^\s,;|"]+')

# Starter-prompt chips (AGENT_BRIEF.md, 29 Sep 2026). Matched on first turns only, after
# normalisation. Versioned with the outcome rules; effective dates are not known yet.
STARTER_PROMPTS = {
    "what is auto-enrolment", "can i get help with low pay", "how much is maternity benefit",
    "what are the housing assistance payment (hap) limits", "how do i renew my passport",
    "how do i apply for the back to school clothing and footwear allowance",
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


def classify(row):
    """Return (outcome, partial) for one feed row. Text is read here and nowhere else."""
    resp = (row.get("Assistant Response") or "").translate(APOS).strip()
    rt = (row.get("Response Time (ms)") or "").strip()
    if resp == "" and rt in ("0", ""):
        return "Error", ""
    cites = len(URL_RE.findall(row.get("Citations") or ""))
    if cites >= 1:
        return "Cited answer", ("Yes" if RX["not_found"].search(resp) else "")
    if RX["not_found"].search(resp):
        return "Not found", ""
    if RX["clarification"].search(resp):
        return "Clarification", ""
    if RX["out_of_scope"].search(resp):
        return "Out of scope", ""
    if RX["greeting"].search(resp):
        return "Greeting", ""
    if (row.get("Flagged") or "").strip().lower() == "yes":
        return "Out of scope", ""
    return "Uncited answer", ""


def out_name(path, out_dir):
    base = os.path.basename(path)
    base = base.replace("qa-feed_", "qa-feed-redacted_", 1) if base.startswith("qa-feed_") else "redacted_" + base
    return os.path.join(out_dir or os.path.dirname(path) or ".", base)


def redact(src, dst):
    with open(src, encoding="utf-8-sig", newline="") as fi, open(dst, "w", encoding="utf-8", newline="") as fo:
        r = csv.DictReader(fi)
        keep = [c for c in r.fieldnames if c not in DROP] + ["Outcome", "Partial", "Outcome Rules", "Starter Prompt", "Query Script"]
        dropped = [c for c in r.fieldnames if c in DROP]
        w = csv.DictWriter(fo, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        n = 0; counts = {}
        for row in r:
            o, partial = classify(row)
            counts[o] = counts.get(o, 0) + 1
            if partial: counts["(partial)"] = counts.get("(partial)", 0) + 1
            row["Outcome"], row["Partial"], row["Outcome Rules"] = o, partial, OUTCOME_RULES_VERSION
            q = row.get("User Query") or ""
            nq = normalise_query(q)
            row["Starter Prompt"] = nq if (row.get("Turn #") or "").strip() == "1" and nq in STARTER_PROMPTS else ""
            row["Query Script"] = query_script(q)
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
