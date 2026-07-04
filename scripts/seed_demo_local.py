"""Seed minimal demo data into the LOCAL dev DB for screenshot / QA runs.

Run via odoo shell (NOT xmlrpc — uses the `env` global):

    docker exec -i namco_odoo19 odoo shell -d namco_odoo19 --no-http \
        < scripts/seed_demo_local.py

Idempotent: keyed on etsy_order_id / nonce so re-runs do not duplicate.
Creates just enough to render:
  - Flow 4 #1  : an Etsy sale.order with a buyer note (the create() override
                 auto-posts it to chatter).
  - Flow 3b #3/#4 : gearment.api.log rows — 2 outbound (200 + 400) and
                 2 inbound webhooks (processed + duplicate) — for the new
                 API Log / Webhook Log views.
"""

from datetime import datetime


def _ref(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec if rec else env[model].create(vals)


shop = _ref('etsy.shop',
            [('name', '=', 'JaHandmadeArt')],
            {'name': 'JaHandmadeArt', 'etsy_api_shop_id': '60752333'})

partner = _ref('res.partner',
               [('name', '=', 'Sarah Miller (demo)')],
               {'name': 'Sarah Miller (demo)', 'email': 'sarah.demo@example.com'})

order = env['sale.order'].search([('etsy_order_id', '=', 'DEMO-ORD-9001')], limit=1)
if not order:
    order = env['sale.order'].create({
        'partner_id': partner.id,
        'etsy_shop_id': shop.id,
        'etsy_order_id': 'DEMO-ORD-9001',
        'sales_channel': 'etsy',
        'channel_order_ref': 'DEMO-ORD-9001',
        'etsy_note_from_buyer':
            'Hi! I love the mug. Could you ship it by Friday? Thank you!',
    })

Log = env['gearment.api.log']


def _log(domain, vals):
    if not Log.search(domain, limit=1):
        Log.create(vals)


now = datetime(2026, 6, 20, 10, 38, 0)
_log([('endpoint', '=', '/v3/orders/draft'), ('sale_order_id', '=', order.id)],
     {'sale_order_id': order.id, 'direction': 'outbound', 'source': 'draft',
      'endpoint': '/v3/orders/draft', 'http_status': 200,
      'request_started_at': now, 'duration_ms': 412,
      'response_summary': 'reference_id=GEA-9001-001 sku_id=SK-77'})
_log([('endpoint', '=', '/v3/orders/price'), ('sale_order_id', '=', order.id)],
     {'sale_order_id': order.id, 'direction': 'outbound', 'source': 'quote',
      'endpoint': '/v3/orders/price', 'http_status': 400,
      'request_started_at': now, 'duration_ms': 388,
      'error_message': 'Invalid address - BA to verify destination ZIP'})
_log([('nonce_value', '=', 'no-9001-aaa')],
     {'sale_order_id': order.id, 'direction': 'inbound', 'source': 'inbound_webhook',
      'endpoint': '/gearment/webhook', 'http_status': 200, 'request_started_at': now,
      'topic_seen': 'order_completed', 'nonce_value': 'no-9001-aaa',
      'signature_verified': True, 'business_handled': True,
      'business_summary': 'tracking saved, status=in_transit'})
_log([('nonce_value', '=', 'no-9001-bbb')],
     {'sale_order_id': order.id, 'direction': 'inbound', 'source': 'inbound_webhook',
      'endpoint': '/gearment/webhook', 'http_status': 200, 'request_started_at': now,
      'topic_seen': 'order_completed', 'nonce_value': 'no-9001-bbb',
      'signature_verified': True, 'business_handled': False,
      'business_summary': 'duplicate nonce (idempotent 200, log only)'})

# --- Phase E additions: D#3 Pipeline tab + D#8 Fulfillment Tracking Detail ---

# D#3 — make the Pipeline tab show a real state + a transition-log row. The
# pipeline resolves to the system-default even with no order lines; the first
# resolve auto-assigns the initial state. Add one transition so the log table
# is non-empty (and the reprint "In Lại" state is reachable from the wizard).
order.invalidate_recordset(['x_pipeline_id', 'x_pipeline_state_id'])
pipeline = order.x_pipeline_id
if pipeline and order.x_pipeline_state_id and not order.pipeline_transition_log_ids:
    states = env['order.pipeline.state'].search(
        [('pipeline_id', '=', pipeline.id)], order='sequence')
    target = states.filtered(lambda s: s.id != order.x_pipeline_state_id.id)[:1]
    if target:
        order._write_pipeline_state(
            target, note='Demo seed transition (screenshot evidence).')

# D#8 — populate the Gearment/Etsy provenance the new Fulfillment Tracking
# Detail form surfaces. gearment_order_ref mirrors x_gearment_outbound_ref;
# the webhook-stamp + etsy-pushed fields are readonly in the UI but writable
# via ORM. tracking_number is address-locked, so bypass the FR-017 guards.
order.write({'x_gearment_outbound_ref': 'GEA-9001-001'})
fulfillment = order.fulfillment_id
if fulfillment:
    fulfillment.with_context(
        bypass_address_change_check=True,
        bypass_label_status_check=True,
    ).write({
        'tracking_number': '9400111202555550000099',
        'tracking_url': 'https://tools.usps.com/go/TrackConfirmAction'
                        '?tLabels=9400111202555550000099',
        'tracking_state': 'in_transit',
        'gearment_last_webhook_at': now,
        'gearment_last_webhook_topic': 'tracking_order_updated',
        'etsy_tracking_pushed': True,
        'etsy_tracking_pushed_at': now,
    })

env.cr.commit()
print('SEED_OK order=%s pipeline=%s state=%s transitions=%s fulfillment=%s '
      'gearment_logs=%s' % (
          order.name,
          order.x_pipeline_id.name if order.x_pipeline_id else None,
          order.x_pipeline_state_id.name if order.x_pipeline_state_id else None,
          len(order.pipeline_transition_log_ids),
          order.fulfillment_id.id if order.fulfillment_id else None,
          Log.search_count([('sale_order_id', '=', order.id)])))
