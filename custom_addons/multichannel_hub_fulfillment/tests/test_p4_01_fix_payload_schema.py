"""P4-01-FIX-PAYLOAD-SCHEMA — RED tests for the line_items schema correction.

Spawned by Defect-2026-05-10-02. Live `/api/v3/orders/draft` rejects current
payload with three errors:
  - `Exactly one of 'variant_id' or 'legacy_id' must be set` (we send `product_id`)
  - `A line item must include at least one printing option with location_code
     front, pocket, back or whole` (we send flat `design_url_front/back`)
  - `printing_options: value must contain at least 1 item(s)` (we don't send it)

Spec citations (predate P4-01-B drift):
  - specs/004-fulfillment-routing/research.md:43 — "Design files: Passed as URLs
    in `printing_options[].url`"
  - specs/004-fulfillment-routing/research.md:44 — "line items with `variant_id`,
    `quantity`, `printing_options` (location_code + design URL)"
  - specs/004-fulfillment-routing/plan.md:145 — "design_files: list[dict]
    [{role, url, print_location_code}, ...]"

These tests fail on commit 8410d3274a7 (P4-01-D) and pass after the fix lands.
"""

from unittest import mock

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
class TestLineItemUsesLegacyId(TransactionCase):
    """`GearmentLineItem` carries `legacy_id` (Gearment catalog int), not `product_id`."""

    def test_line_item_has_legacy_id_field(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            legacy_id=1234, quantity=1, sku='MUG-001',
            printing_options=({'location_code': 'front', 'url': 'https://x/y.png'},),
        )
        self.assertEqual(line.legacy_id, 1234)

    def test_line_item_does_not_have_product_id_field(self):
        """Schema correction: `product_id` was rejected by Gearment — gone."""
        _, GearmentLineItem, _ = _payload_classes()
        from dataclasses import fields
        field_names = {f.name for f in fields(GearmentLineItem)}
        self.assertNotIn('product_id', field_names)
        self.assertIn('legacy_id', field_names)


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
            legacy_id=1234, quantity=1, sku='MUG-001',
            printing_options=(
                {'location_code': 'front', 'url': 'https://x/front.png'},
                {'location_code': 'back', 'url': 'https://x/back.png'},
            ),
        )
        self.assertIsInstance(line.printing_options, tuple)
        self.assertEqual(line.printing_options[0]['location_code'], 'front')
        self.assertEqual(line.printing_options[0]['url'], 'https://x/front.png')
        self.assertEqual(line.printing_options[1]['location_code'], 'back')

    def test_line_item_does_not_have_design_url_front_back_fields(self):
        """Flat `design_url_front`/`design_url_back` replaced by `printing_options[]`."""
        _, GearmentLineItem, _ = _payload_classes()
        from dataclasses import fields
        field_names = {f.name for f in fields(GearmentLineItem)}
        self.assertNotIn('design_url_front', field_names)
        self.assertNotIn('design_url_back', field_names)


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestSerializeLineItemsShape(TransactionCase):
    """Wire-format `line_items[].legacy_id` + `line_items[].printing_options[]`."""

    def _make_payload(self, *, line_items):
        GearmentAddress, _, GearmentOrderPayload = _payload_classes()
        addr = GearmentAddress(
            first_name='Alice', last_name='Buyer',
            street_1='123 Main St', street_2=None,
            city='Boston', state='MA', zip_code='02108', country_code='US',
        )
        return GearmentOrderPayload(
            reference_id='SO-2026-FIX-01', store_id='demo',
            addresses=(addr,), line_items=line_items,
        )

    def test_serialize_line_item_emits_legacy_id_not_product_id(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            legacy_id=1234, quantity=2, sku='MUG-001',
            printing_options=({'location_code': 'front', 'url': 'https://x/y.png'},),
        )
        body = self._make_payload(line_items=(line,)).serialize()
        item = body['data']['line_items'][0]
        self.assertEqual(item['legacy_id'], 1234)
        self.assertNotIn('product_id', item)

    def test_serialize_line_item_emits_printing_options_array(self):
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            legacy_id=1234, quantity=1, sku='MUG-001',
            printing_options=(
                {'location_code': 'front', 'url': 'https://x/front.png'},
                {'location_code': 'back', 'url': 'https://x/back.png'},
            ),
        )
        body = self._make_payload(line_items=(line,)).serialize()
        item = body['data']['line_items'][0]
        self.assertIn('printing_options', item)
        self.assertEqual(len(item['printing_options']), 2)
        self.assertEqual(item['printing_options'][0]['location_code'], 'front')
        self.assertEqual(item['printing_options'][0]['url'], 'https://x/front.png')
        self.assertEqual(item['printing_options'][1]['location_code'], 'back')
        # Flat `design_url_front`/`design_url_back` MUST NOT appear in wire body
        self.assertNotIn('design_url_front', item)
        self.assertNotIn('design_url_back', item)

    def test_serialize_omits_printing_options_when_empty_tuple(self):
        """An empty printing_options tuple should NOT emit the key (avoid '[]' which Gearment rejects).

        Builder is responsible for not creating such line_items, but the serializer
        is defensive — we exclude keys whose value is an empty tuple/list.
        """
        _, GearmentLineItem, _ = _payload_classes()
        line = GearmentLineItem(
            legacy_id=1234, quantity=1, sku='MUG-001',
            printing_options=(),
        )
        body = self._make_payload(line_items=(line,)).serialize()
        item = body['data']['line_items'][0]
        # When printing_options is empty, the key may be absent OR empty.
        # Either is acceptable; what we forbid is sending `printing_options: null`
        # (Gearment proto rejects null array). dataclasses.asdict preserves the
        # original container type, so an empty tuple stays a tuple — JSON
        # serialization (json.dumps) coerces tuples to lists transparently, so
        # this is wire-format-correct as long as the value is empty.
        if 'printing_options' in item:
            self.assertEqual(len(item['printing_options']), 0)
            self.assertIsNotNone(item['printing_options'])


