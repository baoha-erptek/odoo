#!/usr/bin/env bash
#
# push_to_jira.sh — Push a local .md issue file to JIRA via Direct API
#
# Usage:
#   bash .claude/skills/jira-create/scripts/push_to_jira.sh <path-to-md-file>
#
# The .md file must have YAML frontmatter with: type, project, summary
# After successful push, updates frontmatter with jira_key and status=pushed
#
set -euo pipefail

JIRA_BASE_URL="https://${JIRA_SITE:?set JIRA_SITE, e.g. yourco.atlassian.net}"
CREDENTIALS_FILE="${ATLASSIAN_CREDS:-$HOME/.atlassian_credentials}"

# --- Helpers ---

die() { echo "ERROR: $1" >&2; exit 1; }

check_deps() {
    command -v python3 >/dev/null 2>&1 || die "python3 is required"
    command -v curl >/dev/null 2>&1 || die "curl is required"
    [ -f "$CREDENTIALS_FILE" ] || die "Credentials file not found: $CREDENTIALS_FILE"
}

# Extract a frontmatter field value using python (handles YAML safely)
get_field() {
    local file="$1" field="$2"
    python3 -c "
import sys
content = open('$file').read()
if not content.startswith('---'):
    sys.exit(1)
end = content.index('---', 3)
fm = content[3:end]
for line in fm.strip().split('\n'):
    if line.startswith('$field:'):
        val = line.split(':', 1)[1].strip()
        # Remove quotes
        if val.startswith('\"') and val.endswith('\"'):
            val = val[1:-1]
        if val.startswith(\"'\") and val.endswith(\"'\"):
            val = val[1:-1]
        print(val)
        break
" 2>/dev/null
}

# Extract description body (everything after frontmatter)
get_body() {
    local file="$1"
    python3 -c "
content = open('$1').read()
if not content.startswith('---'):
    print(content)
else:
    end = content.index('---', 3) + 3
    body = content[end:].strip()
    print(body)
"
}

# Map type name to JIRA issue type name
map_issue_type() {
    case "$1" in
        epic)  echo "Epic" ;;
        story) echo "Story" ;;
        bug)   echo "Bug" ;;
        task)  echo "Task" ;;
        *)     die "Unknown issue type: $1. Must be: epic, story, bug, task" ;;
    esac
}

# Convert markdown body to Atlassian Document Format (ADF) JSON
# Simple conversion: splits into paragraphs by double newlines
body_to_adf() {
    local body="$1"
    python3 -c "
import json, sys, re

body = '''$body'''

# Split by double newlines into paragraphs
paragraphs = re.split(r'\n\n+', body.strip())

content = []
for para in paragraphs:
    para = para.strip()
    if not para:
        continue

    # Handle headings (## Heading)
    heading_match = re.match(r'^(#{1,6})\s+(.+)$', para, re.MULTILINE)
    if heading_match and '\n' not in para:
        level = len(heading_match.group(1))
        content.append({
            'type': 'heading',
            'attrs': {'level': level},
            'content': [{'type': 'text', 'text': heading_match.group(2)}]
        })
        continue

    # Handle bullet lists
    lines = para.split('\n')
    if all(re.match(r'^[-*]\s+', l.strip()) or re.match(r'^\[.\]\s+', l.strip().lstrip('- ')) for l in lines if l.strip()):
        items = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remove bullet marker
            text = re.sub(r'^[-*]\s+(\[.\]\s+)?', '', line)
            items.append({
                'type': 'listItem',
                'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}]
            })
        if items:
            content.append({'type': 'bulletList', 'content': items})
        continue

    # Handle numbered lists
    if all(re.match(r'^\d+\.\s+', l.strip()) for l in lines if l.strip()):
        items = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            text = re.sub(r'^\d+\.\s+', '', line)
            items.append({
                'type': 'listItem',
                'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}]
            })
        if items:
            content.append({'type': 'orderedList', 'content': items})
        continue

    # Default: paragraph
    content.append({
        'type': 'paragraph',
        'content': [{'type': 'text', 'text': para}]
    })

adf = {
    'type': 'doc',
    'version': 1,
    'content': content if content else [{'type': 'paragraph', 'content': [{'type': 'text', 'text': ' '}]}]
}
print(json.dumps(adf))
"
}

