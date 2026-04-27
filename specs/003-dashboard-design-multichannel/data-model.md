# Data Model: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Phase**: 1 (input → research.md, plan.md; output → tasks.md via /speckit-tasks)
**Date**: 2026-04-27 (Stage 4.1 refresh)
**Module**: `multichannel_hub_core` (per ADR-003 Phase 1 sequencing)
**Supersedes**: `_archive/data-model-2026-04-06.md` (single-dashboard, single `order.design.file` design)

---

## ER Overview

```
                          ┌────────────────────────────────────────────┐
                          │  sale.order  (extended)                    │
                          │  + sales_channel, channel_order_ref        │
                          │  + x_pipeline_id ── M2O ──> order.pipeline │
                          │  + x_pipeline_state_id ─ M2O ─> *.state    │
                          │  + has_pending_address_change (computed)   │
                          └─┬───────────────┬──────────────┬───────────┘
                            │ O2O           │ O2M          │ O2M
                  ┌─────────▼──────┐ ┌──────▼────────┐ ┌──▼──────────┐
                  │ s.o.fulfillment│ │ design.file   │ │ etsy.address│
                  │ ADR-007 delegate│ │ (ADR-009)     │ │ .change.req │
                  │ + production   │ │ + parent_file │ └─────────────┘
                  │   fields       │ │ + version     │
                  │ + carrier M2O  │ │ + state       │
                  └────────────────┘ │ + storage     │
                                     └─┬─────────────┘
                                       │ O2M           ┌──────────────────┐
                                ┌──────▼────────┐      │ design.print.batch│
                                │design.file    │      │ (wizard, ADR-009)│
                                │.route         │      │ + cached_pdf_id  │
                                │ (per recipient)│      └──────────────────┘
                                └───────────────┘

  ┌─────────────────────┐      ┌──────────────────────┐      ┌─────────────────────┐
  │ order.pipeline      │ O2M  │ order.pipeline.state │ O2M  │ pipeline.team       │
  │ ADR-010 §1          │─────▶│ ADR-010 §1           │─────▶│ ADR-010 §6          │
  │ + parent_pipeline_id│      │ + responsible_team_id│      │ (lightweight team)  │
  │ + version           │      │ + next_stage_ids     │      └─────────────────────┘
  │ + transition_policy │      │ + is_initial/term/   │
  └─────────────────────┘      │   term_for_inventory │
                               └──────────────────────┘

                    ┌──────────────────────────────────────────┐
                    │ order.pipeline.transition.log            │
                    │ (single audit table for all pipeline ops)│
                    │ change_type ∈ {struct,rename,reassign,   │
                    │                transition}               │
                    └──────────────────────────────────────────┘

  ┌──────────────────────┐
  │ shipping.carrier     │ ◀─── M2O — sale.order.fulfillment.shipping_carrier_id
  │ ADR-005 unified      │
  │ + etsy_carrier_name  │
  │ + gearment_carrier   │
  └──────────────────────┘
```

---

## 1. `sale.order` (extended)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `sales_channel` | Selection: `etsy`/`amazon`/`website`/`other` | Yes | (per onboarding) | Indexed; backfilled to `etsy` on existing rows (FR-025); `tracking=True` |
| `channel_order_ref` | Char | No | derived | Generic external order ref. For Etsy: backfilled to `etsy_order_id`. Indexed. `tracking=True` |
| `x_pipeline_id` | Many2one(`order.pipeline`) | No | per resolver | Resolved on `_create` via `pipeline_resolver` (product → category → system param). NULL on historical orders (REQ-MIG-07). `ondelete='restrict'` |
| `x_pipeline_state_id` | Many2one(`order.pipeline.state`) | No | initial-state of `x_pipeline_id` | Set on confirm; gated transitions writes via `_write_pipeline_state` helper. `tracking=True`. `domain="[('pipeline_id', '=', x_pipeline_id)]"` |
| `has_pending_address_change` | Boolean | computed | `False` | `store=True`, `compute_sudo=True`, `@api.depends('address_change_request_ids.state')`. Indexed |
| `address_change_request_ids` | One2many(`etsy.address.change.request`, `order_id`) | — | — | Inverse |
| `design_file_ids` | One2many(`design.file`, `order_id`) | — | — | Inverse |
| `fulfillment_id` | One2one — see `sale.order.fulfillment` `_inherits` | — | auto-create | Per ADR-007 |

