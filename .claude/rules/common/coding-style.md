# Coding Style

## File Organization
- Group imports: stdlib, third-party, project-local (separated by blank lines)
- One class per file when files exceed 500 lines
- Constants at module level, before class definitions

## Error Handling
- Never use bare `except:` — always catch specific exceptions
- Never suppress errors silently (`except: pass`)
- Include context in error messages
- Log errors before re-raising when adding context

## Debug Statements
- **Never** use `print()` in production code
- Use the project's logging framework for all output
- Remove all debugging artifacts before committing

## Code Quality
- Functions should do one thing (Single Responsibility)
- Maximum function length: ~50 lines (prefer shorter)
- Maximum file length: ~500 lines (split if larger)
- Prefer early returns over deep nesting
- Use descriptive variable names — avoid single letters except loop counters
