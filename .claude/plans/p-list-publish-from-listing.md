# P-LIST-PUBLISH-FROM-LISTING — Publish to Etsy button on Listing form

**Status:** PLANNED — awaiting owner go-ahead for Phase 2 RED
**Branch:** `feature/006-master-plan-coding`
**Owner / driver:** Bao Ha (this session)
**Date drafted:** 2026-06-08

---

## 1. Context & motivation

Marketing / BA users currently bounce between two form views to publish
a product to Etsy:

1. `multichannel_hub_core.view_multichannel_listing_form` — where they
   curate listing-level overrides (title, description, hero image,
   video, Etsy taxonomy, shipping profile, who_made, attribute
   mapping, etc.). This is the *home base* for the marketing flow.
2. `product.product_template_only_form_view` — where the only existing
   **"Publish to Etsy"** button lives (added by
   `etsy_integration/views/product_views.xml:22-28`).

The Listing form **already carries everything the publish wizard
needs** — `product_tmpl_id`, `etsy_shop_id` (typed M2O, see §5), and
`channel_id`. Forcing the user to leave Listing → navigate to Product
→ click Publish is pure UX friction that the doc
`docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.2 currently
papers-over by describing only the BA path from Product form.

---

## 2. Scope (owner-approved)

### 2.1 View inherit — `etsy_integration` module

New file: `custom_addons/etsy_integration/views/multichannel_listing_views.xml` (~40 LOC).

Inherits `multichannel_hub_core.view_multichannel_listing_form`.
Adds **two header buttons** (same method, different `string` + visibility
domain — Odoo doesn't support computed button labels) **left of the
existing statusbar** (sibling to the existing `action_open_in_etsy_shop_manager`
button at mhc/views/multichannel_listing_views.xml:40-45):

| Button label | `name=` | `class=` | `groups=` | `invisible=` |
|---|---|---|---|---|
| **Publish to Etsy** | `action_open_etsy_publish_wizard` | `oe_highlight` | `multichannel_hub_core.group_ba_user` | `channel_id.code != 'etsy' or state in ('error','published') or not etsy_shop_id` |
| **Resume Publish** | `action_open_etsy_publish_wizard` | `oe_highlight` | `multichannel_hub_core.group_ba_user` | `channel_id.code != 'etsy' or state != 'error' or not etsy_shop_id` |

Rationale for visibility predicates:
- `channel_id.code != 'etsy'` — non-Etsy channels (e.g., future Amazon) hide both
- `state == 'published'` — already pushed; user uses "Open in Etsy Shop Manager" instead
- `not etsy_shop_id` — shop never resolved (NULL after migration backfill); hide rather than show a doomed button. The view-side hide is defense-in-depth; the method ALSO raises UserError to catch the RPC path.

### 2.2 Bridge action — `multichannel.listing._inherit` in `etsy_integration`

Add method to **existing** `MultichannelListingEtsy` class at
`custom_addons/etsy_integration/models/multichannel_listing.py` (~25 LOC
including docstring and i18n error messages).

```python
def action_open_etsy_publish_wizard(self):
    """Spec P-LIST-PUBLISH-FROM-LISTING — open publish wizard from listing.

    Pre-fills both product_tmpl_id and shop_id from the listing record,
    eliminating the bounce to product form. The wizard method itself
    carries the FR-017 BA-group gate (defense-in-depth with view).
    """
    self.ensure_one()
    if not self.channel_id or self.channel_id.code != 'etsy':
        raise UserError(_("This listing is not bound to the Etsy channel."))
    if not self.etsy_shop_id:
        raise UserError(_(
            "This listing has no Etsy Shop resolved. Open the Advanced "
            "settings group and set the Etsy Shop manually, or contact "
            "an admin to re-run the shop backfill."
        ))
    return {
        'type': 'ir.actions.act_window',
        'name': _('Publish to Etsy'),
        'res_model': 'etsy.publish.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_product_tmpl_id': self.product_tmpl_id.id,
            'default_shop_id': self.etsy_shop_id.id,
        },
    }
