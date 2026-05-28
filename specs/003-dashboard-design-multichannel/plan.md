# Implementation Plan: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Branch**: `003-dashboard-design-multichannel` | **Date**: 2026-04-27 | **Spec**: [spec.md](spec.md) (Wave B, 2026-04-13)
**Authority**: [SRS_Multichannel_Hub_EN.md v2.2](../006-master-plan/SRS_Multichannel_Hub_EN.md) §5/§6/§7/§8/§10/§10.5/§11
**ADRs**: [001](../006-master-plan/adrs/ADR-001-spec-004-split.md) (split) · [003](../006-master-plan/adrs/ADR-003-module-decomposition.md) (4-module split) · [005](../006-master-plan/adrs/ADR-005-carrier-unification.md) (carrier) · [006](../006-master-plan/adrs/ADR-006-design-file-storage.md) (storage) · [007](../006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md) (mixin) · **[009](../006-master-plan/adrs/ADR-009-file-lifecycle.md) (file lifecycle)** · **[010](../006-master-plan/adrs/ADR-010-configurable-order-pipeline.md) (configurable pipeline)** · **[012](../006-master-plan/adrs/ADR-012-gdrive-failover.md) (GDrive failover)**

## Summary

Replace the Google-Sheet workflow (BA / Marketing / Production / Pricing-Audit tabs) with a coherent set of role-specific Odoo dashboards backed by a single `sale.order` data model and a delegation sibling (`sale.order.fulfillment`, ADR-007). Ship the safety-critical address-change approval workflow (`etsy.address.change.request`). Replace the original spec.md's hardcoded `production_stage` enum with the **configurable order pipeline** stack from ADR-010 (`order.pipeline`, `order.pipeline.state`, `pipeline.team`, `order.pipeline.transition.log`). Replace the original spec.md's simple `order.design.file` model with the **immutable-history file lifecycle** stack from ADR-009 (`design.file`, `design.file.route`, `design.print.batch`). Lay a multi-channel foundation (`sales_channel`, `channel_order_ref`) so Amazon (Spec 010) and Website (Spec 011) channels plug in without schema churn.

## Stage-2 ADR deltas vs spec.md (Wave B)

The Wave B spec (2026-04-13) was authored before the Stage-2 ADRs landed (2026-04-26). This plan integrates those deltas; spec.md remains the authoritative requirements document for FR-001..FR-033 but is augmented as follows:

| Spec.md FR | Wave B intent | Stage-2 ADR refinement |
|---|---|---|
| **FR-018** `order.design.file` model | Single record per file with `state` enum + small/url storage | **Replaced by ADR-009 §1**: `design.file` (immutable, version chain via `parent_file_id`, GDrive primary URL + checksum) + `design.file.route` (per-recipient delivery state, queued-job dispatch) + `design.print.batch` (PD bulk-download A4 layout wizard with 24h cache) |
| **FR-021** roll-up `design_status` on `sale.order.line` | Lowest-of-children rollup | Same intent; computation now reads `design.file` records linked by route, with route-state aware (a file approved but not yet routed shows "approved-pending-route") |
| **FR-022** kanban view | 3 columns (Chờ duyệt / Duyệt / Cần chỉnh lại) | Kanban now reads `design.file.state` plus a "stuck route" badge per ADR-009 §4 (route pending/failed >2h) |
| **FR-023** historical seed | `storage_mode='url'` from DESIGN_LINK_FRONT/BACK | Same; `design.file.parent_file_id=NULL` for seed rows |
| **Spec.md US3 + FR-007** Process Dashboard production_stage enum (Vietnamese labels: Mới / Chờ file / Đang sản xuất / Đã sản xuất / Đã đóng gói / Đã gửi / Huỷ) | Hardcoded enum on `sale.order.fulfillment` | **Replaced by ADR-010 §1**: `sale.order.x_pipeline_id` (Many2one `order.pipeline`) + `sale.order.x_pipeline_state_id` (Many2one `order.pipeline.state`). Default seed pipeline `"Vietnam Internal Production"` ships the 17 SRS §6 stages (CHỜ FILE → … → VN-Fulfilled) + the 7 PD-feedback states the original spec requested. Admin can edit at runtime; in-flight orders pin to pipeline version per ADR-010 §5. |
| **Spec.md US3** stock-move on "Đã sản xuất" | Delegated to Spec 004a hook | Hook signature unchanged; trigger field is now `x_pipeline_state_id.is_terminal_for_inventory` (per ADR-010 §6) instead of a hardcoded enum compare |
| **FR-006** carrier inline-edit | M2O to `shipping.carrier` | Unchanged; ADR-005 carrier model is in scope of this plan |
| **FR-031..FR-033** audit + i18n | mail.thread + tracking=True + vi_VN.po | Unchanged; pipeline + file lifecycle inherit chatter |

