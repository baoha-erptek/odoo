#!/usr/bin/env bash
# validate-hooks.sh — every hook command wired in .claude/settings.json that points
# at a project script resolves to a file that exists and is executable.
# This is the check that would have caught the original "scripts/ dir missing" bug.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SETTINGS="$PROJECT_ROOT/.claude/settings.json"
ERRORS=0

echo "=== Validating hooks (settings.json) ==="
[ -f "$SETTINGS" ] || { echo "FAIL: $SETTINGS not found"; exit 1; }

python3 -c "import json,sys; json.load(open('$SETTINGS'))" 2>/dev/null \
  || { echo "FAIL: settings.json is not valid JSON"; exit 1; }
echo "PASS: settings.json valid JSON"

# Extract every hook command string, and the statusLine command.
CMDS="$(python3 - "$SETTINGS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
out = []
for grp in (d.get("hooks") or {}).values():
    for entry in grp:
        for h in entry.get("hooks", []):
            if h.get("command"):
                out.append(h["command"])
sl = (d.get("statusLine") or {}).get("command")
if sl:
    out.append(sl)
print("\n".join(out))
PY
)"

while IFS= read -r cmd; do
  [ -n "$cmd" ] || continue
  # Pull the first token that looks like a .claude/scripts path (strip quotes + $CLAUDE_PROJECT_DIR).
  path="$(echo "$cmd" | grep -oE '(\$CLAUDE_PROJECT_DIR/)?\.claude/[^" ]+\.(sh|py)' | head -1)"
  [ -n "$path" ] || continue
  rel="${path#\$CLAUDE_PROJECT_DIR/}"
  full="$PROJECT_ROOT/$rel"
  if [ ! -f "$full" ]; then
    echo "FAIL: hook references missing script: $rel"; ERRORS=$((ERRORS + 1))
  elif [ ! -x "$full" ]; then
    echo "FAIL: hook script not executable: $rel"; ERRORS=$((ERRORS + 1))
  else
    echo "PASS: $rel"
  fi
done <<< "$CMDS"

echo ""
[ "$ERRORS" -eq 0 ] && echo "hooks: ALL CHECKS PASSED" || echo "hooks: $ERRORS ERROR(S) FOUND"
exit "$ERRORS"
