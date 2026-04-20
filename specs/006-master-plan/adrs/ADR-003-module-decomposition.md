# ADR-003: Decompose `etsy_integration` into Four Modules

- **Status**: Accepted
- **Date**: 2026-04-10
- **Sign-off**: 2026-04-13 (owner)
- **Deciders**: Owner, architect
- **Affects**: All specs 002–005 and future 006+
- **Related**: [MASTER_PLAN.md §3](../MASTER_PLAN.md), [tech-architect.md §2](../agent-reports/tech-architect.md)

## Context

The current `custom_addons/etsy_integration/` module is ~1,776 LOC (Spec 001, shipped). By the end of Spec 005 it will balloon to an estimated **8,000–12,000 LOC** with:

- 13 new models
- 5–7 new services
- 2+ new controllers (webhooks)
- 3 new wizards
- Seed XML files for fiscal data, product categories, carrier mappings
- Dependencies on both Gmail (legacy) and Etsy API v3 (new)

Problems with the monolith:

1. **Cognitive load**: Contributors will struggle to navigate 10k+ LOC. Odoo's module conventions work well at 500–3,000 LOC; past that, finding anything becomes a grep exercise.
2. **Merge conflicts**: Spec 004 (Gearment + GKE) and Spec 005 (Etsy API) are genuinely independent concerns that two devs should be able to build in parallel. Sharing one module's `__manifest__.py`, `models/__init__.py`, `services/__init__.py`, and `views/menu.xml` creates constant merge friction.
3. **Unclean retirement**: The historical import wizard (Spec 001) and the data migration wizard (Spec 002) are one-shot tools. They should be uninstallable after cutover to prevent accidental re-runs. In a monolith, uninstalling means losing the whole module.
4. **Channel scaling**: When Amazon (future Spec 010) and Website (future Spec 011) channels arrive, they need a shared core (dashboards, fulfillment routing, design files) without depending on Etsy-specific models.
5. **Testability**: A 10k-LOC module has slow test startup (Odoo loads all models before running tests). Splitting reduces the set of tests that must run for channel-specific work.

## Decision

Decompose `etsy_integration` into **four modules**, introduced progressively (not all at once):

```
multichannel_hub_core
  Purpose: foundation — shared across all channels and fulfillment partners
  Contents:
    - sale.order channel fields (sales_channel, channel_order_ref)
    - sale.order.fulfillment delegation mixin (see ADR-007)
    - order.design.file model + 3-state approval workflow
    - shipping.carrier model (unified — see ADR-005)
    - carrier_detector.py service
    - order.return model
    - fulfillment_status state machine + transitions
    - production_stage, pic_user_id, order_priority
    - Order Dashboard, Tracking Dashboard, Process Dashboard views
    - multichannel.sync.health observability model (renamed from etsy.sync.health)
    - Rate limiter utility (utils/rate_limiter.py)
    - Webhook controller base (controllers/webhook_base.py)
  Depends on: sale_management, stock, contacts, mail

multichannel_hub_fulfillment
  Purpose: external fulfillment partners and tracking ingestion
  Contents:
    - fulfillment.partner, partner.sync.log
    - logistics.partner
    - tracking.import.log, tracking.import.line
    - partner_sync.py adapter base (Protocol)
    - gearment_adapter.py (Spec 004b)
    - tracking_importer.py (Spec 004a)
    - Generic partner webhook controller (uses webhook_base)
  Depends on: multichannel_hub_core

etsy_channel
  Purpose: Etsy-specific connectors (email and API)
  Contents:
    - etsy.shop (extended)
    - etsy.email.log (Spec 001)
    - etsy.api.log, etsy.webhook.event (Spec 005)
    - product.template Etsy fields (etsy_listing_id, etsy_listing_state)
    - email_parser.py (Spec 001) — will be deprecated per ADR-002
    - gmail_client.py (Spec 001)
    - etsy_api_client.py (Spec 005)
    - etsy_order_syncer.py (Spec 005)
    - etsy_tracking_pusher.py (Spec 005)
    - OAuth2 flow (both Gmail and Etsy PKCE)
    - Etsy webhook controller (uses webhook_base)
  Depends on: multichannel_hub_core, multichannel_hub_fulfillment

etsy_channel_migration
  Purpose: one-shot migration tools; uninstallable after cutover
  Contents:
    - import_orders_wizard.py (historical Excel import)
    - data_migration_wizard.py (Spec 002)
    - product_categorizer.py
    - etsy_fiscal_data.xml, etsy_product_categories.xml, product_category_keywords.json
    - Auxiliary $0-price anomaly export tool
  Depends on: etsy_channel
  Designed to be uninstalled after historical migration is complete
```

