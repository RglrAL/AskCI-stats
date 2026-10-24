#!/usr/bin/env python3
"""The content-gap register (brief §73): evidence rows rebuilt from the published files; a status file people edit.

Four kinds of gap, each from counts only, over the last `months` full months in register-config.json:
  detail     the page was cited in min_answers+ answers and a share of them said something was missing; the intent
             split says what was missing (rate → a figure, timing → a date, eligibility → a condition)  [content team]
  retrieval  typed questions named the page min_asks_month+ times in a month and a share ended not found: the page
             exists and was named, so this is a chunking or index item                                   [AskCI team]
  stale      the page was cited min_answers+ times and its LastMod is before stale_before                [content team]
  unknown    not-found answers to questions naming no scheme the site has, by the category the question named: the
             count is published, the subjects only after a local read                                 [analyst]
Priority = asks (or answers) × the rate that raised the row, so volume counts.

Writes content-gaps.csv (one row per gap, with its rules and lexicon versions) and creates content-gaps-status.csv
with its header and the owners from config if it does not exist; it never overwrites the status file. The dashboard
joins the two on page and kind.

Usage:
    python3 tools/make_register.py
"""
import csv, json, os, collections as C
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = lambda x: int(float(x or 0))


def rd(p):
    try:
        with open(os.path.join(REPO, p), encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def main():
    cfg = json.load(open(os.path.join(REPO, "register-config.json"), encoding="utf-8"))
    U = rd("usage.csv"); days = sorted(r["Date"] for r in U); last = days[-1]
    allm = sorted({d[:7] for d in days}); full = [m for m in allm if m < last[:7]][-cfg["months"]:]
    rules = next((r.get("OutcomeRules") for r in reversed(U) if r.get("OutcomeRules")), "")
    lex = {}
    try: lex = json.load(open(os.path.join(REPO, "question-lexicon.json"), encoding="utf-8"))
    except (OSError, ValueError): pass
    lexv = lex.get("version", ""); period = f"{full[0]}..{full[-1]}" if full else ""
    rows = []
    # detail: partial by cited page, with the intent split
    CM = [r for r in rd("citations-monthly.csv") if r["Month"] in full]; A = C.defaultdict(C.Counter)
    for r in CM: A[r["URL"].rstrip("/")]["ans"] += I(r["Answers"]); A[r["URL"].rstrip("/")]["p"] += I(r["Partial"])
    CI = [r for r in rd("citations-intent-monthly.csv") if r["Month"] in full]; AI = C.defaultdict(lambda: C.defaultdict(C.Counter))
    for r in CI: AI[r["URL"].rstrip("/")][r["Intent"]]["ans"] += I(r["Answers"]); AI[r["URL"].rstrip("/")][r["Intent"]]["p"] += I(r["Partial"])
    typ = sum(a["p"] for a in A.values()) / max(sum(a["ans"] for a in A.values()), 1)
    for u, a in A.items():
        if a["ans"] < cfg["min_answers"]: continue
        share = a["p"] / a["ans"]
        if share < max(cfg.get("page_partial", 0.3), typ * 1.5): continue   # the page-detail floor lives in register-config.json (brief §76)
        byi = sorted(((e["p"], i, e["ans"]) for i, e in AI[u].items() if e["ans"] >= 5), reverse=True)
        top = byi[0][1] if byi else ""
        rows.append({"kind": "detail", "page": u, "category": u.split("/en/")[-1].split("/")[0] if "/en/" in u else "", "intent": top, "evidence": f"{a['p']} of {a['ans']} answers citing it said something was missing ({share:.0%}; typical {typ:.0%})" + (f"; most on {top} questions ({byi[0][0]} of {byi[0][2]})" if byi else ""),
                     "asks": a["ans"], "rate": round(share, 3), "priority": round(a["ans"] * share), "team": cfg["teams"]["content"]})
    # retrieval: named pages that end not found
    AP = [r for r in rd("asked-pages-monthly.csv") if r["Month"] in full]; N = C.defaultdict(C.Counter)
    for r in AP:
        n = N[r["URL"].rstrip("/")]
        for k in ("Asked", "CitedSame", "CitedUnderHub", "CitedSameCategory", "NotFound"): n[k] += I(r[k])
        n["maxm"] = max(n["maxm"], I(r["Asked"]))
    for u, n in N.items():
        if n["maxm"] < cfg["min_asks_month"]: continue
        nf = n["NotFound"] / n["Asked"]; hit = (n["CitedSame"] + n["CitedUnderHub"]) / n["Asked"]; reached = hit + n["CitedSameCategory"] / n["Asked"]
        # a sibling cited is usually the right page under another name (an alias names one page of a family), so the
        # list takes a page only when questions naming it end not found, or neither it nor a sibling was reached
        if nf < cfg["retrieval_not_found"] and reached >= cfg["retrieval_reached"]: continue
        rows.append({"kind": "retrieval", "page": u, "category": u.split("/en/")[-1].split("/")[0] if "/en/" in u else "", "intent": "", "evidence": f"named in {n['Asked']} typed questions; the answer cited it {hit:.0%}, a sibling in the same category {n['CitedSameCategory'] / n['Asked']:.0%}, not found {nf:.0%}",
                     "asks": n["Asked"], "rate": round(nf, 3), "priority": round(n["Asked"] * max(nf, 1 - reached)), "team": cfg["teams"]["retrieval"]})
    # stale: cited pages last changed before this year
    site = {r["URL"].rstrip("/").lower(): r.get("LastMod", "")[:10] for r in rd("site-pages.csv")}; y0 = cfg.get("stale_before", last[:4] + "-01-01")
    for u, a in A.items():
        lm = site.get(u.lower(), "")
        if a["ans"] < cfg["min_answers"] or not lm or lm >= y0: continue
        rows.append({"kind": "stale", "page": u, "category": u.split("/en/")[-1].split("/")[0] if "/en/" in u else "", "intent": "", "evidence": f"cited in {a['ans']} answers; last changed {lm}; {a['p'] / a['ans']:.0%} of its answers said something was missing",
                     "asks": a["ans"], "rate": round(a["p"] / a["ans"], 3), "priority": round(a["ans"] * (1 + (last[:4] > lm[:4]) * 0.5)), "team": cfg["teams"]["stale"]})
    # unknown: not-found answers naming no scheme, by the category the question named (question-topics) and the residue
    QT = [r for r in rd("question-topics-daily.csv") if r["Date"][:7] in full]; QI = [r for r in rd("question-intent-daily.csv") if r["Chip"] == "0" and r["Date"][:7] in full]
    nf_all = sum(I(r["NotFound"]) for r in QI); nf_named = sum(I(r["NamedNotFound"]) for r in QI)
    rows.append({"kind": "unknown", "page": "", "category": "(no scheme named)", "intent": "", "evidence": f"{nf_all - nf_named} typed not-found answers named no scheme the lexicon knows ({(nf_all - nf_named) / max(nf_all, 1):.0%} of {nf_all}); subjects need the themes step",
                 "asks": nf_all - nf_named, "rate": 1.0, "priority": nf_all - nf_named, "team": cfg["teams"]["unknown"]})
    byc = C.Counter()
    for r in QT: byc[r["Category"]] += I(r["NotFound"])
    for c, n in byc.most_common(6):
        rows.append({"kind": "unknown", "page": "", "category": c, "intent": "", "evidence": f"{n} not-found answers whose question named a {c} scheme but whose answer cited no page", "asks": n, "rate": 1.0, "priority": n, "team": cfg["teams"]["unknown"]})
    # topic rows computed from the topic layer (brief §75): a topic (not a category's general bucket) with topic_min_turns+
    # typed questions in the period enters as missing-page when its not-found share is topic_not_found+, or as detail when
    # the partial share of its cited answers is topic_partial+ (and not already missing-page). The topic name sits in the
    # page column; a computed row replaces a seeded row of the same category and topic
    QT = [r for r in rd("question-topics-monthly.csv") if r["Month"] in full]; T = C.defaultdict(C.Counter)
    for r in QT:
        t = T[(r["Category"], r["Topic"])]; t["n"] += I(r["Turns"]); t["nf"] += I(r["NotFound"]); t["c"] += I(r["Cited"]); t["p"] += I(r["Partial"])
    general = {(c, name) for c, tops in (lex.get("topics") or {}).items() for name, spec in tops.items() if spec.get("general")}
    typ_t = sum(t["p"] for t in T.values()) / max(sum(t["c"] for t in T.values()), 1)   # the period's typical partial share, so a site-wide rise does not fill the register
    computed = set()
    for (c, name), t in sorted(T.items()):
        if (c, name) in general or t["n"] < cfg.get("topic_min_turns", 100): continue
        nf = t["nf"] / t["n"]; part = t["p"] / max(t["c"], 1)
        if nf >= cfg.get("topic_not_found", 0.1):
            rows.append({"kind": "missing-page", "page": name, "category": c, "intent": "", "evidence": f"{t['n']} typed questions on this topic in the period; {nf:.0%} not found, {part:.0%} of cited answers said something was missing (topic layer, lexicon {lexv}; not yet reader-checked)",
                         "asks": t["n"], "rate": round(nf, 3), "priority": round(t["n"] * nf), "team": cfg["teams"]["missing-page"]}); computed.add((c, name))
        elif part >= max(cfg.get("topic_partial", 0.25), typ_t * 1.5):
            rows.append({"kind": "detail", "page": name, "category": c, "intent": "", "evidence": f"{t['n']} typed questions on this topic in the period; {part:.0%} of cited answers said something was missing, {nf:.0%} not found (topic layer, lexicon {lexv}; not yet reader-checked)",
                         "asks": t["n"], "rate": round(part, 3), "priority": round(t["n"] * part), "team": cfg["teams"]["content"]}); computed.add((c, name))
    # seeded topic rows (register-themes.json): subjects from the housing read that the topic layer does not yet compute,
    # and the signpost rows, which no count can infer; a seeded row is dropped once a computed row of the same topic exists
    try: themes = json.load(open(os.path.join(REPO, "register-themes.json"), encoding="utf-8")).get("rows", [])
    except (OSError, ValueError): themes = []
    themes = [t for t in themes if (t.get("category", ""), t["topic"]) not in computed]
    for t in themes:
        rows.append({"kind": t["kind"], "page": t["topic"], "category": t.get("category", ""), "intent": "",
                     "evidence": t["evidence"] + ("" if t.get("reader_checked") else "; themes not yet reader-checked") + f" [{t.get('period', '')}]",
                     "asks": I(t.get("asks")), "rate": 1.0, "priority": I(t.get("asks")), "team": cfg["teams"].get(t["kind"], cfg["teams"].get("content", ""))})
    rows.sort(key=lambda r: (-r["priority"], r["kind"]))
    cols = ["kind", "page", "category", "intent", "evidence", "asks", "rate", "priority", "team", "period", "rules_version", "lexicon_version", "built"]
    with open(os.path.join(REPO, "content-gaps.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({**r, "period": period, "rules_version": rules, "lexicon_version": lexv, "built": date.today().isoformat()})
    sp = os.path.join(REPO, "content-gaps-status.csv")
    if not os.path.exists(sp):
        with open(sp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["kind", "page", "owner", "status", "raised", "expected_effect", "changed", "closed", "note"])
            w.writerow(["_comment", "", cfg["owners"]["status"], "", "", "one row per gap, keyed by kind and page as in content-gaps.csv; status one of " + " / ".join(cfg["statuses"]) + "; write the expected effect when the row is raised", "", "", "evidence file: " + cfg["owners"]["evidence"]])
        print("created content-gaps-status.csv")
    k = C.Counter(r["kind"] for r in rows)
    print(f"wrote content-gaps.csv: {len(rows)} rows over {period} ({dict(k)}); rules {rules}, lexicon {lexv}")


if __name__ == "__main__":
    main()