**Constraints (`@api.constrains`)**:
- C-SO-001: A write to any field in {`partner_shipping_id`, `street`, `street2`, `city`, `zip`, `state_id`, `country_id`} when `has_pending_address_change == True` raises `UserError` with i18n key `error_address_locked`. Bypass: `self.env.context.get('approve_address_change') == True` (set only by `etsy.address.change.request.action_approve`).
- C-SO-002: Pipeline-state writes must respect the policy on `x_pipeline_id.transition_policy` (`dag_strict` / `dag_with_admin_override` / `free_form`). Helper `_write_pipeline_state` performs the check.

**ACL**:
- All extended fields: read for `sales_team_user`; write per existing `sale.order` ACL plus the address-change `@api.constrains`.

**Indexes**: `sales_channel` (single col), `channel_order_ref` (single col), `has_pending_address_change` (single col), `(sales_channel, has_pending_address_change)` (composite for Tracking-Dashboard filter)

---

## 2. `sale.order.fulfillment` (NEW — ADR-007 delegation sibling)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `order_id` | Many2one(`sale.order`, `ondelete='cascade'`) | Yes | (auto on parent create) | The `_inherits = {'sale.order': 'order_id'}` parent link |
| `tracking_number` | Char | No | — | Indexed; `tracking=True` |
| `shipping_carrier_id` | Many2one(`shipping.carrier`) | No | — | M2O replaces the old `shipping_carrier` Char (FR-028); `tracking=True` |
| `shipping_date` | Date | No | — | Set on bulk "Mark shipped"; `tracking=True` |
| `label_status` | Selection: `none`/`requested`/`buying`/`bought`/`failed` | No | `none` | Inline-edit on Tracking Dashboard; `tracking=True` |
| `tracking_state` | Selection: `none`/`label_requested`/`label_ready`/`shipped`/`in_transit`/`delivered`/`returned` | No | `none` | Carrier-webhook write target (FR-008 + REQ-TRK-08). `tracking=True` |
| `mp_note` | Text | No | — | "Marketing note" — separate from `note`; `tracking=True` |
| `pd_note` | Text | No | — | "Production note" — visible on Process Dashboard; `tracking=True` |
| `pic_user_id` | Many2one(`res.users`) | No | — | Person-In-Charge (BA); inline-editable; `tracking=True` |
| `pd_pic_user_id` | Many2one(`res.users`) | No | — | PD's PIC; inline on Process Dashboard; `tracking=True` |
| `order_priority` | Selection: `normal`/`push`/`urgent` | No | `normal` | Drives row decorations (FR-003); `tracking=True` |
| `production_blocked` | Boolean | No | `False` | Drives row decoration; `tracking=True` |
| `block_reason` | Text | No | — | Required when `production_blocked == True` (constraint); `tracking=True` |
| `warehouse_zone` | Selection: `vn`/`us` | No | derived | R1 decision: logical only for now; group-by/filter on Process Dashboard |
| `etsy_ship_notified_at` | Datetime | No | — | Stamped when Spec 005's `EtsyTrackingPusher` returns 200 OK |
| `has_pending_address_change` | Boolean (related) | computed | `_inherits` parent | Read-through for Tracking Dashboard convenience |

**Constraints**:
- C-SOF-001: `block_reason` required when `production_blocked == True`.

**Auto-create**: `_create` on `sale.order` triggers `sale.order.fulfillment.create({'order_id': self.id})` to maintain the 1:1 invariant (ADR-007 mandate).

**ACL**:
- Read: `sales_team_user` + `group_production_team`
- Write: `group_production_team` (production fields), BA group (PIC, priority), MP (mp_note only)

