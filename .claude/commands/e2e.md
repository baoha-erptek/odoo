---
description: Generate and run end-to-end tests for Odoo using agent-browser (default) or Playwright (fallback). Creates test journeys for Odoo workflows, captures screenshots/snapshots, and generates reports.
---

# E2E Command

This command invokes the **e2e-runner** agent to generate, maintain, and execute end-to-end tests for Odoo web interface. Uses **agent-browser** as default tool, with automatic **Playwright** fallback.

## Tool Detection

The agent auto-detects which tool is available:

```bash
if command -v agent-browser &>/dev/null; then
  # PRIMARY: agent-browser — AI-friendly accessibility tree, @e refs
  echo "Using agent-browser"
else
  # FALLBACK: Playwright — TypeScript test framework
  echo "Using Playwright"
fi
```

## What This Command Does

1. **Detect Tool** - Check for agent-browser, fall back to Playwright
2. **Generate Test Journeys** - Create E2E tests for Odoo workflows
3. **Run E2E Tests** - Execute tests against Odoo at `http://localhost:8079`
4. **Capture Artifacts** - Screenshots, snapshots, traces on failures
5. **Generate Report** - Results with pass/fail and artifacts

## When to Use

Use `/e2e` when:
- Testing critical Odoo workflows (HR, attendance, sales)
- Verifying multi-step wizard flows
- Testing UI interactions and navigation
- Validating form submissions and field updates
- Preparing for production deployment

## How It Works

### With agent-browser (Default)

1. **Open Odoo** and take accessibility snapshot
2. **Discover elements** via `snapshot -i` (returns `@e1`, `@e2`... refs)
3. **Interact** using `fill`, `click`, `type` with element refs
4. **Verify** via `snapshot` text content and `wait --text`
5. **Capture** screenshots and snapshot dumps

### With Playwright (Fallback)

1. **Analyze Odoo workflow** and identify test scenarios
2. **Generate Playwright test** using Odoo-specific CSS selectors
3. **Run tests** in headless Chromium
4. **Capture failures** with screenshots, videos, and traces
5. **Generate HTML report** with results and artifacts

## Example Usage

### agent-browser Example

```
User: /e2e Test the attendance sheet creation flow

Agent (e2e-runner):
# E2E Test: Attendance Sheet Workflow

## Tool: agent-browser

## Steps Executed

### 1. Login
agent-browser open http://localhost:8079/web/login
agent-browser snapshot -i
agent-browser fill @e1 "admin"
agent-browser fill @e2 "admin"
agent-browser click @e3
agent-browser wait --text "Discuss"
agent-browser screenshot artifacts/01-logged-in.png

### 2. Navigate to Attendance Sheets
agent-browser find text "Attendances"
agent-browser click @e5
agent-browser find text "Managers"
agent-browser click @e8
agent-browser wait --selector ".o_list_view"
agent-browser screenshot artifacts/02-attendance-list.png

### 3. Create New Sheet
agent-browser find text "Create"
agent-browser click @e12
agent-browser wait --selector ".o_form_view"
agent-browser snapshot -i
agent-browser fill @e15 "Test Employee"
agent-browser wait --text "Test Employee"
agent-browser click @e18
agent-browser screenshot artifacts/03-sheet-created.png

## Results
- Login: PASS
- Navigation: PASS
- Record creation: PASS
- Artifacts: artifacts/01-*.png through artifacts/03-*.png
```

### Playwright Fallback Example

```
User: /e2e Test the sale order creation and confirmation flow

Agent (e2e-runner):
# E2E Test: Sale Order Workflow (Playwright Fallback)

## Generated Test Code

```typescript
import { test, expect } from '@playwright/test'

test.describe('Sale Order Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8079/web/login')
    await page.fill('input[name="login"]', 'admin')
    await page.fill('input[name="password"]', 'admin')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/web#*')
  })

  test('create and confirm sale order', async ({ page }) => {
    await page.click('.o_menu_entry_lvl_1:has-text("Sales")')
    await page.click('.o_menu_entry_lvl_2:has-text("Orders")')
    await page.waitForSelector('.o_list_view')
    await page.click('.o_list_button_add')
    await page.waitForSelector('.o_form_view')
    // ... (full test)
  })
})
```

## Running
npx playwright test tests/e2e/sales/order-workflow.spec.ts
```

## Running Tests

### agent-browser

```bash
# Interactive test (run commands one by one)
agent-browser open http://localhost:8079/web/login
agent-browser snapshot -i
# ... follow snapshot-inspect-act pattern

# With session persistence
agent-browser open http://localhost:8079/web --profile odoo-admin
```

### Playwright

```bash
# Run all E2E tests
ODOO_URL=http://localhost:8079 npx playwright test

# Run specific test
npx playwright test tests/e2e/attendance/sheet.spec.ts

# Debug mode
npx playwright test --debug

# View report
npx playwright show-report
```

## Odoo Selectors Quick Reference

### agent-browser

```bash
agent-browser find text "Save"          # By visible text
agent-browser find role button           # By ARIA role
agent-browser find label "Employee"      # By label text
agent-browser snapshot -i                # Get all @e refs
```

### Playwright

```typescript
page.locator('[data-name="name"] input')              // Field by name
page.locator('.o_field_many2one[name="partner_id"]')   // Many2one
page.locator('.o_form_button_save')                    // Save button
page.locator('button[name="action_confirm"]')          // Action button
page.locator('.o_statusbar_status button.btn-primary') // Active state
```

## Odoo Critical Flows

**CRITICAL (Must Always Pass):**
1. User can login
2. User can navigate to module
3. User can create/edit records
4. Workflow buttons work (confirm, cancel, etc.)
5. Computed fields update correctly
6. One2many/Many2many fields work

**IMPORTANT:**
1. Search filters work
2. Reports generate correctly
3. Wizards complete successfully
4. Attachments upload
5. Chatter messages post

## Best Practices

**DO:**
- Run tool detection before starting
- Use `snapshot -i` (agent-browser) or Odoo-specific selectors (Playwright)
- Wait after actions that trigger network requests
- Capture screenshots at key workflow steps
- Use test database, not production

**DON'T:**
- Hardcode `@e` refs across snapshots (they change per page load)
- Hardcode CSS classes that may change between Odoo versions
- Test against production database
- Ignore Odoo's loading states
- Test every edge case with E2E (use unit tests for that)

## Environment

```bash
# This workspace
ODOO_URL=http://localhost:8079
ODOO_DB=__PROJECT__
ODOO_USER=admin
ODOO_PASSWORD=admin
```

## Related

- **Agent**: `.claude/agents/e2e-runner.md`
- **Skill**: `.claude/skills/agent-browser/SKILL.md`
- **Playwright fallback**: Playwright MCP plugin
