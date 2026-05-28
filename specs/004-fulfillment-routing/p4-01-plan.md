# P4-01 — Spec 004b Gearment Adapter, Full State Machine + UI Surfaces

**Slice ID**: P4-01
**Critical-path step**: 9
**Branch**: `feature/006-master-plan-coding`
**Phase 1 author**: planner agent (Opus) 2026-05-10; orchestrator extracted decisions
**Depends on**: Phase 2 exit ✓, P0-18 ✓, P1-01b ✓, P0-22 ✓ — all done
**Blocks**: P4-01b (bulk-action), P4-02 (returns), P5 reporting suite

---

## 1. Decisions

### D1 — Sandbox vs production env: **D1.c (skip fresh discovery)**

Owner confirmed via Telegram 2026-05-10: the Gearment account in `.env` IS owner's dev account. No abandoned-draft risk; production URL is the dev environment. Plus the readiness probe in `findings.md` 2026-05-09 already captured the `/orders/draft` schema (G2), `/orders/price` Money-proto response (G3), HMAC round-trip (Probe 5), and 503 throttling pattern (S4). We have enough probe data to drive Sub-phase B without a fresh round of live calls. One live verification call against `/orders/draft` will confirm field-correctness once the new payload is wired.

### D2 — Sub-phase B test breakage handling: **D2.a (atomic update of P0-18b1 mocks)**

