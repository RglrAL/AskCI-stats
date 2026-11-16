#!/usr/bin/env python3
"""The content-gap register (brief §73): evidence rows rebuilt from the published files; a status file people edit.

Four kinds of gap, each from counts only, over the last `months` full months in register-config.json:
  detail     the page was cited in min_answers+ answers and a share of them said something was missing; the intent
             split says what was missing (rate → a figure, timing → a date, eligibility → a condition)  [content team]
  retrieval  typed questions named the page min_asks_month+ times in a month and a share ended not found: the page
             exists and was named, so this is a chunking or index item                                   [AskCI team]
  stale      the page was cited min_answers+ times, its LastMod is before stale_before, and it shows a sign of a
             problem: a partial share stale_partial_ratio x typical or more, or stale_unmatched+ of its checkable
             figures on no cited page (stale_min_checkable+ checkable); priority answers x that rate      [content team]
             (an old page with no such sign is written as kind "old": outside the register, listed for reference)
  archive-cited  an archive page (archive_patterns, e.g. a past year's Budget) cited in min_answers+ answers: the page
             is right to be old; the gap is that AskCI cites it for current questions                    [AskCI team]
  unknown    not-found answers to questions naming no scheme the site has, by the category the question named: the
             count is published, the subjects only after a local read                                 [analyst]
Priority = asks (or answers) × the rate that raised the row, so volume counts.

Writes content-gaps.csv (one row per gap, with its rules and lexicon versions) and creates content-gaps-status.csv
with its header and the owners from config if it does not exist; it never overwrites the status file. The dashboard
joins the two on page and kind.

Usage:
    python3 tools/make_register.py
"""
import csv, json, os, re, collections as C
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")   # the published files the page reads (brief §97)
I = lambda x: int(float(x or 0))


