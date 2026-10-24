#!/usr/bin/env python3
"""Cases for guard_feed_text.py: each is (expect, tool, input). Run: python3 tools/hooks/test_guard.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
FX = os.path.join(tempfile.gettempdir(), "guard_fixture_reads_feed.py")   # outside tools/, like a scratch script
X = "exports/askci-export-x/qa-feed-redacted_1.csv"
CASES = [
    ("deny", "Read", {"file_path": REPO + "/exports/qa-feed_20261023_135700.csv"}),
    ("allow", "Read", {"file_path": REPO + "/index.html"}),
    ("allow", "Read", {"file_path": REPO + "/tools/redact_feed.py"}),
    ("deny", "Bash", {"command": f"cut -f2 {X} | head"}),
    ("allow", "Bash", {"command": f"cd {REPO} && python3 tools/redact_feed.py exports/qa-feed_20261023_135700.csv --out-dir exports/askci-export-x --force"}),
    ("allow", "Bash", {"command": f"python3 tools/make_usage.py exports/askci-export-x/qa-feed-redacted_*.csv --out-dir exports/askci-export-x > exports/askci-export-x/generate.txt 2>&1"}),
    ("deny", "Bash", {"command": f"python3 tools/make_usage.py {X} --out-dir exports/x | head -40"}),
    ("allow", "Bash", {"command": "ls -la exports/askci-export-full"}),
    ("allow", "Bash", {"command": f"head -1 {X} | tr , \\\\n"}),
    ("deny", "Bash", {"command": f"head -3 {X}"}),
    ("deny", "Bash", {"command": f"python3 - <<EOF\nimport csv\nfor r in csv.DictReader(open('{X}')): print(r)\nEOF"}),
    ("deny", "Bash", {"command": "SCR=/tmp python3 " + FX}),
    ("allow", "Bash", {"command": "git status -sb"}),
    ("allow", "Bash", {"command": "python3 tools/audit_data.py --files-only"}),
    ("deny", "Grep", {"pattern": "User Query", "path": "tools"}),
    ("deny", "Read", {"file_path": REPO + "/ask review/LiveLogs_AskCI_Gpt5_4.txt"}),
    ("allow", "Read", {"file_path": REPO + "/ask review/backend-structure-notes.md"}),
    ("allow", "Bash", {"command": "python3 tools/score_labels.py exports/labelling-2026-10-23/labels.csv"}),
    ("deny", "Bash", {"command": "cat exports/labelling-2026-10-23/labels.csv"}),
    ("allow", "Bash", {"command": "wc -l exports/qa-feed_20261023_135700.csv"}),
    ("allow", "Bash", {"command": "cd /x && mkdir -p exports/askci-export-y && python3 tools/redact_feed.py exports/qa-feed_1.csv --out-dir exports/askci-export-y --force > exports/askci-export-y/redact.txt 2>&1"}),
    ("deny", "Bash", {"command": "mkdir -p exports/y && cat exports/qa-feed_1.csv"}),
    ("allow", "Bash", {"command": "head -5 exports/askci-export-x/usage.csv"}),
    ("allow", "Bash", {"command": "tail -3 exports/askci-export-x/generate.txt"}),
    ("deny", "Bash", {"command": f"head -5 {X}"}),
    ("deny", "Read", {"file_path": REPO + "/exports/labelling-2026-10-23/labels.csv"}),
    ("allow", "Bash", {"command": "python3 tools/collect_aggregates.py exports/askci-export-x"}),
    ("allow", "Bash", {"command": "python3 tools/audit_data.py exports/askci-export-x"}),
]


def main():
    fx = FX
    with open(fx, "w") as fh: fh.write("import csv\nrows=list(csv.DictReader(open('exports/x/qa-feed-redacted_1.csv')))\n")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": REPO}
    bad = 0
    try:
        for expect, tool, ti in CASES:
            out = subprocess.run([sys.executable, os.path.join(HERE, "guard_feed_text.py")], input=json.dumps({"tool_name": tool, "tool_input": ti}), capture_output=True, text=True, env=env)
            got = "deny" if out.stdout.strip() else "allow"
            ok = got == expect; bad += not ok
            print(("ok   " if ok else "FAIL ") + f"{expect:5} {tool:5} " + (ti.get("command") or ti.get("file_path") or ti.get("pattern") or "").replace("\n", " ")[:100])
    finally:
        os.remove(fx)
    print(f"{len(CASES) - bad} of {len(CASES)} cases as expected")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
