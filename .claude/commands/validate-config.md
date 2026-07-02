---
allowed-tools: Bash
description: Validate all Claude Code configuration files (hooks, agents, rules)
---

# /validate-config - Configuration Validation

Run all validation scripts to check Claude Code configuration integrity.

## Usage
```
/validate-config
```

## Workflow

Run the three validation scripts and report combined results:

```bash
# Run all validators
echo "============================================"
echo "  Claude Code Configuration Validation"
echo "============================================"
echo ""

TOTAL_ERRORS=0

# 1. Validate hooks
bash .claude/scripts/ci/validate-hooks.sh
TOTAL_ERRORS=$((TOTAL_ERRORS + $?))
echo ""

# 2. Validate agents
bash .claude/scripts/ci/validate-agents.sh
TOTAL_ERRORS=$((TOTAL_ERRORS + $?))
echo ""

# 3. Validate rules
bash .claude/scripts/ci/validate-rules.sh
TOTAL_ERRORS=$((TOTAL_ERRORS + $?))
echo ""

echo "============================================"
if [ $TOTAL_ERRORS -eq 0 ]; then
  echo "  ALL VALIDATIONS PASSED"
else
  echo "  $TOTAL_ERRORS TOTAL ERROR(S) FOUND"
fi
echo "============================================"
```

## Output Format

```
============================================
  Claude Code Configuration Validation
============================================

=== Validating hooks.json ===
PASS: Valid JSON
PASS: Has 'hooks' key
PASS: All event types and hook structures valid

=== Validating agents ===
PASS: architect.md
PASS: code-reviewer.md
...

=== Validating rules ===
PASS: common/coding-style.md
PASS: odoo/coding-style.md (with paths)
...

============================================
  ALL VALIDATIONS PASSED
============================================
```
