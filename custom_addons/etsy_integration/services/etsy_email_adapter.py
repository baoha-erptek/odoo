"""EtsyEmailAdapter — converts a `ParseResult` (from email_parser) into
the canonical `EtsyOrderPayload` so email-sourced orders flow through the
same `EtsyOrderIngestor → OrderCreator.process_etsy_payload` write path
that API-sourced orders use.

This is the single canonical write path mandated by P0-22:

    Etsy email   →  email_parser.ParseResult  →  EtsyEmailAdapter
                                                       │
                                                       ▼
                                              EtsyOrderPayload
                                                       │
                                                       ▼
                                       EtsyOrderIngestor.ingest()
                                                       │
                                                       ▼
                                  OrderCreator.process_etsy_payload()
                                                       │
                                                       ▼
                                                 sale.order

Both adapters (`EtsyApiAdapter` and `EtsyEmailAdapter`) emit the same
canonical payload shape, so the ingestor / creator never has to branch
on `payload.source` to decide which fields to write. P0-22 broadens the
payload schema with 4 optional channel-agnostic fields
(`shipping_service`, `processing_time`, `discount_code`, `subtotal`)
plus `EtsyLineItemPayload.name_override` so email-only data fits.

The legacy `OrderCreator.process_parse_result()` entry point stays in
place for the email-polling cron during the cutover window (deferred to
P2-07). Once the cron rebinds onto this adapter, `process_parse_result`
can be deleted along with the rest of the email-channel code as part of
the `etsy_channel_email` module rename (T085–T087).

Reference: `specs/005-etsy-api-channel/p0-22-plan.md` §1, §3.
"""

from datetime import datetime

from .etsy_order_payload import (
    EtsyAddressPayload,
    EtsyLineItemPayload,
    EtsyOrderPayload,
)


class EtsyEmailAdapter:
    """Stateless converter from `email_parser.ParseResult` to the canonical
    `EtsyOrderPayload`. Pure Python; no Odoo ORM dependency.

    Instantiate per-call or memoise — there is no per-instance state.
    """

    def parse_result_to_payload(
        self,
        parse_result,
        email_log_id: int,
        shop_id: int,
    ) -> EtsyOrderPayload:
        """Build a canonical payload from a parsed Etsy email.

        `email_log_id` becomes the `raw_source_id` ("email_log:42") so the
        ingestor can stamp `sale.order.etsy_raw_source_id` for audit. The
        same id is used by the email-cron to mark the source row consumed.

        `shop_id` is the `etsy.shop` PK; required because the canonical
        payload is shop-scoped (the API path's syncer also threads this).
        Caller looks it up from `parse_result.shop` (the shop name string)
        before invoking the adapter — keeping the adapter pure.
        """
        return EtsyOrderPayload(
            etsy_shop_id=shop_id,
            etsy_receipt_id=parse_result.order_id,
            etsy_order_id=parse_result.order_id,
            buyer_name=getattr(parse_result.shipping_address, 'name', '') or '',
            buyer_country=getattr(
                parse_result.shipping_address, 'country_code', '',
            ) or '',
            order_date=self._parse_email_date(parse_result.date),
            currency=getattr(parse_result, 'currency', None) or 'EUR',
            amount_total=(parse_result.subtotal or 0.0)
            + (parse_result.shipping_cost or 0.0),
            shipping_total=parse_result.shipping_cost or 0.0,
            line_items=tuple(
                self._transaction_to_line_item(txn)
                for txn in parse_result.transactions
            ),
            shipping_address=self._address_to_payload(parse_result.shipping_address),
            buyer_message=parse_result.note_from_buyer or None,
            # Email parser does not surface buyer email separately from
            # the shipping_address.email field — copy it through, falling
            # back to None so partner dedup behaves consistently.
            buyer_email=(
                getattr(parse_result.shipping_address, 'email', '') or None
            ),
            listing_id=None,  # Email parser does not surface listing_id.
            payment_status='paid',  # Etsy emails are sent post-payment.
            is_gift=bool(parse_result.gift_message),
            gift_message=parse_result.gift_message or None,
            source='email',
            fetched_at=datetime.utcnow(),
            raw_source_id=f'email_log:{email_log_id}',
            last_modified=self._parse_email_date(parse_result.date),
            # P0-22 — channel-agnostic fields lifted from the email parser.
            # Empty strings normalised to None so downstream `or False`
            # writes don't churn `sale.order.write_date`.
            shipping_service=parse_result.shipping_service or None,
            processing_time=getattr(parse_result, 'processing_time', '') or None,
            discount_code=getattr(parse_result, 'discount_code', '') or None,
            subtotal=parse_result.subtotal or 0.0,
        )

    def _transaction_to_line_item(self, txn) -> EtsyLineItemPayload:
        return EtsyLineItemPayload(
            listing_id=None,
            transaction_id=str(txn.transaction_id),
            title=txn.product_name or '',
            sku=txn.sku or None,
            quantity=int(txn.quantity or 1),
            unit_price=float(txn.price or 0.0),
            variations={},  # Email parser splits options into per-attr fields,
            #              # not a generic dict; keep empty for now.
            personalisation=getattr(txn, 'personalisation', '') or None,
            # Email path's product_name is the buyer-facing line label after
            # variation/personalisation tokens have been rendered by Etsy.
            # The ingestor uses this as `sale.order.line.name` so the
            # operator dashboard shows the same string the buyer saw.
            name_override=txn.product_name or None,
        )

    def _address_to_payload(self, shipping) -> EtsyAddressPayload:
        return EtsyAddressPayload(
            name=getattr(shipping, 'name', '') or '',
            street_1=getattr(shipping, 'address1', '') or '',
            street_2=getattr(shipping, 'address2', '') or None,
            city=getattr(shipping, 'city', '') or '',
            state=getattr(shipping, 'state', '') or None,
            zip=getattr(shipping, 'zipcode', '') or '',
            country_code=getattr(shipping, 'country_code', '') or '',
        )

    @staticmethod
    def _parse_email_date(date_str: str) -> datetime:
        """Parse RFC-2822 date strings as the email_parser produces.

        Falls back to `datetime.utcnow()` when the string is unparseable —
        the email is still ingestible; only `order_date` precision is lost.

        Returned datetimes are NAIVE UTC because Odoo Datetime fields
        reject tz-aware values; `parsedate_to_datetime` produces aware
        datetimes when the source string carries an offset.
        """
        if not date_str:
            return datetime.utcnow()
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
        except Exception:  # pylint: disable=broad-except
            # Defensive: any malformed input from email_parser falls back
            # to utcnow(). Email is still ingestible; only `order_date`
            # precision is lost. Broad catch per security-reviewer P0-22 M1.
            return datetime.utcnow()
        if dt.tzinfo is not None:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
