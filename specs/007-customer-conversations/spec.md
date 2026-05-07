# Feature Specification: Customer Conversations (Pre-Sale & Post-Sale)

**Feature Branch**: `007-customer-conversations`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "Spec 007 covers two related but distinct customer-message flows for the multichannel hub: (1) pre-sale enquiries — buyers contacting the shop before placing an order via Etsy messaging or direct email — and (2) post-sale conversation messages on existing orders. Source channels: Etsy API (preferred, requires `conversations_r` OAuth scope) and email parser (fallback today). Reference plan: `/home/odoo/.claude/plans/check-claude-plans-006-master-plan-track-glistening-kernighan.md` Family D."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Post-sale conversation thread on existing order (Priority: P1)

A BA / customer-service operator opens an order that has chatter messages from the buyer (e.g., "Please ship to a different address", "When will my order arrive?"). All messages are visible in the standard `sale.order` chatter, with the buyer identified, and the operator can reply in-thread.

**Why this priority**: Address-change requests, shipping enquiries, and personalisation questions are an existing operational pain — operators currently switch between Etsy seller dashboard, Gmail, and Odoo. Surfacing the conversation on the order eliminates the context-switch and produces an audit trail tied to the order. Email-fallback path can ship without external dependency on Etsy scope approval.

**Independent Test**: Send a buyer message via Etsy seller account against a known test order; within 10 minutes the message appears as a chatter entry on the matching `sale.order` with author = buyer partner. Operator reply via Odoo chatter persists locally (sending the reply back to Etsy is **out of scope for v1** — see SC-005).

**Acceptance Scenarios**:

1. **Given** a `sale.order` with `etsy_receipt_id=12345` exists, **When** the Etsy API returns a new message on conversation tied to receipt 12345, **Then** a `mail.message` is posted on that order with body=message text, subtype=`mail.mt_comment`, author=buyer's `res.partner` (matched by email/name).
2. **Given** the same order, **When** the buyer's "you have a new message" email arrives in the seller's Gmail inbox and the API path is unavailable (E1v2 not yet approved), **Then** the email-fallback parser posts the same chatter entry with `author_id` resolved to the buyer partner and the email body sanitized.
3. **Given** API and email channels both deliver the same message (overlap risk), **When** ingestion runs, **Then** only one chatter entry is created (deduplicated by `(shop_id, etsy_message_id)`).
4. **Given** an order has 5 buyer messages, **When** an operator opens the order form, **Then** all 5 are visible in chatter sorted oldest→newest with the original timestamps preserved.

---

### User Story 2 — Pre-sale enquiry routing to a CRM-style record (Priority: P2)

A prospect contacts the shop via Etsy "contact seller" or via direct email asking about a product before any order exists. The message creates a record (Lead/Opportunity OR `multichannel.enquiry`, decision in ADR-011) with the buyer's question, contact details, and a way for sales staff to reply, qualify, and convert to a quote.

**Why this priority**: Lower volume than post-sale messages and gated on an architectural decision (full `crm` dep vs lightweight model). Can ship after P1.

**Independent Test**: Send an enquiry email to the configured `mail.alias` address; a new record is created with the message in chatter, assigned to a default sales-ops user, and clicking "Convert to Quote" produces a draft `sale.order` linked to the contact's partner.

**Acceptance Scenarios**:

1. **Given** a `mail.alias` `enquiries@<domain>` is configured to route to the enquiry model, **When** an email arrives at that alias from `buyer@example.com` (no existing order), **Then** an enquiry record is created with `partner_email='buyer@example.com'`, body in chatter, state=`new`, assigned to the alias's default user.
2. **Given** the Etsy API path provides non-receipt-bound conversations (requires `conversations_r`), **When** a new conversation arrives that does NOT match any existing receipt, **Then** an enquiry record is created with `source='etsy_api'` and `etsy_conversation_id` populated.
3. **Given** an enquiry record exists, **When** the operator clicks "Convert to Quote", **Then** a `sale.order` is created in `state='draft'` with `partner_id` linked to the enquiry's partner and the enquiry's `state` flips to `converted` with a back-link to the order.
4. **Given** a prospect emails again on the same thread, **When** the new email arrives, **Then** the message is appended to the existing enquiry's chatter (matched by `In-Reply-To` / `References` headers) and not a new record.

