#!/usr/bin/env python3
"""Score people's labels against the outcome rules (the sample from make_label_sample.py).

Reads key.csv and label_sheet.csv (and label_sheet_second.csv when the second labeller has filled it in) from a
labelling folder and prints, per period:
  - a confusion matrix: the class the rules gave (rows) against the class the labeller gave (columns)
  - per rule class: the share the labeller agreed with (precision of that rule) and, weighted back to how common each
    class was in the period, an estimate of how much of each true class the rules caught (recall)
  - overall agreement, weighted back to the period's real mix of the sampled classes
  - the figure the 14 Sep question turns on: of answers the rules call "not found", the share a reader says
    did answer the question (yes or partly)
  - if the second sheet is filled in: agreement between the two labellers (per cent and Cohen's kappa)
"can't tell" labels are counted and left out of the rates.

It prints no question or answer text, so its output can be shared. Its last line is the CONFIG entry for the
dashboard's data-quality strip (CONFIG.outcome_rules_measured), which replaces "unvalidated" with the measured figure.

Usage:
    python3 tools/score_labels.py exports/labelling-2026-10-24
"""
import csv, os, sys, collections as C, json
from datetime import date

KIND = {"answered with a source": "cited", "answered but says something is missing": "partial",
        "says it couldn't find it": "notfound", "asks to clarify": "clarification", "declines as out of scope": "oos",
        "answered without a source": "uncited", "other": "other", "can't tell": "cant"}
CLASSES = ["cited", "partial", "notfound", "clarification"]
INTENTS = {"status", "contact", "documents", "apply", "rate", "eligibility", "timing", "definition", "other"}
COLS = CLASSES + ["oos", "uncited", "other", "cant"]


def norm(v, allowed):
    v = (v or "").strip().lower().replace("’", "'")
    return v if v in allowed else ("" if not v else "?" + v)


def read_sheet(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {r["item"]: (norm(r.get("what_kind"), KIND), norm(r.get("answered"), {"yes", "partly", "no", "can't tell"}),
                            norm(r.get("detail_on_page"), {"yes", "no", "can't tell"}), norm(r.get("what_asked"), INTENTS),
                            (r.get("scheme_page") or "").strip().lower().rstrip("/")) for r in csv.DictReader(fh)}


def wilson(k, n, z=1.96):
    """95% interval for a share k/n (Wilson): honest about how little 10 or 20 answers can say."""
    if not n:
        return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0, c - h), min(1, c + h)


