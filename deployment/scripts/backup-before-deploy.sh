#!/usr/bin/env bash
# backup-before-deploy.sh — Pre-deployment backup of Odoo 19 Namco DB and filestore
#
# Usage:
#   ./backup-before-deploy.sh
#
# Reads configuration from .env in parent directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env
if [[ -f "$DEPLOY_DIR/.env" ]]; then
    set -a
    source "$DEPLOY_DIR/.env"
    set +a
fi

BACKUP_BASE="${ODOO_BACKUP_DIR:-/odoo/namco19/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/pre_deploy_${TIMESTAMP}"

DB_HOST="${DB_HOST:?DB_HOST not set}"
DB_PORT="${DB_PORT:-6432}"
DB_NAME="${DB_NAME:?DB_NAME not set}"
DB_USER="${DB_USER:?DB_USER not set}"
ODOO_DATA_DIR="${ODOO_DATA_DIR:-/odoo/namco19/.local/share/Odoo}"

echo "========================================="
echo "Pre-Deployment Backup: Odoo 19 Namco"
echo "Timestamp: $TIMESTAMP"
echo "Database: $DB_NAME @ $DB_HOST:$DB_PORT"
echo "Filestore: $ODOO_DATA_DIR"
echo "Backup dir: $BACKUP_DIR"
echo "========================================="

# Create backup directory
mkdir -p "$BACKUP_DIR"

# 1. Database dump
echo ""
echo "--- Dumping database ---"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -Fc \
    "$DB_NAME" \
    > "${BACKUP_DIR}/${DB_NAME}.dump"

DB_SIZE=$(du -sh "${BACKUP_DIR}/${DB_NAME}.dump" | cut -f1)
echo "Database dump: ${DB_SIZE} -> ${BACKUP_DIR}/${DB_NAME}.dump"

# 2. Filestore backup
echo ""
echo "--- Backing up filestore ---"
if [[ -d "$ODOO_DATA_DIR" ]]; then
    tar czf "${BACKUP_DIR}/filestore.tar.gz" -C "$(dirname "$ODOO_DATA_DIR")" "$(basename "$ODOO_DATA_DIR")"
    FS_SIZE=$(du -sh "${BACKUP_DIR}/filestore.tar.gz" | cut -f1)
    echo "Filestore backup: ${FS_SIZE} -> ${BACKUP_DIR}/filestore.tar.gz"
else
    echo "WARNING: Filestore directory not found: $ODOO_DATA_DIR"
fi

# 3. Backup current config
echo ""
echo "--- Backing up configuration ---"
if [[ -f "$DEPLOY_DIR/odoo-server.conf" ]]; then
    cp "$DEPLOY_DIR/odoo-server.conf" "${BACKUP_DIR}/odoo-server.conf.bak"
fi
if [[ -f "$DEPLOY_DIR/.env" ]]; then
    cp "$DEPLOY_DIR/.env" "${BACKUP_DIR}/.env.bak"
fi

# 4. Record current image tag
if docker inspect "${CONTAINER_NAME:-namco_odoo19}" &>/dev/null; then
    docker inspect "${CONTAINER_NAME:-namco_odoo19}" --format='{{.Config.Image}}' \
        > "${BACKUP_DIR}/previous_image.txt" 2>/dev/null || true
fi

echo ""
echo "========================================="
echo "Backup complete: $BACKUP_DIR"
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "Total size: $TOTAL_SIZE"
echo "========================================="
