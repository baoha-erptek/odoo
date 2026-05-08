# ADR-009: Design-File Lifecycle — `design.file` + `design.file.route` + `design.print.batch`

- **Status**: Accepted
- **Date**: 2026-04-26
- **Sign-off**: 2026-04-26 (owner; recorded via Stage-1 synthesis — Owner accepted recommended design)
- **Deciders**: Owner, architect (synthesis), BA lead, MP lead, PD lead
- **Affects**: Spec 003 (data model US2/US3), SRS REQ-FIL-01..03 (formal contract), `etsy_integration` module (or successor `multichannel_hub_core` per ADR-001)
- **Related**: [ADR-006](ADR-006-design-file-storage.md), [ADR-008a](ADR-008a-email-as-mandatory-backup.md), [ADR-012](ADR-012-gdrive-failover.md), [`../clarifications/spec-005-roi-memo.md`](../clarifications/spec-005-roi-memo.md)

## Context

ADR-006 chose Google Drive as the primary store for design files (10 MB cap on `ir.attachment`; URLs on records). ADR-012 added the failover policy (service account, queue with backoff, Discord as permanent manual escape hatch).

What was missing: the **data model** that ties design files to orders, the **routing mechanism** that delivers a file to MP/BA/PD/Partner without re-uploading, and the **bulk-print wizard** that lets PD render N approved design files into one A4 layout PDF.

E2 §2.2 pain #7 / pain #18 ("Thiết kế & điều hướng tệp phức tạp") and SRS §10 REQ-FIL-01..03 framed the requirements but did not define the schema. This ADR locks the schema and lifecycle.

Per the project's Owner principles (2026-04-26):
> Flexible, cover all known issues, **stay in Odoo internal system, avoid going outside to fetch information**, utilise all resources we have.

The schema below puts design-file metadata inside Odoo even when the file body lives on GDrive — Odoo is the source of truth for who owns the file, who's seen it, and what state it's in. GDrive is a storage backend.

## Decision

### 1. Three new models

#### `design.file`
The file record. One per logical design (a buyer's customised SKU, a merchandiser's mockup, etc.). Body lives on GDrive; Odoo holds metadata.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Human-readable label (e.g., "Order #12345 — buyer's monogram") |
| `sale_order_id` | M2O → `sale.order` | Required — every design file belongs to an order. NULL allowed only for sample/mockup files (see §3 below). |
| `gdrive_url` | Char | Primary storage. Present when GDrive upload succeeded. |
| `gdrive_file_id` | Char | GDrive's stable identifier (separate from URL so URL changes don't orphan the link). |
| `discord_url` | Char | Optional — set only when the file was placed on Discord during a GDrive incident (see ADR-012 §4). |
| `local_attachment_id` | M2O → `ir.attachment` | Optional fallback for files <10 MB that don't need GDrive (e.g., proof images). |
| `state` | Selection | `draft / awaiting_approval / approved / needs_revision / archived` |
| `state_reason` | Text | Required when `state='needs_revision'` (per REQ-FIL-02 audit). |
| `version` | Integer | Auto-incremented on each re-upload. Old versions retained per REQ-DUY-01. |
| `parent_file_id` | M2O → `design.file` | NULL on first upload; points to previous version on re-upload. Enables version history. |
| `created_by_user_id` | M2O → `res.users` | Who uploaded (BA in normal flow). |
| `approved_by_user_id` | M2O → `res.users` | Who approved (MP in normal flow). NULL until state='approved'. |
| `approved_at` | Datetime | When approved. NULL until state='approved'. |
| `route_ids` | O2M → `design.file.route` | The recipients this file was routed to. |
| `checksum` | Char | SHA-256 of the file contents (computed at upload time). Used to detect corruption + dedup repeated uploads. |

ACLs: `etsy_integration.group_designer` create/write own, `group_mp` write `state='approved'/'needs_revision'`, all internal users read.

#### `design.file.route`
Per-recipient delivery tracking. Each `design.file` gets N routes when published; each route is independently tracked for delivery state.

