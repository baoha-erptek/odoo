# Repository git hooks

Version-controlled git hooks for this repo. Standard git ignores `.git/hooks/`,
so we keep our hooks in `.githooks/` and ask devs to opt in once per clone.

## Activation (one-time per clone / per server)

```bash
git config core.hooksPath .githooks
chmod +x .githooks/*
```

Verify:
```bash
git config core.hooksPath          # should print: .githooks
ls -la .githooks/                  # should show post-commit as executable
```

## Installed hooks

| Hook | Trigger | Action | Bypass |
|---|---|---|---|
| `post-commit` | After every commit | If commit touched `docs/owner/**/*.md` → run `.claude/scripts/push_owner_confluence.py` in background; logs to `.docs/tasks/_post_commit_confluence.log` | `SKIP_CONFLUENCE_SYNC=1 git commit ...` OR include `[skip-confluence]` in commit message OR `.env` missing `JIRA_API_KEY` |

## Logs

Background sync output → `.docs/tasks/_post_commit_confluence.log` (gitignored).
Tail to verify a post-commit run worked:

```bash
tail -50 .docs/tasks/_post_commit_confluence.log
```

## Disable temporarily

```bash
git config --unset core.hooksPath          # revert to default .git/hooks
# or for one commit:
SKIP_CONFLUENCE_SYNC=1 git commit -m "..."
# or via marker in message:
git commit -m "WIP [skip-confluence]"
```

## Why background

The push touches Atlassian Cloud API (~13 pages, ~5-10s with hash-skip
optimisation; up to ~30s if all pages changed). Running synchronously would
slow every commit. Background + log file gives the best of both: fast `git
commit`, traceable failures.
