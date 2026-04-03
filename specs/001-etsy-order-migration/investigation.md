# Investigation: Etsy Email Collection -> Odoo 19 CE Migration

**Date**: 2026-04-02
**Status**: Complete
**Analyst Team**: BA Agent, Technical Architect Agent, Devil's Advocate Agent

## Executive Summary

This investigation analyzes the feasibility and approach for migrating an existing Etsy order collection system (Python script + Google Sheets, 17,659 orders) to Odoo 19 CE. Three perspectives were explored: business analysis, technical architecture, and critical risk assessment.

**Recommendation**: Proceed with the migration using an incremental approach. The business case is strong (proper CRM, workflows, reporting), but the team must be realistic about:
1. The email parser remains the weakest link regardless of backend
2. Odoo 19 CE is sufficient for all identified requirements
3. Phase 1 (MVP) should be achievable in 2-3 weeks of focused development
4. The Etsy API should be evaluated as a Phase 3 strategic improvement

## 1. Current System Assessment

### What Works Well
- Simple, working system (600 lines of Python)
- 17,659 orders successfully collected
- Multi-shop support (Viktor, Julien, Carina)
- Multi-language field label handling (EN, DE)
- Deduplication by ORDER_ID
- Automatic Gmail label removal after processing

### What Needs Improvement
- **No error handling**: Silent failures, no monitoring
- **Security issues**: Credentials committed to git (credentials.json, token.pickle, service_account.json)
- **No tests**: Zero automated tests
- **Fragile parsing**: Regex tied to Etsy's email HTML structure
- **Limited querying**: Google Sheets has no real search/filter/reporting
- **No customer management**: Flat data, no CRM
- **No product catalog**: Product names repeated per order line
- **No audit trail**: If an email fails to parse, it's silently dropped
- **Single point of failure**: One script, one VPS, no redundancy

### Data Characteristics

| Metric | Value |
|--------|-------|
| Total orders | 17,659 |
| Columns per order | 34 |
| Active shops | 3+ (Viktor, Julien, Carina) |
| Currency | EUR |
| Price range | ~EUR 15-25 typical |
| Product types | Handcrafted goods (ring dishes, tattoos, etc.) |
| Order frequency | ~50-100/day (estimated) |
| Personalization rate | ~40% of orders have customization text |

## 2. Business Case for Odoo 19 CE

### Value Proposition

| Capability | Google Sheets | Odoo 19 CE |
|------------|--------------|------------|
| Order storage | Flat table | Structured, relational |
| Customer management | None | Full CRM (res.partner) |
| Product catalog | None | Products with images, categories |
| Search/Filter | Basic | Advanced filters, saved searches |
| Reporting | Manual charts | Pivot, graph, dashboard views |
| Workflow | None | Quotation -> Confirmed -> Done |
| Multi-user | Shared sheet | RBAC, audit trail |
| Data integrity | Append-only | Constraints, validation |
| Extensibility | Google Apps Script | Odoo module ecosystem |
| Offline access | No | Yes (local Docker) |

### ROI Estimate

| Cost | Estimate |
|------|----------|
| Development effort (Phase 1 MVP) | 2-3 weeks |
| Development effort (Phase 2 Catalog+CRM) | 1-2 weeks |
| Development effort (Phase 3 Analytics) | 1 week |
| Ongoing maintenance | 2-4 hours/month |
| **Total initial investment** | **4-6 weeks** |

| Benefit | Impact |
|---------|--------|
| Eliminate manual Google Sheets management | ~5 hours/week saved |
| Customer lookup speed | From minutes to seconds |
| Order search and filtering | From impossible to instant |
| Business reporting | From manual to automatic |
| Error detection | From "eventually noticed" to immediate |

## 3. Technical Architecture Summary

### Module Design: `etsy_integration`

**Models** (7):
1. `etsy.shop` — Etsy storefront entity
2. `etsy.email.log` — Email processing audit trail
3. `sale.order` (inherited) — Extended with 9 Etsy fields
4. `sale.order.line` (inherited) — Extended with 11 Etsy fields
5. `product.product` (inherited) — Extended with 2 Etsy fields
6. `res.partner` (inherited) — Extended with 2 Etsy fields
7. `res.config.settings` (inherited) — Gmail configuration

**Services** (3 isolated layers):
1. `email_parser.py` — Pure Python regex parser (no ORM)
2. `gmail_client.py` — Gmail API OAuth2 wrapper
3. `order_creator.py` — Odoo ORM order creation with deduplication

**Key Design Decision**: Parser is ORM-free and independently testable. Can be replaced with Etsy API parser in Phase 3 without touching Odoo models.

### Migration Path

```
Phase 1 (MVP): Email -> Parse -> sale.order (replace Sheets)
Phase 2 (CRM): Product catalog + Customer management
Phase 3 (API): Etsy REST API (replace email parsing)
```

## 4. Risk Assessment

### High Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Etsy email template changes break parser | HIGH | HIGH | Store raw emails for recovery; alert on failures; keep regex maintainable |
| Gmail OAuth2 token management complexity | MEDIUM | HIGH | Auto-refresh in gmail_client; admin alert on auth failure; document manual refresh steps |
| Scope creep ("add inventory, purchasing...") | HIGH | MEDIUM | Strict phasing; Phase 1 is ONLY email-to-order; resist scope expansion until MVP works |

