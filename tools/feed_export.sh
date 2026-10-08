#!/bin/sh
# AskCI feed export pipeline: redact -> compare with the dashboard files -> write aggregates.
# Used by the "AskCI Feed Export" droplet; can also be run by hand.
#
#   tools/feed_export.sh OUT_DIR qa-feed_a.csv [qa-feed_b.csv ...]
#
# Writes into OUT_DIR: qa-feed-redacted_*.csv, usage.csv, usage-hours.csv, categories.csv,
# categories-daily.csv, compare.txt and summary.txt. Never touches the dashboard folder;
# copying the aggregates in is a separate, deliberate step.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; shift
[ -n "$OUT" ] && [ "$#" -ge 1 ] || { echo "usage: $0 OUT_DIR feed.csv [feed.csv ...]" >&2; exit 2; }
for c in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do [ -x "$c" ] && PY="$c" && break; done
[ -n "$PY" ] || { echo "python3 not found" >&2; exit 1; }
mkdir -p "$OUT"
"$PY" "$REPO/tools/redact_feed.py" "$@" --out-dir "$OUT" --force > "$OUT/redact.txt"
set -- "$OUT"/qa-feed-redacted_*.csv
"$PY" "$REPO/tools/make_usage.py" "$@" --compare "$REPO" > "$OUT/compare.txt" 2>&1
"$PY" "$REPO/tools/make_usage.py" "$@" --out-dir "$OUT" > "$OUT/generate.txt" 2>&1
{
  grep -m1 " days, " "$OUT/generate.txt"
  grep -h "^note:" "$OUT/generate.txt" | sort -u
  echo
  grep -E "totals on shared days|^  [A-Z][a-z]+: feed [0-9]+ · existing" "$OUT/compare.txt" | sed 's/^  //'
  n=$(grep -c "<-- differs" "$OUT/compare.txt" || true)
  echo
  echo "$n day(s) differ from the current usage.csv. Full detail in compare.txt."
  echo "Redacted feed and aggregates are in: $OUT"
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
