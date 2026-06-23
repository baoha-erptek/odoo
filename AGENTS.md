# Repository Guidelines

## Project Structure & Module Organization

This repository is an Odoo 19 workspace. Core server code lives in `odoo/`, standard addons in `addons/`, and project-specific modules in `custom_addons/`. Current custom modules include `etsy_integration`, `multichannel_hub_core`, and `multichannel_hub_fulfillment`; each follows normal Odoo layout with `__manifest__.py`, models, views, security files, data, and `tests/`. Browser UAT lives in `tests/e2e/` with specs in `tests/e2e/tests/`, page objects in `tests/e2e/page-objects/`, and seed/auth helpers in `tests/e2e/fixtures/`. Deployment assets are under `deployment/`, while product specs and implementation plans are under `specs/`.

## Build, Test, and Development Commands

- `python3 odoo-bin --addons-path=addons,custom_addons -d <db> -u <module> --stop-after-init`: upgrade one module in a local database.
- `python3 odoo-bin --addons-path=addons,custom_addons -d <db> -i <module> --test-enable --stop-after-init`: install a module and run its Odoo tests.
- `ruff check custom_addons/<module>`: run Python lint checks using the repo `ruff.toml`.
- `cd tests/e2e && npm install`: install Playwright dependencies.
- `cd tests/e2e && npm run test:all`: run all browser UAT specs.
- `cd tests/e2e && npm run report`: open the Playwright HTML report.

## Coding Style & Naming Conventions

Use Python 3.10-compatible code and standard Odoo conventions. Keep module names snake_case, model names dotted and domain-specific such as `etsy.shop`, and test files named `test_*.py`. Follow the import ordering in `ruff.toml`: standard library, third-party, `odoo`, then local addon imports. XML IDs should be stable, descriptive, and module-scoped. TypeScript E2E files use `*.spec.ts` for tests and page-object classes under `page-objects/`.

## Testing Guidelines

Place Odoo unit and integration tests in each module’s `tests/` directory and keep fixtures under `tests/data/` or `tests/fixtures/`. Prefer focused test names that describe the workflow or regression, for example `test_etsy_order_syncer.py` or `test_p_list_publish_from_listing_phase2_orm.py`. For browser tests, configure required `STAGING_*` environment variables as described in `tests/e2e/README.md`, then run a targeted script such as `npm run test:wave-2-3` before broader `npm run test:all`.

## Odoo Implementation Rules

Before adding a new field, model, view, or service, search standard Odoo first in `addons/`, `odoo/addons/`, and existing custom modules. Reuse standard Odoo constructs when they fit, such as `product.tag`, `list_price`, `product_template_image_ids`, standard attribute values, partner merge tooling, and built-in routes. If a custom model or field is still needed, document the standard option considered and why it does not fit before implementing.

For Odoo models, include `_description`, set `_order` for deterministic ordering where useful, use `_rec_name` when the display field is not `name`, and specify `ondelete` on every `Many2one`. Keep model files ordered as metadata, fields, constraints, compute methods, onchange methods, CRUD overrides, actions, then private helpers. Use `@api.depends` for computed fields, `@api.constrains` for validations, `@api.onchange` only for UI-only behavior, and `@api.model_create_multi` for batch create overrides.

## Verification & Review

After Python or Odoo changes, run the narrowest meaningful checks first: `ruff check custom_addons/<module>`, targeted Odoo tests, and a module upgrade/install command for the affected module when database access is available. For new behavior, prefer two-phase coverage: database/state verification for stored values and constraints, then ORM tests for business workflows. Before finishing, scan changed Python files for stray `print()` calls and debug-only `_logger.info()` usage.

Code review should prioritize security issues, data integrity, missing tests, Odoo upgrade/install failures, access control regressions, raw SQL risks, and unnecessary custom code where standard Odoo already provides a pattern.

## Commit & Pull Request Guidelines

Git history uses scoped conventional-style messages, often prefixed by module or docs scope, for example `[etsy_integration] fix(regression): repair latent failures` or `[docs] docs(business-flows): record regression sweep`. Keep commits narrow and mention the affected module. Pull requests should include a clear problem statement, summary of changes, linked issue or spec when relevant, test results, and screenshots for UI or browser-flow changes.

## Security & Configuration Tips

Do not commit secrets, credentials, staging passwords, or generated Playwright artifacts. Keep environment-specific values in local environment files or deployment templates, and review `SECURITY.md` before reporting or handling vulnerabilities. Every new Odoo model needs ACLs in `ir.model.access.csv`; add record rules for multi-company or ownership boundaries. Prefer ORM over raw SQL. When raw SQL is necessary, use parameterized queries and document why ORM is not sufficient. Use `sudo()` only for a narrow operation, with an inline comment explaining why elevated access is required and why it is safe.

## Relationship To `.claude`

This repository also contains `.claude/` with Claude-specific agents, skills, hooks, commands, and rules. Codex should treat `.claude/rules/`, `.claude/commands/`, and relevant `.claude/plans/` files as reference material when they apply to the task, but those files are not automatically executed by Codex. Do not assume Claude plugins, hooks, Telegram routing, or agent dispatch are available unless the user explicitly asks for that workflow. If `.claude` guidance conflicts with this `AGENTS.md` or higher-priority user/system instructions, follow the higher-priority instruction.
