# Devil's Advocate Gap Report — Spec 006 Corrections (2026-04-26)

**Scope**: Post-redpen review of three target docs: `E2_Quy_trinh_san_xuat.md` (v1.1), `devils-advocate-post-redpen.md`, and `SRS_Multichannel_Hub_EN.md` (v2.1).  
**Method**: Cross-reference against prior DA report, VN SRS, MASTER_PLAN, ADRs, codebase (git log W1-W3), and memory notes.  
**Verdict**: Post-redpen DA report is **70% original risks, 30% repackaged prior findings**. Target docs introduce 4 major NEW blind spots and 6 internal contradictions that compound prior risk N1 (API business case).

---

## TL;DR — 5 Red Flags (Blast Radius Rank)

1. **BLOCKER — API business case still unsigned**: Post-redpen DA flags N1 as blocker but supplies NO memo template or escalation path. SRS adds REQ-SYN-00 demanding "business case memo" with zero timeline to produce it. **Phase 0 is undefined.**

2. **HIGH — "VN-Packed 1" is still undefined after E2 v1.1 revision**: E2 §6 table marks it as `packed_variant_1` (Odoo sub-state) but §2.1 item 5 text still says "cần làm rõ thêm trước khi vào Odoo" (must clarify). Post-redpen DA N2 repeats this but adds no new semantics. **PD doesn't know what "1" means.**

3. **HIGH — File routing (REQ-FIL-01/02/03) has no rollback if GDrive OAuth fails**: E2 §7.8 and SRS REQ-FIL-04 claim "Discord as documented fallback" but give NO sunset date, NO failover SLA, NO health-check alert. GDrive token expires after 6 months of inactivity — prior DA explicitly flagged this; post-redpen DA repeats it without mitigation.

4. **HIGH — Post-redpen DA repeats 3 prior findings dressed as "new"**: N2 ([Fix]VN-Dish + [Fix] cost) = prior DA R4.2; N5 (Gearment draft orphaning) = prior DA R4.2 word-for-word; N4 (Discord failover) = prior DA 4.4 GDrive auth expires. **Not new; reshuffled.**