### Medium Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Odoo upgrade pain (19 -> future) | MEDIUM | MEDIUM | Keep custom module minimal; follow Odoo conventions; no monkey-patching |
| Historical import data quality issues | MEDIUM | LOW | Dry-run import; validate counts; spot-check samples |
| Performance with 17K+ orders | LOW | MEDIUM | Batch processing; proper indexes; test with full dataset |

### Devil's Advocate Considerations

1. **"Is Odoo overkill?"** — For pure order storage, yes. But the business needs CRM, products, reporting, and multi-user access. A custom webapp would need to rebuild all of these.
2. **"Keep Google Sheets?"** — Viable short-term but doesn't scale. No customer management, no product catalog, limited reporting, shared access issues.
3. **"Use Etsy API instead of emails?"** — Better long-term but requires Etsy app registration and different OAuth flow. Email parsing is proven and working. API is a Phase 3 improvement.
4. **"Lighter alternative (FastAPI + PostgreSQL)?"** — Would need to build views, RBAC, search, reporting from scratch. Odoo provides all of this out of the box.

## 5. Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Use Odoo 19 CE (not custom webapp) | Built-in CRM, sale orders, products, RBAC, views, reporting |
| D2 | Keep Gmail API (not IMAP fetchmail) | Need label management; existing OAuth2 flow works |
| D3 | Email parser is ORM-free service | Testability; replaceable with Etsy API later |
| D4 | Phase 1 is email-to-order only | Minimize scope; deliver value fast; iterate |
| D5 | Store raw emails for failed parses | Safety net for Etsy template changes |
| D6 | Use Odoo's ir.config_parameter for credentials | Standard approach; admin UI; no files in git |
| D7 | EUR prices stored as-is | Single currency simplifies Phase 1; multi-currency available if needed |
| D8 | Products matched by exact name | Simple, sufficient for handcrafted goods with unique names |
| D9 | Partners matched by email then name+zip | Balances deduplication accuracy vs. false merge risk |
| D10 | Module name: `etsy_integration` | Clear, descriptive, follows Odoo naming conventions |

## 6. Resolved Questions (2026-04-03)

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| Q1 | Should orders be auto-confirmed or stay as draft? | **Stay in draft** | Order creator sets state='draft'. Manual confirmation workflow by operators. |
| Q2 | Need Odoo inventory (stock) module? | **Yes** | Add `stock` to module dependencies. Enables inventory tracking per product. Phase 2 scope. |
| Q3 | How many users? | **>10 users** | Full RBAC required. Multiple security groups (shop operator, design team, admin). Justifies Odoo over simpler tools. |
| Q4 | Download/store Etsy images in Odoo? | **Yes** | Add image download service. Store in ir.attachment / product image field. Fetch from etsy_image_url on product creation. |
| Q5 | Vietnamese translations? | **No** | Skip i18n directory. English-only interface. |
| Q6 | What happens to Google Sheets? | **Retire** | Full cutover to Odoo. No dual-write. Sheets archived as static backup. |
| Q7 | More shops beyond Viktor, Julien, Carina? | **Yes** | Dynamic shop auto-creation from email parsing is critical. No hardcoded shop list. |
| Q8 | Etsy API v3 evaluation? | **Keep for future** | Validates Phase 3 plan. Email parsing for now; Etsy API as strategic improvement later. |

### Implications of Resolved Questions

**Business case strengthened**: With >10 users, inventory module, and full Sheets retirement, the Devil's Advocate's concern about "overkill" is addressed. The team will use **4 core Odoo modules** (sale + stock + contacts + mail), exceeding the recommended minimum of 3.

**New scope items**:
- Image download service (fetch from etsystatic.com, store in Odoo filestore)
- `stock` module dependency and basic inventory setup
- Proper multi-group RBAC (not just 2 groups)
- No i18n effort saved

## 7. Spec-Kit Document Index

| Document | Purpose | Status |
|----------|---------|--------|
| [constitution.md](../../.specify/memory/constitution.md) | Project principles and governance | Complete |
| [spec.md](./spec.md) | Feature specification with 10 user stories | Complete |
| [research.md](./research.md) | Technical research and investigation findings | Complete |
| [plan.md](./plan.md) | Implementation plan with phased approach | Complete |
| [data-model.md](./data-model.md) | Detailed Odoo data model design | Complete |
| [tasks.md](./tasks.md) | 57 actionable tasks in 10 phases | Complete |
| [contracts/email-parser-contract.md](./contracts/email-parser-contract.md) | Email parser service interface | Complete |
| [contracts/gmail-client-contract.md](./contracts/gmail-client-contract.md) | Gmail API client interface | Complete |
| [contracts/order-creator-contract.md](./contracts/order-creator-contract.md) | Order creation service interface | Complete |
| [investigation.md](./investigation.md) | This file — consolidated investigation | Complete |

## 8. Next Steps

1. ~~Review this investigation with the team~~ Done (2026-04-03)
2. ~~Answer open questions (Section 6)~~ All resolved (2026-04-03)
3. Begin Phase 1 implementation (Setup + Foundation + MVP)
   - Scaffold `etsy_integration` module with `sale`, `stock`, `contacts`, `mail` dependencies
   - Set up Docker Compose for Odoo 19 CE development environment
   - Port email parser to `services/email_parser.py` (ORM-free)
4. Set up Docker environment at `other_projects/odoo19_esty/`
5. Historical data import wizard for 17,659 orders from Excel
6. Image download service for Etsy product photos
