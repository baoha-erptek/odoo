"""Unit tests for scripts/_sku_classifier.py.

No Odoo dependency — pure pytest. Run via::

    python3 -m pytest scripts/tests/test_sku_classifier.py -v

Two test families:
1. **Drift guard** vs `custom_addons/multichannel_hub_core/data/sku_family_seed.xml` —
   asserts the English regex table is byte-identical to the live seed so
   classifier output cannot silently diverge from the live mhc.sku.family
   model. Edit the seed → re-run tests → re-extract the table.
2. **Behavioural** — classify representative product names from the owner's
   actual inventory file + the v2.1 SKU validator.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _sku_classifier import (  # noqa: E402
    _ENGLISH_FAMILIES,
    MSC,
    classify,
    validate_v2_sku,
)


SEED_XML = (
    Path(__file__).resolve().parents[2]
    / 'custom_addons'
    / 'multichannel_hub_core'
    / 'data'
    / 'sku_family_seed.xml'
)


def _parse_seed_rows() -> list[tuple[str, int, str]]:
    """Extract (code, priority, regex_pattern) tuples from the seed XML."""
    tree = ET.parse(SEED_XML)
    rows: list[tuple[str, int, str]] = []
    for record in tree.iter('record'):
        if record.get('model') != 'mhc.sku.family':
            continue
        fields = {f.get('name'): (f.text or '') for f in record.findall('field')}
        rows.append((fields['code'], int(fields['priority']), fields['regex_pattern']))
    return sorted(rows, key=lambda r: r[1])


def test_no_drift_vs_seed_xml() -> None:
    """Classifier table is byte-identical to live mhc.sku.family seed."""
    expected = _parse_seed_rows()
    actual = sorted(_ENGLISH_FAMILIES, key=lambda r: r[1])
    assert actual == expected, (
        'Drift detected vs sku_family_seed.xml — re-extract _ENGLISH_FAMILIES '
        'in scripts/_sku_classifier.py to match the live seed.'
    )


@pytest.mark.parametrize(
    ('name', 'expected_fam'),
    [
        # English happy paths (subset of the 22-family table)
        ('Ceramic Ring Dish', 'RDS'),
        ('Wooden Cutting Board', 'CBD'),
        ('Coffee Mug', 'MUG'),
        ('Personalized Apron', 'APR'),
        ('Doormat for Front Door', 'DMT'),
        ('Memorial Picture Frame', 'PHF'),
        ('Wedding Gift Box', 'KSK'),
        # Vietnamese hints from owner's inventory file
        ('Đĩa bèo', 'CDS'),
        ('Đĩa vuông nhỏ', 'CDS'),
        ('Đĩa tròn cũ', 'CDS'),
        ('Tạp dề đen trơn', 'APR'),
        ('Khăn lau đĩa', 'KCH'),
        ('RCD style A - 6 inches', 'RDS'),
        # MSC fallback for un-classifiable items (packaging supplies)
        ('Băng keo trong', MSC),
        ('Bông gòn', MSC),
        ('Xốp chống sốc gói hàng', MSC),
        ('Kéo', MSC),
        # Empty / whitespace
        ('', MSC),
        ('   ', MSC),
    ],
)
def test_classify_examples(name: str, expected_fam: str) -> None:
    assert classify(name) == expected_fam


@pytest.mark.parametrize(
    ('sku', 'valid'),
    [
        ('MUG-CR-F11', True),
        ('MUG-CR-F15-BK', True),
        ('RDS-CE-SQ', True),
        ('APR-TX-AM', True),
        ('DMT-TX-R30X18', True),
        ('CDS-MX-S001', True),  # MSC-style generic-size fallback used by import script
        ('mug-cr-f11', False),  # uppercase required
        ('TOOLONG-CR-F11-BK', False),  # exceeds 14 chars
        ('MUG-CR', False),      # missing SIZE
        ('', False),
    ],
)
def test_validate_v2_sku(sku: str, valid: bool) -> None:
    assert validate_v2_sku(sku) is valid


def test_priority_order_respected_for_english() -> None:
    """`Ring dish` should match RDS (priority 1) not CDS (priority 21).

    Both regex match this string; the lower-priority family wins.
    """
    assert classify('Ceramic Ring Dish') == 'RDS'


def test_vietnamese_longest_keyword_wins() -> None:
    """`Đĩa gỗ` should match WDS not generic CDS (longer keyword)."""
    assert classify('Đĩa gỗ tròn') == 'WDS'
