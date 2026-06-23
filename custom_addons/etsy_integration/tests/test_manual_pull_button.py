from unittest import mock

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestManualPullButtonPhase1(TransactionCase):

    def test_quotation_list_arch_contains_pull_button(self):
        view = self.env.ref(
            'etsy_integration.view_quotation_tree_with_onboarding_etsy_pull')
        self.assertIn('action_pull_etsy_orders', view.arch)


@tagged('post_install', '-at_install')
class TestManualPullButtonPhase2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._user('etsy_pull_user')
        cls.other_user = cls._user('etsy_pull_other')
        cls.admin = cls._user(
            'etsy_pull_admin',
            extra_groups=['base.group_system'],
        )
        cls.shop_user = cls._api_shop('Pull User', cls.user, '910001')
        cls.shop_other = cls._api_shop('Pull Other', cls.other_user, '910002')
        cls.email_shop = cls.env['etsy.shop'].sudo().create({
            'name': 'Pull Email',
            'user_id': cls.user.id,
            'active_source': 'email',
        })

    @classmethod
    def _user(cls, login, extra_groups=None):
        groups = [cls.env.ref('base.group_user').id]
        for xmlid in extra_groups or []:
            groups.append(cls.env.ref(xmlid).id)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [(6, 0, groups)],
        })

    @classmethod
    def _api_shop(cls, name, user, api_shop_id):
        return cls.env['etsy.shop'].sudo().create({
            'name': name,
            'user_id': user.id,
            'active_source': 'api',
            'etsy_api_shop_id': api_shop_id,
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'refresh',
        })

    def _run_with_mock(self, user):
        calls = []

        def fake_sync(syncer, shop):
            calls.append(shop.id)
            return {'ingested': 1, 'audited': 2, 'errors': 0}

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_order_syncer.'
            'EtsyOrderSyncer.sync_shop_orders',
            autospec=True,
            side_effect=fake_sync,
        ):
            action = self.env['sale.order'].with_user(user).action_pull_etsy_orders()
        return action, calls

    def test_admin_resolves_all_api_shops(self):
        action, calls = self._run_with_mock(self.admin)
        self.assertEqual(set(calls), {self.shop_user.id, self.shop_other.id})
        self.assertEqual(action['params']['type'], 'success')

    def test_scoped_user_resolves_only_own_api_shops(self):
        _action, calls = self._run_with_mock(self.user)
        self.assertEqual(calls, [self.shop_user.id])

    def test_no_shop_user_gets_notification_without_sync(self):
        user = self._user('etsy_pull_none')
        action, calls = self._run_with_mock(user)
        self.assertEqual(calls, [])
        self.assertEqual(action['params']['type'], 'warning')
        self.assertIn('No Etsy shops assigned', action['params']['message'])
