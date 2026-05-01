#!/usr/bin/env bash
# Build the `demo_esty` database for end-user E2E demo.
#
# Idempotent: drops + recreates the DB on every run.
#
# Prereqs: source Excel at .0temp/Esty main 2 - 15h VN 06 08 2025.xlsx
# (real Etsy orders — used for partner/address fields only, not products).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/odoo/odoo_dev/other_projects/odoo19_esty}"
DB="${DEMO_DB:-demo_esty}"
ODOO_CONTAINER="${ODOO_CONTAINER:-namco_odoo19}"
DB_CONTAINER="${DB_CONTAINER:-esty_mvp_db}"
DB_USER="${DB_USER:-odoo}"
HTTP_PORT="${HTTP_PORT:-8889}"
EXCEL_SRC="$REPO_ROOT/.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx"

if [ ! -f "$EXCEL_SRC" ]; then
    echo "ERROR: source Excel missing: $EXCEL_SRC"
    exit 1
fi

echo "==> [1/5] dropping + recreating $DB"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
     WHERE datname='$DB' AND pid <> pg_backend_pid();" >/dev/null || true
docker exec "$DB_CONTAINER" dropdb --if-exists -U "$DB_USER" "$DB"
docker exec "$DB_CONTAINER" createdb -U "$DB_USER" -O "$DB_USER" "$DB"

echo "==> [2/5] copying source Excel into Odoo container"
docker cp "$EXCEL_SRC" "$ODOO_CONTAINER:/tmp/etsy_main.xlsx"

echo "==> [3/5] installing modules into $DB (no demo data)"
docker exec "$ODOO_CONTAINER" odoo -d "$DB" \
    -i base,multichannel_hub_core,multichannel_hub_fulfillment,etsy_integration \
    --without-demo=all \
    --stop-after-init \
    --http-port="$HTTP_PORT" --workers=0 --max-cron-threads=0

echo "==> [4/5] seeding demo users + products + 30 orders"
docker exec -i "$ODOO_CONTAINER" odoo shell -d "$DB" \
    --http-port="$HTTP_PORT" --workers=0 --max-cron-threads=0 \
    --no-http \
    < "$REPO_ROOT/deployment/scripts/seed-demo-esty.py"

echo "==> [5/5] verifying"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB" -c \
    "SELECT op.code AS pipeline, COUNT(*) AS orders
     FROM sale_order so
     JOIN order_pipeline op ON op.id = so.x_pipeline_id
     WHERE so.client_order_ref LIKE 'DEMO-%'
     GROUP BY op.code ORDER BY op.code;"

cat <<EOF

================================================================
demo_esty ready.

Login URL:   http://localhost:8169/odoo (after switching DB)  OR
             https://odoo.hatafax.com (once nginx points at $DB)

Switch DB:   /web/database/selector  → pick "$DB"

Demo users (password "demo1234"):
  demo_kinhdoanh@hatafax.demo    (Sales / kinh doanh)
  demo_sanxuat@hatafax.demo      (Production team)
  demo_ba_shipping@hatafax.demo  (BA Vận chuyển)
  demo_ba_manager@hatafax.demo   (Quản lý BA Vận chuyển)
  demo_quanly@hatafax.demo       (Sales manager)

Counts: 30 orders, 10 per pipeline, real buyer names + addresses.
Hand the Vietnamese user manual (HUONG_DAN_NGUOI_DUNG.md) to testers.
================================================================
EOF
