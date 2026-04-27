# Research: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Phase**: 0 (input → plan.md technical context, output → data-model.md design)
**Date**: 2026-04-27 (Stage 4.1 refresh)
**Supersedes**: `_archive/research-2026-04-06.md` and the Wave A research that targeted a single-dashboard design

## R1 — VN/US warehouse: real `stock.location` partition or logical only?

**Decision**: **Logical-only for Phase 1.** A single `stock.warehouse` (existing default) hosts both VN and US production zones; the partition is a Selection (`vn` / `us`) on `sale.order.fulfillment.warehouse_zone`. Filtering/grouping on the Process Dashboard uses this Selection.

**Rationale**: True `stock.location` per warehouse adds inventory accounting separation (per-location reorder rules, per-location quants, per-location pickings). The team has not asked for those mechanics and the master-plan open question Q9 has not been resolved. Splitting now would force migration of every product reorder rule when the answer comes back. Selection now → migrate to `stock.warehouse` later if/when the answer is "yes" — that migration is straightforward (set warehouse based on zone for all open orders).

**Alternatives considered**:
- Two `stock.warehouse` records seeded immediately. Rejected: introduces inventory mechanics the team has not yet committed to. Reordering, transfers between warehouses, and per-warehouse forecasting all become live decisions the moment we ship.
- Two `stock.location` records under one warehouse. Rejected: same accounting overhead as above with weaker isolation.

## R2 — 17 default-seed pipeline stages: exact names, colours, transitions

**Decision**: Default seed pipeline `"Vietnam Internal Production"` ships with the following stages (from SRS_EN v2.2 §6 + spec.md §US3, ordered by `sequence` step 10):

| Seq | Technical Name | Vietnamese Label | Colour | Initial | Terminal | Terminal-for-Inventory | Mapped MO state |
|----|----|----|----|----|----|----|----|
| 10 | `awaiting_design_file` | CHỜ FILE | `#FFC107` (amber) | ✓ | | | `draft` |
| 20 | `awaiting_mp_approval` | CHỜ DUYỆT | `#03A9F4` (sky) | | | | `draft` |
| 30 | `proof_sent_to_buyer` | ĐÃ GỬI PROOF | `#9C27B0` (purple) | | | | `draft` |
| 40 | `route_us_partner` | US-od | `#2196F3` (blue) | | | | `confirmed` |
| 50 | `route_vn_internal` | Vietnam-od | `#4CAF50` (green) | | | | `confirmed` |
| 60 | `producing_dish` | VN-Dish | `#8BC34A` (lime) | | | | `progress` |
| 65 | `defect_rework` | VN-Dish NG | `#F44336` (red) | | | | `done` (parent) + child MO |
| 68 | `redesign_required` | [Fix]VN-Dish | `#FF9800` (orange) | | | | `cancel` + new MO |
| 70 | `new_product_qa` | VN-SP mới | `#3F51B5` (indigo) | | | | `draft` |
| 75 | `producing_apron` | VN-Apron | `#8BC34A` | | | | `progress` |
| 80 | `producing_hkf` | VN-Handkerchief | `#8BC34A` | | | | `progress` |
| 85 | `partial` | Sản xuất 1 phần | `#FFEB3B` (yellow) | | | | `progress` |
| 90 | `packed` | VN-Packed | `#009688` (teal) | | | ✓ | `done` |
| 92 | `packed_variant_1` | VN-Packed 1 | `#009688` | | | ✓ | `done` |
| 95 | `fulfilled` | VN-Fulfilled | `#4CAF50` | | ✓ | ✓ | `done` (MO + picking) |
| 98 | `bad_approval` | Duyệt sai | `#795548` (brown) | | ✓ | | `cancel` |
| 99 | `overdue` | Quá hạn sản xuất | `#E91E63` (pink) | | | | (any) |

**Transitions**: per ADR-010 §7, the seed ships with `transition_policy='dag_with_admin_override'`. Allowed `next_stage_ids` derived from the natural flow:
- `awaiting_design_file → awaiting_mp_approval → proof_sent_to_buyer? → {route_us_partner, route_vn_internal}`
- `route_vn_internal → {producing_dish, producing_apron, producing_hkf, new_product_qa, partial}`
- Any producing state `→ packed | packed_variant_1 | defect_rework | redesign_required`
- `packed | packed_variant_1 → fulfilled`
- `*_required → bad_approval` (manual)
- `overdue` is a derived flag (auto-set when `date_planned < now`), not a step in the DAG

**Two additional seed pipelines** (per ADR-010 §9):
- **"Gearment POD"** (4 stages: `pending → accepted → in_production → shipped`)
- **"Multi-Technique Hybrid"** (template: 3 unspecified stages — admin clones and customises per hybrid SKU)

**Rationale**: The 17-stage seed is a faithful encoding of the existing PD workflow from SRS §6. Colours follow Material Design 500-tier hex codes for visual consistency (and survive accessibility contrast checks). The DAG-with-admin-override policy preserves PD discipline (the 17 transitions cover 95% of legitimate moves) while letting an admin patch around edge cases without a code change.

**Alternatives considered**:
- `transition_policy='dag_strict'`: rejected because it would force PD to file admin-tickets when an order genuinely needs to backflow (e.g., from `packed` to `defect_rework` after a final-QA failure).
- `transition_policy='free_form'`: rejected because it removes the audit-driven discipline that the policy exists to enforce.
- Different colour palette per stage type (initial / progressing / terminal). Rejected: the team has not asked for it and the visual noise would compete with row decorations (qty≥2, Push, Amazon, overdue) which carry the higher-priority signal.

