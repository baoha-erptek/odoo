# Technical Architecture Report — odoo19_esty Multichannel Hub

**Lens**: Data model coherence, module/service boundaries, performance, integration patterns, testing, technical debt
**Date**: 2026-04-10
**Scope**: Specs 001–005 + shipped `etsy_integration` module

---

## 1. Data model coherence across 001–005

### Full model inventory
- **001 (shipped)**: new `etsy.shop`, `etsy.email.log`; extensions on `sale.order`, `sale.order.line`, `product.product`, `res.partner`, `res.config.settings`
- **002**: new `etsy.data.migration.wizard` (transient); extends `res.users` (`etsy_shop_ids` M2M)
- **003**: new `order.design.file`; extends `sale.order`, `sale.order.line`
- **004**: 7 new — `fulfillment.partner`, `partner.sync.log`, `order.return`, `shipping.carrier`, `logistics.partner`, `tracking.import.log`, `tracking.import.line`
- **005**: 3 new — `etsy.api.log`, `etsy.webhook.event`, `etsy.carrier.mapping`; extends `etsy.shop`, `product.template`

**Total**: 13 new models + 6 model extensions. Realistic for the domain.

### Conflicts, overlaps, missing FKs

**CONFLICT-1: Carrier identity split three ways.**
- `sale.order.shipping_carrier` (Char) — Spec 003
- `shipping.carrier` (model) — Spec 004
- `etsy.carrier.mapping` (system_name -> etsy_name) — Spec 005
- `tracking.import.line.carrier_id -> shipping.carrier` — Spec 004

**Fix**: Promote `sale.order.shipping_carrier` to `Many2one('shipping.carrier')`. Merge `etsy.carrier.mapping` into `shipping.carrier.etsy_carrier_name` field. Net: 3 places -> 1.

**CONFLICT-2: `product.product` vs `product.template` extensions.**
Spec 001 extends product.product (`etsy_image_url`, `is_etsy_product`). Spec 005 extends product.template (`etsy_listing_id`, `etsy_listing_state`). Etsy listing IS a template. **Fix**: Move 001's fields from product.product to product.template in Spec 002's data fix.

**CONFLICT-3: Replacement order lineage.** `order.return.replacement_order_id` vs `sale.order.original_order_id` vs `sale.order.is_replacement_order`. **Fix**: Single source of truth on `sale.order.original_order_id`; compute the rest.

**MISSING FK-1**: `etsy.webhook.event` / `etsy.api.log` should use `ondelete='restrict'` or `'set null'`, not `cascade`. Audit logs must survive their referents.

**MISSING FK-2**: `etsy.api.log` has no `correlation_id` to trace a sync cycle through N API calls. Add.

### Is sale.order becoming a god object?

Yes. Field count by spec:
- 001: 11
- 002: 1
- 003: 9
- 004: 13
- 005: 6
- **Total: 40 new fields**

Standard sale.order already has ~80. Pushing toward 120+ on a single table. Postgres handles it, but form views and code cognitive load suffer.

**Proposal: delegation mixin `sale.order.fulfillment`** (`_inherits={'sale.order': 'order_id'}`) to absorb 13 Spec 004 fields + 6 Spec 003 ops fields. Keep only Etsy identity (001), channel fields (003), and API sync bookkeeping (005) on `sale.order`.

If delegation is too invasive right now, at minimum group into XML view groups and document ownership boundaries before Spec 004 code lands.

### etsy.shop vs sales_channel vs per-channel credentials

Clean for Etsy. Breaks for Amazon. When Amazon lands, you'll want `amazon.marketplace` with its own creds. Pattern: N channels -> N FKs on sale.order.

**Proposal**: Introduce `sales.channel.account` polymorphic reference (via `res_model` + `res_id`). Defer to the Amazon spec, but **flag in Spec 003's data-model.md as a known evolution point.**

### order.design.file vs ir.attachment

Spec 003 uses `Binary` fields — default `attachment=True` since v12, so `ir.attachment` backing is automatic. **Gotcha**: If you want attachments to show in the sale.order chatter panel, create explicit `ir.attachment` records with `res_model='sale.order'` / `res_id=order_id` and reference via M2O. Spec 003 should clarify.