> **GDrive policy**: per [ADR-012](../006-master-plan/adrs/ADR-012-gdrive-failover.md), design files may store their primary URL on Google Drive (service account, queue + backoff on auth failure, **no auto-fallback to Discord** — Discord remains the manual escape hatch). The `design.file.file_url` field accepts either an Etsy CDN URL (historical) or a GDrive shareable link (forward).

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (`sale_management`, `stock`, `contacts`, `mail`); no Enterprise modules per ADR-004
**Storage**: PostgreSQL 16+ via Odoo ORM. Design files: GDrive-URL primary (ADR-006 + ADR-012); filestore (`ir.attachment` with `attachment=True` Binary fields) for previews ≤ 2 MB; 10 MB hard cap on filestore Binary writes (`multichannel_hub.large_file_threshold_bytes` `ir.config_parameter`)
**Testing**: TransactionCase + HttpCase + QUnit (OWL views). Phase-1 (DB) verification + Phase-2 (ORM unit) per the project's two-phase rule
**Target Platform**: Linux Docker container (Odoo 19 CE on PostgreSQL 16) + staging at `129.150.63.207` per master-plan §6
**Project Type**: Odoo module — initially in `custom_addons/etsy_integration`, migrated to **`multichannel_hub_core`** during Phase 1 of ADR-003 sequencing (this spec triggers the move)
**Performance Goals**: First-page Order Dashboard render ≤ 3 s on the full 17K+ row dataset; 80 rows per page server-side pagination; bus-pushed live updates within 5 s on Tracking Dashboard
**Constraints**: Odoo 19 CE only (no Enterprise); Vietnamese as default UI language with `vi_VN.po` 100% coverage; UTF-8 round-trip preserved across Excel/CSV; ACL gate on inline-edit (MP cannot edit destination address fields without filing an `etsy.address.change.request`)
**Scale/Scope**: 17,659+ existing orders (post Spec 002 normalization); 19 Etsy shops; 2,294 products; 5–15 production-team users; 17-stage default seed pipeline expandable to N pipelines per ADR-010

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Note**: `.specify/memory/constitution.md` v1.0.0 (ratified 2026-04-02) was authored for the Phase-1 email-parser scope. Several principles are now contextualised by the master plan (ADR-008a v2 makes the email parser a permanent failover, not a deprecation target). The principle-by-principle gate evaluation below maps spec 003 work onto the current state of the master plan.

