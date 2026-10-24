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
from redact_feed import classify, URL_RE, OUTCOME_RULES_VERSION, normalise_query, intent_of, topic_of, INTENT_VERSION, lexicon   # the rules being measured, exactly as they run
from redact_feed import question_topic, check_figures, situation_of, DERIVATION_VERSION, STARTER_PROMPTS   # the §75 layers, measured by the same sheet
CATEGORIES = ["social-welfare", "employment", "housing", "moving-country", "money-and-tax", "travel-and-recreation", "health", "birth-family-relationships",
              "education", "justice", "consumer", "returning-to-ireland", "about", "death", "government-in-ireland", "environment"]

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
    ap.add_argument("--extra", default="figmatched=8,figunmatched=8,situation=8,letter=4,topic=16",
                    help="brief §75 strata, from the after period, typed turns: answers whose quoted figures all matched a cited page / had one unmatched; questions giving a personal detail; pasted letters; one question per category placed by its topic alone (topic=N caps the total)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    periods = {"before": span(a.before), "after": span(a.after)}
    per = {k: int(v) for k, v in (x.split("=") for x in a.per.split(","))}

    seen, pool = set(), {p: {s: [] for s in per} for p in periods}
    starter = normalise_query(a.starter) if a.starter else None; spool = []
    extra = {k: int(v) for k, v in (x.split("=") for x in a.extra.split(","))} if a.extra else {}
    xpool = {"figmatched": [], "figunmatched": [], "situation": [], "letter": [], "topic": {c: [] for c in CATEGORIES}}
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
                # the §75 strata: typed turns in the after period, by what the derivation says about them
                if extra and p == "after" and (row.get("Question Type") or "").strip() in ("new_topic", "user_followup") and not (
                        (row.get("Turn #") or "").strip() == "1" and normalise_query(row.get("User Query")) in STARTER_PROMPTS):
                    q = row.get("User Query") or ""; ans = row.get("Assistant Response") or ""
                    qp, qc, _ = topic_of(q); tname, tcat = question_topic(q)
                    f = check_figures(ans, row.get("Citations"), d.isoformat()) if ("€" in ans or "%" in ans) else (0, 0, 0, 0)
                    if f[0] and f[3] == 0:
                        xpool["figunmatched" if f[2] else "figmatched"].append((d, row, s or o))
                    sit = situation_of(q, qc == "social-welfare")
                    if any(sit[:5]): xpool["situation"].append((d, row, s or o))
                    if "letter" in sit[6]: xpool["letter"].append((d, row, s or o))
                    if tname and not qc and tcat in xpool["topic"]: xpool["topic"][tcat].append((d, row, s or o))

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
    # the §75 strata; an item already drawn is not drawn twice
    drawn = {(r.get("Conversation ID"), (r.get("Turn #") or "").strip()) for r in items}
    xcounts = {}
    for name in ("figmatched", "figunmatched", "situation", "letter"):
        got = [x for x in xpool[name] if (x[1].get("Conversation ID"), (x[1].get("Turn #") or "").strip()) not in drawn]
        pick = rnd.sample(got, min(extra.get(name, 0), len(got))); xcounts[name] = len(xpool[name])
        for d, row, s in pick:
            items.append(row); drawn.add((row.get("Conversation ID"), (row.get("Turn #") or "").strip()))
            key.append({"period": "after", "rule_outcome": s, "date": d.isoformat(), "stratum_population": len(xpool[name]), "stratum_sample": len(pick), "stratum": name})
    tpop = sum(len(v) for v in xpool["topic"].values()); tpick = 0
    for c in CATEGORIES:   # one per category, up to the cap
        if tpick >= extra.get("topic", 0): break
        got = [x for x in xpool["topic"][c] if (x[1].get("Conversation ID"), (x[1].get("Turn #") or "").strip()) not in drawn]
        if not got: continue
        d, row, s = rnd.choice(got); tpick += 1
        items.append(row); drawn.add((row.get("Conversation ID"), (row.get("Turn #") or "").strip()))
        key.append({"period": "after", "rule_outcome": s, "date": d.isoformat(), "stratum_population": tpop, "stratum_sample": 0, "stratum": "topic"})
    for k in key:
        if k["stratum"] == "topic": k["stratum_sample"] = tpick
    xcounts["topic"] = tpop
    order = list(range(len(items)))
    rnd.shuffle(order)

    out = a.out or os.path.join(REPO, "exports", f"labelling-{date.today().isoformat()}")
    os.makedirs(out, exist_ok=True)
    cols = ["item", "question", "answer", "cited_pages", "what_kind", "answered", "detail_on_page", "what_asked", "scheme_page", "category", "topic", "figure_match", "notes"]

    def sheet(path, idx):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols)
            for i in idx:
                row = items[i]
                w.writerow([f"A{i + 1:03d}", (row.get("User Query") or "").strip(), (row.get("Assistant Response") or "").strip(),
                            "\n".join(URL_RE.findall(row.get("Citations") or "")), "", "", "", "", "", "", "", "", ""])

    sheet(os.path.join(out, "label_sheet.csv"), order)
    second = rnd.sample(order, min(a.double, len(order)))
    rnd.shuffle(second)
    sheet(os.path.join(out, "label_sheet_second.csv"), second)
    with open(os.path.join(out, "key.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["item", "period", "rule_outcome", "date", "stratum_population", "stratum_sample", "rules_version", "stratum", "rule_intent", "rule_form", "rule_page", "rule_category", "intent_version",
                                        "rule_topic", "rule_topic_category", "derivation_version", "fig_total", "fig_matched", "fig_unmatched", "fig_unverifiable", "sit_county", "sit_age", "sit_household", "sit_work", "sit_payment", "sit_shape"])
        for i, k in enumerate(key):
            q = items[i].get("User Query"); ans = items[i].get("Assistant Response") or ""
            qi, qf = intent_of(q); qp, qc, _ = topic_of(q); tn, tc = question_topic(q)
            fg = check_figures(ans, items[i].get("Citations"), k["date"]); sit = situation_of(q, qc == "social-welfare")
            w.writerow([f"A{i + 1:03d}", k["period"], k["rule_outcome"], k["date"], k["stratum_population"], k["stratum_sample"], OUTCOME_RULES_VERSION, k["stratum"], qi, qf, qp, qc, INTENT_VERSION + "+" + lexicon()["version"],
                        tn, tc, DERIVATION_VERSION, *fg, sit[0], sit[1], sit[2], sit[3], sit[4], sit[6]])
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
  what_asked       what the question asks for, one of:
                   status (about their own claim or application) / contact (a number, office or hours) / documents
                   (what to bring or provide) / apply (how to apply, renew, register, change) / rate (an amount, rate,
                   limit, how much, how many weeks) / eligibility (can I, am I entitled, who qualifies) / timing (when,
                   how long, deadline, backdated) / definition (what is X, tell me about X, or just a scheme name) / other
                   Pick the one the person most wants answered; a personal story with "can I get" is eligibility.
  scheme_page      the citizensinformation.ie page the question is about, if it names a scheme or subject: paste the
                   address of the page you would send them to (search the site), or leave blank if it names none.
  category         which part of citizensinformation.ie the question belongs to, one of:
                   {', '.join(CATEGORIES)}
                   (about = a question about the service itself). Leave blank only if none fits at all.
  topic            in a few words of your own, what the question is about: the subject, not the wording
                   (e.g. "HAP limits", "passport renewal", "council rent review", "which visa for a spouse").
  figure_match     only when the answer quotes a euro amount, a percentage or a year: open the cited page(s) and say
                   whether every figure the answer quotes is on them.
                   yes (all of them) / no (at least one figure is on no cited page) / partly (some are, some are not) /
                   can't tell. Leave blank when the answer quotes no figure. A rounded figure or a weekly rate the page
                   gives annually counts as on the page.
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
    print(f"wrote {len(items)} items to {out} (second labeller: {len(second)}); rules {OUTCOME_RULES_VERSION}, derivation {DERIVATION_VERSION}")
    for p in periods:
        print(f"  {p} {periods[p][0]}..{periods[p][1]}: population " + ", ".join(f"{s} {counts[p][s]}" for s in per))
    if extra:
        print("  §75 strata (after period, typed): population " + ", ".join(f"{k} {v}" for k, v in xcounts.items()) + f"; drawn " + ", ".join(f"{k} {sum(1 for x in key if x['stratum'] == k)}" for k in xcounts))


if __name__ == "__main__":
    main()
