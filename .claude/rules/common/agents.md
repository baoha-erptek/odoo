# Agent Delegation Rules

## When to Delegate
- **planner**: Complex features requiring multi-step planning
- **architect**: Module design, inheritance decisions, manifest dependencies
- **tdd-guide**: New features or bug fixes requiring test coverage
- **code-reviewer**: After writing code, before committing
- **security-reviewer**: New models, sensitive data handling, sudo usage
- **e2e-runner**: Critical user flows requiring browser testing
- **refactor-cleaner**: Dead code identification and removal
- **doc-updater**: Documentation sync from source files
- **odoo-build-error-resolver**: Module install/upgrade failures

## Parallel Execution
- Launch independent agents concurrently using Task tool
- Common parallel patterns:
  - code-reviewer + security-reviewer (after implementation)
  - planner + architect (during design phase)
  - tdd-guide + e2e-runner (during test phase)

## Agent Chain Patterns
- **Feature**: planner -> tdd-guide -> code-reviewer -> security-reviewer
- **Bugfix**: architect -> tdd-guide -> code-reviewer
- **Security**: security-reviewer -> code-reviewer -> architect
