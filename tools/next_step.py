#!/usr/bin/env python3
"""What people do next, after each kind of answer (brief §53, step 3).

A label can be checked without reading the answer by how people respond to it. If, after 14 September, people
treat "not found" answers the way they used to treat cited answers (they move on, or end satisfied, rather than
rephrase), the label is suspect; if they respond as they always did to a not-found answer, the rise is real.
This is evidence, not ground truth: the hand-labelled sample is that.

For every answer in a mature conversation (no turn within 24 hours of the end of the data), by model era and by
answer class (cited, not partial · partial · not found · clarification):
  Ended       it was the conversation's last turn
  Rephrased   the next question is typed and shares at least half its words with this one (Jaccard on word sets,
              lower case, words of 3+ letters): the person asked the same thing again. Computed here from the raw
              text; only the count leaves this machine
  Typed / Chip / New topic   the next question's type
  Within 1 min   the next question came in the same or the next minute (timestamps are to the minute)
  Next cited  the next answer cited a page
  Disliked    this answer got a thumbs down
Each share comes with a 95% Wilson interval. The eras are the model or prompt eras in events.json, as the dashboard's
era scorecard cuts them (brief §58). The last block puts each class in each later era beside every class of the
earlier eras, to see which profile it resembles.

It writes answer-next-daily.csv (Date, Class, Answers, Ended, Rephrased, NextTyped, NextChip, NextNew, Within1m,
NextCited, Disliked) for the dashboard: counts only, by the day of the answer.

Usage:
    python3 tools/next_step.py exports/qa-feed_*.csv              # print, and write answer-next-daily.csv here
    python3 tools/next_step.py FEEDS --no-write
"""
import argparse, csv, json, os, re, sys, collections as C
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_feed import classify, normalise_query

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = "%b %d, %Y %H:%M"
Z = 1.96
CLASSES = ["cited", "partial", "notfound", "clarification"]
NAMES = {"cited": "cited, not partial", "partial": "partial", "notfound": "not found", "clarification": "clarification"}
COLS = ["Answers", "Ended", "Rephrased", "NextTyped", "NextChip", "NextNew", "Within1m", "NextCited", "Disliked"]
WORD = re.compile(r"[a-z]{3,}")


def eras(first, last):
    """Model or prompt eras from events.json, as the dashboard's era scorecard cuts them (brief §58): a confirmed model
    or prompt event's `era` names the era it starts, `era_before` on the first names the era before it; the change
    day and the event's settling days belong to neither."""
    ev = json.load(open(os.path.join(REPO, "events.json")))["events"]
    cuts = sorted((e for e in ev if e.get("status") == "confirmed" and e.get("kind") in ("model", "prompt") and len(e.get("start", "")) == 10), key=lambda e: e["start"])
    if not cuts:
        return [("all", first, last)]
    out = [(cuts[0].get("era_before") or "before " + cuts[0]["start"], first, date.fromisoformat(cuts[0]["start"]) - timedelta(days=1))]
    for i, e in enumerate(cuts):
        a = date.fromisoformat(e["end"] if len(e.get("end") or "") == 10 else e["start"]) + timedelta(days=1)
        b = date.fromisoformat(cuts[i + 1]["start"]) - timedelta(days=1) if i + 1 < len(cuts) else last
        out.append((e.get("era") or "from " + e["start"], a, b))
    return [x for x in out if x[1] <= x[2]]


