"""Product categorizer.

Loads the keyword-to-category mapping from
``data/product_category_keywords.json`` (stored in the module's data dir) and
exposes a single ``categorize(product_name)`` method that returns the matching
``product.category`` record, or the configured fallback if no keyword matches.

Matching is case-insensitive; the first matching keyword wins (per category
order in the JSON file). Per R2 in research.md.
"""
import json
import logging
import os

_logger = logging.getLogger(__name__)

_KEYWORDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'product_category_keywords.json',
)


class ProductCategorizer:
    """Stateful service: loads the JSON map once at construction."""

    def __init__(self, env):
        self._env = env
        self._categories = []
        self._fallback_xmlid = None
        self._load()

    def _load(self):
        try:
            with open(_KEYWORDS_PATH, encoding='utf-8') as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            _logger.warning(
                'Could not load %s: %s — categorizer will always fall back',
                _KEYWORDS_PATH, exc)
            return
        self._categories = [
            (entry['xmlid'],
             tuple(kw.lower() for kw in entry.get('keywords', [])))
            for entry in payload.get('categories', [])
        ]
        self._fallback_xmlid = payload.get('fallback_xmlid')

    def categorize(self, product_name):
        """Return the ``product.category`` matching the first keyword found.

        Falls back to the configured ``fallback_xmlid`` when no keyword
        matches, or returns ``False`` when even the fallback cannot be
        resolved.
        """
        name = (product_name or '').lower()
        if name:
            for xmlid, keywords in self._categories:
                if any(kw in name for kw in keywords):
                    cat = self._env.ref(xmlid, raise_if_not_found=False)
                    if cat:
                        return cat
        if self._fallback_xmlid:
            return self._env.ref(self._fallback_xmlid, raise_if_not_found=False)
        return False
