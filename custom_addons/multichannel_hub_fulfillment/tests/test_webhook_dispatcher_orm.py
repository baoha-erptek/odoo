"""P0-18b2c Phase 2 — Dispatcher unit + HTTP integration tests.

Covers:
- _handle_order_completed/_cancelled/_tracking_order_updated/_on_hold
- _handle_log_only for shipping_address_*, product_out_of_stock, variant_*
- Unknown-topic soft-fail
- Handler exception soft-fail (no re-raise)
- XSS escaping in chatter posts
- End-to-end POST /gearment/webhook with valid signature → fulfillment write
- Order-not-found returns 200 (no Gearment retry storm)
- Invalid signature does NOT call dispatcher
"""
import base64
import hashlib
import hmac
import json
import os
import time
from unittest import mock

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services.gearment_webhook_dispatcher import (
    GearmentWebhookDispatcher,
)


# Synthetic auth credentials (mirror test_webhook_verify_orm.py pattern).
TEST_CLIENT_KEY = 'TEST_KEY_DO_NOT_USE'
TEST_SECRET = 'TEST_SECRET_DO_NOT_USE_IN_PROD_64chars_padded_xxxxxxxxxxxxxxxxxx'
_WEBHOOK_PATH = '/gearment/webhook'


def _compute_sig(nonce, ts, body_bytes, secret=TEST_SECRET, url_path=_WEBHOOK_PATH):
    body_b64 = base64.urlsafe_b64encode(body_bytes).decode('ascii')
    msg = (url_path + nonce + ts + body_b64).encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii')


def _seed_order_and_fulfillment(env, name='SO-TEST-DISPATCH-001'):
    """Create a sale.order with default fulfillment for handler tests."""
    partner = env['res.partner'].create({'name': 'Webhook Test Partner'})
    order = env['sale.order'].create({
        'name': name,
        'partner_id': partner.id,
    })
    # fulfillment_id auto-created via _inherits direction-A on sale.order
    return order


