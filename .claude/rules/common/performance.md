# Performance Optimization

## Model Selection Strategy

**Haiku** (fast, cheapest — mechanical work):
- Lightweight agents with frequent invocation
- Deterministic transforms, scaffolding, mockups
- Worker agents in multi-agent systems

**Sonnet** (best coding model — the default working tier):
- Code review, testing, refactoring, documentation
- Structured execution against a plan
- Most day-to-day coding tasks

**Opus** (deepest reasoning — reserve it):
- Complex architectural decisions
- Multi-file planning and design
- Research and analysis tasks

> Cost note: running every agent on Opus is the single biggest source of
> per-session overspend (observed ~2.4x cost/session vs a tiered mix). Default
> agents to Sonnet; escalate to Opus only for planning/architecture.

## Agent Model Assignments

Binding table — the source of truth for each agent's tier. The advisory hook
`.claude/scripts/check-agent-model-tier.sh` (PreToolUse on Task) warns when an
agent's frontmatter `model:` drifts from this table. Keep the model column to a
bare `opus` / `sonnet` / `haiku` matching the agent `.md` frontmatter.

| Agent | Model | Rationale |
|-------|-------|-----------|
| `planner` | opus | Multi-step implementation planning, dependency reasoning |
| `architect` | opus | System design, inheritance decisions, ADRs |
| `product-owner` | sonnet | Requirement/spec review, acceptance-criteria + standard-Odoo triage |
| `code-reviewer` | sonnet | Structured review against known patterns |
| `security-reviewer` | sonnet | ACL/record-rule/sudo audit against checklist |
| `tdd-guide` | sonnet | Test scaffolding and RED/GREEN execution |
| `e2e-runner` | sonnet | Browser/HttpCase test authoring and runs |
| `refactor-cleaner` | sonnet | Dead-code detection and safe removal |
| `doc-updater` | sonnet | Doc/codemap sync from source |
| `python-reviewer` | sonnet | PEP 8 / idiom / type review |
| `ascii-ui-mockup-generator` | haiku | Mechanical ASCII mockup generation |
| `odoo-build-error-resolver` | haiku | Pattern-matched install/upgrade error triage |

## Context Window Management

Avoid last 20% of context window for:
- Large-scale refactoring
- Feature implementation spanning multiple files
- Debugging complex interactions

Lower context sensitivity tasks:
- Single-file edits
- Independent utility creation
- Documentation updates
- Simple bug fixes

## Extended Thinking + Plan Mode

Extended thinking is enabled by default, reserving up to 31,999 tokens for internal reasoning.

Control extended thinking via:
- **Toggle**: Option+T (macOS) / Alt+T (Windows/Linux)
- **Config**: Set `alwaysThinkingEnabled` in `~/.claude/settings.json`
- **Budget cap**: `export MAX_THINKING_TOKENS=10000`
- **Verbose mode**: Ctrl+O to see thinking output

For complex tasks requiring deep reasoning:
1. Ensure extended thinking is enabled (on by default)
2. Enable **Plan Mode** for structured approach
3. Use multiple critique rounds for thorough analysis
4. Use split role sub-agents for diverse perspectives

## Build Troubleshooting

If build fails:
1. Use **build-error-resolver** agent
2. Analyze error messages
3. Fix incrementally
4. Verify after each fix
