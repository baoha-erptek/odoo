# P0-22 — Etsy API ↔ Email-Parser Ingest Parity

**Slice ID**: P0-22
**Critical-path step**: 4b
**Added**: 2026-05-10 (owner D1)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P0-17 ✓ (Spec 005 sandbox complete)
**Blocks**: P2-07 production cutover from email to API
**Phase 1 author**: planner agent (Sonnet) 2026-05-10

---

## 1. Decision

**Route `email_parser` output through `EtsyOrderPayload` adapter** (single canonical write path).

Rationale:
- Both ingest paths converge on `EtsyOrderPayload → EtsyOrderIngestor.ingest()`. Zero divergent code paths going forward.
- Blast radius: minimal. New `EtsyEmailAdapter` is pure Python, isolated from existing `OrderCreator.process_parse_result()`. Existing email path stays untouched until the cutover step.
- P2-07 cutover (deactivate email ingest) becomes a one-line cron rebind, not a code merge.
- Single acceptance test: golden email + golden API receipt → identical `sale.order` records on the 9 parity fields.
- Risk to 162+ existing `etsy_integration` tests: near-zero (no service-layer refactor; new adapter is additive).

Rejected alternative: extend `order_creator.process_parse_result()` directly. Smaller diff but locks in two divergent code paths permanently.

---

## 2. The 9 parity fields (reconnaissance confirmed)

| Layer | Field | API path writes | Email path writes |
|---|---|---|---|
| `sale.order` | `etsy_shipping_service` | ❌ missing | ✓ |
| `sale.order` | `etsy_processing_time` | ❌ missing | ✓ |
| `sale.order` | `etsy_discount_code` | ❌ missing | ✓ |
| `sale.order` | `etsy_subtotal` | ❌ missing | ✓ |
| `sale.order` | `payment_status` | ✓ | ❌ missing |
| `sale.order` | `etsy_last_modified` | ✓ | ❌ missing |
| `sale.order` | `sync_source` | ✓ | ❌ missing |
| `sale.order` | `etsy_raw_source_id` | ✓ | ❌ missing |
| `sale.order.line` | `etsy_transaction_id` | ❌ missing | ✓ |
| `sale.order.line` | `etsy_personalisation` | ❌ missing | ✓ |
| `sale.order.line` | `etsy_sku` | ❌ missing | ✓ |

(`etsy_email_log_id` stays path-specific — no API analogue.)

All 11 model fields already exist on `sale.order` / `sale.order.line` (verified by planner reconnaissance). The fix is in the **adapter→ingestor write path**, not in the schema.

---

## 3. Required schema extensions

### 3.1 `EtsyOrderPayload` (canonical DTO)

Add four optional attributes to capture email-only data that the API path will eventually carry:

```python
@dataclass(frozen=True)
class EtsyOrderPayload:
    # ... existing fields ...
    shipping_service: str | None = None     # NEW — "USPS Priority Mail"
    processing_time: str | None = None      # NEW — "1-2 business days"
    discount_code: str | None = None        # NEW
    subtotal: float | None = None           # NEW — pre-shipping/tax sum
```

Plus on `EtsyLineItemPayload`:

```python
@dataclass(frozen=True)
class EtsyLineItemPayload:
    # ... existing fields ...
    name_override: str | None = None        # NEW — email path's product-name string
```

These are additive; existing call-sites (`EtsyApiAdapter`) construct payloads positionally only via keyword args — verify with grep before commit.

### 3.2 `email_parser.ParseResult`

Already carries `shipping_service`, `processing_time`, `discount_code`, `subtotal`, and per-transaction `product_name` (verified by planner reconnaissance against `services/email_parser.py`). No new fields needed on `ParseResult` itself.

### 3.3 No model-level schema changes

All 11 `sale.order` / `sale.order.line` fields exist. No migrations, no `_sql_constraints`, no ACL changes.

---

## 4. New / changed files

| File | Phase | Scope | LOC est. |
|---|---|---|---|
| `services/etsy_email_adapter.py` | NEW (GREEN) | `EtsyEmailAdapter` class wrapping `email_parser.ParseResult` → `EtsyOrderPayload` | 150–180 |
| `services/etsy_order_payload.py` | EDIT (GREEN) | +4 optional fields on `EtsyOrderPayload` + `name_override` on line | +10 |
| `services/etsy_order_ingestor.py` (or `order_creator.py` write path) | EDIT (GREEN) | Map new payload fields onto `sale.order` / `sale.order.line` writes | +15 |
| `services/etsy_api_adapter.py` | EDIT (GREEN) | Populate new payload fields where the receipt JSON has them (else `None`) | +20 |
| `services/__init__.py` | EDIT (GREEN) | Export `EtsyEmailAdapter` | +1 |
| `tests/test_p0_22_db.py` | NEW (RED) | Phase 1 — 11 field-existence introspection tests + readonly assertions | 60 |
| `tests/test_p0_22_orm.py` | NEW (RED) | Phase 2 — per-field adapter unit tests + ingestor write-through | 200 |
| `tests/test_p0_22_parity.py` | NEW (RED) | Phase 2 — golden-fixture acceptance test (email + API → identical orders) | 150 |
| `tests/data/sample_p0_22_golden.txt` | NEW | Golden email fixture (synthetic; covers all 9 fields) | 60 |
| `tests/fixtures/etsy_v3/p0_22_golden_receipt.json` | NEW | Golden API receipt fixture (synthetic; same order_id as email) | 80 |
| `tests/__init__.py` | EDIT | Register 3 new test modules | +3 |

