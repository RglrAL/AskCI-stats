#!/usr/bin/env python3
"""Incident candidates: error days read against the hours, response times and cost meters (brief §53 step 9, §64).

From the published files only (usage.csv, usage-hours.csv, costs.csv, events.json). A day is a candidate when its
empty-answer share is at least 3% and at least three times the trailing 28-day median, with 20 or more errors. For
each candidate it reports: the hours the errors fell in (how concentrated: share in the busiest two hours, and the
error share within those hours), response time p50 and p90 against the trailing median, turns against the trailing
median, and each cost meter group's spend that day against its own trailing median (Search units and semantic
ranker queries; container vCPU and memory, active and idle; Foundry input and output tokens; bandwidth). A meter that
jumps on an error day names a component; one that falls to nothing names an outage. Whether the day is already an
event in events.json is shown.

It also reports the standing defect found in §63: the empty-answer share of chip first turns against typed first
turns, by month, from the StarterPromptErrors and OrganicFirstErrors columns.

Writes reports/incidents.md (reports/ is git-ignored and published at deploy) and prints a candidate-event JSON line
per new candidate for events.json.

Usage:
    python3 tools/incidents.py
    python3 tools/incidents.py --min-share 0.02 --stdout
"""
import argparse, csv, json, os, re, statistics, collections as C
from datetime import date, datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I = lambda x: int(float(x or 0))
GROUPS = [("Search units", lambda s, m: s == "Azure Cognitive Search" and "Unit" in m),
          ("Semantic ranker queries", lambda s, m: s == "Azure Cognitive Search" and "Ranker" in m),
          ("Container vCPU active", lambda s, m: s == "Azure Container Apps" and "vCPU Active" in m),
          ("Container memory active", lambda s, m: s == "Azure Container Apps" and "Memory Active" in m),
          ("Container idle (vCPU + memory)", lambda s, m: s == "Azure Container Apps" and "Idle" in m),
          ("Model input tokens", lambda s, m: s == "Foundry Models" and re.search(r"\binp|input", m, re.I) and not re.search(r"embed|transcribe", m, re.I)),
          ("Model output tokens", lambda s, m: s == "Foundry Models" and re.search(r"outp|\bopt\b|out\b", m, re.I) and not re.search(r"embed|transcribe", m, re.I)),
          ("Bandwidth", lambda s, m: s == "Bandwidth")]


