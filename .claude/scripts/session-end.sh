#!/usr/bin/env bash
# session-end.sh — SessionEnd hook. Persist a short session summary under
# ~/.claude/sessions/. Slice-based (no JIRA task dirs). Never fails teardown.
set -euo pipefail

SESSION_DIR="$HOME/.claude/sessions"
mkdir -p "$SESSION_DIR" 2>/dev/null || exit 0

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
TS="$(date '+%Y-%m-%d_%H-%M-%S')"
SESSION_FILE="$SESSION_DIR/${PROJECT_NAME}_session_${TS}.md"
TRACKER="$PROJECT_ROOT/.claude/plans/006-master-plan-tracking.md"

BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
ACTIVE=""
[ -f "$TRACKER" ] && ACTIVE="$(grep -iE '\|[^|]*\|[^|]*\|[^|]*(in_progress|doing)' "$TRACKER" 2>/dev/null \
  | head -1 | awk -F'|' '{gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); print $2}' || true)"

{
  echo "# Session Summary"
  echo "- Date: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "- Project: $PROJECT_NAME"
  echo "- Branch: $BRANCH"
  echo "- Active slice: ${ACTIVE:-none}"
  echo ""
  echo "## Recent commits"
  git -C "$PROJECT_ROOT" log --oneline -5 2>/dev/null || echo "No commits"
  echo ""
  echo "## Uncommitted"
  git -C "$PROJECT_ROOT" diff --stat HEAD 2>/dev/null || echo "None"
  echo ""
  echo "## Staged"
  git -C "$PROJECT_ROOT" diff --cached --stat 2>/dev/null || echo "None"
} > "$SESSION_FILE" 2>/dev/null || exit 0

echo "[SessionEnd] Summary saved: $SESSION_FILE"
exit 0
