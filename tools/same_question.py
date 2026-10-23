#!/usr/bin/env python3
"""Same question, before and after a change (brief §53, step 2).

Holding the question fixed removes the question mix from a before/after comparison. Two sets:
  1. Starter prompts: the configured chip texts (redact_feed.STARTER_PROMPTS), asked as a first turn.
  2. Repeated typed questions: first-turn questions (not chips) whose normalised text was asked at least --min
     times in BOTH windows. Matched on this machine from the raw feed; only counts leave it.

For each set and window: turns, cited, not found, clarification, partial, with 95% Wilson intervals, and the
difference in each rate with a 95% Newcombe interval. The repeated set is also compared question by question
(each question weighted equally), so a few very common questions cannot carry the result.

First, a check that the fixed input really is fixed: each chip's first-turn count by week (a chip whose text
changed drops to zero), and any first-turn text asked 30+ times in one week that is not a configured chip
(a new or reworded chip). Those texts are printed: at that frequency they are chips, not citizens' questions.

It proves less than it seems: a fixed question rules out the question mix, not the outcome rules. A change in the
rules' reading of new wording and a change in the answers look the same here.

Usage:
    python3 tools/same_question.py exports/qa-feed_*.csv
    python3 tools/same_question.py FEEDS --before 2026-08-14:2026-09-13 --after 2026-09-14:2026-10-13 --min 3
"""
import argparse, csv, os, sys, collections as C
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_feed import classify, normalise_query, STARTER_PROMPTS

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
TS = "%b %d, %Y %H:%M"
Z = 1.96


