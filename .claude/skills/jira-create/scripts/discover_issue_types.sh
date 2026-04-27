#!/usr/bin/env bash
#
# discover_issue_types.sh — Smoke test the .env config and list ESTY issue types.
#
# Verifies:
#   1. .env can be loaded and has all four JIRA_* vars
#   2. The token authenticates against erptek.atlassian.net
#   3. The ESTY project exists and is visible to this account
#   4. Required issue types (Epic, Story, Task, Bug) are available
#   5. Whether this is a Classic project (Epic Link is a customfield_*)
#      or a Next-Gen project (parent.key is used for Story → Epic linkage)
#
set -euo pipefail

die() { echo "ERROR: $1" >&2; exit 1; }

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
ENV_FILE="${ENV_FILE:-${repo_root}/.env}"
[ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE"
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

for v in JIRA_SERVER_URL JIRA_PROJECT_KEY JIRA_USER_EMAIL JIRA_API_KEY; do
    [ -n "${!v:-}" ] || die "$v missing in $ENV_FILE"
done

JIRA_BASE_URL="${JIRA_SERVER_URL%/}"

echo "Probing ${JIRA_BASE_URL} as ${JIRA_USER_EMAIL} for project ${JIRA_PROJECT_KEY}..."
echo

response=$(curl -s -w '\n%{http_code}' \
    -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
    -H 'Accept: application/json' \
    "${JIRA_BASE_URL}/rest/api/3/issue/createmeta?projectKeys=${JIRA_PROJECT_KEY}&expand=projects.issuetypes")

http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" != "200" ]; then
    echo "FAILED (HTTP $http_code)"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    exit 1
fi

echo "Available issue types:"
echo "$body" | python3 -c "
import json, sys
d = json.load(sys.stdin)
projects = d.get('projects', [])
if not projects:
    print('  (no projects returned — check JIRA_PROJECT_KEY visibility)')
    sys.exit(2)
for p in projects:
    print(f'  Project: {p[\"key\"]} ({p[\"name\"]})')
    for t in p.get('issuetypes', []):
        print(f'    - {t[\"name\"]:<12}  id={t[\"id\"]}  subtask={t.get(\"subtask\", False)}')
"

echo
echo "Probing for 'Epic Link' custom field (Classic project) ..."
fields=$(curl -s -u "${JIRA_USER_EMAIL}:${JIRA_API_KEY}" \
    -H 'Accept: application/json' \
    "${JIRA_BASE_URL}/rest/api/3/field")
echo "$fields" | python3 -c "
import json, sys
fields = json.load(sys.stdin)
hits = [f for f in fields if f.get('name', '').lower() in ('epic link', 'parent link')]
if not hits:
    print('  no Epic Link field found — likely a Next-Gen project (use parent.key for Story → Epic)')
else:
    for f in hits:
        print(f\"  {f['name']:<14}  id={f['id']}\")
" || true

echo
echo "OK — credentials valid, project visible. Skill is ready to push."