**Indexes**: `tracking_number`, `shipping_carrier_id`, `(warehouse_zone, label_status)`, `pic_user_id`, `pd_pic_user_id`, `order_priority`

---

## 3. `sale.order.line` (extended)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `design_status` | Selection: `none`/`pending`/`approved`/`rejected` | computed | `none` | Roll-up of children `design.file.state`. `store=True`, `@api.depends('design_file_ids.state', 'design_file_ids.route_ids.state')`. **Lowest-of-children**: `rejected < pending < approved`. |
| `design_file_ids` | One2many(`design.file`, `order_line_id`) | — | — | Inverse |

---

## 4. `shipping.carrier` (NEW — ADR-005)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | — | "USPS", "UniUni", "YunExpress", "GKE Local" etc. |
| `code` | Char | Yes | — | Unique. Used by carrier-detection regex matching. |
| `is_active` | Boolean | No | `True` | Tracking lookup filter |
| `tracking_url_template` | Char | No | — | e.g. `https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking}`; safe template substitution |
| `tracking_prefix_regex` | Char | No | — | e.g. `^[0-9]{20,22}$` (USPS), `^UU` (UniUni), `^YT` (YunExpress) — used by Spec 004a's auto-detection |
| `etsy_carrier_name` | Selection (mirrors Etsy carrier enum) | No | — | Maps for Spec 005's `EtsyTrackingPusher` |
| `gearment_carrier_name` | Char | No | — | Free text — Gearment's mapping is loose |
| `notes` | Text | No | — | — |

**Constraints**: `code` unique.

**Seed (FR-029)** — `data/shipping_carrier_seed.xml` ships:

| Code | Name | Etsy enum | Gearment | Regex prefix |
|---|---|---|---|---|
| `usps` | USPS | `usps` | `USPS` | `^9[0-9]{19,21}$` |
| `uniuni` | UniUni | `other` | `UniUni` | `^UU` |
| `yunexpress` | YunExpress | `other` | `YunExpress` | `^YT` |
| `4px` | 4PX | `other` | `4PX` | `^4PX` |
| `dhl_ecom` | DHL eCommerce | `dhl` | `DHL` | `^GM[0-9]+` |
| `fedex_smartpost` | FedEx SmartPost | `fedex` | `FedEx` | `^61[0-9]{18}$` |
| `gke_local` | GKE Local | `other` | `GKE` | `^GKE` |

**ACL**: read all; write `base.group_system`.

---

## 5. `etsy.address.change.request` (NEW — safety-critical)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `order_id` | Many2one(`sale.order`, `ondelete='cascade'`) | Yes | — | |
| `requested_fields` | Json | Yes | — | Array of field names being changed (informational) |
| `new_values` | Json | Yes | — | Object: `{field_name: scalar_value}`. M2O fields stored as `{id, display_name}`. |
| `state` | Selection: `requested`/`approved`/`rejected` | Yes | `requested` | `tracking=True` |
| `reason` | Text | Yes | — | Buyer's reason — required at request time |
| `rejection_reason` | Text | No | — | Required when `state='rejected'` |
| `requested_by` | Many2one(`res.users`) | Yes | `env.user` | Auto |
| `approved_by` | Many2one(`res.users`) | No | — | Set on approve |
| `approved_at` | Datetime | No | — | Set on approve |
| `rejected_at` | Datetime | No | — | Set on reject |

**Inherits**: `mail.thread`, `mail.activity.mixin`.

**Constraints**:
- C-AC-001: Order must NOT be in final state (`shipped`, `done`, `cancel`) at create time. Error: "Order already shipped — create a return/ticket instead." Points to Spec 004c.
- C-AC-002: `state='requested'` is exclusive — only one outstanding request per order; new attempt raises `UserError`.
- C-AC-003: `rejection_reason` required when `state='rejected'`.

