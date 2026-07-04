# S-0 Findings — Publisher field-source diff against staging `esty_odoo19`

**Slice**: P-LIST-PUBLISH-DIFF-RUN
**Date**: 2026-06-08
**Env**: `odoo.hatafax.com` / `esty_odoo19`
**Companion data**: `publish_diff_2026_06_08.json` (raw XMLRPC + reconstructed payload, same dir)
**Script**: `scripts/etsy_publish_diff.py`

> **2026-06-08 update — CONFIRMED-BUG #1 fixed.** P-PUB-RESOLVER-CASING-BUG
> landed on `feature/006-master-plan-coding` at commit `3754731394c`. Option A
> shipped (one-line `=ilike` with `\\` / `%` / `_` literal escape at
> `services/etsy_listing_publisher.py:518`). 6 ORM tests pass. Wave 2
> listing-tier override slices are unblocked. Live re-run of this diff against
> staging recommended post-deploy to confirm listing 62 (tmpl 456, Etsy
> 4518406711) now resolves correctly.
>
> **2026-06-08 update — CONFIRMED-BUG #2 fixed.** P-LIST-PUBLISH-STATE-SYNC
> landed at commit `dd40bb4e924`. Publisher's `run()` now mirrors success /
> error state onto the shop-specific `multichannel.listing` row via the new
> `_resolve_shop_specific_listing` helper. 6 ORM tests pass. The 17 stuck-draft
> staging PCS rows with `external_ref` will resolve naturally on the next
> publish (no destructive backfill in this slice). Reprioritised queue slot 2
> closed; next slot is **slot 3 P-LIST-IMAGE-WIRE-HERO**.
>
> **2026-06-08 update — image ORPHAN fixed.** P-LIST-IMAGE-WIRE-HERO landed at
> commit `252a8c3f4f6`. `upload_images` now reads listing tier first via the
> existing `_resolve_listing_intent` (read-side NULL-shop fallback accepted —
> distinct from the write-side state-sync slice). 5 ORM tests pass. The dead
> helper `_resolve_image_with_fallback` at `etsy_listing_publisher.py:472`
> stays in place because `test_p_enh_esty_190_phase2_orm.py` still references
> it — refactor-cleaner sweep deferred. Reprioritised queue slot 3 closed; the
> remaining slots are **slot 4 (live half of this diff — needs SSH/docker
> access)**, **slot 5 P-LIST-GALLERY-OVERRIDE**, **slot 6 P-LIST-PERSONALIZATION-OVERRIDE**, **slot 7 P-LIST-TAGS-MATERIALS**, **slot 8 P-LIST-MODEL-MISSING-FIELDS**.

---

## TL;DR

Two confirmed-bug findings that the code-level plan did not predict, plus
broad confirmation of the FAIL matrix. **Reprioritise: a new highest-priority
slice (P-PUB-RESOLVER-CASING-BUG) ships ahead of every S-1..S-6 in the plan.**

1. **CONFIRMED-BUG #1 (NEW)** — shop_ref case mismatch silently bypasses 100% of
   listing-tier overrides for the single non-stub listing on staging.
2. **CONFIRMED-BUG #2** — PCS.state never advances from `draft` (61/61 rows).
   Already queued as P-LIST-PUBLISH-STATE-SYNC; promote.
3. **Staging-state finding** — only 1 of 53 `multichannel.listing` rows
   (=1.9%) carries real override content; the other 52 are migration stubs.
   The whole listing-tier-override system is effectively unexercised.
4. **Etsy live GET blocked over XMLRPC** — decryption helper is a private
   method. Live half of the diff is gated on alternative access path; the
   code-side analysis below is the sent-side-only view.

---

## Probe target

Picked from staging via `product.channel.status` where `external_ref` is set
(=> a real Etsy listing was created), ordered by id desc:

