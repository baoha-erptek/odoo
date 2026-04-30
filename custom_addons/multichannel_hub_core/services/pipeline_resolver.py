"""pipeline_resolver — resolve fulfillment pipeline for an order.

Resolution chain (ADR-010 §2):
    product.template.x_default_pipeline_id
      → product.template.categ_id.x_default_pipeline_id
        → ICP `multichannel_hub.default_pipeline_code`
          → first active order.pipeline (deterministic by sequence)
            → None

Used by sale.order._compute_x_pipeline_id and by import wizards.
"""
import logging

_logger = logging.getLogger(__name__)

DEFAULT_PIPELINE_ICP_KEY = 'multichannel_hub.default_pipeline_code'


def resolve_pipeline_for_order(order):
    """Return the pipeline recordset (1 record or empty) for a sale.order.

    Picks the "majority" pipeline across order lines; ties broken by sequence.
    Empty recordset when nothing matches (typical: order with no lines yet).
    """
    env = order.env
    Pipeline = env['order.pipeline']

    if not order.order_line:
        return resolve_default_pipeline(env)

    counts = {}
    for line in order.order_line:
        pipeline = resolve_pipeline_for_product(line.product_id.product_tmpl_id)
        if pipeline:
            counts[pipeline.id] = counts.get(pipeline.id, 0) + 1

    if not counts:
        return resolve_default_pipeline(env)

    winner_id = max(counts, key=counts.get)
    return Pipeline.browse(winner_id)


def resolve_pipeline_for_product(template):
    """Return the pipeline recordset (1 or empty) for a product.template.

    Walks: template.x_default_pipeline_id → template.categ_id.x_default_pipeline_id
    → ICP fallback → first-active fallback.
    """
    if not template:
        return template.env['order.pipeline'] if template else None

    env = template.env

    if template.x_default_pipeline_id:
        return template.x_default_pipeline_id

    cat = template.categ_id
    while cat:
        if cat.x_default_pipeline_id:
            return cat.x_default_pipeline_id
        cat = cat.parent_id

    return resolve_default_pipeline(env)


def resolve_default_pipeline(env):
    """Return the system-default pipeline (ICP code, then first-active)."""
    Pipeline = env['order.pipeline']
    code = env['ir.config_parameter'].sudo().get_param(DEFAULT_PIPELINE_ICP_KEY)
    if code:
        match = Pipeline.search([('code', '=', code), ('is_active', '=', True)], limit=1)
        if match:
            return match
        _logger.warning(
            "ICP %s=%r does not match any active order.pipeline.code",
            DEFAULT_PIPELINE_ICP_KEY, code,
        )
    return Pipeline.search([('is_active', '=', True)], order='sequence, name', limit=1)
