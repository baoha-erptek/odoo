"""MF-E2E-3a Phase 2 ORM — carrier detection on the programmatic import path.

Repro (2026-07-04, staging): GDrive-polled tracking files produced
fulfillments with `shipping_carrier_id=False` — carrier detection only ran
in the wizard's `action_preview`, never in
`tracking_importer.import_log_from_bytes` (the poller path; the
apply_to_fulfillment docstring even said "here we leave it None"). Contract
pinned here: the programmatic path detects + applies carriers too.
"""

import io

from openpyxl import Workbook

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services import tracking_importer

# Header order matches .0temp/sample_bc_don_hang2026_04_08.xls (R0) — the
# canonical GKE schema fingerprint (trailing space on 'CREATIVE ' intended).
_GKE_HEADERS = (
    "ORDER NUMBER", "TRACKING NUMBER", "COUNTRY", "SONSIGNEE NAME", "STATE",
    "CITY", "ADDRESS", "POSTCODE", "PRODUCT NAME", "VALUE", "QUANTITY",
    "WEIGHT AT COSTOMER", "WEIGHT AT GKE", "COST", "CREATIVE ",
    "Ngày nhận tại kho", "Tình trạng đơn hàng", "Đường dẫn link label",
    "Đường dẫn link qrcode",
)


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(list(_GKE_HEADERS))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestGdrivePathCarrierDetect(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.usps = cls.env['shipping.carrier'].search(
            [('code', '=', 'usps')], limit=1)
        if not cls.usps:
            cls.usps = cls.env['shipping.carrier'].create({
                'name': 'USPS', 'code': 'usps',
                'tracking_prefix_regex': r'^(9[0-9]{15,21}|[A-Z]{2}[0-9]{9}US)$',
            })
        partner = cls.env['res.partner'].create({'name': 'GD Buyer'})
        product = cls.env['product.product'].create({
            'name': 'GD Product', 'list_price': 5.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': partner.id,
            'etsy_order_id': 'GDCD-1001',
            'order_line': [(0, 0, {'product_id': product.id,
                                   'product_uom_qty': 1.0,
                                   'price_unit': 5.0})],
        })

    def test_import_log_from_bytes_detects_and_applies_carrier(self):
        tracking = '9400111202555560009999'  # 22 digits → USPS regex
        file_bytes = _xlsx([(
            'GDCD-1001', tracking, 'US', 'GD Buyer', 'TX', 'Austin',
            '1 Lane', '78701', 'GD Product', 5.0, 1.0, 50.0, '', 1000.0,
            '01/07/2026', '', 'Get label', '', '',
        )])
        log = tracking_importer.import_log_from_bytes(
            self.env, file_bytes, 'gd_carrier_test.xlsx', source='gdrive')
        self.assertIn(log.state, ('ok', 'warning'))
        line = log.line_ids.filtered(
            lambda l: l.raw_tracking_number == tracking)
        self.assertTrue(line, 'import produced our line')
        self.assertEqual(
            line.detected_carrier_id, self.usps,
            'programmatic path must run carrier detection (was wizard-only)')
        fulfillment = self.env['sale.order.fulfillment'].search(
            [('order_id', '=', self.order.id)], limit=1)
        self.assertTrue(fulfillment)
        self.assertEqual(
            fulfillment.shipping_carrier_id, self.usps,
            'detected carrier must be applied to the fulfillment')


@tagged('post_install', '-at_install')
class TestSchemaComputeUnderBinSize(TransactionCase):
    """MF-E2E-3a: the schema compute must survive the web client's
    bin_size reads. Pre-fix, a form reload recomputed with excel_file
    rendered as a size string ("12.3 KB"), the parse silently failed, and
    New Schema showed unchecked — hiding the BA Manager's Approve Schema
    button and breaking the UI approval path (2026-07-04 TC-MTO-006)."""

    def test_is_new_schema_true_under_bin_size_context(self):
        import base64 as b64
        file_bytes = _xlsx([(
            'BINSZ-1', '9400111202555560009998', 'US', 'B', 'TX', 'A',
            '1 Ln', '78701', 'P', 5.0, 1.0, 50.0, '', 1000.0,
            '01/07/2026', '', 'Get label', '', '',
        )])
        wiz = self.env['tracking.import.wizard'].create({
            'excel_file': b64.b64encode(file_bytes),
            'excel_filename': 'binsize.xlsx',
        })
        wiz_web = self.env['tracking.import.wizard'].with_context(
            bin_size=True).browse(wiz.id)
        wiz_web.invalidate_recordset()
        self.assertTrue(
            wiz_web.schema_hash,
            'schema_hash must compute under bin_size reads (web client)')
        self.assertTrue(
            wiz_web.is_new_schema,
            'is_new_schema must stay truthful under bin_size reads')


@tagged('post_install', '-at_install')
class TestWebhookPushRunsUnderPublicEnv(TransactionCase):
    """MF-E2E-3b: the webhook-triggered Etsy tracking push (ADR D-A PRIMARY
    trigger) ran in the PUBLIC webhook env and died on the
    sale.order.fulfillment ACL — every live webhook push soft-failed and
    silently deferred to the 5-min cron (staging log 2026-07-04 15:50:24:
    "not allowed to access 'Fulfillment lifecycle...'")."""

    def test_tracking_webhook_push_persists_outcome_as_public(self):
        from unittest import mock
        shop = self.env['etsy.shop'].create({
            'name': 'WH Shop', 'etsy_api_shop_id': '60752388',
            'etsy_oauth_access_token': 'tok', 'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })
        partner = self.env['res.partner'].create({'name': 'WH Buyer'})
        product = self.env['product.product'].create({
            'name': 'WH Product', 'list_price': 5.0})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'etsy_order_id': 'WH-9001',
            'etsy_shop_id': shop.id,
            'order_line': [(0, 0, {'product_id': product.id,
                                   'product_uom_qty': 1.0,
                                   'price_unit': 5.0})],
        })
        self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
        })
        from odoo.addons.multichannel_hub_fulfillment.services import (
            gearment_webhook_dispatcher as gwd,
        )
        public_user = self.env.ref('base.public_user')
        public_env = self.env(user=public_user.id)
        body = {
            'order': {'reference': order.name, 'status': 'shipped'},
            'tracking': {'company': 'USPS',
                         'number': '9400111202555560007001',
                         'url': 'https://example.invalid/t'},
        }
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.'
            'EtsyApiClient'
        ) as ClientCls:
            client = mock.MagicMock()
            client.push_tracking.return_value = (True, '', 200)
            ClientCls.return_value = client
            handled, summary = gwd.GearmentWebhookDispatcher(
                public_env).dispatch('tracking_order_updated', body)
        self.assertTrue(handled, summary)
        order.invalidate_recordset()
        self.assertEqual(
            order.etsy_tracking_push_status, 'pushed',
            'webhook-triggered push must persist its outcome even from the '
            'public webhook env (was: AccessError soft-fail, status stayed '
            "'none')")