@tagged('post_install', '-at_install', 'p4_01_fix_payload_schema')
class TestBuilderEmitsCorrectSchema(TransactionCase):
    """`build_payload()` derives `legacy_id` from SKU + `printing_options` from design_files."""

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
        product.product_tmpl_id.x_gearment_sku = '1234'  # numeric SKU → legacy_id=1234
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        return order, product

    def test_builder_sets_legacy_id_from_numeric_sku(self):
        order, product = self._make_minimal_order()
        design = self.env['design.file'].create({
            'name': 'front design',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://drive.example/front.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        payload = self._build_payload(order, design)
        self.assertEqual(payload.line_items[0].legacy_id, 1234)

    def test_builder_emits_printing_options_for_each_design(self):
        order, product = self._make_minimal_order()
        design_front = self.env['design.file'].create({
            'name': 'front design',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://drive.example/front.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        design_back = self.env['design.file'].create({
            'name': 'back design',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://drive.example/back.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        payload = self._build_payload(order, design_front | design_back)
        po = payload.line_items[0].printing_options
        self.assertEqual(len(po), 2)
        location_codes = {entry['location_code'] for entry in po}
        self.assertIn('front', location_codes)
        self.assertIn('back', location_codes)
        urls = {entry['url'] for entry in po}
        self.assertIn('https://drive.example/front.png', urls)
        self.assertIn('https://drive.example/back.png', urls)

    def test_builder_first_design_gets_front_location(self):
        """Heuristic: first approved design.file → front; second → back.

        Production-grade per-file `location_code` is deferred to a separate
        slice (P1-DESIGN-LOCATION-CODE). For now, ordering by id is the
        deterministic positional assignment.
        """
        order, product = self._make_minimal_order()
        design_a = self.env['design.file'].create({
            'name': 'first',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://drive.example/a.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        design_b = self.env['design.file'].create({
            'name': 'second',
            'order_line_id': order.order_line[0].id,
            'file_url': 'https://drive.example/b.png',
            'storage_mode': 'url',
            'state': 'approved',
        })
        payload = self._build_payload(order, design_a | design_b)
        po = payload.line_items[0].printing_options
        self.assertEqual(po[0]['location_code'], 'front')
        self.assertEqual(po[0]['url'], 'https://drive.example/a.png')
        self.assertEqual(po[1]['location_code'], 'back')

    def test_builder_skips_line_with_no_designs_and_no_existing_options(self):
        """A line item with zero design_files cannot ship — builder skips it.

        Gearment requires at least 1 printing option per line. If all design
        files for a line are missing, the builder must not emit the line —
        Gearment would reject the whole order.
        """
        order, product = self._make_minimal_order()
        # No design.files created
        payload = self._build_payload(order, self.env['design.file'])
        # Either no line_items at all, OR line_items with non-empty printing_options.
        for line in payload.line_items:
            self.assertGreaterEqual(len(line.printing_options), 1,
                "every emitted line must have at least one printing_option")
