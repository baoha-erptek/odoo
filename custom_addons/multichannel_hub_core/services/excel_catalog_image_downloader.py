"""Excel catalog image downloader (Spec 010 P-HUB-IMAGES MVP).

Downloads images referenced by `product.catalog.import.line.image_*_ref`
columns onto the matched `product.template.image_1920`. Content-hash
idempotency: skip if the template already has the same image bytes.

Per-run cap from ICP `multichannel_hub.catalog_max_images_per_run`
(default 500). Per-image failure does NOT fail the row — emits a warning
log + counter increment and continues.

GDrive URL handling deferred — initial MVP only handles HTTPS URLs.
Reuses the etsy_integration image_downloader timeout + allowlist
philosophy but with a permissive HTTPS-only check (not domain-locked
since catalog images come from arbitrary operator-trusted sources).
"""

import base64
import hashlib
import logging
from urllib.parse import urlparse

import requests

_logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 20  # seconds


def download_images_for_run(env, run):
    """Download images for all upserted lines in this run.

    Returns counters dict: {'downloaded', 'skipped_unchanged', 'failed'}.
    """
    counters = {'downloaded': 0, 'skipped_unchanged': 0, 'failed': 0}
    cap = int(env['ir.config_parameter'].sudo().get_param(
        'multichannel_hub.catalog_max_images_per_run', '500',
    ))
    Line = env['product.catalog.import.line'].sudo()
    lines = Line.search([
        ('run_id', '=', run.id),
        ('state', '=', 'upserted'),
        '|',
        ('image_1_ref', '!=', False),
        ('image_2_ref', '!=', False),
    ])
    seen = 0
    for line in lines:
        if seen >= cap:
            _logger.info(
                "catalog image cap %s reached; stopping run=%s", cap, run.name,
            )
            break
        tmpl = line.target_product_id
        if not tmpl:
            continue
        for ref_field in ('image_1_ref', 'image_2_ref'):
            url = (line[ref_field] or '').strip()
            if not url:
                continue
            if seen >= cap:
                break
            seen += 1
            result = _download_one(env, tmpl, url)
            counters[result] = counters.get(result, 0) + 1
    return counters


def _download_one(env, tmpl, url):
    """Download a single image; return one of 'downloaded' / 'skipped_unchanged'
    / 'failed'. Per-image failures are logged but never raise.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('https',):
        _logger.warning(
            "catalog image rejected non-https url %s for tmpl=%s",
            url, tmpl.display_name,
        )
        return 'failed'
    try:
        response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        _logger.warning(
            "catalog image download failed url=%s tmpl=%s: %s",
            url, tmpl.display_name, exc,
        )
        return 'failed'
    payload = response.content
    if not payload:
        _logger.warning(
            "catalog image empty body url=%s tmpl=%s", url, tmpl.display_name,
        )
        return 'failed'
    new_hash = hashlib.sha256(payload).hexdigest()
    # Content-hash idempotency check against current template image
    if tmpl.image_1920:
        try:
            existing = base64.b64decode(tmpl.image_1920)
            if hashlib.sha256(existing).hexdigest() == new_hash:
                return 'skipped_unchanged'
        except Exception:  # noqa: BLE001 — defensive only
            pass
    tmpl.sudo().write({'image_1920': base64.b64encode(payload)})
    return 'downloaded'
