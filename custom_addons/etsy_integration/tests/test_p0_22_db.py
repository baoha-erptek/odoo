"""P0-22 Phase 1 DB introspection — schema verification for the 9 parity fields.

Each parity field already exists on `sale.order` / `sale.order.line` (verified
in the slice plan). This test file is the schema contract — if a future
refactor drops one of these fields, the symmetry between API and email ingest
paths breaks silently. Phase 1 DB pins the schema.

Reference: `specs/005-etsy-api-channel/p0-22-plan.md` §2.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'p0_22')
class TestP022SaleOrderFieldsExist(TransactionCase):

    def test_etsy_shipping_service_field_exists(self):
        self.assertIn('etsy_shipping_service', self.env['sale.order']._fields)

    def test_etsy_processing_time_field_exists(self):
        self.assertIn('etsy_processing_time', self.env['sale.order']._fields)

    def test_etsy_discount_code_field_exists(self):
        self.assertIn('etsy_discount_code', self.env['sale.order']._fields)

    def test_etsy_subtotal_field_exists(self):
        self.assertIn('etsy_subtotal', self.env['sale.order']._fields)

    def test_payment_status_field_exists(self):
        self.assertIn('payment_status', self.env['sale.order']._fields)

    def test_etsy_last_modified_field_exists(self):
        self.assertIn('etsy_last_modified', self.env['sale.order']._fields)

    def test_sync_source_field_exists(self):
        self.assertIn('sync_source', self.env['sale.order']._fields)

    def test_etsy_raw_source_id_field_exists(self):
        self.assertIn('etsy_raw_source_id', self.env['sale.order']._fields)


@tagged('post_install', '-at_install', 'p0_22')
class TestP022SaleOrderLineFieldsExist(TransactionCase):

    def test_etsy_transaction_id_field_exists(self):
        self.assertIn('etsy_transaction_id', self.env['sale.order.line']._fields)

    def test_etsy_personalisation_field_exists(self):
        self.assertIn('etsy_personalisation', self.env['sale.order.line']._fields)

    def test_etsy_sku_field_exists(self):
        self.assertIn('etsy_sku', self.env['sale.order.line']._fields)


@tagged('post_install', '-at_install', 'p0_22')
class TestP022FieldReadonlyContract(TransactionCase):
    """Adapter-owned fields must be readonly at the form level — operators
    cannot edit the cached Etsy state through the UI; only the ingestor writes.
    """

    def test_payment_status_is_readonly(self):
        self.assertTrue(
            self.env['sale.order']._fields['payment_status'].readonly,
            'payment_status must be readonly=True (FR-009 — adapter-owned)',
        )

    def test_etsy_last_modified_is_readonly(self):
        self.assertTrue(
            self.env['sale.order']._fields['etsy_last_modified'].readonly,
            'etsy_last_modified must be readonly=True (FR-009 — adapter-owned)',
        )
