# Research: Etsy API v3 Channel Integration (with Email as Permanent Failover)

**Feature**: 005-etsy-api-channel | **Date**: 2026-04-27 (Stage 4.2 refresh, supersedes 2026-04-10)

> Refresh notes: §R1, R2, R3, R5 carried forward from 2026-04-10 (still accurate). §R4 (sync mode) **deleted** — superseded by ADR-008a v2 (`active_source`). New §R7–R10 added for source-switching, buyer-message ingestion, module-rename migration, and source-change logging. Deleted-and-not-replaced: anything referring to `etsy.carrier.mapping` (per ADR-005), `sync_mode='dual'` (per ADR-002), `sync_audit_mode` (per ADR-008a v2).

## R1: Etsy OAuth2 with PKCE

**Decision**: Implement OAuth2 Authorization Code Grant with PKCE (SHA-256) per Etsy's mandatory requirement.

**Key details** (unchanged from 2026-04-10):
- Authorization URL: `https://www.etsy.com/oauth/connect`
- Token URL: `https://api.etsy.com/v3/public/oauth/token`
- PKCE: 43-128 char `code_verifier`, `code_challenge = base64url(sha256(code_verifier))`, send `code_challenge_method=S256`
- Access token TTL: 3600 s. Refresh token: 90 days, single-use.
- Required scopes: `transactions_r transactions_w listings_r listings_w shops_r email_r`
- Header: `x-api-key: <app_keystring>` on all calls
- Callback route: `/etsy/api/oauth/callback`. `code_verifier` stored in `ir.config_parameter` keyed by state-nonce.

**Alternatives considered & rejected**: API key only (read-only public data); OAuth2 without PKCE (not supported by Etsy v3).

## R2: Receipt/Order Sync Strategy

**Decision**: Incremental sync via `GET /v3/application/shops/:shop_id/receipts?min_last_modified=<unix_ts>&limit=100` paginated. Forward-only from API connection date — no historical back-sync (clarified 2026-04-10).

**Cron interval**: 5 min per shop (separate from email cron). Status-only update on re-sync (preserve operator data — clarified 2026-04-10).

**Dedup**: by `etsy_order_id` UNIQUE on `sale.order`. Idempotency keyed by `(shop_id, etsy_receipt_id)`.

## R3: Tracking Push to Etsy

**Decision**: `POST /v3/application/shops/:shop_id/receipts/:receipt_id/tracking` with `tracking_code` + `carrier_name`. `carrier_name` is the **Etsy enum value** read from `shipping.carrier.etsy_carrier_name` (per ADR-005). Carriers without a matching enum push with `other` and log a warning to `etsy.api.log`.

**Trigger**: cron-driven (default 5 min) plus on-demand button on the order. Reads from `sale.order.fulfillment.tracking_number` + `shipping_carrier_id` (per ADR-007 delegation sibling).

## R4: ~~Sync mode selection~~ — SUPERSEDED by ADR-008a v2

The 2026-04-10 design (`sync_mode` enum + `sync_audit_mode` Boolean) is replaced by `etsy.shop.active_source` per ADR-008a §2. See §R7 below.

## R5: Rate Limiting and API Resilience

**Decision** (unchanged from 2026-04-10): token-bucket rate limiter at ~10 req/s. Exponential backoff (3 retries) on transient errors. No retry on 4xx (except 429). Honour `X-RateLimit-Limit-Daily` headers; raise warning at 80% quota, error at 95%.

**Implementation**: `services/etsy_api_client.py` wraps `requests` with the limiter + retry + retry-after handler. Shared with the email-channel module via the `multichannel_hub_core/utils/rate_limiter.py` core utility.

## R6: Webhook Receiver (P2)

**Decision** (unchanged from 2026-04-10, scope downgraded to P2 per ADR-002): HMAC-SHA256 verification using `app_shared_secret`. Event types: `order_paid`, `order_shipped`, `order_cancelled`, `order_delivered`. Idempotent processing. Replay/reorder safe.

**Implementation**: extends `multichannel_hub_core/controllers/webhook_base.py`. Periodic API sync (R2) is the safety net; webhooks are a latency optimization, not a correctness dependency.

## R7 (NEW) — Source-switching contract

**Decision**: `etsy.shop.active_source` Selection (`api`/`email`) with health-check-driven auto-failover (3 consecutive failures → switch, severity HIGH alert) and recovery-probe auto-recovery (6 consecutive successes → switch back, unless `auto_recovery=False`). All transitions logged to `etsy.shop.source.change.log` with `reason ∈ ('auto-failover', 'manual', 'recovery-probe', 'scope-revoked')`.

**Rationale**: Per ADR-008a v2 §1-§3. The 3-fail threshold avoids false-positive flapping on transient 5xx; the 6-success recovery threshold avoids fast-bounce flapping when the underlying issue is partially fixed. Both numbers are `ir.config_parameter`-tunable.

**Health-check probe** (per source):
- API: `GET /v3/application/openapi-ping` (returns `{"application": "v3", ...}` 200 OK).
- Email: Gmail label query — healthy if ≥1 message received in last N hours (default 24h, per-shop-tunable) OR last poll executed without exception.

**Recovery probe** (only when in failover): hourly cron probes the original primary source. If 6 consecutive probes succeed → switch back. The failure-counting state lives on `etsy.shop` as `health_check_consecutive_failures` (Integer, reset on success).

