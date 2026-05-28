# P-DOCS-HUONG-DAN-V12 — Plan

**Slice**: P-DOCS-HUONG-DAN-V12
**Branch**: `feature/006-master-plan-coding`
**Owner**: Dev (orchestrator) + BA review
**State (entry)**: `todo`
**Dependencies (satisfied)**: P-HUB-SKU-AUTODERIVE ✓ + all P-PUB-* ✓ (9 slices, 2026-05-27/28)
**Type**: doc-only — abbreviated 9-phase loop (skip Phases 2 RED, 4-security, full 8)

---

## 1. Scope & Non-Goals

### Scope — `docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` v1.1 → v1.2

- **Delete** old §3 (two-path comparison table), §4 (Classic Wizard walkthrough), §5 (SKU Builder Wizard 4-step) — wizards are hidden (`active="False"` per P-HUB-SKU-AUTODERIVE).
- **Rewrite** new §3 — single canonical path: standard Odoo **Products** menu → form chuẩn → SKU tự sinh từ Danh mục + Biến thể.
- **Fold** old §6 (validator v2 grammar) into new §3 as a 2–3 sentence note (no deep grammar exposition).
- **Renumber** §7→§5, §8→§6, §9→§7.
- **Replace** old §10 (FAQ) with new §10 covering 9 publish-readiness fields (see §3 below); shift old FAQ to §11.
- **Refresh** UAT TC-001..TC-018 — Wizard-specific TC-008..TC-012 become obsolete; new TC-008..TC-015 cover the 9 new fields.
- **Bump** header: version 1.1 → 1.2, date 2026-05-28, new changelog blockquote.

### Scope — `docs/owner/FLOW_TAO_SAN_PHAM_VN.md` v1.1 → v1.2 (sync)

- Header bump (version/date/changelog).
- Tổng quan: drop "Có hai cách... 1. Wizard cổ điển ... 2. SKU Builder Wizard"; replace with single canonical path mention.
- SKU auto-derive in business voice (no Odoo internals).
- Mirror §10 additions at business-flow altitude (one-line per field family).
- FAQ: drop wizard-specific questions, add SKU auto-derive + legacy-SKU FAQs.

### Non-goals

- No code changes.
- No screenshots (text-only; screenshot refresh deferred to a sibling slice).
- No translation of UI labels — Vietnamese strings already live.
- No deep technical exposition (validator grammar, ORM internals).

---

## 2. Voice/Audience Contract — Plain-View Rule

Owner docs follow `feedback_end_user_docs_plain_view` strictly:

- **Forbidden in body text**: `multichannel_hub_core`, `etsy_integration`, `@api.onchange`, `default_code`, `Char`, `Many2one`, `group_ba_user`, `sudo()`, `P-HUB-*`, `P-PUB-*`, `ADR-*`, `REQ-*`, agent names (planner/architect/tdd-guide), Odoo internal model names.
- **Allowed only in changelog blockquote at top**: version-framing ("v1.1 → v1.2 changed X because Y").

### Risk flagged from v1.1 — header line 5

v1.1 line 5 reads:
> **Hệ thống:** Odoo 19 — module `multichannel_hub_core` + `etsy_integration`

This **violates** the plain-view rule. Decision pre-Phase-3: **delete the line entirely** (cleanest) — or generalize to "Hệ thống quản lý sản phẩm tích hợp". Orchestrator to confirm at Phase-3 start; document choice in commit body.

### Acceptable vs. unacceptable phrasing

| Bad (Odoo internals) | Good (plain business) |
| --- | --- |
| Ô `default_code` tự điền | Mã SKU tự điền |
| `product.tag` chuẩn của Odoo | Trường Tags (chuẩn của hệ thống) |
| `@api.onchange` trên form sản phẩm tự generate | Khi BA chọn Danh mục, hệ thống tự gợi ý Mã SKU |
| Gọi `_check_ba_or_raise()` | (no mention of internals) |

---

## 3. Section-by-Section Diff — `HUONG_DAN_TAO_SAN_PHAM_VN.md`

