"""Pure-Python SKU family classifier shim.

Mirrors `multichannel_hub_core.services.sku_grammar_v2.evaluate(name, env)`
name-regex path WITHOUT requiring an Odoo environment, so that one-off
data-prep scripts can pre-compute `default_code` before handing XLSX to
the standard Odoo `base_import` UI (onchange / compute methods are
UI-only and do not fire for `base_import`).

Drift control:
- `_ENGLISH_FAMILIES` is copied verbatim from
  `custom_addons/multichannel_hub_core/data/sku_family_seed.xml`.
  When that seed is edited, this table must be re-extracted.
  `scripts/tests/test_sku_classifier.py::test_no_drift_vs_seed_xml`
  parses the seed XML and asserts byte-identical regex strings + priorities.
- `_VIETNAMESE_HINTS` is project-specific (owner inventory file is in
  Vietnamese) and has no counterpart in the seed; it is documented
  in `docs/owner/INVENTORY_SETUP_VN.md`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

MSC: Final[str] = 'MSC'


@dataclass(frozen=True)
class FamilyRule:
    code: str
    priority: int
    pattern: re.Pattern[str]


# --- English regex table (extracted from sku_family_seed.xml) -------------
_ENGLISH_FAMILIES: Final[tuple[tuple[str, int, str], ...]] = (
    ('RDS', 1, r'\bring\b.{0,20}\b(dish|holder|tray)\b'),
    ('TRK', 2, r'\b(trinket|keepsake)\s+(tray|box|dish|holder)\b'),
    ('JWD', 3, r'\bjewel(ry|lery)\s+(dish|holder|tray|box)\b'),
    ('PHF', 4, r'\b(photo|picture|memorial)\s+frame\b'),
    ('CBD', 5, r'\b(cutting\s+board|charcuterie)\b'),
    ('WCH', 6, r'\bwind\s*chime\b|\bchime\b'),
    ('MUG', 7, r'\bmug\b'),
    ('TUM', 8, r'\btumbler\b'),
    ('TAT', 9, r'\btemporary\b.*\btattoo\b|\btattoo(s)?\b'),
    ('DMT', 10, r'\b(doormat|door\s+mat)\b'),
    ('RUG', 11, r'(?<!door[\s-])\brug(s)?\b'),
    ('ORN', 12, r'\bornament(s)?\b'),
    ('HKF', 13, r'\bhand(ker)?chief\b|\bhankie\b|\bhanky\b'),
    ('APR', 14, r'\bapron(s)?\b'),
    ('PIL', 15, r'\b(pillow|cushion|pillowcase)\b'),
    ('BAG', 16, r'\b(tote|canvas\s+bag|bandana|backpack|duffel)\b'),
    ('SGN', 17, r'\b(metal\s+sign|wood(en)?\s+sign|yard\s+sign|flag|banner)\b'),
    ('KCH', 18, r'\b(recipe\s+dish|recipe\s+holder|spoon\s+holder|kitchen\s+towel)\b'),
    ('APP', 19, r'\b(t-?shirt|hoodie|tank\s+top|sweatshirt|tee|sleep\s*shirt|sleepshirt|sweater)\b'),
    ('KSK', 20, r'\b(keepsake|wedding\s+gift|proposal\s+gift|sympathy\s+gift|memorial\s+gift)\b'),
    ('CDS', 21, r'\bceramic\s+(dish|plate|bowl)\b|\bceramic\b'),
    ('WDS', 22, r'\bwooden\s+(dish|plate|bowl)\b|\bwood(en)?\b'),
)


# --- Vietnamese keyword hints (project-specific) --------------------------
# Owner's inventory file uses Vietnamese product names. These hints map
# Vietnamese keywords (after diacritic-stripping + lowercasing) to the
# same 3-letter FAM3 codes from the English table. The hint with the
# longest matching keyword wins; ties broken by family priority.
#
# Maintenance note: this table is curated from the actual 133-row owner
# inventory; not exhaustive. Un-matched names fall back to MSC (the
# owner can refine the SKU column in the generated XLSX before import).
_VIETNAMESE_HINTS: Final[tuple[tuple[str, str], ...]] = (
    # (keyword without diacritics, lowercased, FAM3 code)
    ('dia ceramic', 'CDS'),
    ('dia su', 'CDS'),       # đĩa sứ = porcelain dish
    ('dia gom', 'CDS'),      # đĩa gốm = ceramic dish
    ('dia go', 'WDS'),       # đĩa gỗ = wooden dish
    ('dia', 'CDS'),          # đĩa generic → default ceramic dish (most owner SKUs are ceramic)
    ('tap de', 'APR'),       # tạp dề = apron
    ('khan', 'KCH'),         # khăn lau = cloth (kitchen)
    ('ly', 'MUG'),           # ly = glass/mug
    ('cup', 'MUG'),
    ('coc', 'MUG'),          # cốc = mug
    ('mug', 'MUG'),
    ('tham', 'RUG'),         # thảm = rug
    ('doormat', 'DMT'),
    ('go khac', 'CBD'),      # gỗ khắc = engraved wood (cutting board family)
    ('khung anh', 'PHF'),    # khung ảnh = picture frame
    ('khung hinh', 'PHF'),
    ('chuong gio', 'WCH'),   # chuông gió = wind chime
    ('hop trang suc', 'JWD'),  # hộp trang sức = jewelry box
    ('hop nhan', 'RDS'),     # hộp nhẫn = ring box
    ('hop', 'TRK'),          # hộp generic → trinket box
    ('tui', 'BAG'),          # túi = bag
    ('ao', 'APP'),           # áo = shirt/clothing
    ('rcd', 'RDS'),          # explicit RCD style codes in owner data
    ('ring dish', 'RDS'),
)


def _strip_diacritics(text: str) -> str:
    """Lowercase + remove Vietnamese diacritics for fuzzy keyword match."""
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_only = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    return ascii_only.replace('đ', 'd').replace('Đ', 'd').lower()


def _compile_rules() -> list[FamilyRule]:
    rules: list[FamilyRule] = []
    for code, priority, pattern in _ENGLISH_FAMILIES:
        rules.append(FamilyRule(code, priority, re.compile(pattern, re.IGNORECASE)))
    return rules


_COMPILED_RULES: Final[list[FamilyRule]] = sorted(
    _compile_rules(), key=lambda r: (r.priority, r.code)
)


def classify(name: str) -> str:
    """Return 3-letter FAM3 family code, or 'MSC' on no match.

    Priority order:
    1. English regex (mirrors live `mhc.sku.family` evaluation).
    2. Vietnamese keyword hint (longest keyword wins; tie → priority).
    3. MSC fallback.
    """
    if not name or not name.strip():
        return MSC

    for rule in _COMPILED_RULES:
        if rule.pattern.search(name):
            return rule.code

    normalised = _strip_diacritics(name)
    best: tuple[int, int, str] | None = None  # (keyword_len, -priority, code)
    priority_by_code = {code: prio for code, prio, _ in _ENGLISH_FAMILIES}
    for keyword, code in _VIETNAMESE_HINTS:
        if keyword in normalised:
            prio = priority_by_code.get(code, 999)
            candidate = (len(keyword), -prio, code)
            if best is None or candidate > best:
                best = candidate

    return best[2] if best else MSC


# --- v2.1 SKU shape validator (kept in sync with services/sku_grammar_v2.py) ---
_VALIDATOR_REGEX: Final[re.Pattern[str]] = re.compile(
    r'^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)(-[A-Z]{2})?$'
)


def validate_v2_sku(default_code: str) -> bool:
    """Return True iff `default_code` matches SKU Grammar v2.1 §7.1."""
    if not default_code:
        return False
    n = len(default_code)
    if n < 8 or n > 14:
        return False
    return bool(_VALIDATOR_REGEX.match(default_code))