| Field | Type | Notes |
|---|---|---|
| `design_file_id` | M2O → `design.file` | Required parent. |
| `recipient_type` | Selection | `mp / ba / pd / partner_gearment / partner_other` |
| `recipient_user_id` | M2O → `res.users` | Required when `recipient_type` ∈ {mp, ba, pd}. |
| `recipient_partner_id` | M2O → `res.partner` | Required when `recipient_type` ∈ {partner_gearment, partner_other}. |
| `state` | Selection | `pending / sent / acknowledged / failed` |
| `sent_at` | Datetime | When the route was published (e.g., GDrive permission granted, Gearment API call succeeded). |
| `acknowledged_at` | Datetime | When the recipient confirmed visibility (clicked the open link / Gearment webhook returned). NULL if not acknowledged. |
| `failed_reason` | Text | Required when `state='failed'`. |
| `delivery_method` | Selection | `gdrive_share / gearment_api / discord_manual / email_attachment` |

This model is the audit trail: who got what, when. It replaces the email-thread / Discord-message-history pattern that was opaque before.

#### `design.print.batch` (transient wizard)
Bulk A4 layout wizard. PD ticks N approved files → wizard generates one PDF in A4 layout → cached in `ir.attachment` for 24h → downloaded.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Auto-named by date + PD user. |
| `design_file_ids` | M2M → `design.file` | Selected files (only `state='approved'` are selectable). |
| `layout` | Selection | `a4_2x2 / a4_3x3 / a4_4x4 / a4_custom` (default `a4_2x2`). |
| `bleed_mm` | Float | Print bleed in millimeters (default 3 mm). |
| `result_attachment_id` | M2O → `ir.attachment` | The generated PDF. NULL until wizard runs. |
| `cache_valid_until` | Datetime | `result_attachment_id` is reusable until this point (24h). |

PDF generation uses Odoo's standard QWeb-to-PDF pipeline (wkhtmltopdf or successor). Wizard caches the result by hash of `(design_file_ids, layout, bleed_mm)` so repeat runs of the same selection don't re-render.

### 2. Lifecycle states (`design.file.state`)

```
   ┌──────────┐    upload     ┌──────────────────────┐    MP approves    ┌──────────┐
   │  draft   │──────────────▶│  awaiting_approval   │──────────────────▶│ approved │
   └──────────┘               └──────────────────────┘                   └──────────┘
                                          │                                    │
                                          │ MP rejects                         │ BA archives (after fulfilled)
                                          ▼                                    ▼
                                ┌────────────────────┐                ┌──────────┐
                                │  needs_revision    │                │ archived │
                                └────────────────────┘                └──────────┘
                                          │
                                          │ BA re-uploads (creates new version, parent_file_id set)
                                          ▼
                                ┌──────────────────────┐
                                │  awaiting_approval   │  (loops back; new design.file row, version+1)
                                └──────────────────────┘
```

Notes:
- Re-upload creates a **new `design.file` row** (immutable history) with `parent_file_id` pointing to the rejected one. The old row stays in `state='needs_revision'`; it's not edited.
- `archived` is terminal. Applied automatically when the parent `sale.order` reaches a terminal pipeline state (see ADR-010), or manually by BA.
- All transitions audited via `mail.message` on the `design.file` record + the `route_ids` audit trail.

### 3. Sample / mockup files (no `sale_order_id`)

A small minority of design files are not tied to a specific order — they're sample mockups, stock templates, marketing previews. For these:

- `sale_order_id` is NULL.
- `name` is required and descriptive.
- `state` lifecycle is the same.
- `route_ids` may be empty (no specific recipient).

These records can be referenced from `product.template.x_default_design_file_id` for products with stock designs (out of scope for this ADR; relevant to REQ-EXT-08).

### 4. Routing mechanism

When a `design.file` transitions to `state='approved'`, an Odoo automation creates `design.file.route` records per the policy:

| Trigger | Routes created |
|---|---|
| Order routing = "internal production" | MP (visibility), BA (visibility), PD (download required) |
| Order routing = "Gearment POD" | MP (visibility), BA (visibility), Gearment partner (API push required) |
| Order routing = "Other partner" | MP (visibility), BA (visibility), partner contact (email or API per partner record) |

The actual delivery action (granting GDrive permission, calling Gearment API, etc.) runs from a queued job on each route record. Failure is captured in the route's `state='failed'` + `failed_reason`. PD/BA can re-trigger from the UI.

**No silent failures.** If any route is `pending` or `failed` for >2h, the order's process-dashboard row shows a warning badge.

### 5. Storage policy

Per ADR-006 and ADR-012:

- Files >10 MB go to GDrive (mandatory; `ir.attachment` rejects via override).
- Files ≤10 MB may go to `ir.attachment` (faster) but the design-file team standard is "always GDrive for design files" so the choice is automatic at upload time. Wizard outputs (PDF generation) are an exception — they live in `ir.attachment` since they're transient.
- `gdrive_url`, `gdrive_file_id`, and `checksum` are mandatory once a non-Discord upload succeeds.
- Discord uploads (manual escape hatch from ADR-012) populate `discord_url` only; `gdrive_url` stays NULL until a "promote to GDrive" action is taken.