def rd(p):
    with open(os.path.join(REPO, p), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def trailing(series, d, n=28):
    """median of the n days before d that have a value"""
    vals = [v for dd, v in series.items() if dd < d and dd >= (date.fromisoformat(d) - timedelta(days=n)).isoformat() and v is not None]
    return statistics.median(vals) if len(vals) >= 7 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-share", type=float, default=0.03); ap.add_argument("--min-errors", type=int, default=20); ap.add_argument("--times", type=float, default=3.0)
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    U = {r["Date"]: r for r in rd("usage.csv")}; days = sorted(U)
    H = C.defaultdict(dict)
    if os.path.exists(os.path.join(REPO, "usage-hours.csv")):
        for r in rd("usage-hours.csv"): H[r["Date"]][I(r["Hour"])] = r
    cost = C.defaultdict(C.Counter)
    if os.path.exists(os.path.join(REPO, "costs.csv")):
        for r in rd("costs.csv"):
            try: d = datetime.strptime(r["UsageDate"], "%d/%m/%Y").date().isoformat()
            except ValueError: continue
            for g, f in GROUPS:
                if f(r.get("ServiceName", ""), r.get("Meter", "")): cost[g][d] += float(r.get("Cost") or 0)
    EV = json.load(open(os.path.join(REPO, "events.json")))["events"]
    share = {d: (I(U[d]["Error"]) / I(U[d]["Questions"]) if I(U[d]["Questions"]) else None) for d in days}
    turns = {d: I(U[d]["Questions"]) for d in days}
    p50 = {d: (I(U[d]["LatencyP50ms"]) or None) for d in days}; p90 = {d: (I(U[d]["LatencyP90ms"]) or None) for d in days}
    out = []; P = out.append; cands = []
    P(f"# Incident candidates from the published files ({days[0]} to {days[-1]})\n")
    P(f"A candidate day has an empty-answer share of at least {a.min_share:.0%}, at least {a.times:g}× its trailing 28-day median, and {a.min_errors}+ errors. Figures are read against each series' own trailing 28-day median.\n")
    for d in days:
        s = share[d]; e = I(U[d]["Error"]); base = trailing(share, d)
        if s is None or e < a.min_errors or s < a.min_share or (base is not None and base > 0 and s < a.times * base) or (base is None and d != days[0] and len(days) > 7 and days.index(d) >= 7):
            if not (s is not None and e >= a.min_errors and s >= a.min_share and (base is None or base == 0 or s >= a.times * base)):
                continue
        cands.append(d)
        ev = [x for x in EV if x["start"][:10] <= d <= (x.get("end") or x["start"])[:10] or x["start"][:10] == d]
        P(f"## {date.fromisoformat(d):%A %-d %B %Y}: {e:,} empty answers in {turns[d]:,} turns ({s:.1%}; trailing median {base:.2%})" if base is not None else f"## {date.fromisoformat(d):%A %-d %B %Y}: {e:,} empty answers in {turns[d]:,} turns ({s:.1%})")
        P("- **On record:** " + ("; ".join(f"{x['title']} ({x['status']})" for x in ev) if ev else "no event in events.json for this day") + ".")
        hb = trailing(turns, d); P(f"- **Turns:** {turns[d]:,} against a trailing median of {hb:,.0f}" + (f" ({turns[d] / hb:.1f}×)" if hb else "") + ".")
        if H.get(d):
            hrs = sorted(H[d].items()); errs = [(h, I(r["Errors"]), I(r["Turns"])) for h, r in hrs]
            top = sorted(errs, key=lambda x: -x[1])[:2]; te = sum(x[1] for x in errs)
            P(f"- **Hours:** errors in {sum(1 for x in errs if x[1])} of {len(errs)} hours with traffic; the busiest two ({', '.join(f'{h:02d}:00 ({n} of {t} turns, {n / t:.0%})' for h, n, t in top if t)}) hold {sum(x[1] for x in top) / te:.0%} of the day's errors."
              + (" A whole-day failure." if sum(1 for x in errs if x[1]) >= 0.8 * len(errs) else " A burst." if sum(x[1] for x in top) / te >= 0.6 else ""))
        for lbl, ser in (("p50", p50), ("p90", p90)):
            b = trailing(ser, d)
            if ser[d] and b: P(f"- **Response time {lbl}:** {ser[d] / 1000:.1f} s against {b / 1000:.1f} s ({ser[d] / b:.1f}×).")
        moved = []
        for g, _ in GROUPS:
            ser = cost[g]
            if not ser: continue
            v = ser.get(d); b = trailing({k: ser.get(k) for k in days}, d)
            if v is None or not b: continue
            r = v / b
            if r >= 1.5 or r <= 0.5: moved.append(f"{g} {r:.1f}× (£{v:.2f} against £{b:.2f})")
        P("- **Cost meters that moved (1.5× or 0.5× their trailing median):** " + ("; ".join(moved) if moved else "none: every meter within range, so the component that failed is not one that bills by use.") + "\n")
    if not cands: P("No candidate days.\n")
    # the standing chip defect
    if "StarterPromptErrors" in U[days[0]]:
        P("## Chip first turns: a standing defect, not a spike\n")
        P("| Month | Chip first turns | Empty | Share | Typed first turns | Empty | Share |")
        P("|---|---|---|---|---|---|---|")
        M = C.defaultdict(C.Counter)
        for d in days:
            m = M[d[:7]]; m["c"] += I(U[d]["StarterPromptFirstTurns"]); m["ce"] += I(U[d]["StarterPromptErrors"]); m["o"] += I(U[d]["OrganicFirstTurns"]); m["oe"] += I(U[d]["OrganicFirstErrors"])
        for k in sorted(M):
            m = M[k]; P(f"| {k} | {m['c']:,} | {m['ce']:,} | {m['ce'] / m['c']:.1%} | {m['o']:,} | {m['oe']:,} | {m['oe'] / m['o']:.2%} |" if m["c"] and m["o"] else f"| {k} | {m['c']:,} | {m['ce']:,} | — | {m['o']:,} | {m['oe']:,} | — |")
        P("\nA chip is a click, not a typed question. The same text typed by hand is answered; the chip's click is the thing that fails, in every month, on every chip, on both surfaces and at every hour (brief §64). That is the request path, not the model or an outage.\n")
    P(f"---\n*tools/incidents.py from the published files; events in events.json are the record, this is the list to check against it.*")
    md = "\n".join(out) + "\n"
    if a.stdout: print(md)
    else:
        os.makedirs(os.path.join(REPO, "reports"), exist_ok=True); p = os.path.join(REPO, "reports", "incidents.md"); open(p, "w", encoding="utf-8").write(md); print(f"wrote {os.path.relpath(p, REPO)}: {len(cands)} candidate day(s): {', '.join(cands)}")
    covered = lambda d: any(x["start"][:10] <= d <= (x.get("end") or x["start"])[:10] for x in EV)
    for d in cands:
        if not covered(d):
            e = I(U[d]["Error"]); print(json.dumps({"start": d, "kind": "observed change", "status": "candidate", "evidence": "QA feed: Error outcome (empty response)", "applies_to": "AskCI", "title": f"Error spike: {share[d]:.0%} of turns failed", "detail": f"{e} errors in {turns[d]} turns. Confirm with the service team."}, ensure_ascii=False))


if __name__ == "__main__":
    main()
