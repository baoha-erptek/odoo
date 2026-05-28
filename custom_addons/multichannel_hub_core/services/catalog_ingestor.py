"""Catalog Excel ingest — line-by-line upsert into product.template.

Spec 010 P-HUB-XLS-INGEST T010. Consumes `product.catalog.import.line`
records (emitted by the future parser service) and either creates or
updates the corresponding `product.template` row per ADR-014 §3 conflict
matrix:

    Excel wins on:  name / description / categ / pricing trio / default_code
    Odoo wins on:   x_channel_applicability_ids (operator-curated)

Per-row savepoint isolates failures; on per-row error, marks the line
`state='error'` + `error_kind='upsert'` + `error_message` and continues
with the next line. Missing-from-Excel templates are NOT auto-archived
(operator-driven decision per spec).

Multi-currency pricelist seed (T011/US5) is deferred to a follow-up.
"""

import logging

_logger = logging.getLogger(__name__)


def upsert(env, run, lines):
    """Apply the conflict matrix line-by-line.

    Returns a dict of counters: {'upserted', 'unchanged', 'error'}.
    The caller (cron / wizard) is responsible for the surrounding
    transaction + writing the result back onto the run row.
    """
    Template = env['product.template'].sudo()
    counters = {'upserted': 0, 'unchanged': 0, 'error': 0}
    for line in lines:
        try:
            with env.cr.savepoint():
                _apply_one(env, Template, line)
            if line.state != 'unchanged':
                line.state = 'upserted'
                counters['upserted'] += 1
            else:
                counters['unchanged'] += 1
        except Exception as exc:  # noqa: BLE001 — per-row isolation
            _logger.warning(
                "catalog ingest line failure run=%s sheet=%s row=%s: %s",
                run.name, line.sheet_name, line.row_number, exc,
            )
            line.sudo().write({
                'state': 'error',
                'error_kind': 'upsert',
                'error_message': (str(exc) or '')[:4000],
            })
            counters['error'] += 1
    return counters


def _apply_one(env, Template, line):
    if not (line.sku or '').strip():
        raise ValueError("missing SKU on line %s/%s" % (line.sheet_name, line.row_number))
    existing = Template.search([('default_code', '=', line.sku)], limit=1)
    excel_vals = _excel_vals(line)
    if existing:
        diff = {k: v for k, v in excel_vals.items() if existing[k] != v}
        if diff:
            # ADR-014 §3 — Excel wins on these fields; Odoo's
            # x_channel_applicability_ids is NEVER touched here.
            existing.write(diff)
            line.sudo().target_product_id = existing.id
        else:
            line.sudo().state = 'unchanged'
            line.sudo().target_product_id = existing.id
    else:
        tmpl = Template.create(excel_vals)
        line.sudo().target_product_id = tmpl.id


def _excel_vals(line):
    vals = {
        'name': (line.name or line.sku or '').strip(),
        'default_code': (line.sku or '').strip(),
    }
    # Pricing trio — Excel "Price USD" → list_price; shipping_fee →
    # x_shipping_price_internal; CAD/EU/VND remain operator-side until
    # the pricelist-seed helper (deferred T011).
    if line.price_usd is not None:
        vals['list_price'] = float(line.price_usd or 0.0)
    if line.shipping_fee is not None:
        vals['x_shipping_price_internal'] = float(line.shipping_fee or 0.0)
    return vals
