# ADR-011: `multichannel.enquiry` over the full `crm` dependency

- **Status**: Accepted
- **Date**: 2026-05-07
- **Sign-off**: 2026-05-07 (owner directive 2026-05-06 to scaffold spec 007; Phase 0 research §R1 picked the lightweight path; this ADR codifies it)
- **Deciders**: Owner, architect (synthesis), BA lead
- **Affects**: [Spec 007 — Customer Conversations](../../007-customer-conversations/spec.md), `multichannel_hub_core`, MP006 slice family `P3-LEAD-*`
- **Related**: [ADR-003](ADR-003-module-decomposition.md), [ADR-008a](ADR-008a-email-as-mandatory-backup.md), [`../../007-customer-conversations/research.md`](../../007-customer-conversations/research.md) §R1

## Note on numbering

ADR-010 reserves the string "ADR-011" for a never-written WC-reassignment-governance ADR that was collapsed into ADR-010 §6 before any file landed. That historical slot was retired, not consumed — no `ADR-011-*.md` ever existed in this repo. This ADR claims the open slot for the new lead-model decision. Future readers chasing the ADR-010 supersedes line should land here and stop.

## Context

Spec 007 (pre-sale customer conversations / CRM Lead) needs a record type that:

- Holds buyer enquiries that have **no `sale.order`** yet (pre-sale).
- Carries `mail.thread` for chatter and `mail.activity.mixin` for follow-ups.
- Has a small lifecycle (new → qualified → converted/closed) plus a "convert to quote" action that creates a `sale.order` once the buyer commits.
- Receives mail via `mail.alias` per shop and threads with the existing `etsy.message.dedupe` ledger (Family C foundational, P3-LEAD-DEDUPE).

Two designs were on the table: extend Odoo's stock `crm.lead` (depend on `crm`), or write a thin `multichannel.enquiry` model on `multichannel_hub_core`.

The Odoo Constitution, Principle I ("Odoo-Native First"), nudges toward `crm.lead`. Principle VII ("Simplicity Over Completeness") and the `multichannel_hub_core` rule "channel-agnostic foundations only; no Etsy-specific code; no UI bloat" push the other way.

## Decision

Build a lightweight `multichannel.enquiry` model on `multichannel_hub_core`. **Do not depend on `crm`**.

Surface area:

- 1 model (`multichannel.enquiry`), `_inherit = ['mail.thread', 'mail.activity.mixin']`.
- ~9 fields (name, partner_id, partner_email, source_channel, etsy_shop_id, state, sale_order_id back-ref, owner_user_id, body summary).
- 4-state Selection (`new` / `qualified` / `converted` / `closed`).
- 1 action `action_convert_to_quote` (creates `sale.order` + back-pointer + chatter audit).
- 1 close wizard (TransientModel) for capturing close reason.
- ACL: BA tier R/W/C, manager full; production_team read-only.
- Form + list + kanban (group-by state) + search views.

Total budget: ~250 LOC across model + views + ACL (per spec 007 tasks T035–T050).

## Rationale

- `crm` ships 4 menu groups + 12 record rules + a kanban that the BA team does not need; adding it shadows the channel-agnostic group hierarchy already curated in `mhc` (auto-memory `feedback_channel_agnostic_groups_in_mhc.md`).
- Re-implementing the 60% of `crm.lead` we actually want is ~150 LOC. Pulling in `crm` to use 40% of it is the wrong trade — installation footprint, training cost, and ACL surface area outweigh the saved code.
- Constitution Principle V ("Incremental Migration") supports starting small: if marketing-ops later wants pipeline reporting, kanban funnels, or lead scoring, we add `crm` and migrate `multichannel.enquiry` records via a small wizard. The reverse (adopt `crm`, then strip it) is materially harder.
- `mhc` already inherits `mail.thread` + `mail.activity.mixin` patterns from prior work (`design.file`, `etsy.address.change.request`); the enquiry model reuses the same idiom — no new abstractions.

## Alternatives considered

1. **Full `crm` dep + `crm.lead` extension.** Rejected: heavyweight; adds menus across the system; team training cost; conflicts with `mhc`'s "channel-agnostic foundations only" rule.
2. **`mail.message` only + a saved filter on the inbox.** Rejected: no state machine, no convert-to-quote action, no per-enquiry record rules — operators lose trackability.
3. **One model handling BOTH `sale.order` chatter AND pre-sale.** Rejected: `sale.order` already inherits `mail.thread`; reusing it for pre-sale would create phantom orders or sentinel rows. The two flows have genuinely different lifecycles.

## Consequences

- New addressable surface in `multichannel_hub_core` — a model not tied to any channel. Future channels (Amazon, website) reuse it via the existing `source_channel` Selection.
- The `etsy.message.dedupe` ledger (P3-LEAD-DEDUPE, foundational) routes inbound messages either to a `sale.order` (post-sale, Family C) or to `multichannel.enquiry` (pre-sale, Family D). One ledger, two destinations.
- If marketing-ops eventually wants pipeline reporting, a follow-up ADR-NNN supersedes this one and migrates records into `crm.lead`. This ADR is **not** load-bearing for that future migration — only the data model is.
- No upgrade-path commitment to `crm.lead`'s field shape. The `multichannel.enquiry` schema is governed by spec 007 `data-model.md`.

## Slice traceability

- `P3-LEAD-SPEC` ✓ (2026-05-07) — spec 007 scaffold, research §R1
- `P3-LEAD-DEPS` ← this ADR (2026-05-07)
- `P3-LEAD-DEDUPE` — foundational `etsy.message.dedupe` (also unblocks Family C `P1-MSG-API-PULL`)
- `P3-LEAD-MODEL` — `multichannel.enquiry` model + actions + views
- `P3-LEAD-MAIL-ALIAS` — per-shop `mail.alias` provisioning
- `P3-LEAD-CONVERT` — `action_convert_to_quote` polish
- `P3-LEAD-API-ROUTING` — replaces `NotImplementedError` in `EtsyConversationPoller._route_message`

See [`/home/odoo/odoo_dev/other_projects/odoo19_esty/.claude/plans/006-master-plan-tracking.md`](../../../.claude/plans/006-master-plan-tracking.md) §"Family D — Pre-sale enquiry / CRM Lead".
