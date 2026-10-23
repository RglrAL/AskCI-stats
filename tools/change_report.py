#!/usr/bin/env python3
"""Change report: equal windows before and after a date, from the published files (brief §53, step 4).

One reusable before-and-after reading for a confirmed event or a version change. It is descriptive: it says what
moved and by how much, with intervals, and what did not. It never attributes a change to a cause; the reader does
that with the guardrails and the other events listed.

Windows   N days each side (default 28, a multiple of 7 so both windows hold the same weekday mix by construction;
          the weekday counts are printed so that can be seen). The change day is left out, and so are the days to an
          event's `end` in events.json (a change that settles over two billing days).
Primary   outcome rates on scored turns: cited, not found, clarification, partial (of cited), cited and not partial,
          uncited, and the cited rate for web and pop-up turns separately (a change in the surface mix cannot move
          both); words and pages per cited answer; dislikes per 1,000 and click-throughs per 100 cited answers.
Guardrail traffic and the question mix, which a model-only change should leave alone: turns and conversations a
          day, modal and starter-prompt shares, typed and chip follow-ups, non-Latin script, greetings, out of scope.
          One that moves names something other than the model: traffic, a launch, a chip change.
System    response time, errors and generation cost a turn (settled billing days). A model change can move these;
          so can an outage, a capacity change or the billing, so they are read beside the events listed.
Topic mix the cited rate among topic-attributed turns, then the after window's rate re-weighted to the before window's
          topic mix (direct standardisation, "unknown" left out: failed answers usually carry no topic, so a mix
          adjustment that keeps it understates the change). The share of the change the mix accounts for, and the
          per-topic table.
Rule drift  the mix of deciding phrases (outcome rule ids) between the windows: total variation distance, the phrases
          that moved most, and the share of the after window's not-found and partial answers that sit on phrases the
          before window hardly used. A wording shift is the trace of a model or prompt change.
Wording   the fingerprint per answer (words, list lines, hedges, signposts, links) by outcome.
Conversations  by start day: turns per conversation, single-turn share, reached a cited answer, chip use, and what
          followed a not-found answer.
Intervals 95% Wilson on each rate, Newcombe on each difference. "Moved" = the difference's interval excludes zero and
          the difference is at least 1 point (rates) or 10% (means).

The report was calibrated on the 9 March 2026 model change (brief §57) before it was read on 14 September.

Usage:
    python3 tools/change_report.py 2026-09-14                 # reports/change-2026-09-14.md
    python3 tools/change_report.py 2026-03-09 --days 28 --stdout
    python3 tools/change_report.py --events                   # every confirmed model event, to reports/
"""
import argparse, csv, json, os, re, sys, statistics, collections as C
from datetime import date, datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = 1.96
SETTLEMENT_DAYS = 3        # as CONFIG.settlement_days in index.html
MIN_N = 50                 # a rate needs this many in its denominator
MOVE_PTS, MOVE_REL = 1.0, 0.10
WORDING_RULE = re.compile(r"^(nf|cl)\.|^cited\.partial\.")
ISO = lambda d: d.isoformat()
I = lambda x: int(float(x or 0))


