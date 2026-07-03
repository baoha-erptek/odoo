#!/usr/bin/env bash
# session-start.sh — SessionStart hook. Report branch + active master-plan slice.
# Slice model is tracker-driven (.claude/plans/master-plan-tracking.md), not JIRA.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TRACKER="$PROJECT_ROOT/.claude/plans/006-master-plan-tracking.md"

BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

echo "[Session Start]"
[ -n "$BRANCH" ] && echo "  Branch: $BRANCH"

if [ -f "$TRACKER" ]; then
  # Active slice = first table row whose state column is in_progress / doing (col 2 = slice_id).
  ACTIVE="$(grep -iE '\|[^|]*\|[^|]*\|[^|]*(in_progress|doing)' "$TRACKER" 2>/dev/null \
    | head -1 | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); print $2}' || true)"
  if [ -n "$ACTIVE" ]; then
    echo "  Active slice: $ACTIVE"
  else
    echo "  No slice in_progress — run /dispatch-slice next"
  fi
  echo "  Tracker: .claude/plans/006-master-plan-tracking.md (slice counts: session-cost.py --by slice)"
else
  echo "  No master-plan-tracking.md yet — see CLAUDE.md 'Master Plan' to start a multi-slice initiative."
fi
