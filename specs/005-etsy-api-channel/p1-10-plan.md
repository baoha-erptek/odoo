# P1-10 Tactical Plan — Production OAuth + Fernet-at-Rest Token Encryption

**Slice**: Master Plan 006 / P1-10
**Spec**: 005-etsy-api-channel
**Branch**: `feature/006-master-plan-coding`
**Authored by**: planner agent, 2026-05-12 (Phase 1 of 9-phase loop)
**Depends on**: E1 ✓ (approved 2026-05-12), P0-14..P0-17 ✓
**Unblocks**: P1-12 (EtsyTrackingPusher), P1-11 (pilot cutover), P1-13 (additional shops)

---

## 1. Slice Summary

Layer production-grade OAuth cutover on top of P0-14's dev-token scaffolding. Three sub-objectives:

- **A** — Fernet-at-rest encryption for the 3 plaintext token fields on `etsy.shop` (architect Q2 deferral from P0-14).
- **B** — Scope assertion against the four approved Etsy scopes (`transactions_r/w`, `listings_r/w`, `shops_r`, `email_r`); hard-reject `conversations_r` (excluded from E1 approval set).
- **C** — Prod-app credential plumbing audit + operator runbook (no schema change — confirms `ir.config_parameter` path is clean).

Per Decision **D-D** in the 2026-05-12 roadmap plan: Fernet via `cryptography.fernet`, key sourced from `ir.config_parameter` (`etsy.oauth.fernet_key`, system-only ACL).

---

## 2. Spec Drift Check (per memory `feedback_phase1_spec_drift_check.md`)

| Name in tracker/spec | Name in code | Status |
|---|---|---|
| `etsy_oauth_access_token` | `etsy.shop.etsy_oauth_access_token` (Char, `groups='base.group_system'`) | match |
| `etsy_oauth_refresh_token` | `etsy.shop.etsy_oauth_refresh_token` (Char, `groups='base.group_system'`) | match |
| `etsy_oauth_token_expires_at` | `etsy.shop.etsy_oauth_token_expires_at` (Datetime) — **verify exact name** (tracker says `token_expires_at`, code may use `etsy_oauth_token_expires_at`) | confirm at GREEN |
| OAuth callback handler | `controllers/etsy_oauth_callback.py` + `services/etsy_oauth.py` | match (P0-14) |
| Token refresh on 401 | `EtsyApiClient._request()` + `_refresh_token()` | match (P0-15) |
| Scope validation | not implemented | **drift — new in P1-10** |
| Fernet encryption layer | not implemented | **drift — new in P1-10** |
| `etsy.api.log.source` Selection | enum includes `audit, sync, tracking_push, webhook_register, listing_push, listing_pull, buyer_message_sync, health_check` | needs `scope_validation` (D-P1-10-05) |

**Plaintext write sites discovered via `grep -rn "etsy_oauth_access_token" custom_addons/`**:

- `controllers/etsy_oauth_callback.py` — callback writes plaintext after Etsy token exchange.
- `services/etsy_api_client.py` — refresh-token path writes plaintext.
- (Verify both at tdd-guide RED — paths may shift slightly.)

**Action at Phase 3 (GREEN)**: Read the actual files and **quote field names verbatim** before authoring code. If `etsy_oauth_token_expires_at` is named differently in the model, update this plan inline before writing tests.

---

## 3. Surface

### Sub-objective A — Fernet-at-rest encryption

**Add**:
- `services/fernet_crypto.py` — stateless `encrypt(plaintext: str) -> str` / `decrypt(ciphertext: str) -> str`. Key from `ir.config_parameter.etsy.oauth.fernet_key`. Raises `ValueError` if key missing or ciphertext malformed.
- `data/ir_config_parameter.xml` — declares `etsy.oauth.fernet_key` ICP with `groups='base.group_system'`; empty default value (key is generated lazily at first use, not at module install — see D-P1-10-02).

