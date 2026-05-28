# Phase 1 Plan: P1-DESIGN-WIZ-ATTACH-SCOPE

**Spec**: `specs/003-dashboard-design-multichannel/`
**Slice**: Add explicit ownership check in `design.file.upload.wizard._do_upload_for_attachment`
**Estimated LOC**: ~15 model + ~45 test
**Manifest version**: 19.0.1.0.35 → 19.0.1.0.36

## 1. Slice Rationale

**Threat model** (from findings.md §P1-DESIGN-MULTI-UPLOAD, line 1143):

> `attachment_ids = Many2many('ir.attachment')` accepts any attachment the user can read. In Odoo 19 base, `ir.attachment` ships with record rules that scope visibility to attachments for records the user can read (`res_model`/`res_id`-based ACL). The production-team group already has tight membership. Accepted as designed; flagged in commit body. **Follow-up tracker row**: `P1-DESIGN-WIZ-ATTACH-SCOPE` — add an explicit `_do_upload_for_attachment` ownership check (`attachment.create_uid == env.user OR attachment.res_model == 'design.file.upload.wizard'`) once owner confirms threat model.

**Why now**: P1-DESIGN-MULTI-UPLOAD is merged and production. Security-reviewer flagged a design-time carve-out for self-created attachments (the widget auto-creates `ir.attachment` rows with `res_model='design.file.upload.wizard'`). The ownership gate is pure defense-in-depth — Odoo's base `ir.attachment` record rules already constrain visibility, but FR-017 (memory `feedback_fr017_write_defense_in_depth.md`) dictates explicit per-model validation gates.

**Depends on**: P1-DESIGN-MULTI-UPLOAD ✓ (merged 2026-05-08).

---

## 2. Spec Drift Checks

### Check A: Single call site confirmed
**Grep**: `_do_upload_for_attachment` appears only in `design_file_upload_wizard.py:125` (called from `_do_upload()` on line 125). **No other code paths invoke this method.** Safe to add the check at the top of the method.

### Check B: Wizard self-created attachments
**Finding**: `design_file_upload_wizard.xml:17` declares `widget="many2many_binary"` on the `attachment_ids` field. Odoo's stock `many2many_binary` widget creates `ir.attachment` rows with:
- `create_uid = env.user` (the wizard caller)
- `res_model = 'design.file.upload.wizard'` (the wizard model)
- `res_id = wizard.id` (the wizard instance ID)

**Decision**: The carve-out condition `attachment.res_model == 'design.file.upload.wizard'` must be included. Otherwise, a wizard opened by user A, populated with files (which the widget auto-saves as attachments with `res_model='design.file.upload.wizard'`), then modified by the transaction but not yet saved, would be accessible only to user A. On action_upload, if the wizard instance is still transient and live, the attachments belong to the wizard's res_model. Verify this is the case in Phase 2 test.

### Check C: No pre-existing ownership checks
**Grep** for `attachment.create_uid` across `custom_addons/`: **0 matches**. No other model already validates attachment ownership. This is the first enforcement point.

### Check D: ACL scope
From `ir.model.access.csv`:
```
access_design_file_upload_wizard_production_team,design.file.upload.wizard production team,model_design_file_upload_wizard,group_production_team,1,1,1,0
```
Production-team has Create=1 on the wizard. The new ownership check does not relax this — it strengthens the gate by ensuring cross-user attachment smuggling is blocked even if Odoo's base `ir.attachment` record rules were relaxed.

---

## 3. Implementation Steps

### Step 1: Add ownership gate to `_do_upload_for_attachment` (design_file_upload_wizard.py:129)

**File**: `custom_addons/multichannel_hub_core/models/design_file_upload_wizard.py`
**Location**: Method `_do_upload_for_attachment` (currently line 129), top of method before any work.

**Add check immediately after the docstring**:
```python
def _do_upload_for_attachment(self, attachment):
    """Per-attachment dispatch reusing the storage_mode-specific helpers."""
    # FR-017 defense-in-depth: explicit ownership gate
    # Odoo base ir.attachment record rules limit visibility, but we enforce
    # per-model ownership check: attachment must be created by current user
    # OR associated with this wizard (auto-created by many2many_binary widget).
    if (
        attachment.create_uid.id != self.env.user.id
        and attachment.res_model != 'design.file.upload.wizard'
    ):
        raise AccessError(
            _("You can only upload files that you created or that are attached to this wizard.")
        )

    blob = (
        base64.b64decode(attachment.datas) if attachment.datas else b''
    )
    file_name = attachment.name or 'design'
    if self.storage_mode == 'gdrive':
        self._upload_gdrive_with(file_blob=blob, file_name=file_name)
    elif self.storage_mode == 'small':
        self._upload_small_with(file_blob=blob, file_name=file_name)
```

**Why at method entry (not at action_upload)?**
- Spec is clear: "explicit ownership check in `_do_upload_for_attachment`". Placing it at the helper level ensures per-file validation and clarity of intent.
- `action_upload` already has the FR-017 RPC gate (`_check_production_team_or_raise`). This is data-access defense, not role-based defense.
- Centralizing at the helper avoids duplication if the method is ever called from another code path.

