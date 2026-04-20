# Git Workflow

## Commit Message Format
```
[module_name] type(scope): description
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks

### Rules
- Subject line under 72 characters
- Use imperative mood ("add feature" not "added feature")
- Reference JIRA ticket when applicable: `(NCNB-1234)`
- Do NOT include Claude Code signature in commits

## Branch Naming
```
feature/NCNB-1234-short-description
bugfix/NCNB-1234-short-description
refactor/short-description
```

## Pre-Push Checklist
- Run `/code-review` before pushing
- Ensure all tests pass
- Verify module installs cleanly
- Check for debug statements (print, _logger.info)
