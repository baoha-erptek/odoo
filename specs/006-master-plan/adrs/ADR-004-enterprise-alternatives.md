# ADR-004: Enterprise Alternatives — Custom Minimal Implementations

- **Status**: Proposed (awaiting owner sign-off)
- **Date**: 2026-04-10
- **Deciders**: Owner, architect, BA lead
- **Affects**: Spec 003 (design file + approval), Spec 004c (ticket system), future inventory and documents work
- **Related**: [MASTER_PLAN.md §3](../MASTER_PLAN.md), [ba-consultant.md §3](../agent-reports/ba-consultant.md), [devils-advocate.md §7](../agent-reports/devils-advocate.md)

## Context

Several features requested by end users and drafted in the specs implicitly assume Odoo modules that **are NOT available in Odoo 19 Community Edition**:

| Requested feature | Assumed module | CE availability |
|---|---|---|
| Ticket system for replace/refund (BA #7) | `helpdesk` | **Enterprise only** |
| Design file management with approval workflow | `documents` | **Enterprise only** |
| Generic address-change approval workflow | `approvals` | CE has basic version, Enterprise version is richer and better wired into other models |
| Google Drive document sync | `documents_google_drive` | **Enterprise only** |
| Field service / production scheduling | `planning`, `field_service` | **Enterprise only** |
| Marketing automation | `marketing_automation` | **Enterprise only** |

The project has committed to Odoo 19 **CE only** (per CLAUDE.md constraints and the `odoo19_esty` workspace design). Buying Enterprise is not on the table for cost reasons.

The devil's advocate review flagged this as a **redesign risk**: if specs ship with the assumption that these modules exist, the first engineer to open `__manifest__.py` discovers the dependency and has to rewrite the feature. Better to decide now.

The BA consultant review identified that **~70% of the requested "Enterprise" features can be built as minimal custom models on Odoo CE primitives** (`mail.thread`, `mail.activity`, `ir.attachment`, `mail.tracking.value`, etc.) with modest effort.

## Decision

For each Enterprise-only capability assumed by the specs, commit to a **custom minimal implementation** on top of Odoo CE primitives. Do NOT buy Enterprise. Do NOT block on OCA modules of uncertain quality (evaluate case-by-case only if a specific OCA module is actively maintained and has >100 stars).

### 1. Replace/Refund Ticket System (BA #7)

**Do not** use `helpdesk`.

**Build**: a new `etsy.order.ticket` model with:
- Many2one to `sale.order`
- `ticket_type` Selection (`replace`, `refund`, `address_change_request`, `complaint`, `other`)
- `state` Selection (`draft`, `pending_ba`, `approved`, `rejected`, `closed`)
- `request_reason` Text, `resolution_note` Text
- `replacement_order_id` Many2one self-reference for replacement orders
- `requested_by` Many2one `res.users`, `approved_by` Many2one `res.users`
- Inherits `mail.thread` + `mail.activity.mixin` for chatter, approval activities, and audit trail

Form view with state buttons (`Submit for BA Review`, `Approve`, `Reject`, `Close`). Kanban view grouped by state. One2many on `sale.order` form for a "Tickets" tab. Reference UX: Dreamship's per-order ticket page.

**Estimate**: 1 model (100 LOC) + 1 form view + 1 kanban view + 1 one2many panel on sale.order = 2–3 days.

Lives in: `multichannel_hub_core` (per [ADR-003](ADR-003-module-decomposition.md)) since the ticket concept is channel-agnostic.

### 2. Design File Management with Approval Workflow (Spec 003)

**Do not** use `documents`.

**Build**: already in Spec 003's plan. `order.design.file` model stores design files as `ir.attachment` records with explicit `res_model='sale.order'` + `res_id` so they appear in the standard chatter attachments panel. Approval workflow is a 3-state Selection (`pending`, `approved`, `needs_rework`) with kanban grouping and `mail.activity` for the approval prompt.

**Existing Spec 003 wording is fine.** This ADR just formalizes the "do not assume `documents`" constraint.

Lives in: `multichannel_hub_core`.

### 3. Address-Change Approval Workflow (BA #9)

**Do not** use CE `approvals` (too generic, awkward to wire to `sale.order`).

**Build**: new `etsy.address.change.request` model with:
- Many2one to `sale.order`
- `requested_fields` JSON or structured fields (partner_shipping_id, street, street2, city, zip, state_id, country_id)
- `new_values` JSON (what the MP wants to change to)
- `state` Selection (`requested`, `approved`, `rejected`)
- `requested_by`, `approved_by`, `rejection_reason`
- Inherits `mail.thread` + `mail.activity.mixin`

On `sale.order`, add a **computed lock**: if any open `etsy.address.change.request` exists with state `requested`, shipping-address fields are read-only in the UI (`attrs={'readonly': [('has_pending_address_request', '=', True)]}`). When the request is approved, the write to `sale.order` happens from the request form (not from the order form) and then the request transitions to `approved`.

Critical integration: when the Tracking Dashboard queries orders for label purchase, it must filter out orders with pending address change requests to prevent the duplicate-label-buy bug BA explicitly warned about.

**Estimate**: 1 model (80 LOC) + 1 form view + `sale.order` computed field + domain filter on Tracking Dashboard = 3 days.

Lives in: `multichannel_hub_core`.

### 4. Google Drive Document Sync (Spec 004 US9)

**Do not** build. **Deferred entirely** per master plan §3.

The master plan downgrades this from P3 to P4. Tracking files can be manually uploaded via the wizard (Spec 004a). If the ops team complains after 3 months of manual uploads, revisit. Use `google-api-python-client` as a last resort, **not** `documents_google_drive`.

### 5. Approval Workflow (Generic)

**Do not** use CE `approvals` as the primary mechanism.

`mail.activity` is sufficient for all identified approval use cases (address change, design file, ticket). It provides: assignee, due date, type, summary, chatter integration, and user notification. The activity mixin works on any model that inherits `mail.thread`.

For explicit state machines (where the state must persist past the activity completion), combine `mail.activity` (for the "notify the approver" side) with a Selection field (for the durable state).

### 6. Audit Log (BA #8)

**Do not** build custom audit tables.

`mail.thread` + `tracking=True` on tracked fields is the Odoo-native audit log. It produces `mail.tracking.value` records showing old/new values per change, with user and timestamp, displayed in the chatter tab of every record. Free. Declare it as an explicit functional requirement in Spec 003 so reviewers enforce `tracking=True` on every new field.

### 7. Stock Barcode Scan Sheet (BA #15)

**Verify**: `stock_barcode` is available in Odoo 19 CE (was historically CE-contributed). If yes, use it. If no, build a minimal `/scan` HTTP controller with a QWeb template and JS barcode event listener.

**Action item**: Phase 0 task — confirm `stock_barcode` module availability in the project's `addons/` directory.

### 8. Raw Material Forecasting (PD feedback)

**Do not** build parallel forecasting engine.

Reuse Odoo 19 CE's native forecasted inventory reports: `stock.forecasted.product.product`, `stock.warehouse.orderpoint` (reordering rules). See [ADR-007 context](ADR-007-fulfillment-delegation-mixin.md) and master plan §4 Phase 5.

## Consequences

### Positive
- **Zero license cost** — stays within CE.
- **All features remain on the roadmap**: nothing is dropped because of licensing.
- **Minimal custom code** — the alternatives above total ~500–700 LOC of new model/view code across the whole project.
- **Upgradable**: if the owner later decides to buy Enterprise, the custom models coexist fine with `helpdesk`/`documents`/`approvals` (they are namespaced).
- **Better fit**: the custom models are tailored exactly to the print-on-demand workflow rather than being retrofitted from generic Enterprise tools.

### Negative
- **Maintenance burden**: the custom ticket, address-change, and design-file models must be maintained by this team. No upstream bug fixes from Odoo.
- **Missing polish**: Enterprise `helpdesk` has SLA tracking, KPIs, customer portal, email-in ticket creation — none of which the custom `etsy.order.ticket` will have (nor are they asked for).
- **Documentation gap**: engineers joining the project will look for `helpdesk` in the Odoo docs and not find the custom equivalent. Mitigate with a "custom modules reference" doc in each spec.

### Neutral
- The commitment to CE was already made. This ADR just makes it explicit.

## Alternatives considered

1. **Buy Odoo Enterprise** (~$7–25/user/month) — rejected. Project budget constraint.
2. **Use OCA modules** (`helpdesk_mgmt`, `dms`, etc.) — case-by-case only. Most CE-oriented OCA modules in this space have inconsistent maintenance and don't match the Odoo core conventions. Revisit if a specific well-maintained OCA module solves a concrete pain point (e.g. OCA `queue_job` for background tasks is excellent, but that's a different use case).
3. **Build richer custom "helpdesk-lite" clone** with SLAs and portal — rejected. YAGNI; the team needs replace/refund tickets, not a full helpdesk.
4. **Defer all Enterprise-assuming features** — rejected. BA request #7 (tickets) and #9 (address approval) are safety-critical and already in the MVP.

## Implementation notes

- Each custom model above should land in `multichannel_hub_core` per [ADR-003](ADR-003-module-decomposition.md).
- Each should inherit `mail.thread` and `mail.activity.mixin` by default.
- Each should have `tracking=True` on all significant fields.
- Add a "Custom Enterprise Alternatives" section to each spec's `plan.md` that cites this ADR.
- Confirm `stock_barcode` CE availability as a Phase 0 task (part of the Gearment spike week).