**Methods**:
- `action_approve(self)`: applies `new_values` to the related `sale.order` in a single transaction with `context={'approve_address_change': True}` (bypasses C-SO-001). Sets `state='approved'`, `approved_by`, `approved_at`. Closes the BA `mail.activity`. Posts chatter delta on the `sale.order`.
- `action_reject(self)`: requires `rejection_reason`; sets `state='rejected'`. Closes activity. Notifies requester via chatter @mention.

**Activity**: on create, posts `mail.activity` to `group_ba_lead` (or BA-lead-of-shop fallback) with summary `Approve address change for order <ref>`, type "To Do", deadline +24h.

**ACL**:
- Create: `group_marketing_user` + `group_ba_user`
- Read: requester + BA group + Manager
- Write (approve/reject): `group_ba_lead` only
- Delete: `base.group_system` only

---

## 6. `design.file` (NEW — ADR-009 §1, immutable history)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | — | File label |
| `order_id` | Many2one(`sale.order`, `ondelete='cascade'`) | No | — | Either `order_id` OR `order_line_id` set |
| `order_line_id` | Many2one(`sale.order.line`, `ondelete='cascade'`) | No | — | Same |
| `parent_file_id` | Many2one(`design.file`, `ondelete='set null'`) | No | — | Chains revisions; NULL on initial upload + on historical seed |
| `version` | Integer | Yes | `1` | `parent.version + 1` on revision; immutable after create |
| `storage_mode` | Selection: `small`/`url` | Yes | `url` (default for forward) | `small` = filestore Binary; `url` = GDrive primary |
| `design_file` | Binary (`attachment=True`) | No | — | Used only when `storage_mode='small'` |
| `preview_file` | Binary (`attachment=True`) | No | — | Always optional; ≤ 2 MB |
| `file_url` | Char | No | — | Used when `storage_mode='url'` (GDrive shareable URL or Etsy CDN) |
| `file_name` | Char | No | — | Original filename |
| `file_size` | Integer | No | — | Bytes |
| `file_checksum` | Char | No | — | SHA-256 if reachable |
| `state` | Selection: `pending`/`approved`/`rejected` | Yes | `pending` | `tracking=True` |
| `rejection_reason` | Text | No | — | Required when `state='rejected'` |
| `approved_by` | Many2one(`res.users`) | No | — | Set on approve |
| `approved_at` | Datetime | No | — | Set on approve |
| `route_ids` | One2many(`design.file.route`, `design_file_id`) | — | — | Inverse |
| `is_seed` | Boolean | No | `False` | `True` for historical-import rows (REQ-DUY historical seed) |

**Inherits**: `mail.thread`, `mail.activity.mixin`.

**Constraints**:
- C-DF-001: Exactly one of `order_id` or `order_line_id` must be set.
- C-DF-002: `storage_mode='small'` requires `design_file` non-empty AND `file_size <= multichannel_hub.large_file_threshold_bytes` (default 10 MB). Implemented as both an `@api.constrains` AND an `ir.attachment.create` override (defence in depth, FR-019).
- C-DF-003: `storage_mode='url'` requires `file_url` non-empty.
- C-DF-004: A `design.file` record cannot be deleted by non-admin. Use `state='rejected'` to mark superseded; immutable history is preserved.
- C-DF-005: Re-upload pattern: rejected → user uploads new → new `design.file.create` with `parent_file_id=rejected_one.id, version=parent.version+1`. The new record starts in `state='pending'`. Old record remains `rejected`.

**ACL**:
- Read: `sales_team_user` + `group_production_team`
- Write/state-change: `group_production_team`

**Indexes**: `(order_id, state)`, `(order_line_id, state)`, `parent_file_id`

---

