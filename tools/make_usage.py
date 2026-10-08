#!/usr/bin/env python3
"""Generate the dashboard's daily aggregate files from AskCI QA feed exports (raw or redacted).

Outputs (all daily counts; nothing per-turn and no text crosses into the dashboard):

  usage.csv            Date, Questions, Sessions, then optional columns the dashboard may use:
                         Answered, Unanswered, Flagged            turn outcomes (see below)
                         NewTopic, UserFollowup, SuggestedFollowup  question types
                         ModalTurns, WebTurns, OtherTurns, ModalSessions, WebSessions  by source
                         Citations                                 cited URLs
                         LatencyP50ms, LatencyP90ms                response time, positive values only
                         VoiceTurns, VoiceSessions                 only when the export has an input-mode column
  usage-hours.csv      Date, Hour, Turns, Sessions   (hour of day, Irish time)
  categories.csv       Category, Citations, Month    (current dashboard contract; display names)
  categories-daily.csv Date, Category, Citations     (slugs, by day)

Definitions:
  Questions   turns received (one feed row each)
  Sessions    conversations started (distinct Conversation ID with Turn # == 1)
  Answered    turns with at least one citation URL
  Flagged     turns with Flagged == Yes (these carry no citations)
  Unanswered  turns with no citation and not flagged
  Categories  one hit per distinct category per turn, from the Categories column (or, if blank,
              from the /en/<category>/ segment of the cited URLs). From April 2026 the feed's
              Categories column is already distinct per turn, so this equals the hand-maintained
              categories.csv (within 5%). Before April the column repeated a category once per
              citation, and the old file counted those repeats, which inflated Jan–Mar by roughly
              40%. `--category-rule tokens` reproduces that old counting if continuity matters.

Rows repeated across input files (same Conversation ID and Turn #, as happens on the boundary
day of two exports) are counted once.

Feed timestamps are Irish local time (Europe/Dublin, confirmed 8 Oct 2026), so days and hours
here are Irish. The feed files themselves stay out of git.

Usage:
    python3 tools/make_usage.py qa-feed-redacted_*.csv --out-dir .          # write the four files
    python3 tools/make_usage.py qa-feed-redacted_*.csv --compare .          # compare with existing files, write nothing
    python3 tools/make_usage.py qa-feed_*.csv -o usage.csv                  # usage.csv only (old behaviour)
"""
import argparse, csv, os, re, sys
from collections import defaultdict
from datetime import datetime

TS_FORMAT = "%b %d, %Y %H:%M"   # e.g. "Jun 06, 2026 19:50"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
CAT_NAME = {  # feed slug -> display name used by the existing categories.csv (later months' spelling)
    "social-welfare": "Social Welfare", "money-and-tax": "Money & Tax", "employment": "Employment",
    "moving-country": "Moving Country", "housing": "Housing", "travel-and-recreation": "Travel and Recreation",
    "birth-family-relationships": "Family and Relationships", "health": "Health", "returning-to-ireland": "RTI",
    "education": "Education", "justice": "Justice", "consumer": "Consumer", "death": "Death", "about": "About",
    "government-in-ireland": "Government in Ireland", "environment": "Environment",
}
URL_RE = re.compile(r'https?://[^\s,;|"]+')
# Category from a cited URL: citizensinformation.ie only, /en/<slug>/ or the old-site /<slug>/ with
# underscores; the slug must be a known category or the hit is dropped (and counted).
CAT_SEG_RE = re.compile(r'^https?://(?:www\.)?citizensinformation\.ie/(?:en/)?([^/?#]+)')
KNOWN_SLUGS = set(CAT_NAME) | {"my-situation"}


def url_slug(u):
    m = CAT_SEG_RE.match(u)
    if not m:
        return None
    slug = m.group(1).lower().replace("_", "-")
    return slug if slug in KNOWN_SLUGS else None
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def pct(sorted_vals, p):
    if not sorted_vals:
        return ""
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100 * len(sorted_vals) + 0.5)) - 1))
    return sorted_vals[k]


