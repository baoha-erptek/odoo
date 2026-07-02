#!/usr/bin/env bash
# pre-bash-push-reminder.sh - Remind about /code-review before a git push.
# Triggered by PreToolUse on Bash. Native Claude Code hooks deliver the tool
# call as JSON on stdin (not via $TOOL_INPUT), so parse the command from there.
# Advisory only: always exits 0 so it never blocks the push.
set -euo pipefail

INPUT=$(cat 2>/dev/null || echo "")

# Pull the .tool_input.command string out of the hook JSON.
CMD=""
if [ -n "$INPUT" ]; then
  CMD=$(echo "$INPUT" | grep -oE '"command"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"command"\s*:\s*"//;s/"$//' || true)
fi

if echo "$CMD" | grep -qE 'git[[:space:]]+push'; then
  echo "[Pre-Push] Reminder: run /code-review before pushing."
fi

exit 0