| Field | Value |
|---|---|
| PCS row id | 83 |
| Etsy listing_id (`external_ref`) | **4518406711** |
| Odoo product.template id | 456 |
| Product name | "Personalized Coordinates Leather Tray, Where We Met Gift, …" |
| etsy.shop | JaHandmadeArt (id=10, etsy_api_shop_id=60752333) |
| PCS state | `draft` ← **bug #2 evidence** |
| PCS last_sync_at | False ← **bug #2 evidence** |

This is the **single product on staging** with both a real
`multichannel.listing` and a published Etsy listing.

---

## CONFIRMED-BUG #1 — `shop_ref` casing silently bypasses listing-tier overrides

`multichannel.listing` row id=62 exists for tmpl=456 with full marketing
content:

| Field on listing | Value |
|---|---|
| `shop_ref` | `'jahandmadeart'` |
| `etsy_shop_id` (typed M2O) | JaHandmadeArt (id=10) |
| `title` | "Personalized Coordinates Leather Tray - Testing 101" |
| `description` | (1439-char marketing copy — see JSON) |
| `etsy_who_made` | `collective` |
| `etsy_when_made` | `2020_2026` |
| `etsy_taxonomy_id` | "Trays & Platters [#1053]" |
| `video_attachment_id` | DIvid_dzkrni.mp4 |
| `state` | `ready` |

But `etsy.shop.name` on staging is `'JaHandmadeArt'` (CamelCase). The
publisher's `_resolve_listing_intent` does an exact ORM match
(`('shop_ref', '=', shop_name)` at `services/etsy_listing_publisher.py:515`),
so `'jahandmadeart' != 'JaHandmadeArt'` → empty match → falls through to
"shop_ref empty" fallback → no listing row at all → uses template/shop tiers.

### Impact

Every override the operator set on this listing is silently ignored.
The actual sent payload uses:
- title from `tmpl.name` (the long messy SEO name, not the cleaned-up one)
- description fell to the last hardcoded fallback (= tmpl.name again)
- when_made = `made_to_order` (template) instead of `2020_2026` (listing)
- taxonomy_id = 2172 (shop default) instead of #1053 (listing's Trays & Platters)
- video absent (listing.video_attachment_id never read)

Subtly worse: **operators currently have no way to detect this**. The
listing form shows the fields populated. The Etsy listing shows different
content. There's no warning anywhere that the override didn't apply.

### Root cause + fix shape

`services/etsy_listing_publisher.py:515` uses `=`. The shop_ref column is
plain `Char`. Three options ordered by safety:

1. **A — case-insensitive match in the publisher**: change `('shop_ref', '=', shop_name)`
   to `('shop_ref', '=ilike', shop_name)`. Smallest change. Risk: `=ilike` is
   pattern syntax; `shop_name` with `_` or `%` would behave oddly. Mitigate
   by `shop_name.replace('_', r'\_').replace('%', r'\%')`. Or do a sudo
   browse-and-Python-compare loop. ~5 LOC.
2. **B — normalise both sides on write**: add a `@api.depends('shop_ref')`
   computed-stored `_shop_ref_norm` field, search by it. ~30 LOC + 1
   migration. Heavier but type-safe.
3. **C — drop the Char shop_ref entirely** and rely on the typed
   `etsy_shop_id` M2O that already exists (added by P-ENH-ESTY-195). The
   resolver becomes `('etsy_shop_id', '=', shop.id)` — no string compare at
   all. This is the architecturally correct end state per ADR-015 but
   requires backfilling `shop_ref → etsy_shop_id` for the 9 other non-stub
   listings on staging (UAT seed data) and removing the resolver fallback
   chain. ~80 LOC + migration. Cleanest.

**Recommendation**: ship A as hotfix (one-line), queue C as the
architecturally-clean follow-up. Either way, this slice **must ship before
any of S-1..S-6** — they all add new listing-tier override fields whose
runtime effect is zero until the resolver match works.

**New slice ID**: **P-PUB-RESOLVER-CASING-BUG** (or `P-PUB-RESOLVER-TYPED-FK`
if we go straight to option C).

