---
name: odoo-deployment
description: Deploy, manage, and troubleshoot Odoo Docker containers across development, test, and production. Version-parametric — works for Odoo 15 and Odoo 19. Use whenever the user mentions deploying, redeploying, updating modules on a remote server, building/pushing an image to a registry, checking server health, viewing container logs, rolling back a deploy, or troubleshooting "database manager disabled", filestore loss, container health failures, or UID permission issues.
---

# Odoo Deployment Skill

Deploy and manage Odoo Docker containers across three environments: **development** (local),
**test**, and **production**. Version-parametric: substitute `__ODOO_VERSION__` (e.g. `15` or
`19`) wherever it appears. Keyed to this repo's `deployment/` directory.

> Placeholders used below — replace per project: `__PROJECT__` (module/db/image base name),
> `__ODOO_VERSION__`, `<registry>` (e.g. `ghcr.io/<org>`), `<test-host>` / `<prod-host>`,
> `<db-name>`. Never hardcode private IPs or credentials in this repo — keep them in an
> untracked `.env` (see `deployment/.env.prod.example`).

## Architecture (typical)
```
Local Dev (docker-compose.yml)
  → Build image → Push to <registry>/__PROJECT__:<tag>
    → Test Server   — auto-deploy on `develop` push (or manual)
    → Production     — manual dispatch with approval

Odoo (Docker) → [PgBouncer] → PostgreSQL   |   Nginx → Odoo (8069 / 8072 longpoll)
```
Common constraint: PostgreSQL and Nginx often stay bare-metal; only Odoo runs in Docker.

## Environment matrix (fill per project)
| Env | Container | DB | Branch | Image tag | Auto-deploy |
|-----|-----------|-----|--------|-----------|-------------|
| Development | `__PROJECT___odoo` | `__PROJECT__` (local) | any | local build | N/A |
| Test | `__PROJECT___odoo_test` | `<db-name>` | develop | `:develop` | optional |
| Production | `__PROJECT___odoo` | `<db-name>` | main/master | `:latest` | manual |

Key per-env settings: `DB_FILTER` (prod locks to `^<db-name>$`; test `.*`), `LIST_DB`
(prod `False`, test `True`), `LOG_LEVEL` (prod `warning`, test `debug`), `IMAGE_TAG`.

## Credentials & SSH
Keep all secrets in an untracked `.env`; load with `set -a && source deployment/.env && set +a`.
Reach remote hosts via SSH keys (preferred) or `sshpass -p "$SSH_PASSWORD"`. Never commit
hosts, ports, users, passwords, or tokens — reference them only as `$VAR`.

## Common operations

### 1. Build & push image
```bash
docker build -t <registry>/__PROJECT__:latest .
docker push  <registry>/__PROJECT__:latest
# test channel
docker build -t <registry>/__PROJECT__:develop . && docker push <registry>/__PROJECT__:develop
```

### 2. Deploy (ALWAYS docker compose, never docker run)
```bash
cd <remote-deploy-dir>
docker pull <registry>/__PROJECT__:<tag>
docker compose -f docker-compose.prod.yml down --timeout 60
docker compose -f docker-compose.prod.yml up -d
```
**NEVER `docker run` / `docker stop && rm && run`** — that creates anonymous volumes and
loses the filestore. Always `docker compose` so the bind mount is preserved.

### 3. Upgrade modules on remote
```bash
docker exec __PROJECT___odoo odoo -d <db-name> -u MODULE1,MODULE2 --stop-after-init --no-http
docker compose -f docker-compose.prod.yml restart
```

### 4. Regenerate config from template (Python regex, not envsubst)
`deployment/odoo-server.conf.template` uses `${VAR}` / `${VAR:-default}`. `envsubst` does
not support `:-` defaults — use:
```bash
set -a && source deployment/.env && set +a
python3 -c "
import os, re
t = open('deployment/odoo-server.conf.template').read()
r = re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)(?::-([^}]*?))?\}',
    lambda m: os.environ.get(m.group(1), m.group(2) or ''), t)
open('deployment/odoo-server.conf','w').write(r)
"
```
**Never nest `${}`** inside a default (e.g. `${DB_FILTER:-^${DB_NAME}$}`) — the regex can't
resolve nesting. Use flat vars.