def find_col(fields, pattern):
    rx = re.compile(pattern, re.I)
    return next((c for c in fields if rx.search(c)), None)


CATEGORY_RULE = "distinct"   # or "tokens": every Categories entry, repeats included, no URL fallback (old file's rule)


def aggregate(files):
    D = defaultdict(lambda: defaultdict(int))        # date -> counter name -> n
    sess = defaultdict(lambda: defaultdict(set))     # date -> set name -> conversation ids
    lat = defaultdict(list)                          # date -> latencies
    hours = defaultdict(lambda: defaultdict(int))    # (date, hour) -> turns
    hour_sess = defaultdict(set)                     # (date, hour) -> conversation ids (turn 1)
    cats = defaultdict(lambda: defaultdict(int))     # date -> slug -> hits
    bad = 0; has_voice = False; cat_dropped = 0
    seen = set(); dupes = 0   # exports taken on different days overlap on their boundary day
    for f in files:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            r = csv.DictReader(fh)
            voice_col = find_col(r.fieldnames, r"input.?mode|modality")
            has_voice = has_voice or bool(voice_col)
            for row in r:
                key = (row.get("Conversation ID") or "", (row.get("Turn #") or "").strip())
                if key in seen:
                    dupes += 1
                    continue
                seen.add(key)
                ts = (row.get("Timestamp") or "").strip()
                try:
                    t = datetime.strptime(ts, TS_FORMAT)
                except ValueError:
                    bad += 1
                    continue
                d = t.date(); conv = row.get("Conversation ID") or ""
                first = (row.get("Turn #") or "").strip() == "1"
                c = D[d]; c["turns"] += 1
                if first: sess[d]["all"].add(conv)
                hours[(d, t.hour)]["turns"] += 1
                if first: hour_sess[(d, t.hour)].add(conv)
                # outcome
                urls = URL_RE.findall(row.get("Citations") or "")
                flagged = (row.get("Flagged") or "").strip().lower() == "yes"
                if urls: c["answered"] += 1
                elif flagged: c["flagged"] += 1
                else: c["unanswered"] += 1
                c["citations"] += len(urls)
                # question type
                qt = (row.get("Question Type") or "").strip()
                if qt == "new_topic": c["new_topic"] += 1
                elif qt == "user_followup": c["user_followup"] += 1
                elif qt == "suggested_followup": c["suggested_followup"] += 1
                # source
                src = (row.get("Source") or "").strip().lower()
                key = "modal" if src == "modal" else "web" if src == "web" else "other"
                c[key + "_turns"] += 1
                if first and key != "other": sess[d][key].add(conv)
                # latency
                try:
                    ms = int(float(row.get("Response Time (ms)") or ""))
                    if ms > 0: lat[d].append(ms)
                except ValueError:
                    pass
                # voice
                if voice_col and "voice" in (row.get(voice_col) or "").lower():
                    c["voice_turns"] += 1
                    if first: sess[d]["voice"].add(conv)
                # categories: one hit per distinct category per turn
                toks = [s.strip() for s in (row.get("Categories") or "").split(",") if s.strip()]
                if CATEGORY_RULE == "tokens":          # old file's rule: column entries only, repeats included, no URL fallback
                    for s in toks: cats[d][s] += 1
                else:
                    if not toks and urls:
                        slugs = [url_slug(u) for u in urls]
                        cat_dropped += sum(1 for x in slugs if x is None)
                        toks = [x for x in slugs if x]
                    for s in set(toks): cats[d][s] += 1
    return D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped


