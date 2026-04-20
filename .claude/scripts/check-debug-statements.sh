#!/usr/bin/env bash
# check-debug-statements.sh - Check git-modified Python files for debug statements
# Triggered by Stop hook after Claude finishes responding
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Get modified Python files (staged + unstaged), excluding tests
MODIFIED_FILES=$(git -C "$PROJECT_ROOT" diff --name-only --diff-filter=ACMR HEAD 2>/dev/null | grep '\.py$' | grep -v '/tests/' || true)
STAGED_FILES=$(git -C "$PROJECT_ROOT" diff --cached --name-only --diff-filter=ACMR 2>/dev/null | grep '\.py$' | grep -v '/tests/' || true)

ALL_FILES=$(echo -e "${MODIFIED_FILES}\n${STAGED_FILES}" | sort -u | grep -v '^$' || true)

if [ -z "$ALL_FILES" ]; then
  exit 0
fi

FOUND_ISSUES=false

while IFS= read -r file; do
  FULL_PATH="$PROJECT_ROOT/$file"
  [ -f "$FULL_PATH" ] || continue

  # Check for print() statements
  PRINT_LINES=$(grep -n 'print(' "$FULL_PATH" 2>/dev/null | grep -v '^\s*#' || true)
  if [ -n "$PRINT_LINES" ]; then
    if [ "$FOUND_ISSUES" = false ]; then
      echo "[Debug Statement Check]"
      FOUND_ISSUES=true
    fi
    echo "  WARNING: print() found in $file"
    echo "$PRINT_LINES" | head -3 | while IFS= read -r line; do
      echo "    $file:$line"
    done
  fi

  # Check for _logger.info used for debugging
  INFO_LINES=$(grep -n '_logger\.info' "$FULL_PATH" 2>/dev/null | grep -v '^\s*#' || true)
  if [ -n "$INFO_LINES" ]; then
    if [ "$FOUND_ISSUES" = false ]; then
      echo "[Debug Statement Check]"
      FOUND_ISSUES=true
    fi
    echo "  WARNING: _logger.info in $file (use _logger.debug for debugging)"
    echo "$INFO_LINES" | head -3 | while IFS= read -r line; do
      echo "    $file:$line"
    done
  fi
done <<< "$ALL_FILES"

if [ "$FOUND_ISSUES" = true ]; then
  echo "  Tip: Use _logger.debug() for investigation, remove print() statements"
fi