```

**Imports needed at top of file:** add `from odoo import _` (currently only
`api, fields, models`) and `from odoo.exceptions import UserError`.

### 2.3 Manifest + __init__ wiring

- `custom_addons/etsy_integration/__manifest__.py`:
  - Add `'views/multichannel_listing_views.xml'` to `data` list, placed **after**
    the existing `'views/multichannel_listing_etsy_views.xml'` so all the
    listing-related inherits are grouped (load order doesn't strictly matter
    here since both inherit the same base view, but keep them adjacent for
    grep-ability).
  - Bump version (current → next patch).
- `models/__init__.py` already imports `multichannel_listing` (no change).

### 2.4 Tests

Two-phase, per `.claude/plans/006-implementation-playbook.md`.

**Phase 1 (DB) — `tests/test_p_list_publish_from_listing_phase1_db.py`** (~60 LOC):

| # | Test | Assertion |
|---|---|---|
| 1 | `test_view_arch_has_publish_button` | `ir.ui.view` for `multichannel.listing` form with `etsy` in name has button `name="action_open_etsy_publish_wizard"` |
| 2 | `test_button_has_ba_group_gate` | Button has `groups="multichannel_hub_core.group_ba_user"` |
| 3 | `test_button_visibility_hides_non_etsy` | Button's `invisible` domain references `channel_id.code != 'etsy'` |
| 4 | `test_button_visibility_hides_no_shop` | Button's `invisible` domain references `not etsy_shop_id` |
| 5 | `test_resume_button_label_for_error_state` | A second button exists with `string="Resume Publish"` (or similar) gated on `state == 'error'` |

**Phase 2 (ORM) — `tests/test_p_list_publish_from_listing_phase2_orm.py`** (~180 LOC):

| # | Test | Setup → expectation |
|---|---|---|
| 1 | `test_happy_path_returns_wizard_action` | Listing with valid `etsy_shop_id` + `channel_id.code='etsy'` → returns act_window dict with `res_model='etsy.publish.wizard'`, ctx has both `default_product_tmpl_id` and `default_shop_id` matching the listing |
| 2 | `test_error_non_etsy_channel` | Listing with channel_id pointing to non-etsy channel → UserError matching "Etsy channel" |
| 3 | `test_error_no_etsy_shop_id` | Listing with `etsy_shop_id=False` → UserError matching "no Etsy Shop resolved" |
| 4 | `test_ensure_one_recordset` | Call on 2-record recordset → ValueError from `ensure_one()` |
| 5 | `test_fr017_wizard_still_gates_non_ba` | Open wizard as non-BA user → wizard method gate fires (the bridge action itself doesn't gate; the wizard does) |

Coverage target: ≥80% on changed lines (action method + view arch loaded paths).

### 2.5 Doc update — `docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md`

- Bump version line (line 3): `Phiên bản: 1.3 · Ngày: 2026-06-08`
- Add changelog entry under existing v1.2 blockquote.
- §7.2 "Bấm 'Publish to Etsy'": split into two sub-paths:
  - **Cách 1 (mới, dành cho Marketing):** Operations → Listings → mở Listing → bấm nút **Publish to Etsy** ở header. Hệ thống tự chọn shop từ trường Etsy Shop của Listing.
  - **Cách 2 (dành cho BA, không đổi):** Sản phẩm → mở SP → bấm **Publish to Etsy** ở header form Sản phẩm → chọn shop trong Wizard.
- Keep the rest of §7.2 (action choices, fallbacks) unchanged.

---

## 3. Tracker row text (drop-in for `006-master-plan-tracking.md`)

```markdown
| P-LIST-PUBLISH-FROM-LISTING | Listing UX: Publish to Etsy button on listing form header | Wave 2 / Listing UX | this session | feature/006-master-plan-coding | main | none | NEW | — | — | — | — | Eliminates BA bounce between Listing form and Product form. View inherit + bridge action reading existing `etsy_shop_id` M2O (no resolver needed — already backfilled by migration 19.0.3.8.0). Doc HUONG_DAN_TAO_SAN_PHAM_VN.md §7.2 updated. |
```

Place under existing Wave 2 / Listing UX rows (search for `P-LIST-UX-FIXES` or `P-LIST-VIDEO` to find the right group).

---

## 4. Phase 3 implementation order

1. **Add action method** to `models/multichannel_listing.py` — self-contained, no XML dependency
2. **Create view file** `views/multichannel_listing_views.xml` — references the new method
3. **Wire manifest** — add data file + bump version
4. **Write Phase 1 DB tests** — verify view arch landed
5. **Write Phase 2 ORM tests** — verify action method behavior
6. **Run `-u etsy_integration --stop-after-init`** — exit 0
7. **Run test tags** — both phases pass
8. **Update doc** `HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.2

---

## 5. Risks & open questions

### Risk 1 (RESOLVED): shop_ref → etsy.shop resolution

**Status: RESOLVED before plan was finalized.**