# Update frontmatter in the .md file
update_frontmatter() {
    local file="$1" field="$2" value="$3"
    python3 -c "
content = open('$file').read()
if not content.startswith('---'):
    exit(1)
end = content.index('---', 3)
fm = content[3:end]
body = content[end:]
lines = fm.strip().split('\n')
updated = False
new_lines = []
for line in lines:
    if line.startswith('$field:'):
        new_lines.append('$field: $value')
        updated = True
    else:
        new_lines.append(line)
if not updated:
    new_lines.append('$field: $value')
new_content = '---\n' + '\n'.join(new_lines) + '\n' + body
with open('$file', 'w') as f:
    f.write(new_content)
"
}

# --- Main ---

main() {
    local md_file="${1:-}"
    [ -n "$md_file" ] || die "Usage: push_to_jira.sh <path-to-md-file>"
    [ -f "$md_file" ] || die "File not found: $md_file"

    check_deps

    # Extract frontmatter fields
    local issue_type project summary jira_key status
    issue_type=$(get_field "$md_file" "type")
    project=$(get_field "$md_file" "project")
    summary=$(get_field "$md_file" "summary")
    jira_key=$(get_field "$md_file" "jira_key")
    status=$(get_field "$md_file" "status")

    [ -n "$issue_type" ] || die "Missing 'type' in frontmatter"
    [ -n "$project" ] || die "Missing 'project' in frontmatter"
    [ -n "$summary" ] || die "Missing 'summary' in frontmatter"

    # Check if already pushed
    if [ -n "$jira_key" ] && [ "$jira_key" != "" ]; then
        echo "WARNING: This file was already pushed as $jira_key"
        echo "         Set jira_key to empty in frontmatter to push again."
        exit 1
    fi

    # Map type
    local jira_type
    jira_type=$(map_issue_type "$issue_type")

    # Get body and convert to ADF
    local body adf_json
    body=$(get_body "$md_file")
    adf_json=$(body_to_adf "$body")

    # Build request payload
    local payload
    payload=$(python3 -c "
import json
data = {
    'fields': {
        'project': {'key': '$project'},
        'summary': '$summary',
        'issuetype': {'name': '$jira_type'},
        'description': $adf_json
    }
}
print(json.dumps(data))
")

    echo "Creating $jira_type in $project: $summary"

    # Make API call
    local response http_code
    response=$(bash -c "source $CREDENTIALS_FILE && curl -s -w '\n%{http_code}' -X POST \
        -u \"\${ATLASSIAN_EMAIL}:\${ATLASSIAN_API_TOKEN}\" \
        -H 'Content-Type: application/json' \
        -d '$payload' \
        '$JIRA_BASE_URL/rest/api/3/issue'")

    http_code=$(echo "$response" | tail -1)
    local body_response
    body_response=$(echo "$response" | sed '$d')

    if [ "$http_code" = "201" ]; then
        local new_key
        new_key=$(echo "$body_response" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")
        local issue_url="$JIRA_BASE_URL/browse/$new_key"

        # Update frontmatter
        update_frontmatter "$md_file" "jira_key" "$new_key"
        update_frontmatter "$md_file" "status" "pushed"

        echo ""
        echo "Created: $new_key"
        echo "URL: $issue_url"
        echo "File updated: jira_key=$new_key, status=pushed"
    else
        echo ""
        echo "FAILED (HTTP $http_code)"
        echo "$body_response" | python3 -m json.tool 2>/dev/null || echo "$body_response"
        exit 1
    fi
}

main "$@"
