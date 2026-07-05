"""P4-01-FIX-PAYLOAD-SCHEMA — line_items schema for the live /orders/draft.

History:
  - Spawned by Defect-2026-05-10-02: draft rejected `product_id` + flat
    `design_url_front/back`; corrected to `printing_options[]`.
  - 2026-07-05: the enum fix (Defect-05-10-05) unblocked the draft and the 400
    moved to `some gm product variants not found`. The draft line-item key is the
    GM-prefixed catalog `variant_id` (e.g. GM0249020374), NOT `legacy_id`. These
    tests now pin `variant_id`. Proven live 200: draft 260705P-GM3MUJU-Y20XJXY6.

Spec citations:
  - specs/004-fulfillment-routing/research.md:44 — "line items with `variant_id`,
    `quantity`, `printing_options` (location_code + design URL)"
  - docs/vendor/gearment/api_api.order.v1.vendororderapi.md — draft line_item
    example carries `variant_id`.
"""

from odoo.tests.common import TransactionCase, tagged


def _payload_classes():
    """Defer import so module loads even when GREEN hasn't shipped yet."""
    from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
        GearmentAddress,
        GearmentLineItem,
        GearmentOrderPayload,
    )
    return GearmentAddress, GearmentLineItem, GearmentOrderPayload


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestLineItemUsesVariantId(TransactionCase):
    """`GearmentLineItem` carries the GM catalog `variant_id`, not legacy_id/product_id."""

    def test_line_item_has_variant_id_field(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            variant_id='GM0249020374', quantity=1,
            printing_options=({'location_code': 'PRINT_LOCATION_CODE_FRONT',
                               'url': 'https://x/y.png'},),
        )
        self.assertEqual(line.variant_id, 'GM0249020374')

    def test_line_item_dropped_legacy_and_product_id_fields(self):
        """Draft is keyed by variant_id — legacy_id/product_id are gone."""
        _, GearmentLineItem, _ = _payload_classes()
        from dataclasses import fields
        field_names = {f.name for f in fields(GearmentLineItem)}
        self.assertNotIn('product_id', field_names)
        self.assertNotIn('legacy_id', field_names)
        self.assertIn('variant_id', field_names)


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestLineItemPrintingOptions(TransactionCase):
    """`GearmentLineItem.printing_options` is a tuple of {location_code, url} dicts."""

    def test_line_item_has_printing_options_field(self):
        _, GearmentLineItem, _ = _payload_classes()
        from dataclasses import fields
        field_names = {f.name for f in fields(GearmentLineItem)}
        self.assertIn('printing_options', field_names)

    def test_line_item_printing_options_is_tuple_of_dicts(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            variant_id='GM0249020374', quantity=1,
            printing_options=(
                {'location_code': 'PRINT_LOCATION_CODE_FRONT', 'url': 'https://x/front.png'},
                {'location_code': 'PRINT_LOCATION_CODE_BACK', 'url': 'https://x/back.png'},
            ),
        )
        self.assertIsInstance(line.printing_options, tuple)
        self.assertEqual(line.printing_options[0]['location_code'], 'PRINT_LOCATION_CODE_FRONT')
        self.assertEqual(line.printing_options[0]['url'], 'https://x/front.png')
        self.assertEqual(line.printing_options[1]['location_code'], 'PRINT_LOCATION_CODE_BACK')

    def test_line_item_does_not_have_design_url_front_back_fields(self):
        """Flat `design_url_front`/`design_url_back` replaced by `printing_options[]`."""
        _, GearmentLineItem, _ = _payload_classes()
        from dataclasses import fields
        field_names = {f.name for f in fields(GearmentLineItem)}
        self.assertNotIn('design_url_front', field_names)
        self.assertNotIn('design_url_back', field_names)


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestSerializeLineItemsShape(TransactionCase):
    """Wire-format `line_items[].variant_id` + `line_items[].printing_options[]`."""

    def _make_payload(self, *, line_items):
        GearmentAddress, _, GearmentOrderPayload = _payload_classes()
        addr = GearmentAddress(
            first_name='Alice', last_name='Buyer',
            street_1='123 Main St', street_2=None,
            city='Boston', state_code='MA', zip_code='02108', country_code='US',
        )
        return GearmentOrderPayload(
            reference_id='SO-2026-FIX-01', store_id='demo',
            platform='MARKETPLACE_PLATFORM_ETSY',
            addresses=(addr,), line_items=line_items,
        )

    def test_serialize_line_item_emits_variant_id_not_product_id(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            variant_id='GM0249020374', quantity=2,
            printing_options=({'location_code': 'PRINT_LOCATION_CODE_FRONT',
                               'url': 'https://x/y.png'},),
        )
        body = self._make_payload(line_items=(line,)).serialize()
        item = body['data']['line_items'][0]
        self.assertEqual(item['variant_id'], 'GM0249020374')
        self.assertNotIn('product_id', item)
        self.assertNotIn('legacy_id', item)

    def test_serialize_line_item_emits_printing_options_array(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            variant_id='GM0249020374', quantity=1,
            printing_options=(
                {'location_code': 'PRINT_LOCATION_CODE_FRONT', 'url': 'https://x/front.png'},
                {'location_code': 'PRINT_LOCATION_CODE_BACK', 'url': 'https://x/back.png'},
            ),
        )
        body = self._make_payload(line_items=(line,)).serialize()
        item = body['data']['line_items'][0]
        self.assertIn('printing_options', item)
        self.assertEqual(len(item['printing_options']), 2)
        self.assertEqual(item['printing_options'][0]['location_code'], 'PRINT_LOCATION_CODE_FRONT')
        self.assertEqual(item['printing_options'][0]['url'], 'https://x/front.png')
        self.assertEqual(item['printing_options'][1]['location_code'], 'PRINT_LOCATION_CODE_BACK')
        self.assertNotIn('design_url_front', item)
        self.assertNotIn('design_url_back', item)

    def test_serialize_emits_singular_address_and_platform(self):
        """Envelope uses SINGULAR `address` + required `platform` (proven-200 shape)."""
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            variant_id='GM0249020374', quantity=1,
            printing_options=({'location_code': 'PRINT_LOCATION_CODE_FRONT',
                               'url': 'https://x/y.png'},),
        )
        data = self._make_payload(line_items=(line,)).serialize()['data']
        self.assertIn('address', data)
        self.assertNotIn('addresses', data)
        self.assertEqual(data['address']['state_code'], 'MA')
        self.assertEqual(data['platform'], 'MARKETPLACE_PLATFORM_ETSY')


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestBuilderEmitsCorrectSchema(TransactionCase):
    """`build_payload()` derives `variant_id` from x_gearment_sku + printing_options."""

    def setUp(self):
        super().setUp()
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload_builder import (
            build_payload,
        )
        self._build_payload = build_payload

    def _make_minimal_order(self):
        partner = self.env['res.partner'].create({
            'name': 'Buyer Test',
            'street': '123 Main St',
            'city': 'Boston',
            'state_id': self.env.ref('base.state_us_22').id,
            'zip': '02108',
            'country_id': self.env.ref('base.us').id,
        })
        product = self.env['product.product'].create({
            'name': 'Demo Mug',
            'type': 'consu',
            'list_price': 5.0,
        })
        product.product_tmpl_id.x_gearment_sku = 'GM0249020374'  # GM variant_id
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        return order, product

    def _approved_design(self, order, name, url):
        return self.env['design.file'].create({
            'name': name,
            'order_line_id': order.order_line[0].id,
            'file_url': url,
            'storage_mode': 'url',
            'state': 'approved',
        })

    def test_builder_sets_variant_id_from_sku(self):
        order, product = self._make_minimal_order()
        design = self._approved_design(order, 'front design', 'https://drive.example/front.png')
        payload = self._build_payload(order, design)
        self.assertEqual(payload.line_items[0].variant_id, 'GM0249020374')

    def test_builder_sets_platform_and_shipping_method(self):
        order, product = self._make_minimal_order()
        design = self._approved_design(order, 'front design', 'https://drive.example/front.png')
        payload = self._build_payload(order, design)
        self.assertEqual(payload.platform, 'MARKETPLACE_PLATFORM_ETSY')
        self.assertEqual(payload.shipping_method, 'METHOD_STANDARD')

    def test_builder_emits_printing_options_for_each_design(self):
        order, product = self._make_minimal_order()
        design_front = self._approved_design(order, 'front design', 'https://drive.example/front.png')
        design_back = self._approved_design(order, 'back design', 'https://drive.example/back.png')
        payload = self._build_payload(order, design_front | design_back)
        po = payload.line_items[0].printing_options
        self.assertEqual(len(po), 2)
        location_codes = {entry['location_code'] for entry in po}
        self.assertIn('PRINT_LOCATION_CODE_FRONT', location_codes)
        self.assertIn('PRINT_LOCATION_CODE_BACK', location_codes)
        urls = {entry['url'] for entry in po}
        self.assertIn('https://drive.example/front.png', urls)
        self.assertIn('https://drive.example/back.png', urls)

    def test_builder_first_design_gets_front_location(self):
        """Heuristic: first approved design.file → FRONT; second → BACK."""
        order, product = self._make_minimal_order()
        design_a = self._approved_design(order, 'first', 'https://drive.example/a.png')
        design_b = self._approved_design(order, 'second', 'https://drive.example/b.png')
        payload = self._build_payload(order, design_a | design_b)
        po = payload.line_items[0].printing_options
        self.assertEqual(po[0]['location_code'], 'PRINT_LOCATION_CODE_FRONT')
        self.assertEqual(po[0]['url'], 'https://drive.example/a.png')
        self.assertEqual(po[1]['location_code'], 'PRINT_LOCATION_CODE_BACK')

    def test_builder_skips_line_with_no_designs_and_no_existing_options(self):
        """A line item with zero design_files cannot ship — builder skips it."""
        order, product = self._make_minimal_order()
        payload = self._build_payload(order, self.env['design.file'])
        for line in payload.line_items:
            self.assertGreaterEqual(len(line.printing_options), 1,
                "every emitted line must have at least one printing_option")