**Modify**:
- `models/etsy_shop.py` — add internal helper methods `_get_access_token()` / `_get_refresh_token()` returning decrypted plaintext via `sudo()` (inline justified comment); never expose as ORM-readable fields. All API client and refresh paths route through these helpers.
- `controllers/etsy_oauth_callback.py` — wrap pre-write encryption around the token exchange result.
- `services/etsy_api_client.py` — replace direct `self.shop.sudo().etsy_oauth_access_token` reads with `self.shop._get_access_token()`; in `_refresh_token()`, encrypt before `shop.sudo().write({...})`.
- `__manifest__.py` — bump version to `19.0.1.0.X` (next patch); add `data/ir_config_parameter.xml` to `data`; declare `cryptography` in `external_dependencies['python']` (likely already present — verify).

### Sub-objective B — Scope assertion

**Modify**:
- `services/etsy_oauth.py` — `build_authorize_url()` requests explicit scope string `'transactions_r transactions_w listings_r listings_w shops_r email_r'` (space-separated, no `conversations_r`).
- `controllers/etsy_oauth_callback.py` — after Etsy returns the access token, parse the returned `scope` parameter; assert all 4 required scopes present; assert `conversations_r` absent. On failure: write `etsy.api.log` row with `source='scope_validation'` + HTTP 400 + redirect operator to error page. On success: proceed with token persistence.
- `models/etsy_api_log.py` — extend `source` Selection to include `('scope_validation', 'OAuth Scope Validation')`.

### Sub-objective C — Prod credential plumbing audit

**No code change required**, but:
- Verify `controllers/etsy_oauth.py` reads client_id / client_secret from `ir.config_parameter` (not hard-coded).
- If any hard-coded dev value is found, replace with ICP read + fail fast on missing key.
- Author `specs/005-etsy-api-channel/operator-runbook.md` (or extend if present) with:
  - How to install prod client_id / client_secret via Settings → Technical → Parameters → System Parameters.
  - How to verify the Fernet key is generated (single one-time admin action).
  - How to revoke + reauthorize a shop if scope grant drifts.

---

## 4. Decision Points

**D-P1-10-01 — Field encryption strategy**: **Helper-method indirection over the raw Char columns** (not a custom field type, not shadow fields). All callers route through `etsy.shop._get_access_token()` / `_set_access_token()` helpers; underlying column stores ciphertext as a base64 Fernet token. Rationale: minimal schema change, no Odoo ORM extension, preserves P0-14's ACL guarantee. Cost: every call site must use the helper — enforced by grep + lint in code review.

**D-P1-10-02 — Fernet key lifecycle**: ICP key `etsy.oauth.fernet_key`, system-only ACL, **lazy-generated on first encrypt call** (not at module install). Rationale: avoids generating an unused key in dev DBs; install-time generation invites accidental key loss during DB clones. Generation path: `Fernet.generate_key()` → base64 string → `sudo().set_param(...)`. Concurrency: protect with PG advisory lock (`pg_advisory_xact_lock(<int>)`) to prevent two requests racing key creation.

**D-P1-10-03 — Existing plaintext rows**: **Lazy migration on next write**. P0-14 left at most a single dev shop with plaintext tokens. On next refresh (5-min cron), helpers re-encrypt. No data migration script. Verification: a Phase 1 DB test asserts that after one refresh-token cycle, the column holds Fernet-prefixed ciphertext (starts with `gAAAAA`).

**D-P1-10-04 — Scope-assertion failure behavior**: **Hard-error 400** — better to surface drift at the OAuth handshake than silently accept reduced scopes and fail mid-sync. Audit row with `source='scope_validation'`, error message names which scopes are missing / which forbidden scope leaked. Operator runbook documents the recovery (revoke at Etsy, request reapproval).

**D-P1-10-05 — `etsy.api.log.source` enum extension**: Add `'scope_validation'`. Selection extension lands in `etsy_integration` module bump (`19.0.1.0.X` → `19.0.1.0.X+1` if model already at a stable point). Verify no existing rows use a clashing value.

**D-P1-10-06 — Audit-log durability**: Per memory `feedback_capture_response_body_before_blackbox_probe.md`, wrap `etsy.api.log.create({...})` inside `with self.env.registry.cursor() as cr: ...; cr.commit()` so the row survives even if the outer OAuth callback transaction rolls back on the 400. Mandatory for scope-validation failures.

---

## 5. Phase 1 (DB) Test List