### 5. Logs / health / rollback
```bash
docker logs -f __PROJECT___odoo ; docker logs --tail 100 __PROJECT___odoo
curl -sI http://localhost:8069/web/login          # 200 or 303 (db selector) = healthy
# rollback: re-deploy the previous image tag via docker compose (pin IMAGE_TAG in .env)
```

## Production deploy checklist (MANDATORY)
Skipping these has caused real filestore data loss.

**Pre-deploy**
- [ ] Image built & pushed (`<registry>/__PROJECT__:latest`).
- [ ] Pre-deploy DB + filestore backup taken; verify it is non-zero.

**Deploy** — `docker compose down --timeout 60 && docker compose up -d` (never `docker run`).

**Post-deploy**
- [ ] Container healthy: `docker ps --filter name=__PROJECT___odoo`.
- [ ] **Mount check (CRITICAL)** — `/var/lib/odoo` must be a **bind** mount, not anonymous:
  ```bash
  docker inspect __PROJECT___odoo --format '{{range .Mounts}}{{.Type}}: {{.Source}} -> {{.Destination}}{{println}}{{end}}'
  ```
- [ ] HTTP: `curl -sI http://localhost:8069/web/login` (expect 200/303).
- [ ] Filestore present: `docker exec __PROJECT___odoo ls /var/lib/odoo/filestore/<db-name>/ | wc -l`.
- [ ] No 404s on `.min.js` / `.min.css` asset bundles in the browser.

## CI/CD (GitHub Actions pattern)
A `.github/workflows/deploy.yml` (not shipped in this template — add per project) typically:

| Trigger | Image tags | Action |
|---------|-----------|--------|
| Push `main`/`master` | `:latest`, `:YYYYMMDD`, `:YYYYMMDD-SHA` | Build prod image (no auto-deploy) |
| Push `develop` | `:develop`, `:develop-YYYYMMDD-SHA` | Build test image; deploy test |
| `workflow_dispatch` (production) | `:latest` | Build → backup → deploy → upgrade (requires approval) |

Auto-detect changed modules: `git diff --name-only "$BASE" HEAD -- custom_addons/ | cut -d/ -f2 | sort -u`.
Required GH config: SSH-key secrets + host/user variables; a gated `production` environment.

## Troubleshooting
- **"Database manager has been disabled"** — `dbfilter` matches no DB or is invalid regex.
  Fix the regex in `odoo-server.conf` (regenerate from template); for test set `DB_FILTER=.*`,
  `LIST_DB=True`.
- **`getpwuid(): uid not found`** — a `user: "NNNN:NNNN"` compose directive with no
  `/etc/passwd` entry. Remove `user:` and `chown -R 101:101` the filestore (Odoo image UID 101).
- **Longpolling 404** — normal for the first 30–60 s after start (gevent warm-up). Retry.
- **Login returns 303** — normal when `list_db=True` (redirect to DB selector). Healthy.
- **Unresolved `${VAR:-default}` in config** — caused by `envsubst`; use the Python regen (§4).

## Odoo 15 vs 19 notes
- **Asset regen**: after upgrade, stale asset bundles can 404. Clear with
  `DELETE FROM ir_attachment WHERE name LIKE '%.assets_%.min.%';` then restart (both versions).
- **Container/health endpoints** (`/web/login`, `/web/health`, longpoll 8072) are the same.
- **Python base image** differs: Odoo 15 → Python 3.7–3.10; Odoo 19 → Python 3.12+. Pin the
  matching base in `Dockerfile.base`.

## File locations (this repo)
| Path | Purpose |
|------|---------|
| `deployment/docker-compose.prod.yml` | Production/test container config |
| `deployment/odoo-server.conf.template` | Config template with env vars |
| `deployment/.env.prod.example` | Production env template (copy to untracked `.env`) |
| `deployment/nginx-odoo.example.conf` | Nginx reverse-proxy template |
