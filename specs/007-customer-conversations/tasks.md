---
description: "Task list for Spec 007 — Customer Conversations (Pre-Sale & Post-Sale)"
---

# Tasks: Customer Conversations (Pre-Sale & Post-Sale)

**Input**: Design documents from `/specs/007-customer-conversations/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/etsy_conversation_poller.md, contracts/email_fallback.md, contracts/enquiry_actions.md

**Tests**: REQUIRED. Project enforces Two-Phase Testing (Phase 1 DB + Phase 2 ORM) per `.claude/plans/006-implementation-playbook.md` and memory `feedback_follow_master_plan_playbook.md`. Tests written first (RED) before implementation (GREEN).

**Organization**: Tasks grouped by user story to enable independent slice landing on `feature/006-master-plan-coding`. Each user-story phase maps to one or more tracked slices in `.claude/plans/006-master-plan-tracking.md` Family C / Family D.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different file, no ordering dependency on incomplete tasks in the same phase
- **[Story]**: US1 (post-sale chatter, P1), US2 (pre-sale enquiry, P2). US3 (outbound) is deferred per spec.md and Plan §"Phase 3 — Outbound".
- File paths are absolute repository paths.

## Slice traceability

| Slice ID (tracker) | Phase here | User story |
|---|---|---|
| `P3-LEAD-DEPS` | Phase 2 — Foundational (doc-only T002) | (cross-cutting) |
| `P3-LEAD-DEDUPE` | Phase 2 — Foundational (T003–T010) | US1 + US2 |
| `P1-MSG-EMAIL-FALLBACK` | Phase 3 — US1 §A (T011–T020) | US1 |
| `P1-MSG-SCOPE` | Phase 3 — US1 §B (T021 doc-only owner action) | US1 |
| `P1-MSG-API-PULL` | Phase 3 — US1 §B (T022–T034) | US1 |
| `P3-LEAD-MODEL` | Phase 4 — US2 §A (T035–T050) | US2 |
| `P3-LEAD-MAIL-ALIAS` | Phase 4 — US2 §B (T051–T058) | US2 |
| (poller routing extension) | Phase 4 — US2 §C (T059–T062) | US2 |
| `P3-LEAD-CONVERT` | Phase 4 — US2 §D (T063–T067) | US2 |
| (i18n + quickstart validation) | Phase 5 — Polish (T068–T072) | (cross-cutting) |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm no new deps required; lock baseline so foundational work begins from a clean state.

- [ ] T001 Verify `multichannel_hub_core/__manifest__.py` and `etsy_integration/__manifest__.py` already declare `mail`, `sale_management`, `contacts`, `stock` and that `crm` is NOT added — record decision in commit message; no file edits expected.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: ADR + dedup ledger model. **Blocks both US1 and US2** because every inbound message — receipt-bound or not, API or email — writes a `etsy.message.dedupe` row.

**Slice**: `P3-LEAD-DEPS` (doc) + `P3-LEAD-DEDUPE` (model).

### Foundational tests (RED)

- [X] T002 Add `specs/006-master-plan/adrs/ADR-011-multichannel-enquiry-vs-crm.md` documenting the lightweight-model decision per research.md §R1; cite this spec; commit doc-only on `feature/006-master-plan-coding` (`docs(MP006): ADR-011 multichannel.enquiry over crm dep`). Mark `P3-LEAD-DEPS` slice `done` in tracker.
- [X] T003 [P] Phase 1 DB tests for `etsy.message.dedupe` in `custom_addons/etsy_integration/tests/test_phase1_db_message_dedupe.py`: assert table exists; UNIQUE constraint on `(etsy_shop_id, etsy_message_id)` enforced at PG level via direct INSERT; partial index `idx_emd_pending` exists with predicate `state='buffered'`; columns + types per data-model.md §2.
- [X] T004 [P] Phase 2 ORM tests for `etsy.message.dedupe` in `custom_addons/etsy_integration/tests/test_phase2_orm_message_dedupe.py`: C-EMD-001 XOR constraint between `target_sale_order_id` / `target_enquiry_id` / `pending_target_receipt_id`; ACL — `base.group_system` full, `etsy_integration.group_etsy_api_log_reader` read-only; `payload_excerpt` hard-truncated to 256 chars on create.

### Foundational implementation (GREEN)

- [X] T005 Create `custom_addons/etsy_integration/models/etsy_message_dedupe.py` — Model `etsy.message.dedupe` with fields per data-model.md §2 (`etsy_shop_id`, `etsy_message_id`, `body_sha256_prefix`, `channel`, `posted_at`, `target_sale_order_id`, `target_enquiry_id`, `pending_target_receipt_id`, `state`, `payload_excerpt`); `_sql_constraints` UNIQUE `(etsy_shop_id, etsy_message_id)`; `init()` mirrors via `pg_constraint IF NOT EXISTS` pre-check per memory `project_sql_constraints_drift.md`; `@api.constrains` for C-EMD-001 XOR.
- [X] T006 Register model in `custom_addons/etsy_integration/models/__init__.py`.
- [X] T007 Add ACL rows in `custom_addons/etsy_integration/security/ir.model.access.csv` for `etsy.message.dedupe`: `group_etsy_api_log_reader` R-only; `base.group_system` full.
- [X] T008 Extend `etsy.api.log.source` Selection in `custom_addons/etsy_integration/models/etsy_api_log.py` to include `('conversation_sync', 'Conversation sync')` and `('message_send', 'Outbound message send')`. Migration script if existing rows have NULL — none expected; assert via Phase 1 DB test.
- [X] T009 Add `cron_message_dedupe_retention` to `custom_addons/etsy_integration/data/ir_cron_data.xml` — daily, deletes `state='posted'` rows with `posted_at < now()-30d`; preserves `state='orphaned'` indefinitely (per data-model.md §2 Retention).
- [X] T010 [P] Phase 2 ORM test for retention cron in `custom_addons/etsy_integration/tests/test_phase2_orm_message_dedupe.py` (extend file from T004): time-travel via `freezegun` or direct `posted_at` write; run `_cron_dedupe_retention()`; assert posted-old rows deleted, orphaned-old rows kept.

**Checkpoint**: Foundation ready — both user stories can now begin. Dedup ledger committed; ADR-011 in place; `etsy.api.log` extended.

---

## Phase 3: User Story 1 — Post-sale conversation thread on `sale.order` chatter (Priority: P1) 🎯 MVP

**Goal**: Inbound buyer messages (post-sale) land in `sale.order` chatter via either Etsy API (gated on E1v2 `conversations_r` scope) or email-fallback parser. Cross-channel dedupe via `etsy.message.dedupe` (Phase 2).

**Independent Test**: Send a buyer message via Etsy seller account against a known test order; within 10 minutes the message appears as a chatter entry on the matching `sale.order` with author = buyer partner. Verify with email-only path first (no E1v2 dependency) — then with API path once scope is granted.

**Slices**: `P1-MSG-EMAIL-FALLBACK` (US1 §A) → `P1-MSG-SCOPE` (US1 §B owner action) → `P1-MSG-API-PULL` (US1 §B code).

### §A — Email fallback (independent of E1v2)

#### Tests for US1 §A (RED)

- [ ] T011 [P] [US1] Phase 1 DB test in `custom_addons/etsy_integration/tests/test_phase1_db_email_fallback.py`: assert `etsy.email.log` table accepts `template='buyer_message'` Selection value (will fail before T013 lands).
- [ ] T012 [P] [US1] Phase 2 ORM test in `custom_addons/etsy_integration/tests/test_phase2_orm_email_fallback.py`: feed three fixture emails (`tests/fixtures/email_buyer_message_*.eml`) into `email_parser.parse()` — receipt-bound matched, receipt-bound unmatched (buffered), no-receipt (creates enquiry stub for US2 to consume); assert one `etsy.message.dedupe` row per email with `channel='email'`; assert `mail.message` posted on matched `sale.order` with `author_id` = buyer partner, `email_from` populated, `date` from email header; assert second-feed of same email is a no-op (dedupe).

#### Implementation for US1 §A (GREEN)

- [ ] T013 [US1] Add `'buyer_message'` to the Selection on `etsy.email.log.template` in `custom_addons/etsy_integration/models/etsy_email_log.py`.
- [ ] T014 [US1] Extend `custom_addons/etsy_integration/services/email_parser.py` with a 3rd template handler `_parse_buyer_message(raw_email) -> ParsedBuyerMessage` per `contracts/email_fallback.md` §"Body extraction"; subject prefix `^(Re:\s*)?New message from `; extract `buyer_email`, `buyer_name`, `subject`, `body`, optional `receipt_id`. Pure ORM-free function. Return `None` on parse fail (caller logs to `etsy.email.log` with `parse_status='failed'`).
- [ ] T015 [US1] Extend `custom_addons/etsy_integration/services/order_creator.py` with `post_buyer_message(env, parsed, shop) -> dedupe_record`: synthesize `etsy_message_id` per `contracts/email_fallback.md` §"Synthesizing"; pre-check `etsy.message.dedupe` UNIQUE; resolve buyer `res.partner` via existing Spec 002 US4 helper (`is_etsy_customer=True` flag); if `receipt_id` and matching `sale.order` → call `order.message_post(body=..., subtype_xmlid='mail.mt_comment', author_id=..., date=..., email_from=...)` + write dedupe row `state='posted'` `target_sale_order_id`; if `receipt_id` and NO match → write dedupe row `state='buffered'` `pending_target_receipt_id`; if no `receipt_id` → defer to US2 path (raise `NotImplementedError` until T046 lands; tests in T012 only exercise the receipt-bound branches).
- [ ] T016 [US1] Wire `post_buyer_message()` into the Gmail polling cron caller in `custom_addons/etsy_integration/services/gmail_client.py` (or wherever `email_parser.parse()` results are dispatched today). Single dispatch point keeps the parser ORM-free.
- [ ] T017 [US1] Add `cron_replay_buffered_messages` to `custom_addons/etsy_integration/data/ir_cron_data.xml` — every 30 min, calls `etsy.message.dedupe._cron_replay_buffered()`; for each `state='buffered'` row, look up `sale.order` by `etsy_receipt_id == pending_target_receipt_id`, post chatter via the same `message_post()` call, flip to `state='posted'`; rows with `posted_at < now()-7d` flip to `state='orphaned'` (alert via `multichannel.sync.health`).
- [ ] T018 [P] [US1] Phase 2 ORM test for buffer replay in `custom_addons/etsy_integration/tests/test_phase2_orm_email_fallback.py` (extend file from T012): create buffered row → ingest matching order via existing factory → run cron → assert flip to posted + chatter posted; create buffered row dated 8 days ago → run cron → assert flip to orphaned.
- [ ] T019 [US1] Add fixtures `custom_addons/etsy_integration/tests/fixtures/email_buyer_message_receipt_bound.eml`, `..._receipt_unmatched.eml`, `..._no_receipt.eml` based on real Etsy notification headers (sanitize PII).
- [ ] T020 [US1] Update `custom_addons/etsy_integration/__manifest__.py` `data` list with the new cron XML if separate file; bump module version per playbook §"Phase 6: Commit". Run `odoo -d <db> -u etsy_integration --stop-after-init` and verify exit 0; run `--test-tags /etsy_integration:TestEmailFallbackPhase1,TestEmailFallbackPhase2`.

**Checkpoint US1 §A**: Email-fallback path is live for receipt-bound messages. Mark slice `P1-MSG-EMAIL-FALLBACK` `done` in tracker. **US1 ships independently here for receipt-bound traffic** — API path follows when E1v2 lands.

---

### §B — Etsy API path (gated on E1v2 — `conversations_r` scope approval)

#### US1 §B owner action (`P1-MSG-SCOPE`)

- [ ] T021 [US1] Doc-only: update `guides/vi/etsy-app-review-guide.md` with the re-submission steps for adding `conversations_r` scope; track owner submission as new external-dep row **E1v2** in `.claude/plans/006-master-plan-tracking.md` §"External dependencies". Code change for `etsy_oauth.DEFAULT_SCOPES` does NOT land here — it ships in T024 with the poller so the deploy doesn't request a scope before approval.

#### Tests for US1 §B (RED)

- [ ] T022 [P] [US1] Phase 1 DB test in `custom_addons/etsy_integration/tests/test_phase1_db_etsy_shop_conversation.py`: assert `etsy.shop` has columns `granted_scopes` (Char) and `etsy_last_conversation_sync_at` (Datetime, nullable, indexed).
- [ ] T023 [P] [US1] Phase 2 ORM test in `custom_addons/etsy_integration/tests/test_phase2_orm_conversation_poller.py`: mock `EtsyApiClient` (pattern from P0-15/P0-16c); feed canned JSON fixtures for conversation-list + per-conversation-message endpoints; assert `EtsyConversationPoller.poll_shop()` returns `PollResult(posted=N, buffered=M, skipped=K)`; receipt-bound branch posts chatter on matched SO; receipt-bound unmatched writes buffered dedupe; 401 triggers `etsy_oauth.refresh_access_token` mock; 403 raises `PermissionError`; cursor `etsy_last_conversation_sync_at` advances to `max(message.create_timestamp)`; idempotent re-run skips dups via UNIQUE.

#### Implementation for US1 §B (GREEN)

- [ ] T024 [US1] Add `'conversations_r'` to `DEFAULT_SCOPES` in `custom_addons/etsy_integration/services/etsy_oauth.py`. Existing tokens lose access on rotation per research.md §R2 — documented as known migration step.
- [ ] T025 [US1] Add `granted_scopes` (Char, indexed) and `etsy_last_conversation_sync_at` (Datetime, indexed) fields to `etsy.shop` in `custom_addons/etsy_integration/models/etsy_shop.py`. Backfill `granted_scopes` from existing OAuth token introspection in a `migrations/19.0.X.X.X/post-backfill-conversation-fields.py` post-migration script (one-shot read of token info).
- [ ] T026 [US1] Create `custom_addons/etsy_integration/services/etsy_conversation_poller.py` — `EtsyConversationPoller` class per `contracts/etsy_conversation_poller.md`. ORM-free service consuming `EtsyApiClient` + injected env. Public `poll_shop(shop, since) -> PollResult` (frozen dataclass `posted, buffered, skipped, errors`). Uses `TokenBucket(8, 1.0)` from `multichannel_hub_core/utils/rate_limiter.py`. 3 retries on 429 with `(1, 2, 4)` backoff capped at `Retry-After`. 401 → refresh + 1 retry. 403 → raise `PermissionError`. Internal `_route_message(env, shop, msg)` writes the dedupe row + chatter; receipt-bound matched → `sale.order.message_post`; unmatched → buffered dedupe; no-receipt branch → defer to US2 (returns `('enquiry', None)` until T060 lands; tests in T023 only assert receipt-bound branches at this stage).
- [ ] T027 [US1] Implement `etsy.shop._cron_sync_conversations()` model method in `custom_addons/etsy_integration/models/etsy_shop.py` — iterates shops with `sync_mode='api_only'` AND `'conversations_r' IN granted_scopes`; per shop wraps in `cr.savepoint()` per playbook + memory `feedback_fr017_write_defense_in_depth.md`; calls `EtsyConversationPoller(env, client).poll_shop(shop, since=shop.etsy_last_conversation_sync_at)`; on `PermissionError` logs `_logger.warning` and skips shop; advances cursor on success.
- [ ] T028 [US1] Add `cron_etsy_conversation_sync` to `custom_addons/etsy_integration/data/ir_cron_data.xml` — 10-min interval, model `etsy.shop`, `code: model._cron_sync_conversations()` per `contracts/etsy_conversation_poller.md` §Cron.
- [ ] T029 [US1] Implement PII-scrub list extension on `etsy.api.log.body_excerpt` writer for `source IN ('conversation_sync', 'message_send')` — redact `message_body`, `subject`, `from_email`, `from_name` to `<scrubbed:N chars>`. Code in `custom_addons/etsy_integration/models/etsy_api_log.py`.
- [ ] T030 [US1] Add `conversation_polling_enabled` ICP killswitch read at the top of `_cron_sync_conversations()` (default `'True'`; strict-equality check per memory `feedback_staging_gdrive_provisioning.md` lesson). Allows ops to silence the cron without manifest change.
- [ ] T031 [US1] Add fixtures `custom_addons/etsy_integration/tests/fixtures/etsy_conversations_list.json`, `etsy_conversation_messages_<id>.json` (sanitized; one receipt-bound, one orphan-receipt, one no-receipt for US2).
- [ ] T032 [P] [US1] Phase 2 ORM test for cross-channel dedupe in `custom_addons/etsy_integration/tests/test_phase2_orm_message_dedupe.py` (extend file from T004): feed same logical message via both email-fallback (T015) AND poller (T026); assert exactly one `mail.message` on the order; assert `etsy.message.dedupe.channel` records the first-arriving channel; verify body_sha256 reconciliation when API arrives after email per research.md §R3.
- [ ] T033 [P] [US1] Phase 2 ORM test for buffer-replay via API path (poller writes buffered → order ingested → cron flips to posted) in `custom_addons/etsy_integration/tests/test_phase2_orm_conversation_poller.py` (extend T023).
- [ ] T034 [US1] Run `odoo -d <db> -u etsy_integration --stop-after-init` (exit 0); run `--test-tags /etsy_integration:TestConversationPoller,TestMessageDedupe`. Mark slices `P1-MSG-SCOPE` (doc), `P1-MSG-API-PULL` (code) `done` in tracker.

**Checkpoint US1**: Both API + email paths live. `P1-MSG-EMAIL-FALLBACK`, `P1-MSG-SCOPE`, `P1-MSG-API-PULL` slices closed. SC-001, SC-002, SC-004 acceptance criteria met.

---

## Phase 4: User Story 2 — Pre-sale enquiry routing to `multichannel.enquiry` (Priority: P2)

**Goal**: Buyer-side enquiries (no order yet) land as `multichannel.enquiry` records via `mail.alias` (email) or non-receipt-bound Etsy conversations (API). Operators qualify, close, or convert to a draft `sale.order`.

**Independent Test**: Send an email to the configured `mail.alias`; verify a new `multichannel.enquiry` record with state=`new`, body in chatter, assigned to the alias's default user; click "Convert to Quote" → produces `sale.order` `state='draft'` linked to the enquiry's partner; enquiry flips to `converted`.

**Slices**: `P3-LEAD-MODEL` (US2 §A) → `P3-LEAD-MAIL-ALIAS` (US2 §B) → poller-routing extension (US2 §C, no new slice — extends T026) → `P3-LEAD-CONVERT` (US2 §D polish).

### §A — `multichannel.enquiry` model + actions (`P3-LEAD-MODEL`)

#### Tests for US2 §A (RED)

- [X] T035 [P] [US2] Phase 1 DB test in `custom_addons/multichannel_hub_core/tests/test_phase1_db_enquiry.py`: assert `multichannel_enquiry` table exists with columns per data-model.md §1; partial UNIQUE index `idx_mhe_etsy_conv` exists on `(etsy_shop_id, etsy_conversation_id)` WHERE `etsy_conversation_id IS NOT NULL`; `idx_mhe_partner_email_state` index exists; FK constraints to `res_partner`, `res_users`, `etsy_shop`, `sale_order` per ondelete spec.
- [X] T036 [P] [US2] Phase 2 ORM test in `custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py`: state machine transitions (`new→qualified→converted` allowed; backwards forbidden via `ValidationError` per data-model.md §1 "Backwards transitions disallowed"); `state='closed'` requires non-null `closed_reason` (`@api.constrains`); `_compute_name` produces "Enquiry from <email> · <date>"; `mail.thread` chatter post on every state transition; ACL — `sales_team.group_sale_user` R/W/C, `multichannel_hub_core.group_ba_lead` full, `sales_team.group_sale_manager` full.

#### Implementation for US2 §A (GREEN)

- [X] T037 [US2] Create `custom_addons/multichannel_hub_core/models/multichannel_enquiry.py` — Model `multichannel.enquiry` with `_inherit=['mail.thread', 'mail.activity.mixin']`, fields per data-model.md §1, `_compute_name()` stored compute, `_sql_constraints` for the partial UNIQUE on `(etsy_shop_id, etsy_conversation_id)`, `init()` mirror per memory `project_sql_constraints_drift.md`.
- [X] T038 [US2] Implement state-machine guard via `write()` override + `@api.constrains('state')`: forbid `qualified→new`, `converted→*`, `closed→*` transitions; require `closed_reason` when transitioning to `closed`.
- [X] T039 [US2] Implement `action_qualify()` per `contracts/enquiry_actions.md` — `state='new'→'qualified'`, chatter post `'Qualified by <user>'`, raises `UserError` from non-`new` state.
- [X] T040 [US2] Implement `_match_or_create_partner()` private helper per `contracts/enquiry_actions.md`: search by `email_normalized=email_normalize(partner_email)`; create with `is_etsy_customer=True` (Spec 002 channel-agnostic flag) when no match; sets `self.partner_id`.
- [X] T041 [US2] Implement `action_close(reason)` — terminal transition with required reason; chatter post; ACL gated to `group_sale_user` per FR-013.
- [X] T042 [US2] Create `custom_addons/multichannel_hub_core/wizards/multichannel_enquiry_close_wizard.py` — `multichannel.enquiry.close.wizard` TransientModel with `enquiry_id` Many2one, `reason` Selection (mirrors `closed_reason` per data-model.md §1), `notes` Text; `action_close()` calls `enquiry.action_close(reason)` then writes notes to chatter.
- [X] T043 [US2] Register model + wizard in `custom_addons/multichannel_hub_core/models/__init__.py` and `wizards/__init__.py`; add `wizards/__init__.py` import to top-level `__init__.py`.
- [X] T044 [US2] Add ACL rows in `custom_addons/multichannel_hub_core/security/ir.model.access.csv` per data-model.md §1: `sales_team.group_sale_user` 1/1/1/0, `multichannel_hub_core.group_ba_lead` 1/1/1/1, `sales_team.group_sale_manager` 1/1/1/1; same matrix for the close wizard with the wizard's TransientModel default lifetime.
- [X] T045 [US2] Create `custom_addons/multichannel_hub_core/views/multichannel_enquiry_views.xml` — form view (header buttons: Qualify, Convert to Quote, Close; chatter; partner+email+source+state+converted_order_id+notes); list view with state decoration; kanban grouped by state; search view with filters by `state`, `source`, `assigned_user_id`, group-by `state` (flat siblings per Odoo 19 RNG, memory note); action + menu under Operations.
- [X] T046 [US2] Create `custom_addons/multichannel_hub_core/wizards/multichannel_enquiry_close_wizard_views.xml` — form view + action `act_window`.
- [X] T047 [US2] Create `custom_addons/multichannel_hub_core/data/multichannel_enquiry_seed.xml` — close-reason selection labels for i18n (XML records under `noupdate=1` if any; mostly placeholder for `.po` strings).
- [X] T048 [US2] Update `custom_addons/multichannel_hub_core/__manifest__.py` `data` list with the new XML files; bump version per playbook.
- [X] T049 [P] [US2] Phase 2 ORM test for close-wizard flow in `custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py` (extend file from T036): create enquiry → instantiate wizard with `reason='spam'` → `action_close()` → assert state=`closed`, `closed_reason='spam'`, chatter row added, `notes` appended.
- [X] T050 [US2] Run `odoo -d <db> -u multichannel_hub_core --stop-after-init` (exit 0); run `--test-tags /multichannel_hub_core:TestEnquiryPhase1,TestEnquiryPhase2`. Mark slice `P3-LEAD-MODEL` `done` in tracker.

**Checkpoint US2 §A**: Model + actions + close wizard live. Operators can manually create + manage enquiry records; inbound routing follows in §B and §C.

### §B — `mail.alias` provisioning + inbound (`P3-LEAD-MAIL-ALIAS`)

#### Tests for US2 §B (RED)

- [ ] T051 [P] [US2] HttpCase test in `custom_addons/etsy_integration/tests/test_http_mail_alias.py`: provision alias on a test `etsy.shop`; simulate inbound email via `mail.thread.message_process()` (no real SMTP); assert new `multichannel.enquiry` row with `source='email_alias'`, `etsy_shop_id` set from `alias_defaults`, `partner_email` resolved, body in chatter.
- [ ] T052 [P] [US2] Phase 2 ORM test in `custom_addons/etsy_integration/tests/test_phase2_orm_mail_alias.py`: `etsy.shop.action_provision_enquiry_alias()` creates a `mail.alias` with `alias_name='enquiries_<shop_slug>'`, `alias_model_id=ref('multichannel_hub_core.model_multichannel_enquiry')`, `alias_defaults={'source': 'email_alias', 'etsy_shop_id': <id>}`, `alias_contact='everyone'`; idempotent — second call returns existing alias, no duplicate.
- [ ] T053 [P] [US2] Phase 2 ORM threading test (FR-006): inbound email with `In-Reply-To: <existing-enquiry-message-id>` appends to the existing enquiry's chatter, NOT a new record.

#### Implementation for US2 §B (GREEN)

- [ ] T054 [US2] Implement `etsy.shop.action_provision_enquiry_alias()` action method in `custom_addons/etsy_integration/models/etsy_shop.py` — `sudo()` write to `mail.alias` (justification comment: alias creation requires admin write; user gate is already on the shop record via existing ACL); idempotent search-then-create; returns the alias record.
- [ ] T055 [US2] Implement `multichannel.enquiry._message_new(self, msg_dict, custom_values=None)` override in `custom_addons/multichannel_hub_core/models/multichannel_enquiry.py` per `contracts/enquiry_actions.md` — populates `partner_email` from `msg_dict['email_from']`, `subject` from `msg_dict['subject']`, `source='email_alias'`, `state='new'`; calls `_match_or_create_partner()` to set `partner_id`; threading via `In-Reply-To` is handled by Odoo's standard `mail.thread` — no override needed.
- [ ] T056 [US2] Add a "Provision Enquiry Alias" button to `custom_addons/etsy_integration/views/etsy_shop_views.xml` (or wherever the shop form lives) under a new "Conversations" tab; gated by `groups="base.group_system"` (admin-only).
- [ ] T057 [US2] Update `custom_addons/etsy_integration/__manifest__.py` `data` list with the view changes; bump version.
- [ ] T058 [US2] Run `odoo -d <db> -u multichannel_hub_core,etsy_integration --stop-after-init`; run `--test-tags /etsy_integration:TestMailAlias,TestPhase2OrmMailAlias`. Mark slice `P3-LEAD-MAIL-ALIAS` `done` in tracker.

**Checkpoint US2 §B**: Email-alias path live. Inbound emails create enquiries; threading reuses Odoo's stock behavior. **US2 ships independently here for email-alias traffic** — Etsy API non-receipt-bound path follows in §C.

### §C — Etsy API non-receipt-bound routing (poller extension)

This sub-section extends `EtsyConversationPoller._route_message()` (T026) — same slice as `P1-MSG-API-PULL` for code review purposes; no separate tracker slice. Schedule after US1 §B is in production AND `P3-LEAD-MODEL` is landed.

#### Tests for US2 §C (RED)

- [ ] T059 [P] [US2] Phase 2 ORM test in `custom_addons/etsy_integration/tests/test_phase2_orm_conversation_poller.py` (extend T023): feed canned no-receipt conversation JSON; assert one `multichannel.enquiry` row created with `source='etsy_api'`, `etsy_conversation_id` populated, `etsy_shop_id` set, `partner_email` from message; assert `etsy.message.dedupe` row written with `target_enquiry_id` set; second-feed of same message is a no-op via UNIQUE.

#### Implementation for US2 §C (GREEN)

- [ ] T060 [US2] Replace the `NotImplementedError` placeholder in `EtsyConversationPoller._route_message()` (T026) for the no-receipt branch — search `multichannel.enquiry` by `(etsy_shop_id, etsy_conversation_id)`; if missing, create with `source='etsy_api'` + `_match_or_create_partner()`; if existing, append message to chatter via `enquiry.message_post(...)`; always write `etsy.message.dedupe` `state='posted'` `target_enquiry_id`.
- [ ] T061 [US2] Run `--test-tags /etsy_integration:TestConversationPoller`. Verify the previously-deferred no-receipt branch tests (T023) now exercise the real path.
- [ ] T062 [US2] Update `etsy.shop` form to surface enquiry-side stats (count of open enquiries via stat button on the Conversations tab) — small UX polish; ~10 LOC.

**Checkpoint US2 §C**: API + email-alias paths both create enquiries. Cross-channel dedupe verified.

### §D — Convert-to-quote polish (`P3-LEAD-CONVERT`)

#### Tests for US2 §D (RED)

- [X] T063 [P] [US2] Phase 2 ORM test in `custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py` (extend T036): `action_convert_to_quote()` from `state='new'` creates `sale.order` with `state='draft'`, `partner_id=enquiry.partner_id`, `origin=enquiry.name`; enquiry flips to `state='converted'`, `converted_order_id` set, `converted_at` stamped; chatter posted on both records.
- [X] T064 [P] [US2] Idempotency test: `action_convert_to_quote()` re-invocation when `state='converted'` returns the existing order's `act_window` action without creating a duplicate `sale.order`.
- [X] T065 [P] [US2] Pre-condition test: `action_convert_to_quote()` from `state='closed'` raises `UserError`.

#### Implementation for US2 §D (GREEN)

- [X] T066 [US2] Implement `action_convert_to_quote()` in `custom_addons/multichannel_hub_core/models/multichannel_enquiry.py` per `contracts/enquiry_actions.md`. State guard at method entry. `_match_or_create_partner()` if `partner_id` empty. Create `sale.order` via `self.env['sale.order'].create({...})`. Stamp back-pointer + state in a single `write()`. Chatter on both records via `markupsafe.Markup % escape(...)` per memory `feedback_fr017_write_defense_in_depth.md` — defends against XSS on operator-supplied subject/notes (not paranoid, just consistent with P1-04's pattern).
- [X] T067 [US2] Run `odoo -d <db> -u multichannel_hub_core --stop-after-init`; run `--test-tags /multichannel_hub_core:TestEnquiryConvert`. Mark slice `P3-LEAD-CONVERT` `done` in tracker.

**Checkpoint US2**: All pre-sale paths live. SC-003 (convert in ≤3 clicks), FR-008, FR-009, FR-010 met.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: i18n, quickstart validation, audit-trail hardening across the feature.

- [ ] T068 [P] Extend `custom_addons/multichannel_hub_core/i18n/vi_VN.po` with all new user-facing strings: enquiry state labels, action button labels (`Qualify`, `Convert to Quote`, `Close`), close-reason labels, view labels. Adjacency to slice `P1-07` per plan.md §"Project Structure".
- [ ] T069 [P] Extend `custom_addons/etsy_integration/i18n/vi_VN.po` with: "buyer message" template name, alias-provisioning button label, scope-warning notification text.
- [ ] T070 Run `quickstart.md` smoke test on staging `demo_esty` (`https://odoo.hatafax.com`) against a synthetic Etsy shop: §A.1 (email-only path), §B.1 (alias provisioning), §C.1 (cross-channel dedupe). Document any deltas in `specs/007-customer-conversations/findings.md`.
- [ ] T071 Verify PII-scrub list on `etsy.api.log` per FR-015 — manually inspect 3 sample rows for `source='conversation_sync'` confirming buyer email/name/body redacted; lock the assertion via a Phase 2 ORM test in `custom_addons/etsy_integration/tests/test_phase2_orm_pii_scrub.py`.
- [ ] T072 Run `code-reviewer` and `security-reviewer` agents in **parallel** (single message, two `Agent` calls) per playbook Phase 4 against the full Spec 007 diff (`git diff main..feature/006-master-plan-coding -- custom_addons/multichannel_hub_core custom_addons/etsy_integration specs/007-customer-conversations`); block on CRITICAL/HIGH; address any MEDIUM advisories per memory `feedback_fr017_write_defense_in_depth.md` patterns. Run `/learn` to capture surprises.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup (T001)**: No dependencies.
- **Phase 2 Foundational (T002–T010)**: Depends on Setup. **BLOCKS US1 and US2** — both stories write to `etsy.message.dedupe`.
- **Phase 3 US1 §A (T011–T020)**: Depends on Foundational. Independent of E1v2. Ships first as MVP for receipt-bound traffic.
- **Phase 3 US1 §B (T021–T034)**: Depends on US1 §A + external dep E1v2 (Etsy app review approval). T021 (owner doc) can land any time; T022–T034 land after E1v2 is approved.
- **Phase 4 US2 §A (T035–T050)**: Depends on Foundational only. Can run in parallel with US1 §A.
- **Phase 4 US2 §B (T051–T058)**: Depends on US2 §A.
- **Phase 4 US2 §C (T059–T062)**: Depends on US2 §A AND US1 §B (extends the poller's `_route_message`).
- **Phase 4 US2 §D (T063–T067)**: Depends on US2 §A.
- **Phase 5 Polish (T068–T072)**: Depends on US1 + US2 desired surfaces being landed.

### User Story Dependencies (high-level)

- **US1 (P1)** ships independently; receipt-bound MVP via §A is the smallest deployable increment.
- **US2 (P2)** ships independently of US1's API path. US2 §C (API non-receipt-bound) does depend on US1 §B (poller scaffold) — the only cross-story coupling.
- **US3 (P3)** is deferred per spec.md and out-of-scope for this `tasks.md`.

### Parallel Opportunities

Within Phase 2 Foundational:
- T003, T004, T010 (test files) [P] — independent files
- T005, T006, T007, T008, T009 — sequential within-file or order-dependent

Within Phase 3 US1 §A:
- T011, T012, T018 (test files) [P]
- T013, T014, T015, T016, T017, T019, T020 — model + service edits with order dependency

Within Phase 3 US1 §B:
- T022, T023, T032, T033 (test files) [P]
- T024–T031 — service + model edits with order dependency

Within Phase 4 US2 §A:
- T035, T036, T049 (test files) [P]
- T037–T048 — model + view + ACL with order dependency
- T040 (`_match_or_create_partner`) can be written before T039/T041 [P]

Within Phase 4 US2 §B:
- T051, T052, T053 (test files) [P]
- T054, T055, T056 [P each in different files]

Within Phase 5:
- T068, T069 (i18n) [P]

### Parallel teams

If two devs:
- Dev A: Phase 2 Foundational → Phase 3 US1 §A → Phase 3 US1 §B (after E1v2)
- Dev B: Phase 2 Foundational → Phase 4 US2 §A → Phase 4 US2 §B → Phase 4 US2 §D
- US2 §C requires sync between the two (Dev A's poller; Dev B's enquiry model)

For the project's single-contributor reality, the strict order is: Phase 1 → Phase 2 → Phase 3 §A → Phase 4 §A → Phase 4 §B → (E1v2 unblocks) Phase 3 §B → Phase 4 §C → Phase 4 §D → Phase 5.

---

## Parallel Example: Phase 2 Foundational tests

```bash
# Launch foundational tests in parallel before any implementation:
Task: "Phase 1 DB tests for etsy.message.dedupe in custom_addons/etsy_integration/tests/test_phase1_db_message_dedupe.py"  # T003
Task: "Phase 2 ORM tests for etsy.message.dedupe in custom_addons/etsy_integration/tests/test_phase2_orm_message_dedupe.py"  # T004
```

## Parallel Example: Phase 4 US2 §A tests

```bash
Task: "Phase 1 DB tests for multichannel.enquiry in custom_addons/multichannel_hub_core/tests/test_phase1_db_enquiry.py"  # T035
Task: "Phase 2 ORM tests for multichannel.enquiry in custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py"  # T036
Task: "Phase 2 ORM test for close-wizard flow in custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py"  # T049
```

---

## Implementation Strategy

### MVP First (US1 §A — Email-fallback for receipt-bound messages)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 §A (T011–T020).
2. **STOP and VALIDATE**: send a real "buyer messaged you" email through Gmail polling on staging; verify chatter post on the matched order; verify dedupe row.
3. Demo + ship — closes a known operational pain point without waiting on Etsy review.

### Incremental Delivery

1. Foundation + US1 §A → Demo (MVP, email-only).
2. US2 §A + §B → Demo (manual + email-alias enquiries).
3. (E1v2 lands) US1 §B → Demo (API path live; cross-channel dedupe in production).
4. US2 §C + §D → Demo (full enquiry pipeline).
5. Phase 5 polish → Final ship.

### Constraint: Owner E1v2 dependency

US1 §B (T022–T034) is **gated on E1v2 approval** — Etsy review timeline 3–8 weeks. Treat this as a parallel track: T021 doc-only owner action lands now to start the Etsy clock; T022–T034 wait for approval. Email-fallback (US1 §A) remains permanent failover per ADR-008a v2 even after the API path is live, so US1's MVP value is fully captured without E1v2.

---

## Notes

- [P] tasks = different files, no ordering dependency on incomplete tasks within the same phase.
- Slice IDs in the traceability table map every code task to a row in `.claude/plans/006-master-plan-tracking.md` Family C / Family D so playbook Phase 0 (Dispatch) can pick up directly.
- Two-Phase Testing per project memory: Phase 1 = DB introspection (information_schema, pg_constraint, ACL CSV verification); Phase 2 = ORM behavior with `TransactionCase`; HttpCase only where browser/email-routing is required (T051).
- Per-slice 9-phase loop applies to each slice in the traceability table — Plan, RED, GREEN, parallel Review, Verify, Commit, Document, Learn, Land. Tests come BEFORE implementation in every phase.
- All `mail.message` author resolution reuses Spec 002 US4 partner-dedup helper to keep the `is_etsy_customer=True` flag consistent.
- All `sudo()` writes carry an inline comment with justification per `coding-style.md`.
- All raw SQL (`init()` constraint mirrors, retention cron) carries a justification comment.
- Avoid: cross-story dependencies that break independent shipping; the only legitimate one is US2 §C → US1 §B (poller scaffold extension).