File: `custom_addons/etsy_integration/tests/test_p1_10_db.py`
Class: `TestP1_10Schema(SingleTransactionCase)`

- `test_fernet_key_icp_record_exists` — `ir.config_parameter` row with key `etsy.oauth.fernet_key` is loaded by `data/ir_config_parameter.xml`.
- `test_fernet_key_system_group_acl` — non-admin user `read('etsy.oauth.fernet_key')` raises `AccessError`; admin succeeds.
- `test_api_log_source_includes_scope_validation` — `etsy.api.log` `_fields['source'].selection` contains `('scope_validation', ...)`.
- `test_etsy_shop_token_columns_unchanged_after_p1_10` — confirms the 3 token columns still exist with `groups='base.group_system'` (no schema regression).
- `test_token_column_holds_ciphertext_after_write` — direct SQL query after `_set_access_token('plaintext')` returns a string starting with `gAAAAA` (Fernet token marker).

## 6. Phase 2 (ORM) Test List

File: `custom_addons/etsy_integration/tests/test_p1_10_orm.py`
Classes: `TestFernetCrypto`, `TestScopeValidation`, `TestTokenHelpers`

`TestFernetCrypto`:
- `test_round_trip_known_plaintext` — `encrypt → decrypt` returns input string.
- `test_decrypt_with_missing_key_raises` — delete ICP key, decrypt raises `ValueError` with no-key message.
- `test_decrypt_with_wrong_key_raises_invalid_token` — rotate key between encrypt and decrypt, decrypt raises `InvalidToken`.
- `test_lazy_key_generation_is_idempotent` — concurrent (simulated) callers see the same key after first generation.
- `test_encrypted_output_is_unique` — two `encrypt('same')` calls return different ciphertexts (Fernet uses random IV).

`TestScopeValidation`:
- `test_scope_assertion_accepts_four_approved_scopes` — granted `'transactions_r transactions_w listings_r listings_w shops_r email_r'` → callback proceeds.
- `test_scope_assertion_rejects_missing_scope` — granted `'transactions_r listings_r shops_r email_r'` (missing `transactions_w` + `listings_w`) → HTTP 400 + audit row.
- `test_scope_assertion_rejects_conversations_r` — granted `'transactions_r ... email_r conversations_r'` → HTTP 400 + audit row with explicit forbidden-scope mention.
- `test_scope_validation_audit_log_survives_rollback` — confirms D-P1-10-06 — the audit row exists in DB even after the 400 rolls back the request transaction.
- `test_scope_validation_audit_row_has_pii_scrubbed` — confirms the audit row doesn't carry the raw access token (only scope strings + shop_id).

`TestTokenHelpers`:
- `test_set_access_token_encrypts_on_disk` — `shop._set_access_token('plain')` → raw column ciphertext, helper returns decrypted plaintext.
- `test_refresh_token_round_trip_through_api_client` — mock Etsy refresh endpoint, verify `EtsyApiClient._refresh_token()` reads ciphertext, calls API with decrypted bearer, writes new ciphertext.
- `test_authorization_header_uses_plaintext` — mock `requests.Session.request`, assert `Authorization: Bearer <plaintext>` (not ciphertext).
- `test_get_access_token_returns_empty_string_when_unset` — fresh shop with no token returns `''`, not raises.

---

## 7. Agent Dispatch Order

