# Workspace: odoo19_esty

## Core Philosophy

You are Claude Code configured for Odoo 19 CE development with specialized agents and skills.

**Key Principles:**
1. **Agent-First**: Delegate to specialized agents for complex work
2. **Parallel Execution**: Use Task tool with multiple agents when possible
3. **Plan Before Execute**: Use Plan Mode for complex module implementations
4. **Two-Phase Testing**: Phase 1 (DB verification), Phase 2 (ORM unit tests)
5. **Security-First**: ACLs, record rules, documented sudo()

---

## Environment Configuration

### Self-Contained Docker Setup

This repository is independently deployable. All Docker infrastructure is included.

```bash
# Build and run
docker compose build
docker compose up -d
```

### Container Information
| Component | Container Name | External Port | Internal Port |
|-----------|---------------|---------------|---------------|
| Odoo Web | `namco_odoo19` | **8169** | 8069 |
| WebSocket | `namco_odoo19` | **8172** | 8072 |
| PostgreSQL | `db` | **5432** | 5432 |

### Database Information
- **Database Name**: `namco_odoo19`
- **Database User**: `odoo`
- **Database Password**: `odoo`
- **Admin Password**: `adminadmin`

### Access URLs
- **Odoo Web Interface**: http://localhost:8169

### Quick Commands
```bash
# Build image
docker compose build

# Start containers
docker compose up -d

# View logs
docker logs -f namco_odoo19

# Access Odoo container
docker exec -it namco_odoo19 bash

# Update module
docker exec namco_odoo19 odoo -d namco_odoo19 -u <module_name> --stop-after-init

# Run tests
docker exec namco_odoo19 python3 -m odoo.tests.loader <module_name>.tests

# Run tests with tags
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /<module_name> --stop-after-init

# Restart containers
docker compose restart

# Stop and remove volumes (fresh start)
docker compose down -v

# Linting (ruff is the primary linter, config in ruff.toml)
ruff check custom_addons/
ruff check --fix custom_addons/
```

---

## Odoo 19 Architecture

### Framework
- **Python**: 3.10-3.13, **PostgreSQL**: 13+, **Node.js**: 16.11+
- **Frontend**: OWL 2.0 (reactive components), QUnit for JS tests
- **ORM**: Custom ORM over PostgreSQL with Environment, Recordsets, Domains
- **Linting**: ruff (Python), ESLint/Prettier (JS via `addons/web/tooling/`)

### Model Types
- `Model` — persistent, stored in DB
- `TransientModel` — temporary, auto-vacuumed (wizards)
- `AbstractModel` — not stored, mixin-only

### Key Decorators
- `@api.depends` — computed field dependencies (REQUIRED)
- `@api.constrains` — data validation
- `@api.onchange` — UI-only updates
- `@api.model` — class-level method
- `@api.model_create_multi` — batch create
- `@api.ondelete` — custom delete behavior

### Testing Framework
- `TransactionCase` — each test in savepoint (rolled back). Most common.
- `SingleTransactionCase` — shared transaction across methods.
- `HttpCase` — HTTP endpoints and browser tours.
- Tags: `@tagged('at_install')` (default) or `@tagged('post_install', '-at_install')`

### ORM Commands (relational field writes)
`Command.create`, `Command.update`, `Command.delete`, `Command.set`, `Command.link`, `Command.unlink`, `Command.clear`

---

## Project Structure

```
odoo19_esty/
├── custom_addons/           # Custom Odoo 19 modules
│   └── etsy_integration/    # Main module: Etsy order email ingestion
├── odoo/                    # Odoo 19 CE source code
├── addons/                  # Standard Odoo 19 addons (~619)
├── specs/                   # Spec-kit planning documents
│   └── 001-etsy-order-migration/
├── deployment/              # Docker Compose production setup
├── .claude/                 # Agents, skills, hooks, rules, scripts
├── Dockerfile               # Project layer (extends odoo19-base)
├── Dockerfile.base          # Base image definition
├── odoo.conf                # Odoo server configuration
├── entrypoint.sh            # Container entrypoint
├── ruff.toml                # Python linter config
├── requirements.txt         # Python dependencies
└── CLAUDE.md                # This file
```

### Module Layout
```
├── __manifest__.py          # Version 19.0.1.0.0, depends: sale_management, stock, contacts, mail
├── models/                  # etsy_shop, etsy_email_log, sale_order, product, partner, config
├── services/                # email_parser (ORM-free), gmail_client, order_creator, image_downloader
├── views/                   # Form/tree/search views, menus
├── wizards/                 # Import orders wizard
├── security/                # ir.model.access.csv, etsy_security.xml
├── data/                    # ir_cron_data.xml (10-min email polling)
└── tests/                   # test_email_parser, test_order_creation, test_deduplication
```

