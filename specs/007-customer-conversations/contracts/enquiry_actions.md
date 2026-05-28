# Contract — `multichannel.enquiry` action methods

**Module**: `multichannel_hub_core`
**File**: `multichannel_hub_core/models/multichannel_enquiry.py` (new)

## `action_qualify(self) -> None`

- Pre: `self.state == 'new'` (else `UserError`).
- Side effects: `state -> qualified`, chatter post `'Qualified by <user>'`, no other field change.
- ACL: `sales_team.group_sale_user`+.

## `action_convert_to_quote(self) -> ir.actions.act_window`

- Pre: `self.state in ('new', 'qualified')`.
- Side effects:
  - Create `sale.order` with `partner_id=self.partner_id`, `state='draft'`, `origin=self.name`.
  - Write `self.converted_order_id`, `self.converted_at=now`, `self.state='converted'`.
  - Chatter post on enquiry: `'Converted to <order ref>'`.
  - Chatter post on order: `'Created from enquiry <enquiry name>'`.
- Returns: `ir.actions.act_window` opening the new `sale.order` form.
- ACL: `sales_team.group_sale_user`+.
- Idempotency: re-invocation when `state='converted'` returns the existing order action without creating a duplicate.

## `action_close(self, reason: str) -> None`

- Pre: `self.state in ('new', 'qualified')`; `reason in {'no_response','not_interested','spam','duplicate','other'}`.
- Side effects: `state='closed'`, `closed_reason=reason`, chatter post.
- Wizard: `multichannel.enquiry.close.wizard` (TransientModel) prompts for `reason` + optional notes.

## `_match_or_create_partner(self) -> res.partner`

Private helper. Logic (mirrors Spec 002 US4 pattern):

1. If `self.partner_id` set → return.
2. Else search `res.partner` by `email_normalized=email_normalize(self.partner_email)`.
3. If found → set `self.partner_id`, return.
4. Else create with `name=parsed-from-email-or-from-message`, `email=self.partner_email`, `is_etsy_customer=True` (channel-agnostic flag from Spec 002).

## `_message_new(self, msg_dict, custom_values=None)` (mail.thread hook)

Override to populate `partner_email`, `subject`, `source='email_alias'`, `state='new'`. Called automatically by `mail.alias` when an inbound email creates a new record. Threading (FR-006) uses Odoo's standard `In-Reply-To` matching — no override needed.