### 6. Backfill of historical files

The 17,659 historical orders being normalized in Spec 002 do not have `design.file` records. Migration policy:

- For each historical order, create a `design.file` with `state='archived'`, `name='Historical order — design unknown'`, all storage URLs NULL, `created_by_user_id=admin`, `version=1`. This satisfies the FK + provides an attachment point for any future reconstruction.
- A separate migration script (post-MVP) can attempt to associate Discord/email-attached design files to historical orders by matching order ID; out of scope for Phase 1.

### 7. Source-agnostic design

Per ADR-008a (single ingestion pipeline, source-switching), the `design.file` model does not care whether the parent `sale.order` was ingested via API or email. The order's `etsy_receipt_id` is the FK; both adapters provide it.

## Consequences

### Positive

- **Design files become first-class Odoo records** with audit trail, version history, ACLs, and search — not opaque GDrive folders / Discord channels.
- **Single upload, multi-route** matches the team's actual workflow and removes the "re-upload to every recipient" friction documented in pain #18.
- **Bulk A4 wizard** addresses pain #12 (PD spending hours arranging files for printing).
- **Audit trail per recipient** (`design.file.route`) lets BA / PD / Owner see exactly who has the file and who hasn't acknowledged, eliminating "did MP receive the proof?" coordination overhead.
- **Versioning via `parent_file_id`** preserves the rejection history without conflating with the approved version. KPI on first-pass approval rate becomes computable.
- **Storage-backend-agnostic** model — if GDrive is replaced by something else later, only the URL fields and the upload action change; the lifecycle, routing, and audit trail are unaffected.

### Negative

- **One more model family** to maintain (3 new models + 1 wizard). Reasonable given the pain points but adds onboarding cost for new developers.
- **Route automation depends on Q&A with order-routing classification** (internal vs Gearment vs Other) — this is determined by the order's pipeline assignment (see ADR-010); if a product's pipeline is mis-configured, route policy may be wrong.
- **PDF wizard timeout risk** — wkhtmltopdf hangs on large batches. Mitigation: cap batch size (default 50 files), wizard runs as queued job for batches >20.
- **Backfill creates 17K placeholder rows** that never carry real data. Mitigation: index on `state='archived'` excluded from default search filters; placeholder rows are invisible in normal use.

### Neutral

- ACL/group definitions follow the existing `etsy_integration` security file pattern.
- `mail.message` on `design.file` is free chatter (Odoo standard); no extra audit code needed.
- The 10 MB cap from ADR-006 is enforced at the `ir.attachment` level, not duplicated in `design.file`.

## Alternatives considered

1. **Store files entirely in `ir.attachment` (no GDrive)** — rejected by ADR-006 (10 MB cap; binary bloat in Postgres; backup cost).
2. **No `design.file` model — just put `gdrive_url` on `sale.order` directly** — rejected. Loses version history, multi-recipient routing, and the ability to have multiple files per order (proof + final + revision cycles).
3. **Use Odoo's native `documents` module** — rejected. Documents is Enterprise-only (we're on CE). And its lifecycle model is generic; the per-route audit trail and the bulk-print wizard would still need custom code.
4. **Single `design.file.route` row per file (one recipient)** — rejected. Multi-recipient is the whole point of pain #18 ("upload once, route to many").
5. **Embed file content as base64 in `design.file`** — rejected. Same Postgres-bloat problem ADR-006 identified, plus no shareable URL.
6. **Use file checksums as primary key (content-addressable)** — rejected. Dedup is nice-to-have, but two different orders with coincidentally-identical files should still be tracked separately. `checksum` is for corruption detection, not identity.

## Implementation notes

Spec 003 tasks (added to its `tasks.md` after this ADR + ADR-010 land):

