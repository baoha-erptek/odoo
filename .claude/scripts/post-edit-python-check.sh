#!/usr/bin/env bash
# post-edit-python-check.sh - Check edited Python files for common issues
# Triggered by PostToolUse on Edit|Write operations
set -euo pipefail

# Read hook input from stdin (JSON with tool_input containing file path)
INPUT=$(cat 2>/dev/null || echo "")

# Extract file path from hook input
FILE_PATH=""
if [ -n "$INPUT" ]; then
  # Try to extract file_path from JSON input
  FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//' || true)
fi

# Only process Python files
if [ -z "$FILE_PATH" ] || [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Skip test files
if echo "$FILE_PATH" | grep -q '/tests/'; then
  exit 0
fi

[ -f "$FILE_PATH" ] || exit 0

FOUND_ISSUES=false

# Check for print() statements (excluding comments)
PRINT_LINES=$(grep -n 'print(' "$FILE_PATH" 2>/dev/null | grep -v '^\s*#' || true)
if [ -n "$PRINT_LINES" ]; then
  FOUND_ISSUES=true
  echo "[Post-Edit Check] print() detected in $(basename "$FILE_PATH"):"
  echo "$PRINT_LINES" | head -3 | while IFS= read -r line; do
    echo "  $line"
  done
  echo "  -> Use _logger.debug() instead"
fi

# Check for _logger.info (should be _logger.debug for investigation)
INFO_LINES=$(grep -n '_logger\.info' "$FILE_PATH" 2>/dev/null | grep -v '^\s*#' || true)
if [ -n "$INFO_LINES" ]; then
  FOUND_ISSUES=true
  echo "[Post-Edit Check] _logger.info in $(basename "$FILE_PATH"):"
  echo "$INFO_LINES" | head -3 | while IFS= read -r line; do
    echo "  $line"
  done
  echo "  -> Use _logger.debug() for debugging/investigation"
fi

# Check for Python syntax errors
SYNTAX_CHECK=$(python3 -m py_compile "$FILE_PATH" 2>&1 || true)
if [ -n "$SYNTAX_CHECK" ]; then
  FOUND_ISSUES=true
  echo "[Post-Edit Check] Syntax error in $(basename "$FILE_PATH"):"
  echo "  $SYNTAX_CHECK"
fi