| Principle | Status | Notes |
|---|---|---|
| I. Odoo-Native First | PASS | Three dashboards = saved `ir.actions.act_window`. Configurable pipeline = data-driven (pure Odoo Models + Selection-via-stage-records, not custom workflow engine). Carrier = standard model with seed XML. No custom JS beyond what OWL list/kanban natively supports. |
| II. Email Parser Isolation | PASS | This spec does not touch the email parser. Per ADR-008a §1 the parser stays in `etsy_channel_email` (peer of `etsy_channel_api`); `multichannel_hub_core` (where this spec lands) has zero source dependency on either channel module. |
| III. Data Integrity First | PASS | Address-change approval is atomic (single `_write` transaction wrapping `etsy.address.change.request.action_approve`). Pipeline transitions write `order.pipeline.transition.log` in the same transaction as the `x_pipeline_state_id` change (ADR-010 §1). Design-file routing writes `design.file.route.state` via queued jobs with idempotency-key dedup (ADR-009 §4). |
| IV. Test-Driven Development | PASS | TDD enforced per project rule. Two-Phase Testing: Phase 1 (DB) verifies row counts + state transitions; Phase 2 (ORM unit) verifies the address-change `@api.constrains`, the design-file 10 MB ceiling, the pipeline auto-version-on-edit logic, and the `vi_VN.po` 100% coverage CI check. Target: 80%+ coverage on new models. |
| V. Incremental Migration | PASS | This spec is independently shippable. US1 (Order Dashboard) ships first as the MVP and unblocks BA adoption; US2/US3 (Tracking + Process) follow within Phase 1; US4–US7 layer in. ADR-009/010 stacks land in dependency order: pipeline + file-lifecycle models → routes/jobs → views. |
| VI. Security by Default | PASS | New ACL group `group_production_team` for design-file approval. Address-change form is read-only for non-BA users at both UI (`readonly` attrs) and ORM (`@api.constrains`). Pipeline structure edits gated by admin group (`base.group_system`). Audit log on every model. No secrets — GDrive uses service account per ADR-012, never a per-user OAuth token. |
| VII. Simplicity Over Completeness | **JUSTIFIED VIOLATION** — see Complexity Tracking. The configurable pipeline (ADR-010) is more complex than a hardcoded enum, justified by the open question "VN-Packed 1 means what?" being unanswerable at code-time. The file-lifecycle stack (ADR-009) is more complex than a single `order.design.file`, justified by the file-routing pain points #11/#12/#18 from the E2 doc. Both choices were Owner-signed in `decision-log.md` D-11/D-15. |

## Project Structure

### Documentation (this feature)

```text
specs/003-dashboard-design-multichannel/
├── plan.md              # This file
├── research.md          # Phase 0 — resolved questions
├── data-model.md        # Phase 1 — full model definitions per ADRs 005/007/009/010
├── quickstart.md        # Phase 1 — verification walkthrough
├── checklists/
│   └── requirements.md  # spec.md FR coverage check (existing)
├── _archive/            # 2026-04-06 single-dashboard spec archived here
└── tasks.md             # Phase 2 — generated by /speckit-tasks (Stage 4.3)
```

### Source Code

```text
custom_addons/multichannel_hub_core/        # NEW module per ADR-003 Phase 1 sequencing
├── __manifest__.py                         # version 19.0.1.0.0; depends: sale_management, stock, contacts, mail
├── models/
│   ├── __init__.py
│   ├── sale_order.py                       # extends with sales_channel, channel_order_ref, x_pipeline_id, x_pipeline_state_id, has_pending_address_change
│   ├── sale_order_fulfillment.py           # ADR-007 delegation sibling (production fields + carrier M2O)
│   ├── sale_order_line.py                  # extends with rolled-up design_status
│   ├── shipping_carrier.py                 # ADR-005 unified carrier
│   ├── etsy_address_change_request.py      # safety-critical approval model
│   ├── design_file.py                      # ADR-009 §1
│   ├── design_file_route.py                # ADR-009 §1 + §4
│   ├── design_print_batch.py               # ADR-009 §1 (wizard)
│   ├── order_pipeline.py                   # ADR-010 §1
│   ├── order_pipeline_state.py             # ADR-010 §1
│   ├── pipeline_team.py                    # ADR-010 §6
│   ├── order_pipeline_transition_log.py    # ADR-010 §1 (single audit table)
│   └── product_template.py                 # extends with x_default_pipeline_id (ADR-010 §2)
├── services/
│   ├── __init__.py
│   ├── design_file_router.py               # queued-job-based route delivery (ADR-009 §4)
│   └── pipeline_resolver.py                # product → category → system-param fallback (ADR-010 §2)
├── views/
│   ├── menu.xml
│   ├── order_dashboard_views.xml           # FR-001..FR-010
│   ├── tracking_dashboard_views.xml        # FR-006, FR-008, FR-017
│   ├── process_dashboard_views.xml         # US3 + ADR-010 pipeline column
│   ├── design_file_views.xml               # kanban + form (FR-022)
│   ├── design_print_batch_wizard.xml       # PD bulk-download wizard
│   ├── etsy_address_change_request_views.xml
│   ├── order_pipeline_views.xml            # admin pipeline editor
│   └── shipping_carrier_views.xml
├── data/
│   ├── order_pipeline_seed.xml             # ADR-010 §9 — 3 default pipelines
│   ├── shipping_carrier_seed.xml           # FR-029 — USPS/UniUni/YunExpress/4PX/DHL/FedEx/GKE
│   └── ir_config_parameter.xml             # large_file_threshold_bytes default 10485760
├── security/
│   ├── ir.model.access.csv
│   ├── multichannel_hub_security.xml       # group_production_team, group_pipeline_admin
│   └── record_rules.xml
├── i18n/
│   └── vi_VN.po                            # FR-032 — 100% coverage CI gate
└── tests/
    ├── __init__.py
    ├── test_address_change_workflow.py     # FR-011..FR-017
    ├── test_design_file_lifecycle.py       # ADR-009 immutable-history + route + batch
    ├── test_order_pipeline.py              # ADR-010 — assignment, versioning, transition log
    ├── test_dashboards.py                  # render perf + decoration logic
    ├── test_carrier.py                     # FR-027..FR-029
    ├── test_channel_backfill.py            # FR-024..FR-026
    └── test_i18n_coverage.py               # FR-032 CI check

custom_addons/etsy_integration/             # EXISTING module — declares dependency on multichannel_hub_core after migration
└── (existing Spec 001 + 002 code; design.file historical seed migration script lands here)
```