Initial planner draft assumed we'd need to do `etsy.shop.search([('name','=',self.shop_ref)])` at action time. **Reading the code revealed `multichannel.listing.etsy_shop_id` already exists** — a typed M2O backfilled by migration `19.0.3.8.0` (post-migrate name-lookup, see
`custom_addons/etsy_integration/migrations/_19_0_3_8_0/post_migrate.py:30`).
The shop is therefore already resolved on every existing listing
(NULL when migration couldn't find a unique match). This eliminates
~50 LOC of resolver code + 2 test cases. Net: slice is **smaller and
safer** than initially planned.

### Risk 2: Button label toggling

Odoo XML buttons don't support computed `string=`. Implementing as two
buttons with mutually-exclusive `invisible` domains. Each phase-1 test
expects the right `string=` value on the right button. Standard Odoo
pattern — low risk.

### Risk 3: Backfill-NULL listings (FR-017 layer-1 hide)

Listings whose migration backfill produced `etsy_shop_id=NULL` (because
their `shop_ref` matched 0 or >1 etsy.shop records) will see the
Publish button hidden by the view-level `invisible="not etsy_shop_id"`
predicate. They can fix it by manually setting `etsy_shop_id` in the
Advanced settings group (already visible in dev mode per mhc view line
93-94). Documented in the UserError text.

### Risk 4: Wizard fields exist and accept context defaults

Verified by reading `custom_addons/etsy_integration/wizards/etsy_publish_wizard.py:24-29`:
both `product_tmpl_id` and `shop_id` are `fields.Many2one`, `required=True`,
and Odoo auto-populates from `default_*` context keys. No wizard changes
needed.

### Risk 5 (open, low-severity): Listing state ↔ Etsy publish state divergence

The mhc listing `state` (draft/ready/published/error) is a **marketing
approval workflow**, while the actual Etsy publish state lives on
`product.channel.status`. This slice does NOT wire post-publish auto-flip
of `multichannel.listing.state` because the publisher service
(`EtsyListingPublisher`) currently writes only to `product.channel.status`.
Result: pressing "Publish to Etsy" from the Listing form successfully
pushes to Etsy but the Listing.state stays in 'draft' (or wherever it
was). User must manually flip via Reset to Draft / Mark Ready / etc.

This is **acceptable for the current slice** but worth a follow-up
slice `P-LIST-PUBLISH-STATE-SYNC` to wire the listener.

---

## 6. Exit criteria (machine-checkable)

- [ ] Action method added at `models/multichannel_listing.py` with `_(...)` i18n on all UserError messages
- [ ] View file `views/multichannel_listing_views.xml` created with 2 buttons (Publish / Resume)
- [ ] Manifest `data` list includes new view file + version bumped
- [ ] Phase 1 (DB) test file passes 5/5 tests
- [ ] Phase 2 (ORM) test file passes 5/5 tests
- [ ] Coverage ≥ 80% on changed lines
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exits 0
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init` exits 0
- [ ] `ruff check custom_addons/etsy_integration/models/multichannel_listing.py custom_addons/etsy_integration/views/multichannel_listing_views.xml` (XML: skip if ruff doesn't lint XML; Python file: must pass)
- [ ] `grep -n '_logger.info\|print(' custom_addons/etsy_integration/models/multichannel_listing.py` returns no debug artifacts
- [ ] `code-reviewer` + `security-reviewer` agents run in parallel, no CRITICAL/HIGH unresolved
- [ ] One conventional commit on `feature/006-master-plan-coding`: `[etsy_integration] feat(P-LIST-PUBLISH-FROM-LISTING): Publish to Etsy button on listing form`
- [ ] Doc `HUONG_DAN_TAO_SAN_PHAM_VN.md` §7.2 updated + version bumped to 1.3
- [ ] Tracker row added to `006-master-plan-tracking.md`
- [ ] `/learn` run at session end (or note "no new patterns")

---

## 7. What this slice does NOT do (explicit out-of-scope)

- ❌ Make the listing statusbar (`draft → ready → published`) clickable as a state-flip trigger
- ❌ Auto-flip `multichannel.listing.state` to `published` / `error` after wizard success (separate slice P-LIST-PUBLISH-STATE-SYNC if/when needed)
- ❌ Modify `etsy.publish.wizard` model, view, or method (consumes the wizard as-is via `default_*` context)
- ❌ Touch the existing Product-form "Publish to Etsy" button (the BA-from-Product path stays intact)
- ❌ Add a new tracker phase or rename existing tracker columns