def wilson(k, n):
    if not n:
        return None, None
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d; h = Z * ((p * (1 - p) / n + Z * Z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def klass(o, partial):
    if o == "Cited answer":
        return "partial" if partial else "cited"
    return {"Not found": "notfound", "Clarification": "clarification"}.get(o)


def words(q):
    return set(WORD.findall(normalise_query(q)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    seen = set(); conv = C.defaultdict(list); last_ts = None
    for f in a.feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if k in seen:
                    continue
                seen.add(k)
                try:
                    t = datetime.strptime((row.get("Timestamp") or "").strip(), TS); tn = int(k[1])
                except ValueError:
                    continue
                o, partial = classify(row)
                conv[k[0]].append((tn, t, klass(o, partial), o == "Cited answer", (row.get("Question Type") or "").strip(),
                                   words(row.get("User Query") or ""), (row.get("Feedback") or "").strip().lower() == "dislike"))
                last_ts = t if last_ts is None or t > last_ts else last_ts
    cutoff = last_ts - timedelta(hours=24)
    ERAS = eras(min(t[1] for ts in conv.values() for t in ts).date(), cutoff.date())
    daily = C.defaultdict(C.Counter)
    for cid, turns in conv.items():
        turns.sort(key=lambda x: x[0])
        if turns[-1][1] > cutoff:
            continue   # not mature: the person may still come back
        for i, (tn, t, cl, cited, qt, ws, disl) in enumerate(turns):
            if not cl:
                continue
            e = daily[(t.date(), cl)]; e["Answers"] += 1; e["Disliked"] += disl
            if i == len(turns) - 1:
                e["Ended"] += 1; continue
            nx = turns[i + 1]
            e["NextTyped"] += nx[4] == "user_followup"; e["NextChip"] += nx[4] == "suggested_followup"; e["NextNew"] += nx[4] == "new_topic"
            e["Within1m"] += (nx[1] - t) <= timedelta(minutes=1)
            e["NextCited"] += nx[3]
            if nx[4] != "suggested_followup" and ws and nx[5]:
                e["Rephrased"] += len(ws & nx[5]) / len(ws | nx[5]) >= 0.5

    def era_sum(era, cl):
        _, x, y = era; s = C.Counter()
        for (d, c), e in daily.items():
            if c == cl and x <= d <= y:
                s.update(e)
        return s

    S = {(era[0], cl): era_sum(era, cl) for era in ERAS for cl in CLASSES}
    f = lambda k, n: "—" if not n else f"{k / n * 100:5.1f}%"
    print(f"Mature conversations only (last turn before {cutoff:%d %b %Y %H:%M}). Shares of answers; 95% interval in brackets.\n")
    for cl in CLASSES:
        print(f"== after a {NAMES[cl]} answer")
        print("   " + f"{'':14}" + "".join(f"{x:>24}" for x in ("answers",) + tuple(c for c in COLS[1:])))
        for era in ERAS:
            s = S[(era[0], cl)]; n = s["Answers"]
            cells = [f"{n:>24}"]
            for c in COLS[1:]:
                lo, hi = wilson(s[c], n)
                cells.append(f"{f(s[c], n)} ({'—' if lo is None else f'{lo*100:.0f}–{hi*100:.0f}'})".rjust(24))
            print(f"   {era[0]:14}" + "".join(cells))
        print()
    # which earlier profile does each 5.4 class look like? Distance over the behaviour shares (ended, rephrased,
    # typed, chip, new topic, within 1 min, next cited)
    keys = ["Ended", "Rephrased", "NextTyped", "NextChip", "NextNew", "Within1m", "NextCited"]
    prof = lambda s: [s[k] / s["Answers"] if s["Answers"] else 0 for k in keys]
    dist = lambda p, q: sum(abs(x - y) for x, y in zip(p, q)) / 2
    print("== Which earlier profile each class resembles (half the summed absolute difference in the shares above; 0 = identical)")
    names = [e[0] for e in ERAS]
    refs = [(f"{e} {NAMES[c]}", prof(S[(e, c)])) for e in names[:-1] for c in CLASSES if S[(e, c)]["Answers"]]
    print("   " + f"{'':28}" + "".join(f"{r[0][:22]:>24}" for r in refs))
    for era in names[1:]:
        for cl in CLASSES:
            p = prof(S[(era, cl)])
            print(f"   {era + ' ' + NAMES[cl]:28}" + "".join(f"{dist(p, r[1]):>24.3f}" for r in refs))
    if not a.no_write:
        out = os.path.join(REPO, "answer-next-daily.csv")
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["Date", "Class"] + COLS)
            for (d, c), e in sorted(daily.items()):
                w.writerow([d.isoformat(), c] + [e[k] for k in COLS])
        print(f"\nwrote {os.path.relpath(out, REPO)} ({len(daily)} rows)")


if __name__ == "__main__":
    main()
