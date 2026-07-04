#!/usr/bin/env bash
# validate-rules.sh — every .claude/rules/**/*.md is non-empty and has a top heading.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RULES_DIR="$PROJECT_ROOT/.claude/rules"
ERRORS=0
CHECKED=0

echo "=== Validating rules ==="
[ -d "$RULES_DIR" ] || { echo "FAIL: $RULES_DIR not found"; exit 1; }

while IFS= read -r -d '' file; do
  CHECKED=$((CHECKED + 1))
  rel="${file#$PROJECT_ROOT/}"
  if [ ! -s "$file" ]; then
    echo "FAIL: $rel - empty file"; ERRORS=$((ERRORS + 1)); continue
  fi
  if ! grep -qE '^#[[:space:]]' "$file"; then
    echo "WARN: $rel - no top-level '# ' heading"
  fi
  echo "PASS: $rel"
done < <(find "$RULES_DIR" -type f -name '*.md' -print0)

echo ""
echo "Rules checked: $CHECKED"
[ "$ERRORS" -eq 0 ] && echo "rules: ALL CHECKS PASSED" || echo "rules: $ERRORS ERROR(S) FOUND"
exit "$ERRORS"
