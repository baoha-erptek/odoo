# Data Model: Etsy API v3 Channel Integration (with Email as Permanent Failover)

**Phase**: 1 (input → research.md, plan.md; output → tasks.md via /speckit-tasks)
**Date**: 2026-04-27 (Stage 4.2 refresh; supersedes 2026-04-10 single-channel-monolith design)
**Modules**: `etsy_channel_api` (NEW) and `etsy_channel_email` (RENAMED from email-parser portion of `etsy_integration`) per ADR-008a §5 + ADR-001 §11

> **Removed from the 2026-04-10 design** per Stage-2 ADRs:
> - `etsy.carrier.mapping` model — superseded by `shipping.carrier.etsy_carrier_name` (ADR-005)
> - `sync_mode` enum on `etsy.shop` — superseded by `active_source` (ADR-008a §2)
> - `sync_audit_mode` Boolean on `etsy.shop` — removed (ADR-008a §2; canonical payload makes audit-mode redundant)
> - "Phase 3 deletion" lifecycle on `etsy_channel_legacy` — module is now `etsy_channel_email` (peer, NOT legacy) per ADR-008a §5

---

## Entity Overview

| Entity | Disposition | Module | Description |
|---|---|---|---|
| `etsy.shop` | Extended | `etsy_channel_api` | Add API tokens, `active_source`, `auto_recovery`, source-change tracking fields |
| `etsy.shop.source.change.log` | NEW | `etsy_channel_api` | Append-only audit of every source switch (auto-failover, manual, recovery-probe, scope-revoked) |
| `etsy.api.log` | NEW | `etsy_channel_api` | Per-call audit (request, response, status, duration) |
| `etsy.buyer.message` | NEW | `etsy_channel_api` | REQ-MSG-01 — buyer_message ingestion per receipt |
| `etsy.webhook.event` | NEW (P2) | `etsy_channel_api` | Webhook event log with HMAC verification status |
| `sale.order` | Extended (read) | `etsy_channel_api` | Adds `sync_source` (existing FR-011) — uses fields already added by Spec 003 (`channel_order_ref`) and Spec 002 (`etsy_order_id`) |
| `product.template` | Extended | `etsy_channel_api` | Adds `etsy_listing_id`, `etsy_listing_state` (P2 listing management) |
| `shipping.carrier` | Extended (read) | `etsy_channel_api` | Reads `etsy_carrier_name` already added by Spec 003 / ADR-005 |
| `etsy.email.log` | EXISTING | `etsy_channel_email` | Migrated unchanged from `etsy_integration` |
| Email-parser models | EXISTING | `etsy_channel_email` | `email_parser`, `gmail_client`, OAuth flow — migrated unchanged |
| `etsy.order.payload` | NEW (in-memory) | shared | Frozen Python dataclass — NOT a DB model. The contract between adapters and `EtsyOrderIngestor`. See research.md R8. |

---

## 1. `etsy.shop` (extended — `etsy_channel_api`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `etsy_numeric_shop_id` | Char | No | — | Indexed; resolved from API user profile after OAuth |
| `etsy_api_key` | Char | No | — | `groups='base.group_system'`; application keystring |
| `etsy_shared_secret` | Char | No | — | `groups='base.group_system'`; webhook HMAC |
| `etsy_access_token` | Char | No | — | `groups='base.group_system'`; refreshed automatically |
| `etsy_access_token_expires_at` | Datetime | No | — | TTL: 1 hour |
| `etsy_refresh_token` | Char | No | — | `groups='base.group_system'`; 90-day TTL, single-use |
| `etsy_refresh_token_expires_at` | Datetime | No | — | Alert at -7 days |
| `etsy_token_scopes` | Char | No | — | Granted scopes (csv) |
| `etsy_last_receipt_sync_at` | Datetime | No | — | Incremental-sync checkpoint (`min_last_modified` cursor) |
| **`active_source`** | Selection: `api`/`email` | Yes | `email` (existing shops) / `api` (new shops post scope-grant) | **REQ-SRC-02 / ADR-008a §2**. `tracking=True` |
| **`active_source_changed_at`** | Datetime | No | (set on every change) | `tracking=True` |
| **`auto_recovery`** | Boolean | Yes | `True` | When `False`, recovery-probe never auto-switches back. ADR-008a §3. `tracking=True` |
| **`health_check_consecutive_failures`** | Integer | No | `0` | Reset to 0 on success. Counter for 3-fail threshold. NOT tracked (frequent updates). |
| **`recovery_probe_consecutive_successes`** | Integer | No | `0` | Reset to 0 on failure. Counter for 6-success threshold. NOT tracked. |
| `etsy_buyer_message_last_sync_at` | Datetime | No | — | REQ-MSG-01 cursor — usually equals `etsy_last_receipt_sync_at` (ingestion is bundled) |

