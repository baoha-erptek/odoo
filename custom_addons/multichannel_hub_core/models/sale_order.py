from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _inherits = {'sale.order.fulfillment': 'fulfillment_id'}

    fulfillment_id = fields.Many2one(
        'sale.order.fulfillment',
        string='Fulfillment',
        required=True,
        ondelete='cascade',
        index=True,
    )

    def unlink(self):
        # `_inherits` makes sale.order a variant of sale.order.fulfillment;
        # the fulfillment record is the "parent" and is not auto-deleted when
        # the variant is deleted (same semantics as product.product /
        # product.template). ADR-007's contract is that the sibling row is
        # 1:1 with the order — when the order is gone, its fulfillment row
        # has no reason to exist. Cascade explicitly here.
        #
        # sudo() rationale: the cascade is system-enforced data integrity,
        # not a user-initiated operation on the fulfillment row. The user's
        # permission to delete the *order* is what gates this code path
        # (super().unlink() above runs the ACL check on sale.order). Once
        # the order is gone, the orphaned 1:1 sibling must follow regardless
        # of whether the user holds perm_unlink on sale.order.fulfillment.
        # Without sudo, sales-users with order-unlink rights but no
        # fulfillment-unlink rights would hit a confusing AccessError after
        # the order had already been deleted (rolled back by the transaction).
        fulfillments = self.fulfillment_id
        result = super().unlink()
        fulfillments.sudo().exists().unlink()
        return result
