#!/usr/bin/env python3
"""PreToolUse guard (brief §75): no tool call in a Claude Code session may read citizens' question or answer text.

The design rule is that feed text stays on the analyst's machine and only counts leave it. A model session is not the
machine: whatever a tool prints is sent to the model. So this hook denies, before it runs, any Read, Grep or Bash call
that would print text from a feed, a redacted feed, a labelling sheet or a backend log, and allows only the pipeline
tools in tools/ to open those files (they print counts). Installed by .claude/settings.json; a guard against accident,
not a security boundary. Exit 0 with a JSON decision; anything else and onFailure:block stops the call.

Denied paths: any feed or redacted feed (*qa-feed*.csv, per-turn rows), labelling sheets (exports/labelling-*), the backend
logs and their parsed turns under "ask review/", wherever they sit. The aggregate CSVs and the tools' own count output in a
review folder are counts and stay readable.
Allowed Bash forms that mention those paths: `python3 tools/<pipeline tool>.py …`, and `ls`, `wc`, `du`, `head -1`,
`head -n 1` (a header is column names, not text). A python script outside tools/ that itself mentions those paths is
denied too, as are `python3 -c` and heredoc programs that mention them.
"""
import json, os, re, sys

TEXT_PATHS = re.compile(r"qa-feed[^\s'\"]*\.csv|\.turns\.csv|ask review/[^\s'\"]*(Logs|Monitoring|\.txt)|labelling-[^\s'\"]*|User Query|Assistant Response", re.I)
PIPELINE = r"(?:redact_feed|make_usage|cache_coverage|make_lexicon|next_step|make_label_sample|score_labels|change_report|incidents|log_parser|check_rules_vs_prompts|audit_data|collect_aggregates)\.py"
ALLOWED_BASH = re.compile(r"^\s*(?:(?:cd\s+\S+|mkdir\s+-p\s+\S+)\s*&&\s*)*(?:[A-Z_]+=\S+\s+)*(?:python3\s+(?:-I\s+)?(?:\S*/)?tools/" + PIPELINE + r"\b|ls\b|wc\b|du\b|mkdir\b|head\s+-(?:n\s*)?1\b)[^|;&]*(?:\s*(?:>|2>)\s*\S+)*\s*$")
SCRIPT = re.compile(r"(\S+\.py)\b")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": "feed-text guard (brief §75): " + reason}}))
    sys.exit(0)


def main():
    try: inp = json.load(sys.stdin)
    except ValueError: sys.exit(0)
    tool = inp.get("tool_name", ""); ti = inp.get("tool_input") or {}
    if tool in ("Read", "Grep", "Glob"):
        p = str(ti.get("file_path") or ti.get("path") or "")
        pat = str(ti.get("pattern") or "")
        if TEXT_PATHS.search(p) or (tool == "Grep" and re.search(r"User Query|Assistant Response", pat)):
            deny(f"{tool} of feed text ({p or pat}); citizens' text stays on this machine. The pipeline tools print counts.")
        sys.exit(0)
    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        if TEXT_PATHS.search(cmd):
            if ALLOWED_BASH.match(cmd) or re.match(r"^\s*head\s+-(?:n\s*)?1\s+\S+(?:\s*\|\s*(?:tr|nl|cut|wc|sort|uniq|cat)\b[^|;&]*)*\s*$", cmd): sys.exit(0)   # a header line only
            deny("this command would print feed text. Allowed: python3 tools/<pipeline tool>.py, ls, wc, du, head -1 on those paths.")
        # a script outside tools/ that reads the feeds itself
        for m in SCRIPT.finditer(cmd):
            path = os.path.expandvars(m.group(1).strip("'\""))
            if "/tools/" in path or path.startswith("tools/"): continue
            if not os.path.isabs(path): path = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()), path)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh: src = fh.read(200000)
            except OSError: continue
            if TEXT_PATHS.search(src):
                deny(f"{m.group(1)} reads feed text; write the derivation into a tool under tools/ that prints counts.")
        if re.search(r"python3?\s+(?:-c\b|-\s*<<|-\s*$)", cmd) and TEXT_PATHS.search(cmd):
            deny("an inline python program that reads feed text.")
    sys.exit(0)


if __name__ == "__main__":
    main()
