"""SKU grammar v2.1 — DB-driven family classifier.

Reads `mhc.sku.family` rows ordered by priority and runs each row's
regex against the input name. First match wins; no match → ('MSC', 'MSC').

Per-cursor compile cache keyed by (family.id, write_date.timestamp()) so
edits to regex_pattern invalidate the cached compiled pattern on the next
call. Cache is cursor-local (not process-global), which naturally isolates
multi-worker deployments.

A family with a malformed regex_pattern is logged at WARNING level and
skipped — evaluation continues with the remaining families. This way one
bad BA edit does not break the whole classifier.

Spec 009 §2.5 P-HUB-SKU-BUILDER T043. Replaces the frozen Python tuple
that landed in P-HUB-PROD-MODEL T005.
"""

import logging
import re
from typing import NamedTuple

_logger = logging.getLogger(__name__)


# Sentinel for the "no family matched" outcome.
_MSC = ('MSC', 'MSC')


# --- v2.1 SKU shape validator (SKU_GRAMMAR.md §7.1) ----------------------
# Public ICP key gating soft vs hard enforce mode (D-V2-2 default 'soft').
ICP_ENFORCE_MODE_KEY = 'multichannel_hub.sku_v2_enforce_mode'

# Compile-once. Format: <FAM3>-<MAT2>-<SIZE>[-<VAR2>] where SIZE is one of
# the shape tokens (SQ|HT|OV|LSQ|WV|AR|BW|RD), fluid_oz Fn, apparel A...,
# generic size Sn, or rectangular RnXn. Total length 8-14 chars.
_VALIDATOR_REGEX = re.compile(
    r'^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)(-[A-Z]{2})?$'
)


def validate_v2_sku(default_code: str) -> bool:
    """Return True iff ``default_code`` matches SKU Grammar v2.1.

    Length check (8-14 chars) fast-fails before regex. See SKU_GRAMMAR.md §7.1.
    Used by `product.creation.wizard` and `product.sku.builder.wizard` at
    `_validate()` time; soft/hard enforcement is gated by
    `ir.config_parameter` key `ICP_ENFORCE_MODE_KEY`.
    """
    if not default_code:
        return False
    n = len(default_code)
    if n < 8 or n > 14:
        return False
    return bool(_VALIDATOR_REGEX.match(default_code))


class FamilyRule(NamedTuple):
    code: str
    pattern: re.Pattern


# Per-cursor compiled-regex cache.
# Stored on the cursor object so it lives exactly as long as the cursor;
# Odoo's transaction lifecycle bounds it naturally.
_CACHE_ATTR = '_sku_grammar_v2_cache'


def _get_cache(cr):
    cache = getattr(cr, _CACHE_ATTR, None)
    if cache is None:
        cache = {}
        try:
            setattr(cr, _CACHE_ATTR, cache)
        except (AttributeError, TypeError):
            # Cursor proxy in some test contexts disallows attribute writes;
            # fall back to a per-call dict — slower but always correct.
            cache = {}
    return cache


def _compile_family(family) -> FamilyRule | None:
    """Compile a family's regex; return None if the pattern is malformed."""
    try:
        return FamilyRule(
            code=family.code,
            pattern=re.compile(family.regex_pattern, re.IGNORECASE),
        )
    except re.error as exc:
        _logger.warning(
            "SKU family %s has malformed regex %r — skipping (error: %s)",
            family.code, family.regex_pattern, exc,
        )
        return None


def _load_rules(env) -> list[FamilyRule]:
    """Return compiled rules for all active families, in (priority, code) order.

    Uses a per-cursor cache keyed by (family.id, write_date_ts) so a BA edit
    invalidates the entry on the next call.
    """
    # sudo() is intentional and bounded to a read: the family taxonomy is
    # conceptually public (ACL grants read to base.group_user) and drives
    # x_sku_v2_suggested on every product.template compute call, so any
    # signed-in user must be able to read it via the classifier.
    families = env['mhc.sku.family'].sudo().search([])
    cache = _get_cache(env.cr)
    rules: list[FamilyRule] = []
    for family in families:
        wd = family.write_date or family.create_date
        wd_ts = wd.timestamp() if wd else 0.0
        cache_key = (family.id, wd_ts)
        cached = cache.get(cache_key)
        if cached is None:
            compiled = _compile_family(family)
            if compiled is None:
                # Negative-cache the failure so we don't recompile every call,
                # but only for the duration of the cursor (write_date moves on
                # next edit and invalidates the negative entry).
                cache[cache_key] = False
                continue
            cache[cache_key] = compiled
            cached = compiled
        elif cached is False:
            continue
        rules.append(cached)
    return rules


def evaluate(
    name: str,
    env,
    categ_id=None,
    attribute_values=None,
) -> tuple[str, str] | str:
    """Return (suggested_sku, family_code) or full SKU for the given product.

    Args:
        name: Product name (for legacy name-regex fallback).
        env: Odoo Environment to read `mhc.sku.family` and variants.
        categ_id: product.category.id. If provided, use its SKU family (priority).
        attribute_values: dict {attribute_name: code_value, ...} for variants
                         (e.g., {'Material': 'CR', 'Size': 'F11'}).
                         Used with categ_id to build full SKU like 'MUG-CR-F11'.

    Returns:
        If categ_id + attribute_values: full SKU string (e.g., 'MUG-CR-F11').
        Otherwise: (family_code, family_code) tuple.
        No match or empty inputs → ('MSC', 'MSC').

    Spec 009 §2.6 P-HUB-SKU-AUTODERIVE: categ_id wins over name-regex;
    name fallback retained for Excel ingestor with no categ_id.
    """
    # Priority 1: categ_id + family chain
    family_code = None
    if categ_id:
        cat = env['product.category'].browse(categ_id)
        if cat and cat.exists():
            sku_family = cat._get_sku_family_chain()
            if sku_family:
                family_code = sku_family.code

    # Priority 2: name-regex fallback (legacy)
    if not family_code:
        if not name:
            return _MSC
        for rule in _load_rules(env):
            if rule.pattern.search(name):
                family_code = rule.code
                break
        if not family_code:
            return _MSC

    # If attribute_values provided, build full SKU
    if attribute_values and isinstance(attribute_values, dict):
        # family_code-MAT2-SIZE[-VAR2] pattern
        segments = [family_code]
        # Collect attribute codes in order (Material, Size, Color, etc.)
        for attr_name in sorted(attribute_values.keys()):
            attr_code = attribute_values[attr_name]
            if attr_code:
                segments.append(attr_code)
        full_sku = '-'.join(segments)
        return full_sku

    return (family_code, family_code)
