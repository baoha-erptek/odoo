#!/usr/bin/env bash
# validate-agents.sh — every .claude/agents/*.md has name/description/tools/model
# frontmatter, and its model matches the binding table in performance.md.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
AGENTS_DIR="$PROJECT_ROOT/.claude/agents"
PERF="$PROJECT_ROOT/.claude/rules/common/performance.md"
ERRORS=0
CHECKED=0

echo "=== Validating agents ==="
[ -d "$AGENTS_DIR" ] || { echo "FAIL: $AGENTS_DIR not found"; exit 1; }

for file in "$AGENTS_DIR"/*.md; do
  [ -f "$file" ] || continue
  BASENAME="$(basename "$file")"
  NAME_NOEXT="${BASENAME%.md}"
  [ "$BASENAME" = "CLAUDE.md" ] && continue
  CHECKED=$((CHECKED + 1))

  if [ "$(head -1 "$file")" != "---" ]; then
    echo "FAIL: $BASENAME - Missing YAML frontmatter"; ERRORS=$((ERRORS + 1)); continue
  fi
  FM="$(sed -n '1,/^---$/p' "$file" | tail -n +2 | head -n -1)"

  for field in name description tools model; do
    if ! echo "$FM" | grep -q "^${field}:"; then
      echo "FAIL: $BASENAME - Missing '${field}' in frontmatter"; ERRORS=$((ERRORS + 1))
    fi
  done

  # Model-tier consistency vs performance.md binding table.
  FM_MODEL="$(echo "$FM" | grep -m1 '^model:' | sed 's/model:[[:space:]]*//; s/[[:space:]]*$//' || true)"
  if [ -n "$FM_MODEL" ] && [ -f "$PERF" ]; then
    EXPECTED="$(grep -E "^\|[[:space:]]*\`${NAME_NOEXT}\`[[:space:]]*\|" "$PERF" 2>/dev/null \
      | head -1 | awk -F'|' '{gsub(/[[:space:]]/,"",$3); print $3}')"
    if [ -n "$EXPECTED" ] && [ "$FM_MODEL" != "$EXPECTED" ]; then
      echo "FAIL: $BASENAME - model '$FM_MODEL' != performance.md binding '$EXPECTED'"
      ERRORS=$((ERRORS + 1))
    elif [ -z "$EXPECTED" ]; then
      echo "WARN: $BASENAME - not in performance.md Agent Model Assignments table"
    fi
  fi

  [ "$ERRORS" -eq 0 ] && echo "PASS: $BASENAME" || true
done

echo ""
echo "Agents checked: $CHECKED"
[ "$ERRORS" -eq 0 ] && echo "agents: ALL CHECKS PASSED" || echo "agents: $ERRORS ERROR(S) FOUND"
exit "$ERRORS"