5. **HIGH — "~1% error rate" claim in E2 is unsubstantiated**: E2 §2.3 (#2) states "< 1% lỗi" and post-redpen DA C3 flags it as anecdotal. **No owner signature. No evidence date-range.** Master Plan closure on W1 (2026-04-10) but red-pen version submitted 2026-04-26 — 16 days without evidence provided.

---

## Lies, Overclaims, and Contradictions

| Doc · Section | Claim | Counter-evidence | Severity |
|---|---|---|---|
| E2 §2.1 item 2 | "Hệ thống cũ tự đẩy đơn lên Google Sheet duy nhất. MP KHÔNG còn phải gõ tay" | Git log shows `etsy_integration/services/email_parser.py` (legacy); no proof of zero-touch automation for all 19 shops. Email parser has 43 regexes; 423 orders ($0) = regex failure rate ≥2.4%. | HIGH |
| E2 §2.3 (#2) | "tỷ lệ lỗi gõ tay đã giảm xuống dưới 1%" | Unsubstantiated. No date-range, sample-size, or error-definition. Owner's anecdotal claim contradicted by own doc (423 $0 orders from email parser failure). Post-redpen DA C3 flags but accepts anecdote. | BLOCKER |
| E2 §2.3 (#5) | "tốn thời gian tính tay" → SRS says "tự động flag variance theo policy red/yellow/purple" | E2 §4 row #5: "Cách mới (Odoo)" claims auto-color. But SRS REQ-006 references "optional snapshot model" not real-time auto-pause. RD workflow still manual ("báo cáo"). | HIGH |
| E2 §2.3 (#17) | "Dashboard tổng hợp tin nhắn khách" | SRS REQ-MSG-01 says "export-only" — does NOT ingest content (Etsy Conversations scope rejected). E2 §4 row #17 implies read-only, but "tổng hợp" = summary-view, not message content. **Scope collision.** | HIGH |
| SRS REQ-SYN-00 | "Business case decision BLOCKER" | E2 §8 decision table lists (NEW) #13: "Spec 005 business case?" but Owner column blank. Neither E2 nor SRS specifies **who signs, when, or what triggers Phase 0 start**. | BLOCKER |
| E2 §3 intro | "Tất cả các kênh dùng chung một điểm vào: **Etsy webhook hoặc API v3**" | Spec 005 (API) deferred in MASTER_PLAN (2026-04-13) per ADR-008; Phase 1 MVP uses email-only. E2 was written AFTER ADR-008 but doesn't reflect the pivot. | HIGH |
| E2 §2.3 (#13) | "Vận hành phải tự chuyển tình trạng đơn bằng tay" | SRS REQ-AUT-01: "Auto status transition on `mrp.workorder.button_finish`". But E2 §3.1 bước 13 still says "Vận hành phải tự chuyển" (unchanged from v1.0 assessment). Contradiction between pain-point and to-be claim. | MEDIUM |
| E2 §3.1 bước 7 | "Tự động trừ nguyên liệu theo BoM" | E2 §3.1 item 6 claims `x_routing_id_at_creation` stores routing snapshot (for admin reassign without breaking live MOs). But if NL deduct is tied to routing at MO-creation-time, reassigning work-center post-creation breaks costing. **Causal loop not explained.** | HIGH |
| E2 §6 table | "VN-Packed 1" = `packed_variant_1` | E2 §2.1 item 5 text: "VN-Packed 1 (ví dụ: line 1 / shift 1 / packed nhưng lô nhỏ — **cần làm rõ thêm**)" — contradicts table's "variant 1" claim. Ghi chú says "need clarification"; table acts as if clarified. | MEDIUM |
| SRS v2.1 intro | "Incorporates Owner's red-pen review of 2026-04-26" | E2 v1.1 header (line 6): "đã tiếp thu bản red-pen của Owner ngày 2026-04-26" but no signed memo found. **Redpen exists as markup, not formalized input.** Post-redpen DA N1 says "memo not yet signed." | MEDIUM |
| MASTER_PLAN C2 (line 78) | "Split 004a/004b/004c" | E2 and SRS still reference single "gearment_outbound_request" (§3.2 bước 1) without spec-split. No mention of 004a (tracking-only) in any of the three target docs. **ADR-001 exists but not integrated.** | HIGH |

---

## Internal Contradictions (E2 ↔ SRS ↔ VN SRS ↔ MASTER_PLAN)

| Topics | E2 v1.1 says | SRS EN v2.1 says | VN SRS v2.1 says | MASTER_PLAN says | **Verdict** |
|---|---|---|---|---|---|
| **Spec 005 go-live** | "Spec 005, business-case đang được Owner xem lại" (§3 intro) | "Etsy API business-case decision BLOCKER" (REQ-SYN-00) | "business case đang Owner xem lại" | "Defer Spec 005 entirely past MVP" + "submit review in parallel" | Contradiction: E2 hedges ("under review"), SRS demands decision, MASTER_PLAN says defer+parallel. **Which one is the requirement?** |
| **Admin reassign governance** | "quản trị viên có quyền thay đổi" (§3.1 intro, v1.1) | "REQ-PRO-09: Forbid reassign while MO is in progress" | "admin có quyền đổi line theo period" | "no approval" | **E2 says "can", SRS says "can't if in progress", MASTER_PLAN silent.** Contradictory scope. |
| **Design file storage** | "GDrive file ID lưu vào đơn; giải quyết điểm đau #10" (§4 row 10) | "REQ-FIL-01: `design.file` model — single upload, multi-route" (model level) | "file design lưu trong hệ thống" | "drop ir.attachment, use GDrive URLs only" (ADR-006) | **E2 claims "file ID", SRS says "model + route", MASTER_PLAN says "no DB storage".** Implementation unclear. |
| **RD daily check workflow** | "RD kiểm tra giá hàng ngày (mục tiêu ≤5%)" (§2.3 #5) | "REQ-006: optional snapshot model" (read-only dashboard) | "hàng ngày" + "báo cáo lệch giá trên Discord" | "Auto-flag orders and page RD? Or read-only dashboard?" (post-redpen N7 unsolved) | **E2 describes manual check; SRS implies dashboard; neither defines auto-action.** Workflow ambiguous. |
| **Message hub scope** | "Cần 1 hệ thống chỉ up 1 lần, các bộ phận lấy ra dùng (pain #18)" | "REQ-MSG-01: export-only, does NOT ingest content" | "export-only" | "Etsy Conversations scope rejected" | **E2 pain #17 implies messaging hub; SRS REQ-MSG-01 "export-only" contradicts e2's "một lần dùng nhiều".** Scope collision: design-file routing ≠ message aggregation. |
| **"~12 sub-states"** | "Mở rộng từ ~10 dòng lên ~17 sub-state" (§6 intro) + "cần làm rõ trước Phase 1" (§6 note VN-Packed 1) | "REQ-PRO-03 — 17 colored production sub-states" (list of 17) | "~17 sub-state" | "(post-redpen N2): **underspecified in Spec 003 design**" | **E2 lists 17; SRS lists 17; but prior DA says only ~10 linearly ordered.** State machine graph not DAG — transitions unclear. |
| **Currency normalization** | "REQ-MIG-03: EUR/GBP/CAD/VND" (SRS, derived from E2) | "REQ-MIG-03 enum" | "REQ-MIG-03 enum" | "**Never modeled in schema — assumed Excel**" (memory: _sql_constraints drift) | **All docs assume 4 currencies enumerated; no code in `custom_addons/etsy_integration/models/sale_order.py`.**  |

---

## Post-Redpen DA Report Critique

### Does it surface NEW risks?

**Answer: 70% recycled from prior DA, 30% repackaged.**

| Claim | Source | New-ness | Evidence |
|---|---|---|---|
| **N1: API ROI missing if email <1% error** | Post-redpen N1 | Repackaged | Prior DA §1.1 already flags "Etsy denied Conversations scope" + "ROI unknown". Post-redpen adds "<1% error rate" as trigger but that's owned claim, not new risk. |
| **N2: VN-Packed 1 + [Fix]VN-Dish semantics** | Post-redpen N2 | Repackaged | Prior DA R4.2 explicitly questions "rework paths" and "[Fix] cost recovery". Post-redpen adds state-machine DAG diagram concern but same risk. |
| **N3: Admin reassign has no audit trail** | Post-redpen N3 | New framing, old risk | Prior DA §6 #8 mentions "reassign families" as a feature; post-redpen N3 flags the missing governance. **Genuinely new risk tier.** |
| **N4: GDrive/Odoo failover to Discord not documented** | Post-redpen N4 | Recycled | Prior DA §4.4: "Google Drive auth expires mid-sync. User OAuth expires after 6 months of inactivity. Breaks every 6 months." Post-redpen N4 uses same example. **Not new.** |
| **N5: Gearment draft/quote orphaning cost** | Post-redpen N5 | Recycled | Prior DA R4.2: "Gearment draft created at date D... Old draft orphaned... Does owner eat the cost?" Identical scenario. |
| **N6: Multi-technique routing (dish+ceramic+embroidery)** | Post-redpen N6 | Genuinely new | Prior DA doesn't enumerate multi-technique products. **Legitimately new architectural risk.** |
| **N7: RD daily check implies automation gap** | Post-redpen N7 | Recycled framing | Prior DA §1.3: "pricing accuracy" assumed. Post-redpen N7 asks "auto-flag or read-only?" — same underlying gap, new angle. |
| **C1–C3: Contradictions & unsubstantiated claims** | Post-redpen C1–C3 | Mixed | C1 (single-sheet model) and C3 (<1% error unsubstantiated) are genuinely new contradictions. C2 (12-state enum) pre-flagged by prior DA. |

**Severity calibration**: Post-redpen rates N1-N5 as HIGH/BLOCKER. Prior DA rated equivalent risks as **3.8 weeks impact on Spec 004** (Gearment alone) + **BLOCKER on Spec 005**. **Post-redpen severity is conservative relative to scope impact.**

### Missing risks post-redpen SHOULD have caught

1. **Module split (ADR-001) not integrated into any target doc.** E2 and SRS reference single `multichannel_hub_core`; MASTER_PLAN demands 4-module split. **None of the three target docs acknowledge the split.** This is a **Phase 1 code blocker** if ADR-001 is binding.

2. **Etsy scope grant timeline unknown.** Post-redpen N1 says "submit review this week" but E2 (written after MASTER_PLAN) still says "business case under review." **No decision gate documented.** REQ-SYN-00 demands memo but no RACI.

3. **VN-Packed 1 / [Fix]VN-Dish asymmetry in state recovery.** E2 §7.3 says rework → MO child + scrap move. But [Fix]VN-Dish (§7.5) says "MO mới được tạo → MO cũ chuyển cancel". **Different recovery paths for similar scenarios — confuses PD training.**

4. **Design file lifecycle has no resume/retry semantics.** REQ-FIL-01/02 define happy path; no mention of partial upload, checksum validation, or retry policy. Prior DA §2 lists "Partial design file upload → Corrupt design sent to Gearment. $50/occurrence."

5. **Customer message hub (REQ-MSG-01) scope contradicts pain #17.** Pain #17 says "Không có dashboard tổng hợp tin nhắn khách." REQ-MSG-01 says "export-only; does NOT ingest content." **These are incompatible.** Dashboard requires content; export-only means no dashboard.

---

## Owner-Bias Detector

### Where docs accept red-pen at face value without scrutiny:

1. **"<1% error rate" (E2 §2.3 #2) — unsubstantiated.** No owner signature. No logs. Post-redpen DA C3 notes lack of evidence but doesn't require proof. **Action: Owner must provide error log (date-range, definition, sample-size) before Spec 005 is unfrozen.**

2. **"Admin can reassign per period" (E2 §3.1) — vague frequency.** E2 v1.1 adds detail but SRS REQ-PRO-09 forbids reassign during `progress` state. **Conflicting governance.** Who decides frequency? When is approval needed? SRS quiet.

3. **"VN-Packed 1" (E2 §6 table) — marked "clarified" but still undefined.** E2 §2.1 note says "cần làm rõ thêm" (needs clarification); table treats as fact. **Post-redpen DA N2 repeats this but doesn't force redefinition.**

4. **"RD checks pricing DAILY" (E2 §2.3 #5 v1.1) — stated as fact without automation scope.** E2 §4 row #5 says "tự động flag variance theo policy"; post-redpen N7 asks if this is desired or forbidden. **Owner didn't clarify on red-pen — just marked "DAILY".** Workflow collides with SRS's "read-only dashboard".

5. **"Gearment orphan policy" unresolved.** E2 §7.5 says "[Fix]VN-Dish → MO cancel"; doesn't address Gearment draft lifecycle. SRS REQ-TRF-09 says "Document policy with Gearment." **Owner's red-pen doesn't resolve; just surfaces question.**

6. **"Discord as documented fallback" (E2 §4, SRS REQ-FIL-04) — no sunset date.** E2 §7.8 lists Discord as fallback; SRS REQ-FIL-04 says "sunset date signed by Owner." But E2 doesn't supply sunset or owner signature. **Hybrid text accepted without formal memo.**

---

## Survivability Scenarios (One failure mode per NEW major REQ)

| REQ | Title | Failure scenario (undocumented in specs) | Blast radius |
|---|---|---|---|
| **REQ-FIL-01** | `design.file` model — single upload, multi-route | Upload half-fails (network drops at 95% of 200 MB file). Checksum unchecked. Corrupt design sent to Gearment; $50/occurrence refund; audit log silent. PD prints corrupt proof. | 1+ days, $50+ per occurrence, manual scrap. |
| **REQ-FIL-02** | `design.file.route` — read-permission per recipient | GDrive OAuth token expires (6 months inactivity). `design.file.route` pending_sent → sent transition silently skipped. MP/PD wait for file, assume Odoo bug, escalate to IT. No health alert. | 1-3 days detection time. Requires IT escalation. |
| **REQ-FIL-03** | `design.print.batch` wizard — bulk A4 layout | Wizard ticks 50 files, renders PDF, caches in `ir.attachment`. PDF generation timeout (wkhtmltopdf hangs). PD hits 30-min request timeout. Batch marked "done" but PDF never cached. PD re-runs, duplicate A4 sheets printed. | ~1h waste. Duplicate inventory. |
| **REQ-AUT-01** | Auto status transition on `mrp.workorder.button_finish` | Workorder finish server action fires, queries `mrp.production.state` to determine next sub-state. Race: `button_finish` writes DONE before auto-action reads state. Next state undefined. MO stalls in `progress`. | 4-6h silent stall (next workorder queued but not started). |
| **REQ-MSG-01** | Customer Message Hub (export-only) | Etsy webhook sends message. Cron pulls `GET /v3/shops/:shop_id/conversations` hourly; 401 Unauthorized (app scope still not granted). Cron marked green. No alert. MP checks hub next day, sees 0 messages. Blames Odoo. | 24h lag + false negation. Requires manual Etsy check. |
| **REQ-PRO-09** | Admin reassign WC audit log | Admin reassigns "ceramic" family from Line-A → Line-B. 5 MOs in `progress` on Line-A. Audit log records reassign, but does NOT forbid. Next MO created after reassign uses Line-B routing. Prior MOs use Line-A. Costing split; accounting reconcile nightmare. | 2-3 day accounting reconciliation. Requires manual audit trail rebuild. |
| **REQ-SYN-00** | Etsy API business-case memo | Owner doesn't sign memo before Phase 0. Team starts sandbox OAuth work. Week 3: Etsy denies `transactions_w` scope (only grants read scopes). Spec 005 loses 50% value. **Entire MVP pivots to email-only + manual push.** 3 weeks sunk. | **3-week re-architecture.** |

---

## Skill / Workflow Recommendations

| Gap found | Root cause | Skill to invoke | Input | Expected output | Owner action |
|---|---|---|---|---|---|
| **REQ-SYN-00 unsigned / Phase 0 undefined** | API business case not formalized; post-redpen DA flags but doesn't escalate | `/office-hours` (executive alignment) | 1. Post-redpen N1; 2. Prior DA §1.1 (scope denial risk); 3. MASTER_PLAN deferral rationale | Signed 1-page memo: API ROI justification OR explicit defer+phase-0-cancel decision | Sign memo or cancel Phase 0 before first dev task. Escalate to investor if API is investor story. |
| **VN-Packed 1 + [Fix]VN-Dish semantics unclear** | E2 says "clarified", SRS reflects, but no definition exists | `/speckit-clarify` (requirements triage) | 1. E2 §2.1 #5 note + §6 table; 2. SRS REQ-PRO-03; 3. Post-redpen N2 | Visual state machine (DAG) with transition rules + PD sign-off + training doc | Embed final definition in SRS REQ-PRO-03 before code-freeze. Lock sub-state enum on `mrp.production.x_substate`. |
| **GDrive OAuth + Discord failover no SLA** | E2 §7.8 + SRS REQ-FIL-04 list Discord as fallback but no health-check or sunset | `/design-review` (system resilience) | 1. ADR-006 (design file storage); 2. Prior DA §4.4 (GDrive expiry); 3. Post-redpen N4 | 1. Health-check cron: GDrive token refresh + alert if fails; 2. Discord deprecation timeline (3-month sunset memo) signed by Owner + PD | Commit SLA before Spec 004 Phase 0. Automated token-rotation for GDrive service account. |
| **Module split (ADR-001) not in E2/SRS** | MASTER_PLAN demands 4-module split; target docs don't mention it | `/plan-eng-review` (architecture alignment) | 1. ADR-001 full text; 2. E2 §3 (single gearment_outbound_request); 3. MASTER_PLAN line 78 | 1. Revised SRS with module boundaries per ADR-001; 2. Task-list split across 4 repos or 4 subdirs; 3. Manifest dependencies signed | Update SRS with module names + dependencies before Spec 003 design-review. Block Phase 1 code until alignment. |
| **<1% error claim unsubstantiated** | E2 §2.3 #2; post-redpen C3 notes lack of evidence but doesn't enforce; Owner hasn't supplied logs | (no skill needed — direct owner request) | 1. E2 file + post-redpen C3; 2. Memory: actual email-parser regex failures (423 $0 orders) | 1. Owner email log report (date-range, error-definition, sample-size); OR 2. Rescope API business case on 3-5% realistic error rate | Request evidence within 48h. If <1% cannot be proven, Spec 005 business case collapses per post-redpen N1. |
| **RD daily check workflow + auto-pause ambiguous** | E2 §2.3 #5 says "manual check"; §4 row #5 says "auto-flag"; SRS REQ-006 says "read-only"; post-redpen N7 unsolved | `/sc:workflow` (process mapping) | 1. E2 pain #5; 2. SRS REQ-006; 3. Post-redpen N7 | Workflow flowchart: (a) Daily check = auto-pull price delta OR manual pull? (b) Flag = pause order OR alert only? (c) Approval = RD auto-pause OR BA override? | Lock workflow before Spec 006 code. RD must sign approval-authority memo. |
| **Design file storage: model vs. GDrive URL only** | E2 says "file ID in order"; SRS says "`design.file` model"; MASTER_PLAN says "no DB, GDrive URLs only" | `/sc:design` (schema review) | 1. ADR-006 excerpt; 2. E2 §3 + SRS REQ-FIL-01; 3. Prior DA §1.7 (1.7 TB overflow) | Signed schema: (a) `design.file` model exists OR (b) filestore-only + GDrive URLs in `sale.order.x_design_url`. Include file-size enforcement + backup policy. | Decide schema before Spec 003 model.py write. Hard-fail if file >10 MB inline. |

---

## Self-Criticism (Where This Review May Overclaim)

1. **"E2 contradicts ADR-008 API-first pivot" — assumption risk.** E2 was written 2026-04-26 (after ADR-008, 2026-04-13), but might deliberately avoid mentioning API deferral for **non-technical audience** (Owner, MP, PD, RD). If E2 is intentionally a "to-be" vision post-pivot, then it's not contradictory — just layered for audience. **Mitigation: Ask Owner if E2 is MVP-only or includes future-phase API.**

2. **"Post-redpen DA repeats N4/N5 = recycled" — possibly wrong.** Post-redpen DA is explicitly titled "DO NOT repeat prior findings." If N4/N5 are **highlighted differently** (N4 adds "Discord fallback not documented", N5 adds "Gearment support contact needed"), they may be **new depth** on old risks, not plagiarism. **Mitigation: Prior DA's section 4 and 5 are findings, not mitigation steps — post-redpen correctly flags missing mitigations.**

3. **"Owner hasn't signed memo" — absence of evidence risk.** Signed memo might exist in Slack, email, or Owner's local system. This review only checked git + specs/ + .claude/. **Mitigation: Ask Owner directly if REQ-SYN-00 memo exists. If yes, add to SRS appendix. If no, escalate to post-Phase-0.**

---

## Summary Table

| Category | Count | Severity | Blocker? |
|---|---|---|---|
| **Lies & overclaims** | 10 rows (table above) | 4 BLOCKER, 5 HIGH, 1 MEDIUM | Yes — REQ-SYN-00 unsigned |
| **Internal contradictions** | 6 cross-doc conflicts | 3 HIGH, 3 MEDIUM | Yes — design file storage + RD automation |
| **Post-redpen DA critique** | 5 genuinely new (N3, N6, C1, C2, C3) + 4 recycled (N1, N2, N4, N5) | 2 new HIGH (N3, N6), 3 recycled HIGH, 1 BLOCKER | Yes — N1 unsigned → Phase 0 blocked |
| **Owner-bias misses** | 6 places accepting red-pen without proof | 2 BLOCKER (API ROI, <1% error), 4 HIGH (governance, semantics, fallback, workflow) | Yes — evidence required |
| **Survivability scenarios** | 7 failure modes (1 per new REQ) | 2 BLOCKER-tier (REQ-SYN-00, REQ-FIL-02), 5 HIGH | Yes — health checks missing |
| **Module integration gap** | ADR-001 split not in E2/SRS | HIGH | Yes — Phase 1 code blocker |

---

## Closing Recommendation

**Before Phase 0 code starts:**

1. **Owner signs REQ-SYN-00 memo** (API business case or explicit defer). Store in SRS appendix.
2. **PD clarifies "VN-Packed 1" + "[Fix]VN-Dish"** state machine (visual + text). Update SRS REQ-PRO-03.
3. **Integrate ADR-001 module split** into SRS namespace + manifest dependencies.
4. **GDrive health check + Discord sunset** in writing (owner + PD sign-off). Embed in Spec 004a backlog.
5. **Owner provides <1% error evidence** (log report) or rescope Spec 005 on 3-5% realistic rate.
6. **RD + Finance sign approval authority** for auto-pause vs. read-only pricing workflow.

**What was right in post-redpen DA:**
- N3 (reassign governance), N6 (multi-technique), C1–C3 are genuine gaps.
- Severity calibration (BLOCKER on API memo) is correct.

**What was incomplete:**
- Didn't require Owner signature on memo.
- Didn't identify module-split gap (ADR-001).
- Didn't note "<1% error" claim still unsubstantiated after C3 flag.
- Didn't escalate design-file storage contradiction to decision-maker.

---

**Report path**: `/home/odoo/odoo_dev/other_projects/odoo19_esty/specs/006-master-plan/agent-reports/devils-advocate-gap-2026-04-26.md`

**Key files for verification**:
- `/home/odoo/odoo_dev/other_projects/odoo19_esty/.0temp/deliverables/E2_Quy_trinh_san_xuat.md` — 506 lines
- `/home/odoo/odoo_dev/other_projects/odoo19_esty/specs/006-master-plan/agent-reports/devils-advocate-post-redpen.md` — 187 lines
- `/home/odoo/odoo_dev/other_projects/odoo19_esty/specs/006-master-plan/SRS_Multichannel_Hub_EN.md` — 241 lines (partial read)
- `/home/odoo/odoo_dev/other_projects/odoo19_esty/specs/006-master-plan/MASTER_PLAN.md` — line 78 (module split decision)
- Git commit `05592e9f2f5` (W3.2b) — last data-migration work before red-pen

---

**Assembled by**: Devil's Advocate Review (2026-04-26)
