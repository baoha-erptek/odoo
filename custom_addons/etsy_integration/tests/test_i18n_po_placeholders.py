"""Regression: vi.po %-placeholders must survive translation intact.

2026-07-06 (FLW E2E rerun defect): the vi.po msgstr for
"Address change approved by %(user)s..." line-wrapped INSIDE the
%(fields)s placeholder, injecting a literal newline between "%(fields)"
and "s" — action_approve then crashed with
"ValueError: unsupported format character" for every vi_VN user.
A second entry ("Pulled Etsy orders...") had the same break inside
%(errors)s. This test fails on ANY msgstr whose named placeholders do
not match its msgid, across all custom-addon vi.po files.
"""
import re
from pathlib import Path

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

# Full named-placeholder token, incl. precision forms like %(size).1f
# and repr forms like %(tag)r.
_PLACEHOLDER = re.compile(r'%\(([^)]+)\)[#0\- +]?[\d.]*[sdifr]')
# A '%(' that is NOT followed by a valid terminator = broken placeholder.
_BROKEN = re.compile(r'%\([^)]*\)(?![#0\- +]?[\d.]*[sdifr])')

_MODULES = (
    'etsy_integration',
    'multichannel_hub_core',
    'multichannel_hub_fulfillment',
)


@tagged('post_install', '-at_install', 'i18n_po_placeholders')
class TestViPoPlaceholders(TransactionCase):

    def test_vi_po_placeholders_match_msgid(self):
        addons_root = Path(__file__).resolve().parents[2]
        problems = []
        for module in _MODULES:
            po_path = addons_root / module / 'i18n' / 'vi.po'
            if not po_path.exists():
                continue
            with po_path.open('rb') as handle:
                for row in PoFileReader(handle):
                    src, value = row.get('src') or '', row.get('value') or ''
                    if not value:
                        continue
                    src_names = sorted(_PLACEHOLDER.findall(src))
                    dst_names = sorted(_PLACEHOLDER.findall(value))
                    if src_names != dst_names:
                        problems.append(
                            '%s: %r -> %r (placeholders %s != %s)'
                            % (module, src[:60], value[:80],
                               src_names, dst_names))
                    elif _BROKEN.search(value):
                        problems.append(
                            '%s: broken placeholder in %r'
                            % (module, value[:80]))
        self.assertFalse(
            problems,
            'vi.po placeholder drift (crashes %%-format at runtime):\n'
            + '\n'.join(problems))
