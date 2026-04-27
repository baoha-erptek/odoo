# Behavioral Guardrails

Adapted from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md). Bias toward caution over speed; for trivial tasks, use judgment.

## 1. Think Before Coding

State assumptions, don't hide confusion, surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios (only validate at system boundaries — see [coding-style.md](coding-style.md)).
- If you write 200 lines and it could be 50, rewrite it.

Self-check: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor what isn't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

Test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

Strong success criteria enable autonomous loops. Weak criteria ("make it work") require constant clarification.

## Odoo 19 Application Notes

- **Two-Phase Testing** (see [testing.md](testing.md)) is the verification mechanism for #4 — Phase 1 (DB) and Phase 2 (ORM) tests are the success criteria.
- **Surgical changes** (#3) means: don't refactor `_inherit`ed methods beyond the override scope; don't reorganize unrelated XML view records.
- **Simplicity** (#2) means: prefer existing Odoo patterns over custom abstractions; reuse standard models (sale.order, stock.picking) before adding new ones.

## Working Indicator

These guardrails are working when diffs contain fewer unnecessary changes, fewer rewrites due to overcomplication, and clarifying questions come *before* implementation rather than *after* mistakes.