def rd(p):
    with open(os.path.join(REPO, p), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def wilson(k, n):
    if not n:
        return None
    p = k / n; d = 1 + Z * Z / n; c = (p + Z * Z / (2 * n)) / d
    h = Z * ((p * (1 - p) / n + Z * Z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(k1, n1, k2, n2):
    """difference p2 - p1 with its 95% interval (Newcombe method 10)."""
    if not n1 or not n2:
        return None
    p1, p2 = k1 / n1, k2 / n2; l1, u1 = wilson(k1, n1); l2, u2 = wilson(k2, n2); d = p2 - p1
    return d, d - ((p1 - l1) ** 2 + (u2 - p2) ** 2) ** 0.5, d + ((u1 - p1) ** 2 + (p2 - l2) ** 2) ** 0.5


def pct(x, dp=1):
    return "—" if x is None else f"{x * 100:.{dp}f}%"


def pts(t, scale=100, unit=" pts", dp=1):
    if t is None:
        return "—"
    d, lo, hi = t
    s = lambda v: ("+" if v >= 0 else "−") + f"{abs(v) * scale:.{dp}f}"
    return f"{s(d)}{unit} ({s(lo)} to {s(hi)})"


class Window:
    def __init__(self, a, b, label):
        self.a, self.b, self.label = a, b, label

    def has(self, d):
        return self.a <= d <= self.b

    @property
    def days(self):
        return (self.b - self.a).days + 1

    def span(self):
        return f"{self.a:%-d %b}–{self.b:%-d %b %Y}" if self.a.year == self.b.year else f"{self.a:%-d %b %Y}–{self.b:%-d %b %Y}"


def sum_rows(rows, win, datekey="Date", skip=()):
    s = C.Counter(); n = 0
    for r in rows:
        d = r[datekey]
        if win.has(d):
            n += 1
            for k, v in r.items():
                if k not in skip and k != datekey and v not in (None, "") and re.fullmatch(r"-?\d+(\.\d+)?", v):
                    s[k] += float(v)
    s["_days"] = n
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date", nargs="?", help="the change day, YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=28, help="window length each side (default 28)")
    ap.add_argument("--skip", type=int, help="extra days left out after the change day (default: to the event's end)")
    ap.add_argument("--events", action="store_true", help="run for every confirmed model event in events.json")
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--out-dir", default=os.path.join(REPO, "reports"))
    a = ap.parse_args()
    EV = json.load(open(os.path.join(REPO, "events.json")))["events"]
    if a.events:
        dates = [e["start"] for e in EV if e.get("kind") == "model" and e.get("status") == "confirmed"]
    elif a.date:
        dates = [a.date]
    else:
        ap.error("give a date or --events")
    if a.days % 7:
        print(f"note: {a.days} days is not a multiple of 7, so the two windows hold different weekday mixes", file=sys.stderr)
    D = load()
    for ds in dates:
        md = report(ds, a.days, a.skip, EV, D)
        if a.stdout:
            print(md)
        else:
            os.makedirs(a.out_dir, exist_ok=True)
            p = os.path.join(a.out_dir, f"change-{ds}.md")
            open(p, "w", encoding="utf-8").write(md)
            print(f"wrote {os.path.relpath(p, REPO)}")


def load():
    D = {}
    D["usage"] = {r["Date"]: r for r in rd("usage.csv")}
    D["cat"] = rd("category-outcomes-daily.csv")
    D["rules"] = rd("outcome-rules-daily.csv") if os.path.exists(os.path.join(REPO, "outcome-rules-daily.csv")) else []
    D["style"] = rd("answer-style-daily.csv") if os.path.exists(os.path.join(REPO, "answer-style-daily.csv")) else []
    D["conv"] = rd("conversations-daily.csv") if os.path.exists(os.path.join(REPO, "conversations-daily.csv")) else []
    D["next"] = rd("answer-next-daily.csv") if os.path.exists(os.path.join(REPO, "answer-next-daily.csv")) else []
    D["clicks"] = rd("ga4/clicks-daily.csv") if os.path.exists(os.path.join(REPO, "ga4/clicks-daily.csv")) else []
    # generation cost a day: Foundry Models minus embeddings and speech, as the dashboard's "Generation" stage
    gen = C.Counter(); last = None
    if os.path.exists(os.path.join(REPO, "costs.csv")):
        for r in rd("costs.csv"):
            try:
                d = datetime.strptime(r["UsageDate"], "%d/%m/%Y").date()
            except ValueError:
                continue
            last = d if last is None or d > last else last
            if r.get("ServiceName") == "Foundry Models" and not re.search(r"embed|transcribe", r.get("Meter", ""), re.I):
                gen[ISO(d)] += float(r.get("Cost") or 0)
    D["gen"] = gen; D["settled_to"] = ISO(last - timedelta(days=SETTLEMENT_DAYS)) if last else None
    return D


def report(ds, days, skip, EV, D):
    d0 = date.fromisoformat(ds)
    ev = next((e for e in EV if e["start"] == ds and e.get("kind") == "model"), None) or next((e for e in EV if e["start"] == ds), None)
    if skip is None:
        skip = (date.fromisoformat(ev["end"]) - d0).days if ev and ev.get("end") and len(ev["end"]) == 10 else 0
    B = Window(ISO(d0 - timedelta(days=days)), ISO(d0 - timedelta(days=1)), "before")
    A = Window(ISO(d0 + timedelta(days=1 + skip)), ISO(d0 + timedelta(days=days + skip)), "after")
    for w in (B, A):
        w.a, w.b = date.fromisoformat(w.a), date.fromisoformat(w.b)
    U = D["usage"]
    have = lambda w: [d for d in U if w.has(date.fromisoformat(d))]
    if len(have(B)) < 7 or len(have(A)) < 7:
        return f"# Change report: {d0:%-d %B %Y}\n\nNot enough days in usage.csv on both sides ({len(have(B))} before, {len(have(A))} after).\n"
    rows = list(U.values())
    S = {w: sum_rows(rows, WinD(w)) for w in (B, A)}
    out = []; P = out.append
    moved_primary, moved_guard, notes = [], [], []

    # ── header ──────────────────────────────────────────────────────────────
    title = ev["title"] if ev else "no event on record"
    P(f"# Change report: {d0:%-d %B %Y}\n")
    P(f"**Event:** {title}" + (f" ({ev.get('kind')}, {ev.get('status')})" if ev else "") + ".  ")
    P(f"**Windows:** before {B.span()} ({S[B]['_days']:.0f} days), after {A.span()} ({S[A]['_days']:.0f} days); the change day"
      + (f" and the {skip} day(s) after it are" if skip else " is") + " left out. Equal windows of whole weeks hold the same weekday mix.  ")
    wd = lambda w: C.Counter((w.a + timedelta(days=i)).strftime("%a") for i in range(w.days))
    P(f"**Weekdays:** before {dict(wd(B))}; after {dict(wd(A))}.  ")
    inside = [e for e in EV if e is not ev and (B.has(ev_date(e["start"])) or A.has(ev_date(e["start"])))]
    if inside:
        P("**Other events inside the windows** (each is a rival explanation for anything that moved):")
        for e in inside:
            P(f"- {e['start']}: {e['title']} ({e.get('kind')}, {e.get('status')}).")
    else:
        P("**Other events inside the windows:** none on record.")
    P("")
    P("Descriptive only: differences are shown with their intervals, not attributed. A measure has *moved* when its interval excludes zero and the change is at least 1 point (rates) or 10% (means).\n")

    # ── helpers ─────────────────────────────────────────────────────────────
    def rate_row(label, num, den, scale=100, unit=" pts", dp=1, per=None, guard=False, fmt=None):
        k1, n1, k2, n2 = S[B][num] if isinstance(num, str) else num(S[B]), S[B][den] if isinstance(den, str) else den(S[B]), \
                         S[A][num] if isinstance(num, str) else num(S[A]), S[A][den] if isinstance(den, str) else den(S[A])
        if n1 < MIN_N or n2 < MIN_N:
            return f"| {label} | {int(n1):,} | — | {int(n2):,} | — | — | under {MIN_N} |"
        t = newcombe(k1, n1, k2, n2); d, lo, hi = t
        moved = (lo > 0 or hi < 0) and abs(d) * scale >= (MOVE_PTS if scale == 100 else MOVE_PTS * 10)
        f = fmt or (lambda v: f"{v * scale:.{dp}f}" + ("%" if scale == 100 else ""))
        (moved_guard if guard else moved_primary).append((label, d * scale, unit)) if moved else None
        return f"| {label} | {int(n1):,} | {f(k1 / n1)} | {int(n2):,} | {f(k2 / n2)} | {pts(t, scale, unit, dp)} | {'**moved**' if moved else 'steady'} |"

    def mean_row(label, num, den, fmt, guard=True, invert=False):
        n1, n2 = (den(S[B]) if callable(den) else S[B][den]), (den(S[A]) if callable(den) else S[A][den])
        if not n1 or not n2:
            return f"| {label} | — | — | — | — |"
        v1, v2 = (num(S[B]) if callable(num) else S[B][num]) / n1, (num(S[A]) if callable(num) else S[A][num]) / n2
        rel = (v2 - v1) / v1 if v1 else None
        moved = rel is not None and abs(rel) >= MOVE_REL
        if moved:
            (moved_guard if guard else moved_primary).append((label, rel * 100, "%"))
        return f"| {label} | {fmt(v1)} | {fmt(v2)} | {'—' if rel is None else ('+' if rel >= 0 else '−') + f'{abs(rel) * 100:.0f}%'} | {'**moved**' if moved else 'steady'} |"

    # ── 1. primary outcomes ─────────────────────────────────────────────────
    P("## 1. Outcomes (scored turns)\n")
    P("| Rate | Before n | Before | After n | After | Change (95%) | |")
    P("|---|---|---|---|---|---|---|")
    P(rate_row("Cited answer", "Cited", "Scored"))
    P(rate_row("Not found", "NotFound", "Scored"))
    P(rate_row("Clarification", "Clarification", "Scored"))
    P(rate_row("Partial, of cited answers", "Partial", "Cited"))
    P(rate_row("Cited and not partial", lambda s: s["Cited"] - s["Partial"], "Scored"))
    P(rate_row("Uncited", "Uncited", "Scored", dp=2))
    P(rate_row("Cited answer, web turns only", "WebCited", "WebScored"))
    P(rate_row("Cited answer, pop-up turns only", "ModalCited", "ModalScored"))
    P(rate_row("Dislikes per 1,000 cited answers", "DislikesOnCited", "Cited", scale=1000, unit=" per 1,000", dp=1, fmt=lambda v: f"{v * 1000:.1f}"))
    P("")
    P("| Per cited answer | Before | After | Change | |")
    P("|---|---|---|---|---|")
    P(mean_row("Words", "CitedWords", "CitedWordsTurns", lambda v: f"{v:.0f}", guard=False))
    P(mean_row("Pages cited", "Citations", "Cited", lambda v: f"{v:.2f}", guard=False))
    ck_b, ck_a = clicks_per_cited(D, U, B), clicks_per_cited(D, U, A)
    if ck_b and ck_a and ck_b[0] is not None and ck_a[0] is not None:
        rel = (ck_a[0] - ck_b[0]) / ck_b[0] if ck_b[0] else None; mv = rel is not None and abs(rel) >= MOVE_REL
        if mv: moved_primary.append(("Click-throughs per 100 cited answers", rel * 100, "%"))
        P(f"| Click-throughs per 100 cited answers (days with GA4: {ck_b[1]} / {ck_a[1]}) | {ck_b[0]:.1f} | {ck_a[0]:.1f} | {'—' if rel is None else ('+' if rel >= 0 else '−') + f'{abs(rel) * 100:.0f}%'} | {'**moved**' if mv else 'steady'} |")
    else:
        P(f"| Click-throughs per 100 cited answers | — | — | — | GA4 covers {ck_b[1] if ck_b else 0} / {ck_a[1] if ck_a else 0} days; needs 7 on each side |")
    P("")

    # ── 2. guardrails: traffic and the question mix ─────────────────────────
    P("## 2. Guardrails: traffic and the question mix (should not move for a model-only change)\n")
    P("| Measure | Before | After | Change | |")
    P("|---|---|---|---|---|")
    P(mean_row("Turns a day", "Questions", "_days", lambda v: f"{v:,.0f}"))
    P(mean_row("Conversations a day", "Sessions", "_days", lambda v: f"{v:,.0f}"))
    P("")
    P("| Share of turns | Before n | Before | After n | After | Change (95%) | |")
    P("|---|---|---|---|---|---|---|")
    P(rate_row("Modal (pop-up) turns", "ModalTurns", "Questions", guard=True))
    P(rate_row("Starter prompt, of first turns", "StarterPromptFirstTurns", lambda s: s["StarterPromptFirstTurns"] + s["OrganicFirstTurns"], guard=True))
    P(rate_row("Typed follow-ups", "UserFollowup", "Questions", guard=True))
    P(rate_row("Chip follow-ups", "SuggestedFollowup", "Questions", guard=True))
    P(rate_row("Non-Latin script", lambda s: s["Questions"] - s["ScriptLatin"] - s["ScriptNone"], "Questions", guard=True, dp=2))
    P(rate_row("Greeting", "Greeting", "Questions", guard=True, dp=2))
    P(rate_row("Out of scope", "OutOfScope", "Questions", guard=True, dp=2))
    P("")

    # ── 2b. system: response time, errors, cost ──────────────────────────────
    P("## 2b. System: response time, errors and cost (a model change can move these; so can an outage, a capacity change or the billing)\n")
    moved_sys = []
    P("| Measure | Before | After | Change | |")
    P("|---|---|---|---|---|")
    P("| Response time p50 (median of days) " + med_row(U, B, A, "LatencyP50ms", moved_sys))
    P("| Response time p90 (median of days) " + med_row(U, B, A, "LatencyP90ms", moved_sys))
    gen_b, gen_a = gen_per_turn(D, U, B), gen_per_turn(D, U, A)
    if gen_b and gen_a:
        rel = (gen_a[0] - gen_b[0]) / gen_b[0]; mv = abs(rel) >= MOVE_REL
        if mv: moved_sys.append(("Generation cost a turn", rel * 100, "%"))
        P(f"| Generation cost a turn (settled billing days: {gen_b[1]} / {gen_a[1]}) | {gen_b[0]:.2f}p | {gen_a[0]:.2f}p | {'+' if rel >= 0 else '−'}{abs(rel) * 100:.0f}% | {'**moved**' if mv else 'steady'} |")
    else:
        P("| Generation cost a turn | — | — | — | no settled billing days on both sides |")
    P("")
    P("| Share of turns | Before n | Before | After n | After | Change (95%) | |")
    P("|---|---|---|---|---|---|---|")
    hold, moved_guard[:] = moved_guard[:], []
    P(rate_row("Error", "Error", "Questions", guard=True, dp=2))
    P(rate_row("Over 30 s, of timed turns", "LatOver30s", lambda s: s["LatUnder10s"] + s["Lat10to20s"] + s["Lat20to30s"] + s["LatOver30s"], guard=True))
    moved_sys += moved_guard; moved_guard[:] = hold
    P("")

    # ── 3. topic mix ────────────────────────────────────────────────────────
    P("## 3. Topic mix\n")
    mix = topic_mix(D["cat"], B, A)
    if mix:
        P(f"Among topic-attributed scored turns (a turn may carry more than one topic; \"unknown\" left out), the cited rate went {pct(mix['pb'])} → {pct(mix['pa'])}. "
          f"Re-weighted to the before window's topic mix the after rate is {pct(mix['std'])}, so the mix accounts for "
          + (f"**{'none' if abs(mix['share']) < 0.05 else ('−' if mix['share'] < 0 else '') + f'{abs(mix[chr(115)+chr(104)+chr(97)+chr(114)+chr(101)]) * 100:.0f}%'}** of the change" if mix['share'] is not None else "— (the change is under half a point)")
          + f". \"Unknown\" was {pct(mix['ub'])} of scored turns before and {pct(mix['ua'])} after; failed answers usually carry no topic, so a rise there is part of the change, not the mix.\n")
        notes.append(("mix", mix['share']))
        P("| Topic | Before n | Before cited | After n | After cited | Change (95%) | |")
        P("|---|---|---|---|---|---|---|")
        for c, kb, nb, ka, na in mix["rows"][:12]:
            t = newcombe(kb, nb, ka, na) if nb >= MIN_N and na >= MIN_N else None
            mv = t is not None and (t[1] > 0 or t[2] < 0) and abs(t[0]) * 100 >= MOVE_PTS
            P(f"| {c} | {nb:,} | {pct(kb / nb) if nb else '—'} | {na:,} | {pct(ka / na) if na else '—'} | {pts(t)} | {'**moved**' if mv else 'steady' if t else ''} |")
        P(f"\n{sum(1 for c, kb, nb, ka, na in mix['rows'] if nb >= MIN_N and na >= MIN_N and (lambda t: t and (t[1] > 0 or t[2] < 0) and abs(t[0]) * 100 >= MOVE_PTS)(newcombe(kb, nb, ka, na)))} of {sum(1 for r in mix['rows'] if r[2] >= MIN_N and r[4] >= MIN_N)} topics with {MIN_N}+ turns on both sides moved. A change across most topics is a system change; one or two topics moving is content.\n")
    else:
        P("No topic data on both sides.\n")

    # ── 4. rule drift ───────────────────────────────────────────────────────
    P("## 4. Deciding phrases (outcome rule ids)\n")
    dr = rule_drift(D["rules"], B, A)
    if dr:
        P(f"Mix of not-found, clarification and partial phrases: **{dr['tvd'] * 100:.0f}%** of it moved between the windows (total variation distance; the dashboard's weekly drift flag is at 20%). "
          f"Of the after window's not-found answers, {pct(dr['nf_new'])} sit on phrases that were under 1% of the before window's not-found answers; of its partial answers, {pct(dr['pt_new'])}.\n")
        notes.append(("drift", dr))
        P("| Phrase | Before per 1,000 turns | After per 1,000 | Change |")
        P("|---|---|---|---|")
        for k, b, a_ in dr["movers"][:10]:
            P(f"| {k} | {b:.1f} | {a_:.1f} | {'+' if a_ >= b else '−'}{abs(a_ - b):.1f} |")
        P("")
    else:
        P("No outcome-rule data on both sides.\n")

    # ── 5. wording ──────────────────────────────────────────────────────────
    P("## 5. How the answers are written (per answer)\n")
    st = {w: C.defaultdict(C.Counter) for w in (B, A)}
    for r in D["style"]:
        for w in (B, A):
            if w.has(date.fromisoformat(r["Date"])):
                for k, v in r.items():
                    if k not in ("Date", "Outcome"): st[w][r["Outcome"]][k] += I(v)
    if any(st[w] for w in (B, A)):
        P("| Outcome | Answers (before / after) | Words | List lines | Hedges | Signposts | Links |")
        P("|---|---|---|---|---|---|---|")
        for oc in ("Cited answer", "Not found", "Clarification"):
            b, a_ = st[B][oc], st[A][oc]
            if b["Turns"] < MIN_N or a_["Turns"] < MIN_N:
                continue
            cell = lambda k: f"{b[k] / b['Turns']:.2f} → {a_[k] / a_['Turns']:.2f}" if k != "Words" else f"{b[k] / b['Turns']:.0f} → {a_[k] / a_['Turns']:.0f}"
            P(f"| {oc} | {b['Turns']:,} / {a_['Turns']:,} | {cell('Words')} | {cell('Lines')} | {cell('Hedges')} | {cell('Signposts')} | {cell('Links')} |")
        P("")
    else:
        P("No wording data on both sides.\n")

    # ── 6. conversations ────────────────────────────────────────────────────
    P("## 6. Conversations (by start day, finished conversations)\n")
    cv = {w: sum_rows(D["conv"], WinD(w)) for w in (B, A)}
    if cv[B]["Mature"] >= MIN_N and cv[A]["Mature"] >= MIN_N:
        S2 = {B: cv[B], A: cv[A]}
        def rr(label, num, den):
            k1, n1, k2, n2 = S2[B][num], S2[B][den], S2[A][num], S2[A][den]
            if n1 < MIN_N or n2 < MIN_N:
                return f"| {label} | {int(n1):,} | — | {int(n2):,} | — | — | under {MIN_N} |"
            t = newcombe(k1, n1, k2, n2); mv = (t[1] > 0 or t[2] < 0) and abs(t[0]) * 100 >= MOVE_PTS
            if mv: moved_primary.append((label, t[0] * 100, " pts"))
            return f"| {label} | {int(n1):,} | {pct(k1 / n1)} | {int(n2):,} | {pct(k2 / n2)} | {pts(t)} | {'**moved**' if mv else 'steady'} |"
        P(f"Turns per conversation {cv[B]['MatureTurns'] / cv[B]['Mature']:.2f} → {cv[A]['MatureTurns'] / cv[A]['Mature']:.2f}.\n")
        P("| Share | Before n | Before | After n | After | Change (95%) | |")
        P("|---|---|---|---|---|---|---|")
        P(rr("Single-turn conversations", "Turns1", "Mature"))
        P(rr("Reached a cited answer", "ReachedCited", "Mature"))
        P(rr("Used a chip", "ChipUse", "Mature"))
        P(rr("Not-found answers: conversation ended there", "NFEnded", "NFTurns"))
        P(rr("Not-found answers: a later turn was cited", "NFLaterCited", "NFTurns"))
        P(rr("Clarifications: a later turn was cited", "ClarLaterCited", "ClarTurns"))
        P("")
    else:
        P("Not enough finished conversations on both sides.\n")

    # ── 6b. follow-ups against first questions ──────────────────────────────
    # Follow-ups pass through the question-rewriting step (the smaller model, brief §53); first questions do not.
    # If follow-ups moved more than new questions, that step is implicated; if alike, the change is downstream of it.
    P("## 6b. Follow-ups against new questions\n")
    ty = [("New topic", "NewTopic"), ("Typed follow-up", "UserFollowup"), ("Chip follow-up", "Suggested")]
    if all(S[w][p + "Scored"] >= MIN_N for w in (B, A) for _, p in ty):
        P("| Question type | Before n | Cited | Not found | After n | Cited | Not found | Cited change (95%) | Not-found change (95%) |")
        P("|---|---|---|---|---|---|---|---|---|")
        dd = {}
        for l, p in ty:
            b, a_ = S[B], S[A]
            tc = newcombe(b[p + "Cited"], b[p + "Scored"], a_[p + "Cited"], a_[p + "Scored"]); tn = newcombe(b[p + "NotFound"], b[p + "Scored"], a_[p + "NotFound"], a_[p + "Scored"])
            dd[p] = (tc, tn)
            P(f"| {l} | {int(b[p + 'Scored']):,} | {pct(b[p + 'Cited'] / b[p + 'Scored'])} | {pct(b[p + 'NotFound'] / b[p + 'Scored'])} | {int(a_[p + 'Scored']):,} | {pct(a_[p + 'Cited'] / a_[p + 'Scored'])} | {pct(a_[p + 'NotFound'] / a_[p + 'Scored'])} | {pts(tc)} | {pts(tn)} |")
        # difference in differences: follow-up change minus new-topic change, interval by adding the variances
        def did(p, i):
            x, y = dd[p][i], dd["NewTopic"][i]; d = x[0] - y[0]; h = (((x[2] - x[1]) / 2) ** 2 + ((y[2] - y[1]) / 2) ** 2) ** 0.5
            return d, d - h, d + h
        # the verdict rests on typed follow-ups: chips are a fixed set near a 99% ceiling, and the set itself changes
        c, n = did("UserFollowup", 0), did("UserFollowup", 1); tot = dd["UserFollowup"][0][0]
        fl = (c[1] > 0 or c[2] < 0) and abs(c[0]) * 100 >= MOVE_PTS
        share = abs(c[0] / tot) if fl and tot and abs(c[0]) < abs(tot) else None
        P(f"\nTyped follow-ups against new topics: the cited rate moved {pts(c)} more, the not-found rate {pts(n)} more. "
          + ("**The follow-up path moved on its own.**" if fl and share is None or (fl and share >= 0.5) else f"A small extra on a shared change: the follow-up path accounts for at most {share * 100:.0f}% of the typed follow-up fall." if fl else "Alike: the change is not specific to the follow-up path."))
        cc = did("Suggested", 0)
        P(f"Chip follow-ups moved {pts(cc)} more than new topics, but chips are a fixed set of well-covered questions near a 99% ceiling, so they cannot fall as far; they are not used for the verdict.")
        notes.append(("fu", "own" if fl and (share is None or share >= 0.5) else f"extra:{share * 100:.0f}" if fl else "alike"))
        P("")
    else:
        P("Too few scored turns of one type on a side.\n")
    if cv[B].get("TypedTopicBoth") is not None and cv[A].get("TypedTopicBoth") is not None:
        P("| Follow-up turns where both turns carry a topic | Before n | Switched topic | After n | Switched topic | Change (95%) | |")
        P("|---|---|---|---|---|---|---|")
        for l, t in (("Typed follow-up", "Typed"), ("Chip follow-up", "Chip"), ("New topic (as classified)", "New")):
            k1, n1, k2, n2 = cv[B][t + "TopicSwitched"], cv[B][t + "TopicBoth"], cv[A][t + "TopicSwitched"], cv[A][t + "TopicBoth"]
            if n1 < MIN_N or n2 < MIN_N:
                P(f"| {l} | {int(n1):,} | — | {int(n2):,} | — | — | under {MIN_N} |"); continue
            tt = newcombe(k1, n1, k2, n2); mv = (tt[1] > 0 or tt[2] < 0) and abs(tt[0]) * 100 >= MOVE_PTS
            P(f"| {l} | {int(n1):,} | {pct(k1 / n1)} | {int(n2):,} | {pct(k2 / n2)} | {pts(tt)} | {'**moved**' if mv else 'steady'} |")
        P("\nA topic comes from the cited page, so drift is measured only between two answers that both cite one. A follow-up that switched topic is one the rewriting step may have reread; a typed follow-up switching more often than before is the trace of a rewriting change.\n")

    # ── 7. reading ──────────────────────────────────────────────────────────
    P("## 7. Reading\n")
    if moved_primary:
        P("**Outcomes that moved:** " + "; ".join(f"{l} {'+' if v >= 0 else '−'}{abs(v):.1f}{u}" for l, v, u in moved_primary) + ".  ")
    else:
        P("**Outcomes that moved:** none.  ")
    if moved_guard:
        P("**Traffic and mix guardrails that moved:** " + "; ".join(f"{l} {'+' if v >= 0 else '−'}{abs(v):.0f}{u}" for l, v, u in moved_guard) + ". Each names something other than the model (see the events listed above), and what moved in the outcomes may be its work as much as the event's.  ")
    else:
        P("**Traffic and mix guardrails that moved:** none. The traffic and the question mix held, so what moved in the outcomes is not a change in who asked or how.  ")
    if moved_sys:
        P("**System measures that moved:** " + "; ".join(f"{l} {'+' if v >= 0 else '−'}{abs(v):.0f}{u}" for l, v, u in moved_sys) + ". A model change can do this; an outage or capacity change can too.  ")
    else:
        P("**System measures that moved:** none. Response time, errors and cost a turn held.  ")
    m = dict(notes)
    if "mix" in m:
        P("**Topic mix:** " + (("accounts for none of the change in the cited rate." if abs(m['mix']) < 0.05 else f"accounts for {m['mix'] * 100:.0f}% of the change in the cited rate.") if m["mix"] is not None else "no change in the cited rate to account for.") + "  ")
    fu = dict(notes).get("fu")
    if fu:
        P("**Follow-ups:** " + ("typed follow-ups moved on their own, apart from new questions: that points at the question-rewriting step." if fu == "own" else f"typed follow-ups moved a little more than new questions; the rewriting step accounts for at most {fu.split(':')[1]}% of their fall, the rest is shared with first questions." if fu.startswith("extra") else "typed follow-ups and new questions moved alike, so the change is not specific to the rewriting step.") + "  ")
    if "drift" in m:
        d = m["drift"]
        P(f"**Wording:** {d['tvd'] * 100:.0f}% of the phrase mix moved; {pct(d['nf_new'])} of after not-found answers and {pct(d['pt_new'])} of after partial answers use phrases the before window hardly used. "
          + ("A shift this size on a confirmed model change is that model's wording; on a date with no model change it is the trace of a prompt or configuration change." if d['tvd'] >= 0.2 else "The phrases are the same ones as before.") + "  ")
    P("\nWhat this cannot say: whether any label is right. That is the hand-labelled sample. A system change shows as outcomes moving across topics with steady guardrails and little mix share; a content change shows as one or two topics; a traffic or launch change shows in the guardrails first.")
    P(f"\n---\n*Generated by tools/change_report.py from the published files; windows of {days} days; intervals 95% Wilson and Newcombe; rates need {MIN_N}+ in the denominator. Billing settled to {D['settled_to'] or '—'}.*")
    return "\n".join(out) + "\n"


def ev_date(s):
    """an event's start: a day, or a month (events.json allows "2026-05"), taken as its first day"""
    return date.fromisoformat(s if len(s) == 10 else s + "-01")


class WinD:
    """a Window wrapper that tests ISO date strings"""
    def __init__(self, w): self.w = w
    def has(self, d): return self.w.has(date.fromisoformat(d))


def med_row(U, B, A, col, moved_guard):
    vb = [I(U[d][col]) for d in U if B.has(date.fromisoformat(d)) and I(U[d][col]) > 0]
    va = [I(U[d][col]) for d in U if A.has(date.fromisoformat(d)) and I(U[d][col]) > 0]
    if len(vb) < 7 or len(va) < 7:
        return "| — | — | — | under 7 timed days |"
    m1, m2 = statistics.median(vb) / 1000, statistics.median(va) / 1000; rel = (m2 - m1) / m1; mv = abs(rel) >= MOVE_REL
    if mv: moved_guard.append((f"Response time {'p50' if '50' in col else 'p90'}", rel * 100, "%"))
    return f"| {m1:.1f} s | {m2:.1f} s | {'+' if rel >= 0 else '−'}{abs(rel) * 100:.0f}% | {'**moved**' if mv else 'steady'} |"


def gen_per_turn(D, U, w):
    if not D["gen"] or not D["settled_to"]:
        return None
    cost = turns = n = 0
    for d, r in U.items():
        if w.has(date.fromisoformat(d)) and d <= D["settled_to"] and d in D["gen"] and I(r["Questions"]) > 0:
            cost += D["gen"][d]; turns += I(r["Questions"]); n += 1
    return (cost / turns * 100, n) if n >= 7 and turns else None


def clicks_per_cited(D, U, w):
    if not D["clicks"]:
        return None
    byday = C.Counter()
    for r in D["clicks"]:
        byday[r["Date"]] += I(r["Views"])
    v = c = n = 0
    for d in byday:
        if d in U and w.has(date.fromisoformat(d)):
            v += byday[d]; c += I(U[d]["Cited"]); n += 1
    return (v / c * 100, n) if n >= 7 and c else (None, n)


def topic_mix(rows, B, A):
    bk, bn, ak, an = C.Counter(), C.Counter(), C.Counter(), C.Counter(); ub = ua = sb = sa = 0
    for r in rows:
        d = date.fromisoformat(r["Date"]); c = r["Category"]; sc, ci = I(r["Scored"]), I(r["Cited"])
        if B.has(d):
            sb += sc
            if c == "unknown": ub += sc
            else: bk[c] += ci; bn[c] += sc
        elif A.has(d):
            sa += sc
            if c == "unknown": ua += sc
            else: ak[c] += ci; an[c] += sc
    if sum(bn.values()) < MIN_N or sum(an.values()) < MIN_N:
        return None
    pb, pa = sum(bk.values()) / sum(bn.values()), sum(ak.values()) / sum(an.values())
    both = [c for c in bn if an[c] > 0]; wsum = sum(bn[c] for c in both)
    std = sum(bn[c] / wsum * (ak[c] / an[c]) for c in both)
    share = (pa - std) / (pa - pb) if abs(pa - pb) >= 0.005 else None
    rows_ = sorted(((c, bk[c], bn[c], ak[c], an[c]) for c in set(bn) | set(an)), key=lambda x: -(x[2] + x[4]))
    return dict(pb=pb, pa=pa, std=std, share=share, ub=ub / sb if sb else None, ua=ua / sa if sa else None, rows=rows_)


def rule_drift(rows, B, A):
    b, a_ = C.Counter(), C.Counter(); tb = ta = 0
    for r in rows:
        d = date.fromisoformat(r["Date"]); n = I(r["Turns"])
        if B.has(d): b[r["Rule"]] += n; tb += n
        elif A.has(d): a_[r["Rule"]] += n; ta += n
    if not tb or not ta:
        return None
    wb = {k: v for k, v in b.items() if WORDING_RULE.match(k)}; wa = {k: v for k, v in a_.items() if WORDING_RULE.match(k)}
    sb, sa = sum(wb.values()), sum(wa.values())
    if sb < 100 or sa < 100:
        return None
    keys = set(wb) | set(wa)
    tvd = sum(abs(wa.get(k, 0) / sa - wb.get(k, 0) / sb) for k in keys) / 2
    def new_share(prefix):
        pb = {k: v for k, v in b.items() if k.startswith(prefix)}; pa = {k: v for k, v in a_.items() if k.startswith(prefix)}
        nb, na = sum(pb.values()), sum(pa.values())
        if not na or not nb:
            return None
        return sum(v for k, v in pa.items() if pb.get(k, 0) / nb < 0.01) / na
    movers = sorted(((k, b.get(k, 0) / tb * 1000, a_.get(k, 0) / ta * 1000) for k in keys), key=lambda x: -abs(x[2] - x[1]))
    return dict(tvd=tvd, nf_new=new_share("nf."), pt_new=new_share("cited.partial."), movers=movers)


if __name__ == "__main__":
    main()