### Header & changelog
- Line 3: `Phiên bản: 1.1` → `1.2`; `Ngày: 2026-05-26` → `2026-05-28`.
- Line 5 (Hệ thống): delete or generalize per §2 risk note.
- Line 10 changelog: replace v1.1 blockquote with v1.2 summary — pivot to standard Products menu, SKU auto-derive, new §10 with 9 publish fields, refreshed UAT.

### Mục lục (lines 14–27)
- Remove items 3 (Two paths), 4 (Cách 1A), 5 (Cách 1B).
- Renumber items 6→3 (note: §6 validator content folds into new §3), 7→5, 8→6, 9→7.
- **New item 10**: "Thêm các trường mới — Tags, Cá nhân hóa, Vật liệu, Kích thước".
- Old §10 (FAQ) → §11; §11 (UAT) → §12; §12 (Báo lỗi) → §13.

### §1 Yêu cầu trước khi bắt đầu (lines 31–40)
- Light edit on line ~37: change "Mã SKU nội bộ (nếu đã có) hoặc để hệ thống gợi ý" → "Hệ thống sẽ tự gợi ý Mã SKU dựa trên Danh mục + Biến thể; BA có thể sửa lại nếu cần".
- Otherwise unchanged.

### §2 Vai trò và quyền (lines 44–52)
- Keep as-is.

### NEW §3 — Cách tạo sản phẩm (replaces old §3 + §4 + §5, lines 59–226)
- Intro: "Mở menu **Sản phẩm** → bấm **Tạo mới**. Hệ thống dùng form chuẩn của Odoo — không cần mở Wizard riêng."
- Steps:
  1. Điền Tên sản phẩm (tiếng Anh).
  2. Chọn Danh mục sản phẩm.
  3. Thêm Biến thể (Chất liệu, Kích thước, …) nếu cần.
  4. **Mã SKU tự điền** từ Danh mục + Biến thể (ví dụ `MUG-CR-F11`). BA xem lại; có thể chỉnh tay.
  5. Điền giá USD, mô tả, ảnh (tuỳ chọn).
  6. Bấm **Lưu**.
- Note about SKU legacy: "Sản phẩm cũ có mã legacy — BA gõ tay vào ô Mã SKU, hệ thống giữ nguyên."
- Note about validator (folds old §6): "Mã SKU tự động kiểm tra theo quy chuẩn nội bộ; sản phẩm cũ không bị ảnh hưởng."
- Note about difference vs. Wizards: "Trước đây có Wizard riêng (Classic + SKU Builder); nay form sản phẩm chuẩn đã đủ — BA không cần mở Wizard nào."

### Old §6 validator (lines 229–264)
- Delete; key bits folded into §3 note above.

### §5 / §6 / §7 — Excel, SKU Drift, Publish (renumbered)
- Keep content; section numbers only.

### NEW §10 — Thêm các trường mới
Intro: "Hệ thống bổ sung 9 trường mới giúp sản phẩm đủ thông tin khi đăng lên Etsy. Các trường nằm trên form sản phẩm chuẩn (không cần Wizard)."

- **§10.1 Tags (Từ khoá tìm kiếm)** — tối đa 13 tags, mỗi tag ≤ 20 ký tự; gửi lên Etsy giúp tìm kiếm.
- **§10.2 Cá nhân hoá** — 4 trường: (a) cho phép cá nhân hoá, (b) bắt buộc hay tuỳ chọn, (c) số ký tự tối đa (mặc định 256, dải 1–1024), (d) hướng dẫn cho khách.
- **§10.3 Vật liệu** — hệ thống tự suy ra từ thuộc tính Chất liệu của Biến thể; BA không nhập lại.
- **§10.4 Ảnh đa (Multi-image)** — thêm ảnh phụ vào form sản phẩm; hệ thống gửi tất cả lên Etsy (tối đa 10 ảnh) theo thứ tự BA sắp.
- **§10.5 Override Danh mục / Ai làm / Khi nào làm** — mặc định dùng giá trị chung của shop; BA có thể override từng sản phẩm (taxonomy Etsy riêng, "Ai làm", "Khi nào làm" khác).
- **§10.6 Cân nặng & Kích thước** — điền vào trường Cân nặng chuẩn (hệ thống chuyển đổi sang ounce/gram); Kích thước tự suy ra từ tên Biến thể dạng `R30X18` cho dòng Rect (Mug giữ kích thước trống).
- **§10.7 Thuộc tính biến thể** — mỗi biến thể có Material/Color/Size, hệ thống gửi nhãn tương ứng lên Etsy.

