#!/usr/bin/env python3
"""How much traffic a cache of fixed questions would cover (brief §53 step 8, §63). Runs on the RAW feed, locally.

A cache keyed on the exact question text can serve a question only if that text recurs. This measures, per month:
  - first turns, all turns, and first turns that are a configured starter prompt (the chips: a cache would cover them all);
  - distinct normalised first-turn questions, and how many were asked twice or more;
  - the share of first turns covered by the top 10, 25, 50, 100 and 250 most-asked first-turn texts (chips included).
Normalisation is redact_feed.normalise_query: lower case, straight apostrophes, one space, no trailing punctuation.
Only counts leave this machine, in repeat-questions-monthly.csv. The most common non-chip texts and the most
clicked suggested follow-ups are printed here for the analyst and never written.

Usage:
    python3 tools/cache_coverage.py exports/qa-feed_*.csv              # writes repeat-questions-monthly.csv in the repo
    python3 tools/cache_coverage.py FEEDS --no-write --show 15
"""
import argparse, csv, os, sys, collections as C
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_feed import normalise_query, STARTER_PROMPTS, classify

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = "%b %d, %Y %H:%M"
TOPS = [10, 25, 50, 100, 250]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+"); ap.add_argument("--no-write", action="store_true"); ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()
    seen = set(); first = C.defaultdict(C.Counter); turns = C.Counter(); sugg = C.defaultdict(C.Counter); sugg_out = C.defaultdict(C.Counter)
    for f in a.feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if k in seen: continue
                seen.add(k)
                try: m = datetime.strptime((row.get("Timestamp") or "").strip(), TS).strftime("%Y-%m")
                except ValueError: continue
                turns[m] += 1
                q = normalise_query(row.get("User Query") or "")
                if k[1] == "1": first[m][q] += 1
                if (row.get("Question Type") or "").strip() == "suggested_followup":
                    sugg[m][q] += 1; sugg_out[q][classify(row)[0]] += 1
    cols = ["Month", "Turns", "FirstTurns", "StarterFirstTurns", "DistinctFirstTurnTexts", "TextsAskedTwicePlus", "FirstTurnsOnRepeatedTexts"] + [f"Top{n}" for n in TOPS] + ["SuggestedClicks", "DistinctSuggestedTexts", "SuggestedTop25"]
    rows = []
    print(f"{'month':8}{'turns':>8}{'first':>8}{'chips':>7}{'distinct':>9}{'repeat':>8}" + "".join(f"{'top'+str(n):>8}" for n in TOPS) + f"{'sugg':>7}{'sTop25':>8}")
    for m in sorted(turns):
        c = first[m]; ft = sum(c.values()); ch = sum(v for q, v in c.items() if q in STARTER_PROMPTS)
        rep = {q: v for q, v in c.items() if v >= 2}; ranked = [v for q, v in c.most_common()]
        tops = [sum(ranked[:n]) for n in TOPS]
        sc = sugg[m]; st = sum(sc.values()); s25 = sum(v for q, v in sc.most_common(25))
        rows.append([m, turns[m], ft, ch, len(c), len(rep), sum(rep.values())] + tops + [st, len(sc), s25])
        print(f"{m:8}{turns[m]:>8}{ft:>8}{ch:>7}{len(c):>9}{sum(rep.values()):>8}" + "".join(f"{t / ft * 100 if ft else 0:>7.1f}%" for t in tops) + f"{st:>7}{s25 / st * 100 if st else 0:>7.1f}%")
    if a.show:
        allf = C.Counter(); [allf.update(c) for c in first.values()]
        print(f"\nmost asked first-turn texts that are not configured chips (all months; local only):")
        for q, v in [(q, v) for q, v in allf.most_common(200) if q not in STARTER_PROMPTS][:a.show]: print(f"   {v:6}  {q[:90]}")
        alls = C.Counter(); [alls.update(c) for c in sugg.values()]
        print(f"\nmost clicked suggested follow-ups (all months; local only), with their own outcome:")
        for q, v in alls.most_common(a.show):
            o = sugg_out[q]; print(f"   {v:6}  cited {o['Cited answer'] / v * 100:3.0f}%  nf {o['Not found'] / v * 100:3.0f}%  {q[:80]}")
    if not a.no_write:
        p = os.path.join(REPO, "repeat-questions-monthly.csv")
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
        print(f"\nwrote {os.path.relpath(p, REPO)}")


if __name__ == "__main__":
    main()
