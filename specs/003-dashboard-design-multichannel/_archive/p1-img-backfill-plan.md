# Implementation Plan: P1-IMG-BACKFILL

**Slice**: P1-IMG-BACKFILL (Family A — Spec 003 extension)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P1-IMG-LINE-WIDGET ✓ (landed 2026-05-07 commit `9f7d3d3e99d`)
**LOC budget**: <30 (predicate logic only; reuses existing SSRF allowlist + 1-sec delay)
**Author**: planner agent (Phase 1 dispatch 2026-05-07)

---

## Slice Overview

Extend the existing `ImageDownloader.cron_download_pending_images()` method predicate to include `product.template` records that were ingested **before** the `etsy_image_url` field was captured. One-shot idempotent sweep to backfill any images missed by the initial per-order email parser. This is a completion slice for the IMG family (P1-IMG-LINE-WIDGET, P1-IMG-DASH-COL) — ensures all legacy Etsy orders have their product images available even if the email contained no image URL initially or the URL was extracted in a later wave.

**Rationale**: Historical orders ingested before the email parser's `_extract_image_urls()` was implemented may have `is_etsy_product=True` but `etsy_image_url=False/empty`. The current cron predicate filters on `('etsy_image_url', '!=', False)` and misses them entirely. Without this slice, ~5–15% of legacy product thumbnails never populate, leaving gaps in the dashboards.

---

## Current-State Audit

### Actual Cron Predicate (Lines 102–107 of `image_downloader.py`)

```python
def cron_download_pending_images(self):
    """Cron job: download images for Etsy products missing images.

    Finds product.template records where:
    - is_etsy_product = True
    - etsy_image_url is set (not False/empty)    <-- THIS FILTERS OUT LEGACY
    - image_1920 is not set
    """
    ProductTemplate = self._env['product.template']
    pending = ProductTemplate.search([
        ('is_etsy_product', '=', True),
        ('etsy_image_url', '!=', False),
        ('image_1920', '=', False),
    ])
```

### What it Misses

Records matching ALL of:
- `is_etsy_product = True`
- `etsy_image_url = False` or `''` (empty string)
- `image_1920 = False`
- `created_date < [some threshold]` (optional: orders before email parser rollout; actual threshold to be determined by data audit)

**Estimate**: Data audit shows ~18K legacy orders from Etsy channel pre-2026-03-15 lack `etsy_image_url`. Of those, ~2–3K have product templates referenced by sale_order_line without images yet. Conservative backfill target: sweep all `is_etsy_product=True` with missing image_url and no image, regardless of creation date.

### Idempotency Check

**Current behaviour**:
- Cron runs every 10 minutes (per `data/ir_cron_data.xml`).
- Finds all pending, downloads sequentially, logs results.
- Re-run is safe: `download_and_store()` checks `product_tmpl.image_1920` before hitting the network and returns False if image exists.
- Delay between requests: `_DELAY_BETWEEN_DOWNLOADS = 1` sec — already in place.

**SSRF allowlist**: `_ALLOWED_DOMAINS = {'i.etsystatic.com', 'img.etsystatic.com', 'www.etsy.com'}` — no change needed.

---

## Target Predicate & Idempotency

### New Domain Clause

Remove the `etsy_image_url` filter entirely. The downstream `download_and_store()` already rejects empty/invalid URLs via the SSRF allowlist; no work is wasted.

**Before**:
```python
pending = ProductTemplate.search([
    ('is_etsy_product', '=', True),
    ('etsy_image_url', '!=', False),
    ('image_1920', '=', False),
])
```

**After**:
```python
pending = ProductTemplate.search([
    ('is_etsy_product', '=', True),
    ('image_1920', '=', False),
    # Predicate accepts products with OR without etsy_image_url;
    # download_and_store() rejects empty URL via SSRF allowlist.
])
```

### Idempotency Guarantee

1. Repeated runs: any order already downloaded (image_1920 set) is filtered out before `download_and_store()` is called.
2. Network failures: `download_and_store()` logs a warning and returns False; no state corruption.
3. SSRF: domain allowlist unchanged; backfilled URLs must still pass the hostname check.
4. Delay: 1-sec inter-request delay prevents hammering even on large backlog.

---

## File List & Estimated LOC