**Cron cutover deferred**: replacing `process_parse_result()` with the new adapter in the email-polling cron is a separate slice (P0-22-cutover or fold into P2-07). This slice ships the adapter + tests proving parity, not the production rebind. The plan keeps both paths runnable in parallel.

---

## 5. Slice tasks (for `tasks.md`)

```
- [ ] T0-22-01 Read EtsyOrderPayload + EtsyLineItemPayload; add 4 optional sale.order fields + name_override on line item
- [ ] T0-22-02 Read email_parser.ParseResult; verify it exposes shipping_service / processing_time / discount_code / subtotal / per-line product_name
- [ ] T0-22-03 Write Phase 1 DB tests — 11 field existence + readonly=True on payment_status / etsy_last_modified
- [ ] T0-22-04 Write Phase 2 ORM unit tests — per-adapter per-field mapping (4 email-side, 4 API-side)
- [ ] T0-22-05 Write Phase 2 golden-fixture parity test — email + API → identical sale.order on 9 fields
- [ ] T0-22-06 Author golden-email fixture (tests/data/sample_p0_22_golden.txt) covering all 9 fields
- [ ] T0-22-07 Author golden-receipt JSON fixture (tests/fixtures/etsy_v3/p0_22_golden_receipt.json) with same order_id
- [ ] T0-22-08 Implement EtsyEmailAdapter._parse_result_to_payload (ParseResult → EtsyOrderPayload, source='email')
- [ ] T0-22-09 Extend EtsyApiAdapter to populate new payload fields (shipping_service / processing_time / discount_code / subtotal) where receipt JSON has them
- [ ] T0-22-10 Update EtsyOrderIngestor to write the 4 new payload fields onto sale.order + name_override onto sale.order.line
- [ ] T0-22-11 Run code-reviewer + security-reviewer in parallel; block on CRITICAL/HIGH
- [ ] T0-22-12 Run odoo -u etsy_integration --stop-after-init; verify 0 errors + all etsy_integration test tags pass
- [ ] T0-22-13 Append findings.md §"P0-22" with implementation-choice rationale + any surprises
- [ ] T0-22-14 Update tracker P0-22 row to state=done; update T089 cross-reference
```

T089 (existing tasks.md row) is the parity test under the future `etsy_channel_email` module rename. P0-22 is the early-arriving implementation; T089 will close as part of the module-rename slice when this code moves to its final home.

---

## 6. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| `EtsyApiAdapter` callers break when new keyword-only fields added to payload | LOW | HIGH | All new fields default to `None`; verify no call-site uses positional construction past field 19. |
| Golden-email fixture lacks one of the 9 fields (regex doesn't extract) | MEDIUM | MEDIUM | Build fixture from a real Etsy receipt email already in tests/data/sample_single_order.txt; verify `email_parser.parse_etsy_email()` populates all 4 email-side fields before writing parity test. |
| Golden API receipt JSON missing `shipping_service` / `processing_time` (Etsy receipts API returns these inconsistently) | MEDIUM | LOW | Where API doesn't carry the field, the API adapter writes `None`. Parity test asserts equality of `(email_value, api_value or fall-through)` — a documented allowed asymmetry, not a bug. **Mitigation**: scope the parity assertion to fields the receipts API genuinely carries; document the "API-soft" fields in the test docstring. |
| `name_override` line-level addition collides with existing `etsy_integration` line-name handling | LOW | MEDIUM | Grep `_build_line_vals` and `EtsyOrderIngestor._line_vals_from_payload` for `name=` writes; only set `name=name_override` when non-None and different from `product.name`. |
| FR-017 write-defense newly required because of writable email-side fields | LOW | MEDIUM | These fields already exist and are already writable today via `process_parse_result()` — no new attack surface. No FR-017 work needed. |
| Migration-version collision with parallel slices | LOW | LOW | This slice has no migration. Manifest version bump optional (no schema change). |

---

## 7. Exit-criteria mapping

Per playbook §"Slice exit criteria":

| Criterion | Closed by |
|---|---|
| All slice tasks `[X]` | T0-22-01..14 |
| Tests pass; coverage ≥80% changed lines | T0-22-12 (run test tags + coverage on the 3 new test files + 4 changed services) |
| Module installs cleanly | T0-22-12 (`odoo -u etsy_integration --stop-after-init` exit 0) |
| ACLs / sudo / raw SQL annotated | N/A this slice — no new model, no new sudo, no raw SQL |
| Tracker state updated | T0-22-14 |
| `/learn` insight captured (or "no new patterns" note) | T0-22-13 |
| `findings.md` updated | T0-22-13 |

---

## 8. Phase 2..9 hand-off

Order:
1. **Phase 2 RED** (`tdd-guide`): T0-22-03..07 (test files + fixtures). Verify they fail for the right reasons.
2. **Phase 3 GREEN** (orchestrator inline): T0-22-01, T0-22-08..10. Execute against RED tests.
3. **Phase 4 Review** (parallel `code-reviewer` + `security-reviewer`): T0-22-11. Single message, two `Agent` calls.
4. **Phase 5 Verify**: T0-22-12.
5. **Phase 6 Commit**: RED commit + GREEN commit + plan/findings doc commit on `feature/006-master-plan-coding`. Cite P0-22 in body.
6. **Phase 7 Document**: T0-22-13, T0-22-14.
7. **Phase 8 Learn**: `/learn` against the diff; capture if a new pattern surfaced (candidate: dual-adapter parity testing recipe).
8. **Phase 9 Land**: stays on feature branch; merges to `main` after W7 E2E sprint.
