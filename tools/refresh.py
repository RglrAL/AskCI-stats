#!/usr/bin/env python3
"""One data refresh, in order, stopping at the first failure (brief §76): the analyst's runner.

    python3 tools/refresh.py exports/qa-feed_*.csv                      # full refresh into exports/askci-export-<today>
    python3 tools/refresh.py exports/qa-feed_*.csv --out-dir DIR --skip-fetch --skip-test

Steps, each a tool that already exists; this script only orders them, keeps their output in <out-dir>/refresh.log and
prints each step's last line (counts and versions, never text):
  1 fetch_pages.py            dated snapshots of the cited pages (skipped with --skip-fetch)
  2 make_lexicon.py           --topic-counts FEEDS: the 20-match check, then the lexicon
  3 redact_feed.py            each feed to the review folder, text dropped, derived columns added; then --write-templates
  4 make_usage.py             the aggregate files, from the redacted feeds
  5 cache_coverage.py, next_step.py   from the raw feeds, into the repo root
  6 collect_aggregates.py     the aggregates into the repo root
  7 audit_data.py DIR         the audit WITH the feed recount (the deploy can only run files-only)
  8 make_register.py, make_findings.py, change_report.py --events, incidents.py, make_facts.py
  9 test_ask.py               the Ask bar regression (skipped with --skip-test)
 10 VERSIONS.json             the manifest: every version string, the recount's date and counts, the commit, and a
                              hash and row count of each aggregate file, so the deploy's audit can confirm the committed
                              aggregates are the ones the recount passed

Nothing here opens a feed; the tools do, on this machine. The log holds the tools' own output, which is counts.
"""
import argparse, csv, hashlib, json, os, re, subprocess, sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("feeds", nargs="+", help="raw QA feed exports")
    ap.add_argument("--out-dir", default=os.path.join(REPO, "exports", f"askci-export-{date.today().isoformat()}"))
    ap.add_argument("--skip-fetch", action="store_true"); ap.add_argument("--skip-test", action="store_true")
    ap.add_argument("--from-audit", action="store_true", help="the review folder already holds this refresh's redacted feeds and aggregates: start at the audit")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    log = open(os.path.join(a.out_dir, "refresh.log"), "a", encoding="utf-8")
    results = {}

    def run(name, cmd, must=True):
        log.write(f"\n== {name}: {' '.join(cmd)}\n"); log.flush()
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        log.write(r.stdout); log.write(r.stderr); log.flush()
        last = next((l for l in reversed((r.stdout + r.stderr).strip().split("\n")) if l.strip()), "")
        print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {name}: {last[:160]}")
        results[name] = {"returncode": r.returncode, "last": last[:200]}
        if r.returncode and must:
            print(f"stopped at {name}; see {os.path.relpath(log.name, REPO)}"); sys.exit(1)
        return r

    py = [sys.executable]
    if not a.from_audit:
        if not a.skip_fetch: run("fetch pages", py + ["tools/fetch_pages.py"])
        run("lexicon (20-match check)", py + ["tools/make_lexicon.py", "--topic-counts"] + a.feeds)
        for f in a.feeds:
            run(f"redact {os.path.basename(f)}", py + ["tools/redact_feed.py", f, "--out-dir", a.out_dir, "--force"])
        run("templates json", py + ["tools/redact_feed.py", "--write-templates", "answer-templates.json"])
        redacted = sorted(os.path.join(a.out_dir, x) for x in os.listdir(a.out_dir) if x.startswith("qa-feed-redacted_") and x.endswith(".csv"))
        run("aggregates", py + ["tools/make_usage.py"] + redacted + ["--out-dir", a.out_dir])
        run("repeat questions", py + ["tools/cache_coverage.py"] + a.feeds)
        run("what people do next", py + ["tools/next_step.py"] + a.feeds)
        run("collect", py + ["tools/collect_aggregates.py", a.out_dir])
    r = run("audit (feed recount)", py + ["tools/audit_data.py", a.out_dir])
    passed = r.stdout.count("✓"); failed = r.stdout.count("✗")
    run("register", py + ["tools/make_register.py"]); run("findings", py + ["tools/make_findings.py"])
    run("change reports", py + ["tools/change_report.py", "--events"], must=False); run("incidents", py + ["tools/incidents.py"], must=False); run("fact sheet", py + ["tools/make_facts.py"], must=False)
    if not a.skip_test: run("ask bar test", py + ["tools/test_ask.py"])

    # the manifest
    import redact_feed as RF, make_lexicon as ML
    page = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    cfgv = (re.search(r"version:'([\d.\-]+)'", page) or [None, ""])[1]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    files = {}
    for x in sorted(os.listdir(a.out_dir)):
        if x.endswith(".csv") and "qa-feed" not in x and os.path.exists(os.path.join(REPO, x)):
            p = os.path.join(REPO, x)
            with open(p, "rb") as fh: b = fh.read()
            files[x] = {"sha256": hashlib.sha256(b).hexdigest()[:16], "rows": b.count(b"\n") - 1}
    man = {"_comment": "Written by tools/refresh.py at the end of a data refresh (brief §76): the version strings in force, the feed recount's result, "
                       "and a hash of each aggregate file as committed, which the deploy audit checks so that the published aggregates are the ones the recount passed.",
           "generated": date.today().isoformat(), "commit_before_refresh": commit, "review_folder": os.path.relpath(a.out_dir, REPO), "feeds": [os.path.basename(f) for f in a.feeds],
           "versions": {"outcome_rules": RF.OUTCOME_RULES_VERSION, "style": RF.STYLE_VERSION, "safety": RF.SAFETY_VERSION, "intent": RF.INTENT_VERSION, "lexicon": ML.LEXICON_VERSION, "derivation": RF.DERIVATION_VERSION, "page_config": cfgv},
           "audit": {"mode": "feed recount", "date": date.today().isoformat(), "passed": passed, "failed": failed},
           "tests": {"ask_bar": results.get("ask bar test", {}).get("last", "skipped")},
           "aggregates": files}
    with open(os.path.join(REPO, "VERSIONS.json"), "w", encoding="utf-8") as fh: json.dump(man, fh, indent=1, ensure_ascii=False); fh.write("\n")
    print(f"wrote VERSIONS.json: derivation {RF.DERIVATION_VERSION}, lexicon {ML.LEXICON_VERSION}, recount {passed} passed {failed} failed, {len(files)} aggregate files hashed")
    print("next: review git status, commit, push; the deploy repeats the files-only audit and the test")


if __name__ == "__main__":
    main()
