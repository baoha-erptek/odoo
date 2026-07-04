#!/bin/bash
# worktree-path-guard.sh — PreToolUse hook for Edit|Write
#
# Prevents accidental edits to the main repo when running from a worktree.
# If the current working directory is inside a worktree but the file being
# edited is in the main repo's addons/, block the edit with a clear warning.
#
# How it works:
#   1. Detect if CWD is a worktree (not the main repo)
#   2. Read the tool input (file_path) from stdin
#   3. If file_path points to the main repo's addons/ tree, block it
#
# Usage: Added as PreToolUse hook for Edit|Write in .claude/hooks.json

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat 2>/dev/null || true)

# Extract file_path from JSON input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Handle both direct and nested tool_input formats
    if isinstance(data, dict):
        print(data.get('file_path', data.get('tool_input', {}).get('file_path', '')))
    else:
        print('')
except:
    print('')
" 2>/dev/null || true)

# If no file path detected, allow (non-file operation)
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Detect worktree vs main repo
WORKTREE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
MAIN_ROOT=$(git worktree list 2>/dev/null | head -1 | awk '{print $1}' || true)

# If not in a git repo or not in a worktree, allow
if [[ -z "$WORKTREE_ROOT" || -z "$MAIN_ROOT" ]]; then
    exit 0
fi

# If CWD is in the main repo (not a worktree), allow
if [[ "$WORKTREE_ROOT" == "$MAIN_ROOT" ]]; then
    exit 0
fi

# We are in a worktree. Check if the file being edited is in the main repo.
# Resolve to absolute path
RESOLVED_PATH=$(realpath "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")

# Check if the resolved path starts with the main repo root
# BUT exclude paths inside the worktree itself (worktree may be nested in main repo)
if [[ "$RESOLVED_PATH" == "$MAIN_ROOT"/* ]] && [[ "$RESOLVED_PATH" != "$WORKTREE_ROOT"/* ]]; then
    BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    echo ""
    echo "================================================================"
    echo "BLOCKED: Editing main repo file from worktree!"
    echo "================================================================"
    echo ""
    echo "  You are on worktree branch: $BRANCH"
    echo "  Worktree root: $WORKTREE_ROOT"
    echo ""
    echo "  File being edited: $FILE_PATH"
    echo "  This file is in the MAIN repo: $MAIN_ROOT"
    echo ""
    echo "  Edit the worktree copy instead:"
    echo "  ${WORKTREE_ROOT}/${RESOLVED_PATH#$MAIN_ROOT/}"
    echo ""
    echo "================================================================"
    exit 1
fi

exit 0
