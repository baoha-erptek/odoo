#!/usr/bin/env bash
# record-token-spend.sh — SessionEnd hook.
# Attributes this session's Claude token usage to the active master-plan SLICE
# and appends one idempotent line to .claude/metrics/token-ledger.jsonl.
#
# Why a local ledger when the global ~/.claude/metrics/costs.jsonl already exists?
# The global file is per-session only. This ledger adds the *slice* dimension, so
# session-cost.py can report cost-per-slice / sessions-per-slice throughput.
#
# Slice resolution order: (1) an id like `P1-02` or `S001` in the branch name,
# (2) the first `in_progress`/`doing` row in .claude/plans/master-plan-tracking.md,
# (3) "no-slice". Never fails session teardown (always exit 0).
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
METRICS_DIR="$PROJECT_ROOT/.claude/metrics"
LEDGER="$METRICS_DIR/token-ledger.jsonl"
TRACKER="$PROJECT_ROOT/.claude/plans/006-master-plan-tracking.md"

# --- read hook stdin JSON (best-effort; no hard jq dependency) ---
STDIN_JSON="$(cat 2>/dev/null || true)"
json_get() { printf '%s' "$STDIN_JSON" | grep -oE "\"$1\"\\s*:\\s*\"[^\"]*\"" | head -1 | sed "s/.*\"$1\"\\s*:\\s*\"//;s/\"$//" || true; }
TRANSCRIPT="$(json_get transcript_path)"
SESSION_ID="$(json_get session_id)"
[ -z "$SESSION_ID" ] && SESSION_ID="unknown-$(date -u +%s)"

# --- resolve active slice ---
BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
SLICE="$(printf '%s' "$BRANCH" | grep -oE '[A-Z][0-9]+-[0-9a-z]+|S[0-9]{3}' | head -1 || true)"
if [ -z "$SLICE" ] && [ -f "$TRACKER" ]; then
  # First markdown table row whose state column is in_progress / doing; col 2 = slice_id.
  SLICE="$(grep -iE '\|[^|]*\|[^|]*\|[^|]*(in_progress|doing)' "$TRACKER" 2>/dev/null \
    | head -1 | awk -F'|' '{gsub(/[[:space:]`]/,"",$2); print $2}' || true)"
fi
[ -z "$SLICE" ] && SLICE="no-slice"

# --- sum this session's usage from the transcript JSONL (needs jq) ---
S_IN=0; S_OUT=0; S_CR=0; S_CW=0
if command -v jq >/dev/null 2>&1 && [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  read -r S_IN S_OUT S_CR S_CW <<EOF
$(jq -rs '
     [ .[] | (.message.usage // .usage // empty) ] as $u
     | [ ($u | map(.input_tokens // 0)               | add // 0),
         ($u | map(.output_tokens // 0)              | add // 0),
         ($u | map(.cache_read_input_tokens // 0)    | add // 0),
         ($u | map(.cache_creation_input_tokens // 0)| add // 0) ]
     | "\(.[0]) \(.[1]) \(.[2]) \(.[3])"' "$TRANSCRIPT" 2>/dev/null || echo "0 0 0 0")
EOF
fi
S_IN=${S_IN:-0}; S_OUT=${S_OUT:-0}; S_CR=${S_CR:-0}; S_CW=${S_CW:-0}

# --- idempotent append (once per session_id) ---
mkdir -p "$METRICS_DIR" 2>/dev/null || exit 0
touch "$LEDGER" 2>/dev/null || exit 0
if command -v flock >/dev/null 2>&1; then
  exec 9>>"$LEDGER" 2>/dev/null && flock -w 10 9 2>/dev/null || true
fi
if ! grep -q "\"session\":\"$SESSION_ID\"" "$LEDGER" 2>/dev/null; then
  printf '{"session":"%s","ts":"%s","slice":"%s","in":%s,"out":%s,"cr":%s,"cw":%s}\n' \
    "$SESSION_ID" "$(date -u +%FT%TZ)" "$SLICE" "$S_IN" "$S_OUT" "$S_CR" "$S_CW" >> "$LEDGER"
  echo "[token-spend] slice=$SLICE session=$SESSION_ID in=$S_IN out=$S_OUT"
fi
exit 0