---

## CONFIRMED-BUG #2 — PCS.state never advances from `draft`

**61 of 61** `product.channel.status` rows on staging have `state='draft'` —
including row id=83 above whose `external_ref=4518406711` is a real live
Etsy listing.

Direct evidence: even on the highest-evidence published row, the state
machine and `last_sync_at` (False!) never reflect that Etsy received the
listing.

Already queued as **P-LIST-PUBLISH-STATE-SYNC** in tracker
(`Wave 2 UX follow-up`). Promote — it's the prerequisite for any operator
filter / dashboard / report that says "show me what's actually on Etsy."
Also blocks future runs of THIS diff, which had to fall back from
`state='published'` to `external_ref IS NOT NULL` as the proxy.

---

## Staging-state finding — listing-tier overrides barely exercised

| Counter | Count |
|---|---|
| `multichannel.listing` rows total | 53 |
| Of those, with any non-stub content (title OR shop_ref OR etsy_*) | 10 |
| Of those, with a corresponding PCS row carrying `external_ref` | **1** |
| Of those, where shop_ref matches `etsy.shop.name` case-correctly | **0** |
| `product.channel.status` rows | 61 |
| PCS rows with `external_ref` (= real Etsy listing exists) | 17 |

The denominator is so small that this diff cannot generalise beyond the one
sample. But the result on that one sample — "publisher bypassed the listing
overrides 100% via the casing bug" — combined with the architecture (every
listing in production will go through the same resolver) makes the casing
bug a hard finding.

---

## Per-field PASS/FAIL/WARN reconfirmation

The plan's matrix is reconfirmed *with one correction*: every PASS row was
PASS-in-theory but FAIL-in-practice on the sole sample due to the casing
bug. After the resolver fix, the PASS classifications hold. The table below
keeps the *theoretical* status (post-fix world) since the fix is queued.

