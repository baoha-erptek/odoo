"""P2-02 Phase 2 — ORM tests for carrier auto-detection service + bulk action."""
import json

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..services.carrier_detector import detect_carrier


# Real USPS Priority Mail tracking format (22 digits starting with 9).
_USPS_REAL = '9214090199870080089007'
_UNIUNI_REAL = 'UUS123ABC456DEF'
_YT_REAL = 'YT2024010100001'
_UNKNOWN = 'XX-NOT-A-REAL-TRACKING-001'


@tagged('post_install', '-at_install')
class TestCarrierDetector(TransactionCase):

    def setUp(self):
        super().setUp()
        self.usps = self.env.ref('multichannel_hub_core.shipping_carrier_usps')
        self.uniuni = self.env.ref('multichannel_hub_core.shipping_carrier_uniuni')
        self.yt = self.env.ref('multichannel_hub_core.shipping_carrier_yunexpress')
        self.other = self.env.ref('multichannel_hub_core.shipping_carrier_other')

    def test_usps_match(self):
        carrier, needs_review = detect_carrier(self.env, _USPS_REAL)
        self.assertEqual(carrier, self.usps)
        self.assertFalse(needs_review)

    def test_uniuni_match(self):
        carrier, needs_review = detect_carrier(self.env, _UNIUNI_REAL)
        self.assertEqual(carrier, self.uniuni)
        self.assertFalse(needs_review)

    def test_yunexpress_match(self):
        carrier, needs_review = detect_carrier(self.env, _YT_REAL)
        self.assertEqual(carrier, self.yt)
        self.assertFalse(needs_review)

    def test_unknown_falls_back_to_other(self):
        carrier, needs_review = detect_carrier(self.env, _UNKNOWN)
        self.assertEqual(carrier, self.other)
        self.assertTrue(needs_review)

    def test_empty_tracking_returns_no_carrier(self):
        carrier, needs_review = detect_carrier(self.env, '')
        self.assertFalse(carrier)
        self.assertTrue(needs_review)
        carrier2, nr2 = detect_carrier(self.env, None)
        self.assertFalse(carrier2)
        self.assertTrue(nr2)

    def test_inactive_carrier_skipped(self):
        self.uniuni.is_active = False
        try:
            carrier, _ = detect_carrier(self.env, _UNIUNI_REAL)
            # UniUni inactive → falls back to 'other'.
            self.assertEqual(carrier, self.other)
        finally:
            self.uniuni.is_active = True

    def test_sequence_priority_on_overlap(self):
        # Add a high-priority carrier with a regex that ALSO matches USPS.
        usps_clone = self.env['shipping.carrier'].create({
            'name': 'USPS Priority (test)',
            'code': 'usps_priority_test',
            'sequence': 5,  # lower sequence = higher priority
            'is_active': True,
            'tracking_prefix_regex': r'^9214[0-9]+$',
        })
        try:
            carrier, _ = detect_carrier(self.env, _USPS_REAL)
            self.assertEqual(
                carrier, usps_clone,
                "Lower-sequence carrier must win on overlap")
        finally:
            usps_clone.unlink()

    def test_regex_constraint_rejects_empty_match(self):
        with self.assertRaises(ValidationError):
            self.env['shipping.carrier'].create({
                'name': 'Bad Regex',
                'code': 'bad_regex',
                'tracking_prefix_regex': r'.*',
            })

    def test_regex_constraint_rejects_invalid_pattern(self):
        with self.assertRaises(ValidationError):
            self.env['shipping.carrier'].create({
                'name': 'Bad Regex 2',
                'code': 'bad_regex_2',
                'tracking_prefix_regex': r'(unclosed[group',
            })


@tagged('post_install', '-at_install')
class TestRedetectAction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.usps = cls.env.ref('multichannel_hub_core.shipping_carrier_usps')
        cls.other = cls.env.ref('multichannel_hub_core.shipping_carrier_other')
        cls.ba_shipping_group = cls.env.ref(
            'multichannel_hub_fulfillment.group_ba_shipping')
        cls.ba_user = cls.env['res.users'].create({
            'name': 'BA Shipping User RD',
            'login': 'ba_rd@test.com',
            'email': 'ba_rd@test.com',
            'group_ids': [(6, 0, [cls.ba_shipping_group.id])],
        })
        cls.regular_user = cls.env['res.users'].create({
            'name': 'Regular User RD',
            'login': 'regular_rd@test.com',
            'email': 'regular_rd@test.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.log = cls.env['tracking.import.log'].create({
            'filename': 'rd.xlsx',
            'file_size_bytes': 100,
            'schema_hash': 'rd-test-hash',
            'header_columns': '[]',
            'state': 'pending',
        })

    def _make_line(self, *, tracking, carrier=False, needs_review=True,
                   row_number=1, source_row_hash=None):
        return self.env['tracking.import.line'].create({
            'log_id': self.log.id,
            'row_number': row_number,
            'source_row_hash': source_row_hash or f'rd-hash-{row_number}',
            'state': 'pending',
            'raw_order_number': 'X',
            'raw_tracking_number': tracking,
            'raw_payload': json.dumps({}),
            'detected_carrier_id': carrier.id if carrier else False,
            'needs_review': needs_review,
        })

    def test_redetect_updates_lines(self):
        line = self._make_line(tracking=_USPS_REAL,
                               carrier=self.other, needs_review=True,
                               row_number=10, source_row_hash='rd-up-1')
        line.with_user(self.ba_user).action_re_detect_carriers()
        self.assertEqual(line.detected_carrier_id, self.usps)
        self.assertFalse(line.needs_review)

    def test_redetect_falls_back_to_other_on_unknown(self):
        line = self._make_line(tracking=_UNKNOWN,
                               carrier=self.usps, needs_review=False,
                               row_number=11, source_row_hash='rd-fb-1')
        line.with_user(self.ba_user).action_re_detect_carriers()
        self.assertEqual(line.detected_carrier_id, self.other)
        self.assertTrue(line.needs_review)

    def test_redetect_gated_to_ba_shipping(self):
        line = self._make_line(tracking=_USPS_REAL,
                               row_number=12, source_row_hash='rd-acl-1')
        with self.assertRaises(AccessError):
            line.with_user(self.regular_user).action_re_detect_carriers()
