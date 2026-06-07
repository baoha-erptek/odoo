# Gearment Support Email Draft (2026-05-11)

> **Pre-send checklist for the operator:**
>
> 1. Review the body below; replace `[REPRO_DETAIL]` placeholders with current data.
> 2. Confirm Defect-05 status via `gearment.api.log` (verified 2026-05-11: line_items empty was the real cause; printing_options was a symptom).
> 3. Send from a Gearment-registered email address (typically the integration-account owner).
> 4. CC: internal Gearment integration channel + project lead.
> 5. After sending, log Linear/Notion ticket with email thread reference + record in `docs/E2E_DEFECTS_2026-05-11.md` Defect-05 row.

---

## Recipients

- **To**: Gearment integration support — `support@gearment.com` (or whichever address resolves the API integration team — confirm via partner manager)
- **Cc**: Account manager / partner success contact

## Subject

> v3 Integration questions — Order draft + idempotency + sandbox availability

## Body

```
Hi Gearment integration team,

I'm integrating an Odoo-based fulfillment platform with the v3 API
(production base URL: https://apiv2.gearment.com/integration-handler).
Auth headers (X-Gearment-Client-Key / X-Gearment-Client-Secret) work; we
are reaching the API and receiving structured error responses. Three
questions below; numbered for easy reply.

== Q1. Sandbox / staging environment ==

Is there a public sandbox base URL where we can exercise POST
/api/v3/orders/draft + GET /api/v3/orders/{ref}/price + POST
/api/v3/orders/draft/labeled without invoicing real costs?

We saw `https://api.gearmentinc.com/integration-handler` referenced in
old documentation but it does not appear to accept our production
keys. If the sandbox uses different keys, can we get them issued for
account [ACCOUNT_NAME / ID]?

== Q2. Idempotency-Key behavior on retry ==

We send `Idempotency-Key: sha256(reference_id)` on POST
/api/v3/orders/draft. On the FIRST send for a given reference_id we
get 200 OK with `data.order_id` + `data.reference_id`.

On a second send with the same reference_id + the same idempotency
key (e.g., after a transient error or operator-driven retry):
  (a) Does the API return the same `order_id` (replay) or a new one?
  (b) If the order body changed in any field between send 1 and send 2,
      is that change applied or ignored?
  (c) How long is the idempotency window — minutes / hours / days?

This information is missing from developers.gearment.com/api/section
and we want to model the retry semantics correctly in our adapter.

== Q3. Validation contract documentation ==

We have hit several 400 responses where the body is structured as:

  {
    "message": "error validation failed for some fields:
                validation error:\n - data.line_items: value must
                contain at least 1 item(s) [repeated.min_items]",
    "request_id": "175dc2c8-737a-4014-a1d6-82c89bb796..."
  }

The `request_id` is helpful for cross-referencing with your logs. Two
follow-ups on the validation contract:

  (a) Is there a public schema (OpenAPI / JSON-Schema / proto file)
      we can pull so our payload builder validates client-side BEFORE
      the round-trip? The web docs cover field names but not constraint
      lists like `[repeated.min_items]` / enum values for
      `printing_options[].location_code`.

  (b) Can we file a request_id with you for a forensic look-up (e.g.,
      the one above) to confirm our payload was actually received as we
      sent it, vs. mangled by a proxy in between?

== Reproduction details (optional appendix) ==

Account: [ACCOUNT_NAME / ID]
Integration name: [INTEGRATION_NAME]
Production base URL: https://apiv2.gearment.com/integration-handler
Endpoints we exercise:
  POST /api/v3/orders/draft
  GET  /api/v3/orders/{ref}/price
  POST /api/v3/orders/draft/labeled
Auth: X-Gearment-Client-Key + X-Gearment-Client-Secret headers
Recent failing request_ids (last 24h):
  - 175dc2c8-737a-4014-a1d6-82c89bb796...   (line_items min_items violation)
  - [add 2-3 more from gearment.api.log if helpful]

Thanks for your time. Happy to jump on a 15-min call if any of these
are easier to walk through live.

Best,
[NAME]
[ROLE / COMPANY]
[CONTACT]
```

---

## Internal notes (DO NOT include in the email)

### What changed since 2026-05-10

The original Defect-05 hypothesis was that Gearment's `printing_options[].location_code` validator was rejecting our values. After fixing the audit-log durability gap (Defect-2026-05-11-02, commit `6ef702b5605`), we re-pushed S01359 (Etsy receipt 3703975562) and the FULL response body became visible in `gearment.api.log` id=148:

> `data.line_items: value must contain at least 1 item(s) [repeated.min_items]`

So the actual cause is an EMPTY `line_items` array. The payload builder filters lines by approved design-file state; the email-ingested orders have NO design files (Defect-2026-05-11-01), so all lines drop out → empty array.

This means:
- Defect-2026-05-10-05 reclassified as **SYMPTOM**, not root cause.
- The 12 printing_options variants we tried earlier were never actually reaching the validator that returned the message we saw — that message came from a *different* validation pass on a *different* prior payload.
- True fix path = ensure design files exist (operator workflow OR the new auto-create slice — Defect-2026-05-11-01 routing).

### Which questions to actually send

If this email is not yet pressing, consider:
- **Q1 (sandbox)**: ALWAYS USEFUL — push regardless.
- **Q2 (idempotency)**: NICE TO HAVE — needed eventually for retry semantics; not blocking today.
- **Q3 (schema)**: USEFUL — if we get a JSON schema we can drop the blackbox-probing pattern (per memory `feedback_capture_response_body_before_blackbox_probe`).

If Q3 is sent, attach 2–3 actual `request_id` values from staging for vendor lookup.

### Memory + tracker updates after sending

- [ ] Add a memory entry under `feedback_capture_response_body_before_blackbox_probe.md` documenting that the audit-log fix is what unblocked the RCA.
- [ ] Move tracker entry **P4-01-FIX-PRINTING-OPTIONS** from `blocked` to `resolved (re-classification)`; reference Defect-2026-05-11-01 as the actual blocker.
- [ ] Schedule **P1-DESIGN-AUTO-CREATE-FROM-EMAIL** (or equivalent) as the genuine fix path.

### When vendor replies

- Update `docs/GEARMENT_API_REFERENCE.md` Section 10 ("Open Questions") with the answers.
- Close out the question by deleting it from the open list, NOT just adding the answer below it (keeps section short for new readers).