def rd(p):
    try:
        with open(os.path.join(DATA, p), encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def main():
    cfg = json.load(open(os.path.join(DATA, "register-config.json"), encoding="utf-8"))
    U = rd("usage.csv"); days = sorted(r["Date"] for r in U); last = days[-1]
    allm = sorted({d[:7] for d in days}); full = [m for m in allm if m < last[:7]][-cfg["months"]:]
    rules = next((r.get("OutcomeRules") for r in reversed(U) if r.get("OutcomeRules")), "")
    lex = {}
    try: lex = json.load(open(os.path.join(DATA, "question-lexicon.json"), encoding="utf-8"))
    except (OSError, ValueError): pass
    lexv = lex.get("version", ""); period = f"{full[0]}..{full[-1]}" if full else ""
    rows = []
    # detail: partial by cited page, with the intent split
    CM = [r for r in rd("citations-monthly.csv") if r["Month"] in full]; A = C.defaultdict(C.Counter)
    for r in CM: A[r["URL"].rstrip("/")]["ans"] += I(r["Answers"]); A[r["URL"].rstrip("/")]["p"] += I(r["Partial"])
    CI = [r for r in rd("citations-intent-monthly.csv") if r["Month"] in full]; AI = C.defaultdict(lambda: C.defaultdict(C.Counter))
    for r in CI: AI[r["URL"].rstrip("/")][r["Intent"]]["ans"] += I(r["Answers"]); AI[r["URL"].rstrip("/")][r["Intent"]]["p"] += I(r["Partial"])
    typ = sum(a["p"] for a in A.values()) / max(sum(a["ans"] for a in A.values()), 1)
    # archive pages (brief §103): a pattern's year group before the data's year makes a page an archive page; it is
    # raised as archive-cited, never as detail or stale
    yr = int(last[:4])
    def archive(u):
        for ap in cfg.get("archive_patterns", []):
            m = re.search(ap["pattern"], u)
            if m and (not ap.get("year_before_data") or int(m.group(1)) < yr): return True
        return False
    for u, a in sorted(A.items()):
        if a["ans"] < cfg["min_answers"] or not archive(u): continue
        rows.append({"kind": "archive-cited", "page": u, "category": u.split("/en/")[-1].split("/")[0] if "/en/" in u else "", "intent": "",
                     "evidence": f"an archive page cited in {a['ans']} answers in the period ({a['p'] / a['ans']:.0%} said something was missing): the page is right to be old; AskCI cites it for current questions",
                     "asks": a["ans"], "rate": 1.0, "priority": a["ans"], "team": cfg["teams"]["archive-cited"]})
    for u, a in A.items():
        if a["ans"] < cfg["min_answers"] or archive(u): continue
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
    # stale (brief §103): a cited page last changed before stale_before AND showing a sign of a problem, a partial share
    # at least stale_partial_ratio x the typical share, or stale_unmatched+ of its checkable figures on no cited page;
    # age alone raises nothing. An old page with no sign is written as kind "old", outside the register
    site = {r["URL"].rstrip("/").lower(): r.get("LastMod", "")[:10] for r in rd("site-pages.csv")}; y0 = cfg.get("stale_before", last[:4] + "-01-01")
    FG = C.defaultdict(C.Counter)
    for r in rd("answer-figures-monthly.csv"):
        if r["Month"] in full and not r["URL"].startswith("("): FG[r["URL"].rstrip("/")]["m"] += I(r["Matched"]); FG[r["URL"].rstrip("/")]["u"] += I(r["Unmatched"])
    for u, a in A.items():
        lm = site.get(u.lower(), "")
        if a["ans"] < cfg["min_answers"] or not lm or lm >= y0 or archive(u): continue
        part = a["p"] / a["ans"]; f = FG.get(u, C.Counter()); chk = f["m"] + f["u"]; um = f["u"] / chk if chk >= cfg.get("stale_min_checkable", 30) else None
        sign_p = part >= cfg.get("stale_partial_ratio", 1.25) * typ; sign_f = um is not None and um >= cfg.get("stale_unmatched", 0.1)
        base = {"page": u, "category": u.split("/en/")[-1].split("/")[0] if "/en/" in u else "", "intent": "", "asks": a["ans"]}
        figs = f"{um:.0%} of {chk} checkable figures on no cited page" if um is not None else "too few checkable figures"
        if sign_p or sign_f:
            rate = max(part if sign_p else 0, um if sign_f else 0)
            rows.append({**base, "kind": "stale", "evidence": f"cited in {a['ans']} answers; last changed {lm}; {part:.0%} of its answers said something was missing (typical {typ:.0%}); {figs}",
                         "rate": round(rate, 3), "priority": round(a["ans"] * rate), "team": cfg["teams"]["stale"]})
        else:
            rows.append({**base, "kind": "old", "evidence": f"cited in {a['ans']} answers; last changed {lm}; {part:.0%} said something was missing (typical {typ:.0%}); {figs}: old, no sign of a problem",
                         "rate": round(part, 3), "priority": 0, "team": cfg["teams"]["old"]})
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
    # rising and failing (brief §104, handoff 3e): a topic among the ten fastest risers by share (the latest complete month
    # against the one before, 60+ questions across the two, as on the Questions view) whose not-found share in the latest
    # month is topic_not_found+; priority = its questions now x that share
    QM = rd("question-topics-monthly.csv"); allm2 = sorted({r["Month"] for r in QM}); lastfull = last[:7] if last[8:10] == f"{__import__('calendar').monthrange(int(last[:4]), int(last[5:7]))[1]:02d}" else None
    cm = [m for m in allm2 if m < last[:7] or m == lastfull]
    if len(cm) >= 2:
        mA, mB = cm[-1], cm[-2]; ag = lambda m: {(r["Category"], r["Topic"]): (I(r["Turns"]), I(r["NotFound"])) for r in QM if r["Month"] == m}
        a_, b_ = ag(mA), ag(mB); ta = sum(x[0] for x in a_.values()); tb = sum(x[0] for x in b_.values())
        ris = []
        for key in set(a_) | set(b_):
            n1, f1 = a_.get(key, (0, 0)); n0 = b_.get(key, (0, 0))[0]
            if n1 + n0 < 60 or not n1: continue
            ratio = (n1 / ta) / (n0 / tb) if n0 else float("inf")
            if ratio > 1: ris.append((ratio, key, n0, n1, f1))
        for ratio, (c, name), n0, n1, f1 in sorted(ris, reverse=True)[:10]:
            nf = f1 / n1
            if nf < cfg.get("topic_not_found", 0.1): continue
            rows.append({"kind": "rising-failing", "page": name, "category": c, "intent": "", "asks": n1, "rate": round(nf, 3), "priority": round(n1 * nf), "team": cfg["teams"]["rising-failing"],
                         "evidence": f"{n0} questions in {mB}, {n1} in {mA}: its share of topic-placed questions x{'new' if ratio == float('inf') else f'{ratio:.1f}'}; {nf:.0%} of them not found in {mA} (rising by share, failing by rule)"})
    # seeded topic rows (register-themes.json): subjects from the housing read that the topic layer does not yet compute,
    # and the signpost rows, which no count can infer; a seeded row is dropped once a computed row of the same topic exists
    try: themes = json.load(open(os.path.join(DATA, "register-themes.json"), encoding="utf-8")).get("rows", [])
    except (OSError, ValueError): themes = []
    themes = [t for t in themes if (t.get("category", ""), t["topic"]) not in computed]
    for t in themes:
        rows.append({"kind": t["kind"], "page": t["topic"], "category": t.get("category", ""), "intent": "",
                     "evidence": t["evidence"] + ("" if t.get("reader_checked") else "; themes not yet reader-checked") + f" [{t.get('period', '')}]",
                     "asks": I(t.get("asks")), "rate": 1.0, "priority": I(t.get("asks")), "team": cfg["teams"].get(t["kind"], cfg["teams"].get("content", ""))})
    rows.sort(key=lambda r: (-r["priority"], r["kind"]))
    cols = ["kind", "page", "category", "intent", "evidence", "asks", "rate", "priority", "team", "period", "rules_version", "lexicon_version", "built"]
    with open(os.path.join(DATA, "content-gaps.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({**r, "period": period, "rules_version": rules, "lexicon_version": lexv, "built": date.today().isoformat()})
    sp = os.path.join(DATA, "content-gaps-status.csv")
    if not os.path.exists(sp):
        with open(sp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["kind", "page", "owner", "status", "raised", "expected_effect", "changed", "closed", "note"])
            w.writerow(["_comment", "", cfg["owners"]["status"], "", "", "one row per gap, keyed by kind and page as in content-gaps.csv; status one of " + " / ".join(cfg["statuses"]) + "; write the expected effect when the row is raised", "", "", "evidence file: " + cfg["owners"]["evidence"]])
        print("created content-gaps-status.csv")
    k = C.Counter(r["kind"] for r in rows)   # "old" rows are outside the register: the page lists them apart
    print(f"wrote content-gaps.csv: {len(rows)} rows over {period} ({dict(k)}); rules {rules}, lexicon {lexv}")


if __name__ == "__main__":
    main()
