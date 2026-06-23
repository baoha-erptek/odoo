from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestShopUserScopingPhase1(TransactionCase):

    def test_user_id_column_exists(self):
        self.env.cr.execute("""
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'etsy_shop' AND column_name = 'user_id'
        """)
        self.assertEqual(self.env.cr.fetchone()[0], 'integer')

    def test_sale_order_record_rules_present(self):
        restrictive = self.env.ref(
            'etsy_integration.sale_order_etsy_shop_user_scope_rule')
        permissive = self.env.ref(
            'etsy_integration.sale_order_etsy_shop_admin_scope_rule')
        self.assertEqual(
            restrictive.domain_force,
            "['|', ('etsy_shop_id', '=', False), ('etsy_shop_id.user_id', '=', user.id)]",
        )
        self.assertEqual(permissive.domain_force, "[(1, '=', 1)]")
        self.assertIn(self.env.ref('base.group_user'), restrictive.groups)
        self.assertIn(self.env.ref('sales_team.group_sale_manager'), permissive.groups)
        self.assertIn(self.env.ref('base.group_system'), permissive.groups)


@tagged('post_install', '-at_install')
class TestShopUserScopingPhase2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Scoped Buyer'})
        cls.user_a = cls._user('etsy_scope_a')
        cls.user_b = cls._user('etsy_scope_b')
        cls.manager = cls._user(
            'etsy_scope_manager',
            extra_groups=['sales_team.group_sale_manager'],
        )
        cls.system = cls._user(
            'etsy_scope_system',
            extra_groups=['base.group_system'],
        )
        Shop = cls.env['etsy.shop'].sudo()
        cls.shop_a = Shop.create({'name': 'Scope A', 'user_id': cls.user_a.id})
        cls.shop_b = Shop.create({'name': 'Scope B', 'user_id': cls.user_b.id})
        cls.order_a = cls._order('ESTY-SCOPE-A', cls.shop_a)
        cls.order_b = cls._order('ESTY-SCOPE-B', cls.shop_b)
        cls.order_regular = cls._order(False, False)

    @classmethod
    def _user(cls, login, extra_groups=None):
        groups = [
            cls.env.ref('base.group_user').id,
            cls.env.ref('sales_team.group_sale_salesman').id,
        ]
        for xmlid in extra_groups or []:
            groups.append(cls.env.ref(xmlid).id)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [(6, 0, groups)],
        })

    @classmethod
    def _order(cls, etsy_id, shop):
        return cls.env['sale.order'].sudo().create({
            'partner_id': cls.partner.id,
            'etsy_order_id': etsy_id or False,
            'etsy_shop_id': shop.id if shop else False,
        })

    def test_scoped_user_sees_own_etsy_and_non_etsy_orders(self):
        orders = self.env['sale.order'].with_user(self.user_a).search([])
        self.assertIn(self.order_a, orders)
        self.assertIn(self.order_regular, orders)
        self.assertNotIn(self.order_b, orders)

    def test_sale_manager_sees_all(self):
        orders = self.env['sale.order'].with_user(self.manager).search([])
        self.assertTrue(self.order_a | self.order_b | self.order_regular <= orders)

    def test_system_admin_without_sale_manager_sees_all(self):
        self.system.group_ids -= self.env.ref('sales_team.group_sale_manager')
        orders = self.env['sale.order'].with_user(self.system).search([])
        self.assertTrue(self.order_a | self.order_b | self.order_regular <= orders)
