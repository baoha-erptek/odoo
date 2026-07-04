# Findings — Spec 014 / P-ENH-ESTY-190 (Listing Channel Overrides)

## Step 1: Standard-Odoo-First evidence

### Standard Odoo 19 CE product fields

```bash
$ grep -n "name\|description_sale\|image_1920" odoo/addons/product/models/product_template.py | head -20
28: name = fields.Char(...)
35: description = fields.Text(...)
36: description_sale = fields.Text(...)
52: image_1920 = fields.Image(...)
```

**Verdict**: Standard Odoo 19 CE product.template ships `name`, `description_sale`, `image_1920`. These are the canonical product-level fields. No custom naming here.

### Existing `multichannel.listing` fields

```bash
$ grep -A 2 "title\|description\|image_1920" custom_addons/multichannel_hub_core/models/multichannel_listing.py
65:    title = fields.Char(
66:        help='Per-listing marketing title; empty → product.template.name.',
67:    )
68:    description = fields.Text(
69:        help='Per-listing marketing description; empty → '
70:             'product.template.description_sale.',
71:    )
72:    image_1920 = fields.Image(
73:        max_width=1920,
74:        max_height=1920,
75:        help='Per-listing hero image; empty → product.template.image_1920.',
76:    )
```

**Verdict**: P-LIST-MODEL (spec 012, commit 696c4068a99) already shipped `multichannel.listing.title`, `.description`, `.image_1920` fields. They serve as per-listing marketing overrides. The docstring even names the fallback chain: `listing.title` → `product.template.name`.

### Existing `etsy.shop` default fields

```bash
$ grep -n "default_" custom_addons/etsy_integration/models/etsy_shop.py | head -20
77:    default_taxonomy_id = fields.Char(...)
80:    default_shipping_profile_id = fields.Char(...)
83:    default_return_policy_id = fields.Char(...)
87:    default_readiness_state_id = fields.Char(...)
102:    listing_currency_id = fields.Many2one(...)
```

**Verdict**: `etsy.shop` ships 4 `default_*` fields for Etsy-specific configs, PLUS `listing_currency_id`. NO `default_title`, `default_description`, `default_image_1920` fields exist yet.

### Search for `mhc.product.channel.copy` model

```bash
$ grep -rn "product.channel.copy\|product_channel_copy" custom_addons/ || echo "Not found"
Not found
```

**Verdict**: The tracker's note about a new `mhc.product.channel.copy` model is stale. No such model exists in the codebase.

## Step 2: Multichannel listing UNIQUE constraint analysis

From `custom_addons/multichannel_hub_core/models/multichannel_listing.py:127-142`:

```python
def init(self):
    """Mirror UNIQUE(product_tmpl_id, channel_id, shop_ref) at PG."""
    self.env.cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
            uniq_multichannel_listing_tmpl_channel_shop
        ON multichannel_listing (
            product_tmpl_id, channel_id, COALESCE(shop_ref, '')
        )
    """)
```

**Finding**: The UNIQUE INDEX enforces "one listing per (product_template, channel, shop)". This means:
- One product (e.g. "Ceramic Mug") + one channel (Etsy) + one shop (JaHandmadeArt) = exactly one `multichannel.listing` row.
- That row can hold title/description/image overrides at the listing level.
- **Therefore, the listing-level fields already serve as per-shop overrides** — no new model needed.

The tracker note suggesting a `mhc.product.channel.copy` model would be **redundant** — it would create the same (product, channel, shop) cardinality as `multichannel.listing` already enforces.

## Step 3: ADR scope decision

**Decision**: New ADR-017. Rationale:
- ADR-015 covers the listing-model split and the two-layer fallback chain (listing → product).
- Adding a third layer (shop-level defaults) is orthogonal and deserves separate documentation.
- Separate ADR allows independent deprecation/refactoring in future waves.

## Step 4: Scope clarification — no new model, only shop defaults

**Key insight**: The tracker row mentioned:
> Per-channel/per-shop overrides for Title, Description, Image. New `mhc.product.channel.copy` model FK'd to `mhc.product.channel.status` + `etsy.shop`

But P-LIST-MODEL (spec 012) already solved this:
- `multichannel.listing` IS the per-channel-per-shop override row.
- Its UNIQUE INDEX enforces (product, channel, shop) cardinality.
- Fields `title`, `description`, `image_1920` are already the per-shop overrides.

**Recommended scope** (minimal, Standard-Odoo-First):
1. Add THREE shop-level **default** fields to `etsy.shop`:
   - `default_title` (Char, fallback when listing + product title are empty)
   - `default_description` (Text, fallback when listing + product description are empty)
   - `default_image_1920` (Image, fallback when listing + product image are empty)

2. Update publisher fallback logic to use the three-layer chain:
   - Level 1: `multichannel.listing.title` / `.description` / `.image_1920` (per-listing)
   - Level 2: `product.template.name` / `.description_sale` / `.image_1920` (per-product)
   - Level 3: `etsy.shop.default_title` / `.default_description` / `.default_image_1920` (per-shop, **NEW**)

3. NO new model. NO new listing-level fields (they exist). Only shop-level additions.

## Step 5–9: Implementation surprises

| Phase | Surprise | Resolution | Memory? |
|---|---|---|---|
| 2 RED | `fields.Image()` is attachment-backed in Odoo 19 — no column lands on the host `etsy_shop` table. Phase-1 column-existence test against `information_schema.columns` failed for `default_image_1920` even though the field was correctly registered. | Switched the Phase-1 assertion to `ir_model_fields` lookup (memory item 152 pattern). | No (already covered by item 152 in `feedback_odoo19_test_gotchas.md`). |
| 2 RED | `product.template.name` is NOT NULL in Odoo 19. Phase-2 test for the "shop default fires when product name empty" branch cannot be exercised via a real ORM row — `record.name = False` raises `null value in column "name"`. | Duck-typed the template parameter with `types.SimpleNamespace(name='')` so the helper exercises the fallback path. Documented in test docstring. | Worth a one-line note: NOT NULL on `product.template.name` blocks "empty name" test fixtures; use SimpleNamespace mock. |
| 3 GREEN | The publisher's `_build_create_draft_payload` originally inlined `(intent.title or '') or s.name or ''`; refactoring to call `_resolve_title_with_fallback` simplified the read site AND let the DEBUG log fire on the correct tier. | Inlined chain replaced with helper call; helper handles the 3-tier logic + log. | No (refactor to spec, no surprise). |
| 5 verify | Spec §8 referenced `docs/owner/HUONG_DAN_QUAN_LY_KENH_BAN.md` which doesn't exist in the repo. Owner-doc tree centralises Etsy publishing docs under `HUONG_DAN_TAO_SAN_PHAM_VN.md`. | Appended §7.4b-defaults to the existing file + added UAT TC-024 to `UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md`. Spec §8 reference was aspirational, not authoritative. | No (one-off spec-vs-repo drift). |
| 5 verify | Suite baseline expanded from 744 (post-ENH-195) to 757 (after wiring the 13 new ENH-190 tests). Fail count 18 / error 5 unchanged → zero new regressions. | Recorded baseline shift in commit body + tracker. | No. |
| 6 commit | Phase 4 reviewers SKIPPED inline given: (a) BA already passed Standard-Odoo-First gate at spec time, (b) the 3 new shop helpers mirror the already-reviewed `_resolve_who_made` pattern (spec 011), (c) no `sudo()` writes — only reads inside helpers (security trivially clean). | Logged the skip in commit body per CLAUDE.md "Acceptable shortcuts" rule. | No (rule already in CLAUDE.md). |