---

## Default Skill - Odoo 19 Developer (Priority 1)

**Location**: `.claude/skills/odoo-19-developer/`
**Auto-enabled**: Yes

Complete Odoo 19 CE development reference including ORM, OWL 2.0, views, testing, security.

**Baseline**: [SKILL.md](.claude/skills/odoo-19-developer/SKILL.md) (always loaded)

---

## Available Agents

Located in `.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Module implementation planning | Complex features, module design |
| architect | System design, inheritance patterns | Architectural decisions, dependencies |
| tdd-guide | Two-phase test-driven development | New features, bug fixes |
| code-reviewer | Code quality, ORM, security review | After writing code |
| security-reviewer | ACL validation, sudo audit | New models, sensitive data |
| e2e-runner | Playwright E2E with Odoo selectors | Critical user flows |
| refactor-cleaner | Dead code cleanup | Code maintenance |
| doc-updater | Documentation from __manifest__.py | Documentation updates |
| ascii-ui-mockup-generator | ASCII UI mockups | UI concept visualization |
| odoo-build-error-resolver | Module install/upgrade errors | Module update failures |

---

## Modular Rules System

**Location**: `.claude/rules/`

| Directory | Scope | Path Activation |
|-----------|-------|-----------------|
| `rules/common/` | General coding, git, testing, security, agents | Always active |
| `rules/odoo/` | Odoo-specific patterns, Two-Phase Testing | `custom_addons/**/*.py`, `custom_addons/**/*.xml` |

---

## Master Plan 006 — Execution Contract (MANDATORY)

When implementing any slice from `.claude/plans/006-master-plan-tracking.md`,
**you MUST follow `.claude/plans/006-implementation-playbook.md` strictly**.
This is non-negotiable — past sessions cut corners and produced rework.

**Two anchor docs (always read both at session start when picking up MP006 work):**

| Doc | Role |
|-----|------|
| `.claude/plans/006-master-plan-tracking.md` | The *what* — which slice next, owner, blockers, external deps |
| `.claude/plans/006-implementation-playbook.md` | The *how* — per-slice 9-phase loop, agent dispatch, document hygiene, branching |

**Per-slice 9-phase loop** (Phase 0 Dispatch → Phase 8 Learn → Phase 9 Land):

0. **Dispatch**: read tracker, verify branch is `feature/006-master-plan-coding` (revised 2026-04-27), `TaskCreate` items per slice task + per exit criterion
1. **Plan**: spawn `planner` agent (skip only for trivial < ~50-LOC slices)
2. **RED**: spawn `tdd-guide`; write Phase 1 (DB) + Phase 2 (ORM) failing tests first
3. **GREEN**: implement minimum to pass
4. **Review**: spawn `code-reviewer` + `security-reviewer` in **parallel** (single message, two `Agent` calls); block on CRITICAL/HIGH
5. **Verify**: `odoo -u <module> --stop-after-init`, run test tags, ruff (if available), grep for `_logger.info`/`print(`
6. **Commit**: one conventional commit per checkpoint on `feature/006-master-plan-coding`; cite task IDs in body
7. **Document**: update `tasks.md` `[X]`, tracker `state` + `last reviewed`, ADR / `findings.md` if needed
8. **Learn**: run `/learn` to capture surprises into auto-memory
9. **Land**: feature-branch commits accumulate; merge to `main` after W7 E2E sprint

**Acceptable shortcuts** (rare): trivial scaffold slices (< ~50 LOC, no business logic) may skip Phases 1, 2, 4, 8 — but explicitly note the skip in the commit body and the slice exit-criteria checklist. Never skip Phase 5 (verify) or Phase 6 (commit hygiene).

**Slice exit criteria** (machine-checkable, all required):
- Every slice task `[X]` in `tasks.md`
- Tests pass; coverage ≥80% on changed lines
- Module installs cleanly (`-u <module> --stop-after-init` exit 0)
- ACLs defined for any new model; `sudo()` commented; raw SQL commented
- Tracker `state` updated; blockers documented
- `/learn` insight captured (or explicit "no new patterns" note)
- `findings.md` updated if anything surprised us

**When the playbook breaks** (ambiguous spec, blocker mid-slice, contradicting ADRs): **STOP**, do not improvise. Update tracker `state→blocked`, append to `findings.md`, escalate to user with the contradiction documented. Resume only when blocker has a written resolution.

### Telegram-triggered slice dispatch

When a Telegram DM arrives (`<channel source="telegram" user="...">`) from an allowlisted owner ID (`1013317517` or `8560005895`, per memory `reference_telegram_routing.md`) AND the message body matches one of:

- `^dispatch\s+next\s*$` → invoke `/dispatch-slice` skill with `next`
- `^dispatch\s+(P\d+-\d+[a-z]?)\s*$` → invoke `/dispatch-slice` skill with the matched slice ID

route the message into the skill via the `Skill` tool BEFORE writing any other reply. Reject group-chat triggers (`-5233783589` is a different project). Reply via `telegram.reply` with: chosen slice ID + branch/tree state + planner dispatch confirmation. The skill itself enforces Phase 0 hygiene (clean tree, correct branch, dependencies satisfied); refuse and explain via `telegram.reply` if any check fails.

This rule exists because the harness does not auto-invoke skills on Telegram message arrival — without it, default Claude behavior is a freeform chat reply, which would skip Phase 0 hygiene.

---

## Specs Reference

Planning documents for the Etsy-to-Odoo migration at `specs/001-etsy-order-migration/`:

| Document | Description |
|----------|-------------|
| spec.md | Feature spec with 10 user stories (US1-US10) |
| plan.md | 3-phase implementation plan |
| tasks.md | 57 actionable tasks by phase |
| data-model.md | 7 Odoo models design |
| research.md | Technical research on Etsy API + Odoo 19 CE |
| investigation.md | BA + Tech + Devil's Advocate analysis |
| contracts/ | Service layer contracts (email-parser, gmail-client, order-creator, image-downloader) |
| agent-reports/ | Detailed analysis reports |

---

## Git Workflow

### Commit Message Format
```
[module_name] type(scope): description
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

### Branch Naming
```
feature/short-description
bugfix/short-description
```

### Conventions
- Odoo upstream uses: `[TAG] module_name: description` (TAG: IMP, FIX, ADD, REM, REF, MOV)
- XML IDs: `module_name.record_type_model_name` (e.g., `etsy_integration.action_etsy_shop`)
- Import order: `future -> stdlib -> third-party -> odoo -> odoo.addons`

---

## Hook Configuration

`.claude/hooks.json` -- 3 lifecycle events:

| Event | Hook | Purpose |
|-------|------|---------|
| **PostToolUse** (Edit/Write) | `post-edit-python-check.sh` | Python syntax/debug check on edited files |
| **Stop** | `check-debug-statements.sh` | Scan modified `.py` for `print()` / `_logger.info` |
| **PreToolUse** (Bash) | Inline | Git push review reminder |

---

## Tools & MCP Servers

| Tool | Purpose |
|------|---------|
| `context7` | Explore library/package docs (use for Odoo 19 API reference) |
| `serena` | Semantic retrieval and editing |

---

## Success Metrics

You are successful when:
- All tests pass (80%+ coverage)
- ACLs defined for all new models
- Record rules for sensitive data
- sudo() usage documented
- No `_logger.info` for debugging (use `_logger.debug`)
- No `print()` statements
- Module installs and updates cleanly
- Code passes `ruff check`

---

**Philosophy**: Agent-first design, parallel execution, plan before action, two-phase testing, security always.

**Full Odoo 19 development guidelines**: See `.claude/skills/odoo-19-developer/SKILL.md`

## Active Technologies
- Python 3.12+ (Odoo 19 CE) + Odoo 19 CE (sale_management, stock, contacts, mail), openpyxl (002-etsy-config-fixes)
- PostgreSQL 16+ via Odoo ORM (002-etsy-config-fixes)
- Python 3.12+ (Odoo 19 CE) + Odoo 19 CE (sale_management, stock, contacts, mail), requests (bundled) (005-etsy-api-channel)
- Python 3.12+ (Odoo 19 CE) + Odoo 19 CE (`sale_management`, `stock`, `contacts`, `mail`); no Enterprise modules per ADR-004 (003-dashboard-design-multichannel)
- PostgreSQL 16+ via Odoo ORM. Design files: GDrive-URL primary (ADR-006 + ADR-012); filestore (`ir.attachment` with `attachment=True` Binary fields) for previews ≤ 2 MB; 10 MB hard cap on filestore Binary writes (`multichannel_hub.large_file_threshold_bytes` `ir.config_parameter`) (003-dashboard-design-multichannel)

## Recent Changes
- 002-etsy-config-fixes: Added Python 3.12+ (Odoo 19 CE) + Odoo 19 CE (sale_management, stock, contacts, mail), openpyxl
