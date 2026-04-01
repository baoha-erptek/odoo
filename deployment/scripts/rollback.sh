#!/usr/bin/env bash
# rollback.sh — Revert Odoo 19 Namco to previous Docker image
#
# Usage:
#   ./rollback.sh [--tag IMAGE_TAG]
#
# Without --tag, uses the image recorded during last deploy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

ROLLBACK_TAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) ROLLBACK_TAG="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--tag IMAGE_TAG]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$DEPLOY_DIR"

# Source .env
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Determine rollback image
if [[ -z "$ROLLBACK_TAG" ]]; then
    if [[ -f /tmp/namco_odoo19_previous_image ]]; then
        ROLLBACK_IMAGE=$(cat /tmp/namco_odoo19_previous_image)
    else
        echo "ERROR: No previous image recorded and no --tag specified"
        echo ""
        echo "Available tags:"
        docker images "ghcr.io/baoha-erptek/odoo19-namco" --format "  {{.Tag}}\t{{.CreatedAt}}"
        exit 1
    fi
else
    ROLLBACK_IMAGE="ghcr.io/baoha-erptek/odoo19-namco:${ROLLBACK_TAG}"
fi

echo "========================================="
echo "Rollback: Odoo 19 Namco"
echo "Rolling back to: $ROLLBACK_IMAGE"
echo "Container: ${CONTAINER_NAME:-namco_odoo19}"
echo "========================================="

# Pull the rollback image
echo ""
echo "--- Pulling rollback image ---"
docker pull "$ROLLBACK_IMAGE"

# Update IMAGE_TAG
ROLLBACK_TAG_ONLY="${ROLLBACK_IMAGE##*:}"
export IMAGE_TAG="$ROLLBACK_TAG_ONLY"

# Stop current container
echo ""
echo "--- Stopping current container ---"
docker compose -f docker-compose.prod.yml down --timeout 60 2>/dev/null || true

# Start with rollback image
echo ""
echo "--- Starting rollback container ---"
docker compose -f docker-compose.prod.yml up -d

# Wait and check health
echo ""
echo "--- Checking health ---"
sleep 15

if bash "$SCRIPT_DIR/health-check.sh"; then
    echo ""
    echo "========================================="
    echo "Rollback successful!"
    echo "Running: $ROLLBACK_IMAGE"
    echo "========================================="
else
    echo ""
    echo "WARNING: Health check failed after rollback!"
    echo "Check logs: docker logs ${CONTAINER_NAME:-namco_odoo19}"
    exit 1
fi
