# Development Workflow

## Standard Flow
1. **Plan** — Understand requirements, assess risks, design approach
2. **Implement** — Write code following project patterns
3. **Test** — Verify with automated tests (TDD preferred)
4. **Review** — Run code review before committing
5. **Commit** — Clean commit with descriptive message

## Before Writing Code
- Read existing code in the target area
- Understand current patterns and conventions
- Check for related existing functionality (avoid duplication)
- Identify test requirements

## After Writing Code
- Run module update to verify installation
- Run relevant tests
- Check for debug statements
- Verify security (ACLs, record rules)
- Review i18n compliance

## When Blocked
- Investigate root cause before trying workarounds
- Check logs for error details
- Search codebase for similar patterns
- Ask for clarification rather than guessing

## Architecture Decision Records (ADRs)
When a slice diverges from the obvious/standard approach — a non-default inheritance
choice, a new model where a standard one nearly fit, an integration topology decision —
record a short ADR alongside the spec (`specs/<NNN>-<slug>/adrs/ADR-NNN-<slug>.md`).
Capture: context, the decision, alternatives considered, and consequences. The ADR
explains the *why* that the code and git history cannot. Reference the ADR id in the
slice's tracker notes. (Both openeducat and esty projects run this discipline.)