**Constraints**:
- C-ESY-001: When `active_source='api'`, the OAuth tokens must be present at create-time (validation on transition). When `active_source='email'`, OAuth tokens may be absent.
- C-ESY-002: Manually toggling `active_source` from UI requires `base.group_system` AND records a row in `etsy.shop.source.change.log` with `reason='manual'`.

**Removed fields** (per ADR-008a v2):
- `sync_mode` (Selection email_only/api_only) — replaced by `active_source`
- `sync_audit_mode` (Boolean) — removed entirely

**Migration script** (in `etsy_channel_api/migrations/19.0.1.0.0_post.py`):
```python
def migrate(cr, version):
    cr.execute("""
        UPDATE etsy_shop SET active_source = CASE
            WHEN sync_mode = 'api_only' THEN 'api'
            WHEN sync_mode = 'email_only' THEN 'email'
            ELSE 'email'
        END
        WHERE active_source IS NULL
    """)
```

---

## 2. `etsy.shop.source.change.log` (NEW — `etsy_channel_api`, ADR-008a §3)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `shop_id` | Many2one(`etsy.shop`, `ondelete='cascade'`) | Yes | — | Indexed |
| `from_source` | Selection: `api`/`email`/`null` | No | — | `null` for the very first row per shop |
| `to_source` | Selection: `api`/`email` | Yes | — | |
| `changed_at` | Datetime | Yes | `now()` | Indexed |
| `reason` | Selection: `auto-failover`/`manual`/`recovery-probe`/`scope-revoked`/`bootstrap` | Yes | — | |
| `actor_user_id` | Many2one(`res.users`) | No | — | NULL for cron-driven changes |
| `health_check_failures_at_change` | Integer | No | — | Snapshot of `health_check_consecutive_failures` at the moment of change |
| `notes` | Text | No | — | Free-form |

**Constraints**:
- C-SCL-001: Rows are append-only (no `unlink` permitted except `base.group_system`).
- C-SCL-002: For `reason='auto-failover'` and `'recovery-probe'`, `actor_user_id` MUST be NULL.

**ACL**: read `group_audit_reader` + Manager; create via system or manual UI; no update.

**Indexes**: `(shop_id, changed_at DESC)`, `(reason, changed_at DESC)` for analytics queries (`auto_failover_count_7d` health tile).

---

## 3. `etsy.api.log` (NEW — `etsy_channel_api`)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `shop_id` | Many2one(`etsy.shop`, `ondelete='cascade'`) | Yes | — | |
| `endpoint` | Char | Yes | — | e.g. `GET /v3/application/shops/:shop_id/receipts` |
| `http_status` | Integer | No | — | NULL on connection failures |
| `request_started_at` | Datetime | Yes | `now()` | |
| `duration_ms` | Integer | No | — | |
| `request_payload_summary` | Text | No | — | Body summary; `Authorization` header scrubbed |
| `response_summary` | Text | No | — | Body summary (truncated to 4 KB) |
| `error_message` | Text | No | — | Exception/error details |
| `quota_used_today` | Integer | No | — | From `X-RateLimit-Limit-Daily` header |
| `quota_remaining_today` | Integer | No | — | |
| `source` | Selection: `audit`/`sync`/`tracking_push`/`webhook_register`/`listing_push`/`listing_pull`/`buyer_message_sync`/`health_check` | Yes | — | For filter/group. `audit` added P0-17 (was missing pre-2026-04-28 — see findings 2026-04-26 architect Q4 conflict resolution). |

**Retention**: cron-driven cleanup of rows >30 days (`ir.config_parameter`-tunable). Implements FR-035.

**ACL**: read `base.group_system` + a new `etsy_api_log_reader` group.

**Indexes**: `(shop_id, request_started_at DESC)`, `(source, request_started_at DESC)`, `http_status` (for alerting on 5xx spikes).

---

