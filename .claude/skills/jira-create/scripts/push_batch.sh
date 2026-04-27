#!/usr/bin/env bash
#
# push_batch.sh — Push staged .md drafts under .docs/tasks/ESTY-DRAFT-*/ to JIRA.
#
# Usage:
#   bash .claude/skills/jira-create/scripts/push_batch.sh epics
#   bash .claude/skills/jira-create/scripts/push_batch.sh stories
#   bash .claude/skills/jira-create/scripts/push_batch.sh tasks
#   bash .claude/skills/jira-create/scripts/push_batch.sh all     # epics, then stories, then tasks
#
# Files already containing a non-empty jira_key are skipped (idempotent).
# After a successful push, the parent directory is renamed from
# ESTY-DRAFT-<slug>/ to ESTY-<returned-key>/ so future runs skip it.
#
set -euo pipefail

die() { echo "ERROR: $1" >&2; exit 1; }

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo_root" ] || die "must be run inside a git repo"
cd "$repo_root"

PUSH_SCRIPT="$repo_root/.claude/skills/jira-create/scripts/push_to_jira.sh"
[ -x "$PUSH_SCRIPT" ] || die "push_to_jira.sh not executable: $PUSH_SCRIPT"

KIND="${1:-all}"
case "$KIND" in
    epics|stories|tasks|all) ;;
    *) die "usage: push_batch.sh {epics|stories|tasks|all}" ;;
esac

# Read frontmatter type from a file (epic/story/task/bug)
get_type() {
    python3 -c "
import sys
content = open('$1').read()
if not content.startswith('---'): sys.exit(1)
end = content.index('---', 3)
for line in content[3:end].strip().split('\n'):
    if line.startswith('type:'):
        print(line.split(':', 1)[1].strip()); break
" 2>/dev/null
}

push_kind() {
    local want="$1" pushed=0 skipped=0 failed=0
    echo "===> Pushing $want issues"
    shopt -s nullglob
    for dir in .docs/tasks/ESTY-DRAFT-*/; do
        local file="${dir}progress-tracker.md"
        [ -f "$file" ] || continue
        local got
        got=$(get_type "$file" || true)
        [ "$got" = "$want" ] || continue

        echo "--- $file"
        if "$PUSH_SCRIPT" "$file"; then
            # Extract returned key from the just-updated frontmatter
            local key
            key=$(python3 -c "
content = open('$file').read()
end = content.index('---', 3)
for line in content[3:end].strip().split('\n'):
    if line.startswith('jira_key:'):
        print(line.split(':', 1)[1].strip()); break
")
            if [ -n "$key" ]; then
                local target=".docs/tasks/${key}"
                mv "$dir" "$target"
                echo "renamed: $dir → $target/"
                pushed=$((pushed+1))
            else
                echo "WARN: push reported success but no jira_key in frontmatter — left as-is"
                failed=$((failed+1))
            fi
        else
            echo "FAILED on $file — stopping batch (resume by re-running this command)"
            failed=$((failed+1))
            return 1
        fi
    done
    shopt -u nullglob
    echo "===> $want: pushed=$pushed skipped=$skipped failed=$failed"
}

case "$KIND" in
    epics)   push_kind epic ;;
    stories) push_kind story ;;
    tasks)   push_kind task ;;
    all)     push_kind epic && push_kind story && push_kind task ;;
esac
