# Codex Implementation Brief — Etsy Order Coverage + Manual Pull + Per-User Shop Scoping

> Source of truth: `~/.claude/plans/about-specs-005-etsy-api-channel-databas-floofy-steele.md`
> (approved 2026-06-23). JIRA: ESTY-205 / ESTY-206 / ESTY-207. Slices:
> P1-SHOP-USER-SCOPE / P1-ORD-PULL-BTN / P1-ORD-COVERAGE in
> `.claude/plans/006-master-plan-tracking.md`. Review gate: `review-plan.md` (sibling).

This brief is **self-contained** — implement only from what is written here plus the
cited files. All paths are under `custom_addons/etsy_integration/` unless noted.

## Rules of engagement
- Branch: `feature/006-master-plan-coding`. One conventional commit per story:
  `[etsy_integration] feat(...)` (or `[multichannel_hub_core]` if the model lives there);
  cite the ESTY key + slice ID in the body.
- **TDD (MP006 Two-Phase):** write Phase 1 (DB-introspection) + Phase 2 (ORM) tests
  FIRST (RED), then implement (GREEN). Keep diffs surgical — no drive-by refactors.
- **Standard-Odoo-First:** reuse existing fields/patterns; `default_code` is the SKU key.
- No `print()`, no `_logger.info` for debugging (use `_logger.debug`). Functions <50 lines.
- New model ⇒ ACL row required; every `sudo()` / raw SQL gets an inline justification.
- **Implementation order: C → B → A** (B reads C's `user_id`; A is gated on the A1 diff).

---

## Story 1 (do first) — P1-SHOP-USER-SCOPE / ESTY-205 — per-user shop scoping

### C1. `etsy.shop.user_id` (`models/etsy_shop.py`)
Add the conventional "Responsible" field and surface it on the shop form + list
(`views/etsy_shop_views.xml`):
```python
user_id = fields.Many2one(
    'res.users', string='Responsible',
    help='Odoo user who manages this shop; scopes order visibility and manual pull.',
    ondelete='set null', index=True)
```
One user may own many shops; each shop has exactly one responsible user.

### C2. Record rules on `sale.order` (`security/etsy_security.xml`)
Two `ir.rule` records. Odoo OR-combines non-global rules across a user's groups, so a
restrictive rule on the base group plus a permissive rule on the admin groups yields
"scoped users restricted, admins see all":

- **Restrictive** — `groups = base.group_user`, perm_read/write/create/unlink all True,
  domain (only Etsy orders are restricted; non-Etsy pass through the `False` branch):
  ```python
  ['|', ('etsy_shop_id', '=', False), ('etsy_shop_id.user_id', '=', user.id)]
  ```
- **Permissive** — `groups = sales_team.group_sale_manager` + `base.group_system`,
  domain `[(1, '=', 1)]`.

Notes:
- Odoo only auto-bypasses record rules for superuser id=1. An Administrator who is NOT
  a sale manager must still match the permissive rule — that is why `base.group_system`
  is on it. Confirm by test.
- Do **not** add a `mail.message` rule — chatter visibility already follows the parent
  `sale.order` access.
- The sync cron runs as `__system__` (superuser) and the Story-2 button uses `sudo()`,
  so ingestion is unaffected by the rules.

### C3. ACL — none (no new model).

### Tests (`tests/test_shop_user_scoping.py`)
- Phase 1: `etsy.shop.user_id` column exists; both `ir.rule` rows present with the
  expected `domain_force` and group links.
- Phase 2 (use `with_user`): shops S1→userA, S2→userB; an Etsy order on each + one
  non-Etsy order. userA `sale.order.search([])` returns A's Etsy order + the non-Etsy
  order, NOT B's. A `sales_team.group_sale_manager` user sees all. An Administrator
  (`base.group_system`) who is not a sale manager sees all.

---

## Story 2 — P1-ORD-PULL-BTN / ESTY-207 — manual "Pull Etsy Orders" button

### B1. List header button (`views/sale_order_views.xml`)
New inherited view extending `sale.view_quotation_tree_with_onboarding`,
xpath `//header` position `inside`:
```xml
<button name="action_pull_etsy_orders" type="object"
        string="Pull Etsy Orders" class="btn-secondary"
        groups="base.group_user"/>
```
List `<header>` object buttons render in the control panel and call the model method on
an empty recordset (no row selection). Mirrors the stock "Create Invoices" header
button in `sale.sale_order_tree`.

### B2. `action_pull_etsy_orders` (`models/sale_order.py`)
```text
def action_pull_etsy_orders(self):
    # 1. Resolve allowed shops from env.user (the security gate):
    #    - if user has base.group_system OR sales_team.group_sale_manager:
    #          shops = etsy.shop.search([('active_source', '=', 'api')])
    #    - else:
    #          shops = etsy.shop.search([('active_source','=','api'),
    #                                    ('user_id','=', env.user.id)])
    # 2. if not shops: return a display_notification ("No Etsy shops assigned to you").
    # 3. syncer = EtsyOrderSyncer(self.env.sudo())   # sudo justified below
    #    for shop in shops: aggregate syncer.sync_shop_orders(shop) -> {ingested, audited, errors}
    # 4. return a display_notification with the totals.
```
- **sudo justification (inline comment required):** OAuth tokens + `etsy_api_shop_id`
  are `groups='base.group_system'` fields; a scoped user cannot read them. The
  user→shop assignment search in step 1 is the security gate (FR-017 write-defense
  pattern). sudo is applied ONLY after the allowed-shop set is computed from `env.user`
  — never to a user-supplied shop id.
- Reuse `services/etsy_order_syncer.py:EtsyOrderSyncer.sync_shop_orders` unchanged.
  `_cron_sync_orders`'s `_is_system()` gate is on the cron method, not the syncer, so
  this path is fine.

### Tests (`tests/test_manual_pull_button.py`)
- Phase 1: resolved arch of `view_quotation_tree_with_onboarding` contains
  `action_pull_etsy_orders`.
- Phase 2 (mock `EtsyOrderSyncer.sync_shop_orders`): admin resolves ALL api shops;
  scoped user resolves only own `user_id` api shops; no-shop user gets the clean
  notification (no traceback); the sudo path is not reachable for an unassigned shop.

---

## Story 3 — P1-ORD-COVERAGE / ESTY-206 — full receipt → sale.order coverage

### A1. Live diff FIRST (read-only) — `scripts/etsy_receipt_diff.py`
Run on staging (SSH `ubuntu@129.150.63.207`, DB `esty_odoo19`; creds in repo `.env` +
key `~/.ssh/esty_project`). The script:
- Loads the `sale.order` for Etsy receipt `3818231452` (referenced as S0007; the
  P1-11-WIRE-LIVE tracker row recorded it as `S00006` — confirm the live number) plus
  its lines + partner; dumps all `etsy_*` and total fields.
- Reads the order's `etsy_shop_id` stored OAuth token and calls
  `GET /v3/application/shops/{etsy_api_shop_id}/receipts/{3818231452}` via
  `services/etsy_api_client.py:EtsyApiClient`.
- Prints a 3-column table **Etsy key → current Odoo target → status**
  (mapped / missing / mismatch) + a **total reconciliation** line
  (`amount_total` vs `grandtotal`, `subtotal`, `total_shipping_cost`, tax).
Save the receipt JSON as a test fixture. The diff output drives which candidate fields
below are real; prune the rest.

### A2. Extend mapping (payload → adapter → order_creator → model/view)
Thread each populated-but-missing field through:
- `services/etsy_order_payload.py` — add fields to `EtsyOrderPayload` /
  `EtsyLineItemPayload` (frozen dataclasses; keep tuples/immutability).
- `services/etsy_api_adapter.py` — populate in `_receipt_to_payload` /
  `_transaction_to_line_item`.
- `services/order_creator.py` — write in `process_etsy_payload` (header vals + the
  `line_vals` dict, currently around lines 591-608).
- `models/sale_order.py` / `models/sale_order_line.py` — add fields only where none
  exists; REUSE existing line fields `etsy_color/size/option/side/face_mask_size`,
  `etsy_image_url`.
- `services/etsy_order_ingestor.py:_status_only_resync` — refresh a new field on
  re-sync only if appropriate; keep operator-owned fields preserved.
- `views/sale_order_views.xml` — surface new fields read-only in the `etsy_tab` page.

Candidate set (confirm/prune via A1):
| Etsy field | Odoo target | Note |
|---|---|---|
| `transactions[].variations[]` | line `etsy_color/size/option/side/face_mask_size` | **confirmed gap** — `variations` dict parsed but never written; map it; text fallback for unmapped axes |
| `transactions[].listing_id`/image | line `etsy_image_url` | currently empty |
| `total_tax_cost`,`total_vat_cost` | new `etsy_tax_total` (order, informational) | feed reconciliation check |
| `status` | new `etsy_receipt_status` (order) | distinct from `payment_status` |
| `is_shipped` | informational flag (order) | |
| discount amount | new `etsy_discount_amount` (order) | code mapped, amount not |
| `needs_gift_wrap`,`gift_wrap_price` | new `etsy_gift_wrap_*` (order) | if present |

**Reconciliation gate:** Odoo `amount_total` must equal Etsy `grandtotal`. New tax/
discount fields are **informational only** — do NOT overwrite computed pricing.
If totals don't reconcile, STOP and escalate (pricing bug), don't paper over it.

### A3. Product resolution (SKU-first) — `services/order_creator.py`
Today `find_or_create_product` matches by **name only** and auto-creates on miss,
ignoring the Etsy SKU. Add `_resolve_line_product(sku, title, listing_id, image_url)`
used by `process_etsy_payload` (and the email `process_parse_result` path):
1. `etsy.listing.product` where `sku == line.sku` (active) → its `product_id`
   (already SKU-matched, honours operator overrides). Prefer the variant whose
   `listing_id.etsy_listing_id == line.listing_id` when multiple share a SKU.
2. else `product.product` where `default_code == line.sku` — mirror
   `models/etsy_listing_product.py:_match_variant` (single-company `default_code`,
   deterministic first-by-id on duplicates).
3. else exact-name match (current behaviour).
4. else **auto-create + flag** — create as today (`is_etsy_product=True`) and set a new
   `etsy_needs_product_review` Boolean on `product.product` (grep first; reuse an
   existing review flag if one fits), filterable on the product list. Never silently
   spawn unlinked duplicates.
Empty `sku` skips tiers 1-2. Keep `find_or_create_product` as the tier-4 creator; the
new helper wraps it. Tiers 1-2 must NOT auto-create.

### Tests (`tests/test_etsy_order_coverage.py`)
- Phase 2: feed the captured `3818231452` fixture through `EtsyApiAdapter` +
  `OrderCreator`; assert variation/tax/status/discount fields land on order+lines and
  `amount_total` reconciles with `grandtotal`.
- `_resolve_line_product`: one test per tier (SKU-link hit, default_code hit, name hit,
  create+flag) + duplicate-SKU determinism; assert tiers 1-2 never auto-create.

---

## Verify before handing back for review (each story)
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`
  exits 0; `--test-tags /etsy_integration` green; no NEW full-suite regressions.
- `ruff check custom_addons/etsy_integration/`; grep modified `.py` for `_logger.info`/`print(`.
- After upgrade, `docker restart namco_odoo19` before any browser QA (stale-registry trap).
