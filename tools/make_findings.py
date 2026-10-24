#!/usr/bin/env python3
"""The findings and recommendations, recomputed from the published files at every deploy (brief §72).

Brief §72 is the dated record: what the data showed on 24 October 2026, with the figure of that day and a confidence
line for each item. This writes reports/findings.md beside it: every measurable item recomputed now, shown next to the
§72 figure, with a status (steady, moved, or fixed when a defect has gone), and the conclusions that no tool can
rederive listed with their date and section. The dashboard page shows figures and claims no causes; the causes live
here and in the brief.

Usage:
    python3 tools/make_findings.py            # writes reports/findings.md
    python3 tools/make_findings.py --stdout
"""
import argparse, csv, json, os, re, collections as C
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = lambda x: int(float(x or 0))
RECORDED = "24 Oct 2026"
# The figures §72 recorded, so the report can say whether each has moved. Dated on purpose: they are the record.
BASE = {"chip_empty": 8.2, "typed_first_empty": 0.99, "unexpected": 11.9, "sit_nf": 14.1, "other_nf": 9.2, "whatis_named_clar": 14.8, "whatis_unnamed_clar": 33.9,
        "named_hit": 54.8, "named_nf": 6.9, "old_share": 28.3, "crisis_per_k": 0.59, "crisis_cited": 76, "about_partial": 52, "intent_named": 77.0, "ext_nf": 21.2, "fig_unmatched": 4.1}


