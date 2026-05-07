# Quickstart — Spec 007 Customer Conversations

Operator-side checklist for enabling pre-sale + post-sale conversation routing on a shop.

---

## Prerequisites

- `multichannel_hub_core` ≥ 19.0.1.0.20 (after `P3-LEAD-MODEL` lands).
- `etsy_integration` ≥ 19.0.2.4.0 (after `P1-MSG-API-PULL` lands).
- E1v2 Etsy app review **approved** with `conversations_r` scope (for User Story 1 API path). Email fallback works without this.
- A working SMTP / Gmail send config on Odoo (for mail.alias delivery confirmations).

---

## A. Post-sale conversation thread (User Story 1)

### A.1 — Email-only path (works today)

1. **No setup required.** When the existing Gmail-polling cron catches an Etsy "buyer messaged you" notification email and the order exists in Odoo, the message is auto-posted to the order chatter.
2. Verify on a live shop: send a test message from a buyer test account against an existing test order; within 10 minutes (Gmail poll interval), open the order in Odoo → chatter shows the message with the buyer as author.

### A.2 — API path (after E1v2)

1. Owner re-submits Etsy app review with `conversations_r` scope (see `guides/vi/etsy-app-review-guide.md` §re-submission).
2. After Etsy approves, each shop's OAuth token must be re-issued: open `etsy.shop` form → Settings → "Re-authorize" button → walk through OAuth.
3. Verify `etsy.shop.granted_scopes` (Char field, post-P1-MSG-SCOPE) contains `conversations_r`.
4. Within 10 min the conversation cron picks up new messages via API; existing email-fallback continues but dedupe prevents double-posting.

### A.3 — Operator workflow

- Open `sale.order` form → chatter tab shows the conversation thread.
- Reply via the chatter input — for v1, this is **internal-only** (the reply does NOT go back to the buyer; see User Story 3 for the deferred outbound path).
- For an actual buyer reply, log into the Etsy seller dashboard (link surfaced on the order form via existing `etsy_order_url`).

---

## B. Pre-sale enquiry routing (User Story 2)

### B.1 — Provision the email alias

1. On `etsy.shop` form → Conversations tab → "Provision Enquiry Alias" button. This creates `mail.alias` `enquiries_<shop_slug>@<your.domain>` pointing at `multichannel.enquiry`.
2. Add the new alias as a forwarding rule from the shop's primary inbox or from a custom domain MX record.
3. Test: send an email to the alias from any external account → within 1 minute a new `multichannel.enquiry` record appears in *Multichannel → Enquiries*, state=`new`, with the email body in chatter.

### B.2 — Etsy API path (after E1v2 + scope)

After `conversations_r` is granted, conversations not bound to a receipt automatically create `multichannel.enquiry` rows on the next 10-min cron. No additional config.

### B.3 — Operator workflow

1. Open *Multichannel → Enquiries*; filter `state=new`.
2. Open an enquiry → review chatter → click **Qualify** to mark it actively-pursued, OR **Close** with a reason.
3. Click **Convert to Quote** to spawn a draft `sale.order` for the buyer's partner record. The enquiry flips to `state=converted` with a back-link.
4. Continue the standard quote/order workflow.

---

## C. Verify the dedupe + buffer paths

### C.1 — Cross-channel dedupe smoke test

1. Send the same buyer message via API path AND via test email simultaneously.
2. Open the order chatter — exactly one entry exists.
3. Check `etsy.message.dedupe` table — exactly one row with `channel` set to whichever path arrived first (typically API).

### C.2 — Buffer replay (message before order)

1. (Test fixture only) Insert a `etsy.message.dedupe` row with `state='buffered'`, `pending_target_receipt_id='999999'`.
2. Trigger the order-sync cron with a synthetic receipt 999999 → after the next 30-min buffer-sweep cron, the row flips to `state='posted'` and the order chatter has the message.

---

## D. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No buyer messages on existing orders | Gmail cron not running OR `email_parser` template unmatched | Check `etsy.sync.health` tile; check `etsy.email.log` for `parse_status='failed'` rows |
| Duplicate chatter entries | Dedupe key collision (synthetic email-side ID vs real API ID) | Check `etsy.message.dedupe` for two rows with identical `body_sha256_prefix`; manual reconcile + log to `findings.md` |
| Enquiry not created from email | `mail.alias` not resolving | Check `mail.alias` config; verify MX/forwarding chain delivers to Odoo |
| API path returns 403 | `conversations_r` not granted | Re-authorize shop OAuth (see A.2 step 2) |
| Buffered message orphaned | Order never ingested (e.g. shop not on `api_only`, email path also failing) | Investigate upstream order-sync; manually create the order or close the dedupe row with state=`orphaned` |

---

## E. Rollback

If the conversation-poller misbehaves on a single shop, set `etsy.shop.conversation_polling_enabled=False` (ICP killswitch added with P1-MSG-API-PULL). Email fallback continues independently. To disable email path too, disable the `mail.alias` for that shop.

To uninstall the entire feature: `odoo -d <db> --uninstall multichannel_hub_core` is **not** safe (other modules depend); instead, archive all `multichannel.enquiry` records and remove the `mail.alias` rows. The feature degrades gracefully — no data loss, just no new enquiries created.