---

## 4. Test Design (Phase 2 RED)

### Test File Location
**Path**: `custom_addons/multichannel_hub_core/tests/test_design_file_upload_wizard_attach_scope.py`

### Test Registration
**File**: `custom_addons/multichannel_hub_core/tests/__init__.py`
**Action**: Add a new import line:
```python
from . import test_design_file_upload_wizard_attach_scope
```
**Note** (memory `feedback_tdd_guide_init_py_imports.md`): The tdd-guide agent frequently forgets to register test files. **Orchestrator must verify this import is added before Phase 5 verification.**

### Test Class & Methods

#### Class name: `TestDesignFileUploadWizardAttachScope` (TransactionCase, post_install)

#### Test 1: `test_upload_own_attachment_succeeds`
- **Scenario**: User A creates an attachment; User A opens wizard, adds attachment, calls action_upload → succeeds.

#### Test 2: `test_upload_other_user_attachment_raises_accesserror`
- **Scenario**: User A creates attachment; User B (same production-team group) opens wizard, adds User A's attachment, calls action_upload → raises AccessError.
- **Assert**: AccessError raised; zero `design.file` rows created (atomic rollback)
- **Memory warning** (feedback_odoo19_test_gotchas.md): `assertRaises((A,B))` tuple breaks Odoo's `_assertRaises`. Use a single class.

#### Test 3: `test_upload_wizard_self_attachment_succeeds`
- **Scenario**: Attachment with `res_model='design.file.upload.wizard'` and `create_uid=user_a`; user_b can upload it (carve-out allows).

#### Test 4: `test_upload_n_files_one_unauthorized_raises_atomically`
- **Scenario**: 3 attachments — 2 owned by User A, 1 by User B. User A tries to upload all 3 → fails atomically on the 2nd file. Zero `design.file` rows.

### Test Fixtures & Helpers
- Reuse `_JPEG_2X2` fixture from `test_design_file_upload_wizard_multi.py` (copy or import)
- Two `production_team` users in `setUpClass`

---

## 5. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Carve-out logic inverted (`and` vs `or`) | Low | High | Phase 2 test #3 explicitly covers `res_model='design.file.upload.wizard'` |
| Wrong field for ownership check | Medium | High | Phase 2 test asserts on `create_uid`; fails immediately if wrong |
| Atomic rollback doesn't fire | Low | High | Phase 2 test #4 verifies zero files on failure |
| Message translation missing (no `_()` wrap) | Medium | Low | Implementation wraps in `_()`; test does partial match |

---

## 6. Agent Dispatch & Execution Order

### Phase 2 (RED) — Orchestrator inline
**Reasoning** (per memory `feedback_tdd_guide_init_py_imports.md` + `feedback_reviewer_agent_diff_hallucination.md`): Small slice (~15 LOC + 45 test). tdd-guide self-deception risk is elevated on tiny slices. Orchestrator inline.

### Phase 3 (GREEN) — Orchestrator inline
~5 LOC + 1 import (AccessError already imported via odoo.exceptions if not, add).

### Phase 4 (Review) — Parallel agents
Single message: `code-reviewer` + `security-reviewer` (both Sonnet — no sudo/raw-SQL needing Opus).

### Phase 5 (Verify)
```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core --stop-after-init
ruff check custom_addons/multichannel_hub_core/  # if available in container
grep -rE "_logger\.info\(|^[[:space:]]*print\(" custom_addons/multichannel_hub_core/models/design_file_upload_wizard.py
grep -rE "_logger\.info\(|^[[:space:]]*print\(" custom_addons/multichannel_hub_core/tests/test_design_file_upload_wizard_attach_scope.py
```

---

## 7. Exit Criteria Mapping

| Criterion | Status | Notes |
|-----------|--------|-------|
| Slice tasks [X] in `tasks.md` | N/A | No tasks.md row (security follow-up). Tracker row + findings.md is spec. |
| Tests pass; ≥80% on changed lines | TBD | 4 test methods + gate code coverage |
| Module installs clean | TBD | `-u multichannel_hub_core` exit 0 |
| ACLs / sudo / raw-SQL | N/A | Document inline in commit body |
| Tracker state → done | TBD | Update `.claude/plans/006-master-plan-tracking.md` row |
| /learn run | TBD | Capture FR-017 defense-in-depth + carve-out pattern |
| findings.md updated | TBD | Note: `res_model` carve-out is intentional per threat model |
| Manifest version bump | TBD | 19.0.1.0.35 → 19.0.1.0.36 |

---

## 8. Shortcut Eligibility & Recommendation

**Recommendation**: **Run full 9-phase loop**. Rationale:
1. Security-reviewer pair is mandatory (Phase 4).
2. Ownership gate + carve-out logic needs explicit Phase 2 test to avoid inversion bugs.
3. Slice is security-adjacent to already-shipped feature.
