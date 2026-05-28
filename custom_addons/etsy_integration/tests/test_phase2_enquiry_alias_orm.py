"""Phase 2 ORM tests for P3-LEAD-MAIL-ALIAS etsy.shop side."""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestEtsyShopEnquiryAlias(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'ALIAS TEST SHOP',
            'sync_mode': 'email_only',
            'etsy_api_shop_id': '11111111',
        })
        cls.plain = new_test_user(
            cls.env, login='alias_test_plain', groups='base.group_user',
        )

    def test_provision_creates_alias(self):
        alias = self.shop.action_provision_enquiry_alias()
        self.assertTrue(alias)
        self.assertEqual(alias._name, 'mail.alias')
        self.assertEqual(alias.alias_model_id.model, 'multichannel.enquiry')
        self.shop.invalidate_recordset()
        self.assertEqual(self.shop.enquiry_alias_id, alias)

    def test_provision_idempotent(self):
        a = self.shop.action_provision_enquiry_alias()
        b = self.shop.action_provision_enquiry_alias()
        self.assertEqual(a, b, "Second call must return same alias")

    def test_non_admin_blocked(self):
        with self.assertRaises(AccessError):
            self.shop.with_user(self.plain).action_provision_enquiry_alias()
