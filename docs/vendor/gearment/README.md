# Gearment API — crawled doc corpus

Local markdown snapshot of the official Gearment v3 developer docs, captured to
resolve **Defect-2026-05-10-05** (opaque 400 on `orders/draft` `printing_options`).
See `docs/GEARMENT_API_REFERENCE.md` for the analysis; this folder is the raw evidence.

## Contents (committed)

| File | Source URL |
|------|-----------|
| `api_api.order.v1.vendororderapi.md` | https://developers.gearment.com/api/api.order.v1.vendororderapi |
| `api_api.webhook.v1.vendorwebhookapi.md` | https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi |
| `api_section_overview.md` | https://developers.gearment.com/api/section/overview |

- **Crawled:** 2026-07-05
- **Method:** `crawl4ai` (uv tool at `~/.local/share/uv/tools/crawl4ai`) with a JS
  step that expands Stoplight Elements collapsibles. Script:
  `render_gearment.py` (kept in the session scratchpad; re-runnable).
- `_raw/` holds the source HTML snapshots and is **git-ignored** (see `.gitignore`).
- The docs portal is a JS SPA but server-renders the example payloads, so the
  authoritative request shapes are captured. The exhaustive `location_code` enum is
  shown only as an example (`PRINT_LOCATION_CODE_WHOLE`) + a "+N more" truncation —
  full set inferred from the proto3 house-style + the 400 error contract (see below).

## Key facts extracted

- **Draft line item** (`POST /api/v3/orders/draft`) keys on **`variant_id`** (e.g.
  `GM0002003147`) + `product_id` (e.g. `G5000`) — **not** a free-text SKU. Our
  `DEMO-T-*` SKUs are not catalog variants and are rejected on lookup.
- **Draft** printing shape: `printing_options: [{ "location_code":
  "PRINT_LOCATION_CODE_WHOLE", "url": "..." }]`.
- **Quote** (`POST /api/v3/orders/.../price`) uses a *different* shape:
  `print_locations: ["front"]` (lowercase string array). Do not conflate the two.
- Enums are proto3 SCREAMING_SNAKE with a type prefix throughout
  (`VENDOR_ORDER_STATUS_*`, `VENDOR_CREATED_METHOD_*`, `PRINT_LOCATION_CODE_*`).

## Search

```bash
# ripgrep the corpus directly, or use the docs-corpus skill:
rg -i 'printing_option|location_code|variant_id' docs/vendor/gearment/*.md
python ~/.claude/skills/docs-corpus/references/search.py \
    --corpus docs/vendor/gearment --query "printing_option"
```
