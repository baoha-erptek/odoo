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


def evaluate(name: str, env) -> tuple[str, str]:
    """Return (suggested_sku, family_code) for the given product name.

    `env` is the Odoo Environment used to read `mhc.sku.family` rows.
    Empty name or no match → ('MSC', 'MSC').

    Spec 009 §2.5: DB-driven; replaces the frozen tuple landed in T005.
    """
    if not name:
        return _MSC
    for rule in _load_rules(env):
        if rule.pattern.search(name):
            return (rule.code, rule.code)
    return _MSC
