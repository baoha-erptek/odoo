# SKU Grammar — Canonical Specification

**Phiên bản:** v2.1 · **Last updated:** 2026-05-26 · **Status:** LIVING SPEC (canonical)
**Đối tượng:** Architect, Dev team, BA Lead (technical reference)
**Confluence (auto-sync):** space HEP — see push pipeline §10
**Supersedes:** `.0temp/deliverables/A3_grammar_v2_frozen.md` (v2.0 frozen 2026-04-14)
**Companion audit trail (historical):** `.0temp/deliverables/A1_sku_grammar_proposal.md` (v0/A1), `.0temp/deliverables/A2_devils_advocate_critique.md` (red-team review), `.0temp/deliverables/C1_redteam_final.md` (final red-team)

---

## 0. TL;DR

SKU Grammar v2.1 defines the canonical SKU format for the multichannel product hub:

```
<FAM3>-<MAT2>-<SIZE>[-<VAR2>]
```

- `FAM3` — 3-letter family code (22 families + MSC fallback; §2)
- `MAT2` — 2-letter material code (§3)
- `SIZE` — 2-6 character size token, namespace-scoped per family (§4)
- `VAR2` — optional 2-letter permanent product-level variant (color); per-order personalization NOT in SKU (§5)

**v2.1 vs v2.0 (frozen 2026-04-14):** DSGN segment + `sku.design.code` registry removed (§9 amendment log).

**Example SKUs:**

| Family | Example SKU | Decoded |
|---|---|---|
| Mug | `MUG-CR-F11` | Mug, ceramic+chrome combo, 11oz |
| Mug with color variant | `MUG-CR-F15-BK` | Mug, ceramic+chrome, 15oz, black |
| Ring Dish | `RDS-CE-SQ` | Ring Dish, ceramic, square shape |
| Apron | `APR-TX-AM` | Apron, textile, apparel size M |
| Doormat (rectangular) | `DMT-TX-R30X18` | Doormat, textile, 30"×18" |

**Length budget:** ≤14 chars (was ≤20 in v2.0 — tightened after DSGN removal).

---

## 1. Implementation status (as of 2026-05-26)

| Component | Spec | Implementation | Status |
|---|---|---|---|
| Family classifier `evaluate(name) -> FAM3` | §2 | `custom_addons/multichannel_hub_core/services/sku_grammar_v2.py` lines 29-52 | ✅ Working (frozen tuple — to be DB-driven per §2.5) |
| Wizard preview `sku_v2_suggested_preview` | §1 | `product_creation_wizard.py` lines 71-78 | ✅ Working (FAM3 only) |
| Per-product canonicalise wizard (legacy ↔ v2) | §6 | `product.sku.canonicalise.wizard` | ✅ Working (per-product drift fix) |
| Managed taxonomy models (Family + variant attributes) | §2.5 | Not built | ⚠️ MP006 slice `P-HUB-SKU-BUILDER` (todo) — foundational data layer for the wizard |
| `<FAM3>-<MAT2>-<SIZE>` builder wizard (multi-step) | §1 | Not built | ⚠️ MP006 slice `P-HUB-SKU-BUILDER` (todo) |
| Validator on create | §7 | Not built | ⚠️ MP006 slice `P-HUB-V2-VALIDATE-ON-CREATE` (todo) |
| Missing-info handler | §8 | Not built | ⚠️ MP006 slice `P-HUB-MISSING-INFO-WIZARD` (todo) |
| Color normalization dictionary | §5 | Not enforced in code yet | ⚠️ Spec-only |
| Catalog backfill from Excel | §11 | Manual today | ⚠️ Future P-HUB-BULK-CANONICALISE |

Excel catalog `.0temp/raw/[2025] Product Catalog.xlsx` is currently **100% legacy SKUs** (sampled: MUG-1, TAT1, APR1, SQR1, etc.). Migration to v2.1 happens per-product via the canonicalise wizard (or in bulk via future slice).

---

## 2. Family list — 22 families + MSC (priority-ordered, most-specific first)

Apply regex rules in order; **first match wins**.

