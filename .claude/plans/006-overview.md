# Master Plan 006 — Overview Snapshot

**Snapshot date**: 2026-05-21
**Generated from**: [`006-master-plan-tracking.md`](006-master-plan-tracking.md) (authoritative — owner, blockers, per-slice detail live there)
**Regenerate**: refreshed in playbook Phase 7. Do NOT hand-edit slice detail here; this is a derived digest only.

---

## Final target

Per ADR-008 (API-first pivot): a real **Etsy → Odoo → Gearment ingest→fulfill→track pipeline live on production shops**, replacing the legacy email parser. Reporting/observability is explicitly post-E2E polish.

**Coded toward the E2E-pipeline target: ~85%.** The ingest→fulfill→track code loop is closed (P1-12 landed 2026-05-16, closed US3). Remaining work to the target is **operational cutover**, not new feature code. **New gate surfaced 2026-05-21**: staging Odoo is still on `etsy_integration` 19.0.1.0.0 (no `active_source`, no OAuth columns, mhc/mhf not installed, no secrets mount) — `P1-11-DEPLOY-STAGING` must land before P1-11 can be exercised against jahandmadeart or any other shop.

---

## Scope scorecard

| Scope | Done / Total | % done | What's left |
|---|---|---|---|
| External deps | E3 ✓, E1 ✓ (4 scopes), E2 partial | ~80% | E2 Gearment API sandbox keys (owner); `conversations_r` not approved |
| Phase 0 — Spec 002 cleanup + Spec 005 sandbox + observability | 17 / 27 | ~63% | Critical path all done; remaining = deferred polish (P0-08/09/10 data triage, P0-11/12/13 health/logger/index, P0-19 GKE fingerprint); P0-02/04 owner-ops |
| Phase 1 — Dashboards + approvals + Spec 005 cutover | ~40 / ~50 | ~80% | P1-07 i18n, **P1-11** pilot flip (owner-op), **P1-13** (waiting P1-11), P1-AUTO-TX, P4-01b, P1-DESIGN-AUTO-ARCHIVE |
| ↳ Hybrid dropship + MTO | 7 / 7 | 100% | — |
| ↳ Family A — product images | 4 / 4 | 100% | — |
| ↳ Family B — multi-design | 5 / 7 | ~70% | P1-DESIGN-AUTO-ARCHIVE; ENV-FIX-MRP (ops) |
| ↳ Family C — after-sale conversations | 0 / 3 | 0% | **Blocked**: `conversations_r` excluded from E1; P1-MSG-SCOPE re-submit is live prereq |
| ↳ Family D — CRM lead (Spec 007) | 5 / 7 | ~70% | P3-LEAD-MAIL-ALIAS, P3-LEAD-API-ROUTING |
| ↳ Listings & inventory (Spec 008) | 3 / 4 | 75% | P-LIST-INV-PUSH (first `listings_w` writeback, deferred) |
| Phase 2 — Tracking import + GDrive poll + shop cutovers | 6 / 8 | 75% | P2-07 (Gmail-cron rebind / email→API cutover), P2-08; exit = all 19 shops `api_only` |
| Phase 4 — Gearment + returns + pricing audit | ~8 / 10 | ~80% | P4-02 returns, P4-03 pricing audit |
| Phase 5 — Inventory/catalog/scan/Amazon/website | 0 / 5 | 0% | Future parallel tracks P5-01..05 |

---

## Priority to reach the final target

**P0 — on the cutover critical path:**
0. **P1-11-DEPLOY-STAGING** — pre-cutover staging refresh (rsync 3 modules + install mhc/mhf + upgrade etsy_integration 19.0.1.0.0→19.0.2.3.8 + add `secrets/` mount + drop Etsy credentials JSON + set `etsy.oauth.credentials_path`). *Hard prereq for P1-11*; release/ops task. _Added 2026-05-21._
1. **P1-11** pilot-shop cutover — owner-operational flip (`active_source='api'`); biggest single unblock once 0 is green
2. **P1-13** — additional 2–4 shops (waiting only on P1-11)
3. **P2-07** — Gmail-cron rebind / email→API cutover; Phase 2 exit = all 19 shops `api_only`, Gmail off
4. **E2 Gearment sandbox keys** (owner) — required for P1-11 §5.3 tracking-back round-trip verify

**P1 — clean/complete pipeline:**
5. P-LIST-INV-PUSH (inventory writeback)
6. P1-07 Vietnamese i18n (Phase 1 exit criterion)
7. P1-DESIGN-AUTO-ARCHIVE, P4-01b

**P2 — deferred until E2E green:**
8. P0-08/09/10 (data triage — BA-dependent)
9. P0-11/12/13/19 (health tile, `_logger.info` ban, indexes, GKE fingerprint)

**P3 — off critical path:**
10. Family C conversations (blocked on Etsy `conversations_r` re-approval)
11. Family D tail (P3-LEAD-MAIL-ALIAS, P3-LEAD-API-ROUTING)
12. P4-02 returns, P4-03 pricing audit; all of Phase 5

---

## Pointers

- **Next codeable dispatch**: P-LIST-INV-PUSH deferred → see tracker §"Active prioritization" for next; P1-11 stays owner-operational, now gated on `P1-11-DEPLOY-STAGING` (release/ops slice, not a code dispatch)
- **Last tracker change-log entry**: 2026-05-21 (P1-11-DEPLOY-STAGING raised — bookkeeping)
- **Branch**: `feature/006-master-plan-coding` (merge to `main` after W7 E2E sprint)
