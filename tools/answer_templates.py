#!/usr/bin/env python3
"""The bot's fixed wording (brief §75, response layer 1): find it, and count it per day.

The answering model is told to use fixed sentences for some situations: a no-results line, an out-of-scope line, a
greeting, a sign-off, a safety signpost. Those sentences are configuration, not citizen text, so their names and counts
are publishable, and a change in which ones appear is the trace of a prompt change that no model event explains.

    --discover FEEDS [--min N] [--since DATE]
        local: the sentences that appear verbatim in N+ answers (default 200) and 50+ conversations, after
        normalising case, whitespace, digits and links. The thresholds are the privacy rule: a sentence repeated that
        often across that many conversations is the bot's own, not an echo of what one person typed. Prints the
        sentence, how many answers carry it, how many conversations, first and last date, and the outcome split.
        Nothing under the thresholds is printed.

The template list itself lives in redact_feed.py (TEMPLATES), named by hand from this report, and the redaction writes
an "Answer Templates" column; make_usage.py counts it per day into answer-templates-daily.csv.
"""
import argparse, csv, re, sys, collections as C
from datetime import datetime

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
TS = "%b %d, %Y %H:%M"
SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
URL = re.compile(r"https?://\S+|\[[^\]]*\]\([^)]*\)")


def norm_sentence(s):
    s = URL.sub(" <link> ", s)
    s = re.sub(r"\d+", "#", s.lower())
    s = re.sub(r"[*_`#>]+", " ", s)
    return re.sub(r"\s+", " ", s).strip(" -•")


def discover(feeds, min_answers, min_convs, since):
    seen = set(); n = 0
    answers = C.Counter(); convs = C.defaultdict(set); first = {}; last = {}; outs = C.defaultdict(C.Counter)
    for f in feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID"), row.get("Turn #"))
                if k in seen: continue
                seen.add(k)
                try: d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date().isoformat()
                except ValueError: continue
                if since and d < since: continue
                a = row.get("Assistant Response") or ""
                if not a.strip(): continue
                n += 1
                sents = {norm_sentence(s) for s in SPLIT.split(a) if len(s.strip()) >= 25}
                for s in sents:
                    if len(s) < 25 or len(s) > 300: continue
                    answers[s] += 1; convs[s].add(k[0])
                    first[s] = min(first.get(s, d), d); last[s] = max(last.get(s, d), d)
                    outs[s][(row.get("Question Type") or "").strip() or "?"] += 1
    keep = [(s, c) for s, c in answers.items() if c >= min_answers and len(convs[s]) >= min_convs]
    keep.sort(key=lambda sc: -sc[1])
    print(f"{n:,} answers read; {len(keep)} sentences in {min_answers}+ answers and {min_convs}+ conversations (nothing below the thresholds is printed)\n")
    for s, c in keep:
        print(f"{c:7,}  convs {len(convs[s]):6,}  {first[s]} .. {last[s]}  {s}")
    return keep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", nargs="+", metavar="FEED", required=True)
    ap.add_argument("--min", type=int, default=200); ap.add_argument("--min-convs", type=int, default=50); ap.add_argument("--since")
    a = ap.parse_args()
    discover(a.discover, a.min, a.min_convs, a.since)


if __name__ == "__main__":
    main()