**Structure Decision**: Land all this spec's models, views, services, data, and tests in a NEW Odoo module `multichannel_hub_core`, which becomes the dependency root for the existing `etsy_integration` (Spec 001 + 002 + 003 forward) and the future `etsy_channel_api` / `etsy_channel_email` / `gearment_partner` modules per ADR-001 §11. Phase 1 of ADR-003's sequencing (`Phase 1 (start of Spec 003 rewrite)`) explicitly times this module move to coincide with this spec.

## Implementation Phases

> Per spec-kit workflow: Phase 0 = research, Phase 1 = design, Phase 2 = task generation (separately via `/speckit-tasks`).

### Phase 0 — Research (output: research.md)

Resolve open questions:
- R1: Does the team have separate VN and US warehouses requiring `stock.location` per warehouse, or is this logical-only? (Master-plan open question Q9)
- R2: Default seed pipeline naming — exact 17 stage names + colours + transitions, locked from SRS §6
- R3: Auto-failover semantics for design-file delivery (ADR-009 §4 vs ADR-012 GDrive failure)
- R4: Inline-edit ACL — should MP see destination fields as read-only with a hint, or completely hidden?
- R5: Performance budget — 80 rows × N tracked fields × tracking=True overhead. Acceptable for `_compute_has_pending_address_change` to be `store=True` + `compute_sudo=True`?

### Phase 1 — Design (output: data-model.md, quickstart.md, optional contracts/)

- Full ER diagram + per-model field tables for the 9 new models above + the 3 extended models
- Migration strategy: how the historical 17,659 orders get `x_pipeline_id` (NULL per REQ-MIG-07) + `sales_channel='etsy'` (FR-025 backfill)
- Quickstart: 7 verification scenarios (one per User Story) that an installer can run from a fresh module install

### Phase 2 — Tasks (output: tasks.md, generated by `/speckit-tasks`)

Stage 4.3 of the master-plan execution. Tasks ordered: shared fixtures → core models → ACL → views → services → data seed → tests → docs. Each User Story (US1–US7) becomes an independently testable task cluster.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Configurable order pipeline (4 new models) instead of hardcoded enum | Owner red-pen identified that "VN-Packed 1", "[Fix]VN-Dish" semantics are unsettled at code-time; PD lead needs runtime-config power | Hardcoded enum forces a code change every time PD adds a new sub-state, blocks the cutover. Enum-only would also force "Multi-Technique Hybrid" (ADR-010 §9) to be a separate code-level branch, doubling the dashboard code paths. |
| File-lifecycle stack (3 new models: file + route + batch) instead of single `order.design.file` | Pain points #11 (files lost in handover), #12 (PD wastes time searching Discord), #18 (re-upload at every step) require explicit routing semantics + bulk A4 layout | A single `order.design.file` model cannot represent per-recipient delivery state; pain #11/#12/#18 stay open. Splitting at runtime via separate `mail.activity` records would push the routing logic to chatter, defeating audit + permission models. |
| 4-module split (per ADR-001) starting with this spec | Future Amazon/Website channels need to plug into shared core; 10k+ LOC monolith is unmaintainable | Keep monolith → mid-spec-005 refactor would block the API cutover; LATE refactor is strictly worse than EARLY per ADR-003 §Alternatives. |

