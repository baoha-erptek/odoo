#!/usr/bin/env bash
# PreToolUse(Agent/Task) advisory hook — warn (never block) when a spawned agent's
# frontmatter `model:` drifts from the binding table in performance.md.
#
# Reads the hook JSON from stdin, extracts the agent name (subagent_type), compares its
# `.claude/agents/<name>.md` frontmatter model to the expected tier, and prints a
# `[model-tier]` WARNING to stderr on mismatch. Always exits 0 — advisory only.
#
# Wired in .claude/settings.json under PreToolUse matcher "Task".

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
AGENTS_DIR="${REPO_ROOT}/.claude/agents"
PERF="${REPO_ROOT}/.claude/rules/common/performance.md"

INPUT="$(cat)"

# Extract subagent_type from the hook payload (best-effort; no jq dependency).
AGENT="$(printf '%s' "$INPUT" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = data.get("tool_input") or data.get("toolInput") or {}
print((ti.get("subagent_type") or ti.get("subagentType") or "").strip())
' 2>/dev/null)"

[ -n "$AGENT" ] || exit 0

AGENT_FILE="${AGENTS_DIR}/${AGENT}.md"
[ -f "$AGENT_FILE" ] || exit 0   # built-in / non-project agent (Explore, Plan, general-purpose): nothing to check

# Frontmatter model for the spawned agent.
FM_MODEL="$(grep -m1 '^model:' "$AGENT_FILE" 2>/dev/null | sed 's/model:[[:space:]]*//; s/[[:space:]]*$//')"
[ -n "$FM_MODEL" ] || exit 0

# Expected tier from the binding table row: | `agent-name` | model | rationale |
[ -f "$PERF" ] || exit 0
EXPECTED="$(grep -E "^\|[[:space:]]*\`${AGENT}\`[[:space:]]*\|" "$PERF" 2>/dev/null \
  | head -1 | awk -F'|' '{gsub(/[[:space:]]/,"",$3); print $3}')"
[ -n "$EXPECTED" ] || exit 0   # agent not in the table — nothing authoritative to compare

if [ "$FM_MODEL" != "$EXPECTED" ]; then
  echo "[model-tier] WARNING: agent '${AGENT}' frontmatter model '${FM_MODEL}' != performance.md binding '${EXPECTED}'. Update .claude/agents/${AGENT}.md or the Agent Model Assignments table." >&2
fi

exit 0