> **Spec-drift check (Phase 3 pre-flight)**: trước khi viết §10, đọc commit bodies của 9 slice (`P-HUB-SKU-AUTODERIVE` 8df9b524b42; `P-PUB-TAGS`; `P-PUB-MULTI-IMAGE`; `P-PUB-PERSONALIZATION` 39bbc2843; `P-PUB-PER-PRODUCT-DEFAULTS` c637b4058; `P-PUB-MATERIALS`; `P-PUB-VARIANT-PROPERTIES` 9ce4e93df1d; `P-PUB-WEIGHT-DIMENSIONS` 8a04a7df21d) và verify field names + max values + conditional emit rules; ghi summary vào `findings.md` của spec 011.

### §11 FAQ (renumbered)
- Drop old FAQs về Wizard cũ / SKU Builder.
- Add:
  - Q: "Mã SKU tự sinh có sai không?" — A: dựa trên Danh mục + Biến thể; chọn đúng thì SKU đúng; BA vẫn sửa được.
  - Q: "Tôi muốn giữ mã legacy cho sản phẩm cũ — làm sao?" — A: gõ tay vào ô Mã SKU, hệ thống giữ nguyên.

### §12 UAT Checklist (renumbered, refreshed)
- **TC-001..TC-007**: rewrite for standard Products menu flow (drop Wizard step references).
- **TC-008..TC-012**: mark `[DEPRECATED — Wizard hidden in v1.2]` or delete.
- **NEW TC-008**: Create SP với Tags (max 13, max 20 chars each) → verify Etsy nhận đúng.
- **NEW TC-009**: Cá nhân hoá (4 fields) → verify Etsy payload chứa 4 keys.
- **NEW TC-010**: Materials tự extract từ variant → verify Etsy nhận đúng list.
- **NEW TC-011**: Multi-image — upload 3 ảnh → verify Etsy nhận 3 ảnh theo thứ tự.
- **NEW TC-012**: Per-product override taxonomy → verify publish dùng override không phải shop default.
- **NEW TC-013**: Cân nặng — điền 0.35 kg → Etsy nhận 12.35 oz (shop weight_unit_pref=oz).
- **NEW TC-014**: Dimensions từ `R30X18` → Etsy nhận length=30, width=18.
- **NEW TC-015**: Variant với Material/Color/Size → property_values gửi đúng nhãn.

### §13 Báo lỗi cho ai (renumbered)
- Keep as-is.

---

## 4. Section-by-Section Diff — `FLOW_TAO_SAN_PHAM_VN.md`

### Header
- Line 3: `Phiên bản: 1.1` → `1.2`; `Ngày: 2026-05-26` → `2026-05-28`.
- Line 7-8 changelog blockquote: replace v1.1 text with v1.2 summary (single canonical path; SKU auto-derive; 9 new fields).

### Tổng quan (lines 11–22)
- Delete "Có hai cách tạo sản phẩm bằng tay: 1. Wizard cổ điển ... 2. SKU Builder Wizard" + the 3-way bullet list.
- Replace with: **"Cách 1 — Form Sản phẩm chuẩn (chính)"**: BA mở menu Sản phẩm → Tạo mới → Mã SKU tự sinh từ Danh mục + Biến thể. Không cần Wizard riêng.
- Add **"Cách 2 — Đồng bộ từ Excel (sắp ra mắt)"**: đặt file Excel vào GDrive → hệ thống tự nhập hàng ngày.
- Keep "bản gốc duy nhất" paragraph (lines 13–14 of v1.1).

### Old "Cách 1A: Wizard cổ điển" (lines 26–52)
- Replace heading with "Cách 1 — Form Sản phẩm chuẩn"; rewrite body to describe Products-menu flow in business voice; mention SKU auto-derive.

### Old "Cách 1B: SKU Builder Wizard" (lines 56–78)
- Delete section heading; fold SKU auto-derive explanation into Cách 1.