| Priority | Code | Name | Regex (on normalized product_name) | Default route | Default material |
|---|---|---|---|---|---|
| 1  | RDS | Ring Dish            | `\bring\b.{0,20}\b(dish\|holder\|tray)\b`                  | in_house | CE |
| 2  | TRK | Trinket Tray/Box     | `\b(trinket\|keepsake)\s+(tray\|box\|dish\|holder)\b`      | in_house | CE |
| 3  | JWD | Jewelry Dish         | `\bjewel(ry\|lery)\s+(dish\|holder\|tray\|box)\b`          | in_house | CE |
| 4  | PHF | Photo/Memorial Frame | `\b(photo\|picture\|memorial)\s+frame\b`                   | in_house | WD |
| 5  | CBD | Cutting Board        | `\b(cutting\s+board\|charcuterie)\b`                       | in_house | WD |
| 6  | WCH | Wind Chime           | `\bwind\s*chime\b\|\bchime\b`                              | in_house | MT |
| 7  | MUG | Mug                  | `\bmug\b`                                                  | tbd      | CR |
| 8  | TUM | Tumbler              | `\btumbler\b`                                              | tbd      | MT |
| 9  | TAT | Temporary Tattoo     | `\btemporary\b.*\btattoo\b\|\btattoo(s)?\b`                | gearment | PA |
| 10 | DMT | Doormat              | `\b(doormat\|door\s+mat)\b`                                | gearment | TX |
| 11 | RUG | Rug                  | `(?<!door[\s-])\brug(s)?\b`                                | gearment | TX |
| 12 | ORN | Ornament             | `\bornament(s)?\b`                                         | in_house | CE |
| 13 | HKF | Handkerchief         | `\bhand(ker)?chief\b\|\bhankie\b\|\bhanky\b`               | in_house | TX |
| 14 | APR | Apron                | `\bapron(s)?\b`                                            | gearment | TX |
| 15 | PIL | Pillow/Cushion       | `\b(pillow\|cushion\|pillowcase)\b`                        | gearment | TX |
| 16 | BAG | Bag/Tote/Bandana     | `\b(tote\|canvas\s+bag\|bandana\|backpack\|duffel)\b`      | gearment | TX |
| 17 | SGN | Sign/Flag            | `\b(metal\s+sign\|wood(en)?\s+sign\|yard\s+sign\|flag\|banner)\b` | in_house | MT |
| 18 | KCH | Kitchen Ware         | `\b(recipe\s+dish\|recipe\s+holder\|spoon\s+holder\|kitchen\s+towel)\b` | in_house | CE |
| 19 | APP | Apparel              | `\b(t-?shirt\|hoodie\|tank\s+top\|sweatshirt\|tee\|sleep\s*shirt\|sleepshirt\|sweater)\b` | gearment | TX |
| 20 | KSK | Generic Keepsake     | `\b(keepsake\|wedding\s+gift\|proposal\s+gift\|sympathy\s+gift\|memorial\s+gift)\b` | in_house | CE |
| 21 | CDS | Ceramic Dish         | `\bceramic\s+(dish\|plate\|bowl)\b\|\bceramic\b`           | in_house | CE |
| 22 | WDS | Wooden Dish          | `\bwooden\s+(dish\|plate\|bowl)\b\|\bwood(en)?\b`          | in_house | WD |
| 23 | MSC | Misc (fallback)      | anything not matching above                                | tbd      | MX |

Machine-readable copy: `.0temp/deliverables/D1_product_taxonomy_SKU.xlsx` sheet `family_rules` (canonical when out of sync with this table — owner edits Excel first, then propagates here).

---

## 2.5 Managed taxonomy (CRUD models)

**Decision D-V2-6 (2026-05-26)**: replace the hardcoded Python tuple in `services/sku_grammar_v2.py` with **DB-managed taxonomy** so BA / operations can add/edit/retire families and variant codes without a code release.