## R3 — Design-file delivery failure semantics (ADR-009 §4 + ADR-012 GDrive)

**Decision**: Three layers of state:

1. **Route record state** (per `design.file.route`): `pending → sent | acknowledged | failed` (per ADR-009 §4). Job dispatcher writes `state='sent'` after successful delivery action (e.g., GDrive permission grant succeeded, Gearment API push returned 200), `state='acknowledged'` if the recipient model confirms back, `state='failed'` after final retry exhausts.
2. **Stuck-route warning badge** (per ADR-009 §4): any `design.file.route` with `state ∈ {'pending', 'failed'}` and `create_date < now() - 2h` raises a yellow badge on the **order's** Process Dashboard row. Click → opens the route's chatter for triage.
3. **GDrive auth failure** (per ADR-012): handled at the *job* layer below the route layer. If the GDrive service-account token is expired, the job enters Odoo's queue-job retry policy (exponential backoff, 5 retries over 10 minutes). After retry exhaustion, the route flips to `state='failed'` and an alert (sentry + chatter) fires. **No automatic fallback to Discord.** The on-call admin is expected to either (a) reissue the GDrive service-account credential and rerun, or (b) manually post the file to Discord and click an explicit "Mark routed via Discord (manual)" action on the route, which sets `state='acknowledged'` with an audit note.

**Rationale**: The two ADRs specify the layers from different angles (file-lifecycle vs storage-failover). The Decision combines them into one timeline so a developer reading the spec sees the whole picture.

**Alternatives considered**:
- Auto-fallback to Discord. Rejected by ADR-012 §3.
- Combine state and badge into a single `route_health` enum. Rejected because state and badge measure different concepts (state = where in the pipeline; badge = is it stuck?). Conflating them removes the "approved-pending-route" gradient.

## R4 — MP inline-edit on destination fields: hidden, read-only, or banner?

**Decision**: **Read-only with banner.** When `sale.order.has_pending_address_change == True`, the destination fields (`partner_shipping_id`, `street`, `street2`, `city`, `zip`, `state_id`, `country_id`) render with `readonly` attrs and a banner appears at the top of the form: "Đang chờ duyệt yêu cầu đổi địa chỉ — bấm vào Yêu cầu đổi địa chỉ để xem chi tiết." A "Request address change" button is visible to MP users to initiate a new request.

**Rationale**: MP needs visibility into the *current* address (and the requested change) for customer-service triage — hiding the fields would break that workflow. Read-only with banner is the standard Odoo idiom (matches Sale Order Confirmation lock, Invoice posted lock).

**Alternatives considered**:
- Hide fields entirely. Rejected: MP support agents cannot answer "what address is on the order today?" without leaving the form.
- Allow MP edit but raise on save. Rejected: bad UX, surprises the user after they've typed.

## R5 — `has_pending_address_change` storage strategy

**Decision**: `store=True` + `compute_sudo=True` + `@api.depends('address_change_request_ids.state')` with a search method fallback. Indexed for fast Tracking Dashboard filter.

**Rationale**: The Tracking Dashboard uses this field as a row-decoration trigger and as a bulk-action exclusion filter (FR-017). Both need cheap reads. Computed-but-not-stored would force a join on every dashboard render against the request table; `store=True` invalidates the join. `compute_sudo=True` is needed because MP users (without read access on `etsy.address.change.request`) still see the boolean on their Order Dashboard.

**Cost**: a write on `etsy.address.change.request.state` triggers recompute + write on the related `sale.order` row. Acceptable: address-change requests are rare (<10/day projected) and the recompute is single-row.

**Alternatives considered**:
- `store=False` (purely virtual). Rejected: cannot index, cannot search, cannot decorate efficiently.
- Trigger via inverse `_inverse_state` on the request model. Rejected: harder to reason about than `@api.depends`, no search-method support.

## Open questions deferred to Phase 1

These do NOT block Phase 1 design but should be tracked:

- **Q-DEFER-1**: Should the auto-version-on-edit policy (ADR-010 §5) snapshot the entire pipeline or just the stage list? Decision-time: at Phase 1 data-model design.
- **Q-DEFER-2**: When a pipeline is auto-versioned mid-cutover, what happens to in-flight orders whose stages were renamed? Per ADR-010 §5 they pin to the old version — but does the old version stay editable for typo fixes? Default: NO; admin must rename + new-version. Confirmed via decision-log later.
- **Q-DEFER-3**: GDrive folder layout for design files — flat per-shop, or nested by year/month? Defer to ADR-012 implementation notes.

## Cross-references

- SRS_EN v2.2 §5 (Order Dashboard), §6 (Tracking Dashboard), §7 (Process Dashboard), §8 (approval flows), §10/§10.5 (file lifecycle + configurable pipeline)
- ADR-005 (carrier), ADR-006 (storage policy), ADR-007 (delegation mixin), ADR-009 (file lifecycle), ADR-010 (configurable pipeline), ADR-012 (GDrive failover)
- Master plan open questions Q9 (warehouse), Q11 (VN-Packed 1 semantics — now resolved at runtime per ADR-010), Q15 (multi-technique routing — now resolved via "Multi-Technique Hybrid" pipeline per ADR-010 §9)
