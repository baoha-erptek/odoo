# Optional integrations

Battle-tested workflow pieces ported from the sibling Odoo projects (`hr_project`,
`odoo19_esty`). **All disabled by default** — nothing here is wired into
`.claude/settings.json`. Each bundle carries external dependencies most projects
won't need, so enable per-project only.

Credentials are always via env or a git-ignored file — never hardcode.

## How to enable a bundle

1. Set the tokens listed for the bundle (env vars or a sourced creds file).
2. Move the relevant files up into the live tree:
   - commands → `.claude/commands/`
   - agents → `.claude/agents/` (then add a row to the model-tier table in
     `rules/common/performance.md`)
   - skills → `.claude/skills/`
   - scripts → `.claude/scripts/` and wire any hook in `settings.json`
3. Run `.claude/scripts/ci/validate-hooks.sh` after wiring so a bad path is caught.

---

## 1. JIRA task-bootstrap loop

Files: `commands/jira-to-task.md`, `commands/resume-task.md`, `commands/sync-to-jira.md`,
`skills/jira-ticket-analyzer/`, `skills/jira-create/`.

Bootstraps a task dir from a JIRA ticket, classifies it (`jira-ticket-analyzer`), creates
issues local-first then pushes via Direct API (`jira-create`), and (for scope/AC triage)
dispatches the `product-owner` agent — which now ships **live** in `.claude/agents/`, so no
port needed. `jira-create` is env-driven: set `JIRA_SITE`, and its `.md` templates carry a
`__JIRA_KEY__` placeholder for your project key.

**Tokens:** `JIRA_SITE` (e.g. `yourco.atlassian.net`), `JIRA_KEY` (e.g. `PROJ`),
`ATLASSIAN_CREDS` (file exporting `ATLASSIAN_EMAIL` + `ATLASSIAN_API_TOKEN`).

**Dropped/softened from hr_project:** gbrain seeding removed (filesystem
`progress-tracker.md` is canonical); `human-mcp` attachment extraction and superpowers
`brainstorming` are optional; use the `using-git-worktrees` skill instead of hr's
`utils/worktree-env.sh`. `product-owner` runs at Sonnet tier — add it to the
performance.md binding table when you enable it.

## 2. Owner-docs → Confluence / JIRA sync

> **This project (odoo19_esty) runs bundle 2 LIVE**: the `push_owner_*.py` +
> `gen_owner_status_pdf.py` scripts live in `.claude/scripts/` (not here) and are wired
> via `.githooks/post-commit`. The copies were intentionally omitted from `optional/scripts/`
> to avoid divergence. Edit the live copies under `.claude/scripts/`.

Files: `scripts/push_owner_confluence.py`, `scripts/push_owner_jira.py`,
`scripts/push_owner_jira_delta.py`, `scripts/gen_owner_status_pdf.py`,
`githooks/post-commit`, `githooks/README.md`.

Syncs `docs/owner/*.md` operator guides to a Confluence space and pushes slice status
to JIRA on commit. **Tokens:** Confluence space key + `ATLASSIAN_*` creds; JIRA project
key. Bypass a single sync with `SKIP_CONFLUENCE_SYNC=1` or `[skip-confluence]` in the
commit message. Enable by symlinking `githooks/post-commit` into `.git/hooks/` (or
`git config core.hooksPath`).

## 3. Pipeline gates + worktree guard

Files: `scripts/pipeline-gate-check.sh`, `scripts/worktree-path-guard.sh`.

`pipeline-gate-check.sh` enforces plan → test → review ordering before commit/push;
`worktree-path-guard.sh` refuses edits in the main repo when a ticket belongs in a
worktree. Wire as PreToolUse(Bash)/Stop hooks in `settings.json` if you want hard
ordering gates. Heavier than the default advisory hooks — opt in deliberately.

## 4. Feature ledger

Files: `feature-ledger/FEATURE-TEMPLATE.md`.

Filesystem regression-catch record read by the `product-owner` agent (bundle 1). Copy
the template to `.docs/po/features/<id>.md` per feature and keep its invariants current.
No gbrain dependency.
