#!/usr/bin/env python3
"""Fingerprint the local system-prompt snapshot (brief §60).

The prompts are backend detail and stay in the git-ignored review folder, one dated folder per export and one file per
prompt. This writes prompts.json to the repo with nothing but a set-level fingerprint: the snapshot date, how many
prompts, one SHA-256 over all of them (canary lines excluded), and whether the set is known to be current. The
dashboard's data-quality strip shows the date and "unverified since". A new export goes in a new dated folder; a
changed fingerprint is a `prompt` event for events.json (kind prompt, status candidate), dated by the export, with no
text.

Usage:
    python3 tools/prompt_fingerprint.py                      # latest dated folder → prompts.json
    python3 tools/prompt_fingerprint.py --verified-current   # when the AskCI team has confirmed the set is live
"""
import argparse, glob, hashlib, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(REPO, "ask review", "prompts")
CANARY = re.compile(r"<!--\s*ASKCI-PROMPT-" + "CANARY.*?-->\n?")


def snapshot(folder):
    """(date, count, sha256) for one dated folder; the hash covers every prompt's text, canary and header lines removed."""
    h = hashlib.sha256(); n = 0
    for p in sorted(glob.glob(os.path.join(folder, "*.md"))):
        t = CANARY.sub("", open(p, encoding="utf-8").read(), count=1)
        t = re.sub(r"^<!--.*?-->\n", "", t, count=1)
        h.update(os.path.basename(p).encode()); h.update(t.strip().encode("utf-8")); h.update(b"\0"); n += 1
    return os.path.basename(folder), n, h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verified-current", action="store_true")
    a = ap.parse_args()
    folders = sorted(d for d in glob.glob(os.path.join(PROMPTS, "????-??-??")) if os.path.isdir(d))
    if not folders:
        sys.exit(f"no dated prompt folder under {PROMPTS}")
    snaps = [snapshot(f) for f in folders]
    date, n, sha = snaps[-1]
    out = {"_comment": "Set-level fingerprint of the system prompts the outcome rules were checked against (brief §60). "
                       "The prompts themselves are held locally and never published. A changed fingerprint between two "
                       "exports is a prompt change; whether anything changed between exports cannot be known from this file.",
           "snapshot": date, "prompts": n, "set_sha256": sha, "verified_current": bool(a.verified_current),
           "history": [{"snapshot": d, "prompts": k, "set_sha256": s} for d, k, s in snaps]}
    p = os.path.join(REPO, "prompts.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(p, "a").write("\n")
    print(f"wrote prompts.json: snapshot {date}, {n} prompts, {sha[:12]}…, verified current: {out['verified_current']}")


if __name__ == "__main__":
    main()
