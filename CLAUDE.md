# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Odoo 19.0 community edition -- a monolithic Python web application with a modular addon system. Uses Werkzeug for HTTP, a custom ORM over PostgreSQL, and OWL (Odoo Web Library) for frontend components.

**Requirements:** Python 3.10-3.13, PostgreSQL 13+, Node.js 16.11+

## Common Commands

### Starting the Server

```bash
./odoo-bin -c odoo.conf -d <dbname>
# or
python -m odoo -c odoo.conf -d <dbname>
```

### Running Tests

```bash
# Run all tests for a specific module
./odoo-bin -c odoo.conf -d <dbname> --test-tags /module_name

# Run a specific test class
./odoo-bin -c odoo.conf -d <dbname> --test-tags :TestClassName

# Run a specific test method
./odoo-bin -c odoo.conf -d <dbname> --test-tags :TestClassName.test_method_name

# Run tests matching a tag (e.g., 'external', 'post_install')
./odoo-bin -c odoo.conf -d <dbname> --test-tags external

# Exclude specific tests
./odoo-bin -c odoo.conf -d <dbname> --test-tags standard,-:TestToExclude

# Legacy flag (implies --test-tags +standard)
./odoo-bin -c odoo.conf -d <dbname> --test-enable

# Install/update a module and run its tests
./odoo-bin -c odoo.conf -d <dbname> -i module_name --test-tags /module_name
```

`--test-tags` implies `--stop-after-init` (server stops after tests).

**Test tag filter format:** `[-][tag][/module][:class][.method][[params]]`

### Linting

```bash
# Python linting (ruff is the primary linter, config in ruff.toml)
ruff check .
ruff check --fix .

# JavaScript linting (from addons/web/tooling after running enable.sh)
npm run lint-all
npm run format-all
npm run lint-diff    # only changed files
npm run format-diff
```

### Module Scaffolding

```bash
./odoo-bin scaffold <module_name> <target_directory>
```

### Shell Access

```bash
./odoo-bin shell -c odoo.conf -d <dbname>
```

## Architecture

### Directory Structure

- `odoo/` -- Core framework: ORM, HTTP server, CLI, tools, service layer
- `odoo/orm/` -- ORM system: field definitions, model classes, decorators, environments, domains
- `odoo/cli/` -- CLI commands (server, shell, scaffold, db, deploy, i18n, etc.)
- `odoo/tools/` -- Shared utilities (config, mail, image, caching, SQL helpers)
- `odoo/addons/` -- Core addons (`base`, plus `test_*` modules for framework tests)
- `addons/` -- 600+ community addon modules (the main application code)

### Module/Addon System

Each addon is a directory with a `__manifest__.py` that defines metadata, dependencies, data files, and asset bundles. Models, views, security rules, and data are loaded per-module during installation.

Key manifest fields: `depends`, `data` (XML/CSV loaded on install), `demo`, `assets` (JS/CSS bundles), `auto_install`, `installable`.

### ORM

- **Model types:** `Model` (persistent, stored in DB), `TransientModel` (temporary, auto-vacuumed), `AbstractModel` (not stored, mixin-only)
- **Key decorators** (`odoo/orm/decorators.py`): `@api.model`, `@api.constrains`, `@api.depends`, `@api.onchange`, `@api.ondelete`
- **Environment** (`odoo/orm/environments.py`): `self.env` provides access to models, cursor, user, and context. `self.env['model.name']` returns a recordset.
- **Domains** (`odoo/orm/domains.py`): Filter expressions as lists of tuples, e.g., `[('field', '=', value)]`
- **Commands** (`odoo/orm/commands.py`): Special ORM write commands for relational fields (`Command.create`, `Command.update`, `Command.delete`, `Command.set`, `Command.link`, `Command.unlink`, `Command.clear`)

### Testing Framework

Tests are unittest-based. Key test classes in `odoo/tests/common.py`:

- **`TransactionCase`** -- Each test method runs in a savepoint (rolled back after each test). Most common test base class.
- **`SingleTransactionCase`** -- All test methods share one transaction (not rolled back between methods).
- **`HttpCase`** -- For testing HTTP endpoints and browser-based tours.

Tagging: `@tagged('at_install')` (default, runs during module install) or `@tagged('post_install', '-at_install')` (runs after all modules loaded).

### Frontend

- **OWL** framework for components (declarative, reactive)
- Asset bundles declared in `__manifest__.py` under the `assets` key
- JS tooling in `addons/web/tooling/` -- run `enable.sh` to activate ESLint/Prettier
- ESLint config: 4-space indent, semicolons, double quotes, 100-char line width
- QUnit for JavaScript unit tests

### Import Ordering (enforced by ruff)

```
future -> standard-library -> third-party -> first-party (odoo) -> local-folder (odoo.addons)
```

## Conventions

- Commit messages follow the pattern: `[TAG] module_name: description` where TAG is IMP, FIX, ADD, REM, REF, MOV, etc.
- XML IDs follow: `module_name.record_type_model_name` (e.g., `sale.action_sale_order`)
- Security access is defined in `security/ir.model.access.csv` and record rules in XML
- Python code follows PEP 8, linted by ruff (config in `ruff.toml`; E501/line-length is NOT enforced)
- Test files live in `tests/` subdirectory of each addon, named `test_*.py`, imported in `tests/__init__.py`