## Dependencies

| This plan needs | From | When |
|---|---|---|
| Spec 002 normalization complete | Spec 002 (in flight, W3) | Before Phase 1 design data-model migration scripts can be tested |
| `shipping.carrier` seed entries | ADR-005 / this spec | Phase 1 design (this spec owns the seed) |
| `pipeline.team` seed | ADR-010 / this spec | Phase 1 design (this spec owns the seed) |
| Constitution principle re-validation | Master plan §6 + decision log | Done; updates noted above |

| Other deliverables need from this | What |
|---|---|
| Spec 004a (tracking import) | `shipping.carrier` model + Tracking Dashboard view + `sale.order.fulfillment` mixin |
| Spec 004b (Gearment) | Mixin + carrier (`gearment_carrier_name`) + Process Dashboard pipeline |
| Spec 004c (returns) | Chatter scaffolding + dashboards |
| Spec 005 (Etsy API) | `shipping.carrier.etsy_carrier_name` for tracking push; `sales_channel`; `x_pipeline_state_id` (visible on dashboards but not directly written) |
| Spec 010 / 011 (Amazon / Website) | Channel field + delegation mixin reuse |

## Stage-2 implementation: P1-09 GDrive Upload Service & Wizard

**Slice context**: ADR-006 (revised 2026-04-13) made GDrive the primary storage mode for design files (10 MB cap on filestore, GDrive primary URL). P1-02a implemented the model + small/url modes; P1-09 implements the **GDrive upload path** — service-account auth, Drive upload, thumbnail generation, wizard-driven `design.file` creation with `storage_mode='gdrive'`. Unblocks P1-02c (queued retry wrap) and P2-06 (GDrive polling cron).

**Scope**: service layer (`services/gdrive_uploader.py`, `services/design_thumbnail_generator.py`) + TransientModel wizard (`models/design_file_upload_wizard.py`) + view + 4 fields on `design.file` + 1 cache field on `etsy.shop`. No cron; no async; queue_job retry deferred to P1-02c.

### Architecture

**GDrive client** (`services/gdrive_uploader.py`):
- Service-account JSON read from `/opt/odoo/secrets/gdrive-service-account.json` (matches P0-15 credential-path pattern; provisioned by P0-03).
- Scopes: `https://www.googleapis.com/auth/drive.file` (minimum — app-created files only).
- API: `upload_file(file_blob, file_name, folder_id) → {file_id, web_view_link, error}` and `ensure_shop_folder(shop) → folder_id`.
- Folder structure (ADR-006 §6): `Multichannel Hub/Design Files/<shop_code>/<YYYY>/`. Folder-id cached on `etsy.shop.x_gdrive_design_folder_id` (single Drive lookup per shop per year).
- Errors: auth/quota/503 → `{error: str(e), file_id: None}`. **No silent fallback to `storage_mode='small'`** (ADR-012 §3 explicit). Caller raises `ValidationError` with "use URL instead" affordance.
- Retry (P1-09): synchronous try-once + exponential-backoff sleep. Queued retry-with-backoff cron lands in P1-02c.
- Library: `google-api-python-client>=2.80.0` + `google-auth>=2.16.0` pinned in `requirements.txt`.
- Audit: `_logger.debug` per call (file_id, folder_id, result); no PII.

**Thumbnail generator** (`services/design_thumbnail_generator.py`):
- Library: Pillow (`pillow>=9.0.0`) pure-python; no system deps. Wand fallback deferred (see findings P1-09).
- API: `generate_thumbnail(file_blob, max_size_kb=256) → bytes | None`.
- Inputs: TIFF/JPEG/PNG/PSD (PSD via `psd-tools` if Pillow base fails); output JPEG ≤ 256 KB, quality auto-tuned.
- Failure mode: returns `None` (caller stores empty `gdrive_thumbnail`); non-fatal — Drive holds the canonical file.
- Timeout: ≤ 2s wall-clock; abort beyond.

