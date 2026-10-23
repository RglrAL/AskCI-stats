#!/usr/bin/env python3
"""Check the outcome rules against the system prompts, locally (brief §60).

The prompts are the specification the outcome rules were guessing at. This reads the local prompt snapshot (the
git-ignored review folder, one dated folder per export), pulls out every fixed wording a prompt prescribes as an
example response or template, and for each one reports: whether an outcome rule in redact_feed.py matches it, which
rule, and how often the wording occurs in the raw feed, by outcome and by model era. It writes the result next to the
prompts, never to the repo: the wordings are prompt text. The brief records the counts.

A wording that occurs in the feed and no rule matches is a coverage gap. A wording that matches a rule of the wrong
family is a misclassification. A wording that never occurs tells us that path is not in use (or the model does not
copy the template).

Usage:
    python3 tools/check_rules_vs_prompts.py exports/qa-feed_*.csv              # latest prompt snapshot
    python3 tools/check_rules_vs_prompts.py FEEDS --snapshot 2026-08-28
"""
import argparse, csv, glob, json, os, re, sys, collections as C
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redact_feed import RULES, RX, classify_rule, rule_of, APOS

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(REPO, "ask review", "prompts")
TS = "%b %d, %Y %H:%M"
FAMILY = {"nf.": "Not found", "cl.": "Clarification", "oos.": "Out of scope", "gr.": "Greeting", "cited.partial.": "Cited answer (partial)"}


def eras():
    ev = json.load(open(os.path.join(REPO, "events.json")))["events"]
    cuts = sorted((e for e in ev if e.get("status") == "confirmed" and e.get("kind") in ("model", "prompt") and len(e.get("start", "")) == 10), key=lambda e: e["start"])
    out = []; prev = (cuts[0].get("era_before") or "before", date(2000, 1, 1)) if cuts else ("all", date(2000, 1, 1))
    for e in cuts:
        out.append((prev[0], prev[1], date.fromisoformat(e["start"])))
        prev = (e.get("era") or e["start"], date.fromisoformat(e["start"]))
    out.append((prev[0], prev[1], date(2100, 1, 1)))
    return out


def phrases(folder):
    """Fixed wordings a prompt prescribes: backticked responses, the "answer" of an example JSON, and quoted example
    sentences of five or more words that begin with a capital letter or I'm/I'd. Returns [(prompt, wording)]."""
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*.md"))):
        name = os.path.basename(p)[:-3]; t = open(p, encoding="utf-8").read()
        found = set()
        for m in re.finditer(r"Response: `([^`]+)`", t): found.add(m.group(1))
        for m in re.finditer(r'"answer":\s*"((?:[^"\\]|\\.)+)"', t): found.add(m.group(1).split(". ")[0] + ".")
        for m in re.finditer(r'"((?:I\'m|I\'d|[A-Z])[^"\n]{25,220}?[.?!])"', t):
            s = m.group(1)
            if len(s.split()) >= 5 and "→" not in s: found.add(s)
        for s in sorted(found):
            out.append((name, s))
    return out


def key(s):
    """the wording as the feed would carry it: lower case, straight apostrophes, no bracketed placeholders, one space"""
    s = s.translate(APOS).lower(); s = re.sub(r"\[[^\]]*\]", " ", s); s = re.sub(r"https?://\S+", " ", s)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s)).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+"); ap.add_argument("--snapshot")
    a = ap.parse_args()
    folders = sorted(d for d in glob.glob(os.path.join(PROMPTS, "????-??-??")) if os.path.isdir(d))
    folder = os.path.join(PROMPTS, a.snapshot) if a.snapshot else folders[-1]
    PH = phrases(folder)
    # the longest distinctive stem of each wording (first 8 words) is what we search for: models vary the tail
    stems = {}
    for name, s in PH:
        k = key(s); w = k.split()
        if len(w) < 4: continue
        stems[(name, s)] = " ".join(w[:8])
    ER = eras()
    hits = C.defaultdict(C.Counter); tot = C.Counter(); seen = set()
    for f in a.feeds:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if k in seen: continue
                seen.add(k)
                try: d = datetime.strptime((row.get("Timestamp") or "").strip(), TS).date()
                except ValueError: continue
                era = next(n for n, x, y in ER if x <= d < y)
                o, partial, rule = classify_rule(row)
                tot[era] += 1
                resp = key(row.get("Assistant Response") or "")
                for ps, stem in stems.items():
                    if stem in resp: hits[ps][(era, o, rule)] += 1
    lines = [f"# Outcome rules against the system prompts of {os.path.basename(folder)} (local only)\n",
             f"Rules {__import__('redact_feed').OUTCOME_RULES_VERSION}; {len(seen):,} feed rows; eras " + ", ".join(f"{n} {tot[n]:,}" for n, _, _ in ER) + ".\n",
             "For each prescribed wording: the rule that matches it (checked on the wording itself), then how often its first eight words occur in the feed, by era, with the outcome and rule the feed row got.\n"]
    gaps = mis = 0
    for (name, s), stem in stems.items():
        m = next(((fam, rule_of(mm)) for fam, rx in RX.items() if (mm := rx.search(s.translate(APOS)))), None)
        n_all = sum(hits[(name, s)].values())
        by_era = ", ".join(f"{e} {sum(v for (ee, o, r), v in hits[(name, s)].items() if ee == e):,}" for e, _, _ in ER)
        outs = C.Counter()
        for (e, o, r), v in hits[(name, s)].items(): outs[(o, r)] += v
        top = "; ".join(f"{o} via {r}: {v:,}" for (o, r), v in outs.most_common(4))
        # only the response prompts prescribe outcome wordings; the classifier, rewriter and decomposer examples are
        # inputs, and the main prompt's examples are style (counted by the wording fingerprint, not outcome rules)
        resp_prompt = name.endswith("_response_prompt") and name != "main_response_prompt" or name == "no_results_system_prompt"
        status = ("no rule" if not m else f"rule {m[1]}") + ("" if resp_prompt else " (style or input example, not an outcome wording)")
        if not m and n_all and resp_prompt: gaps += 1; status += " ← GAP"
        if m and n_all and resp_prompt:
            fam = FAMILY.get(next(p for p in FAMILY if m[1].startswith(p)), "")
            wrong = sum(v for (o, r), v in outs.items() if not o.startswith(fam.split(" ")[0]))
            if wrong > n_all * 0.1: mis += 1; status += f" ← {wrong:,} rows land in another family"
        lines.append(f"## {name}\n- wording: “{s[:160]}{'…' if len(s) > 160 else ''}”\n- {status}\n- in the feed: {n_all:,} rows ({by_era})" + (f"\n- feed rows got: {top}" if top else "") + "\n")
    lines.insert(3, f"**{len(stems)} prescribed wordings; {gaps} gaps (occur in the feed, no rule); {mis} land mainly in another family.**\n")
    out = os.path.join(PROMPTS, f"rules-coverage-{os.path.basename(folder)}-rules-{__import__('redact_feed').OUTCOME_RULES_VERSION}.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines[:4])); print(f"wrote {out}")
    for l in lines[4:]:
        if "GAP" in l or "another family" in l: print(l)


if __name__ == "__main__":
    main()