1. **Planner** (this turn) — done.
2. **tdd-guide** (Phase 2 RED) — write all tests above, register them in `tests/__init__.py` (per memory `feedback_tdd_guide_init_py_imports.md`). Run; confirm RED.
3. **Implementation** (orchestrator, inline) — author the Surface files in §3. Read actual code first; quote field names verbatim before editing.
4. **code-reviewer + security-reviewer** in parallel (Phase 4) — single message, two `Agent` calls.
5. **Verify** (Phase 5) — `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0; run `--test-tags /etsy_integration:TestP1_10Schema,/etsy_integration:TestFernetCrypto,/etsy_integration:TestScopeValidation,/etsy_integration:TestTokenHelpers`; `ruff check custom_addons/etsy_integration/`; grep clean for `_logger.info`/`print(`.
6. **Commit** (Phase 6) — single conventional commit body cites: slice ID, D-D reference, E1 approval bookkeeping commit, exit criteria. Title: `[etsy_integration] feat(P1-10): production OAuth scope cutover + Fernet token encryption`.
7. **Document** (Phase 7) — append `findings.md` §P1-10; mark T013–T017 with `(closed by P1-10)` note where applicable; tracker P1-10 row `state→done`.
8. **Learn** (Phase 8) — `/learn` for Fernet + Odoo ORM surprises; expected captures: helper-indirection field strategy, lazy key generation, audit-log durability for OAuth.
9. **Land** (Phase 9) — accumulate on `feature/006-master-plan-coding`; merges to `main` after W7 E2E sprint.

---

## 8. Risks

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R-P1-10-1 | Fernet key loss locks all stored tokens forever | Low | Critical | Key lives in `ir.config_parameter` (DB-backed; included in pg_dump). Operator runbook documents backup; key never deleted without re-encryption migration. |
| R-P1-10-2 | Concurrent decrypt during in-flight requests | Low | Low | `cryptography.Fernet` is stateless and thread-safe. No mitigation needed beyond standard Odoo per-request env isolation. |
| R-P1-10-3 | Etsy issues tokens against old scope set after E1 approval (pre-2026-05-12 cached approvals) | Medium | Medium | Scope assertion catches it at callback. Operator escalation path: revoke at Etsy → reauthorize → drop stale tokens. |
| R-P1-10-4 | `etsy.api.log.source` enum extension breaks existing rows | Low | Low | Selection extension is additive — no existing row uses the new value. Module bump migration sees the new value as part of normal `--update`. |
| R-P1-10-5 | Plaintext-in-memory during decrypt (memory disclosure → leak) | High | Medium | Known acceptable per P0-14 architect Q2 — no in-process secrets store. Re-evaluate at W7 with KMS/Vault if owner directs. |
| R-P1-10-6 | Helper-method indirection (D-P1-10-01) bypassed by future direct field reads | Medium | High | Add ruff/grep CI gate forbidding direct `.etsy_oauth_access_token` reads outside `models/etsy_shop.py` + `tests/`. Document in findings.md. |
| R-P1-10-7 | Concurrent lazy key generation race produces two different keys | Low | Critical | `pg_advisory_xact_lock(hash('etsy.oauth.fernet_key'))` before generate-or-read sequence. Phase 2 test simulates the race. |
| R-P1-10-8 | `cryptography` library not pinned in container | Low | Medium | Verify `requirements.txt`; pin to a known-good version (`cryptography>=42,<46`). |

---

## 9. Exit Criteria (mirror of TaskCreate IDs 6–13)

- [ ] Fernet-at-rest encryption for `etsy_oauth_access_token`, `etsy_oauth_refresh_token`, `etsy_oauth_token_expires_at` (D-P1-10-01).
- [ ] Production OAuth scope validation against 4 approved scopes; reject `conversations_r` (D-P1-10-04).
- [ ] Prod-app credential plumbing audited; operator runbook authored (Sub-objective C).
- [ ] Phase 1 DB + Phase 2 ORM tests pass; ≥80% on changed lines.
- [ ] code-reviewer + security-reviewer parallel, no CRITICAL/HIGH unresolved.
- [ ] `odoo -u etsy_integration --stop-after-init` exit 0; ruff clean; no debug statements.
- [ ] Conventional commit on `feature/006-master-plan-coding` citing slice + decisions + reviewer outcomes.
- [ ] Tracker P1-10 → `done`; tasks.md notes; findings.md §P1-10; `/learn` insight captured.

---

## 10. Out of Scope (explicit non-goals for this slice)

- Key rotation / multi-key support — future hardening slice.
- KMS / Vault integration — future hardening slice.
- Per-shop unique encryption keys — future hardening slice (current model uses one instance-wide key).
- `conversations_r` scope re-request — tracked separately as **P1-MSG-SCOPE**.
- `EtsyTrackingPusher` (US3 implementation) — tracked separately as **P1-12**.
- Pilot shop cutover ceremony — tracked separately as **P1-11**.
- UI for "Reauthorize Shop" button on `etsy.shop` form — defer to P1-11 cutover slice.