**Upload wizard** (`models/design_file_upload_wizard.py`, TransientModel `design.file.upload.wizard`):
- Fields: `file_blob` Binary, `file_name` Char, `storage_mode` Selection {small, url, gdrive} default `'gdrive'`, `file_url` Char, `gdrive_folder_id` Char, `thumbnail_blob` Binary (computed preview), `order_id` / `order_line_id` Many2one (from context).
- Constraint C-DUW-001: `storage_mode='gdrive'` requires `gdrive_folder_id` non-empty.
- Invocation: button on `sale.order.line` → `ir.actions.act_window target='new'` opens modal; context passes `default_order_line_id` + `default_gdrive_folder_id` (from shop cache).
- Action `action_upload()`:
  - `gdrive` mode → upload via `GdriveUploader` → on success create `design.file(storage_mode='gdrive', gdrive_file_id=..., gdrive_preview_url=..., gdrive_folder_id=..., gdrive_thumbnail=...)` → post chatter on parent order
  - `small` / `url` modes → existing P1-02a paths
  - On Drive failure → `raise ValidationError(_("GDrive upload failed: %s. Try again, or switch to URL mode.", err))`
- ACL: `group_production_team` + `group_system` callable; salesman read-only.

**Sale-order integration**: button "Upload Design File" on `sale.order.line` form (visible to `group_production_team` + `group_system`); opens wizard with pre-cached `gdrive_folder_id`.

**Audit trail**: every upload posts a chatter row on the parent `sale.order` (file_name, storage_mode, gdrive_file_id, by-user). RPC-level FR-017 gate on `action_upload` (per `feedback_fr017_write_defense_in_depth` 4-slice pattern).

### Defense-in-depth (FR-017 pattern)

Per memory `feedback_fr017_write_defense_in_depth.md` and 4 prior slice confirmations (P1-02b last):
- View-level `groups=` is bypassable via XML-RPC.
- Wizard `action_upload()` MUST start with `_check_production_team_or_raise()` (or equivalent inline `has_group()` gate raising `AccessError`).
- Add a regression test (`TestRpcGate`) asserting non-production-team user calling `action_upload()` raises.

### Open decisions for P1-09 (captured in findings.md, owner sign-off welcome but non-blocking)

1. **Thumbnail library**: Pillow (default) vs Wand. Pillow chosen for lighter footprint; Wand deferred fallback if PSD support proves brittle.
2. **GDrive folder scope**: per-shop/year (default, cached on `etsy.shop`) vs per-order (extra Drive calls). Default chosen; per-order requires owner ask.
3. **Library pinning**: `>=` lower-bound (default) vs exact `==` lock. Lower-bound chosen.
4. **Historical backfill to Drive**: deferred indefinitely. Etsy-CDN URLs remain valid for legacy `storage_mode='url'` rows; no automated migration.

### Risks / blockers

- **Service-account JSON path drift**: must match P0-15 pattern (`/opt/odoo/secrets/...`). Mock in RED tests; fail-fast on missing in real run.
- **Pillow large-file behaviour**: 200 MB TIFFs may OOM; thumbnail generator catches + returns None (degraded preview, no slice failure).
- **Folder-cache races under concurrent upload**: rare; acceptable race resolves at next call (Drive `files.list` is read-after-write consistent for service accounts).
- **Drive quota on staging**: mocked tests bypass quota; real runs against staging service account (separate from prod).

---

## Revision History

- **2026-04-06**: v1 plan (single dashboard, archived in `_archive/`)
- **2026-04-13**: Wave B spec.md rewrite landed; plan.md NOT regenerated at the time
- **2026-04-27**: Stage 4.1 plan refresh — integrates ADRs 008a/009/010/012 deltas; configurable pipeline replaces hardcoded enum; design-file lifecycle stack replaces single `order.design.file`; module destination is `multichannel_hub_core` per ADR-003 sequencing
- **2026-04-30**: Added Stage-2 P1-09 section (GDrive upload service + wizard); 4 fields appended to `design.file` (`gdrive_file_id`/`gdrive_preview_url`/`gdrive_folder_id`/`gdrive_thumbnail`) + C-DF-006; tasks T094–T101 added in tasks.md; ADR-006 / ADR-012 audited consistent — no amendments needed.