def rng(k, n):
    w = wilson(k, n)
    return f" ({w[0]:.0%}–{w[1]:.0%})" if w else ""


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = C.Counter(a for a, _ in pairs), C.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, (po - pe) / (1 - pe) if pe < 1 else None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    with open(os.path.join(d, "key.csv"), encoding="utf-8-sig", newline="") as fh:
        key = {r["item"]: r for r in csv.DictReader(fh)}
    lab = read_sheet(os.path.join(d, "label_sheet.csv"))
    bad = [i for i, (k, a, dp, wa, sp) in lab.items() if k.startswith("?") or a.startswith("?") or dp.startswith("?") or wa.startswith("?")]
    if bad:
        sys.exit(f"{len(bad)} rows have a value that isn't one of the allowed ones (see README.txt), e.g. {bad[:5]}")
    done = {i: v for i, v in lab.items() if v[0]}
    print(f"labelled {len(done)} of {len(key)} items; rules {next(iter(key.values()))['rules_version']}\n")
    summary = {}
    strat = lambda i: key[i].get("stratum") or key[i]["rule_outcome"]
    for period in ["before", "after"]:
        items = [i for i, k in key.items() if k["period"] == period and i in done and strat(i) != "starter"]
        if not items:
            continue
        cm = C.defaultdict(C.Counter)
        for i in items:
            cm[key[i]["rule_outcome"]][KIND[done[i][0]]] += 1
        # weight of one sampled item = how many answers of its class the period held ÷ how many were sampled
        w = {i: int(key[i]["stratum_population"]) / max(1, int(key[i]["stratum_sample"])) for i in items}
        print(f"== {period} ({min(key[i]['date'] for i in items)} to {max(key[i]['date'] for i in items)}), {len(items)} labelled")
        print("   rules \\ reader  " + " ".join(f"{c:>13}" for c in COLS))
        for r in CLASSES:
            print(f"   {r:15} " + " ".join(f"{cm[r][c]:>13}" for c in COLS))
        acc_n = acc_d = 0
        for r in CLASSES:
            told = sum(cm[r][c] for c in COLS if c != "cant")
            prec = cm[r][r] / told if told else None
            hum_w = sum(w[i] for i in items if KIND[done[i][0]] == r)
            rec = sum(w[i] for i in items if KIND[done[i][0]] == r and key[i]["rule_outcome"] == r) / hum_w if hum_w else None
            print(f"   {r:15} reader agrees {('—' if prec is None else f'{prec:.0%}'):>5} of {told:>3}{rng(cm[r][r], told):<12}"
                  + (f" · of answers a reader calls '{r}' (among the four sampled classes), the rules catch about {rec:.0%}" if rec is not None else ""))
        for i in items:
            k = KIND[done[i][0]]
            if k == "cant":
                continue
            acc_d += w[i]; acc_n += w[i] * (k == key[i]["rule_outcome"])
        acc = acc_n / acc_d if acc_d else None
        nf = [i for i in items if key[i]["rule_outcome"] == "notfound" and done[i][1] in ("yes", "partly", "no")]
        nf_ans = sum(done[i][1] in ("yes", "partly") for i in nf) / len(nf) if nf else None
        print(f"   overall agreement, weighted to the period's real mix: {('—' if acc is None else f'{acc:.0%}')}")
        k_ans = sum(done[i][1] in ("yes", "partly") for i in nf)
        print(f"   rule 'not found' answers a reader says did answer (yes or partly): {('—' if nf_ans is None else f'{nf_ans:.0%}')} of {len(nf)}{rng(k_ans, len(nf))}\n")
        # of answers that say something is missing (rule 'partial' or 'not found'), was the detail on the cited page?
        miss = [i for i in items if key[i]["rule_outcome"] in ("partial", "notfound") and done[i][2] in ("yes", "no")]
        if miss:
            on = sum(done[i][2] == "yes" for i in miss)
            print(f"   answers saying something is missing where the detail WAS on the cited page (a miss, not a gap): {on / len(miss):.0%} of {len(miss)}{rng(on, len(miss))}\n")
        summary[period] = {"agreement": round(acc, 3) if acc is not None else None, "n": len(items),
                           "notfound_answered": round(nf_ans, 3) if nf_ans is not None else None,
                           **({"detail_was_on_page": round(on / len(miss), 3)} if miss else {})}
    # what people ask (brief §66): the rule's intent and page against the reader's, per class
    wa = [i for i in key if i in lab and lab[i][3] and key[i].get("rule_intent")]
    if wa:
        cm2 = C.defaultdict(C.Counter)
        for i in wa: cm2[key[i]["rule_intent"]][lab[i][3]] += 1
        agree = sum(cm2[k][k] for k in cm2); print(f"== what was asked: rule intent against the reader on {len(wa)} items: {agree / len(wa):.0%} agree{rng(agree, len(wa))}")
        for k in sorted(cm2, key=lambda k: -sum(cm2[k].values())):
            n = sum(cm2[k].values()); print(f"   rule '{k:12}' {n:3} items: reader agrees {cm2[k][k] / n:.0%}{rng(cm2[k][k], n)}" + ("" if cm2[k][k] == n else "; reader said " + ", ".join(f"{v}×{c}" for c, v in cm2[k].most_common() if c != k)))
        sp = [i for i in wa if key[i].get("rule_page") or lab[i][4]]
        if sp:
            same = sum((key[i].get("rule_page") or "").lower().rstrip("/") == lab[i][4] for i in sp if lab[i][4] and key[i].get("rule_page"))
            both = sum(1 for i in sp if lab[i][4] and key[i].get("rule_page")); only_rule = sum(1 for i in sp if key[i].get("rule_page") and not lab[i][4]); only_reader = sum(1 for i in sp if lab[i][4] and not key[i].get("rule_page"))
            print(f"   scheme page: both named one on {both} items, the same page on {same} ({same / both:.0%}){rng(same, both) if both else ''}; rule only {only_rule}, reader only {only_reader}\n")
        summary["asked"] = {"n": len(wa), "intent_agree": round(agree / len(wa), 3)}
    st = [i for i in key if strat(i) == "starter" and i in done]
    if st:
        kinds = C.Counter(KIND[done[i][0]] for i in st); ans = C.Counter(done[i][1] for i in st)
        miss = [i for i in st if done[i][2] in ("yes", "no")]; on = sum(done[i][2] == "yes" for i in miss)
        print(f"== the fixed starter question, {len(st)} answers after the change (rules called {dict(C.Counter(key[i]['rule_outcome'] for i in st))})")
        print(f"   reader: kind {dict(kinds)}; answered {dict(ans)}" + (f"; detail was on the page {on} of {len(miss)}{rng(on, len(miss))}" if miss else "") + "\n")
        summary["starter"] = {"n": len(st), "answered_yes": ans["yes"], "partly": ans["partly"], "no": ans["no"], **({"detail_was_on_page": round(on / len(miss), 3)} if miss else {})}
    sec = read_sheet(os.path.join(d, "label_sheet_second.csv"))
    both = [i for i, v in sec.items() if v[0] and i in done]
    if both:
        po, k = kappa([(done[i][0], sec[i][0]) for i in both])
        pa, ka = kappa([(done[i][1], sec[i][1]) for i in both])
        print(f"== two labellers, {len(both)} items: what_kind {po:.0%} agree (kappa {k:.2f}), answered {pa:.0%} agree (kappa {ka:.2f})\n")
        summary["labellers"] = {"n": len(both), "kind_agree": round(po, 3), "kind_kappa": round(k, 2) if k is not None else None}
    n = sum(v["n"] for p, v in summary.items() if p in ("before", "after"))
    entry = {"measured": date.today().isoformat(), "n": n, "rules": next(iter(key.values()))["rules_version"],
             **{f"agreement_{p}": summary[p]["agreement"] for p in ("before", "after") if p in summary},
             **({"notfound_answered_after": summary["after"]["notfound_answered"]} if "after" in summary else {})}
    print("CONFIG.outcome_rules_measured = " + json.dumps(entry))


if __name__ == "__main__":
    main()
