# Security Standards

## Access Control
- Every new model MUST have access control rules
- Define both ir.model.access.csv and record rules
- Follow principle of least privilege
- Document elevated access (sudo) with justification

## Input Validation
- Validate all external input at system boundaries
- Use parameterized queries for any raw SQL
- Never trust user-provided data in SQL, file paths, or shell commands

## Sensitive Data
- Never log passwords, tokens, or API keys
- Never commit credentials or secrets
- Use environment variables for configuration secrets

## Code Review Requirements
- All security-sensitive changes require explicit review
- sudo() usage must include inline comment explaining why
- Raw SQL must include justification comment
