"""P1-MTO-SEED — Auto-create pass-through BOM + assign MTO route.

Wizard for products on the `vn_internal_production` pipeline:
- Adds the standard Odoo MTO route (`stock.route_warehouse0_mto`) to the
  product so that confirming a sale order triggers an `mrp.production`.
- Auto-creates a minimal pass-through BOM (1 finished good <- 1 phantom
  component) so the MO has something to consume.

Idempotent: a second run on the same product is a no-op.

See: specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md
     §"Amendment 2026-05-03 - Hybrid with standard Odoo dropship + MTO routes"
"""
from odoo import _, fields, models
from odoo.exceptions import ValidationError

PHANTOM_XMLID = 'multichannel_hub_core.product_mto_phantom_component'
VN_PIPELINE_XMLID = 'multichannel_hub_core.order_pipeline_vn_internal_production'
MTO_ROUTE_XMLID = 'stock.route_warehouse0_mto'
MANUFACTURE_ROUTE_XMLID = 'mrp.route_warehouse0_manufacture'


class ProductMtoBomWizard(models.TransientModel):
    _name = 'product.mto.bom.wizard'
    _description = 'Auto-create pass-through BOM and enable MTO route for vn_internal_production product'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
    )

    def action_create_bom(self):
        """Enable MTO route + create pass-through BOM for the product.

        Validates the product is on the vn_internal_production pipeline,
        then idempotently links the MTO route and creates a `mrp.bom`
        with a single phantom component line.
        """
        self.ensure_one()
        product = self.product_id
        vn_pipeline = self.env.ref(VN_PIPELINE_XMLID)
        if product.x_default_pipeline_id != vn_pipeline:
            current = product.x_default_pipeline_id.name or _("(none)")
            raise ValidationError(_(
                "Product %(name)s is on pipeline %(current)s, not Vietnam "
                "Internal Production. Set its Default Pipeline before running "
                "this wizard.",
                name=product.display_name,
                current=current,
            ))

        mto_route = self.env.ref(MTO_ROUTE_XMLID)
        manufacture_route = self.env.ref(MANUFACTURE_ROUTE_XMLID)
        missing_routes = (mto_route | manufacture_route) - product.route_ids
        if missing_routes:
            product.write({
                'route_ids': [(4, route.id) for route in missing_routes],
            })

        existing = self.env['mrp.bom'].search(
            [('product_tmpl_id', '=', product.id)],
            limit=1,
        )
        if existing:
            return {'type': 'ir.actions.act_window_close'}

        phantom = self.env.ref(PHANTOM_XMLID, raise_if_not_found=False)
        if not phantom:
            raise ValidationError(_(
                "Manufacturing phantom component is missing. Re-run the "
                "module upgrade to restore the seed (or contact an admin)."
            ))
        phantom_variant = phantom.product_variant_id
        self.env['mrp.bom'].create({
            'product_tmpl_id': product.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [(0, 0, {
                'product_id': phantom_variant.id,
                'product_qty': 1.0,
            })],
        })
        return {'type': 'ir.actions.act_window_close'}