**Alternatives considered & rejected**:
- Single threshold (e.g. just 3-fail): rejected — recovery would be fast-bounce; one transient success could flip back into a still-broken source.
- Combine health-check + recovery into one cron at 5min: rejected — recovery needs lower frequency to be patient (an outage that lasts 30 min should not flap; a 6-success @ 1h ≈ 6h of clean operation before flipping back, which is conservative).

## R8 (NEW) — Canonical `etsy.order.payload` schema

**Decision**: an in-memory Python dataclass (NOT an Odoo model — ephemeral, only flows from adapter to ingestor) with the following fields. Both adapters MUST produce records of this shape:

```python
@dataclass(frozen=True)
class EtsyOrderPayload:
    # Source-agnostic fields (REQUIRED from both adapters)
    etsy_shop_id: int                    # Internal etsy_shop.id
    etsy_receipt_id: str                 # Etsy's receipt identifier
    etsy_order_id: str                   # Etsy's order id (often = receipt_id)
    buyer_name: str
    buyer_country: str
    order_date: datetime
    currency: str                        # ISO 4217
    amount_total: float
    shipping_total: float
    line_items: list[EtsyLineItemPayload]
    shipping_address: EtsyAddressPayload
    buyer_message: str | None            # REQ-MSG-01

    # Source-specific (NULLABLE — emit when present, NULL otherwise)
    buyer_email: str | None              # API-only; email parser cannot extract
    listing_id: str | None               # API-only
    payment_status: str | None           # API: explicit; email: inferred
    is_gift: bool | None
    gift_message: str | None

    # Provenance
    source: Literal['api', 'email']
    fetched_at: datetime
    raw_source_id: str                   # API: receipt_id; Email: gmail_message_id
```

**Rationale**: a frozen dataclass enforces immutability (one source emits, ingestor consumes — never mutated). Source-specific nullable fields let downstream code render "—" gracefully when unavailable. The `source` + `raw_source_id` pair lets `EtsyOrderIngestor` write provenance to `sale.order.sync_source` (existing FR-011 field) without inventing a new audit trail.

**Validation**: `EtsyOrderPayload.__post_init__` raises if a required field is missing. Adapters that cannot emit a required field must fail loudly; the ingestor never silently fills defaults.

## R9 (NEW) — `etsy.buyer.message` ingestion (REQ-MSG-01)

**Decision**: a per-receipt row in new model `etsy.buyer.message` when `buyer_message` is non-empty. Ingestion is part of the same API call as receipt sync (R2) — no extra HTTP round-trip. Stored fields: `(shop_id, receipt_id, buyer_name, message, fetched_at, sale_order_id)`. Deduplicated by `(shop_id, receipt_id)` UNIQUE.

**Rationale**: per SRS v2.2 §10 REQ-MSG-01 and the H8/Pain-#17 resolution. Customers' Etsy Conversations content is NOT ingested (scope rejected by Etsy). Instead, `buyer_message` field on the receipt (already in scope under `transactions_r`) is the practical data source. UI: tab on order form + top-level "Customer Message Hub" view (delivered by Spec 003).

**Alternatives considered & rejected**:
- Wait for Conversations scope: still rejected by Etsy; indefinite wait.
- Free-form text scrape from `buyer_message`: same as decision above, just framed differently.

## R10 (NEW) — Module-rename migration `etsy_integration → etsy_channel_email`

**Decision**: pre-migration script renames the existing module record in `ir_module_module`:

```python
# custom_addons/etsy_channel_email/migrations/19.0.1.0.1/pre-migrate.py
def migrate(cr, version):
    cr.execute("UPDATE ir_module_module SET name = 'etsy_channel_email' WHERE name = 'etsy_integration'")
    # XML-ID model rename (xml_id format: <module>.<noupdate_xmlid>)
    cr.execute("UPDATE ir_model_data SET module = 'etsy_channel_email' WHERE module = 'etsy_integration' AND <subset_clause>")
```

**Subset clause**: only XML IDs that genuinely belong to the email-parsing concern. Bits owned by the new core (delegation mixin, carrier model, design.file) MUST stay associated with `multichannel_hub_core`. Bits owned by API (oauth flow, api log) move to `etsy_channel_api`. The script carves up `ir_model_data` by inspecting the `model` field.

**Validation order**: test on staging with a recent prod snapshot before production. Verify that uninstalling `etsy_channel_email` after rename leaves all sale.order data intact (no cascade delete via XML ID severance).

**Alternatives considered & rejected**:
- Keep the old module name. Rejected — semantic mismatch; Owner-signed in ADR-008a §5.
- Wait for the Phase-2 `etsy_channel_migration` separation (per ADR-003 original Phase 3) before renaming. Rejected — the rename affects Phase 1 work; can't be deferred to Phase 2.

## Cross-references

- SRS_EN v2.2 §3 (REQ-SRC-01..04) and §10 (REQ-MSG-01)
- ADR-008a v2 §1–§5 (single pipeline, source-switching, health-check, parser-as-failover, module rename)
- ADR-005 (carrier unification — `shipping.carrier.etsy_carrier_name`)
- ADR-002 (sync_mode 2-value enum, partially superseded — see banner in ADR-002 file)
- spec.md FR-001..FR-035 — all carried forward except the 2026-04-13 sync_mode/sync_audit_mode language (see §R7)
- master plan §6 + decision log D-13 (Owner sign-off on source-switching)
