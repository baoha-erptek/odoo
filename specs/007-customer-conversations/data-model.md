# Data Model — Spec 007 Customer Conversations

**Status**: Phase 1 output.

Three models touched: `multichannel.enquiry` (NEW), `etsy.message.dedupe` (NEW), `sale.order` (existing — chatter only, no schema change).

---

## §1 `multichannel.enquiry` (new model)

**Module**: `multichannel_hub_core` (channel-agnostic per project memory `feedback_channel_agnostic_groups_in_mhc.md`).
**Inherits**: `mail.thread`, `mail.activity.mixin`
**Description**: "Customer enquiry — pre-sale conversation not yet tied to an order."

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `name` | Char | required, computed `_compute_name` | e.g. "Enquiry from <email> · 2026-05-06" |
| `partner_id` | Many2one(`res.partner`) | ondelete='restrict' | Resolved by email match; created if missing |
| `partner_email` | Char | indexed | Authoritative when `partner_id` is null |
| `subject` | Char | | Email Subject or first line of Etsy message |
| `source` | Selection | required, indexed | `('etsy_api', 'email_alias', 'manual')` |
| `etsy_shop_id` | Many2one(`etsy.shop`) | ondelete='restrict', indexed | Required when `source='etsy_api'` |
| `etsy_conversation_id` | Char | indexed | Etsy conversation ID; UNIQUE with `etsy_shop_id` when set |
| `state` | Selection | required, default `new`, tracking=True | `('new', 'qualified', 'converted', 'closed')` |
| `assigned_user_id` | Many2one(`res.users`) | ondelete='set null' | Default = alias `alias_user_id` for email; rule TBD for API |
| `converted_order_id` | Many2one(`sale.order`) | ondelete='set null' | Set on `state='converted'` |
| `converted_at` | Datetime | readonly | Stamped when state goes `converted` |
| `closed_reason` | Selection | | `('no_response', 'not_interested', 'spam', 'duplicate', 'other')` |
| `notes` | Text | | BA-only internal notes; not shown to buyer |
| `active` | Boolean | default=True | For archive |

### State transitions

```
new --qualify--> qualified --convert--> converted (terminal)
new --close--> closed (terminal, requires closed_reason)
qualified --close--> closed
```

Backwards transitions disallowed (mirror P1-DESIGN-MULTI-AUTO-ARCHIVE pattern).

### Indexes (declarative + `init()` mirror per `project_sql_constraints_drift.md`)

- `idx_mhe_partner_email_state` on `(partner_email, state)`
- `idx_mhe_etsy_conv` on `(etsy_shop_id, etsy_conversation_id)` UNIQUE WHERE `etsy_conversation_id IS NOT NULL`

### ACL

| Group | Read | Write | Create | Unlink |
|---|---|---|---|---|
| `sales_team.group_sale_user` | Y | Y | Y | N |
| `multichannel_hub_core.group_ba_lead` | Y | Y | Y | Y |
| `sales_team.group_sale_manager` | Y | Y | Y | Y |

### Methods

- `action_qualify()` — flips `new → qualified`
- `action_convert_to_quote()` — creates `sale.order` draft, links via `converted_order_id`, flips state, posts chatter audit row
- `action_close(reason)` — terminal, `closed_reason` required
- `_match_or_create_partner()` — private helper; reuses Spec 002 US4 dedup pattern (`is_etsy_customer=True` flag)

---

## §2 `etsy.message.dedupe` (new model)

**Module**: `etsy_integration`
**Inherits**: none (no chatter — high-volume audit table per `etsy.api.log` precedent)
**Description**: "First-seen ledger for Etsy buyer messages across API + email channels."

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `etsy_shop_id` | Many2one(`etsy.shop`) | required, ondelete='cascade', indexed | |
| `etsy_message_id` | Char | required, indexed | Real ID from API; synthesized for email-only path (see research §R3) |
| `body_sha256_prefix` | Char(16) | indexed | First 16 hex chars of SHA-256(body) — collision reconcile when API arrives after email |
| `channel` | Selection | required | `('api', 'email')` — first channel that posted |
| `posted_at` | Datetime | required | UTC; matches the `mail.message.date` stamped on the order chatter |
| `target_sale_order_id` | Many2one(`sale.order`) | ondelete='set null' | Null when message arrived before its order |
| `target_enquiry_id` | Many2one(`multichannel.enquiry`) | ondelete='set null' | Null when post-sale |
| `pending_target_receipt_id` | Char | indexed | Set when API-pull found no matching order yet (research §R6) |
| `state` | Selection | required, default `posted` | `('posted', 'buffered', 'orphaned')` |
| `payload_excerpt` | Char(256) | | First 256 chars only — full body lives in chatter, not here |

### Constraints

- UNIQUE `(etsy_shop_id, etsy_message_id)` — primary dedup key
- C-EMD-001 `target_sale_order_id` XOR `target_enquiry_id` XOR `pending_target_receipt_id` (exactly one populated when `state='posted'`; only `pending_target_receipt_id` populated when `state='buffered'`)

### Indexes

- `idx_emd_pending` on `(etsy_shop_id, pending_target_receipt_id)` WHERE `state='buffered'` — partial; sweep cron predicate

### ACL

| Group | Read | Write | Create | Unlink |
|---|---|---|---|---|
| `etsy_integration.group_etsy_api_log_reader` | Y | N | N | N |
| `base.group_system` | Y | Y | Y | Y (retention cron) |

Created via `sudo()` from poller services (justified inline — same pattern as `etsy.api.log` writes).

### Retention

7-day cron deletes `state='posted'` rows older than 30 days; keeps `state='orphaned'` indefinitely for audit until BA closes the upstream issue.

---

## §3 `sale.order` chatter (existing model — no schema change)

`sale.order` already inherits `mail.thread`. New behavior:

- Inbound buyer messages posted via `order.message_post(body=..., subtype_xmlid='mail.mt_comment', author_id=..., date=..., email_from=...)`.
- `mail.message.message_type='comment'` (default).
- `mail.message` author resolved to buyer `res.partner` (matched / created via Spec 002 US4 helper).
- No new fields on `sale.order`. The existing `etsy_note_from_buyer` (initial-note one-way capture from P0-16b1) is left unchanged — it represents the snapshot of `message_from_buyer` at receipt time, not a conversation.

Out-of-band: the Operations Dashboard (P1-DASH-MERGE) gains a new optional column `message_unread_count` in a future slice; tracked under Spec 003, not here.

---

## §4 `mail.alias` configuration (existing model — data only)

For each `etsy.shop`:

```xml
<record id="mail_alias_enquiry_<shop_id>" model="mail.alias">
  <field name="alias_name">enquiries_<shop_slug></field>
  <field name="alias_model_id" ref="model_multichannel_enquiry"/>
  <field name="alias_defaults" eval="{'source': 'email_alias', 'etsy_shop_id': <shop_id>}"/>
  <field name="alias_contact">everyone</field>
</record>
```

Created at shop-onboarding time via a small `etsy.shop.action_provision_enquiry_alias()` action — no Spec-007 model owns this.

---

## §5 ER summary

```
res.partner ─┐
             │
             ├─< multichannel.enquiry ─── converted_order_id ──> sale.order
             │      ↑                                            │
             │      │                                            │
etsy.shop ──┘  alias_user_id                                    │
                                                                 │
etsy.message.dedupe ─── target_sale_order_id ───────────────────┘
                    └── target_enquiry_id ─> multichannel.enquiry
                    └── pending_target_receipt_id (buffered)
```