### Pricing audit feature home

Options:
1. **Computed stored fields on sale.order** — simple but rate-of-conversion goes stale
2. **New `sale.order.pricing.audit` model** — snapshot per audit run (recommended for historical reports)
3. **SQL view** (`_auto=False`) — zero storage, always fresh, great for dashboard read model

**Recommendation**: Option 3 for dashboard, Option 2 for historical snapshots. Don't bloat sale.order.

### Raw-material inventory

**Reuse stock module**. Raw materials = `product.template` with `type='product'` in category `Raw Materials`. Consumption via `stock.move` on state transition to "Đã sản xuất". Forecasting via native `stock.forecasted`. Low-stock alerts via `stock.warehouse.orderpoint`.

**Do NOT build a parallel `raw.material` model.** Odoo-Native First principle.

---

## 2. Service/module boundaries

### Module decomposition: split or keep?

Current: `etsy_integration/` ~1,776 LOC. End of Spec 005: ~8-12k LOC, 13 new models, 5-7 services, 2 controllers, 3 wizards, seed XML.

**Recommendation: 4 modules.**

```
multichannel_hub_core         # sale.order channel fields, sales_channel, design.file,
                              # shipping.carrier, carrier detection, order.return,
                              # fulfillment_status state machine, Dashboard views
                              # depends: sale_management, stock, contacts, mail

multichannel_hub_fulfillment  # fulfillment.partner, partner.sync.log, logistics.partner,
                              # tracking.import.*, partner_sync adapters + Gearment,
                              # GDrive client, webhook controller
                              # depends: multichannel_hub_core

etsy_channel                  # renamed etsy_integration — etsy.shop, etsy.email.log,
                              # etsy.api.log, etsy.webhook.event, product.template Etsy fields,
                              # email_parser, gmail_client, etsy_api_client, syncers,
                              # OAuth2 flow, webhook controller
                              # depends: multichannel_hub_core, multichannel_hub_fulfillment

etsy_channel_migration        # one-shot, uninstallable post-cutover
                              # import_orders_wizard, data_migration_wizard, product_categorizer
                              # depends: etsy_channel
```

Migration module uninstallable post-cutover so one-shot wizards don't ship forever.

### Services layer scaling

