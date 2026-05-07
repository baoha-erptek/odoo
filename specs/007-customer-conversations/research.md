# Research — Spec 007 Customer Conversations

**Status**: Phase 0 output. All NEEDS CLARIFICATION resolved.

This research drives **ADR-011** (the lead-model architectural decision) and confirms the OAuth-scope and email-routing paths.

---

## R1 — Lead model: full `crm` dep vs lightweight `multichannel.enquiry`

**Decision**: Lightweight `multichannel.enquiry` model on `multichannel_hub_core`, **no `crm` dep**.

**Rationale**:

- Constitution Principle I ("Odoo-Native First") favors `crm.lead`, but Principle VII ("Simplicity Over Completeness") and the project's actual ACL hygiene push the other way.
- `crm` brings 4 menu groups + 12 record rules + a kanban that the BA team does not need; adoption risk is real (see auto-memory `feedback_channel_agnostic_groups_in_mhc.md` — channel-agnostic groups already live in `mhc`, and adding `crm` would shadow that).
- The enquiry surface we need is a thin wrapper around `mail.thread + mail.activity.mixin`: 9 fields + 4 states + 1 conversion action. Re-implementing 60% of `crm.lead` is ~150 LOC vs the indirect cost of pulling in the full `crm` UI.
- Future need: if marketing-ops genuinely wants pipeline reporting, we add `crm` later and migrate `multichannel.enquiry` records via a small wizard. The reverse (adopt `crm`, then strip it) is much harder.
- Constitution Principle V ("Incremental Migration") supports starting small.

**Alternatives considered**:

1. **Full `crm` dep + `crm.lead` extension**. Pros: built-in pipeline kanban, lead scoring, mail.activity. Cons: heavyweight; adds menus across the system; team training cost; conflicts with `multichannel_hub_core`'s "no Etsy-specific code; channel-agnostic foundations only" rule.
2. **`mail.message` only + a saved filter on the inbox**. Pros: zero new model. Cons: no state machine, no convert-to-quote action, no per-enquiry record rules — operators lose trackability; rejected.
3. **One model handling BOTH `sale.order` chatter AND pre-sale**. Rejected — `sale.order` already inherits `mail.thread`; reusing it for pre-sale would create phantom orders or sentinel rows. The two flows have genuinely different lifecycles.

**Authority**: ADR-011 will codify the decision and reference this research note.

---

## R2 — Etsy OAuth `conversations_r` scope re-submission

**Decision**: Add `conversations_r` to `etsy_oauth.DEFAULT_SCOPES` in the **same commit** that ships `EtsyConversationPoller`. Owner re-submits the Etsy app review with the expanded scope list.

**Rationale**:

- Per Etsy v3 docs (verified via Context7 / vendor docs at session start), `/v3/application/shops/{shop_id}/receipts/{receipt_id}/transactions` works under `transactions_r` (already granted). The receipt-bound message field `message_from_buyer` is in the **receipt object itself** — already captured in `EtsyOrderPayload.buyer_message`. **One-way initial note only**, not a thread.
- Full conversation polling (`/v3/application/shops/{shop_id}/messages/conversations` + `/messages/{conversation_id}/messages`) requires `conversations_r`. Without it, we are stuck with the initial buyer-note + email-fallback path.
- E1v2 (the new submission) is independently trackable; we do NOT block Family C email-fallback (`P1-MSG-EMAIL-FALLBACK`) on it.
- Token storage already exists (`etsy.shop.etsy_oauth_access_token` per P0-14); adding scopes does not require schema change. Existing tokens lose access on rotation; re-issuing tokens after Etsy approval is a documented BA step.

**Alternatives considered**:

1. **Defer scope ask until Family D ships**. Rejected — Etsy review is 3–8 weeks; coupling the ask to D delays C unnecessarily.
2. **Skip API entirely; email-only**. Rejected — long-term, the API is more reliable than regex parsing of "buyer messaged you" emails (Constitution VII tolerates parser fragility but the API path is strictly better when available).

**Authority**: existing ADR-008 (API-first pivot) already authorizes this; we just amend the scope list.

---

## R3 — Email fallback: how to detect "buyer messaged you" notifications

**Decision**: Add a new template handler in `email_parser.py` keyed on Etsy notification subject `Subject: ^Re: New message from `, with body extraction from a fixed wrapper text and a regex for the buyer-name + message body.

**Rationale**:

