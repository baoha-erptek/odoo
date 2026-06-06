# Spec 012 — Findings

## 2026-06-06 — P-SPEC-LISTING-MODEL-SPLIT slice landed (doc-only)

**Branch**: `feature/006-master-plan-coding`
**Manifest**: no change (doc-only slice; no code shipped)
**Deliverables**:
- `specs/006-master-plan/adrs/ADR-015-listing-model-split.md` — Option C: separate `multichannel.listing` model with M2O to `product.template`, channel-agnostic, lives in `multichannel_hub_core`. ADR-013 (`etsy.listing` read-only mirror) and ADR-014 (Odoo as central product hub) preserved.
- `specs/012-listing-model-split/spec.md` — 10 user stories (US1-US10) + per-slice acceptance criteria for the 7 Wave-2 listing-parity slices.
- `specs/012-listing-model-split/tasks.md` — task skeleton (T001-T004 for parent slice + T010-T020 for `P-LIST-MODEL` foundation + T101-T706 for the 7 Wave-2 child slices, each with their own Phase 1-9 task list).

**Decisions captured in ADR-015**:
- Model name `multichannel.listing` (not `hatafa.listing` as proposed in `docs/jira/in-progress-2026-06-04.md` — Odoo-conventional + channel-agnostic per ADR-003).
- Three-layer field resolution chain: `multichannel.listing.<field>` override → `product.template.x_<field>` fallback (when one exists) → `etsy.shop.default_<field>` shop default.
- BA owns `product.template` (RW), Marketing owns `multichannel.listing` (RW). BA gets read-only on listings, Marketing gets read-only on products. ACL surface formalized in ADR-015 §4.
- Backfill on existing data is non-destructive: every template with an active `etsy.listing` or `product.channel.status[channel.code=etsy]` row gets a stub `multichannel.listing` row with all override fields null. Zero behavior change at upgrade time.
- Per-channel marketing overrides (Title / Description / Image) ride in on the same model — `P-ENH-ESTY-190` (Wave 3) becomes "fill in the override columns on `multichannel.listing`" instead of a new model.

**Out-of-scope flags** (documented in spec.md):
- Per-channel pricing override — owned by ADR-010 + SKU drift policy.
- Amazon / website channel listing rows — model is channel-agnostic so they slot in later without redesign.
- Excel catalog moving into Odoo as write-surface — recurring import stays canonical per ADR-014 §3.

**Owner-gated next**: T004 (owner sign-off on ADR-015) before `P-LIST-MODEL` implementation slice begins. Owner DM sent via Telegram (msg-id pending after commit).

**Risks documented**:
- Volume sanity check: 1 product × 3 channels × 2 shops/channel ≈ 6 rows; current catalog ~3 000 products → ~18 000 listing rows. Well inside healthy O2M.
- Operator confusion risk on "where do I set the Etsy category?" → mitigated by mandatory `HUONG_DAN_TAO_SAN_PHAM_VN.md` §6.5 ("Sản phẩm vs Listing") update in `P-LIST-MODEL` T018.

**Dispatch ordering recommendation** (in tasks.md):
1. P-SPEC-LISTING-MODEL-SPLIT (this slice — doc only)
2. P-LIST-MODEL (foundation — model + ACL + backfill + publisher wiring)
3. Wave-2 children in Etsy "How to Create a Listing" article order, starting with P-LIST-VIDEO.