Update P0-18b1 mock tests in the same commit that regenerates the payload + adapter URLs. Atomic commit is cleaner for bisect/blame, and P0-18b1 must stay green (it's the regression baseline).

### D3 — State machine field placement: **D3.a (Selection on `sale.order` in mhf)**

New `x_gearment_outbound_state` Selection field on `sale.order` via mhf `_inherit`. Reasons:
- `order.pipeline.state` (P1-PIPELINE-FULL) is a workflow-level state shared across pipelines (vn / gearment / hybrid). The Gearment-specific `draft → quoted → operator_review → confirmed → cancelled` machine is a transport-level state on top of that workflow, not a replacement.
- Adding 4 new pipeline states would inflate `order.pipeline.state` for a transport concern that doesn't apply to vn_internal_production or hybrid.
- Aligns with existing `x_gearment_outbound_ref` Char on `sale.order` (P1-DESIGN+GEARMENT).

### D4 — Wizard granularity: **D4.a (modal launched from form button)**

Owner D5 mandates whole-order granularity on the form button. Modal wizard surfaces price quote + shipping estimate; operator clicks Confirm or Cancel. No per-line checkboxes (per D5).

### D5 — 503/504 retry strategy: **D5.b (separate `ServiceUnavailableError` with 5,15,45 backoff)**

Production throttles via 503 + Cloudflare timeouts (S4). 429 stays at 1,2,4 sec (rate-limit specific); 503/504 gets longer 5,15,45 sec (infrastructure transient). 3 retries each. Separate exception classes so logging/monitoring distinguish "infra blip" from "quota exhaustion."

---

## 2. Contract gaps to close (from findings.md 2026-05-09)

| Gap | Current behaviour | Real behaviour | Fix |
|---|---|---|---|
| **G1** URL | `POST /api/v3/orders` → 404 | `POST /api/v3/orders/draft` | Rewrite URL constant |
| **G2** Payload | `external_order_id` + `address` + `quantity` + `product_id` | `reference_id` + `addresses[].first_name/last_name/street_1/zip_code/country_code` + `line_items[]` | Regen `GearmentOrderPayload` dataclass + new `GearmentPayloadBuilder` service |
| **G3** Quote response | reads `price_quote/shipping_estimate/quote_expires_at` | proto-`Money` shape on `order_sub_total/order_shipping_fee/order_tax/order_discount/order_handle_fee/order_gift_message_fee/order_fee/order_total` + nested `fees[]` + `line_items[]` | New `_money_to_decimal()` helper + rewritten `get_quote()` response parser |
| **G4** Confirm endpoint | unimplemented (raises `NotImplementedError`) | `POST /api/v3/orders/draft/labeled` (per docs; needs live probe to confirm) | Implement `confirm(reference_id, options)` |

---

## 3. New / changed files

### Sub-phase A — Live verification (lightweight; uses container creds)

| File | Phase | Scope |
|---|---|---|
| `specs/004-fulfillment-routing/quickstart.md` | EDIT | Append Section §"P4-01 verified contract" with captured request/response bodies |

### Sub-phase B — Payload + adapter regen (~200 LOC + mock test updates)

| File | Phase | Scope | LOC |
|---|---|---|---|
| `services/gearment_payload.py` | REWRITE | New dataclass: `reference_id`, `addresses: tuple[GearmentAddress, ...]`, `line_items: tuple[GearmentLineItem, ...]`, `shipping_method: str | None`, `notes: str | None`, `idempotency_key: str`. New `GearmentAddress` + `GearmentLineItem` frozen dataclasses. `serialize()` produces the `{"data": {...}}` envelope (single object, not array — per probe S3 the array envelope was rejected on `/orders/draft`). | 100 |
| `services/gearment_payload_builder.py` | NEW | `GearmentPayloadBuilder.build(order, design_files)` extracts shipping address into `GearmentAddress`, builds `GearmentLineItem` per `sale.order.line` with design URL, returns `GearmentOrderPayload`. Pure Python, no ORM. | 90 |
| `services/gearment_adapter.py` | EDIT | URL constants: `_DRAFT_URL = '/api/v3/orders/draft'`, `_PRICE_URL = '/api/v3/orders/{ref}/price'`, `_LABELED_URL = '/api/v3/orders/draft/labeled'`. `push_order` calls `_DRAFT_URL`. `get_quote` returns `GearmentQuote` dataclass with `_money_to_decimal()` parsed totals. New `confirm(reference_id, options)` method calls `_LABELED_URL`. New `_money_to_decimal(money_dict)` helper: `(money['units'] + money['nanos']/1e9) → decimal('USD')`. | 80 |
| `services/gearment_api_client.py` | EDIT | New `ServiceUnavailableError` exception. Extend `_request()` retry loop: 503/504 → 3 retries with 5/15/45 sec backoff. Existing 429 path unchanged. | 50 |
| `tests/test_gearment_payload.py` | EDIT | Update 6 P0-18b1 schema tests for new dataclass shape. | 30 delta |
| `tests/test_gearment_adapter.py` | EDIT | Update ~22 mock tests: new URLs, new payload shape, new Money-proto response parsing. | 80 delta |
| `tests/test_p4_01_payload_db.py` | NEW | Phase 1 DB introspection — confirm new payload dataclass fields exist. | 40 |
| `tests/test_p4_01_payload_orm.py` | NEW | Phase 2 ORM — `GearmentPayloadBuilder.build()` correctness, `_money_to_decimal()` precision, envelope shape per route, address required-field validation. | 150 |
| `tests/test_p4_01_adapter_urls.py` | NEW | Phase 2 ORM — confirm adapter calls correct URLs (mocked HTTPS), 503/504 retry branch, 429 still works. | 100 |

### Sub-phase C — State machine + wizard (~280 LOC)

| File | Phase | Scope | LOC |
|---|---|---|---|
| `models/sale_order.py` (mhf) | EDIT | `x_gearment_outbound_state` Selection (`draft`, `quoted`, `operator_review`, `confirmed`, `cancelled`). Default `draft`. tracking=True. `_advance_gearment_state(target)` helper (idempotent, sequence-compared). Methods: `action_get_gearment_quote()` (calls adapter.get_quote, transitions draft→quoted, stores quote on order), `action_open_gearment_quote_wizard()` (returns `act_window` for the wizard). | 100 |
| `models/sale_order.py` (mhf) — additional fields | EDIT | `x_gearment_quote_total` Float, `x_gearment_quote_currency` Char, `x_gearment_quote_expires_at` Datetime, `x_gearment_quote_breakdown_json` Text (JSON of fee table for the wizard). All readonly. | 30 |
| `wizards/gearment_quote_wizard.py` | NEW | TransientModel `gearment.quote.wizard`. Fields: `order_id` M2O, readonly mirrors of the 4 quote fields. `action_confirm()` calls `adapter.confirm(reference_id, ...)` → transitions order to `confirmed` + advances pipeline. `action_cancel()` transitions to `cancelled`, sets `x_gearment_outbound_ref=False` so re-push is possible. FR-017 11th confirmation gate. | 100 |
| `views/gearment_quote_wizard_views.xml` | NEW | Form view: order info, quote breakdown table (rendered from JSON), expires-at countdown, Confirm/Cancel buttons. | 50 |
| `tests/test_p4_01_state_machine_db.py` | NEW | Phase 1 — Selection field exists, 5 keys correct, default=draft. | 40 |
| `tests/test_p4_01_state_machine_orm.py` | NEW | Phase 2 — state transitions (draft→quoted→operator_review→confirmed; quoted→cancelled), idempotency, FR-017 RPC gate, wizard action_confirm + action_cancel paths, expired-quote guard. | 200 |

### Sub-phase D — UI surfaces (D3 + D4 + D5) (~150 LOC)

| File | Phase | Scope | LOC |
|---|---|---|---|
| `views/sale_order_views.xml` (mhf) | EDIT | Add **"Sync to Gearment"** button on form (visible when `sales_channel == 'etsy'` AND `x_gearment_outbound_ref` is empty); calls `action_push_to_gearment()`. Group: `multichannel_hub_fulfillment.group_ba_shipping`. Add new **"Gearment"** notebook tab showing state, quote breakdown, expires-at, smart link to `gearment.api.log`. | 50 |
| `views/operations_dashboard_views.xml` (mhc) | EDIT | New server action `action_server_gearment_bulk_sync` bound to `sale.order.line` list. Action method `sale.order.line.action_gearment_bulk_sync()` → dedupes via `mapped('order_id')` → calls `action_push_to_gearment()` per order with savepoint isolation → `bus.bus.notification` progress. FR-017 RPC gate. | 30 |
| `models/sale_order_line.py` (mhf NEW or mhc EDIT?) | NEW (mhf) | `_inherit = 'sale.order.line'` adds `action_gearment_bulk_sync()` method. Lives in mhf because it depends on Gearment adapter. | 40 |
| `etsy_integration/views/sale_order_views.xml` | EDIT | Add read-only **Shipping** subsection inside Etsy tab (after "Notes section"). Renders `tracking_number`, `shipping_carrier_id`, `tracking_state`, `shipping_date`, `tracking_url` (all from `sale.order.fulfillment` via existing delegation). All `readonly="1"`. | 30 |
| `tests/test_p4_01_ui_orm.py` (mhf) | NEW | Phase 2 — bulk action dedup, bulk action savepoint isolation, FR-017 ACL gate, form button visibility (smoke test). Etsy tab read-only: introspect view arch. | 100 |
| `tests/test_p4_01_etsy_tab_view.py` (etsy_integration) | NEW | Phase 1 — Etsy tab xpath has Shipping subsection; tracking_number readonly. | 40 |

---

## 4. Slice tasks (for tasks.md)

```
- [ ] T4-01-01 Sub-phase A — verify /orders/draft contract with one live POST against owner's dev account; capture working request body in quickstart.md
- [ ] T4-01-02 Sub-phase B — RED: Phase 1 DB tests for new GearmentOrderPayload dataclass fields
- [ ] T4-01-03 Sub-phase B — RED: Phase 2 ORM tests for GearmentPayloadBuilder + _money_to_decimal + new URL routing + 503/504 retry
- [ ] T4-01-04 Sub-phase B — RED: update P0-18b1 mock tests to expect new URLs + payload shape (will fail until GREEN)
- [ ] T4-01-05 Sub-phase B — GREEN: regen GearmentOrderPayload + new GearmentAddress + GearmentLineItem; new GearmentPayloadBuilder
- [ ] T4-01-06 Sub-phase B — GREEN: rewrite gearment_adapter.py URLs + add _money_to_decimal + new GearmentQuote dataclass + confirm() impl
- [ ] T4-01-07 Sub-phase B — GREEN: add ServiceUnavailableError + 503/504 retry to gearment_api_client.py
- [ ] T4-01-08 Sub-phase B — verify all P0-18b1 + P4-01-B tests green; module installs clean
- [ ] T4-01-09 Sub-phase C — RED: Phase 1 DB test for x_gearment_outbound_state Selection
- [ ] T4-01-10 Sub-phase C — RED: Phase 2 ORM tests for state transitions + wizard actions + FR-017 gate
- [ ] T4-01-11 Sub-phase C — GREEN: x_gearment_outbound_state + 4 quote fields + _advance_gearment_state helper + action_get_gearment_quote
- [ ] T4-01-12 Sub-phase C — GREEN: gearment.quote.wizard TransientModel + form view + action_confirm/action_cancel
- [ ] T4-01-13 Sub-phase D5 — Sync to Gearment form button + Gearment notebook tab on sale_order_views.xml (mhf)
- [ ] T4-01-14 Sub-phase D3 — operations dashboard bulk sync server action + sale_order_line.action_gearment_bulk_sync method
- [ ] T4-01-15 Sub-phase D4 — read-only Shipping subsection in Etsy tab on etsy_integration sale_order_views.xml
- [ ] T4-01-16 Sub-phase D — RED+GREEN: Phase 2 ORM bulk-action tests + view-arch tests
- [ ] T4-01-17 Run code-reviewer + security-reviewer in parallel on full diff; block on CRITICAL/HIGH
- [ ] T4-01-18 Verify: -u multichannel_hub_fulfillment + multichannel_hub_core + etsy_integration --stop-after-init exit 0; full test tags green; grep _logger.info / print
- [ ] T4-01-19 Update tracker P4-01 row state todo-rescoped → done; append findings.md §"P4-01" with G1-G4 resolutions + surprises; T0-18b1 baseline test count delta
- [ ] T4-01-20 /learn capture (or "no new patterns" note)
```

---

## 5. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Sub-phase A live probe surfaces a NEW contract gap (G5) not in findings.md captures | LOW | HIGH — design churn | One verification call BEFORE Sub-phase B GREEN; if a new gap surfaces, document and split slice |
| Updating 28 P0-18b1 mock tests introduces silent regressions in sibling P0-18b2 webhook tests | MEDIUM | MEDIUM | Run full mhf test suite after Sub-phase B GREEN; the 153 mhf tests + 558 cross-module count is the regression baseline |
| Wizard double-click race (operator clicks Confirm twice before adapter response) creates duplicate Gearment confirms | MEDIUM | MEDIUM | Idempotency key + state guard in `action_confirm` (raise if state != 'operator_review'); Gearment also dedupes by `reference_id` belt-and-braces |
| HMAC re-verification on confirm response not implemented (response signature could be forged in MITM) | LOW | LOW | Out of scope for P4-01; documented as M-P4-01-001 in findings.md for future hardening (TLS already covers most of this) |
| 503/504 retry path masks real outages — operator never sees "Gearment is down" | LOW | LOW | After 3 retries, `ServiceUnavailableError` propagates as `UserError`; chatter posts the failure |
| Etsy-tab Shipping subsection reveals tracking data to non-shipping users | LOW | LOW | Fields are mhc/mhf-owned via delegation; existing ACLs on `sale.order.fulfillment` already gate writes; reads stay open per current dashboard policy |
| Bulk action operator-error: selects 200 lines, hits Sync, locks DB for 10s | MEDIUM | LOW | Synchronous push per owner D3, but with `cr.savepoint()` per order so failures don't roll back the batch. If perf becomes an issue, future P4-01b takes it async |
| `x_gearment_outbound_state='confirmed'` doesn't auto-advance pipeline state | LOW | MEDIUM | `action_confirm_gearment_quote` calls `_write_pipeline_state('gearment_pod/confirmed')` after the adapter confirm() succeeds (mirrors P1-DESIGN+GEARMENT) |
| Live probe (Sub-phase A) creates a "real" Gearment draft that owner has to clean up | LOW | LOW | Owner confirmed dev account; abandoned drafts on dev account are acceptable noise |

---

## 6. Exit-criteria mapping

| Criterion | Closed by |
|---|---|
| All 20 slice tasks `[X]` | T4-01-01..20 |
| Tests pass; coverage ≥80% changed lines | T4-01-08 + T4-01-16 + T4-01-18 |
| Module installs cleanly | T4-01-18 |
| ACLs / sudo / FR-017 annotated | T4-01-12 (wizard FR-017 gate); T4-01-14 (bulk-action FR-017 gate); no new sudo |
| Tracker state updated | T4-01-19 |
| `/learn` insight captured | T4-01-20 |
| `findings.md` updated | T4-01-19 |

---

## 7. Phase 2..9 hand-off

1. **Phase 2 RED**: Author Phase 1 DB + Phase 2 ORM tests for Sub-phase B FIRST, then Sub-phase C, then Sub-phase D. Verify each fails for the right reasons before GREEN.
2. **Phase 3 GREEN**: Sub-phase A live verify → Sub-phase B GREEN → Sub-phase C GREEN → Sub-phase D GREEN. Each sub-phase is committed atomically.
3. **Phase 4 Review**: parallel `code-reviewer` + `security-reviewer` after Sub-phase D GREEN.
4. **Phase 5 Verify**: T4-01-18.
5. **Phase 6 Commit**: 4 conventional commits — RED tests / Sub-phase B / Sub-phase C / Sub-phase D — plus a 5th doc commit. Cite P4-01 in body. Note Sub-phase A's verification call (no source change) inside the Sub-phase B GREEN commit body.
6. **Phase 7 Document**: T4-01-19.
7. **Phase 8 Learn**: T4-01-20.
8. **Phase 9 Land**: feature branch accumulates; merges to `main` after W7 E2E.
