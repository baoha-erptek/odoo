"""SKU grammar v2 — frozen family rules.

Module-load precompiled regex tuple. Evaluates a product name against
the priority-ordered family list from `.0temp/deliverables/A3_grammar_v2_frozen.md`
(canonical source: D1_product_taxonomy_SKU.xlsx `family_rules` sheet).

Returns `(suggested_sku, family_code)` where:
- `suggested_sku` is the 3-letter family code on a match
- `family_code` is the same 3-letter code (`MSC` on fallback)

The DSGN registry (D#### sequential design code) and MAT2/SIZE encoding
are not in scope for P-HUB-PROD-MODEL — they will be derived in later
slices when the publisher service needs full SKU strings.

Spec 009 — P-HUB-PROD-MODEL T005. Source: A3_grammar_v2_frozen.md §1.
"""

import re
from typing import NamedTuple


class FamilyRule(NamedTuple):
    code: str
    pattern: re.Pattern


# Priority-ordered: most-specific first. First-match wins.
# Source: .0temp/deliverables/A3_grammar_v2_frozen.md §1 (table, priorities 1-22).
_RAW_RULES: tuple[tuple[str, str], ...] = (
    ('RDS', r'\bring\b.{0,20}\b(dish|holder|tray)\b'),
    ('TRK', r'\b(trinket|keepsake)\s+(tray|box|dish|holder)\b'),
    ('JWD', r'\bjewel(ry|lery)\s+(dish|holder|tray|box)\b'),
    ('PHF', r'\b(photo|picture|memorial)\s+frame\b'),
    ('CBD', r'\b(cutting\s+board|charcuterie)\b'),
    ('WCH', r'\bwind\s*chime\b|\bchime\b'),
    ('MUG', r'\bmug\b'),
    ('TUM', r'\btumbler\b'),
    ('TAT', r'\btemporary\b.*\btattoo\b|\btattoo(s)?\b'),
    ('DMT', r'\b(doormat|door\s+mat)\b'),
    ('RUG', r'(?<!door[\s-])\brug(s)?\b'),
    ('ORN', r'\bornament(s)?\b'),
    ('HKF', r'\bhand(ker)?chief\b|\bhankie\b|\bhanky\b'),
    ('APR', r'\bapron(s)?\b'),
    ('PIL', r'\b(pillow|cushion|pillowcase)\b'),
    ('BAG', r'\b(tote|canvas\s+bag|bandana|backpack|duffel)\b'),
    ('SGN', r'\b(metal\s+sign|wood(en)?\s+sign|yard\s+sign|flag|banner)\b'),
    ('KCH', r'\b(recipe\s+dish|recipe\s+holder|spoon\s+holder|kitchen\s+towel)\b'),
    ('APP', r'\b(t-?shirt|hoodie|tank\s+top|sweatshirt|tee|sleep\s*shirt|sleepshirt|sweater)\b'),
    ('KSK', r'\b(keepsake|wedding\s+gift|proposal\s+gift|sympathy\s+gift|memorial\s+gift)\b'),
    ('CDS', r'\bceramic\s+(dish|plate|bowl)\b|\bceramic\b'),
    ('WDS', r'\bwooden\s+(dish|plate|bowl)\b|\bwood(en)?\b'),
)

FAMILY_RULES: tuple[FamilyRule, ...] = tuple(
    FamilyRule(code=code, pattern=re.compile(pattern, re.IGNORECASE))
    for code, pattern in _RAW_RULES
)


def evaluate(name: str) -> tuple[str, str]:
    """Return (suggested_sku, family_code) for the given product name.

    Empty or no-match → ('MSC', 'MSC').
    """
    if not name:
        return ('MSC', 'MSC')
    for rule in FAMILY_RULES:
        if rule.pattern.search(name):
            return (rule.code, rule.code)
    return ('MSC', 'MSC')
