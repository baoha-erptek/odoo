"""Phase 1 DB tests for P0-11 multichannel.sync.health."""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('at_install', '-post_install')
class TestPhase1SyncHealthDB(TransactionCase):

    def test_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='multichannel_sync_health')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_unique_constraint_mirrored(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname='uniq_multichannel_sync_health_channel_metric'
        """)
        self.assertIsNotNone(self.env.cr.fetchone())

    def test_unique_constraint_enforced(self):
        Health = self.env['multichannel.sync.health']
        ChannelAll = self.env['multichannel.sales.channel'].with_context(active_test=False)
        etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        Health.create({'channel_id': etsy.id, 'metric_key': 'dup_test'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Health.create({'channel_id': etsy.id, 'metric_key': 'dup_test'})
