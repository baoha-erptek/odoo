"""RED — Defect-2026-05-10-05: draft `location_code` must be the proto3 enum.

The live `/api/v3/orders/draft` validator rejects every payload with an opaque
400 (`must include ... location_code front, pocket, back or whole`). The 2026-07-05
doc crawl (`docs/vendor/gearment/api_api.order.v1.vendororderapi.md`) shows the
wire value is the proto3 enum `PRINT_LOCATION_CODE_*` (example
`PRINT_LOCATION_CODE_WHOLE`) — the human names in the 400 message are NOT the wire
values. Our builder emitted bare `front`/`back`, which is why all 14+ probes failed.

These assert the corrected contract. They fail on the pre-fix builder
(`_PRINT_LOCATIONS_DEFAULT = ('front', 'back')`) and pass once it emits the
prefixed enum. WHOLE is literal-confirmed from the docs; FRONT/BACK are the same
prefix applied to the 400's own allowed-list — final confirmation is a live probe
behind the owner-sign-off gate.
"""

from odoo.tests.common import TransactionCase, tagged


def _build_payload():
    from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload_builder import (
        build_payload,
    )
    return build_payload


@tagged('post_install', '-at_install', 'gm_printing_location_enum')
class TestPrintingLocationEnum(TransactionCase):
    """Builder emits `PRINT_LOCATION_CODE_*`, never the bare human names."""

    def setUp(self):
        super().setUp()
        self._build_payload = _build_payload()
        partner = self.env['res.partner'].create({
            'name': 'Buyer Test',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        product = self.env['product.product'].create({
            'name': 'Demo Mug', 'type': 'consu', 'list_price': 5.0,
        })
        product.product_tmpl_id.x_gearment_sku = '1234'
        self.order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })

    def _design(self, name, url):
        return self.env['design.file'].create({
            'name': name,
            'order_line_id': self.order.order_line[0].id,
            'file_url': url,
            'storage_mode': 'url',
            'state': 'approved',
        })

    def test_first_design_uses_print_location_code_front(self):
        d = self._design('front', 'https://drive.example/front.png')
        po = self._build_payload(self.order, d).line_items[0].printing_options
        self.assertEqual(po[0]['location_code'], 'PRINT_LOCATION_CODE_FRONT')

    def test_second_design_uses_print_location_code_back(self):
        da = self._design('a', 'https://drive.example/a.png')
        db = self._design('b', 'https://drive.example/b.png')
        po = self._build_payload(self.order, da | db).line_items[0].printing_options
        codes = [e['location_code'] for e in po]
        self.assertEqual(codes, ['PRINT_LOCATION_CODE_FRONT', 'PRINT_LOCATION_CODE_BACK'])

    def test_no_bare_human_location_names_leak(self):
        """Regression guard: the exact strings that the validator silently rejects."""
        da = self._design('a', 'https://drive.example/a.png')
        db = self._design('b', 'https://drive.example/b.png')
        po = self._build_payload(self.order, da | db).line_items[0].printing_options
        for entry in po:
            code = entry['location_code']
            self.assertNotIn(code, {'front', 'back', 'pocket', 'whole'})
            self.assertTrue(code.startswith('PRINT_LOCATION_CODE_'),
                            f"{code!r} is not the proto3 enum form")
