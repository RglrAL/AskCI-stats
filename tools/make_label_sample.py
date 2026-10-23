#!/usr/bin/env python3
"""Draw a blind, stratified sample of AskCI answers for people to label, to measure the outcome rules.

The outcome rules in redact_feed.py classify every answer from its wording (cited, not found, clarification ...).
From 14 Sep 2026 the cited rate fell from about 92% to 82% when the model changed; this sample tells whether the
answers changed or the rules misread the new model's wording (brief §48, Phase B step 0).

For each period (default: the month before and the month after 14 Sep) it draws answers stratified by the class the
rules gave them, so the rare classes have enough to say something: by default 20 cited, 10 partial (cited but says
something is missing), 10 not found and 10 clarification per period. score_labels.py weights the results back to the
real mix.

Run it on the RAW feed exports, on the analyst's machine. The labelling sheet holds citizens' questions and AskCI's
answers: it is written under exports/ (git-ignored) and must be handled as the feed itself is. Nothing it writes goes
into the dashboard; only score_labels.py's summary (accuracy figures, no text) does.

Outputs, in exports/labelling-<date>/ unless --out is given:
  label_sheet.csv          for the labeller: item, question, answer, cited pages, and blank columns to fill in.
                           No date, model or rule outcome: labelling is blind. Rows from both periods are shuffled.
  label_sheet_second.csv   the same for a second labeller, on a random subset (default 20) of the items, so the two
                           can be compared (agreement tells how much to trust the rest)
  key.csv                  item → period, rule outcome, date, and how many answers of that class the period held
                           (for weighting). Keep it away from the labellers until they finish.
  README.txt               the instructions and the allowed values

--starter TEXT --starter-n N adds N first-turn answers to that starter prompt from the after period (any class), as
their own stratum: the same question asked many times, so the labels say what changed on a fixed input (brief §55:
HAP limits went from 3% to 33% "partial"). They are scored separately, not weighted into the period mix.

Usage:
    python3 tools/make_label_sample.py ~/Downloads/qa-feed_20260929_*.csv ~/Downloads/qa-feed_20261023_*.csv
    python3 tools/make_label_sample.py FEEDS --before 2026-08-14:2026-09-13 --after 2026-09-14:2026-10-13 \\
        --per cited=20,partial=10,notfound=10,clarification=10 --double 20 --seed 2026
"""
import argparse, csv, os, random, sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_feed import classify, URL_RE, OUTCOME_RULES_VERSION, normalise_query   # the rules being measured, exactly as they run

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = "%b %d, %Y %H:%M"
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
WHAT_KIND = ["answered with a source", "answered but says something is missing", "says it couldn't find it",
             "asks to clarify", "declines as out of scope", "answered without a source", "other", "can't tell"]
ANSWERED = ["yes", "partly", "no", "can't tell"]


def stratum(outcome, partial):
    if outcome == "Cited answer":
        return "partial" if partial == "Yes" else "cited"
    return {"Not found": "notfound", "Clarification": "clarification"}.get(outcome)


