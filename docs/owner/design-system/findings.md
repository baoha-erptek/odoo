# Design System Slices — findings

Append-only log of surprises, reviewer pushback, and follow-up items
that surfaced during P-DS-* slice execution.

---

## P-DS-3a — etsy.shop curation (2026-06-07)

### Reviewer pushback (verified, NOT applied)

Both `code-reviewer` and `security-reviewer` flagged a CRITICAL "ACL gap"
on the promoted Tier 1 fields. Verified independently against the model
source — the finding is based on a misread of Odoo field-vs-view groups
semantics.

| Reviewer claim | Actual behavior | Verdict |
|---|---|---|
| Promoting `etsy_api_shop_id` out of `groups="base.group_system"` view group exposes it to sales users | `etsy_api_shop_id` has `groups='base.group_system'` at the **field level** (`models/etsy_shop.py:50`). The ORM elides it from `read()` for non-system users regardless of view placement. | False CRITICAL — not blocking |
| Promoting `listing_currency_id` (M2O to res.currency) into Tier 1 exposes it to sales staff | Same — field has `groups='base.group_system'` at `models/etsy_shop.py:105`. View-level `groups=` cannot bypass ORM-level field groups. | False CRITICAL — not blocking |
| `active_source` ACL gap: sales users can now see API/email adapter state | `active_source` has NO field-level `groups=` in the model (line 228). It was **always** readable by anyone with `etsy.shop` model read ACL (granted to `base.group_user` per `security/ir.model.access.csv` line 2). P-DS-3a moves it from one visual group to another — read scope is unchanged. The only existing gate is a **write-level** gate in `write()` at `models/etsy_shop.py:394` (the C-ESY-002 / FR-017 system-admin write restriction), which is unaffected by this slice. | Not a P-DS-3a-introduced regression |

**Rationale for pushing back**: Odoo's field-level `groups=` is the
authoritative ACL gate for read access; view-level `groups=` is purely a
rendering hint. Demoting field-level groups by removing the view-level
wrapper does not weaken access control. The two existing fields with
field-level groups would have broken on `read()` calls long ago if the
semantics were what the reviewers described.

**Empirical confirmation deferred**: a Phase 2 test that opens the form
as a `base.group_user`-only user and asserts elided fields would prove
this conclusively. Not added in this slice (scope expansion); recorded
as MEDIUM follow-up below.

### Valid reviewer findings (out of P-DS-3a scope, queued as follow-ups)

| Finding | Severity | Follow-up |
|---|---|---|
| `auto_recovery` field has no write-level gate in `EtsyShop.write()` (only `active_source` is gated). Dev/sys-admin in `base.group_no_one` could toggle auto-recovery off via RPC without audit trail. Pre-existing — not introduced by P-DS-3a. | HIGH (security) | Spin out as **P-DS-3a-FOLLOWUP-AUTO-RECOVERY-WRITE-GATE** (add to tracker). Recommended fix: mirror the FR-017 `active_source` gate block in `write()` for `auto_recovery`, with a parallel entry in `etsy.shop.source.change.log` (or a sibling audit model). |
| Phase 2 tests assert XML substring presence — could pass on a structurally-broken view that happens to include the substring. | MEDIUM (test robustness) | Future hardening: parse `arch` with `lxml.etree` and walk the tree by element/attribute. Defer until a real false-positive shows up. |
| No Phase 2 tests asserting `base.group_user`-only user actually sees the elided behavior. | MEDIUM (coverage) | Same follow-up slice as auto_recovery — add one assert that `fields_view_get` for a sales-only user does not include `etsy_api_shop_id` / `listing_currency_id` in the arch. |

### Process notes

- **Code shipped before mockup** (P-DS-2-MVP-BACKPORT precedent). Mockup
  document `MOCKUP_etsy_shop.md` records decisions made, not spec being
  implemented. Acceptable for surgical 3-tier curation where the tier
  model itself is the spec.
- **Borderline Tier 2 fields stayed absent**: per owner gate 2026-06-07,
  `sync_audit_mode`, `etsy_oauth_token_expires_at`, `etsy_last_receipt_sync_at`
  are listed as "stay Tier 2 visible to BA Lead / sys admin." None of
  the three were rendered in the pre-P-DS-3a view; adding them would be
  scope expansion. They remain unrendered. If owner wants them surfaced,
  follow-up slice P-DS-3a-FOLLOWUP-TIER2-EXPOSE-DIAG covers it.
- **SCSS selector `.o_form_view[name="etsy.shop"]`** uses the same
  attribute pattern as the multichannel.listing / product.template
  selectors shipped in commit `a5ae4178eb2` (P-DS-2-MVP-BACKPORT). Pattern
  is validated by prior art; the etsy.shop notebook tab now picks up
  the purple active-tab border for visual consistency across Mu-styled
  forms.
