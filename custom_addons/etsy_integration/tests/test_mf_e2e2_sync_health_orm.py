"""MF-E2E-2 Phase 2 ORM — sync-health rows for BOTH order-ingest paths.

Spec 015 MF-E2E-2 exit criterion: 'sync-health rows written for both paths'.
Neither `_cron_sync_orders` (API receipts) nor `_cron_fetch_etsy_emails`
(email fallback) reported to `etsy.sync.health` before 2026-07-04 — only the
import/migration wizards did. These tests pin the new contract:

- API cron upserts `etsy_api_receipts_sync` (ok / error aggregate).
- Email cron upserts `etsy_email_fetch` on every attempted cycle,
  including the no-new-emails early return; Gmail auth failure → error.
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module

_FAKE_CREDS = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestSyncHealthBothPaths(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE_CREDS)
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.Health = cls.env['etsy.sync.health']

    def _health(self, name):
        return self.Health.search([('name', '=', name)], limit=1)

    def _make_api_shop(self):
        return self.env['etsy.shop'].create({
            'name': 'HealthShop',
            'sync_mode': 'api_only',
            'active_source': 'api',
            'etsy_api_shop_id': '55555550',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def test_api_cron_reports_health_row(self):
        self._make_api_shop()
        with patch.object(
            eac_module.EtsyApiClient, 'get',
            return_value={'count': 0, 'results': []},
        ):
            self.env['etsy.shop']._cron_sync_orders()
        row = self._health('etsy_api_receipts_sync')
        self.assertTrue(row, 'API receipts cron must upsert a sync-health row')
        self.assertEqual(row.state, 'ok')
        self.assertTrue(row.last_run_at)

    def test_api_cron_reports_error_state_on_shop_failure(self):
        self._make_api_shop()
        with patch.object(
            eac_module.EtsyApiClient, 'get',
            side_effect=ValueError('boom'),
        ):
            self.env['etsy.shop']._cron_sync_orders()
        row = self._health('etsy_api_receipts_sync')
        self.assertTrue(row)
        self.assertEqual(row.state, 'error')
        self.assertGreaterEqual(row.last_run_error_count, 1)

    def _email_icp(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('etsy_integration.gmail_client_id', 'gid')
        ICP.set_param('etsy_integration.gmail_client_secret', 'gsec')
        ICP.set_param('etsy_integration.gmail_refresh_token', 'gref')

    def test_email_cron_reports_ok_row_even_with_no_new_emails(self):
        self._email_icp()
        gmail = MagicMock()
        gmail.authenticate.return_value = True
        gmail.fetch_labeled_emails.return_value = []
        with patch(
            'odoo.addons.etsy_integration.services.gmail_client.GmailClient',
            return_value=gmail,
        ):
            self.env['sale.order']._cron_fetch_etsy_emails()
        row = self._health('etsy_email_fetch')
        self.assertTrue(row, 'email cron must upsert a sync-health row even '
                             'on the no-new-emails early return')
        self.assertEqual(row.state, 'ok')
        self.assertEqual(row.last_run_row_count, 0)

    def test_email_cron_reports_error_on_gmail_auth_failure(self):
        self._email_icp()
        gmail = MagicMock()
        gmail.authenticate.return_value = False
        with patch(
            'odoo.addons.etsy_integration.services.gmail_client.GmailClient',
            return_value=gmail,
        ):
            self.env['sale.order']._cron_fetch_etsy_emails()
        row = self._health('etsy_email_fetch')
        self.assertTrue(row)
        self.assertEqual(row.state, 'error')