### Validator mã SKU v2 (lines 81–92)
- Reduce to one-line note: "Mã SKU tự động kiểm tra theo quy chuẩn; sản phẩm cũ không bị ảnh hưởng."

### Cách 2: Excel (lines 94–113)
- Keep, renumber as appropriate.

### SKU — câu chuyện hai mã (lines 115–125)
- Keep; light update: sản phẩm mới dùng v2 (auto-derived); legacy giữ nguyên.

### FAQ (lines 128–146)
- Drop FAQs about Cách 1A vs 1B.
- Add: "Tôi muốn giữ mã legacy — hệ thống có cho phép không?" → "Có, BA gõ tay vào ô Mã SKU."

### Liên hệ (lines 150–155)
- Keep as-is.

---

## 5. Risks & Open Questions

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | v1.1 header line 5 names modules (plain-view violation) | Medium | Delete or generalize at Phase-3 start; document choice in commit body |
| R2 | Screenshots in HUONG_DAN become stale (show Wizard UI not Products menu) | Medium | Out of scope; recommend sibling slice `P-DOCS-SCREENSHOTS-V12` |
| R3 | New UAT TC-008..TC-015 may miss edge cases (e.g., multi-image ordering, weight=0 omitted, Mug no-dimension) | Medium | BA review at Phase 4 cross-checks against code commit bodies |
| R4 | Spec drift between code (9 slices) and doc claims (field names, max values, conditional emit) | High | Phase-3 pre-flight: read 9 commit bodies + test files; record verified field names + bounds in `specs/011-etsy-outbound-publish/findings.md` before editing docs |
| R5 | Vietnamese terms in doc may not match live UI labels | Low | Grep view XML for `string="…"` of new fields; use exact UI label or closest business equivalent |

**Open question**: BA may want screenshots updated in same slice. **Decision**: defer (out of scope) — keep text-only slice atomic, faster ship.

---

## 6. Abbreviated 9-Phase Loop

| Phase | Status | Action |
|---|---|---|
| 0 Dispatch | ✓ done | Branch + clean tree verified; 10 TaskCreate items registered |
| 1 Plan | ✓ this doc | This file |
| 2 RED | **SKIP** | Doc-only; no automated tests for prose (note in commit body) |
| 3 GREEN | pending | Edit both .md files per §3/§4; spec-drift findings recorded first |
| 4 Review | pending | Single `code-reviewer` agent (BA review = orchestrator self-check against plain-view rule + spec-drift findings) |
| 4-security | **SKIP** | No code; nothing to attack (note in commit body) |
| 5 Verify | pending | grep both files for forbidden tokens; `wc -l` sanity (~554→~470 expected for HUONG_DAN) |
| 6 Commit | pending | `[docs] feat(P-DOCS-HUONG-DAN-V12): rewrite v1.2 to standard Products menu` on `feature/006-master-plan-coding`; trust `.githooks/post-commit` for Confluence HEP push |
| 7 Document | pending | Tracker row `todo` → `done` + decision-log entry |
| 8 Learn | **light** | Capture only if surprises; otherwise explicit "no new code patterns; doc-only slice" |

---

## 7. Exit Criteria (10 tasks)

- [ ] T1 — Rewrite §3-§5 to single canonical Products-menu path
- [ ] T2 — Document SKU auto-derive in business voice (no Odoo internals)
- [ ] T3 — Add §10 covering 9 new publish-ready fields
- [ ] T4 — Refresh UAT TC-001..TC-015 (Wizard TCs obsolete, new field TCs added)
- [ ] T5 — Sync `FLOW_TAO_SAN_PHAM_VN.md` (Tổng quan + §10 mirror + FAQ)
- [ ] T6 — Bump version 1.1→1.2, date 2026-05-28, refreshed changelog blockquote in both files
- [ ] T7 — Plain-view rule verified (grep clean for module names, Odoo internals, P-codes outside changelog)
- [ ] T8 — Commit on `feature/006-master-plan-coding` with conventional message + skip notes
- [ ] T9 — Tracker row `P-DOCS-HUONG-DAN-V12` → `done` + decision-log entry
- [ ] T10 — `/learn` insight captured (or explicit "doc-only; no new patterns" note)