## 4. `etsy.buyer.message` (NEW — `etsy_channel_api`, REQ-MSG-01)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `shop_id` | Many2one(`etsy.shop`, `ondelete='cascade'`) | Yes | — | |
| `etsy_receipt_id` | Char | Yes | — | Indexed |
| `sale_order_id` | Many2one(`sale.order`, `ondelete='set null'`) | No | — | Linked once the receipt becomes a sale order; NULL while receipt is pending ingestion |
| `buyer_name` | Char | Yes | — | |
| `buyer_email` | Char | No | — | API-only |
| `message` | Text | Yes | — | Raw `buyer_message` field from Etsy receipt |
| `fetched_at` | Datetime | Yes | `now()` | |
| `is_read` | Boolean | No | `False` | Set when MP/BA opens the message in the Customer Message Hub |
| `read_by_user_id` | Many2one(`res.users`) | No | — | |
| `read_at` | Datetime | No | — | |

**Constraints**:
- C-BM-001: `(shop_id, etsy_receipt_id)` UNIQUE — prevents duplicate ingestion.
- C-BM-002: `message` non-empty (we don't store empty buyer_messages).

**ACL**: read MP + BA + Owner per SRS v2.2 §10 REQ-MSG-01. Write `base.group_system` only (system creates; users only mark-as-read).

**Indexes**: `(shop_id, fetched_at DESC)` for hub view; `etsy_receipt_id` (search); `is_read` (filter).

---

## 5. `etsy.webhook.event` (NEW — `etsy_channel_api`, P2)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `shop_id` | Many2one(`etsy.shop`, `ondelete='cascade'`) | Yes | — | |
| `event_type` | Selection: `order_paid`/`order_shipped`/`order_cancelled`/`order_delivered` | Yes | — | |
| `etsy_event_id` | Char | Yes | — | Etsy's event identifier — UNIQUE for idempotency |
| `payload_raw` | Text | Yes | — | Raw JSON body |
| `signature_status` | Selection: `valid`/`invalid`/`missing` | Yes | — | |
| `received_at` | Datetime | Yes | `now()` | |
| `processed_at` | Datetime | No | — | Set on success |
| `process_error` | Text | No | — | If processing failed |
| `sale_order_id` | Many2one(`sale.order`) | No | — | Set after the order is created/updated |

**Constraints**: `etsy_event_id` unique (idempotency).

**Indexes**: `(shop_id, received_at DESC)`, `(signature_status, received_at DESC)`, `etsy_event_id`.

---

## 6. `sale.order` (extended — already has fields from Spec 002 + 003; this spec adds)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `sync_source` | Selection: `email`/`api`/`webhook` | No | — | FR-011 — diagnostic; written by `EtsyOrderIngestor` from canonical payload's `source` field |
| `etsy_last_modified` | Datetime | No | — | From the receipt's `last_modified_tsz` — used for incremental sync cursor |
| `etsy_tracking_push_status` | Selection: `none`/`pending`/`pushed`/`failed` | No | `none` | FR-016 — set by `EtsyTrackingPusher` |
| `etsy_tracking_push_at` | Datetime | No | — | |
| `etsy_tracking_push_error` | Text | No | — | |

> Existing fields used: `etsy_order_id` (Spec 001), `etsy_shop_id` (Spec 001), `sales_channel` (Spec 003), `channel_order_ref` (Spec 003).

**Indexes** (composite, for sync workload): `(etsy_shop_id, etsy_last_modified DESC)` per Tech-architect recommendation in MASTER_PLAN.md §4.

---

## 7. `product.template` (extended — `etsy_channel_api`, P2 listing management)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `etsy_listing_id` | Char | No | — | Indexed; UNIQUE-but-nullable for products that have an Etsy listing |
| `etsy_listing_state` | Selection: `draft`/`active`/`inactive`/`sold_out`/`expired` | No | — | FR-033 |
| `etsy_listing_url` | Char (computed) | computed | — | Built from `etsy_listing_id` |
| `etsy_last_listing_sync_at` | Datetime | No | — | Cursor for incremental listing pull |

**Constraints**: `etsy_listing_id` unique-when-non-null.

---

## 8. `shipping.carrier` (extended — read-only from this spec)

This model is owned by `multichannel_hub_core` (delivered by Spec 003 per ADR-005). `etsy_channel_api` only **reads** the `etsy_carrier_name` field for tracking-push (FR-014) — it does not extend this model.

The seed in Spec 003 (`shipping_carrier_seed.xml`) covers USPS / UniUni / YunExpress / 4PX / DHL eCommerce / FedEx SmartPost / GKE Local with their `etsy_carrier_name` mappings.

---

## 9. `etsy.order.payload` — Canonical contract dataclass (NOT a DB model)

Lives in `multichannel_hub_core/services/etsy_order_payload.py` (shared), imported by both adapters and the ingestor. See research.md §R8 for the schema.

```python
# multichannel_hub_core/services/etsy_order_payload.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass(frozen=True)
class EtsyAddressPayload:
    name: str
    street_1: str
    street_2: str | None
    city: str
    state: str | None
    zip: str
    country_code: str

@dataclass(frozen=True)
class EtsyLineItemPayload:
    listing_id: str | None
    transaction_id: str
    title: str
    sku: str | None
    quantity: int
    unit_price: float
    variations: dict[str, str] = field(default_factory=dict)
    personalisation: str | None = None

@dataclass(frozen=True)
class EtsyOrderPayload:
    etsy_shop_id: int
    etsy_receipt_id: str
    etsy_order_id: str
    buyer_name: str
    buyer_country: str
    order_date: datetime
    currency: str
    amount_total: float
    shipping_total: float
    line_items: list[EtsyLineItemPayload]
    shipping_address: EtsyAddressPayload
    buyer_message: str | None
    buyer_email: str | None
    listing_id: str | None
    payment_status: str | None
    is_gift: bool | None
    gift_message: str | None
    source: Literal['api', 'email']
    fetched_at: datetime
    raw_source_id: str
```

**Adapter contract** (`multichannel_hub_core/services/etsy_channel_adapter.py`):
```python
class EtsyChannelAdapter(Protocol):
    def fetch_new_orders(self, shop_id: int, since: datetime) -> Iterator[EtsyOrderPayload]: ...
    def health_check(self, shop_id: int) -> HealthStatus: ...

class HealthStatus(Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
```

`EtsyApiAdapter` and `EtsyEmailAdapter` both implement this protocol. The ingestor (`multichannel_hub_core/services/etsy_order_ingestor.py`) reads from `shop.active_source`-selected adapter and writes the canonical payload to `sale.order` via existing `OrderCreator` service.

---

## Migration Strategy

### Module split (one-shot, Phase 0 → Phase 1 transition)
1. Create `etsy_channel_api` (new module). Install fresh.
2. Pre-migrate `etsy_integration` → `etsy_channel_email`:
   - Update `ir_module_module.name`
   - Move email-only XML IDs in `ir_model_data` (selectively, per research.md §R10)
   - Update `__manifest__.py` `name` and `depends`
3. Verify both modules install cleanly + tests pass on staging before production.

### Field migration on `etsy.shop`
- Add `active_source`, `auto_recovery`, counters as new columns. Default `active_source` from existing `sync_mode` per the migration script in §1.
- Drop `sync_mode` and `sync_audit_mode` in a follow-up migration revision (after one full verification cycle).

### Bootstrap source-change log
- Insert a `bootstrap` row in `etsy.shop.source.change.log` for every existing shop with `from_source=null`, `to_source=<derived from sync_mode>`, `reason='bootstrap'`.

### Buyer-message backfill
- NOT done (forward-only per FR-007 clarification). Existing historical orders without `buyer_message` show no message; the field arrives prospectively starting from API connection date.

---

## Cross-Cutting Concerns

### Audit (per project rule)
- `etsy.shop`, `etsy.shop.source.change.log`, `etsy.buyer.message`, `etsy.webhook.event` all inherit `mail.thread`. Tracked fields per the table above.
- `etsy.api.log` does NOT inherit `mail.thread` (high-volume; chatter would balloon).

### i18n
- `i18n/vi_VN.po` ships with 100% string coverage at module install. CI gate per Spec 003's `test_i18n_coverage`.

### Testing
- VCR cassettes stored under `tests/fixtures/vcr_cassettes/` — recorded against owner's dev shop with `transactions_r/w`, `listings_r/w`, `shops_r`, `email_r` scopes granted.
- Two-Phase Testing per project rule:
  - Phase-1 (DB): verify row counts in `etsy_shop_source_change_log` after each test transition; verify `(shop_id, etsy_receipt_id)` UNIQUE on `etsy.buyer.message`.
  - Phase-2 (ORM unit): verify `EtsyApiClient.refresh_token`, `EtsyHealthChecker.evaluate_threshold`, `EtsyRecoveryProber.evaluate_threshold`, HMAC verification, canonical-payload parity between adapters.

---

## Cross-references

- spec.md FR-001..FR-035 (carried forward minus the deleted concerns above)
- SRS_EN v2.2 §3 (REQ-SRC-01..04), §10 (REQ-MSG-01), §11 (module map)
- ADR-008a v2 §1–§5; ADR-005 (carrier); ADR-001 §11 (module destination)
- research.md §R7–R10 (source-switching, canonical payload, buyer-message ingestion, module-rename migration)
