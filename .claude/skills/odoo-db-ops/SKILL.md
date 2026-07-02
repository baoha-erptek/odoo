---
name: odoo-db-ops
description: Restore, initialize, migrate, and create isolated test Odoo databases in a Docker Compose environment. Version-parametric — works for Odoo 15 and Odoo 19. Use when the user asks to restore a backup, init a fresh DB, update/migrate modules, spin up an isolated test database, or fix post-restore issues (blank login, missing assets, CSRF errors, production crons still firing).
---

# Odoo DB Ops (restore · init · migrate · fresh test DB)

All operations run inside the existing Docker containers — no new containers are created.
Version-parametric: the flow is identical for Odoo 15 and 19.

> Placeholders — replace per project: `__PROJECT___odoo` (Odoo container), `__PROJECT___db`
> (PostgreSQL container), `__PROJECT__` (main DB name), web port `8069`. DB user/password
> come from `.env` (`odoo`/`odoo` in the template default).

## Restore from backup

An Odoo backup zip contains `dump.sql` + `filestore/<db>/`. Restore procedure:
```bash
docker compose stop __PROJECT___odoo                 # release DB locks
docker exec __PROJECT___db dropdb   -U odoo --if-exists __PROJECT__
docker exec __PROJECT___db createdb -U odoo __PROJECT__
# load dump (unzip first; large dumps take 10-20 min)
docker exec -i __PROJECT___db psql -U odoo -d __PROJECT__ < dump.sql
# restore filestore into the container's data dir, then start Odoo
docker compose up -d __PROJECT___odoo
```

### Post-restore steps (MANDATORY on a dev box)
Skipping these causes blank login pages, upgrade failures, and **production crons firing
against your dev data**.
```bash
# 1. Filestore perms
docker exec -u root __PROJECT___odoo chown -R odoo:odoo /var/lib/odoo/filestore/__PROJECT__/

# 2. Deactivate ALL cron jobs (stop Odoo first to release locks)
docker compose stop __PROJECT___odoo
docker exec __PROJECT___db psql -U odoo -d __PROJECT__ -c "UPDATE ir_cron SET active = false;"
docker compose start __PROJECT___odoo

# 3. Clear stale sessions (fixes CSRF login errors) + fix base URL
docker exec __PROJECT___db psql -U odoo -d __PROJECT__ -c "DELETE FROM ir_sessions;"
docker exec __PROJECT___db psql -U odoo -d __PROJECT__ \
  -c "UPDATE ir_config_parameter SET value='http://localhost:8069' WHERE key='web.base.url';"

# 4. Drop stale asset bundles so they regenerate, then restart
docker exec __PROJECT___db psql -U odoo -d __PROJECT__ \
  -c "DELETE FROM ir_attachment WHERE name LIKE '%.assets_%' OR url LIKE '/web/assets%';"
docker compose restart __PROJECT___odoo
```
Verify: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8069/web/login` (200),
assets regenerated (`SELECT COUNT(*) FROM ir_attachment WHERE name LIKE '%assets%';` > 0),
and no active crons.

## Initialize a fresh DB
```bash
docker exec __PROJECT___odoo odoo -d __PROJECT__ -i base --stop-after-init
docker exec __PROJECT___odoo odoo -d __PROJECT__ -i base,sale,account --stop-after-init
```

## Migrate / update modules
```bash
docker exec __PROJECT___odoo odoo -d __PROJECT__ -u <module> --stop-after-init
docker exec __PROJECT___odoo odoo -d __PROJECT__ -u all --stop-after-init
```

## Isolated test databases (never touch the main DB)

Create ticket/feature-scoped test DBs, CLI-only, so `__PROJECT__` stays clean. Convention:
prefix every test DB with `test_`; `dbfilter` in `odoo.conf` keeps them off the web.

### Strategies
| Strategy | Speed | When |
|----------|-------|------|
| Fresh empty (`base`) | ~30s | simple ORM/model unit tests |
| Fresh + seed data | 2-5 min | need demo/fixture data |
| Partial clone from prod/test | 5-10 min | need realistic data |
| **Template clone** (`createdb -T`) | ~10s | repeated/CI-like runs |

### Fresh test DB
```bash
docker exec __PROJECT___db createdb -U odoo test_MY_CASE
docker exec __PROJECT___odoo odoo -d test_MY_CASE -i base,<modules> --stop-after-init
docker exec __PROJECT___odoo odoo -d test_MY_CASE --test-enable -u <module> --stop-after-init
```

### Template-clone (fast repeated runs)
Build a template DB once (modules installed), then clone per test in ~10s:
```bash
# one-time: build template
docker exec __PROJECT___db createdb -U odoo test_tpl_base
docker exec __PROJECT___odoo odoo -d test_tpl_base -i base,<modules> --stop-after-init
# per test: clone (Postgres template copy — Odoo must be stopped or DB idle)
docker exec __PROJECT___db createdb -U odoo -T test_tpl_base test_MY_CASE
```
Rebuild the template after a custom-module version bump, or the clone tests stale code.

### Cleanup
```bash
docker exec __PROJECT___db dropdb -U odoo --if-exists test_MY_CASE
# list test DBs:
docker exec __PROJECT___db psql -U odoo -lqt | awk -F'|' '$1 ~ /test_/ {print $1}'
```

## Gotchas (hard-won)

### Worktree bind-mount trap
Running `docker compose up` from a git worktree can mount the worktree's empty
`custom_addons/` instead of the main repo's — custom modules vanish (`KeyError: '<model>'`).
**Always** start Docker from the main repo root, not a worktree. Diagnose:
`docker inspect __PROJECT___odoo --format '{{json .Mounts}}' | python3 -m json.tool | grep -B2 addons`.

### `session_replication_role` bypasses FK/triggers but NOT null constraints
When bulk-inserting via `SET session_replication_role = 'replica'`, required columns still
fail — and in `psql -c` multi-statement mode the failure can be silent. Check NOT NULL
columns first, and keep `SET` + `INSERT` in the **same** `-c` argument (a heredoc loses
session state between statements):
```bash
docker exec __PROJECT___db psql -U odoo -d <db> -tAc "
SELECT column_name FROM information_schema.columns
WHERE table_name='<table>' AND is_nullable='NO' AND column_name!='id'"
```

### 15 vs 19
- Asset regen SQL and login/health checks are identical across versions.
- Backup/restore format (`dump.sql` + `filestore/`) is the same.
- Match the container's Python base to the Odoo version (15 → 3.7–3.10, 19 → 3.12+).

## Safety checklist
- [ ] Never drop/restore onto `__PROJECT__` by accident — confirm the DB name.
- [ ] Test DBs prefixed `test_`; `dbfilter` keeps them off the web.
- [ ] Post-restore: crons deactivated, sessions cleared, assets regenerated.