## 7. `design.file.route` (NEW — ADR-009 §1+§4, per-recipient delivery state)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `design_file_id` | Many2one(`design.file`, `ondelete='cascade'`) | Yes | — | |
| `recipient_type` | Selection: `mp`/`ba`/`pd`/`partner_gearment`/`partner_other` | Yes | — | |
| `recipient_partner_id` | Many2one(`res.partner`) | No | — | Set when `recipient_type` starts with `partner_` |
| `recipient_user_id` | Many2one(`res.users`) | No | — | Set for internal-recipient routes |
| `delivery_method` | Selection: `gdrive_share`/`gearment_api`/`email_link`/`discord_manual` | Yes | — | |
| `state` | Selection: `pending`/`sent`/`acknowledged`/`failed` | Yes | `pending` | `tracking=True` |
| `created_at` | Datetime | Yes | `now()` | |
| `sent_at` | Datetime | No | — | |
| `acknowledged_at` | Datetime | No | — | |
| `failure_reason` | Text | No | — | Required when `state='failed'` |
| `idempotency_key` | Char | Yes | sha256(`{design_file_id}_{recipient_*}_{delivery_method}`) | Prevents duplicate dispatch |
| `job_uuid` | Char | No | — | The Odoo queue-job UUID for this route's delivery action |

**Inherits**: `mail.thread`.

**Constraints**:
- C-DR-001: Exactly one of `recipient_partner_id` or `recipient_user_id` must be set (matching `recipient_type`).
- C-DR-002: `idempotency_key` unique.
- C-DR-003: `failure_reason` required when `state='failed'`.

**Service**: `services/design_file_router.py` orchestrates queued-job dispatch (`design.file.route.action_dispatch`). On failure, retries via Odoo queue-job's standard backoff. Stuck-route badge logic (R3 decision): badge raised on the order if any route has `state IN ('pending', 'failed') AND create_date < now() - 2h`.

**ACL**: read all; write/state-change `group_production_team` + `base.group_system`.

---

## 8. `design.print.batch` (NEW — ADR-009 §1, PD bulk-download wizard)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | derived | `Batch <YYYY-MM-DD HH:MM>-<user>` |
| `created_by` | Many2one(`res.users`) | Yes | `env.user` | |
| `design_file_ids` | Many2many(`design.file`, `design_print_batch_rel`, `batch_id`, `file_id`) | Yes | (via wizard tick) | Only `state='approved'` files allowed (constraint) |
| `layout` | Selection: `a4_2x2`/`a4_3x3`/`single` | Yes | `a4_2x2` | A4 layout style |
| `cached_pdf_id` | Many2one(`ir.attachment`) | No | — | Generated PDF, kept ≤ 24h |
| `cached_at` | Datetime | No | — | TTL anchor |
| `state` | Selection: `draft`/`generated`/`expired` | Yes | `draft` | |

**Constraints**:
- C-DB-001: All `design_file_ids` must be `state='approved'`.
- C-DB-002: A cron `cron_design_print_batch_expire` flips `state='generated' → 'expired'` and unlinks `cached_pdf_id` after 24h.

**ACL**: `group_production_team` only.

---

## 9. `order.pipeline` (NEW — ADR-010 §1, configurable workflow)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | — | "Vietnam Internal Production" |
| `code` | Char | Yes | — | Unique-by-version. Stable identifier for seeds (`vn_internal_production`). |
| `version` | Integer | Yes | `1` | Auto-version on first-use edit per ADR-010 §5 |
| `parent_pipeline_id` | Many2one(`order.pipeline`, `ondelete='set null'`) | No | — | Chains versions |
| `is_active` | Boolean | No | `True` | Inactive = cannot be assigned to new orders, but in-flight orders continue |
| `transition_policy` | Selection: `dag_strict`/`dag_with_admin_override`/`free_form` | Yes | `dag_with_admin_override` | Per ADR-010 §7 |
| `auto_advance_trigger` | Selection: `none`/`on_payment`/`on_design_approved`/`on_tracking_imported` | Yes | `none` | Per ADR-010 §8 (Phase 2 layer) |
| `state_ids` | One2many(`order.pipeline.state`, `pipeline_id`) | — | — | Inverse |

**Inherits**: `mail.thread`.

