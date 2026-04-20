---
name: skill-library
description: Searchable router for off-stack skills not loaded daily in this repo. Use when a task mentions a framework or domain outside the active stack (Odoo 19 CE + Python + PostgreSQL + Docker). Points to skills that live in the ECC plugin cache rather than this project's skills directory.
---

# Skill Library Router

This repo's daily stack is **Odoo 19 CE, Python 3.12, PostgreSQL 16, Docker Compose**. Skills that do not match that stack are kept in the ECC plugin cache at `/home/odoo/.claude/plugins/cache/everything-claude-code/everything-claude-code/1.7.0/skills/` rather than copied into `.claude/skills/`. They remain invokable through Claude's plugin skill search.

## When to consult the library

Reach for these when a task explicitly names one of the trigger keywords below. If the task is Odoo-, Python-, Postgres-, or Docker-related, the daily skill set already covers it — do not import from the library.

## Library groups

### Frontend / mobile (off-stack — Odoo uses OWL 2.0 internally)

- `frontend-patterns` — React / Next.js patterns
- `frontend-slides` — animated HTML presentations
- `foundation-models-on-device` — Apple FoundationModels
- `liquid-glass-design` — iOS 26 Liquid Glass
- `swiftui-patterns`, `swift-actor-persistence`, `swift-concurrency-6-2`, `swift-protocol-di-testing`

Triggers: react, next.js, tailwind, swiftui, ios, macos, liquid glass, slides

### Django (off-stack — this repo uses Odoo ORM, not Django)

- `django-patterns`, `django-security`, `django-tdd`, `django-verification`

Triggers: django, drf, django rest framework

### Spring Boot / JVM (off-stack)

- `springboot-patterns`, `springboot-security`, `springboot-tdd`, `springboot-verification`
- `jpa-patterns`, `java-coding-standards`

Triggers: spring, spring boot, java, jpa, hibernate

### Go (off-stack)

- `golang-patterns`, `golang-testing`

Triggers: go, golang, goroutine

### C++ (off-stack)

- `cpp-coding-standards`, `cpp-testing`

Triggers: c++, cpp, googletest, cmake

### Alternative databases

- `clickhouse-io` — PostgreSQL is the stack; ClickHouse is off-stack

Triggers: clickhouse, olap, columnar

### Generic API / backend (prefer Odoo rules when serving Odoo)

- `backend-patterns` — Node / Express flavoured
- `api-design` (ECC generic copy — project has its own at `skills/api-design/`)

Triggers: rest api design, openapi, node backend

### Testing / deployment (prefer stack-matched alternatives)

- `e2e-testing` — Playwright; this repo uses Odoo HttpCase tours
- `database-migrations` — Odoo handles schema via version bumps + hooks
- `deployment-patterns` — repo is already Docker Compose standardised

Triggers: playwright, prisma migrate, kubernetes deploy

### AI / LLM engineering

- `cost-aware-llm-pipeline` — model routing + budgets
- `regex-vs-llm-structured-text` — decision framework
- `iterative-retrieval` — subagent context refinement
- `content-hash-cache-pattern` — SHA-256 file caching

Triggers: llm pipeline, prompt caching, retrieval, embeddings

### Document processing

- `nutrient-document-processing` — Nutrient DWS API for PDF/DOCX
- `visa-doc-translate` — personal translation utility

Triggers: nutrient dws, visa translate

### Content, marketing, fundraising

- `investor-materials`, `investor-outreach`, `market-research`
- `article-writing`, `content-engine`

Triggers: pitch deck, cold email, market research, blog post, thread

### ECC meta / learning loop

- `eval-harness`, `continuous-learning`, `continuous-learning-v2`
- `skill-stocktake`, `security-scan`, `project-guidelines-example`
- `configure-ecc` — one-shot ECC installer
- `coding-standards` (generic — project uses `rules/common/coding-style.md` instead)

Triggers: eval harness, instinct, ecc install, skill audit

## How to invoke

Library skills are still discoverable via Claude's plugin skill search. When a user's request matches a trigger keyword above, invoke the skill by its bare name through the Skill tool — do not copy the skill file into `.claude/skills/` unless the stack changes and it becomes daily-relevant.

If a library skill starts getting invoked more than twice a week, promote it:

1. Copy from ECC cache into `.claude/skills/`
2. Remove its entry from this router
3. Note the promotion reason in the commit message
