"""P4-01-FIX-LOG-LINKAGE — RED tests for failure-path api.log enrichment.

Spawned by Defect-2026-05-10-03. Today's E2E run produced
`gearment.api.log` rows with `http_status=0`, `sale_order_id=None`, and
`direction=False/null` — operators cannot triage which order failed which
API call. The fields already exist on the model; the bug is in the writers
(adapter `_log_call` failure path + missing `sale_order_id` plumbing from
caller).

Memory: feedback_capture_response_body_before_blackbox_probe (2026-05-10) —
"on 4xx from a vendor API, FIRST step is `r = requests.post(...); print(r.text[:2000])`
before any schema-guessing"; this slice is the production-grade form of that
rule (capture in api.log, not just stdout).
"""

import json
from unittest import mock

import requests

from odoo.tests.common import TransactionCase, tagged


def _http_error(status_code: int, body_text: str) -> requests.exceptions.HTTPError:
    """Build a real-shaped requests.exceptions.HTTPError carrying a Response."""
    response = requests.Response()
    response.status_code = status_code
    response._content = body_text.encode('utf-8')
    err = requests.exceptions.HTTPError(
        f"{status_code} Client Error: Bad Request for url: example",
        response=response,
    )
    return err


@tagged('post_install', '-at_install', 'p4_01_fix_log_linkage')
class TestApiLogFailurePathEnrichment(TransactionCase):
    """When push_order's HTTP request fails, the resulting api.log row
    must carry the order linkage, real status code, response body, and
    direction='outbound'."""

    def setUp(self):
        super().setUp()
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentAddress, GearmentLineItem, GearmentOrderPayload,
        )
        self._GearmentApiAdapter = GearmentApiAdapter
        self._payload = GearmentOrderPayload(
            reference_id='SO-LOG-LINK-01', store_id='demo',
            addresses=(GearmentAddress(
                first_name='A', last_name='B', street_1='1 Main',
                street_2=None, city='X', state='MA', zip_code='02108',
                country_code='US',
            ),),
            line_items=(GearmentLineItem(
                legacy_id=1, quantity=1, sku='T1',
                printing_options=({'location_code': 'front', 'url': 'https://x/y.png'},),
            ),),
        )
        self._partner = self.env['res.partner'].create({'name': 'BuyerLogLink'})
        self._product = self.env['product.product'].create({
            'name': 'P', 'type': 'consu', 'list_price': 5.0,
        })
        self._order = self.env['sale.order'].create({
            'partner_id': self._partner.id,
            'order_line': [(0, 0, {'product_id': self._product.id, 'product_uom_qty': 1})],
        })
        # Flush the order to the DB so the FK-referenced record exists for the
        # fresh cursor's audit-log write (P4-01-FIX-LOG-LINKAGE-EXCEPTION-PATH).
        self.env.flush_all()
        # Patch the adapter's HTTP client to raise a 400.
        self._error = _http_error(
            400,
            '{"message":"validation error","status":"error"}',
        )

    def _push_with_failure(self, *, sale_order_id=None):
        """Invoke push_order through the adapter with the HTTP layer raising 400."""
        mock_client = mock.MagicMock()
        mock_client._request = mock.MagicMock(side_effect=self._error)
        adapter = self._GearmentApiAdapter(env=self.env, client=mock_client)
        try:
            adapter.push_order(self._payload, sale_order_id=sale_order_id)
        except Exception:
            # push_order re-raises; we expect that.
            pass
        # Find the freshly-created api.log row for this push.
        return self.env['gearment.api.log'].search(
            [('endpoint', '=like', 'POST %/orders/draft%')],
            order='id desc', limit=1,
        )

    def test_failure_path_records_real_http_status(self):
        log = self._push_with_failure(sale_order_id=self._order.id)
        self.assertTrue(log, "expected an api.log row created on failure")
        self.assertEqual(
            log.http_status, 400,
            "http_status must come from exc.response.status_code, not stay 0/None",
        )

    def test_failure_path_records_sale_order_id(self):
        log = self._push_with_failure(sale_order_id=self._order.id)
        self.assertTrue(log)
        self.assertEqual(
            log.sale_order_id.id, self._order.id,
            "sale_order_id must be set when caller provides it",
        )

    def test_failure_path_records_direction_outbound(self):
        log = self._push_with_failure(sale_order_id=self._order.id)
        self.assertTrue(log)
        self.assertEqual(
            log.direction, 'outbound',
            "outbound API calls must record direction='outbound'",
        )

    def test_failure_path_records_response_body_in_response_summary(self):
        log = self._push_with_failure(sale_order_id=self._order.id)
        self.assertTrue(log)
        self.assertIsNotNone(log.response_summary,
            "response body must be captured for blackbox-API debugging")
        self.assertIn(
            'validation error', log.response_summary,
            "response body text from exc.response.text must land in response_summary",
        )

    def test_failure_path_no_regression_on_error_message(self):
        log = self._push_with_failure(sale_order_id=self._order.id)
        self.assertTrue(log)
        self.assertTrue(
            log.error_message,
            "error_message stays populated for compatibility with existing UI",
        )


@tagged('post_install', '-at_install', 'p4_01_fix_log_linkage')
class TestApiLogSuccessPathDirection(TransactionCase):
    """Outbound success path must also record direction='outbound' (not False)."""

    def setUp(self):
        super().setUp()
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentAddress, GearmentLineItem, GearmentOrderPayload,
        )
        self._GearmentApiAdapter = GearmentApiAdapter
        self._payload = GearmentOrderPayload(
            reference_id='SO-LOG-LINK-OK', store_id='demo',
            addresses=(GearmentAddress(
                first_name='A', last_name='B', street_1='1 Main',
                street_2=None, city='X', state='MA', zip_code='02108',
                country_code='US',
            ),),
            line_items=(GearmentLineItem(
                legacy_id=1, quantity=1, sku='T1',
                printing_options=({'location_code': 'front', 'url': 'https://x/y.png'},),
            ),),
        )

    def test_success_path_records_direction_outbound(self):
        partner = self.env['res.partner'].create({'name': 'BuyerLogLinkOK'})
        product = self.env['product.product'].create({
            'name': 'POk', 'type': 'consu', 'list_price': 5.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })
        # Flush the order to the DB so the FK-referenced record exists for the
        # fresh cursor's audit-log write (P4-01-FIX-LOG-LINKAGE-EXCEPTION-PATH).
        self.env.flush_all()
        mock_client = mock.MagicMock()
        success_resp = {'data': {'reference_id': 'SO-LOG-LINK-OK', 'order_id': 'gearment-9'}}
        mock_client._request = mock.MagicMock(return_value=success_resp)
        adapter = self._GearmentApiAdapter(env=self.env, client=mock_client)
        adapter.push_order(self._payload, sale_order_id=order.id)
        log = self.env['gearment.api.log'].search(
            [('endpoint', '=like', 'POST %/orders/draft%')],
            order='id desc', limit=1,
        )
        self.assertTrue(log)
        self.assertEqual(log.direction, 'outbound')
        self.assertEqual(log.sale_order_id.id, order.id)
        self.assertEqual(log.http_status, 200)