### Sequencing

The decomposition lands progressively, not all at once:

- **Phase 0 (during Spec 002)**: `etsy_integration` remains monolithic. Spec 002's new files land in the existing module. But the **code organization** is structured as if the split had already happened (directory names, import paths, service boundaries) so the eventual move is a `git mv` rather than a rewrite.
- **Phase 1 (start of Spec 003 rewrite)**: Create `multichannel_hub_core`. Move shared pieces (delegation mixin, shipping.carrier, order.design.file, dashboards) out of `etsy_integration`. `etsy_integration` declares a dependency on `multichannel_hub_core`.
- **Phase 2 (Spec 004a)**: Create `multichannel_hub_fulfillment`. Move tracking import and adapter base into it. `etsy_integration` → rename to `etsy_channel`; declares dependencies on core + fulfillment.
- **Phase 3 (start of Spec 005 code)**: Create `etsy_channel_migration` by extracting all one-shot wizards and seed data. `etsy_channel` keeps only the runtime connectors.
- **Post-cutover**: `etsy_channel_migration` is uninstalled from production. Any leftover code lives in git history.

## Consequences

### Positive
- **Parallel dev work**: Spec 004 and Spec 005 can proceed simultaneously without stepping on each other's `__manifest__.py` or `models/__init__.py`.
- **Testing speed**: Tests for `multichannel_hub_core` don't need Etsy-specific fixtures.
- **Channel extensibility**: Adding Amazon (Spec 010) is a new `amazon_channel` module depending on `multichannel_hub_core` and `multichannel_hub_fulfillment`. No Etsy touchpoints.
- **Clean retirement**: `etsy_channel_migration` uninstalls cleanly post-cutover, removing ~2,500 LOC of one-shot code from production. The migration wizard never gets accidentally re-run.
- **Clear ownership boundaries** in code review.

### Negative
- **Four `__manifest__.py` files** and four `security/ir.model.access.csv` files to maintain. Added ceremony on every new model.
- **Migration risk during Phase 1 split**: Moving models between modules in a live DB requires a data-migration hook (`migrate()` function with model rename). Mitigated by testing the module rename in a staging DB first.
- **Dependency hell potential**: If two modules want to reference the same mixin that belongs to `multichannel_hub_core`, both must depend on core. Usually fine, occasionally annoying.
- **Commit history split**: git log for a given feature now spans multiple directories. Mitigated by conventional commit scopes (`[multichannel_hub_core]`, `[etsy_channel]`, etc).

### Neutral
- Total module count goes from 1 to 4. The four-module structure matches typical Odoo OCA patterns (e.g. `delivery`, `delivery_carrier_label`, `delivery_carrier_sendcloud`).

## Alternatives considered

1. **Keep monolithic `etsy_integration`** — rejected. Will be 10k+ LOC by end of Spec 005; merge pain and cognitive load make this a false economy.
2. **Six modules** (extra split: `multichannel_hub_dashboard` separate from core, `multichannel_hub_pricing_audit` separate) — rejected. Dashboards and pricing audit don't have enough surface area to justify separate modules; they'd be forced to depend on core anyway. Keeps views fragmented across modules with little benefit.
3. **Two modules** (`etsy_legacy` + `multichannel_hub`) — rejected. Muddles the channel/hub distinction; Amazon and Website would have to live inside `multichannel_hub` which breaks the channel-extensibility benefit.
4. **Delay decomposition until after Spec 005** — rejected. Retrofitting a module split on a 10k-LOC monolith is strictly worse than doing it incrementally. The right time is during Spec 003 (before the code bloat).

## Implementation notes

- Each new module's `__manifest__.py` should set `version = '19.0.1.0.0'` following the existing convention.
- Each module has its own `security/ir.model.access.csv` with model access rules for only its own models.
- Module rename during Phase 2 (`etsy_integration` → `etsy_channel`): requires an Odoo upgrade script in `migrations/19.0.1.0.1/pre-migrate.py` that renames the module record in `ir_module_module`. Test on a staging DB first.
- The ruff config (`ruff.toml`) should be per-module or use glob patterns to apply to all four.
- The `.claude/rules/odoo/` patterns should be updated to cover all four modules.
- Odoo 19 supports cross-module model inheritance natively; no special handling needed.
- Git commit scopes: use `[module_name]` prefix per existing convention.
