#!/usr/bin/env bash
# Nightly: restore prod DB snapshot into staging on 129.150.63.207.
#
# Run from cron at 02:00 server time:
#   0 2 * * *  /odoo/namco19/scripts/nightly-restore-from-prod.sh >> /var/log/odoo19/nightly-restore.log 2>&1
#
# Assumes:
# - SSH key authentication to prod (Odoo 15 host) for read-only `pg_dump`.
# - Local PgBouncer on 6432 → Postgres on 5432.
# - Staging DB name = `namco_odoo19_staging` (NEVER overwrites the prod-restore
#   target; staging Odoo container reads this DB).

set -euo pipefail

# ---- CONFIG (override via /etc/default/odoo19-staging) -----------------------
PROD_HOST="${PROD_HOST:-prod.namco.local}"
PROD_USER="${PROD_USER:-odoo}"
PROD_DB="${PROD_DB:-namco_odoo15}"
STAGING_DB="${STAGING_DB:-namco_odoo19_staging}"
STAGING_PG_USER="${STAGING_PG_USER:-odoo}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-/odoo/namco19/snapshots}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"

[ -f /etc/default/odoo19-staging ] && . /etc/default/odoo19-staging

mkdir -p "$SNAPSHOT_DIR"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP="$SNAPSHOT_DIR/${PROD_DB}_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] starting prod→staging restore"

# ---- 1. dump prod (read-only, no locks) -------------------------------------
ssh -o StrictHostKeyChecking=accept-new "${PROD_USER}@${PROD_HOST}" \
    "pg_dump --no-owner --no-acl --clean --if-exists ${PROD_DB} | gzip -9" \
    > "$DUMP"

echo "[$(date -Iseconds)] dump complete: $(du -h "$DUMP" | cut -f1) at $DUMP"

# ---- 2. drop+recreate staging DB --------------------------------------------
psql -U "$STAGING_PG_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
     WHERE datname='${STAGING_DB}' AND pid <> pg_backend_pid();" || true
dropdb --if-exists -U "$STAGING_PG_USER" "$STAGING_DB"
createdb -U "$STAGING_PG_USER" -O "$STAGING_PG_USER" "$STAGING_DB"

# ---- 3. restore -------------------------------------------------------------
gunzip -c "$DUMP" | psql -U "$STAGING_PG_USER" -d "$STAGING_DB" -v ON_ERROR_STOP=1

# ---- 4. neutralize prod outbound calls (CRITICAL — staging must never push
#        tracking/email to real customers!) ---------------------------------
psql -U "$STAGING_PG_USER" -d "$STAGING_DB" <<'SQL'
-- Disable all outbound mail servers.
UPDATE ir_mail_server SET active=false;

-- Cron: disable any cron that sends to external services.
UPDATE ir_cron SET active=false
 WHERE model_id IN (
     SELECT id FROM ir_model
      WHERE model IN ('mail.mail', 'etsy.shop', 'etsy.api.client'));

-- Mark base URL as staging.
DELETE FROM ir_config_parameter WHERE key='web.base.url';
INSERT INTO ir_config_parameter(key, value) VALUES ('web.base.url', 'https://odoo.hatafax.com');

-- Etsy: flip to dev token (api_environment='dev').
UPDATE etsy_shop SET api_environment='dev', active_source='email'
 WHERE api_environment IS NOT NULL;

-- Gearment: clear API keys to force re-config (sandbox keys live in .env).
UPDATE ir_config_parameter
   SET value = ''
 WHERE key LIKE 'gearment.%';
SQL

# ---- 5. trigger module update so any new code on the staging tree applies ---
docker exec namco_odoo19 odoo -d "$STAGING_DB" \
    -u multichannel_hub_core,multichannel_hub_fulfillment,etsy_integration \
    --stop-after-init --no-http || {
    echo "[$(date -Iseconds)] WARNING: -u failed, manual review required"
    exit 1
}

# ---- 6. retention ----------------------------------------------------------
find "$SNAPSHOT_DIR" -name '*.sql.gz' -mtime +"$RETAIN_DAYS" -delete

echo "[$(date -Iseconds)] restore complete; staging DB=${STAGING_DB}"