def usage_rows(D, sess, lat, has_voice):
    cols = ["Date", "Questions", "Sessions", "Answered", "Unanswered", "Flagged", "NewTopic", "UserFollowup", "SuggestedFollowup",
            "ModalTurns", "WebTurns", "OtherTurns", "ModalSessions", "WebSessions", "Citations", "LatencyP50ms", "LatencyP90ms"]
    if has_voice: cols += ["VoiceTurns", "VoiceSessions"]
    out = []
    for d in sorted(D):
        c = D[d]; s = sess[d]; L = sorted(lat[d])
        row = [d.isoformat(), c["turns"], len(s["all"]), c["answered"], c["unanswered"], c["flagged"], c["new_topic"], c["user_followup"],
               c["suggested_followup"], c["modal_turns"], c["web_turns"], c["other_turns"], len(s["modal"]), len(s["web"]), c["citations"],
               pct(L, 50), pct(L, 90)]
        if has_voice: row += [c["voice_turns"], len(s["voice"])]
        out.append(row)
    return cols, out


def hours_rows(hours, hour_sess):
    return ["Date", "Hour", "Turns", "Sessions"], [[d.isoformat(), h, v["turns"], len(hour_sess[(d, h)])] for (d, h), v in sorted(hours.items())]


def categories_rows(cats):
    monthly = defaultdict(lambda: defaultdict(int)); years = set()
    for d, m in cats.items():
        years.add(d.year)
        for s, n in m.items(): monthly[(d.year, d.month)][s] += n
    if len(years) > 1:
        print(f"warning: categories.csv has no year column and the feed spans {sorted(years)}; the dashboard assumes CONFIG.categories_year", file=sys.stderr)
    out = []
    for (y, mo) in sorted(monthly):
        for s, n in sorted(monthly[(y, mo)].items(), key=lambda kv: -kv[1]):
            out.append([CAT_NAME.get(s, s.replace("-", " ").title()), n, MONTHS[mo - 1]])
    daily = [[d.isoformat(), s, n] for d in sorted(cats) for s, n in sorted(cats[d].items(), key=lambda kv: -kv[1])]
    return (["Category", "Citations", "Month"], out), (["Date", "Category", "Citations"], daily)


