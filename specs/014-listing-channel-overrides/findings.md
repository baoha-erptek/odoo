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

## Step 5–9: Deferred to code-slice phase

To be populated during Phase 3 implementation:
- Phase 3 GREEN: Field definitions, publisher methods, view wiring.
- Phase 4 REVIEW: Code-reviewer + security-reviewer findings.
- Phase 5 VERIFY: Module install, test regression baseline.
- Phase 6 COMMIT: Commit details, LOC delta.
- Phase 8 LEARN: Surprises captured to auto-memory.