- Keep ORM-free / ORM-aware split explicit. Name files `email_parser.py` (no ORM) vs `order_creator_service.py` (ORM). Enforce in code review — no ORM imports in ORM-free files.
- Adopt the **Protocol** pattern for service contracts (already matches Spec 004's adapter pattern).
- ORM-free services tested with **plain pytest**. ORM-aware with `TransactionCase`.

### Etsy API client as adapter?

Different direction from partner sync adapter — **do not force into same protocol**. But extract shared concerns (token mgmt, rate limiting, HMAC verification, HTTP retry) as utilities.

---

## 3. Performance at scale

### Dataset facts
- 17,659 orders today; ~3K/month growth = 50K-60K by end of 2026
- Dashboard target: <3s

### Dashboard pagination
Spec 003's 80/page is fine. Bottleneck will be **computed non-stored fields** on tree (`design_file_count`, `has_pending_designs`, `has_active_return`). At 80 rows × 5 subqueries = 400 extra queries.

**Fix**: Store `has_pending_designs` / `has_active_return` as `store=True` booleans (small, indexable). Keep counters unstored and form-only.

### Indexing strategy

**Must have `index=True`**:
- `sale.order.etsy_order_id` (have) — dedup
- `sale.order.line.etsy_transaction_id` (have) — dedup
- `sale.order.sales_channel` (have) — filter
- `sale.order.fulfillment_status` (have) — filter
- `sale.order.tracking_number` — **missing, add**
- `sale.order.fulfillment_partner_id` (have)
- `sale.order.etsy_sync_source` (have)
- `etsy.api.log.endpoint` (have)
- `etsy.webhook.event.etsy_receipt_id` (have)

**Composite indexes**:
- `(etsy_shop_id, etsy_last_modified DESC)` for incremental sync
- `(sales_channel, fulfillment_status)` for multi-tab dashboard

### Batch operations pattern

Spec 002 correctly uses `env.cr.savepoint()` per batch of 100.

**Spec 005 bulk receipt sync**: same batching per Etsy API page of 25-100. If any receipt fails, rollback the batch, log, let next incremental sync retry (idempotent via `etsy_order_id` UNIQUE).

### Shared rate limiter

**Extract to `multichannel_hub_core/utils/rate_limiter.py`.** Token bucket parameterized by `(capacity, refill_per_second)`. Gearment `(100, 10)`, Etsy `(8, 8)`. One class, testable in isolation with fake clock.

For cross-run persistence, use `ir.config_parameter` or a tiny `res.lock` model.

---

## 4. Integration patterns

### Dual-mode sync (email/API/dual) — over-engineered

Dual mode is a trap. Email + API arriving for the same order produces partial data + brittle dedup.

**Recommendation**: Only two modes: `email_only` (legacy) and `api_only` (new). One-way switch per shop. The 90-day email parser is deprecated after first successful API sync.

If overlap is needed during cutover, run email in **audit mode**: parse email, compare against API-sourced order, log differences, do NOT write. 1-week validation tool, not permanent.

### Webhook controllers: share a base

Three webhook endpoints — share 90% of logic via `multichannel_hub_core/controllers/webhook_base.py`:

```
class WebhookBase:
    _verify_signature(payload, signature, secret)
    _rate_limit_check(source_ip)
    _log_event(event_model, vals)
    _idempotency_check(event_model, unique_key)  # critical
```

Idempotency is critical. Etsy + Gearment both retry on non-200. Every handler must: verify HMAC -> idempotency check -> process -> 200. Spec 005 has idempotency on webhook_event; **Spec 004's partner.sync.log doesn't — add it.**

### Google Drive sync — worth it?

Adds a dep + service account setup + token rotation. Start with manual Excel upload. **Defer GDrive to a later iteration.** YAGNI.

### Carrier mapping location

Per CONFLICT-1 fix: `shipping.carrier` owns everything. Add `etsy_carrier_name` field. Delete `etsy.carrier.mapping`.

### Historical data reconciliation

`etsy_order_id` is the API receipt ID — SQL UNIQUE enforces the match. Spec 002 should include a pre-Spec-005 validation step: verify existing `etsy_order_id` format matches API returns. Fallback heuristic: `(buyer_email, order_date, total)`.

---

## 5. Testing strategy

### Two-Phase pattern holding up?

Phase 1 (DB verification) made sense for historical import. Phase 2 (ORM unit tests) is standard. For Specs 003-005, ratio shifts toward Phase 2.

### What needs which test type

**Unit tests (pytest, no Odoo)**:
- `email_parser.py` — 43 regexes with fixture-based tests
- `EtsyApiClient` — rate limiter, token refresh, retry, HMAC
- `carrier_detector.py`
- `product_categorizer.py`
- Rate limiter utility
- Partner sync adapters (with mocked HTTP)

**Integration tests (TransactionCase)**:
- `EtsyOrderSyncer.sync_shop_orders()` with fixture JSON
- `OrderCreator.process_parse_result()` full pipeline
- Migration wizard savepoint batching (inject failure, verify rollback)
- Record rules
- State machine transitions
- Cron methods

**HttpCase**:
- Webhook controllers — HMAC verification, idempotency, 200/401

**E2E (Playwright)**:
- OAuth flow (Spec 005)
- Design file approval workflow
- Tracking import wizard
- Dashboard tree view interactions

### Mocking external APIs

- `responses` library for unit tests
- `pytest-recording` / VCR.py for real-capture replay — sanitize secrets before commit
- Webhook fixtures: capture real payloads once, hash with test secret

---

## 6. Technical debt & refactor targets

### 43-regex parser deprecation timeline

Per my dual-mode recommendation: regex parser lives only until first shop switches to `api_only`. Concrete timeline:
- Spec 005 ships -> pilot shop on API -> 2 weeks parallel audit
- Confirm >= 99.5% match -> flip pilot to `api_only`
- Roll remaining shops over 4-8 weeks
- **6 months**: parser marked deprecated, moved to `etsy_channel_legacy` (uninstallable)
- **12 months**: deleted

### etsy_transaction_id dedup robustness

Robust for API data. Historical concern: regex-parsed IDs may have extraction errors. Spec 002's migration wizard should include a validation pass that re-matches historical transactions against the API once Spec 005 lands. Flag mismatches for manual review.

### 17K stuck-in-draft orders

Spec 002's migration wizard should confirm them in batches of 100 **without auto-invoicing** (money already collected by Etsy months ago). Set `invoice_status='invoiced'` manually via SQL update after review.

### Module rule violations in shipped code

Quick scan found:
- `sale_order.py` lines 66, 69, 78, 118: `_logger.info(...)` for per-email/per-order events (should be `.debug()`)
- `order_creator.py` lines 51, 79, 94, 155, 180, 197: same pattern

**Fix**: Add ruff rule or pre-commit hook banning `_logger.info(` in `services/` and `models/`.

### `_cron_fetch_etsy_emails` is 109 lines in `sale_order.py`

Should live in `gmail_ingestion_service.py`. Model method becomes 5-line wrapper. Refactor target for Spec 002 or 005 cleanup.

---

## 7. Top 10 technical recommendations

| # | Recommendation | Specs | Urgency | Effort | Why |
|---|---|---|---|---|---|
| 1 | **Unify carrier model**. Promote `sale.order.shipping_carrier` to M2O, delete `etsy.carrier.mapping`. | 003, 004, 005 | **Now** (before 004 lands) | S | Eliminates 3 parallel carrier concepts |
| 2 | **Drop `dual` sync mode**; keep only `email_only`/`api_only`. Add 1-week audit mode as one-off flag. | 005 | **Now** | S | Prevents permanent parser maintenance burden |
| 3 | **Extract fulfillment delegation mixin** before code is written. | 003, 004 | **Now** | M | Prevents sale.order from hitting 120+ fields |
| 4 | **Shared rate limiter utility** (`multichannel_hub_core/utils/rate_limiter.py`) | 004, 005 | Next sprint | S | DRY across Gearment + Etsy |
| 5 | **Shared webhook controller base** with HMAC + idempotency + rate-limit guard | 004, 005 | Next sprint | S | 3 controllers should share 90% logic |
| 6 | **4-module decomposition**: core / fulfillment / etsy_channel / etsy_channel_migration | 003, 004, 005 | Next sprint | L | Prevents 10k-LOC monolith |
| 7 | **Ban `_logger.info` in models/services/** via pre-commit; fix 6 existing violations | 001 | Next sprint | S | Rule already documented |
| 8 | **Defer Google Drive auto-sync**. Start manual. | 004 | Later | S (saves L) | YAGNI |
| 9 | **Index `tracking_number`**; add composite `(etsy_shop_id, etsy_last_modified DESC)` | 003, 005 | Next sprint | S | Spec 004 import does per-row lookup |
| 10 | **Raw-material inventory = reuse `stock` + `product.template`**. Do NOT build parallel model. | new | Later | M | Odoo-Native First |

---

## Key file references

- `custom_addons/etsy_integration/models/sale_order.py` — 147-line cron needs extraction; `_logger.info` violations at 66, 69, 78, 118
- `custom_addons/etsy_integration/services/order_creator.py` — 290 lines, violations at 51, 79, 94, 155, 180, 197
- `custom_addons/etsy_integration/services/email_parser.py` — 570 lines, 43-regex parser to deprecate post-Spec 005
- `specs/002-etsy-config-fixes/plan.md` R4 — correct savepoint pattern
- `specs/003-dashboard-design-multichannel/data-model.md` — `shipping_carrier` Char (should be FK)
- `specs/004-fulfillment-routing/data-model.md` — `shipping.carrier` model; `fulfillment.partner` adapter
- `specs/005-etsy-api-channel/data-model.md` — `etsy.carrier.mapping` (to merge); dual sync_mode (to reduce)
