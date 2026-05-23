# Master Plan 006 — Overview Snapshot

**Snapshot date**: 2026-05-23
**Generated from**: [`006-master-plan-tracking.md`](006-master-plan-tracking.md) (authoritative — owner, blockers, per-slice detail live there)
**Regenerate**: refreshed in playbook Phase 7. Do NOT hand-edit slice detail here; this is a derived digest only.

---

## Final target (amended 2026-05-23 per ADR-014)

Per ADR-008 (API-first pivot) **plus ADR-014 (central product hub)**: a real **Etsy ↔ Odoo ↔ Gearment ingest→fulfill→track pipeline live on production shops** (Etsy → Odoo → Gearment for orders; Gearment → Odoo → Etsy for tracking), **plus Odoo as the central catalog source publishing to Etsy** (Excel-canonical recurring sync feeding Odoo `product.template`, operator-wizard publish to Etsy with full create→images→inventory→publish flow). Amazon + ecommerce remain Phase 5. Reporting/observability is post-E2E polish.

**Coded toward the amended target: ~70%.** The denominator grew on 2026-05-23 with the addition of MP006 Phase 3 (15 new implementation slices + 1 deferred — see Spec 009/010/011 tasks.md). The ingest→fulfill→track loop is closed (was ~85% of the pre-amendment target). New work: catalog hub + outbound publish (0/15). Operational cutover for the existing inbound pipeline (P1-11 pilot sign-off, P1-13, P2-07) continues in parallel.

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
| **Phase 3 — Central product hub + Odoo→Etsy publish (NEW 2026-05-23 per ADR-014)** | **1 / 16** | **~6%** | P-HUB-SPEC `doing`; 5 foundation slices (Spec 009) + 4 catalog-sync slices (Spec 010) + 5 publish slices (Spec 011) + 1 deferred (P-HUB-XLS-AVAILABILITY-MAP) + VN docs |
| Phase 4 — Gearment + returns + pricing audit | ~8 / 10 | ~80% | P4-02 returns, P4-03 pricing audit |
| Phase 5 — Inventory/scan/Amazon/website | 0 / 4 | 0% | Future parallel tracks; catalog work relocated to Phase 3 |

---

## Priority to reach the amended final target

**P0 — on the inbound cutover critical path (unchanged from 2026-05-21 snapshot):**
1. **P1-11** pilot-shop cutover — owner-operational flip (`active_source='api'`) on JaHandmadeArt; signed off
2. **P1-11-SHOPID-BOOTSTRAP** — auto-fetch `etsy_api_shop_id` on OAuth + C-ESY-003 constraint + tests for the 3 adapter call sites (follow-up to P1-11-WIRE-LIVE)
3. **P1-13** — additional 2–4 shops (waiting only on P1-11 sign-off)
4. **P2-07** — Gmail-cron rebind / email→API cutover; Phase 2 exit = all 19 shops `api_only`, Gmail off
5. **E2 Gearment sandbox keys** (owner) — required for P1-11 §5.3 tracking-back round-trip verify

**P0' — Phase 3 critical path (new 2026-05-23 per ADR-014):**
6. **P-HUB-PROD-MODEL** — foundation: `multichannel.sales.channel` + `product.channel.status` + `product.template` extensions. Unblocks every other Phase 3 slice.
7. **P-HUB-WIZARD** + **P-HUB-SKU-DRIFT** (mhc-half) — operator entry surfaces for catalog hygiene
8. **P-PUB-CLIENT** — `EtsyApiClient.post/put/patch/post_multipart`; unblocks all publish slices + the Etsy push hook for P-HUB-SKU-DRIFT
9. **P-HUB-XLS-PARSE → P-HUB-XLS-INGEST → P-HUB-XLS-CRON → P-HUB-IMAGES** — recurring catalog sync (sequential)
10. **P-PUB-DRAFT → P-PUB-IMAGES → P-PUB-INVENTORY → P-PUB-PUBLISH → P-PUB-E2E** — outbound publish chain (Spec 011)
11. **P-HUB-BACKFILL** — non-destructive bidirectional link of existing JaHandmadeArt listings

**P1 — clean/complete pipeline:**
12. P1-07 Vietnamese i18n (Phase 1 exit criterion)
13. P1-DESIGN-AUTO-ARCHIVE, P4-01b
14. P-DOCS-FLOW-VN — VN owner-flow docs (can author parts in parallel with Phase 3 implementation; finalize after E2E)

**P2 — deferred until E2E green:**
8. P0-08/09/10 (data triage — BA-dependent)
9. P0-11/12/13/19 (health tile, `_logger.info` ban, indexes, GKE fingerprint)

**P3 — off critical path:**
10. Family C conversations (blocked on Etsy `conversations_r` re-approval)
11. Family D tail (P3-LEAD-MAIL-ALIAS, P3-LEAD-API-ROUTING)
12. P4-02 returns, P4-03 pricing audit; all of Phase 5

---

## Pointers

- **Next codeable dispatch**: **P-HUB-PROD-MODEL** (Phase 3 foundation; unblocks all 14 other Phase 3 slices). P-LIST-INV-PUSH is **superseded by P-PUB-INVENTORY** (Spec 011).
- **Last tracker change-log entry**: 2026-05-23 (MP006 Phase 3 added — central product hub + Odoo→Etsy outbound publish, per ADR-014)
- **Branch**: `feature/006-master-plan-coding` (merge to `main` after W7 E2E sprint)
- **Plan file** (this Phase 3 scope amendment): `/home/odoo/.claude/plans/actually-need-to-check-polymorphic-crayon.md`