def write(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def parse_any_date(s):
    s = s.strip().replace("Sept", "Sep")
    for fmt in ("%Y-%m-%d", "%d-%b-%y", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None


def compare(d, ucols, urows, ccols, crows):
    up = os.path.join(d, "usage.csv"); cp = os.path.join(d, "categories.csv")
    if os.path.exists(up):
        ex = {}
        with open(up, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                dt = parse_any_date(r.get("Date") or "")
                if dt: ex[dt] = (int(r["Questions"].replace(",", "")), int(r["Sessions"].replace(",", "")))
        print(f"\nusage.csv: generated vs {up}")
        tq = tg = sq = sg = 0; shown = 0
        for row in urows:
            dt = datetime.fromisoformat(row[0]).date(); e = ex.get(dt)
            if e: tq += e[0]; sq += e[1]
            tg += row[1]; sg += row[2]
            if shown < 40 or (e and (e[0] != row[1] or e[1] != row[2])):
                mark = "" if (e and e[0] == row[1] and e[1] == row[2]) else "  <-- differs" if e else "  (not in existing)"
                print(f"  {row[0]}: feed {row[1]:5d} turns / {row[2]:5d} conv · existing {e[0] if e else '—':>5} / {e[1] if e else '—':>5}{mark}"); shown += 1
        if tq: print(f"  totals on shared days: feed {tg} / {sg}  existing {tq} / {sq}  ({(tg - tq) / tq * 100:+.1f}% turns, {(sg - sq) / sq * 100:+.1f}% conversations)")
    else:
        print(f"\n{up} not found; usage comparison skipped")
    if os.path.exists(cp):
        ex = defaultdict(int)
        with open(cp, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                name = (r.get("Category") or next(iter(r.values())) or "").strip(); mo = (r.get("Month") or "").strip()
                if name and mo: ex[(mo, name)] += int((r.get("Citations") or "0").replace(",", "") or 0)
        gen = defaultdict(int)
        for name, n, mo in crows: gen[(mo, name)] += n
        print(f"\ncategories.csv: generated vs {cp} (months present in the feed only)")
        for mo in [m for m in MONTHS if any(k[0] == m for k in gen)]:
            g = sum(v for k, v in gen.items() if k[0] == mo); e = sum(v for k, v in ex.items() if k[0] == mo)
            print(f"  {mo}: feed {g} · existing {e}" + (f"  ({(g - e) / e * 100:+.1f}%)" if e else "  (not in existing)"))
            for name in sorted({k[1] for k in gen if k[0] == mo} | {k[1] for k in ex if k[0] == mo}):
                gv, ev = gen.get((mo, name), 0), ex.get((mo, name), 0)
                if gv != ev: print(f"      {name:26s} feed {gv:6d}  existing {ev:6d}")
    else:
        print(f"\n{cp} not found; categories comparison skipped")


def main():
    ap = argparse.ArgumentParser(description="Daily aggregates for the AskCI cost dashboard from QA feed exports.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", help="write usage.csv here (usage only)")
    ap.add_argument("--out-dir", help="write usage.csv, usage-hours.csv, categories.csv and categories-daily.csv here")
    ap.add_argument("--compare", metavar="DIR", help="compare with the usage.csv and categories.csv in DIR; write nothing")
    ap.add_argument("--keep-partial", action="store_true", help="keep the last day even when it is the export day (partial by default it is dropped)")
    ap.add_argument("--category-rule", choices=["distinct", "tokens"], default="distinct", help="distinct per turn with URL fallback (default), or every Categories entry incl. repeats and no fallback (old file's rule)")
    a = ap.parse_args()
    global CATEGORY_RULE; CATEGORY_RULE = a.category_rule
    D, sess, lat, hours, hour_sess, cats, bad, has_voice, dupes, cat_dropped = aggregate(a.files)
    if bad: print(f"warning: {bad} rows with unreadable Timestamp skipped", file=sys.stderr)
    if dupes: print(f"note: {dupes} rows repeated across the input files (same conversation and turn) counted once")
    if cat_dropped: print(f"note: {cat_dropped} cited URLs on rows with a blank Categories column were not citizensinformation.ie category pages; not counted")
    if not D: sys.exit("no rows parsed")
    # An export taken on day X contains only part of day X. Drop it unless asked to keep it.
    export_days = {datetime.strptime(m.group(1), "%Y%m%d").date() for m in (re.search(r"(\d{8})_\d{6}", os.path.basename(f)) for f in a.files) if m}
    last = max(D)
    if last in export_days and not a.keep_partial:
        print(f"note: {last} is the export day and partial; dropped (--keep-partial to keep it)")
        for store in (D, sess, lat, cats): store.pop(last, None)
        for k in [k for k in hours if k[0] == last]: hours.pop(k); hour_sess.pop(k, None)
    ucols, urows = usage_rows(D, sess, lat, has_voice)
    hcols, hrows = hours_rows(hours, hour_sess)
    (ccols, crows), (dcols, drows) = categories_rows(cats)
    days = sorted(D)
    print(f"{len(days)} days, {days[0]} to {days[-1]}, {sum(r[1] for r in urows)} turns, {sum(r[2] for r in urows)} conversations"
          + (", input-mode column found (voice columns included)" if has_voice else ", no input-mode column (voice columns omitted)"))
    if a.compare:
        compare(a.compare, ucols, urows, ccols, crows); return
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        write(os.path.join(a.out_dir, "usage.csv"), ucols, urows)
        write(os.path.join(a.out_dir, "usage-hours.csv"), hcols, hrows)
        write(os.path.join(a.out_dir, "categories.csv"), ccols, crows)
        write(os.path.join(a.out_dir, "categories-daily.csv"), dcols, drows)
    elif a.out:
        write(a.out, ucols, urows)
    else:
        w = csv.writer(sys.stdout); w.writerow(ucols); w.writerows(urows)


if __name__ == "__main__":
    main()
