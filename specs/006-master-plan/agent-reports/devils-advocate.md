# Devil's Advocate Risk Report — Multichannel E-Commerce Hub (Odoo 19 CE)

**Scope**: Specs 002-005, ~194+ tasks, small team, ~3-6 month "plan"
**Verdict**: This roadmap is optimistic by **2-3x on effort** and **has at least 4 load-bearing assumptions that are already wrong**. Ship 002 first, freeze 003-005 until the assumptions are validated.

---

## 1. Load-bearing assumptions that are probably wrong

Ranked by blast radius:

### 1.1 "Etsy will grant us the scopes we need" — ALREADY PARTIALLY FALSE
Etsy already denied the **Conversations (messaging) scope**. Spec 005 is betting on `transactions_r`, `listings_r`, `shops_r`, `email_r` being approved. Etsy app review is notoriously opaque — **3-8 weeks**, and they reject apps that can't demonstrate "significant seller benefit". If `transactions_w` (tracking push-back) is denied, Spec 005 loses half its value. **Spec 004's "push tracking back to Etsy" workflow collapses if `transactions_w` isn't granted.** No fallback plan documented.

### 1.2 "17,659 orders will migrate cleanly in < 30 minutes" — FALSE ON DATA ALONE
- **423 orders with $0 price** (2.4%) — source-data corruption, needs manual triage
- **Stuck-in-draft majority** — state transitions trigger computed fields, stock moves, accounting
- Fiscal position + payment term + sales team + categorization + dedup + record rules all in one pass on 17K rows -> **OOM risk**
- Previous import used unsafe `cr.commit()`; new wizard presumably doesn't, meaning **one bad row can abort a batch**

Realistic target: **3-8 hours, run overnight, with resume capability.** The < 30 min claim will not survive contact with production.

### 1.3 "Dual-mode sync (email + API) is safe" — race conditions unmanaged
- Email arrives 12s before API sync. Two orders created. Dedupe key is receipt_id, BUT email parser's receipt_id extraction is one of the 43 regexes that **already failed 423 times**.
- API webhook fires during email poll. Both write. Last-write-wins. Fulfillment state stomped.
- Tracking arrives via GKE, then API rewrites from stale Etsy cache. Flip-flops.

**No documented reconciliation logic.** Silent data corruption.

### 1.4 "Gearment v3 is production-ready and documented" — UNVERIFIED
Has anyone:
- Gotten sandbox credentials and hit the endpoint?
- Verified rate limit scope (per-key vs per-IP)?
- Verified HMAC format (sha256=hex vs base64, header name, signed fields)?
- Confirmed webhook retries (count, backoff, ordering)?
- Confirmed draft->quote->confirm idempotency on retries?

If any are "find out when we code," **add 3 weeks to Spec 004.**

### 1.5 "Product categorization by JSON keywords works for 17K heterogeneous products"
Etsy products are **handmade and long-tail**. Keyword list produces ~60-70% accuracy ceiling, degrading monthly. BA team ends up doing manual recategorization **forever**. No plan for the tail.

### 1.6 "Customer dedup is fine without email"
Email coverage 0%. Spec 002 is "future-only" dedup. Historical 17K become 17K unique partners, many are the **same repeat customer** under slightly different display names. When Spec 005 brings real emails, you get a second set of canonical partners — **repeat-customer analytics broken on both sides**.

### 1.7 "Design files fit in ir.attachment"
No size cap. Print-on-demand design files typically **30-300 MB each**. 50 MB × 17K orders × 2 files = **1.7 TB in `ir_attachment`**. That's `pg_dump` + backup windows + replication lag. Must be filestore + Google Drive URLs only. Nobody sized this.

### 1.8 "194+ tasks in 3-6 months with 1-3 devs" — math doesn't work
See Section 6. **Realistic: 9-15 months.**

---

## 2. Silent failure modes

| Failure | Symptom | Time to detection |
|---|---|---|
| **Etsy OAuth refresh fails day 91** | Sync stops. No errors visible unless you check cron logs. | 24-72h |
| **Webhook signature mismatch** | Events silently dropped (or worse, logged-and-accepted -> spoofing) | Never, until audit |
| **Rate limit backoff stalls sync** | Cron runs 9h, hits 429 at order #300, killed at timeout. Orders 300-500 never sync. | Days |
| **Cron succeeds but does nothing** | `last_sync_date` updated even on empty fetch. | 1-3 days |
| **Email parser regex rots mid-migration** | Etsy A/B tests template. 3/43 regexes break. $0 orders look "normal". | Weeks |
| **GKE Excel rows skipped** | DEBUG-level log. Tracking for 12 orders never lands. | When customers email |
| **Customer dedup false merge** | Two unrelated "Nguyen Van A" merged. Order history leaks. **GDPR violation.** | Never, unless complaint |
| **Partial design file upload** | Upload half-fails, checksum unchecked. Corrupt design sent to Gearment. $50/occurrence. | When Gearment rejects |
| **Webhook arrives before API sync** | Minimal-data order created. API write overwrites good data with bad. | Never |
| **Idempotency key collision** | Order resubmitted after cancel. Gearment rejects as duplicate. Team thinks fulfillment succeeded. | Days-weeks |
| **GDrive token expires mid-sync** | Silent 401. Cron marked green. | When weekly backup fails |