def span(s):
    a, b = s.split(":")
    return date.fromisoformat(a), date.fromisoformat(b)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+", help="raw QA feed exports (qa-feed_*.csv), with the text columns")
    ap.add_argument("--before", default="2026-08-14:2026-09-13")
    ap.add_argument("--after", default="2026-09-14:2026-10-13")
    ap.add_argument("--per", default="cited=20,partial=10,notfound=10,clarification=10")
    ap.add_argument("--double", type=int, default=20, help="items also given to a second labeller")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--starter", default="what are the housing assistance payment (hap) limits", help="a starter prompt to sample as its own stratum from the after period ('' for none)")
    ap.add_argument("--starter-n", type=int, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    periods = {"before": span(a.before), "after": span(a.after)}
    per = {k: int(v) for k, v in (x.split("=") for x in a.per.split(","))}

    seen, pool = set(), {p: {s: [] for s in per} for p in periods}
    starter = normalise_query(a.starter) if a.starter else None; spool = []
    for f in a.feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            r = csv.DictReader(fh)
            if "Assistant Response" not in (r.fieldnames or []):
                sys.exit(f"{f}: no Assistant Response column (this needs the raw export, not the redacted one)")
            for row in r:
                key = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date()
                except ValueError:
                    continue
                p = next((n for n, (f0, t0) in periods.items() if f0 <= d <= t0), None)
                if not p:
                    continue
                o, partial = classify(row); s = stratum(o, partial)
                if starter and p == "after" and (row.get("Turn #") or "").strip() == "1" and normalise_query(row.get("User Query")) == starter:
                    spool.append((d, row, s or o)); continue   # the fixed question is its own stratum, never double-counted
                if s in per:
                    pool[p][s].append((d, row))

    rnd = random.Random(a.seed)
    items, key = [], []
    for p in periods:
        for s, n in per.items():
            got = pool[p][s]
            pick = rnd.sample(got, min(n, len(got)))
            for d, row in pick:
                items.append(row)
                key.append({"period": p, "rule_outcome": s, "date": d.isoformat(), "stratum_population": len(got), "stratum_sample": len(pick), "stratum": s})
    spick = rnd.sample(spool, min(a.starter_n, len(spool))) if spool else []
    for d, row, s in spick:
        items.append(row)
        key.append({"period": "after", "rule_outcome": s, "date": d.isoformat(), "stratum_population": len(spool), "stratum_sample": len(spick), "stratum": "starter"})
    order = list(range(len(items)))
    rnd.shuffle(order)

    out = a.out or os.path.join(REPO, "exports", f"labelling-{date.today().isoformat()}")
    os.makedirs(out, exist_ok=True)
    cols = ["item", "question", "answer", "cited_pages", "what_kind", "answered", "detail_on_page", "notes"]

    def sheet(path, idx):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols)
            for i in idx:
                row = items[i]
                w.writerow([f"A{i + 1:03d}", (row.get("User Query") or "").strip(), (row.get("Assistant Response") or "").strip(),
                            "\n".join(URL_RE.findall(row.get("Citations") or "")), "", "", "", ""])

    sheet(os.path.join(out, "label_sheet.csv"), order)
    second = rnd.sample(order, min(a.double, len(order)))
    rnd.shuffle(second)
    sheet(os.path.join(out, "label_sheet_second.csv"), second)
    with open(os.path.join(out, "key.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["item", "period", "rule_outcome", "date", "stratum_population", "stratum_sample", "rules_version", "stratum"])
        for i, k in enumerate(key):
            w.writerow([f"A{i + 1:03d}", k["period"], k["rule_outcome"], k["date"], k["stratum_population"], k["stratum_sample"], OUTCOME_RULES_VERSION, k["stratum"]])
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"""AskCI answer labelling ({len(items)} answers; a second sheet of {len(second)} for a second labeller)

This folder holds citizens' questions and AskCI's answers. Handle it as the QA feed itself is handled, and delete
it when the labels are scored. Do not open key.csv until labelling is finished.

For each row of label_sheet.csv, read the question and the answer, then fill in:

  what_kind        which best describes the answer:
                   {(chr(10) + ' ' * 19).join(WHAT_KIND)}
  answered         did the answer give the person what they asked for?
                   {' / '.join(ANSWERED)}
  detail_on_page   only when the answer says something is missing or couldn't be found: open the cited page(s)
                   and say whether the missing detail is in fact there.
                   yes (it was on the page: the answer missed it) / no (a real gap in the content) / can't tell
                   Leave blank for other answers.
  notes            anything worth saying (optional)

Judge the answer as a member of the public would read it. "can't tell" is a fine answer: use it rather than guess.
The rows are in random order and mix two periods; there is no date or model on purpose.

How to read "says something is missing": the system is designed to say when a specific detail is not in the content
it retrieved and to point to the nearest page, so an answer that does this is behaving as intended. What matters is
whether the detail really was missing (detail_on_page = no) or was there to be found (detail_on_page = yes). A table
of rates on the cited page counts as the detail being there.

When done: python3 tools/score_labels.py {os.path.relpath(out, REPO)}
""")
    counts = {p: {s: len(pool[p][s]) for s in per} for p in periods}
    print(f"wrote {len(items)} items to {out} (second labeller: {len(second)}); rules {OUTCOME_RULES_VERSION}")
    for p in periods:
        print(f"  {p} {periods[p][0]}..{periods[p][1]}: population " + ", ".join(f"{s} {counts[p][s]}" for s in per))


if __name__ == "__main__":
    main()
