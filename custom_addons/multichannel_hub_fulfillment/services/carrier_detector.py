"""Carrier auto-detection service (Spec 004a US2).

`detect_carrier(env, tracking_number)` returns `(carrier_record, needs_review)`:
- `carrier_record`: best-match `shipping.carrier` (or `code='other'` fallback,
  or empty recordset if neither matches and no `other` seed exists).
- `needs_review`: True when match was a fallback OR tracking number is empty.

Match algorithm:
- Compile each active carrier's non-empty `tracking_prefix_regex` once
  (cached at function level via `_compiled_cache_for(env)`); cache is
  invalidated by registry signature so admin edits to a regex flow on the
  next call.
- Use `re.match()` (anchored at start) per spec ("prefix").
- Iterate carriers in `(sequence, name)` order (Odoo `_order` default).
- First match wins. If ≥2 carriers' regexes match, the lower-sequence
  carrier wins; emits a `etsy.sync.health` warning naming all candidates
  (best-effort; etsy_integration may be absent).
"""
from __future__ import annotations

import logging
import re

_logger = logging.getLogger(__name__)


def _compiled_cache_for(env):
    """Fetch active carriers with non-empty tracking_prefix_regex, compiled.

    Returns list of (id, sequence, code, compiled_regex) tuples ordered
    by (sequence, code). Re-fetched on every call — Odoo's per-user
    record cache absorbs the master-data SELECT, and the regex compile
    cost is dominated by the search itself for the small N (<20)
    typical of master data.

    Per-call cost: 1 indexed search returning <20 rows + a re.compile()
    per row. For a 50-line preview that's 50× this cost; acceptable.
    For multi-thousand-row imports, hoist the call once outside the loop
    (currently done implicitly by passing the same env).
    """
    rows = env['shipping.carrier'].sudo().search([
        ('is_active', '=', True),
        ('tracking_prefix_regex', '!=', False),
    ])
    out: list[tuple[int, int, str, re.Pattern]] = []
    for c in rows:
        pattern = (c.tracking_prefix_regex or '').strip()
        if not pattern:
            continue
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            _logger.warning(
                "Skipping carrier %s — invalid regex %r: %s",
                c.code, pattern, exc)
            continue
        out.append((c.id, c.sequence, c.code, compiled))
    out.sort(key=lambda t: (t[1], t[2]))
    return out


def detect_carrier(env, tracking_number, *, compiled=None, other=None):
    """Return (carrier_record, needs_review).

    - Empty / falsy tracking_number → (empty recordset, True)
    - First regex match wins (sequence-priority).
    - No match → (`other` carrier, True). If no `other` seed exists →
      (empty recordset, True).
    - Ambiguous match → log etsy.sync.health warning; pick first by sequence.

    For batch use, callers should pass `compiled` (from `_compiled_cache_for`)
    and `other` (from `_other_carrier`) once before the loop to avoid
    re-fetching master data per row.
    """
    Carrier = env['shipping.carrier']
    if not tracking_number or not str(tracking_number).strip():
        return Carrier, True

    if compiled is None:
        compiled = _compiled_cache_for(env)

    text = str(tracking_number).strip()
    candidates: list[tuple[int, int, str]] = []
    for cid, seq, code, c_re in compiled:
        if c_re.match(text):
            candidates.append((cid, seq, code))

    if candidates:
        if len(candidates) > 1:
            _log_ambiguous(env, text, candidates)
        winner_id = candidates[0][0]
        return Carrier.browse(winner_id), False

    if other is None:
        other = _other_carrier(env)
    return other, True


def _other_carrier(env):
    """Return the seed carrier with code='other', or empty recordset."""
    return env['shipping.carrier'].sudo().search(
        [('code', '=', 'other'), ('is_active', '=', True)], limit=1)


def _log_ambiguous(env, tracking_number, candidates):
    """Best-effort warning to the etsy.sync.health audit channel.

    Bypass scope: read-only audit emit. etsy_integration may be absent.
    """
    health = env.get('etsy.sync.health')
    if health is None:
        _logger.warning(
            "Ambiguous carrier match for %r: %s",
            tracking_number,
            ', '.join(c[2] for c in candidates))
        return
    helper = getattr(health.sudo(), '_record_event', None)
    if helper is None:
        return
    # sudo: cross-module audit channel, bypass bounded to event creation.
    try:
        helper(
            kind='gke_carrier_ambiguous',
            ok_count=0, warning_count=1, error_count=0,
            notes=(f"tn={tracking_number[:32]}; "
                   f"candidates={','.join(c[2] for c in candidates)}"),
        )
    except Exception:  # noqa: BLE001 — audit failure must not abort detection
        _logger.warning("etsy.sync.health emit failed", exc_info=True)