- `email_parser.py` already handles 2 templates (order-receipt + dedup). Adding a 3rd follows the existing factory pattern (no architectural shift).
- We detect the template via Subject prefix; body extraction follows the same regex pattern (anchor on "From: <name>" + extract the quoted message text).
- Fragile by design (Constitution VII) — on parse failure, raw email retained in `etsy.email.log`; alert routed via `multichannel.sync.health` (same as existing order-email failures).
- Match key for `etsy.message.dedupe` when the email path is the only one: synthesize `etsy_message_id` from `(receipt_id, sender_email, body_sha256[:16])` so re-processing the same email is a no-op. When API path arrives later with the real `etsy_message_id`, we reconcile via `(shop_id, body_sha256_prefix)` collision — documented as a known limitation.

**Alternatives considered**:

1. Use Gmail label-filter to route notifications into a dedicated Odoo mailbox. Rejected — adds an Odoo-side mailbox config that owner has to maintain; the existing Gmail polling cron already pulls everything.
2. Parse the in-email "Reply" link to extract the conversation id. Rejected — Etsy rotates the link tokens; would break on every email-template version bump.

---

## R4 — `mail.alias` configuration for pre-sale enquiries

**Decision**: One `mail.alias` per `etsy.shop` with `alias_model_id` pointing at `multichannel.enquiry`. Default alias name `enquiries_<shop_slug>@<domain>`.

**Rationale**:

- Standard Odoo CE pattern; works with the existing Gmail/IMAP infra.
- Per-shop aliases let multi-shop operators see enquiries scoped to one shop in the existing dashboard filters.
- Threading (FR-006): `mail.alias` natively respects `In-Reply-To` headers and routes follow-up emails to the existing record. No custom code needed.

**Alternatives considered**:

1. One global alias for all shops. Rejected — loses shop-scoping and complicates ACL filters per shop.
2. Use `fetchmail.server` instead of `mail.alias`. Rejected — duplicates Gmail polling that the etsy_integration already runs.

---

## R5 — Reuse `etsy.api.log` for conversation API calls (FR-015)

**Decision**: Reuse. Add `'conversation_sync'` and `'message_send'` values to the existing `source` Selection on `etsy.api.log`.

**Rationale**:

- P0-17 already established `etsy.api.log` as the single audit table for Etsy API I/O. Constitution III ("Data Integrity First") plus auto-memory `project_sql_constraints_drift.md` (canonical patterns) — adding selection values to the existing model is the established pattern.
- PII scrubbing logic on the existing model (P0-17 retrofit) covers buyer name/email; we extend the scrub list with `message_body` (free-text) and `subject`.

**Alternatives considered**: separate `conversation.api.log` model — rejected as drift.

---

## R6 — Inbound message buffering when target order not yet in Odoo

**Decision**: Use `etsy.message.dedupe` itself as the buffer. Add a nullable `pending_target_receipt_id` field; on each order-sync cron pass, sweep buffer rows for matched orders and post deferred chatter.

**Rationale**:

- Avoids a second buffer table.
- 24-hour SLA before alerting (`multichannel.sync.health`) gives enough margin for normal sync lag.
- If a buffered message is older than 7 days and still no order match, mark `state='orphaned'` and alert; do not silently drop (Constitution VII).

**Alternatives considered**: hold messages in `etsy.api.log` payload — rejected; mixing audit + state machine.

---

## R7 — Outbound reply scope (User Story 3, deferred)

**Decision**: Defer; document the `conversations_w` scope as a future ask but do NOT include it in the P1-MSG-SCOPE re-submission. Reasoning: outbound brings policy questions (auto-reply guardrails, content moderation, multi-language) that belong to a separate spec / ADR.

**Rationale**: Phase the asks to Etsy reviewers — `conversations_r` alone is a smaller surface and likelier to approve quickly. Add `conversations_w` after the first read-only scope is live and we have a v2 case for write access.

---

## Resolved unknowns

| ID | Question | Status |
|---|---|---|
| R1 | Lead model architecture | Resolved → `multichannel.enquiry`, ADR-011 |
| R2 | OAuth scope timing | Resolved → re-submission, code change ships with poller |
| R3 | Email-fallback template detection | Resolved → Subject-prefix + regex, fail-safe via `etsy.email.log` |
| R4 | `mail.alias` topology | Resolved → per-shop |
| R5 | API audit log reuse | Resolved → extend `etsy.api.log` |
| R6 | Buffering messages without an order | Resolved → use `etsy.message.dedupe` itself |
| R7 | Outbound scope | Deferred → out of P1-MSG-SCOPE re-submission |