**Hybrid architecture** — Family gets a dedicated model (carries regex + route + default-material metadata that doesn't fit a generic attribute); Material / Shape / Size / Fluid oz / Apparel size / Color reuse Odoo's stock `product.attribute` + `product.attribute.value` (per §8) with a small `x_code` field added via `_inherit`.

| Segment | Model | Stock or new? | CRUD location |
|---|---|---|---|
| FAM3 (Family) | `mhc.sku.family` | NEW (mhc) | Settings → SKU → Families (custom list + form) |
| MAT2 (Material) | `product.attribute` "Material" + values | stock + 1 inherit field | Inventory → Products → Attributes |
| Shape | `product.attribute` "Shape" + values | stock + 1 inherit field | same |
| Size (dim) | `product.attribute` "Size" + values | stock + 1 inherit field | same |
| Fluid oz | `product.attribute` "Fluid oz" + values | stock + 1 inherit field | same |
| Apparel size | `product.attribute` "Apparel size" + values | stock + 1 inherit field | same |
| VAR2 (Color) | `product.attribute` "Color" + values | stock + 1 inherit field | same |

### `mhc.sku.family` fields

| Field | Type | Notes |
|---|---|---|
| `code` | Char(3), required, indexed, UNIQUE (`init()` mirror per `project_sql_constraints_drift`) | e.g. `MUG`, `APR`, `RDS` |
| `name` | Char, required | Display name, e.g. "Mug" |
| `priority` | Integer, required, default 100 | Lower = matched first; mirrors §2 priority column |
| `regex_pattern` | Char, required | Stored uncompiled; compiled lazily on read |
| `default_route` | Selection [`in_house`, `gearment`, `tbd`] | Per §6 routing table |
| `default_material_id` | Many2one `product.attribute.value` (domain on Material attr) | Default MAT2 hint for builder wizard |
| `active` | Boolean, default True | Standard Odoo soft-delete |
| `_order` | `'priority, code'` | Stable ordering for evaluate() |

### `product.attribute.value` inherit (additive)

| Field | Type | Applies to | Notes |
|---|---|---|---|
| `x_code` | Char(6), indexed | all SKU-bearing attribute values | The 2-letter / 6-char code used in SKU (e.g. `CE`, `F11`, `R30X18`). Empty for non-SKU attributes. |
| `x_namespace` | Selection [`shape`, `dim`, `rect`, `fluid_oz`, `apparel`] | Size-family attribute values | Per §4. Used by SIZE parser to disambiguate. |
| `x_applicable_family_ids` | Many2many `mhc.sku.family` | Size-family attribute values | Family-gating per §4. Empty = applies to all. |

### Refactor of `services/sku_grammar_v2.py`

```
def evaluate(name: str, env) -> tuple[str, str]:
    families = env['mhc.sku.family'].sudo().search([], order='priority, code')
    for fam in families:
        if re.search(fam.regex_pattern, name, re.IGNORECASE):
            return (fam.code, fam.code)
    return ('MSC', 'MSC')
```

Compiled-regex cache keyed by `(family.id, family.write_date)` to avoid recompiling on every call. Frozen tuple in source becomes the seed data only.

### Seeds

- `data/sku_family_seed.xml` (`noupdate=1`) — 22 rows from §2 table, priorities 1–22.
- `data/sku_attribute_seed.xml` (`noupdate=1`) — 7 `product.attribute` rows (Family-tag, Material, Shape, Size, Fluid oz, Apparel size, Color) + ~55 `product.attribute.value` rows (codes from §3 / §4 / §5).

Owner edits via UI persist (`noupdate=1`). Seed only re-applies on `--init`.

### CRUD ACL

| Group | Read | Write | Notes |
|---|---|---|---|
| `base.group_user` | ✅ | ❌ | All users can see the taxonomy |
| `multichannel_hub_core.group_ba_user` | ✅ | ✅ | BA can add new families / codes |
| `base.group_system` | ✅ | ✅ | Admin override |

---

## 3. Material codes (MAT2)

| Code | Material | Detected via |
|---|---|---|
| `CE` | Ceramic | `ceramic`, `porcelain` |
| `WD` | Wood | `wood`, `wooden`, `bamboo`, `oak` |
| `PA` | Paper / Card | `paper`, `card`, tattoo default |
| `TX` | Textile | `cotton`, `polyester`, `linen`, rug default |
| `MT` | Metal | `metal`, `brass`, `steel` |
| `CR` | Ceramic + chrome combo | mug default |
| `MX` | Mixed / Unknown | fallback |

---

## 4. SIZE encoding

Three disjoint namespaces, prefix collision killed. SIZE parser detects namespace by context (family-gated).

| Namespace | Pattern | Applies to | Examples |
|---|---|---|---|
| Shape-class | `SQ/HT/OV/LSQ/WV/AR/BW/RD` | Source has shape only, no dimension | `SQ` = square, `HT` = heart |
| Dimensional | `S<digits>` for square-ish sides in inches×10 (drop decimal) | Dish family dimensional sizes | `S35` = 3.5" square, `S41` = 4.1" |
| Rectangular | `R<W>X<H>` (inches) | Rectangles | `R30X18` |
| Fluid-ounce | `F<digits>` | Mug / tumbler capacity | `F11` = 11oz, `F15` = 15oz, `F20` = 20oz |
| Apparel | `A<letter>` | Apparel S/M/L/XL → `AS/AM/AL/AX/AXX` | `AM` = apparel medium |

**Family-gated rules:**
- Apparel families → only `A*` codes
- Dish families → only shape-class or `S*` codes
- Mug/Tumbler → only `F*` codes
- Doormat → typically `R*` (rectangular)
- No cross-family size codes

---

## 5. VAR2 — permanent product-level variants

`VAR2` is OPTIONAL — used only for permanent shop-level variants (e.g. color choice that's a fixed product attribute, not customer personalization).

### 5.1 Color palette (12-slot canonical)

| Canonical | Maps from (examples) |
|---|---|
| `BK` | black, jet black, coal |
| `WH` | white, ivory, cream |
| `PK` | pink, light pink, blush, rose |
| `BL` | blue, light blue, navy blue, royal blue |
| `GY` | grey, gray, sport grey, heather grey |
| `NV` | navy, midnight |
| `SL` | silver, chrome |
| `PU` | purple, violet, lilac, lavender |
| `GR` | green, olive, sage, mint |
| `RD` | red, burgundy, crimson |
| `OR` | orange, peach, coral |
| `YW` | yellow, gold, mustard |
| _(omit)_ | "keep the original", empty, blank → no VAR2 suffix |

Anything not matching → MSC-COLOR bucket (manual review).

### 5.2 What is NOT VAR2

- **Per-order personalization** (custom text, photos uploaded by buyer) — lives on `sale.order.line.personalization_note` + `sale.order.line` design files (Design Files workflow). NEVER in SKU.
- **Side / orientation** (left vs right hand engraving) — physically meaningful but rare; treated as personalization for now.
- **Per-design uniqueness** (e.g. "Roses pattern" vs "Tulips pattern") — handled via product attributes (`Design Name` no_variant tag, see §8) or as separate products if SKU-level distinguishability is genuinely needed.

---

## 6. Routing table

| Family | Route | Rationale |
|---|---|---|
| RDS, TRK, JWD, CDS, WDS, CBD, WCH, ORN, HKF, PHF, KCH, KSK, SGN | in-house MO | Require physical handling, engraving, custom cutting — team capability confirmed by PD feedback. |
| DMT, RUG, TAT, APP, APR, PIL, BAG | Gearment POD | Print-on-demand economics, no warehouse handling, Gearment catalogue match. |
| MUG, TUM | **TBD** | Small enough for in-house heat-press IF tooling exists (PD mentioned "ép nhiệt"); Gearment sublimation also viable. Owner-to-decide per SKU via `x_gearment_sku` field. |
| MSC | per-item | Manual triage. |

ADR-010 (Hybrid Dropship + MTO) — `x_gearment_sku` field on `product.template` overrides the family default route when set.

---

## 7. Validator (planned — `P-HUB-V2-VALIDATE-ON-CREATE`)

### 7.1 Regex

```
^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)(-[A-Z]{2})?$
```

Length-bounded: 8 ≤ len ≤ 14 chars.

### 7.2 Validation modes

- **Soft-warn (default):** Non-v2 SKU passes with `_logger.warning` + UI banner; persisted as `x_sku_v2_status='ba_approved_legacy'`. Backwards-compat with existing legacy catalog.
- **Hard-fail:** Non-v2 SKU raises `UserError`. Configurable via ICP `multichannel_hub.sku_v2_enforce_mode='hard'`. Owner default during initial rollout: soft.

### 7.3 Opt-out for legacy

Existing products with legacy SKU (`MUG-1`, etc.) get `x_sku_v2_status='ba_approved_legacy'` automatically on first wizard validate — no migration burst required. Bulk re-canonicalisation happens via separate slice `P-HUB-BULK-CANONICALISE` (future).

---

## 8. Attribute taxonomy (Odoo `product.attribute`)

| Attribute | Values | `create_variant` | Notes |
|---|---|---|---|
| Material | CE/WD/PA/TX/MT/CR/MX | always | Drives BoM component |
| Shape | SQ/HT/OV/LSQ/WV/AR/BW/RD | always | Dish families only |
| Size (dim) | S35/S41/R30X18/... | always | Populated per family |
| Fluid oz | F11/F15/F20 | always | MUG/TUM only |
| Apparel size | AS/AM/AL/AX/AXX | always | APP only |
| Color | 12-code palette | dynamic | Avoid combinatorial explosion |
| Family (tag) | 22 codes + MSC | no_variant | Classification only |
| Occasion (tag) | wedding/birthday/memorial/... | no_variant | Analytics, not variants |
| Recipient (tag) | mom/sister/bride/... | no_variant | Marketing cohort, not variants |
| Personalization Required | yes/no | no_variant | Indicator only; content is per-SO-line |
| Design Name (tag) | free-text design label | no_variant | Replaces old DSGN field — human-readable, not in SKU |

**Per-order personalization** stored on `sale.order.line`:
- `personalization_note` (Text)
- `personalization_file_gdrive_id` (Char per ADR-006)
- `design.file` Many2many → GDrive links + 3-state lifecycle (Pending/Approved/Rejected)

---

## 9. Amendment log

### v2.1 — 2026-05-26 (this revision)

**Change:** Remove `DSGN` segment and `sku.design.code` registry from the grammar.

**Old grammar (v2.0):**
```
<FAM3>-<MAT2>-<SIZE>-<DSGN>[-<VAR2>]
DSGN = D#### (4-digit numeric, auto-sequence from sku.design.code registry)
Length ≤ 20 chars
Example: MUG-CR-F11-D0001-BK
```

**New grammar (v2.1):**
```
<FAM3>-<MAT2>-<SIZE>[-<VAR2>]
Length ≤ 14 chars
Example: MUG-CR-F11-BK
```

**Rationale:**
1. **Excel catalog reality**: 100% of existing SKUs (sampled 6 rows × 6 sheets) have ZERO `D####` segment. Owner has been operating successfully without a design code in SKU since inception.
2. **Design is per-order, not per-product**: in the MTO + customization business model, each Etsy order line has unique design files. Marketing uploads design files at `sale.order.line` level, not `product.template`. Baking a design ID into the product SKU does not match reality.
3. **Original DSGN motivation** (R3 HIGH from A2 review): "HRT-vs-HART alpha mnemonic collision". Resolved by switching to numeric `D####`. But the collision only exists if alpha mnemonics are used in design distinguishing. By NOT using design codes in SKU at all, R3 is naturally void.
4. **Variant differentiation** already covered by VAR2 (color) + product attributes (Material/Shape/Size/Fluid oz) → product.product variant SKUs auto-generated by Odoo.
5. **Permanent distinct designs** (rare — most products are customizable templates) can be modeled as separate `product.template` records with distinct `default_code` SKUs (manually disambiguated by BA when creating).
6. **Engineering cost saved**: ~180 LOC + 1 model + 1 migration + ongoing curation (~4-8 hr/week per A3 §10 R10 estimate) eliminated.

**Slice impact** (MP006 tracker Phase 3b):
- ❌ Removed: `P-HUB-DESIGN-CODE-REGISTRY` (was ~180 LOC)
- ⬇️ Simplified: `P-HUB-SKU-BUILDER` (6 step → 4 step, ~280 LOC → ~180 LOC)
- ⬇️ Simplified: `P-HUB-V2-VALIDATE-ON-CREATE` (simpler regex, no registry check, ~80 LOC unchanged)
- ⬇️ Simplified: `P-HUB-MISSING-INFO-WIZARD` (3 case → 2 case, ~120 LOC → ~90 LOC)

Total: 4 slices × ~660 LOC → **3 slices × ~350 LOC**. Net savings ~310 LOC.

**Approval:** Owner directive 2026-05-26 (Telegram session). Captured in MP006 tracker D7 (amendment).

### v2.0 — 2026-04-14 (frozen, now superseded)

Original spec from `.0temp/deliverables/A3_grammar_v2_frozen.md`. Folded in 5 BLOCKER/HIGH findings from A2 critique. Added DSGN registry as solution to R3 HIGH. Post-extraction v2.0.1 update added 6 families (APR, PIL, BAG, SGN, KCH, KSK) and HKF spelling fix to bring MSC bucket from 13.9% → 1.5% (pre-flight gate passed).

### v1.0 / A1 — 2026-04-13 (initial proposal)

See `.0temp/deliverables/A1_sku_grammar_proposal.md`. Used alpha mnemonics for design (HRT, HART) — rejected via A2 R3 critique.

---

## 10. Confluence sync pipeline

This doc lives at `docs/owner/SKU_GRAMMAR.md` in the repo. Confluence is the read-friendly mirror in space HEP.

### 10.1 How auto-sync works

```
git commit → .githooks/post-commit hook fires
            → if any docs/owner/**/*.md changed
            → background: python3 .claude/scripts/push_owner_confluence.py
            → push script computes content hash per page
            → pushes only pages whose hash differs from last sync
            → updates .docs/tasks/_owner_confluence_*.json mapping
```

### 10.2 One-time setup (per developer / per server)

```bash
git config core.hooksPath .githooks
chmod +x .githooks/post-commit
```

### 10.3 Manual push

```bash
python3 .claude/scripts/push_owner_confluence.py --dry-run   # preview only
python3 .claude/scripts/push_owner_confluence.py             # live push
```

### 10.4 Adding a new doc to the sync

Edit `.claude/scripts/push_owner_confluence.py` `PAGES` list:

```python
PAGES = [
    ...,
    ("MY_NEW_DOC.md", "Page Title on Confluence", False),  # False = child of HEP root
]
```

Auto-creates the page on first push, updates on subsequent runs.

---

## 11. Out of scope (deferred)

- **Bulk re-canonicalisation of Excel catalog → v2.1 SKUs** — separate slice `P-HUB-BULK-CANONICALISE` (future).
- **Etsy outbound sync of canonicalised SKUs** — hook exists in `EtsyInventoryPusher`; will activate after `P-HUB-V2-VALIDATE-ON-CREATE` merges. Separate slice `P-HUB-V2-ETSY-SYNC`.
- **Migration of products already published on Etsy with legacy SKUs** — needs coordination with Etsy listing update; separate slice `P-HUB-LEGACY-ETSY-RECANONICAL`.
- **UI splitting full SKU into FAM/MAT/SIZE/VAR read-only badges on product form** — cosmetic; defer.

---

## 12. Decision log (open questions for owner)

| # | Decision | Default proposal | Status |
|---|---|---|---|
| D-V2-1 | DSGN registry needed? | ❌ Skip per v2.1 amendment | **DECIDED 2026-05-26** |
| D-V2-2 | Validator default mode | Soft-warn (backwards-compat) | Pending |
| D-V2-3 | `product.sku.builder.wizard` vs current `product.creation.wizard`: replace or coexist? | Coexist 1 sprint, then sunset legacy | **DECIDED 2026-05-26** |
| D-V2-4 | Family override UI in builder wizard | Dropdown of all active `mhc.sku.family` rows (ordered by priority) | **DECIDED 2026-05-26** |
| D-V2-5 | (Originally about design code timing — voided by v2.1 amendment) | N/A | Voided |
| D-V2-6 | FAM3 / MAT2 / SIZE storage: hardcoded vs DB-managed? | Hybrid — `mhc.sku.family` dedicated model + `product.attribute` reuse for MAT/Shape/Size/Color (§2.5) | **DECIDED 2026-05-26** |

---

## 13. Cross-references

- Current code: `custom_addons/multichannel_hub_core/services/sku_grammar_v2.py`
- Wizard (current): `custom_addons/multichannel_hub_core/wizards/product_creation_wizard.py`
- Canonicalise wizard: `custom_addons/multichannel_hub_core/wizards/product_sku_canonicalise_wizard.py`
- MP006 tracker Phase 3b: `.claude/plans/006-master-plan-tracking.md`
- ADR-014 (central product hub): `specs/006-master-plan/adrs/ADR-014-central-product-hub.md`
- Machine-readable family rules: `.0temp/deliverables/D1_product_taxonomy_SKU.xlsx` sheet `family_rules`
- Historical audit trail:
  - `.0temp/deliverables/A1_sku_grammar_proposal.md` (v1.0 proposal)
  - `.0temp/deliverables/A2_devils_advocate_critique.md` (R1-R12 critique)
  - `.0temp/deliverables/A3_grammar_v2_frozen.md` (v2.0 frozen — superseded by this doc)
  - `.0temp/deliverables/C1_redteam_final.md` (final red-team review)
- UAT findings that prompted v2.1: `docs/owner/UAT_FINDINGS_2026-05-26.md` F4
