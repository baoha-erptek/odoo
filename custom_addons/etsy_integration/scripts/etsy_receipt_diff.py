"""Diff one Etsy receipt against its Odoo sale.order.

Run from an Odoo shell on the target database, for example:

    python3 odoo-bin shell -d esty_odoo19 --addons-path=addons,custom_addons \
        < custom_addons/etsy_integration/scripts/etsy_receipt_diff.py
"""

import json
from pathlib import Path

from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient


RECEIPT_ID = '3818231452'
FIXTURE_PATH = Path(
    'custom_addons/etsy_integration/tests/fixtures/receipt_3818231452.json')


def money_amount(value):
    if not value:
        return 0.0
    return (value.get('amount') or 0) / (value.get('divisor') or 1)


def status(etsy_value, odoo_value):
    if etsy_value in (None, '', [], {}):
        return 'missing upstream'
    if odoo_value in (None, False, ''):
        return 'missing'
    return 'mapped' if str(etsy_value) == str(odoo_value) else 'mismatch'


def line_variation_targets(order):
    result = []
    for line in order.order_line.filtered('etsy_transaction_id'):
        result.append({
            'transaction_id': line.etsy_transaction_id,
            'color': line.etsy_color,
            'size': line.etsy_size,
            'option': line.etsy_option,
            'side': line.etsy_side,
            'face_mask_size': line.etsy_face_mask_size,
            'image_url': line.etsy_image_url,
        })
    return result


def print_row(key, target, row_status):
    print(f'{key:<42} | {str(target):<36} | {row_status}')


def main(env):
    order = env['sale.order'].search([('etsy_order_id', '=', RECEIPT_ID)], limit=1)
    if not order:
        raise RuntimeError(f'No sale.order found for Etsy receipt {RECEIPT_ID}')
    shop = order.etsy_shop_id
    receipt = EtsyApiClient(shop).get(
        f'shops/{shop.sudo().etsy_api_shop_id}/receipts/{RECEIPT_ID}')
    if 'receipt_id' not in receipt and receipt.get('results'):
        receipt = receipt['results'][0]
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True))

    print(f'Odoo order: {order.name} / Etsy receipt: {RECEIPT_ID}')
    print('Etsy key                                  | current Odoo target                | status')
    print('-' * 96)
    print_row('status', order.etsy_receipt_status, status(
        receipt.get('status'), order.etsy_receipt_status))
    print_row('is_shipped', order.etsy_is_shipped, status(
        receipt.get('is_shipped'), order.etsy_is_shipped))
    print_row('total_tax_cost + total_vat_cost', order.etsy_tax_total, status(
        money_amount(receipt.get('total_tax_cost')) + money_amount(receipt.get('total_vat_cost')),
        order.etsy_tax_total,
    ))
    print_row('discount amount', order.etsy_discount_amount, status(
        money_amount(receipt.get('discount_amt') or receipt.get('total_discount_cost')),
        order.etsy_discount_amount,
    ))
    print_row('needs_gift_wrap', order.etsy_needs_gift_wrap, status(
        receipt.get('needs_gift_wrap'), order.etsy_needs_gift_wrap))
    print_row('gift_wrap_price', order.etsy_gift_wrap_price, status(
        money_amount(receipt.get('gift_wrap_price')), order.etsy_gift_wrap_price))
    print_row('transactions[].variations', line_variation_targets(order), 'mapped/mismatch by line')

    etsy_grandtotal = money_amount(receipt.get('grandtotal'))
    subtotal = money_amount(receipt.get('subtotal'))
    shipping = money_amount(receipt.get('total_shipping_cost'))
    tax = money_amount(receipt.get('total_tax_cost')) + money_amount(receipt.get('total_vat_cost'))
    print('-' * 96)
    print(
        'total reconciliation: '
        f'Odoo amount_total={order.amount_total:.2f}; '
        f'Etsy grandtotal={etsy_grandtotal:.2f}; '
        f'subtotal={subtotal:.2f}; shipping={shipping:.2f}; tax={tax:.2f}'
    )


main(env)  # noqa: F821 - provided by odoo-bin shell
