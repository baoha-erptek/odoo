# Contract — `EtsyConversationPoller` service

**Module**: `etsy_integration`
**File**: `etsy_integration/services/etsy_conversation_poller.py` (new)
**Style**: ORM-free service class; consumes `EtsyApiClient` (P0-15); writes via injected env. Mirrors `EtsyOrderSyncer` (P0-16c) shape.

## Public API

```python
class EtsyConversationPoller:
    def __init__(self, env, client: EtsyApiClient): ...

    def poll_shop(self, shop: 'etsy.shop', since: datetime) -> PollResult:
        """Pull conversations + messages for one shop since cursor.

        Returns count of new messages posted, count buffered, count skipped (dup).
        Side effects:
          - posts mail.message on matching sale.order via message_post()
          - creates multichannel.enquiry rows for non-receipt-bound conversations
          - creates etsy.message.dedupe rows for every observed message
          - writes etsy.api.log row per HTTP call (PII-scrubbed body)
        Raises:
          - PermissionError on 403 (conversations_r missing) — caller skips shop
          - RateLimitError on 3 retried 429 (TokenBucket exhaustion)
        """
```

`PollResult` is a frozen dataclass: `posted: int, buffered: int, skipped: int, errors: list[str]`.

## Wire contract

| Step | Etsy endpoint | Response |
|---|---|---|
| 1. List conversations | `GET /v3/application/shops/{shop_id}/messages/conversations?limit=100&offset=N` | `{"results": [{"conversation_id": ..., "subject": ..., "last_message_tsz": ...}]}` |
| 2. Per conversation, list messages | `GET /v3/application/shops/{shop_id}/messages/conversations/{conversation_id}/messages?limit=50&offset=N` | `{"results": [{"message_id": ..., "from_email": ..., "body": ..., "create_timestamp": ..., "receipt_id": ... or null}]}` |

Cursor: `etsy.shop.etsy_last_conversation_sync_at` (new field, datetime, nullable, indexed). Updated to `max(message.create_timestamp)` after each successful pass. Mirrors `etsy_last_receipt_sync_at` pattern from P0-16c.

## Routing matrix

| Message has `receipt_id`? | Receipt → SO match? | Action |
|---|---|---|
| Yes | Yes | `sale.order.message_post(...)` + `etsy.message.dedupe` `state='posted'`, `target_sale_order_id` set |
| Yes | No (yet) | `etsy.message.dedupe` `state='buffered'`, `pending_target_receipt_id` set |
| No | — | `multichannel.enquiry` create-or-append + `etsy.message.dedupe` `state='posted'`, `target_enquiry_id` set |

Buffer sweep: `_cron_replay_buffered_messages()` runs every 30 min; for each `state='buffered'` row, look up `sale.order.etsy_receipt_id == pending_target_receipt_id`, post chatter, flip to `state='posted'`. Rows older than 7 days flip to `state='orphaned'`.

## Idempotency

Pre-write check on `(etsy_shop_id, etsy_message_id) UNIQUE` — `psycopg2.IntegrityError` on duplicate is caught + counted as `skipped`.

## Rate-limiting + retry

Reuse `TokenBucket(8, 1.0)` from `multichannel_hub_core/utils/rate_limiter.py` (already used by `EtsyApiClient`). 3 retries on 429 with `(1, 2, 4)` backoff capped at `Retry-After` header up to 60s.

## Error handling

- 401 → trigger `etsy_oauth.refresh_access_token`, retry once.
- 403 → log `_logger.warning("conversations_r scope missing on shop %s; falling back to email-only")`; raise `PermissionError`; caller (the cron) marks shop as email-only for the run.
- 5xx → retry (3); after 3 → log + skip shop for this pass; cron retries on next interval.

## Audit log

One `etsy.api.log` row per HTTP call with `source='conversation_sync'` and `body_excerpt` PII-scrubbed (buyer email, name, message body redacted to `<scrubbed:N chars>`).

## Cron

```xml
<record id="cron_etsy_conversation_sync" model="ir.cron">
  <field name="name">Etsy: Sync conversations</field>
  <field name="model_id" ref="etsy_integration.model_etsy_shop"/>
  <field name="state">code</field>
  <field name="code">model._cron_sync_conversations()</field>
  <field name="interval_number">10</field>
  <field name="interval_type">minutes</field>
</record>
```

Same shape as `cron_etsy_order_sync` (P0-16c). Filter: shops with `sync_mode='api_only'` AND `conversations_r in granted_scopes`.
