#!/usr/bin/env bash
# health-check.sh — Verify Odoo 19 Namco container is healthy
#
# Checks:
#   1. Container running
#   2. HTTP /web/health (port 8169)
#   3. Web login page
#   4. WebSocket endpoint (port 8172)
#   5. Database connectivity
#
# Usage:
#   ./health-check.sh [--retries N] [--interval SECONDS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

MAX_RETRIES=10
INTERVAL=10

while [[ $# -gt 0 ]]; do
    case $1 in
        --retries) MAX_RETRIES="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        *) shift ;;
    esac
done

# Source .env
if [[ -f "$DEPLOY_DIR/.env" ]]; then
    set -a
    source "$DEPLOY_DIR/.env"
    set +a
fi

CONTAINER="${CONTAINER_NAME:-namco_odoo19}"
ODOO_URL="http://localhost:8169"
WS_URL="http://localhost:8172"
FAILURES=0

check_pass() { echo "  [PASS] $1"; }
check_fail() { echo "  [FAIL] $1"; FAILURES=$((FAILURES + 1)); }

echo "========================================="
echo "Health Check: $CONTAINER"
echo "URL: $ODOO_URL"
echo "WebSocket: $WS_URL"
echo "========================================="

# 1. Container running
echo ""
echo "--- Check 1: Container status ---"
if docker inspect "$CONTAINER" --format='{{.State.Status}}' 2>/dev/null | grep -q "running"; then
    check_pass "Container is running"
else
    check_fail "Container is not running"
    echo "  Container logs (last 20 lines):"
    docker logs "$CONTAINER" --tail 20 2>&1 | sed 's/^/    /'
    echo ""
    echo "RESULT: FAILED (container not running)"
    exit 1
fi

# 2. HTTP health (with retries for Odoo startup time)
echo ""
echo "--- Check 2: HTTP health (max ${MAX_RETRIES} retries) ---"
HTTP_OK=false
for i in $(seq 1 "$MAX_RETRIES"); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${ODOO_URL}/web/health" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        HTTP_OK=true
        check_pass "HTTP /web/health returned 200 (attempt $i)"
        break
    fi
    echo "  Attempt $i/$MAX_RETRIES: HTTP $HTTP_CODE (waiting ${INTERVAL}s...)"
    sleep "$INTERVAL"
done

if [[ "$HTTP_OK" == false ]]; then
    check_fail "HTTP /web/health not responding after $MAX_RETRIES attempts"
fi

# 3. Web login page accessible
echo ""
echo "--- Check 3: Login page ---"
LOGIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "${ODOO_URL}/web/login" 2>/dev/null || echo "000")
if [[ "$LOGIN_CODE" == "200" || "$LOGIN_CODE" == "303" ]]; then
    check_pass "Login page accessible (HTTP $LOGIN_CODE)"
else
    check_fail "Login page returned HTTP $LOGIN_CODE"
fi

# 4. WebSocket endpoint (Odoo 19 uses /websocket instead of /longpolling)
echo ""
echo "--- Check 4: WebSocket endpoint ---"
WS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${WS_URL}/websocket/health" 2>/dev/null || echo "000")
if [[ "$WS_CODE" == "200" ]]; then
    check_pass "WebSocket endpoint responding (HTTP $WS_CODE)"
elif [[ "$WS_CODE" == "404" || "$WS_CODE" == "426" ]]; then
    echo "  [WARN] WebSocket returned $WS_CODE (gevent worker may need more startup time)"
else
    check_fail "WebSocket endpoint returned HTTP $WS_CODE"
fi

# 5. Database connectivity (check via container)
echo ""
echo "--- Check 5: Database connectivity ---"
if docker exec "$CONTAINER" python3 -c "
import psycopg2, os
conn = psycopg2.connect(
    host=os.environ.get('HOST', 'localhost'),
    port=os.environ.get('PORT', '6432'),
    user=os.environ.get('USER', 'odoo'),
    password=os.environ.get('PASSWORD', ''),
    dbname=os.environ.get('DB_NAME', 'postgres')
)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM ir_module_module WHERE state=%s', ('installed',))
count = cur.fetchone()[0]
print(f'Installed modules: {count}')
conn.close()
" 2>/dev/null; then
    check_pass "Database connection successful"
else
    check_fail "Database connection failed"
fi

# Summary
echo ""
echo "========================================="
if [[ $FAILURES -eq 0 ]]; then
    echo "RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "RESULT: $FAILURES CHECK(S) FAILED"
    exit 1
fi