**Constraints**:
- C-OP-001: `(code, version)` unique.
- C-OP-002: A pipeline cannot be edited (state add/remove/rename) if any `sale.order` references it AND `parent_pipeline_id` is the new version's parent — instead, the system creates a new pipeline row with `version+1` and reroutes new orders only. Implemented via override on `write` for fields in {`state_ids`, `transition_policy`, `auto_advance_trigger`}: clones to new version automatically (ADR-010 §5).

**Methods**:
- `clone_for_edit(self)`: creates new pipeline with `version=self.version+1`, `parent_pipeline_id=self.id`, deep-copies `state_ids`. Returns the new pipeline.
- `is_in_use(self) -> bool`: helper to determine whether to clone-on-write.

**ACL**: read all; write `base.group_system` (or `group_pipeline_admin` if more granular needed).

---

## 10. `order.pipeline.state` (NEW — ADR-010 §1, per-stage definition)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `pipeline_id` | Many2one(`order.pipeline`, `ondelete='cascade'`) | Yes | — | |
| `name` | Char | Yes | — | Vietnamese label (e.g., "VN-Packed") |
| `code` | Char | Yes | — | Snake_case technical name (e.g., `packed`) |
| `sequence` | Integer | Yes | step 10 | Drives kanban order |
| `color` | Char (hex) | No | `#9E9E9E` | Drives Process Dashboard chip colour |
| `is_initial` | Boolean | No | `False` | Exactly one per pipeline (constraint) |
| `is_terminal` | Boolean | No | `False` | At least one per pipeline (constraint) |
| `is_terminal_for_inventory` | Boolean | No | `False` | Triggers REQ-EXT-05 BoM auto-deduct |
| `responsible_team_id` | Many2one(`pipeline.team`) | No | — | Default team; per-order override on `sale.order.responsible_team_id` |
| `next_stage_ids` | Many2many(`order.pipeline.state`, `pipeline_state_next_rel`, `from_id`, `to_id`) | No | — | DAG edges (subject to `transition_policy`) |
| `mo_state_at_stage` | Selection: `draft`/`confirmed`/`progress`/`done`/`cancel` | No | `draft` | For Process Dashboard MO mirroring |
| `auto_advance_condition` | Char (Python expr, sandboxed) | No | — | Phase 2; evaluated in cron |

**Constraints**:
- C-OPS-001: `(pipeline_id, code)` unique.
- C-OPS-002: Exactly one `is_initial=True` per pipeline.
- C-OPS-003: At least one `is_terminal=True` per pipeline.
- C-OPS-004: `is_terminal_for_inventory` requires `is_terminal=True`.
- C-OPS-005: `next_stage_ids` must all share the same `pipeline_id`.

**Indexes**: `(pipeline_id, sequence)`, `(pipeline_id, is_initial)`, `(pipeline_id, is_terminal)`

---

## 11. `pipeline.team` (NEW — ADR-010 §6, lightweight team)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | — | "VN Production Line 1", "Gearment Liaison", "BA Approval Group" |
| `member_ids` | Many2many(`res.users`) | No | — | |
| `is_active` | Boolean | No | `True` | |
| `description` | Text | No | — | |

**Constraints**: `name` unique.

**Seed**:
- `team_vn_production_line_1` (initial members from PD)
- `team_ba_approval` (BA leads)
- `team_mp_marketing` (MP)
- `team_gearment_liaison` (BA-Gearment subset)

**ACL**: read all; write `group_pipeline_admin`.

---

## 12. `order.pipeline.transition.log` (NEW — ADR-010 §1, single audit table)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `change_type` | Selection: `pipeline_struct`/`stage_rename`/`stage_reassign`/`order_transition`/`pipeline_clone` | Yes | — | |
| `pipeline_id` | Many2one(`order.pipeline`) | No | — | Set for `pipeline_*` and `stage_*` rows |
| `pipeline_state_id` | Many2one(`order.pipeline.state`) | No | — | Set for `stage_*` rows |
| `order_id` | Many2one(`sale.order`) | No | — | Set for `order_transition` rows |
| `from_state_id` | Many2one(`order.pipeline.state`) | No | — | `order_transition` |
| `to_state_id` | Many2one(`order.pipeline.state`) | No | — | `order_transition` |
| `actor_user_id` | Many2one(`res.users`) | Yes | `env.user` | |
| `actor_at` | Datetime | Yes | `now()` | |
| `change_payload` | Json | No | — | Structured before/after values for `pipeline_struct`/`stage_rename` |
| `note` | Text | No | — | Free-form |