| Etsy field | Status (theoretical) | Casing-bug-blocked? | Sent-tier on staging today |
|---|---|---|---|
| title | PASS | YES — listing value invisible | template |
| description | PASS | YES | hardcoded (template name) |
| who_made | PASS | YES (listing said "collective", same as template) | template |
| when_made | PASS | YES (listing said "2020_2026"; template said "made_to_order") | template |
| taxonomy_id | PASS | YES (listing said #1053; sent shop default 2172) | shop |
| shipping_profile_id | PASS | YES (listing empty; would have fallen to shop) | shop |
| video | PASS | YES (listing had video; ignored) | absent |
| is_supply | WARN | YES | hardcoded `False` |
| sku | FAIL | n/a | template (`KSK` — v2_suggested, status `non_canonical`) |
| price | FAIL | n/a | template raw 10.0 VND (pre-currency-conversion) |
| quantity | FAIL | n/a | template (qty_available=35) |
| tags | FAIL | n/a | template (13 tags — at Etsy's cap) |
| materials | FAIL | n/a | template (variant-derived; not introspected) |
| weight | FAIL | n/a | template raw `0.0` ← **also a data-quality issue, separate** |
| dimensions | FAIL | n/a | template (parsed from Size attribute) |
| main image | WARN | YES (listing.image_1920 ORPHAN — listing didn't set it here) | template |
| gallery images | FAIL | n/a | template (`tmpl.x_extra_image_ids` = 2 of 9 max) |
| return_policy_id | FAIL | n/a | shop default only |
| personalization (4 fields) | FAIL | n/a | template only (separate endpoint) |
| shop_section_id | FAIL (not-modelled) | n/a | omitted |
| production_partner_ids | FAIL (not-modelled) | n/a | omitted |
| type | FAIL (hardcoded) | n/a | hardcoded `'physical'` |

**Plan's claim that scope-limited slices (S-1 hero image, S-2 gallery,
S-3 personalization, S-4 tags/materials) close the gaps remains valid**, but
none of them deliver until the casing bug is fixed.

---

## Live Etsy GET — blocked, two unblock paths

The script attempted `etsy.shop._get_access_token` via XMLRPC and got:

```
<Fault 4: "Private methods (such as 'etsy.shop._get_access_token')
           cannot be called remotely.">
```

Odoo's XMLRPC layer refuses underscore-prefixed methods even for admin users.

Two unblock paths:

**Path α — staging shell access** (no code change):
```
ssh <staging-host>
docker exec -it <esty-staging-container> odoo shell -d esty_odoo19
>>> shop = env['etsy.shop'].browse(10)
>>> token = shop._get_access_token()
>>> client = ...
```
Then call Etsy GET from inside. Cleanest, but needs SSH/docker access.

**Path β — temporary non-underscore wrapper** (small code change):
Add a one-method `etsy.shop.action_dry_run_fetch_listing(self, listing_id)`
that's admin-gated (`_is_system()`) and returns Etsy GET JSON. Deploy it
once, run S-0 second half, then revert. ~40 LOC + 1 module bump.

**Recommendation**: defer the live half. The sent-side findings above
already justify the slice reprioritisation. We can run the live half *after*
the casing fix lands — at that point we'll have non-zero coverage of the
listing-tier override path and the diff will be more interesting.

---

## Reprioritised slice queue

| Order | Slice | State today | Why this order |
|---|---|---|---|
| 1 | **P-PUB-RESOLVER-CASING-BUG (NEW)** | not in tracker | Blocks the runtime effect of every existing PASS row and every S-1..S-6 candidate. ~5 LOC. Ship first. |
| 2 | **P-LIST-PUBLISH-STATE-SYNC** | queued (todo) | Without this, no diff or dashboard can tell what's actually on Etsy. Confirmed by bug #2. ~80 LOC. |
| 3 | **P-LIST-IMAGE-WIRE-HERO (was S-1)** | not yet dispatched | Closes the listing.image_1920 orphan. Tiny patch. Worth shipping with #1 in the same week. |
| 4 | **P-LIST-PUBLISH-DIFF-RUN II** (live half) | this slice extended | After #1 + #2 ship, re-run S-0 with live Etsy GET to validate end-to-end. |
| 5 | **P-LIST-GALLERY-OVERRIDE (was S-2)** | not yet dispatched | Closes the "no place to add multiple images" complaint. ~80 LOC. |
| 6 | **P-LIST-PERSONALIZATION-OVERRIDE (was S-3)** | not yet dispatched | Confirm Etsy 2026 endpoint shape before plumbing. Sample listing had `x_is_personalizable=True` + 1439-char instructions — the field IS used in production. |
| 7 | **P-LIST-TAGS-MATERIALS (was S-4)** | not yet dispatched | Sample listing had 13 tags (at Etsy's cap) — the override is genuinely useful for per-shop tag curation. |
| 8 | **P-LIST-MODEL-MISSING-FIELDS (was S-6)** | gated on live GET | shop_section_id / production_partner_ids / listing_type. Only ship if live GET shows Etsy filling these with defaults we want to control. |

---

## What stays out of scope (per owner directive 2026-06-08)

- price / quantity / sku / weight / dimensions / return_policy → product-level
  per ADR-014. Bug #2 (sample has `weight=0.0`) is a data-quality issue, not
  a publisher fix.
- Adding `last_sync_at` write on read-only ingest cron (separate concern from
  publish flow).

---

## Open questions for owner

1. **Casing-bug fix shape**: A (one-line `=ilike`), B (computed-norm column),
   or C (drop shop_ref string entirely, use typed `etsy_shop_id` M2O)?
   Recommendation: A as hotfix this week, C as architecture cleanup later.
2. **Live diff access**: SSH+docker (path α) or temporary wrapper method
   (path β)? Or defer entirely until after casing fix + state sync ship?
3. **Sample size**: should we backfill the other 9 non-stub listings with
   real test data + publish them to broaden the diff sample before bigger
   investments?
