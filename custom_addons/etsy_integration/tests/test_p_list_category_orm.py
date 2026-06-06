"""Phase 2 ORM tests for P-LIST-CATEGORY (Wave 2 / Jira ESTY-189).

Covers:
- etsy.taxonomy.node cache model — create + UNIQUE etsy_id + full_path compute.
- etsy_taxonomy_syncer.sync_taxonomy() flat upsert + parent wiring.
- EtsyListingPublisher._resolve_taxonomy_id fallback chain
  (listing → product fallback → shop default → UserError).
"""

from unittest.mock import patch, MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services import etsy_api_client as eac_module
from odoo.addons.etsy_integration.services.etsy_taxonomy_syncer import (
    sync_taxonomy, _flatten,
)
from odoo.addons.etsy_integration.services.etsy_listing_publisher import (
    EtsyListingPublisher,
)


_FAKE = {'client_id': 'kid', 'client_secret': 'sec'}


@tagged('post_install', '-at_install')
class TestTaxonomyCacheModel(TransactionCase):

    def test_unique_etsy_id_enforced(self):
        Node = self.env['etsy.taxonomy.node']
        Node.create({'etsy_id': '1', 'name': 'A', 'level': 0})
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Node.create({'etsy_id': '1', 'name': 'A dup', 'level': 0})

    def test_full_path_compute_with_parent(self):
        Node = self.env['etsy.taxonomy.node']
        root = Node.create({'etsy_id': '10', 'name': 'Home', 'level': 0})
        child = Node.create({
            'etsy_id': '11', 'name': 'Kitchen', 'level': 1,
            'parent_id': root.id,
        })
        leaf = Node.create({
            'etsy_id': '12', 'name': 'Cookware', 'level': 2,
            'parent_id': child.id,
        })
        self.assertEqual(leaf.full_path, 'Home / Kitchen / Cookware')


@tagged('post_install', '-at_install')
class TestTaxonomySyncer(TransactionCase):

    def _shop(self):
        return self.env['etsy.shop'].create({
            'name': 'PLC TEST',
            'etsy_api_shop_id': '9000001',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        })

    def test_flatten_recursive_tree(self):
        nodes = [
            {'id': 1, 'name': 'Home', 'children': [
                {'id': 11, 'name': 'Kitchen', 'children': [
                    {'id': 111, 'name': 'Cookware'},
                ]},
                {'id': 12, 'name': 'Bath'},
            ]},
            {'id': 2, 'name': 'Apparel'},
        ]
        flat = _flatten(nodes)
        self.assertEqual(len(flat), 5)
        # Check parent ids
        m = {etsy_id: parent_etsy_id for etsy_id, _n, parent_etsy_id, _l in flat}
        self.assertIsNone(m['1'])
        self.assertEqual(m['11'], '1')
        self.assertEqual(m['111'], '11')
        self.assertIsNone(m['2'])

    def test_sync_taxonomy_creates_and_wires_parents(self):
        shop = self._shop()
        fake_client = MagicMock()
        fake_client.get.return_value = {
            'results': [
                {'id': 100, 'name': 'Top', 'children': [
                    {'id': 101, 'name': 'Mid', 'children': [
                        {'id': 102, 'name': 'Leaf'},
                    ]},
                ]},
            ]
        }
        created, updated = sync_taxonomy(self.env, shop, client=fake_client)
        self.assertEqual(created, 3)
        self.assertEqual(updated, 0)
        leaf = self.env['etsy.taxonomy.node'].search(
            [('etsy_id', '=', '102')], limit=1)
        self.assertTrue(leaf)
        self.assertEqual(leaf.full_path, 'Top / Mid / Leaf')
        # Second run is idempotent (updated, not created)
        created2, updated2 = sync_taxonomy(self.env, shop, client=fake_client)
        self.assertEqual(created2, 0)
        self.assertEqual(updated2, 3)


@tagged('post_install', '-at_install')
class TestResolveTaxonomyId(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._creds = patch.object(
            eac_module, '_read_credentials', return_value=_FAKE,
        )
        cls._creds.start()
        cls.addClassCleanup(cls._creds.stop)
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')

    def _shop(self, **overrides):
        vals = {
            'name': 'PLC TEST',
            'etsy_api_shop_id': '9000002',
            'sync_mode': 'email_only',
            'etsy_oauth_access_token': 'tok',
            'etsy_oauth_refresh_token': 'ref',
            'etsy_oauth_token_expires_at': '2099-12-31 00:00:00',
        }
        vals.update(overrides)
        return self.env['etsy.shop'].create(vals)

    def test_listing_override_wins(self):
        shop = self._shop(default_taxonomy_id='5000')
        tmpl = self.env['product.template'].create({
            'name': 'TaxOverride', 'list_price': 1.0, 'x_taxonomy_id': 6000,
        })
        node = self.env['etsy.taxonomy.node'].create({
            'etsy_id': '4242', 'name': 'Pillows', 'level': 1,
        })
        self.env['multichannel.listing'].sudo().create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.channel.id,
            'etsy_taxonomy_id': node.id,
        })
        publisher = EtsyListingPublisher(self.env)
        self.assertEqual(publisher._resolve_taxonomy_id(tmpl, shop), 4242)

    def test_falls_through_to_product_then_shop(self):
        shop = self._shop(default_taxonomy_id='5000')
        tmpl = self.env['product.template'].create({
            'name': 'TaxNoOverride', 'list_price': 1.0, 'x_taxonomy_id': 6000,
        })
        publisher = EtsyListingPublisher(self.env)
        # No listing intent → product fallback
        self.assertEqual(publisher._resolve_taxonomy_id(tmpl, shop), 6000)
        # Clear product fallback → shop default
        tmpl.x_taxonomy_id = False
        self.assertEqual(publisher._resolve_taxonomy_id(tmpl, shop), 5000)

    def test_soft_fallback_to_zero_when_nothing_set(self):
        """Pre-slice behavior: 0 propagates to Etsy which 400s. Future
        hardening slice will raise UserError when shop default is
        guaranteed present."""
        shop = self._shop(default_taxonomy_id=False)
        tmpl = self.env['product.template'].create({
            'name': 'TaxEmpty', 'list_price': 1.0,
        })
        publisher = EtsyListingPublisher(self.env)
        self.assertEqual(publisher._resolve_taxonomy_id(tmpl, shop), 0)