---

### User Story 3 — Operator-initiated reply (Priority: P3)

An operator types a reply in chatter on either a `sale.order` (post-sale) or enquiry record (pre-sale); the reply is delivered back to the buyer via Etsy API or email, depending on the original channel.

**Why this priority**: Outbound replies require write-scopes (`conversations_w` for Etsy API or SMTP-auth for email). Defer until P1+P2 inbound paths are stable and the OAuth scope question is settled.

**Independent Test**: Operator replies via chatter; within 1 minute the buyer receives the message in the same channel the original came in.

**Acceptance Scenarios**:

1. **Given** an operator has `group_sale_user` and posts a chatter message on a `sale.order` with a buyer-message thread, **When** the message is saved, **Then** an outbound API call to Etsy `POST /conversations/{id}/messages` (or SMTP send for email-channel) is queued and the chatter entry is tagged `delivered_to_buyer=True`.
2. **Given** the API call fails with 5xx, **When** the retry cron runs (≤3 attempts with backoff), **Then** the chatter entry is tagged `delivered_to_buyer=False` and a `mail.activity` is raised on the order for manual follow-up.

---

### Edge Cases

- Buyer email cannot be matched to any existing `res.partner` — create the partner with `is_etsy_customer=True` (consistent with Spec 002 US4 dedup pattern) before linking the message.
- Etsy API returns a message tied to a receipt that does **not** exist in Odoo (e.g., not yet ingested) — buffer the message in `etsy.message.dedupe` (or a small inbox table) and replay after the next order-sync cron pass; alert via `multichannel.sync.health` if buffer > 24h.
- Buyer requests an address change inside a chatter message — out of scope for this spec; the existing `etsy.address.change.request` workflow (P1-04) is operator-initiated. We may surface a "Create Address-Change Request" button later as a usability follow-up.
- Email-fallback receives a message in a language other than English/Vietnamese — store raw body; display unchanged; do not auto-translate (out of scope).
- The Etsy `conversations_r` scope is denied — Family C falls back to email-only (no User Story 1 API path); Family D pre-sale via Etsy API is not possible, only via email-alias.
- Operator replies via Odoo chatter when delivery is out of scope (User Story 3 not yet shipped) — message remains internal-only; no surprise dispatch to buyer.

## Requirements *(mandatory)*

### Functional Requirements

**Inbound — Post-sale (User Story 1):**

- **FR-001**: System MUST poll Etsy conversations via the API every 10 minutes when a shop has `conversations_r` scope, and MUST gracefully degrade to email-only when the scope is missing or returns 403.
- **FR-002**: System MUST locate the matching `sale.order` by `etsy_receipt_id` for receipt-bound messages and post the message body to that order's chatter via `message_post(subtype_xmlid='mail.mt_comment')`.
- **FR-003**: System MUST deduplicate messages across API and email channels by a unique `(shop_id, etsy_message_id)` key.
- **FR-004**: System MUST resolve the buyer to an existing `res.partner` (matched by email or by Etsy buyer-id stored on the partner) before posting; if no match, MUST create the partner with `is_etsy_customer=True`.
- **FR-005**: System MUST preserve the original buyer-side timestamp when posting (`message_post(date=...)`) and mark the message with `email_from` = buyer email.

**Inbound — Pre-sale (User Story 2):**

- **FR-006**: System MUST accept inbound emails on a configured `mail.alias` and create a new enquiry record per thread (matched by `In-Reply-To` / `References`) OR append to the existing enquiry when matched.
- **FR-007**: System MUST poll Etsy non-receipt-bound conversations (i.e., conversations whose `conversation_id` does not map to a known receipt) when `conversations_r` is granted, and create enquiry records.
- **FR-008**: Each enquiry record MUST carry `state ∈ {new, qualified, converted, closed}`; default `new`; transitions logged to chatter.
- **FR-009**: Each enquiry record MUST expose a "Convert to Quote" action that creates a `sale.order` in `state='draft'` linked to the enquiry's partner, and flips enquiry `state='converted'` with a back-pointer.
- **FR-010**: System MUST track `source ∈ {etsy_api, email_alias, manual}` on every enquiry record for funnel reporting.