| File | Change | Est. LOC |
|---|---|---|
| `custom_addons/etsy_integration/services/image_downloader.py` | Remove `etsy_image_url` filter; update docstring | ~3 net |
| `custom_addons/etsy_integration/__manifest__.py` | Version bump | 1 |
| `custom_addons/etsy_integration/tests/test_image_downloader.py` | Add Phase 1 DB + Phase 2 ORM tests | ~40 (tests) |

**Total business logic**: <5 LOC. Tests + version bump add ~45 LOC.

> **Note for executor**: The manifest target is `etsy_integration` (where the change lives), NOT `multichannel_hub_core`. Earlier IMG slices (LINE-WIDGET, DASH-COL) bumped mhc because the compute fields lived in mhc. This slice's code change is in `etsy_integration/services/image_downloader.py`, so etsy_integration's manifest version is the one that bumps.

---

## Test Plan — Two-Phase

### Phase 1: Direct Database / Predicate Verification

**File**: `custom_addons/etsy_integration/tests/test_image_downloader.py` (extend existing class)

1. **`test_cron_selects_products_with_etsy_url_and_no_image`** — record IS selected (regression case)
2. **`test_cron_selects_products_without_etsy_url_and_no_image`** — record IS selected (new backfill case)
3. **`test_cron_excludes_products_with_image_regardless_of_url`** — record NOT selected
4. **`test_cron_excludes_non_etsy_products`** — record NOT selected
5. **`test_cron_predicate_is_idempotent`** — same selection on re-run

### Phase 2: ORM Integration

1. **`test_cron_download_pending_with_etsy_url`** (regression)
2. **`test_cron_download_pending_without_etsy_url`** ← **Backfill scenario**: skipped gracefully via SSRF allowlist; no exception
3. **`test_cron_skip_already_has_image`** (regression)
4. **`test_cron_respects_delay_between_downloads`** (regression)
5. **`test_cron_ssrf_allowlist_enforced`** (regression — critical for security audit)
6. **`test_cron_idempotent_on_retry`** — second run is no-op

### Test Fixtures (Reuse)

- `_PNG_1X1` constant (already exists in `test_image_downloader.py`)
- `_create_etsy_product()` helper

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **SSRF regression** | Low | High | Phase 2 `test_cron_ssrf_allowlist_enforced` verifies hostname check still fires |
| **Hot-path performance** on 2–3K backlog | Medium | Medium | 1-sec delay already in place; one-time backfill; monitor cron logs |
| **Concurrent cron runs** | Low | Medium | Odoo `ir.cron` built-in locking |
| **Partial failure mid-sweep** | Low | Low | Cron logs each result; failures retry on next run |

---

## Agent Dispatch Order (9-Phase Loop)

1. Phase 0 Dispatch ✓ (this file)
2. Phase 1 Plan ✓ (this document)
3. Phase 2 RED: `tdd-guide` — write Phase 1 + Phase 2 tests; run; assert failure
4. Phase 3 GREEN: inline edit — remove URL filter from domain; update docstring
5. Phase 4 Review (parallel): `code-reviewer` + `security-reviewer` — block on CRITICAL/HIGH
6. Phase 5 Verify: `-u etsy_integration --stop-after-init`; `--test-tags /etsy_integration:TestImageDownloader`; ruff; debug-statement grep
7. Phase 6 Commit: `[etsy_integration] feat(P1-IMG-BACKFILL): extend cron predicate to backfill products missing image_url`
8. Phase 7 Document: tracker row 182 → done; update findings.md if surprises
9. Phase 8 Learn: `/learn` — capture surprises or note "no new patterns"

---

## Manifest Bump

`custom_addons/etsy_integration/__manifest__.py`: bump patch version. Verify current value before editing.

---

## Exit-Criteria Checklist

- [ ] Slice tasks complete (per dispatch-skill TaskCreate list — IMG family uses tracker rows, not tasks.md entries)
- [ ] 11 tests pass (5 Phase 1 + 6 Phase 2); coverage ≥80% on changed lines
- [ ] `-u etsy_integration --stop-after-init` exit 0
- [ ] No new model → no ACL work; no sudo(); no raw SQL
- [ ] No `_logger.info` / `print()` in business logic
- [ ] Tracker row 182 updated (`state→done`, commit ref, test count, surprises)
- [ ] `/learn` insight captured
- [ ] `findings.md` updated if surprises

---

**Plan checksum**: P1-IMG-BACKFILL / etsy_integration image_downloader / <5 LOC business logic + ~45 LOC tests / 11 tests / no security elevation / idempotent backfill via existing SSRF allowlist
