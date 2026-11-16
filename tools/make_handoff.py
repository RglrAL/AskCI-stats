#!/usr/bin/env python3
"""The handoff extract for the phone service and the centres (brief §106, handoff 6d): from answer-signposts-monthly.csv,
the answers that named the Citizens Information Phone Service and the Citizens Information centres in the latest full
month, by the category of the turn: how many, the share that were not-found answers, and the share of questions asked
outside the phone service's hours (OutsideHours; the hours are make_usage.py's PHONE_HOURS, for the analyst to
confirm). Counts only, from a published file; category rows under five are already left out of that file.

Writes reports/handoff-<month>.md. Usage: python3 tools/make_handoff.py
"""
import csv, os
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")
I = lambda x: int(float(x or 0))
NAMES = {"cic.phone": "the Citizens Information Phone Service", "cic.centre": "a Citizens Information centre"}


def main():
    rows = list(csv.DictReader(open(os.path.join(DATA, "answer-signposts-monthly.csv"), encoding="utf-8")))
    days = sorted(r["Date"] for r in csv.DictReader(open(os.path.join(DATA, "usage.csv"), encoding="utf-8")))
    months = sorted({r["Month"] for r in rows if r["Month"] < days[-1][:7]})
    if not months or "OutsideHours" not in rows[0]:
        print("no full month, or no OutsideHours column: nothing written"); return
    m = months[-1]; pct = lambda a, b: f"{a / b * 100:.0f}%" if b else "—"
    out = [f"# Answers that named the phone service or a centre, {m}", "",
           f"Generated {date.today().isoformat()} from data/answer-signposts-monthly.csv (brief §106). Counts only. An answer can name both.",
           "Not found = the answer was a not-found answer; outside hours = the question came outside the phone service's hours "
           "(Monday to Friday, 9:00 to 20:00, to confirm). Category rows under five answers are left out of the source file.", ""]
    for oid, name in NAMES.items():
        R = [r for r in rows if r["Month"] == m and r["Org"] == oid]
        tot = next((r for r in R if r["Category"] == "(all)"), None)
        if not tot: continue
        out += [f"## Answers naming {name}: {I(tot['Turns']):,}", "",
                f"{pct(I(tot['NotFound']), I(tot['Turns']))} were not-found answers; {pct(I(tot['OutsideHours']), I(tot['Turns']))} of the questions came outside the phone service's hours.", "",
                "| Category | Answers | Not found | Outside hours |", "| --- | ---: | ---: | ---: |"]
        out += [f"| {r['Category']} | {I(r['Turns']):,} | {pct(I(r['NotFound']), I(r['Turns']))} | {pct(I(r['OutsideHours']), I(r['Turns']))} |"
                for r in sorted((r for r in R if r["Category"] != "(all)"), key=lambda r: -I(r["Turns"]))]
        out.append("")
    os.makedirs(os.path.join(REPO, "reports"), exist_ok=True)
    p = os.path.join(REPO, "reports", f"handoff-{m}.md"); open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"wrote reports/handoff-{m}.md")


if __name__ == "__main__":
    main()