def rd(p):
    try:
        with open(os.path.join(REPO, p), encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def pct(x, dp=1):
    return "—" if x is None else f"{x:.{dp}f}%"


def status(now, base, moved=2.0, lower_is_better=True, fixed_at=None):
    if now is None: return "—"
    if fixed_at is not None and ((lower_is_better and now <= fixed_at) or (not lower_is_better and now >= fixed_at)): return "**fixed**"
    d = now - base
    if abs(d) < moved: return "steady"
    return "**better**" if (d < 0) == lower_is_better else "**worse**"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stdout", action="store_true"); a = ap.parse_args()
    U = {r["Date"]: r for r in rd("usage.csv")}; days = sorted(U); last = days[-1]
    last_full = (date.fromisoformat(last).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    d28 = (date.fromisoformat(last) - timedelta(days=27)).isoformat()
    lex = {}
    try: lex = json.load(open(os.path.join(REPO, "question-lexicon.json"), encoding="utf-8"))
    except (OSError, ValueError): pass
    exp = lex.get("intents", {})
    out = []; P = out.append
    P(f"# Findings and recommendations, recomputed from the published files\n")
    P(f"Data to {last}. Each measurable item is recomputed and shown beside the figure brief §72 recorded on {RECORDED}; a status says whether it moved by two points or more, or whether a defect is fixed. The conclusions at the end are dated and cannot be recomputed: they are read, not measured.\n")
    P("| # | Item | Now | §72 ({}) | Status | Evidence |".format(RECORDED)); P("|---|---|---|---|---|---|")
    # 1. chip empty answers, last full month
    m = [U[d] for d in days if d.startswith(last_full)]
    ce, cn, oe, on = (sum(I(r.get(k)) for r in m) for k in ("StarterPromptErrors", "StarterPromptFirstTurns", "OrganicFirstErrors", "OrganicFirstTurns"))
    chip = ce / cn * 100 if cn else None; typed = oe / on * 100 if on else None
    P(f"| 1 | Chip clicks that get an empty answer ({last_full}) | {pct(chip)} of {cn:,} (typed first questions {pct(typed, 2)}) | {BASE['chip_empty']}% (typed {BASE['typed_first_empty']}%) | {status(chip, BASE['chip_empty'], fixed_at=2.0)} | §63, §64: a standing defect in the chip request path since January |")
    # 2. unexpected outcomes, last 28 days, typed
    QI = [r for r in rd("question-intent-daily.csv") if r["Chip"] == "0" and r["Date"] >= d28]
    un = D = 0
    for r in QI:
        e = exp.get(r["Intent"])
        if not e: continue
        D += I(r["Turns"]); un += (I(r["NotFound"]) + I(r["Uncited"]) + I(r["NamedClarification"])) if e == "cited" else I(r["Cited"])
    unexp = un / D * 100 if D else None
    P(f"| 2 | Answers not what the question needed (last 28 days, typed) | {pct(unexp)} of {D:,} | {BASE['unexpected']}% | {status(unexp, BASE['unexpected'])} | §69, §71: the quality figure weighted by what the person wanted |")
    # 3. personal situations against other typed questions, not found
    sit = C.Counter()
    for r in QI:
        for k in ("Turns", "NotFound", "Situation", "SituationNotFound"): sit[k] += I(r[k])
    snf = sit["SituationNotFound"] / sit["Situation"] * 100 if sit["Situation"] else None; onf = (sit["NotFound"] - sit["SituationNotFound"]) / (sit["Turns"] - sit["Situation"]) * 100 if sit["Turns"] > sit["Situation"] else None
    P(f"| 3 | Personal situations: not found (last 28 days) | {pct(snf)} against {pct(onf)} for other typed questions | {BASE['sit_nf']}% against {BASE['other_nf']}% | {status(snf, BASE['sit_nf'])} | §67, §71: the relevance check applied hardest to questions that describe a person |")
    # 4. what-is questions: clarification by scheme named
    wi = C.Counter()
    for r in QI:
        if r["Intent"] == "definition":
            for k in ("Turns", "Clarification", "WithTopic", "NamedClarification"): wi[k] += I(r[k])
    nc = wi["NamedClarification"] / wi["WithTopic"] * 100 if wi["WithTopic"] else None; uc = (wi["Clarification"] - wi["NamedClarification"]) / (wi["Turns"] - wi["WithTopic"]) * 100 if wi["Turns"] > wi["WithTopic"] else None
    P(f"| 4 | \"What is …\" questions asked to clarify (last 28 days) | {pct(nc)} when a scheme is named, {pct(uc)} when none | {BASE['whatis_named_clar']}% / {BASE['whatis_unnamed_clar']}% | {status(nc, BASE['whatis_named_clar'])} | §71: the pre-search classifier's threshold, separate from the answering model |")
    # 5. named pages: hit and not found, last full month
    AP = [r for r in rd("asked-pages-monthly.csv") if r["Month"] == last_full]; ask = sum(I(r["Asked"]) for r in AP)
    hit = sum(I(r["CitedSame"]) + I(r["CitedUnderHub"]) for r in AP) / ask * 100 if ask else None; nnf = sum(I(r["NotFound"]) for r in AP) / ask * 100 if ask else None
    P(f"| 5 | Questions naming a page that exists ({last_full}) | cited it {pct(hit)}, not found {pct(nnf)} of {ask:,} | {BASE['named_hit']}% / {BASE['named_nf']}% | {status(nnf, BASE['named_nf'])} | §67, §71: retrieval steady, the answering model declining more |")
    miss = sorted(((I(r["NotFound"]) / I(r["Asked"]) * 100, r) for r in AP if I(r["Asked"]) >= 30), key=lambda x: -x[0])[:6]
    P(f"| 5a | Pages named 30+ times and not answered from ({last_full}) | " + ("; ".join(f"{r['URL'].split('/en/')[-1].split('/')[-1]} {v:.0f}%" for v, r in miss if v >= 10) or "none at 10%+") + " | divorce decrees 16%, jobseeker's benefit 15%, income tax 15%, driving licence 14%, local authority housing 11% | — | §67: a chunking list, not a content list |")
    # 6. partial by page and the about page, last two months
    months = sorted({d[:7] for d in days})[-2:]
    CM = [r for r in rd("citations-monthly.csv") if r["Month"] in months]; A = C.defaultdict(C.Counter)
    for r in CM: A[r["URL"].rstrip("/").lower()]["ans"] += I(r["Answers"]); A[r["URL"].rstrip("/").lower()]["p"] += I(r["Partial"])
    about = next((a for u, a in A.items() if u.endswith("/about/about-askci")), None); ab = about["p"] / about["ans"] * 100 if about and about["ans"] else None
    high = sorted(((a["p"] / a["ans"] * 100, u, a["ans"]) for u, a in A.items() if a["ans"] >= 100), reverse=True)[:5]
    P(f"| 6 | The AskCI \"about\" page: answers saying something is missing ({', '.join(months)}) | {pct(ab, 0)} of {about['ans'] if about else 0:,} answers | {BASE['about_partial']}% | {status(ab, BASE['about_partial'], moved=5)} | §62: asked things it does not say |")
    P(f"| 6a | Pages cited in 100+ answers with the highest missing-detail share | " + "; ".join(f"{u.split('/en/')[-1].split('/')[-1]} {v:.0f}% ({n:,})" for v, u, n in high) + " | Budget 2024 60%, about 52%, Budget 2023 52%, Christmas Bonus 44%, vacant property grant 40% | — | §62: past-year Budget pages asked for current figures |")
    # 7. old pages: share of citations to pages last changed before this year
    site = {r["URL"].rstrip("/").lower(): r.get("LastMod", "") for r in rd("site-pages.csv")}
    y0 = last[:4] + "-01-01"; dated = [(site.get(u, ""), a["ans"]) for u, a in A.items() if site.get(u)]; tot = sum(n for lm, n in dated); old = sum(n for lm, n in dated if lm < y0)
    olds = old / tot * 100 if tot else None
    P(f"| 7 | Citations to pages last changed before {last[:4]} ({', '.join(months)}) | {pct(olds)} | {BASE['old_share']}% | {status(olds, BASE['old_share'])} | §62: Budget 2022 and 2022-dated employment and health pages among them |")
    # 8. kinds of question with no chip
    SP = [r for r in rd("starter-prompts-monthly.csv") if r["Month"] in months]; chip_int = {r.get("Intent") for r in SP if I(r["Count"]) >= 10} - {""}
    mix = C.Counter(); T = 0
    for r in rd("question-intent-daily.csv"):
        if r["Chip"] == "0" and r["Date"][:7] in months: mix[r["Intent"]] += I(r["Turns"]); T += I(r["Turns"])
    unc = [(k, v / T * 100) for k, v in mix.most_common() if k not in chip_int and k not in ("other", "statement")]
    P(f"| 8 | Kinds of typed question no chip covers ({', '.join(months)}) | " + ("; ".join(f"{k} {v:.0f}%" for k, v in unc[:3]) or "none") + f" (chips cover {', '.join(sorted(chip_int)) or '—'}) | timing 3%, contact 1% (chips cover apply, what-is, eligibility, rate) | — | §63, §70: the chips cover the large kinds; what is left uncovered is small |")
    # 9. crisis language
    SF = rd("safety-daily.csv"); cr = C.Counter()
    for r in SF:
        if r["Flag"] == "Theme crisis":
            for k in ("Turns", "Cited", "OutOfScope"): cr[k] += I(r[k])
    allt = sum(I(U[d]["Questions"]) for d in days); crk = cr["Turns"] / allt * 1000 if allt else None; crc = cr["Cited"] / cr["Turns"] * 100 if cr["Turns"] else None
    P(f"| 9 | Crisis language (all data) | {crk:.2f} per 1,000 turns; {pct(crc, 0)} got an ordinary cited answer | {BASE['crisis_per_k']} / {BASE['crisis_cited']}% | {status(crc, BASE['crisis_cited'], moved=5)} | §65: a question for the service on signposting, about two turns a week |")
    # 10. named intent share
    nm = (T - mix["other"]) / T * 100 if T else None
    P(f"| 10 | Typed questions with a named intent ({', '.join(months)}) | {pct(nm)} (target 80%) | {BASE['intent_named']}% | {status(nm, BASE['intent_named'], lower_is_better=False)} | §71: the acceptance point still short; by rule until the labelling |")
    # labelling status, from the page's CONFIG
    try: page = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    except OSError: page = ""
    om = re.search(r"outcome_rules_measured:\s*(\{[^}]*\}|null)", page); im = re.search(r"intent_measured:\s*(\{[^}]*\}|null)", page)
    P(f"| 11 | Hand-labelled sample scored | outcome rules: {'yes' if om and om.group(1) != 'null' else 'not yet'}; intents: {'yes' if im and im.group(1) != 'null' else 'not yet'} | not yet / not yet | — | §61, §66: the one step that gives ground truth |")
    # 12. signposting (brief §75): not-found answers that name a body outside Citizens Information's own channels, last full month
    SP = [r for r in rd("answer-signposts-monthly.csv") if r["Month"] == last_full and r["Category"] == "(all)"]
    if SP:
        g = lambda k: next((r for r in SP if r["Org"] == k), None)
        a_, e_, n_ = g("(any)"), g("(external)"), g("(none)")
        nf_all = (I(a_["NotFound"]) if a_ else 0) + (I(n_["NotFound"]) if n_ else 0); ext = I(e_["NotFound"]) / nf_all * 100 if e_ and nf_all else None
        base = BASE.get("ext_nf")
        FG = next((r for r in rd("answer-figures-monthly.csv") if r["Month"] == last_full and r["URL"] == "(all)"), None)
        if FG:
            chk = I(FG["Matched"]) + I(FG["Unmatched"]); um = I(FG["Unmatched"]) / chk * 100 if chk else None; bf = BASE.get("fig_unmatched")
            P(f"| 13 | Figures quoted that no cited page carries ({last_full}) | {pct(um)} of {chk:,} checkable figures; {pct(I(FG['Unverifiable']) / I(FG['Figures']) * 100 if I(FG['Figures']) else None, 0)} unverifiable | {pct(bf) if bf is not None else '—'} | {status(um, bf) if bf is not None else 'baseline'} | §75: an upper bound on quoted-figure error until the labelling calibrates it; employment-permit and rate pages lead |")
        P(f"| 12 | Not-found answers naming an outside body ({last_full}) | {pct(ext)} of {nf_all:,}; {pct(I(a_['NotFound']) / nf_all * 100 if a_ and nf_all else None, 0)} name Citizens Information's own channels | {pct(base) if base is not None else '—'} | {status(ext, base, lower_is_better=False) if base is not None else 'baseline'} | §75: the no-results wording points at the service's own centre and phone line; a theme-aware signpost is the recommendation, this column its measure |")
    P("\n## Conclusions on record (read, not measured)\n")
    for s in ["**14 September 2026 was a model change** (§57): it matches the calibrated signature of one on every count, at twice the size of March's; the mix of what was asked accounts for none of it (§71).",
              "**The answering model applies the relevance-check instruction more readily, hardest on questions that describe a person** (§67, §71): not found rose 5 points further on personal situations than on other typed questions; retrieval cited the named page as often as before.",
              "**The pre-search classifier asks for clarification more, whether or not a scheme is named** (§71): a separate change in the smaller model.",
              "**The rewriting step is not a main cause** (§59): follow-ups and first questions fell together.",
              "**The chip request path fails about one click in twelve, and has all year** (§64): a defect to report, not a model question.",
              "**Requests for when contact with the team resumes** (§60, §68): the current prompt set and where brief mode is used; a log extract one week either side of 14 September.",
              "**The labelling hour** (§61, §66): 120 answers, four columns; until it is scored every outcome and intent figure since 14 September is an inference.",
              "**Every deployment changed the prompt as well as the model** (§75): the bot's fixed sentences step in March, July and September, each on a model-change date, and never otherwise; the 14 September reading has a wording change to weigh alongside the model.",
              "**The no-results answer sends people to Citizens Information's own channels and almost nowhere else** (§75): a theme-aware signpost (RTB and Threshold for a tenancy, MABS for money, the justice pages and a centre for a neighbour dispute) is a small prompt change with a measure already in place."]:
        P(f"- {s}")
    P(f"\n---\n*tools/make_findings.py at deploy; the dated record is brief §72.*")
    md = "\n".join(out) + "\n"
    if a.stdout: print(md)
    else:
        os.makedirs(os.path.join(REPO, "reports"), exist_ok=True); p = os.path.join(REPO, "reports", "findings.md"); open(p, "w", encoding="utf-8").write(md); print(f"wrote {os.path.relpath(p, REPO)}")


if __name__ == "__main__":
    main()
