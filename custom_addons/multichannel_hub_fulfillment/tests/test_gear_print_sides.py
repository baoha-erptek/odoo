"""P-GEAR-PRINT-SIDES — RED tests for per-design print-side selection + push guards.

Spec 015 backlog row P-GEAR-PRINT-SIDES (findings 2026-07-05 (C)). Today the
builder assigns sides positionally over a recordset ordered `create_date DESC,
id DESC` — the NEWEST file gets PRINT_LOCATION_CODE_FRONT, which inverts
front/back on two-sided lines. This slice adds `design.file.print_location`
(explicit side), keeps a deterministic id-ASC positional fallback for unset
rows, rejects duplicate explicit sides, rejects Gearment-eligible lines with
zero printable designs (was a silent drop), and adds a pre-push artwork URL
reachability check behind an ICP killswitch.
"""
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.models import sale_order as so_module
from odoo.addons.multichannel_hub_fulfillment.services import (
    gearment_payload_builder,
)


class _PrintSidesBase(TransactionCase):

    def setUp(self):
        super().setUp()
        partner = self.env['res.partner'].create({
            'name': 'Buyer Sides',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        product = self.env['product.product'].create({
            'name': 'Demo Tee', 'type': 'consu', 'list_price': 9.0,
        })
        product.product_tmpl_id.x_gearment_sku = 'GM0249020374'
        self.product = product
        self.order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })
        self.line = self.order.order_line[0]

    def _design(self, name, url, location=None):
        vals = {
            'name': name,
            'order_line_id': self.line.id,
            'file_url': url,
            'storage_mode': 'url',
            'state': 'approved',
        }
        if location is not None:
            vals['print_location'] = location
        return self.env['design.file'].create(vals)


@tagged('post_install', '-at_install', 'gear_print_sides')
class TestPrintSidesPayload(_PrintSidesBase):
    """build_payload honors explicit design.file.print_location."""

    def test_explicit_sides_honored_regardless_of_creation_order(self):
        # Back file created FIRST — positional heuristic would call it front.
        back = self._design('back art', 'https://x/back.png', location='back')
        front = self._design('front art', 'https://x/front.png', location='front')
        po = gearment_payload_builder.build_payload(
            self.order, back | front).line_items[0].printing_options
        by_code = {e['location_code']: e['url'] for e in po}
        self.assertEqual(by_code, {
            'PRINT_LOCATION_CODE_FRONT': 'https://x/front.png',
            'PRINT_LOCATION_CODE_BACK': 'https://x/back.png',
        })

    def test_explicit_back_plus_unset_assigns_front_to_unset(self):
        auto = self._design('auto art', 'https://x/auto.png')
        self._design('back art', 'https://x/back.png', location='back')
        files = self.order.order_line.design_file_ids
        po = gearment_payload_builder.build_payload(
            self.order, files).line_items[0].printing_options
        by_code = {e['location_code']: e['url'] for e in po}
        self.assertEqual(
            by_code.get('PRINT_LOCATION_CODE_FRONT'), 'https://x/auto.png')
        self.assertEqual(
            by_code.get('PRINT_LOCATION_CODE_BACK'), 'https://x/back.png')
        self.assertFalse(auto.print_location, "no hard default — unset means auto")

    def test_unset_fallback_is_id_asc_not_newest_first(self):
        first = self._design('first', 'https://x/a.png')
        second = self._design('second', 'https://x/b.png')
        # Feed the recordset in the model's natural DESC order.
        files = (second | first).sorted(key=lambda d: -d.id)
        po = gearment_payload_builder.build_payload(
            self.order, files).line_items[0].printing_options
        self.assertEqual(po[0]['location_code'], 'PRINT_LOCATION_CODE_FRONT')
        self.assertEqual(po[0]['url'], 'https://x/a.png',
                         "oldest (id ASC) file must get FRONT, not the newest")

    def test_duplicate_explicit_side_raises_usererror(self):
        self._design('front 1', 'https://x/f1.png', location='front')
        self._design('front 2', 'https://x/f2.png', location='front')
        files = self.order.order_line.design_file_ids
        with self.assertRaises(UserError):
            gearment_payload_builder.build_payload(self.order, files)

    def test_eligible_line_with_no_designs_raises_naming_product(self):
        with self.assertRaises(UserError) as cm:
            gearment_payload_builder.build_payload(
                self.order, self.env['design.file'])
        self.assertIn('Demo Tee', str(cm.exception))

    def test_quote_body_uses_explicit_locations(self):
        self._design('back only', 'https://x/back.png', location='back')
        files = self.order.order_line.design_file_ids
        body = gearment_payload_builder.build_quote_body(self.order, files)
        self.assertEqual(body['line_items'][0]['print_locations'], ['back'])


@tagged('post_install', '-at_install', 'gear_print_sides')
class TestArtworkReachabilityGuard(_PrintSidesBase):
    """action_push_to_gearment HEAD-checks artwork URLs behind an ICP killswitch."""

    _ICP = 'multichannel_hub.gearment_artwork_url_check_enabled'

    def setUp(self):
        super().setUp()
        self._design('front art', 'https://x/front.png', location='front')

    def _push(self, head_status=200, icp=None):
        if icp is not None:
            self.env['ir.config_parameter'].sudo().set_param(self._ICP, icp)
        mock_adapter = mock.MagicMock()
        mock_adapter.return_value.push_order.return_value = {'id': 'GM-REF-1'}
        head_resp = mock.MagicMock(
            status_code=head_status, url='https://x/front.png')
        with mock.patch.object(
                so_module.gearment_adapter, 'GearmentApiAdapter', mock_adapter), \
             mock.patch.object(
                so_module.requests, 'head', return_value=head_resp) as head:
            self.order.action_push_to_gearment()
        return mock_adapter, head

    def test_unreachable_artwork_url_blocks_push(self):
        with self.assertRaises(UserError):
            self._push(head_status=404)
        self.assertFalse(self.order.x_gearment_outbound_ref)

    def test_reachable_artwork_url_allows_push(self):
        adapter, head = self._push(head_status=200)
        head.assert_called()
        self.assertEqual(self.order.x_gearment_outbound_ref, 'GM-REF-1')

    def test_killswitch_off_skips_reachability_check(self):
        adapter, head = self._push(head_status=404, icp='False')
        head.assert_not_called()
        self.assertEqual(self.order.x_gearment_outbound_ref, 'GM-REF-1')

    def test_private_ip_artwork_url_blocked_without_request(self):
        """SSRF defense: a private/loopback artwork URL is rejected before
        any HTTP request fires."""
        files = self.order.order_line.design_file_ids
        files.file_url = 'https://127.0.0.1/internal.png'
        with self.assertRaises(UserError):
            self._push(head_status=200)
        self.assertFalse(self.order.x_gearment_outbound_ref)