@tagged('post_install', '-at_install')
class TestDispatcherUnit(TransactionCase):
    """Pure dispatcher unit tests; no HTTP layer."""

    def setUp(self):
        super().setUp()
        self.dispatcher = GearmentWebhookDispatcher(self.env)

    def _body(self, type_, reference=None, status=None, tracking=None):
        body = {'type': type_, 'order': {'reference': reference or '',
                                          'status': status or ''}}
        if tracking:
            body['tracking'] = tracking
        return body

    def test_order_completed_writes_tracking(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-COMPLETE-001')
        body = self._body(
            'order_completed', reference='SO-COMPLETE-001',
            tracking={'company': 'USPS', 'number': '9400111202555550000099',
                       'url': 'https://track.usps.com/...'},
        )
        handled, summary = self.dispatcher.dispatch('order_completed', body)
        self.assertTrue(handled)
        self.assertIn('order_completed:tracking_set:USPS', summary)
        f = order.fulfillment_id
        self.assertEqual(f.tracking_number, '9400111202555550000099')
        self.assertEqual(f.tracking_url, 'https://track.usps.com/...')
        self.assertEqual(f.tracking_state, 'shipped')
        self.assertEqual(f.shipping_date, fields.Date.context_today(f))

    def test_order_completed_no_match_soft_fails(self):
        body = self._body('order_completed', reference='NONEXISTENT-XYZ',
                            tracking={'number': 'X', 'company': 'Y'})
        handled, summary = self.dispatcher.dispatch('order_completed', body)
        self.assertTrue(handled)  # topic recognised
        self.assertEqual(summary, 'order_not_found')

    def test_order_completed_no_reference_soft_fails(self):
        body = self._body('order_completed', tracking={'number': 'X'})
        handled, summary = self.dispatcher.dispatch('order_completed', body)
        self.assertTrue(handled)
        self.assertEqual(summary, 'no_reference')

    def test_order_cancelled_blocks_production(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-CANCEL-001')
        body = self._body('order_cancelled', reference='SO-CANCEL-001',
                            status='cancelled')
        handled, summary = self.dispatcher.dispatch('order_cancelled', body)
        self.assertTrue(handled)
        self.assertIn('order_cancelled', summary)
        self.assertTrue(order.fulfillment_id.production_blocked)
        self.assertIn('cancelled', (order.fulfillment_id.block_reason or '').lower())

    def test_tracking_order_updated_keeps_existing_state(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-TRACK-001')
        # Bypass FR-017 lock by writing initial state via context.
        order.fulfillment_id.with_context(
            bypass_address_change_check=True,
        ).write({'tracking_state': 'shipped',
                  'tracking_number': 'OLD-TRK-NUM'})
        body = self._body('tracking_order_updated', reference='SO-TRACK-001',
                            tracking={'number': 'NEW-TRK-NUM',
                                      'company': 'UniUni'})
        handled, summary = self.dispatcher.dispatch(
            'tracking_order_updated', body,
        )
        self.assertTrue(handled)
        self.assertIn('refreshed', summary)
        f = order.fulfillment_id
        self.assertEqual(f.tracking_number, 'NEW-TRK-NUM')
        # State must NOT regress from shipped.
        self.assertEqual(f.tracking_state, 'shipped')

    def test_order_on_hold_blocks_no_rollback(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-HOLD-001')
        body = self._body('order_on_hold', reference='SO-HOLD-001',
                            status='waiting_design')
        handled, summary = self.dispatcher.dispatch('order_on_hold', body)
        self.assertTrue(handled)
        self.assertEqual(summary, 'order_on_hold:blocked')
        self.assertTrue(order.fulfillment_id.production_blocked)
        self.assertIn('hold', (order.fulfillment_id.block_reason or '').lower())

    def test_log_only_topic_records_chatter(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-LOG-001')
        body = self._body('shipping_address_unverified',
                            reference='SO-LOG-001', status='manual_review')
        handled, summary = self.dispatcher.dispatch(
            'shipping_address_unverified', body,
        )
        self.assertTrue(handled)
        self.assertIn('shipping_address_unverified', summary)
        # No business field changes.
        self.assertFalse(order.fulfillment_id.production_blocked)

    def test_unknown_topic_returns_unhandled(self):
        body = self._body('weird_event_xyz', reference='SO-LOG-001')
        handled, summary = self.dispatcher.dispatch('weird_event_xyz', body)
        self.assertFalse(handled)
        self.assertIn('unknown_topic:weird_event_xyz', summary)

    def test_handler_exception_does_not_re_raise(self):
        """If a handler raises, dispatcher converts to soft-fail tuple."""
        with mock.patch.object(
            GearmentWebhookDispatcher, '_handle_order_completed',
            side_effect=RuntimeError('boom'),
        ):
            handled, summary = self.dispatcher.dispatch(
                'order_completed', {'type': 'order_completed', 'order': {}},
            )
        self.assertFalse(handled)
        self.assertIn('handler_error:RuntimeError', summary)

    def test_xss_in_status_escaped_in_chatter(self):
        order = _seed_order_and_fulfillment(self.env, 'SO-XSS-001')
        evil = '<img src=x onerror=alert(1)>'
        body = self._body('order_on_hold', reference='SO-XSS-001',
                            status=evil)
        self.dispatcher.dispatch('order_on_hold', body)
        # Chatter body must NOT contain raw <img onerror; markupsafe escape
        # converts < to &lt;
        msgs = order.message_ids.filtered(
            lambda m: 'on hold' in (m.body or '').lower(),
        )
        self.assertTrue(msgs, "Expected an on-hold chatter message")
        body_html = msgs[0].body
        self.assertNotIn('<img src=x onerror', body_html,
                          "XSS payload must be escaped in chatter")
        self.assertIn('&lt;img', body_html)

    def test_invalid_body_shape(self):
        handled, summary = self.dispatcher.dispatch(
            'order_completed', 'not-a-dict',
        )
        self.assertFalse(handled)
        self.assertEqual(summary, 'invalid_body_shape')

    def test_pipeline_rollback_failure_keeps_production_block(self):
        """Security review LOW-1: when _write_pipeline_state raises, the
        fulfillment block must still be persisted (operator sees both
        the block and the failed-rollback log line)."""
        order = _seed_order_and_fulfillment(self.env, 'SO-ROLLBACK-FAIL-001')
        # Force the order's pipeline to gearment_pod with state != quoted so
        # rollback path actually fires.
        gearment_pipeline = self.env.ref(
            'multichannel_hub_core.order_pipeline_gearment_pod',
        )
        confirmed_state = self.env.ref(
            'multichannel_hub_core.state_gearment_confirmed',
        )
        order.with_context(bypass_pipeline_state_guard=True).write({
            'x_pipeline_id': gearment_pipeline.id,
            'x_pipeline_state_id': confirmed_state.id,
        })
        body = {'type': 'order_cancelled',
                'order': {'reference': 'SO-ROLLBACK-FAIL-001',
                           'status': 'forced'}}
        # Patch _write_pipeline_state on the model class to raise.
        from odoo.addons.multichannel_hub_core.models.sale_order import (
            SaleOrder,
        )
        with mock.patch.object(
            SaleOrder, '_write_pipeline_state',
            side_effect=RuntimeError('forced rollback failure'),
        ):
            handled, summary = self.dispatcher.dispatch(
                'order_cancelled', body,
            )
        self.assertTrue(handled)
        self.assertEqual(summary, 'order_cancelled:blocked_and_rolled_back')
        # The block IS persisted even though rollback raised.
        self.assertTrue(order.fulfillment_id.production_blocked)
        self.assertIn('cancelled',
                       (order.fulfillment_id.block_reason or '').lower())


@tagged('post_install', '-at_install')
class TestDispatcherHTTP(HttpCase):
    """End-to-end HTTP webhook + verify + dispatch flow."""

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': TEST_SECRET,
        'GEARMENT_API_KEY': TEST_CLIENT_KEY,
    }, clear=False)
    @mock.patch(
        'odoo.addons.multichannel_hub_fulfillment.controllers.'
        'gearment_webhook.time.time',
        return_value=1777740000.0,
    )
    def test_e2e_valid_signature_dispatches(self, _mock_time):
        # Pre-create the order so the dispatcher can find it.
        # HttpCase shares the DB but the request handler runs in its own
        # cursor; Odoo's test framework propagates pre-test commits via
        # savepoints. Avoid explicit cr.commit() (forbidden in tests).
        order = _seed_order_and_fulfillment(self.env, 'SO-E2E-001')
        self.env.flush_all()
        body = json.dumps({
            'order': {'reference': 'SO-E2E-001'},
            'tracking': {'company': 'USPS', 'number': 'E2E-TRACK-1',
                         'url': 'https://track.usps.com/E2E-TRACK-1'},
            'type': 'order_completed',
        }).encode('utf-8')
        nonce = 'e2e_nonce_001'
        ts = '1777740000'
        sig = _compute_sig(nonce, ts, body)
        response = self.url_open(
            '/gearment/webhook', data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': sig,
                'X-Connect-Client-Key': TEST_CLIENT_KEY,
                'X-Connect-Timestamp': ts,
                'X-Connect-Nonce': nonce,
            },
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)
        log = self.env['gearment.api.log'].sudo().search([
            ('nonce_value', '=', nonce),
        ], limit=1)
        self.assertTrue(log)
        self.assertTrue(log.signature_verified)
        self.assertTrue(log.business_handled)
        self.assertIn('order_completed', log.business_summary or '')
        self.assertEqual(log.sale_order_id.id, order.id)
        order.invalidate_recordset()
        self.assertEqual(order.fulfillment_id.tracking_number, 'E2E-TRACK-1')
        self.assertEqual(order.fulfillment_id.tracking_state, 'shipped')

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': TEST_SECRET,
        'GEARMENT_API_KEY': TEST_CLIENT_KEY,
    }, clear=False)
    @mock.patch(
        'odoo.addons.multichannel_hub_fulfillment.controllers.'
        'gearment_webhook.time.time',
        return_value=1777740100.0,
    )
    def test_e2e_unknown_order_still_returns_200(self, _mock_time):
        body = json.dumps({
            'order': {'reference': 'NEVER-EXISTED-XYZ'},
            'type': 'order_completed',
        }).encode('utf-8')
        nonce = 'e2e_unknown_nonce'
        ts = '1777740100'
        sig = _compute_sig(nonce, ts, body)
        response = self.url_open(
            '/gearment/webhook', data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': sig,
                'X-Connect-Client-Key': TEST_CLIENT_KEY,
                'X-Connect-Timestamp': ts,
                'X-Connect-Nonce': nonce,
            },
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)
        log = self.env['gearment.api.log'].sudo().search([
            ('nonce_value', '=', nonce),
        ], limit=1)
        self.assertTrue(log)
        self.assertTrue(log.signature_verified)
        # business_handled True because topic recognised
        self.assertTrue(log.business_handled)
        self.assertEqual(log.business_summary, 'order_not_found')
        self.assertFalse(log.sale_order_id)

    def test_e2e_invalid_signature_skips_dispatch(self):
        body = json.dumps({
            'order': {'reference': 'SOMETHING'},
            'type': 'order_completed',
        }).encode('utf-8')
        response = self.url_open(
            '/gearment/webhook', data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': 'BOGUS_SIG',
                'X-Connect-Client-Key': 'WRONG',
                'X-Connect-Timestamp': '1',
                'X-Connect-Nonce': 'bogus',
            },
            timeout=30,
        )
        self.assertEqual(response.status_code, 401)
        log = self.env['gearment.api.log'].sudo().search([
            ('nonce_value', '=', 'bogus'),
        ], limit=1)
        self.assertTrue(log)
        self.assertFalse(log.signature_verified)
        # Dispatcher must not have run.
        self.assertFalse(log.business_handled)
        self.assertEqual(log.business_summary or '', '')