- Models: `design.file`, `design.file.route`, `design.print.batch` (wizard) — `models/design_file.py`, `models/design_file_route.py`, `wizards/design_print_batch.py`
- Constraint: `_check_required_storage` ensures `gdrive_url` OR `local_attachment_id` OR `discord_url` is set when `state != 'draft'`
- Computed field: `sale.order.x_design_file_count`, `sale.order.x_design_files_pending_count` (for dashboard badge)
- View: form, list, kanban for `design.file` (kanban grouped by `state`)
- Action: "Generate A4 Layout" on Process Dashboard (multi-select → opens `design.print.batch` wizard)
- Queued job: `design.file.route` delivery (Gearment API push, GDrive share, etc.)
- Cron: warning-badge updater (route `pending`/`failed` >2h)
- Migration: backfill 17K archived placeholders (run once after Spec 002 normalization)
- Tests:
  - Phase 1 (DB): every `design.file` has at least one URL when state != draft
  - Phase 1 (DB): every `design.file.route` has either `recipient_user_id` or `recipient_partner_id`
  - Phase 2 (ORM): create file → route auto-creates per policy → mock GDrive success → state='sent' → ack via UI → state='acknowledged'
  - Phase 2 (ORM): re-upload after rejection creates new `design.file` row with `parent_file_id` set, version+1
  - Phase 2 (ORM): bulk wizard caches PDF for 24h; second invocation with same selection does not re-render

Operational follow-through:

- Define the route-policy table per pipeline routing in admin UI (links to ADR-010 §6 — pipeline-stage resource assignment determines who gets routed)
- Update operations runbook with "design-file stuck in pending route — what to check" page

## Amendment — Sibling-archive on approval (P1-DESIGN-MULTI-DOC, 2026-05-08)

**Context**: P1-DESIGN-MULTI-UPLOAD (landed 2026-05-08, commit `cd5b58fe75d`) made the upload wizard accept N files in one run, so a single `sale.order.line` (or order, when line is null) can now have multiple `design.file` rows in the `pending` state at the same time. P1-DESIGN-AUTO-ARCHIVE (next slice in family) introduces an `active=fields.Boolean(default=True, tracking=True)` flag and the auto-archive rule below to keep the kanban readable.

**Rule** (binding for P1-DESIGN-AUTO-ARCHIVE):

When a `design.file` row's `state` writes to `'approved'`, the system sweeps **sibling rows** on the same `order_line_id` (or the same `order_id` when `order_line_id` is NULL) and writes `active=False` on every sibling whose `state != 'approved'`. The newly-approved row keeps `active=True`. The `state` field itself is NOT touched — sibling rows in `pending` stay `pending` (audit-trail preserved), they just leave the default-search visible set.

**Why a separate `active` flag rather than transitioning state to a hypothetical `archived`**: Odoo's standard `active=False` semantics are well-understood by every kanban / list / search view (default domain `[('active','=',True)]` already filters). A new `state='archived'` would require updating every view's domain and would conflict with the simplified 3-state machine (`pending / approved / rejected`) that P1-02a MVP locked in. The 5-state machine sketched in §2 of this ADR was not implemented; the amendment recognises the simplification.

**Migration / one-time backfill**: existing `state='rejected'` rows from before this rule lands are kept `active=True` to preserve operator visibility into past rejections. Only future `state='approved'` writes trigger sibling sweep. (Effectively: no retroactive archival.)

**Interaction with `design.file.route`**: no-op. Routes are dispatched only for `design.file` rows with `state='approved'` (see `sale.order._after_confirm_routing` filter `lambda f: f.state == 'approved'`). Non-approved siblings have no `route_ids` to begin with; archiving them via `active=False` doesn't strand any route. The approved file (which keeps `active=True`) keeps its routes intact.

**Tests required** (P1-DESIGN-AUTO-ARCHIVE Phase 2 ORM):
- 3 files uploaded → approve middle one → other two `active=False`, middle stays `active=True`.
- Approved file's `route_ids` untouched after the sibling sweep.
- Existing `state='rejected'` row from a fixture before any approval stays `active=True` until a sibling approval triggers it (then it flips because rejected != approved).
- Sibling scope: line-level files only sweep among the same `order_line_id`; order-level files (line is null) sweep among the same `order_id`.

**Out of scope for this amendment**: re-introducing the 5-state machine. If the operator workflow ever needs `awaiting_approval` / `needs_revision` distinct from `pending`, file a separate ADR-009 successor.

## Revision history

- **2026-04-26**: Initial authoring. Accepted same day with Owner-recommended design (flexible, internal-Odoo, leverages GDrive primary + Discord/local fallback per ADR-006/012).
- **2026-05-08**: Amendment — sibling-archive-on-approve rule (`active=False` on non-approved siblings) added to support multi-file uploads from P1-DESIGN-MULTI-UPLOAD. Doc-only change in P1-DESIGN-MULTI-DOC slice; behaviour lands in P1-DESIGN-AUTO-ARCHIVE.
