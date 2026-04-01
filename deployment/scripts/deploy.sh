#!/usr/bin/env bash
# deploy.sh — Deploy Odoo 19 Namco Docker container
#
# Usage:
#   ./deploy.sh [--tag IMAGE_TAG] [--skip-backup]
#
# Prerequisites:
#   - Docker and docker compose installed
#   - .env file configured in deployment/ directory
#   - ghcr.io credentials configured (docker login)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
IMAGE_TAG=""
SKIP_BACKUP=false

usage() {
    echo "Usage: $0 [--tag IMAGE_TAG] [--skip-backup]"
    echo ""
    echo "Options:"
    echo "  --tag           Docker image tag to deploy. Default: from .env"
    echo "  --skip-backup   Skip pre-deployment backup"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) IMAGE_TAG="$2"; shift 2 ;;
        --skip-backup) SKIP_BACKUP=true; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

cd "$DEPLOY_DIR"

# Check .env exists
if [[ ! -f .env ]]; then
    echo "ERROR: .env file not found in $DEPLOY_DIR"
    echo "Copy from .env.prod.example and fill in values"
    exit 1
fi

# Source .env for variable access
set -a
source .env
set +a

# Override image tag if provided
if [[ -n "$IMAGE_TAG" ]]; then
    export IMAGE_TAG
fi

echo "========================================="
echo "Odoo 19 Namco - Docker Deployment"
echo "Image: ghcr.io/baoha-erptek/odoo19-namco:${IMAGE_TAG:-latest}"
echo "Container: ${CONTAINER_NAME:-namco_odoo19}"
echo "Database: ${DB_NAME} @ ${DB_HOST}:${DB_PORT:-6432}"
echo "Ports: 8169 (HTTP), 8172 (WebSocket)"
echo "========================================="

# Generate odoo-server.conf from template
echo ""
echo "--- Generating odoo-server.conf from template ---"
if [[ -f odoo-server.conf.template ]]; then
    python3 -c "
import re, os
with open('odoo-server.conf.template') as f:
    content = f.read()
def replace_var(m):
    var = m.group(1)
    default = m.group(2) if m.group(2) is not None else ''
    return os.environ.get(var, default)
result = re.sub(r'\\\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*?))?\}', replace_var, content)
with open('odoo-server.conf', 'w') as f:
    f.write(result)
"
    echo "Generated odoo-server.conf"
else
    echo "ERROR: odoo-server.conf.template not found"
    exit 1
fi

# Pre-deployment backup (unless skipped)
if [[ "$SKIP_BACKUP" == false ]]; then
    echo ""
    echo "--- Running pre-deployment backup ---"
    bash "$SCRIPT_DIR/backup-before-deploy.sh"
fi

# Pull latest image
echo ""
echo "--- Pulling image ---"
docker pull "ghcr.io/baoha-erptek/odoo19-namco:${IMAGE_TAG:-latest}"

# Get current container ID for rollback reference
CURRENT_IMAGE=""
if docker inspect "${CONTAINER_NAME:-namco_odoo19}" &>/dev/null; then
    CURRENT_IMAGE=$(docker inspect "${CONTAINER_NAME:-namco_odoo19}" --format='{{.Config.Image}}' 2>/dev/null || echo "")
    echo "Current image: ${CURRENT_IMAGE:-none}"
    echo "$CURRENT_IMAGE" > /tmp/namco_odoo19_previous_image
fi

# Stop existing container
echo ""
echo "--- Stopping existing container ---"
docker compose -f docker-compose.prod.yml down --timeout 60 2>/dev/null || true

# Start new container
echo ""
echo "--- Starting new container ---"
docker compose -f docker-compose.prod.yml up -d

# Wait for container to start
echo ""
echo "--- Waiting for container to start ---"
sleep 10

# Run health check
echo ""
echo "--- Running health check ---"
if bash "$SCRIPT_DIR/health-check.sh"; then
    echo ""
    echo "========================================="
    echo "Deployment successful!"
    echo "========================================="
else
    echo ""
    echo "WARNING: Health check failed!"
    echo "Check logs: docker logs ${CONTAINER_NAME:-namco_odoo19}"
    if [[ -n "$CURRENT_IMAGE" ]]; then
        echo "To rollback: bash $SCRIPT_DIR/rollback.sh"
    fi
    exit 1
fi
