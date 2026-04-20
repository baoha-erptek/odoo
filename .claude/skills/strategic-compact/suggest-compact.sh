#!/bin/bash
# Strategic Compact Suggester
# Runs on PreToolUse or periodically to suggest manual compaction at logical intervals
#
# Why manual over auto-compact:
# - Auto-compact happens at arbitrary points, often mid-task
# - Strategic compacting preserves context through logical phases
# - Compact after exploration, before execution
# - Compact after completing a milestone, before starting next
#
# Hook config (in ~/.claude/settings.json):
# {
#   "hooks": {
#     "PreToolUse": [{
#       "matcher": "Edit|Write",
#       "hooks": [{
#         "type": "command",
#         "command": "~/.claude/skills/strategic-compact/suggest-compact.sh"
#       }]
#     }]
#   }
# }
#
# Criteria for suggesting compact:
# - Session has been running for extended period
# - Large number of tool calls made
# - Transitioning from research/exploration to implementation
# - Plan has been finalized

# Track tool call count (increment in a temp file)
# Use workspace hash for project isolation, NOT $$ (PID changes per invocation)
WORKSPACE_HASH=$(echo "$PWD" | md5sum | cut -c1-8)
COUNTER_FILE="/tmp/claude-compact-${WORKSPACE_HASH}"
THRESHOLD=${COMPACT_THRESHOLD:-50}
SESSION_TIMEOUT=7200  # Reset counter after 2 hours (new session)

# Reset counter if file is older than SESSION_TIMEOUT seconds
if [ -f "$COUNTER_FILE" ]; then
  file_age=$(( $(date +%s) - $(stat -c %Y "$COUNTER_FILE") ))
  if [ "$file_age" -gt "$SESSION_TIMEOUT" ]; then
    rm -f "$COUNTER_FILE"
  fi
fi

# Initialize or increment counter
if [ -f "$COUNTER_FILE" ]; then
  count=$(cat "$COUNTER_FILE")
  count=$((count + 1))
  echo "$count" > "$COUNTER_FILE"
else
  echo "1" > "$COUNTER_FILE"
  count=1
fi

# Suggest compact after threshold tool calls
if [ "$count" -eq "$THRESHOLD" ]; then
  echo "[StrategicCompact] $THRESHOLD tool calls reached - consider /compact if transitioning phases" >&2
fi

# Suggest at regular intervals after threshold
if [ "$count" -gt "$THRESHOLD" ] && [ $((count % 25)) -eq 0 ]; then
  echo "[StrategicCompact] $count tool calls - good checkpoint for /compact if context is stale" >&2
fi
