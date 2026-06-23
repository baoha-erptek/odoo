# Codex Review Plan — Etsy Order Coverage + Manual Pull + Per-User Shop Scoping

> Run by the orchestrator (not Codex) after each story lands. Companion to
> `implementation-brief.md`. JIRA ESTY-205/206/207. **Block on any CRITICAL/HIGH.**

## Procedure (per story)
1. `git diff <codex-commit>` for the story's scope.
2. Launch **`code-reviewer` + `security-reviewer` in parallel** (single message, two
   Agent calls) over that diff.
3. Run the story's tests + the cross-cutting checks. Triage findings by severity
   (CRITICAL/HIGH block; MEDIUM fix if cheap; LOW note).
4. Only after sign-off, run the staging E2E for that story.

## Per-story review focus

### Story 1 — P1-SHOP-USER-SCOPE (security-critical; review hardest)
- [ ] Rule semantics proven by **test with `with_user`**, not by reading XML: a plain
      `base.group_user` sees own-shop Etsy + all non-Etsy, NOT other shops' Etsy orders.
- [ ] `sales_team.group_sale_manager` AND a non-manager `base.group_system` admin both
      see ALL orders (Odoo auto-bypasses rules only for superuser id=1).
- [ ] Restrictive rule keeps the `('etsy_shop_id','=',False)` branch (non-Etsy visible).
- [ ] `user_id` is `ondelete='set null'` (deleting a user must not cascade shops/orders).
- [ ] No `mail.message` rule added (redundant — chatter follows parent doc access).
- [ ] Sync cron (`__system__`) and the Story-2 sudo path still ingest with rules active.

### Story 2 — P1-ORD-PULL-BTN (sudo + FR-017 pattern)
- [ ] Allowed-shop set computed from `env.user` BEFORE any `sudo()`; sudo never applied
      to a user-supplied shop id (FR-017 write-defense pattern).
- [ ] Admin/sale-manager branch = all `api` shops; scoped branch = `user_id == env.user`.
- [ ] Inline comment justifies the sudo (OAuth tokens are `base.group_system` fields).
- [ ] Header button actually renders in the control panel — verify resolved arch AND a
      live browser check (the "arch passes but renders nothing" trap), not XML alone.
- [ ] No-shop / empty user gets a clean notification, not a traceback.

### Story 3 — P1-ORD-COVERAGE (correctness + reconciliation)
- [ ] A1 diff artifact present; every "missing/mismatch" row is closed by the patch or
      explicitly deferred with rationale.
- [ ] `amount_total` reconciles with Etsy `grandtotal` on the real receipt; a mismatch
      was **escalated** (pricing bug), not hidden by writing computed fields.
- [ ] New Etsy fields are informational/read-only — pricing engine untouched.
- [ ] `_resolve_line_product`: each tier tested (SKU-link, default_code, name,
      create+flag) incl. duplicate-SKU determinism; tiers 1-2 never auto-create.
- [ ] Frozen-dataclass contract preserved in `etsy_order_payload.py`.
- [ ] `_status_only_resync` still preserves operator-owned fields.

## Cross-cutting checklist (all stories)
- [ ] New model ⇒ ACL present; `sudo()` / raw SQL commented (only `product.product`
      gains a field here — no new model expected).
- [ ] No `_logger.info`-as-debug / `print(`; ruff clean; functions <50 lines; diff surgical.
- [ ] Two-Phase tests with failing-first evidence; coverage ≥80% on changed lines.
- [ ] `-u etsy_integration --stop-after-init` exit 0; `--test-tags /etsy_integration`
      green; no NEW full-suite regressions vs baseline.

## Sign-off gate
- [ ] Both review agents return 0 CRITICAL/HIGH (or all fixed + regression-tested).
- [ ] Staging E2E passes: A1 diff reconciles after the fix; scoped user login shows only
      their shop's orders; admin sees all; **Pull Etsy Orders** returns counts.
- [ ] Tracker rows → `done` with commit shas; ESTY-205/206/207 → In Review (transition 31)
      with ADF evidence comment; `/learn` insight captured; `findings.md` updated if
      anything surprised us.