**ACL**: read `group_pipeline_admin` + `group_audit_reader`; create via system only; no update/delete.

**Indexes**: `(order_id, actor_at DESC)`, `(pipeline_id, change_type, actor_at DESC)`, `change_type`.

---

## 13. `product.template` (extended)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `x_default_pipeline_id` | Many2one(`order.pipeline`) | No | — | Per-product pipeline (ADR-010 §2) |

`product.category` similarly extended with `x_default_pipeline_id` (one level up the resolver chain).

System parameter: `multichannel_hub.default_pipeline_code` (default `vn_internal_production`).

---

## Migration Strategy

### Forward (new orders)
- `_create` on `sale.order` → `pipeline_resolver.resolve(order_lines)` returns `x_pipeline_id`. Rules:
  1. If all `order_line_ids.product_id.product_tmpl_id.x_default_pipeline_id` are non-null and equal → use that.
  2. Else if `product.category.x_default_pipeline_id` resolves and is unique → use that (chain up the category tree if NULL).
  3. Else look up the system parameter.
  4. If still ambiguous (mixed-pipeline order per ADR-010 §3): pick the first line's resolution and set `sale.order.x_pipeline_mixed_warning=True` for BA UI hint.
- `x_pipeline_state_id` set to `x_pipeline_id.state_ids.filtered(is_initial=True)` on confirm.

### Historical (REQ-MIG-07)
- Spec 002 migration sets `x_pipeline_id=NULL`, `x_pipeline_state_id=NULL` for the 17,659 orders.
- Optional: bulk-assign to a "Historical / archived" pipeline (single terminal stage, NOT terminal-for-inventory). Admin-discretionary.

### Module move (ADR-003 sequencing)
- Phase 1 of decomposition: move all 9 new models + extensions to `multichannel_hub_core`. Existing `etsy_integration` declares dependency on it.
- The `migrate()` hook of `multichannel_hub_core/__init__.py` handles the model-rename for any pre-existing tables (none expected — these are net-new tables).

### Backfill (FR-024 / FR-025)
- One-shot script in `multichannel_hub_core/data/migrations/19.0.1.0.0_post.py`:
  - Set `sales_channel='etsy'` and `channel_order_ref=etsy_order_id` for every `sale.order` where `sales_channel` is NULL. Idempotent.

---

## Cross-Cutting Concerns

### Audit (FR-031)
Every model in this spec inherits `mail.thread` + `mail.activity.mixin`. Every user-visible scalar field (excluding Binary and pure technical counters) sets `tracking=True`.

### i18n (FR-032)
- `i18n/vi_VN.po` ships at module install with 100% coverage of new strings (label, help, error messages, kanban column titles).
- CI gate: `tests/test_i18n_coverage.py` parses the `.py` and `.xml` for `_()` calls, parses `.po` for translations, asserts equality.

### UTF-8 (FR-033)
- All Excel/CSV import/export wizards explicitly set `encoding='utf-8-sig'` (BOM-tolerant for Windows Excel).
- A diacritic round-trip fixture in tests: import "Đĩa tim mới" → write to product → export → re-read → assert equality.

---

## Cross-references

- spec.md FR-001..FR-033 (all covered)
- SRS_EN v2.2 §5 (Order), §6 (Tracking), §7 (Process), §8 (approval), §10 (file lifecycle), §10.5 (configurable pipeline)
- ADR-005 (carrier model), ADR-006 (storage policy), ADR-007 (delegation), ADR-009 (file lifecycle), ADR-010 (configurable pipeline), ADR-012 (GDrive failover)
- research.md R1–R5 — design decisions encoded above
