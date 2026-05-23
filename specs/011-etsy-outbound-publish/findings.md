# Findings — Spec 011 (Etsy Outbound Publish)

## P-HUB-SPEC (planning slice) — 2026-05-23

- **Spec 008 P-LIST-INV-PUSH supersession.** The deferred Slice 3 of Spec 008 (entire-array-resubmit inventory writeback) is absorbed into Spec 011 P-PUB-INVENTORY. Reasons: (a) the publisher state machine needs the same PUT path; (b) the canonicalisation wizard (Spec 009 P-HUB-SKU-DRIFT) needs the same; (c) a single owner avoids duplicate retry/audit/rollback code. Spec 008 tracker row stays in place with `superseded by P-PUB-INVENTORY` annotation; the planned `wizards/etsy_listing_push_wizard.py` is not built — its intent is split between `EtsyInventoryPusher.push` (service) and `etsy.publish.wizard` (UI).
- **Owner SKU policy fully resolved by ADR-014 §4.** Two questions answered in-session 2026-05-23: new publishes use v2-canonical; canonicalisation of live listings auto-pushes. Both encoded in P-PUB-DRAFT (SKU resolution at payload-build time) and P-PUB-INVENTORY (entry point reused from canonicalisation wizard).
- **Per-shop Etsy defaults are minimal in MVP.** Only taxonomy / shipping-profile / return-policy IDs are mandatory + `who_made` / `when_made` / `is_supply` enums. Other Etsy fields (`materials`, `tags`, `style`) default to NULL and are accepted by Etsy. Expansion is per-product or per-shop overrides if data shows variation post-MVP.
- **Resumability uses `product.channel.status` state, not a new model.** State machine: `draft` → `published` → `archived` / `error`. The `external_ref` field carries the Etsy listing ID across steps; the `last_sync_error` field carries the last 4xx body for operator triage. Avoids over-engineering a separate `publish.job` model.
- **One concrete publisher, no abstract base.** YAGNI: there's no second channel today. When Amazon arrives, we'll refactor (or not) based on actual shared shape, not anticipated shape.
- **Image diff via SHA-256 manifest on `etsy.listing` (JSON Text).** Listing-side manifest (channel scope), not product-side (would conflate channels). Future Amazon will have its own manifest on `amazon.listing`.
- **No webhook handling for Etsy-side listing edits.** Out of scope. Drift detection (Spec 008 P-LIST-INV-PULL) already surfaces qty drift; title/description drift surface is a future enhancement, not a publish-blocker.
- **Coordination point with Spec 010**: new `etsy.api.log` `source` values are added in a single Selection extension (Spec 011 P-PUB-CLIENT T002) that covers both spec families' new values, so we don't run two migrations.
- **Pure-doc slice (this planning artifact).** No code/tests; Two-Phase Testing N/A for P-HUB-SPEC.
- **Reused codebase invariants pre-loaded into tasks.md**: FR-017 method-top gates (memory `feedback_fr017_write_defense_in_depth` 20+ confirmations); 4xx vendor-body capture with durable cursor (memory `feedback_capture_response_body_before_blackbox_probe`); SKU policy from ADR-014 §4; `etsy_api_shop_id` field for URL construction per memory `reference_etsy_shop_id_mapping`.

## E2E surfacing (live)

_(none yet — implementation not started)_