**Required minimum**: health-check dashboard (`last_successful_sync_at`, `rows_processed_last_run`, `backoff_state`, `rate_limit_headroom`) per integration. **None of this is in any spec.**

---

## 3. Scope risks — what the plan under-sells

**3.1 Spec 001 is not "shipped"** — 17K stuck in draft, $0 on 2.4% is a failing production system. Real completion is ~40%.

**3.2 Spec 002 US10 vs Spec 003 overlap** — design queue status field collision. Whichever ships second gets a field-rename migration not in any task list.

**3.3 Spec 004 is a project, not a spec.** 79 tasks, 7 models, 5 services, 3 external integrations, returns/refunds, HMAC webhooks. Should be **3 specs**: (a) Gearment adapter, (b) GKE tracking import + carrier detection, (c) Returns/refunds.

**3.4 Spec 005 tasks.md doesn't exist.** "35 FRs" with no breakdown = guess. OAuth PKCE + webhooks + rate limiter + dual-mode + token rotation = **50-90 tasks**.

**3.5 BA user-wants not in any spec — all 10.** Combined Process Dashboard treated as rename but is actually a cross-warehouse aggregation. Raw-material forecasting is a **2-month project** not even scheduled. Ticket system implies helpdesk (NOT IN CE).

**3.6 Completely missing**: Customer service tools, BI/reporting layer, multi-warehouse stock (US+VN), returns accounting, reverse tracking, customs/duties, refund accounting, **Amazon integration** (mentioned in BA tag #9), staging environment, monitoring, disaster recovery for 1.7 TB of design files.

---

## 4. Integration hell — specific failure modes

**4.1 Etsy tracking push rejects carrier name.** Etsy accepts `usps`, `ups`, `fedex`, `dhl`, `other`. GKE supplies `UniUni`, `YunExpress`, `GKE`. Spec 004's auto-detection maps to **`other` on 90% of orders**, which disables Etsy's buyer-facing tracking page. Buyers complain.

**4.2 Gearment draft->quote->confirm intermediate failure.** Draft created, confirm fails. Recovery? Quote TTL probably 24h. If recovery cron runs next day, quote is stale, price mismatch. Does adapter re-quote? Does BA approve price change? Are orphan drafts billed as storage? No workflow documented.

**4.3 GKE Excel schema change.** Column added in position 5 -> **silent data scramble** if positional indices used. Column renamed "Tracking Number" -> "Tracking No." -> silent fail. Needs schema fingerprinting + hard-fail.

**4.4 Google Drive auth expires mid-sync.** User OAuth expires after 6 months of inactivity. Breaks every 6 months. Spec 004 doesn't specify auth mode.

**4.5 Webhook before API sync for new order.** Duplicate order unless dedupe uses a locking column or "pending_completion" state.

**4.6 Conflicting email vs API data.** Email says $42.50, API says $41.97 (Etsy fee recalc). Which wins? If email already invoiced, does API re-invoice delta? **No policy documented.**

**4.7 Etsy rate limit during 500+ bulk sync.** 500 orders × 3 calls = 1500 calls per sync. QPD limit (5000-10000/day) means **2-3 full syncs/day max** before throttled until midnight UTC. Hourly cron burns QPD in 4 hours.

---

## 5. Vietnamese / i18n reality check

- **Vietnamese diacritics** in addresses/personalizations — Excel round-trip in Windows Excel with Vietnamese locale can corrupt to CP1258. Encoding sanity check needed on every import.
- **Date format**: GKE Excel "DD/MM/YYYY" as text. Without `dayfirst=True`, **every date where day<=12 silently flips month+day**.
- **Per-shop currency with customer override**: EUR customer on USD shop. Exchange rate source? Conversion date? Needs snapshotting rate on order, not live lookup.
- **Printable labels / customs forms**: Odoo CE wkhtmltopdf has Vietnamese diacritic issues unless Unicode-capable font configured.
- **i18n .po pipeline**: Is there a CI job running `odoo-bin translate`? Big-bang localization at the end always slips.

---

## 6. Team and delivery risks

### The math (1-3 devs, 194+ tasks)

**Optimistic**: 1 task/day. 194 / (2 devs × 20 days/mo) = **4.9 months pure coding**, zero slack.

**Realistic**: 2-3 days/task including planning+TDD+review+rework, + Spec 005's unwritten 50-90 tasks -> ~250 tasks. 250 × 2.5 days / (2 devs × 18 effective days) = **17.4 months**.

**Plus Spec 005 complexity tax**: +1.5 months.

**Plan for 12-18 months, not 3-6.**

### Spec 004 Gearment adapter sub-estimate
- Auth + HMAC: 3 days
- Draft/quote/confirm state machine + idempotency: 5 days
- Rate limiter + backoff: 2 days
- Webhook handler + retry: 4 days
- Error recovery (stuck drafts, failed quotes, cancellation): 4 days
- Sandbox integration tests: 4 days
- Production hardening: 3 days

**25 days = 5 weeks for ONE adapter.** Spec has 79 tasks covering this PLUS GKE PLUS returns PLUS GDrive. Impossible.

### No staging/production split
Where does Gearment sandbox auth live? Where does Etsy OAuth redirect locally? Is there a `test_mode` boolean short-circuiting outbound calls? Not documented. **First production test ships a real $30 order to Gearment.**

### No monitoring
Spec 003 has operations dashboard, not **system health**. Need: cron last-run timestamps, API error counts by endpoint, queue depth, rate-limit headroom. Without this, every outage is "BA noticed orders stopped three days ago."

---

## 7. Hidden Odoo CE assumptions

- **`helpdesk` — Enterprise only.** Ticket system (BA #5) cannot use it. Options: (a) roll own on `mail.thread`, (b) OCA `helpdesk_mgmt` (quality varies), (c) pay Enterprise.
- **`documents` module — Enterprise only.** Design file management workflow -> same problem.
- **`approvals` module — CE has it but basic.** Ugly for address-change use case.
- **`mrp` forecasting**: CE has basic mrp. 1/3/12-month horizons need `stock_forecast` or custom. Request #2 underestimated by **5-10x**.
- **`stock_barcode`**: CE has it. Request #4 feasible.
- **`documents_google_drive` — Enterprise only.** Spec 004 US9 needs custom.

---

## 8. Top 10 "fix before coding or regret it later"

| # | Risk | Consequence | Minimum mitigation | Triggering spec |
|---|---|---|---|---|
| **1** | Etsy scope approval unknown | Spec 005 blocked 4-8 weeks; possible rescope | **Submit Etsy app NOW**, parallel to Spec 002 coding. Document fallback per scope. | 005 |
| **2** | 17K drafts + 423 $0 are blockers | Every Spec 002-005 build on broken data | Freeze 500-order known-good sample. Fix/archive 423 manually. Then run 002. | 002 |
| **3** | Spec 002's <30 min is fiction | OOM or rollback, mixed-state data | Redesign wizard as **batch-resumable** (savepoints per 500 + `last_processed_id` checkpoint). Drop 30-min SLA. | 002 |
| **4** | Gearment v3 unverified | Spec 004 stalls at first API call | **3-day spike** hitting sandbox end-to-end. Document rate limits, HMAC, retry. Before any 004 task starts. | 004 |
| **5** | Dual-mode race conditions | Silent data corruption | Add `etsy_sync_version` + `etsy_sync_lock_until`. Document conflict-resolution policy. | 005 |
| **6** | No monitoring | First outage found 2-3 days late | Build minimal `etsy.sync.health` model in Spec 002 (last_run, row_count, error_count per channel). Single dashboard tile. | 002 |
| **7** | Spec 004 is 3 specs pretending to be 1 | Never ships | Split into 004a (Gearment), 004b (GKE+carrier), 004c (Returns). Ship in order. | 004 |
| **8** | `helpdesk` is Enterprise only | Ticket system cannot be built as designed | **Decide now**: custom, OCA, or Enterprise. | 003/004 |
| **9** | Customer dedup for 17K historical | Repeat-customer reports broken; GDPR | Dedup wizard produces CSV of proposed merges for BA approval. Never auto-merge. | 002 |
| **10** | Design file storage sizing | Postgres -> 1.7 TB | Design files to filestore/S3/GDrive by URL only. Hard-fail if >10 MB to `ir_attachment`. | 003/004 |

---

## Closing

**This plan will slip by 6-12 months if nothing changes.** The quickest wins:

1. **Stop spec-writing.** 5 specs and 0 lines of new code. Ship 002 end-to-end in production before touching 003.
2. **Validate external dependencies.** Etsy review, Gearment sandbox, GKE fingerprinting are **1-week spikes that save months**.
3. **Cut Spec 004 in three.** 79 tasks in one spec is a project.
4. **Build minimal observability during Spec 002.** Not after.
5. **Resolve `helpdesk`/`documents` CE-vs-Enterprise this week.**

The team is one Etsy scope rejection and one broken GKE column away from a **3-month emergency re-architecture**. Plan for it or prevent it.