def wilson(k, n):
    if not n:
        return (None, None)
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d; h = Z * ((p * (1 - p) / n + Z * Z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(k1, n1, k2, n2):
    """95% interval for p2 - p1 (Newcombe's hybrid score method)."""
    if not n1 or not n2:
        return (None, None)
    p1, p2 = k1 / n1, k2 / n2; l1, u1 = wilson(k1, n1); l2, u2 = wilson(k2, n2)
    d = p2 - p1
    return d - ((p2 - l2) ** 2 + (u1 - p1) ** 2) ** 0.5, d + ((u2 - p2) ** 2 + (p1 - l1) ** 2) ** 0.5


def span(s):
    a, b = s.split(":")
    return date.fromisoformat(a), date.fromisoformat(b)


def outcome_key(o, partial):
    return {"Cited answer": "partial" if partial else "cited_clean", "Not found": "notfound", "Clarification": "clar"}.get(o, "other")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+")
    ap.add_argument("--before", default="2026-08-14:2026-09-13")
    ap.add_argument("--after", default="2026-09-14:2026-10-13")
    ap.add_argument("--min", type=int, default=3, help="a typed question must be asked this often in each window")
    a = ap.parse_args()
    W = {"before": span(a.before), "after": span(a.after)}
    seen = set()
    chip_week = C.defaultdict(C.Counter)          # week -> chip -> first turns
    text_week = C.defaultdict(C.Counter)          # week -> normalised first-turn text -> n (for the chip check)
    sets = {s: {w: C.Counter() for w in W} for s in ("chips", "typed")}
    per_q = {w: C.defaultdict(C.Counter) for w in W}   # normalised typed question -> outcome counts
    chip_rows = {w: C.defaultdict(C.Counter) for w in W}
    for f in a.feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if k in seen:
                    continue
                seen.add(k)
                if k[1] != "1":
                    continue
                try:
                    d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date()
                except ValueError:
                    continue
                q = normalise_query(row.get("User Query") or "")
                if not q:
                    continue
                wk = d - timedelta(days=d.weekday())
                text_week[wk][q] += 1
                chip = q in STARTER_PROMPTS
                if chip:
                    chip_week[wk][q] += 1
                win = next((n for n, (x, y) in W.items() if x <= d <= y), None)
                if not win:
                    continue
                o, partial = classify(row)
                if o in ("Greeting", "Error", "Out of scope"):
                    continue   # scored turns only, as the dashboard's rates
                key = outcome_key(o, partial)
                if chip:
                    sets["chips"][win]["n"] += 1; sets["chips"][win][key] += 1
                    chip_rows[win][q]["n"] += 1; chip_rows[win][q][key] += 1
                else:
                    per_q[win][q]["n"] += 1; per_q[win][q][key] += 1

    # ── the fixed input: chips by week, and anything chip-like that is not configured ──
    weeks = sorted(chip_week.keys() | text_week.keys())
    print("== Starter prompts as a first turn, by week (a reworded chip drops to zero)")
    chips = sorted(STARTER_PROMPTS)
    print("   week        " + " ".join(f"c{i + 1:<4}" for i in range(len(chips))) + "   (" + "; ".join(f"c{i + 1}={c}" for i, c in enumerate(chips)) + ")")
    for wk in weeks:
        if wk < date(2026, 4, 27):
            continue
        print(f"   {wk}  " + " ".join(f"{chip_week[wk][c]:<5}" for c in chips))
    odd = [(wk, t, n) for wk in weeks for t, n in text_week[wk].items() if n >= 30 and t not in STARTER_PROMPTS]
    print("\n== First-turn texts asked 30+ times in one week that are not configured chips: " + (str(len(odd)) if odd else "none"))
    for wk, t, n in sorted(odd)[:40]:
        print(f"   {wk}  {n:>4}  {t[:90]}")

    def line(label, c1, c2, key):
        n1, n2 = c1["n"], c2["n"]
        k1 = sum(c1[x] for x in key); k2 = sum(c2[x] for x in key)
        p1 = k1 / n1 if n1 else None; p2 = k2 / n2 if n2 else None
        lo, hi = newcombe(k1, n1, k2, n2)
        f = lambda p: "—" if p is None else f"{p * 100:5.1f}%"
        w1, w2 = wilson(k1, n1), wilson(k2, n2)
        print(f"   {label:24} {k1:>6}/{n1:<6} {f(p1)} ({f(w1[0])}–{f(w1[1])})   {k2:>6}/{n2:<6} {f(p2)} ({f(w2[0])}–{f(w2[1])})   "
              + ("—" if lo is None else f"{(p2 - p1) * 100:+5.1f} pts ({lo * 100:+.1f} to {hi * 100:+.1f})"))

    RATES = [("cited (any)", ("cited_clean", "partial")), ("cited, not partial", ("cited_clean",)), ("partial", ("partial",)),
             ("not found", ("notfound",)), ("clarification", ("clar",))]

    def block(title, c1, c2):
        print(f"\n== {title}")
        print(f"   {'rate':24} {'before ' + a.before:>34}   {'after ' + a.after:>34}   change, 95% interval")
        for lbl, key in RATES:
            line(lbl, c1, c2, key)

    block("1. Starter prompts (scored first turns)", sets["chips"]["before"], sets["chips"]["after"])
    for ch in chips:
        b, af = chip_rows["before"][ch], chip_rows["after"][ch]
        if b["n"] and af["n"]:
            print(f"   · {ch[:60]:60} n {b['n']}→{af['n']}: cited {sum(b[x] for x in ('cited_clean', 'partial')) / b['n'] * 100:.0f}% → {sum(af[x] for x in ('cited_clean', 'partial')) / af['n'] * 100:.0f}%,"
                  f" not partial {b['cited_clean'] / b['n'] * 100:.0f}% → {af['cited_clean'] / af['n'] * 100:.0f}%")

    matched = [q for q in per_q["before"] if per_q["before"][q]["n"] >= a.min and per_q["after"].get(q, {}).get("n", 0) >= a.min]
    tb, ta = C.Counter(), C.Counter()
    for q in matched:
        tb.update(per_q["before"][q]); ta.update(per_q["after"][q])
    block(f"2. Typed first questions asked {a.min}+ times in both windows: {len(matched)} distinct questions (pooled)", tb, ta)
    # question by question: each question weighted equally; the share of questions whose rate went down, up or stayed
    for lbl, key in RATES[:2] + RATES[3:]:
        diffs = []
        for q in matched:
            b, af = per_q["before"][q], per_q["after"][q]
            diffs.append(sum(af[x] for x in key) / af["n"] - sum(b[x] for x in key) / b["n"])
        if diffs:
            m = sum(diffs) / len(diffs); sd = (sum((x - m) ** 2 for x in diffs) / max(1, len(diffs) - 1)) ** 0.5; se = sd / len(diffs) ** 0.5
            print(f"   per question, {lbl:20} mean change {m * 100:+5.1f} pts (95% {(m - Z * se) * 100:+.1f} to {(m + Z * se) * 100:+.1f}); "
                  f"down in {sum(x < 0 for x in diffs)}, up in {sum(x > 0 for x in diffs)}, same in {sum(x == 0 for x in diffs)}")
    print("\nCounts and rates only; no question text above except chip texts and chip-like repeats.")


if __name__ == "__main__":
    main()
