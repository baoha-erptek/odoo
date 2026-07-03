"""Install hook — backfill design.order rows from existing design.file data.

ESTY-244 Phase 7. Idempotent: groups existing design.file rows by their sale
order and creates one design.order per SO (respecting the UNIQUE constraint),
then links the files. State is inferred from the child files (any approved →
approved; else any proof_sent → proof_sent; else any rejected → rejected; else
pending). Safe to re-run.
"""
import logging

_logger = logging.getLogger(__name__)


def _infer_state(files):
    states = set(files.mapped('state'))
    if 'approved' in states:
        return 'approved'
    if 'proof_sent' in states:
        return 'proof_sent'
    if states == {'rejected'}:  # only rejected files, nothing pending
        return 'rejected'
    return 'pending'


def post_init_hook(env):
    DesignFile = env['design.file'].with_context(active_test=False)
    DesignOrder = env['design.order']

    files = DesignFile.search([('design_order_id', '=', False)])
    if not files:
        _logger.info("design: no unlinked design.file rows to backfill.")
        return

    # Group files by their owning sale order (header- or line-level link).
    by_order = {}
    for f in files:
        so = f.order_id or (f.order_line_id.order_id if f.order_line_id else False)
        if not so:
            continue
        by_order.setdefault(so.id, env['design.file'])
        by_order[so.id] |= f

    created = 0
    for so_id, so_files in by_order.items():
        existing = DesignOrder.search([('sale_order_id', '=', so_id)], limit=1)
        order = existing or DesignOrder.create({
            'sale_order_id': so_id,
            'state': _infer_state(so_files),
        })
        if not existing:
            created += 1
        so_files.write({'design_order_id': order.id})

    _logger.info(
        "design: backfilled %s design.order rows from %s design.file rows.",
        created, len(files))