**Outbound — Operator reply (User Story 3, deferred):**

- **FR-011**: When User Story 3 ships, the system MUST queue outbound replies via Etsy API or SMTP (channel-symmetric to inbound) with at-most-once delivery semantics and ≤3 retries on 5xx.

**Cross-cutting:**

- **FR-012**: All conversation models MUST inherit `mail.thread + mail.activity.mixin` so chatter, activities, and audit trail come for free.
- **FR-013**: ACL MUST restrict enquiry create/write to `sales_team.group_sale_user` and above; read for the same. `multichannel_hub_core.group_ba_lead` MAY have full access (decision in ADR-011 alongside model choice).
- **FR-014**: All credentials (Etsy OAuth tokens, mail.alias passwords) MUST live in `ir.config_parameter` or environment, never in code.
- **FR-015**: System MUST log every Etsy API conversation call to `etsy.api.log` (reuse existing model from P0-17) with PII scrubbed; same for outbound replies when User Story 3 lands.

### Key Entities

- **`multichannel.enquiry`** OR **`crm.lead` extension** (decision pending in ADR-011): represents a pre-sale customer conversation not yet tied to an order. Key attributes: `partner_id`, `partner_email`, `subject`, `body` (chatter), `source`, `state`, `etsy_conversation_id`, `etsy_shop_id`, `converted_order_id`.
- **`etsy.message.dedupe`**: small audit table keyed `(shop_id, etsy_message_id)` UNIQUE, recording first-seen timestamp and which channel posted (`api` or `email`). Also used as a buffer for messages whose target order has not yet ingested.
- **`mail.thread` extension on `sale.order`**: no new fields; reuses Odoo's standard chatter for User Story 1 messages.
- **`mail.alias`**: standard Odoo configuration record routing inbound emails to the enquiry model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Within 10 minutes of a buyer sending a message on Etsy, ≥95% of messages tied to a known order appear in `sale.order` chatter (User Story 1 happy path).
- **SC-002**: Zero duplicate chatter entries across API + email overlap over a 7-day soak — measured via `(shop_id, etsy_message_id)` UNIQUE constraint and post-deploy report.
- **SC-003**: Pre-sale enquiry-to-quote conversion completes in ≤3 operator clicks from the enquiry record (User Story 2).
- **SC-004**: Email-fallback path operates standalone with zero dependence on Etsy API scope approval — verified by disabling `conversations_r` in test and observing User Story 1 + 2 still work for email-arrived messages.
- **SC-005**: Outbound reply (User Story 3) success rate ≥98% with ≤3 retries; failed deliveries surface as `mail.activity` within 30 minutes (post-User-Story-3 ship).

## Assumptions

- Odoo CE's `mail.thread` and `mail.alias` are sufficient for chatter + email-routing; no Enterprise-only dependency.
- The current Etsy OAuth flow (P0-14) can have additional scopes appended without breaking existing token storage — needs verification in research.md.
- Buyer partner records are reliably matched via the same email-based dedup that Spec 002 US4 already uses; we do NOT need a separate buyer-id index in v1.
- `etsy.api.log` (P0-17) will be reused for conversation-API audit; no new audit-log model is required.
- Email-fallback "buyer messaged you" notification format from Etsy is a stable enough template for regex parsing — same fragility as existing order-receipt parsing; same mitigation (raw email retained on parse failure, alert via `multichannel.sync.health`).
- Vietnamese UI strings are required; reuse `.po` infrastructure from P1-07.
- Spec 003's CEO-directive unified Operations Dashboard is the eventual home for an "Enquiries" tile; out-of-scope for this spec but must not preclude it.
