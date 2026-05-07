# Contract — Email fallback for buyer messages

**Module**: `etsy_integration`
**File extended**: `etsy_integration/services/email_parser.py` (add a 3rd template)
**File extended**: `etsy_integration/services/order_creator.py` (post chatter when matched)

## Detection

Email is a "buyer messaged you" notification iff:

```
Subject ~= /^(Re:\s*)?New message from /  AND
From ~= "Etsy <transaction@etsy.com>"
```

(Same Subject-prefix detection style as the existing order-receipt template.)

## Body extraction

Regex anchored on:

```
From: <buyer_name>
Subject: <conversation_subject>
Receipt #<receipt_id>?    # optional, only when receipt-bound
[blank line]
<message body — until "View this message on Etsy">
```

Extracted fields:

- `buyer_email` (from email envelope `Reply-To` or `From` of the embedded reply link)
- `buyer_name`
- `subject`
- `body`
- `receipt_id` (optional — when present, message is post-sale)

## Routing

Same matrix as `EtsyConversationPoller` (see contracts/etsy_conversation_poller.md §"Routing matrix"):

| Receipt extracted? | SO match? | Action |
|---|---|---|
| Yes | Yes | `sale.order.message_post(...)` + dedupe row `channel='email'` |
| Yes | No (yet) | dedupe row `state='buffered'` |
| No | — | `multichannel.enquiry` create-or-append + dedupe row |

## Synthesizing `etsy_message_id` (research §R3)

```python
synthetic_id = f"email:{receipt_id or 'noreceipt'}:{sha256(body)[:16]}"
```

Stored in `etsy.message.dedupe.etsy_message_id`. When the API path arrives later for the same conversation (real `etsy_message_id`), reconcile via `body_sha256_prefix` collision query — flip the dedupe row to API-authoritative + delete the synthetic row.

## Failure mode

Parse failure → leave email in `etsy.email.log` (existing model from Spec 001) with `parse_status='failed'`. Alert via `multichannel.sync.health` after 3 consecutive failures (existing pattern).
