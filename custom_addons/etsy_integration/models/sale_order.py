import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    etsy_order_id = fields.Char(
        string='Etsy Order ID', index=True, copy=False,
        help='Unique Etsy order identifier from the notification email')
    etsy_shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop', index=True, ondelete='restrict')
    etsy_note_from_buyer = fields.Text(string='Note from Buyer')
    etsy_gift_message = fields.Text(string='Gift Message')
    etsy_shipping_service = fields.Char(string='Shipping Service')
    etsy_processing_time = fields.Char(string='Processing Time')
    etsy_shipping_cost = fields.Float(string='Etsy Shipping Cost', digits=(12, 2))
    etsy_discount_code = fields.Char(string='Discount Code')
    etsy_subtotal = fields.Float(string='Etsy Subtotal', digits=(12, 2))
    etsy_email_log_id = fields.Many2one(
        'etsy.email.log', string='Source Email', ondelete='set null')
    # Spec 005 P0-16b1 — provenance for orders ingested via canonical
    # `EtsyOrderPayload`. `sync_source` mirrors `payload.source`
    # ('api'/'email') so operators can tell which adapter produced the
    # record. `etsy_raw_source_id` stores `payload.raw_source_id`
    # (e.g. `receipt:1234` or `email_log:567`) so we can navigate back
    # to the originating record for audit + replay.
    sync_source = fields.Selection(
        selection=[
            ('api', 'Etsy API'),
            ('email', 'Etsy Email'),
            # 'webhook' is reserved (Spec 005 US4 / Phase 1) so Odoo
            # never adds a CHECK constraint that would reject the value
            # when the webhook adapter lands. No code currently writes
            # 'webhook' — adding it now is purely a forward-compat hook.
            ('webhook', 'Etsy Webhook (reserved)'),
        ],
        string='Sync Source', copy=False, index=True,
        help='Channel adapter that ingested this order; written by '
             'EtsyOrderIngestor.')
    etsy_raw_source_id = fields.Char(
        string='Source Record Reference', copy=False,
        help="Back-pointer to the originating record (e.g. 'receipt:1234' "
             "for API, 'email_log:567' for the email path).")
    # Spec 005 P0-16c — payment + watermark fields driven by
    # EtsyOrderIngestor on initial create AND on status-only re-sync
    # (FR-009). Operator fields (mp_note, pic_user_id, design state)
    # are NOT touched on re-sync — see EtsyOrderIngestor.ingest.
    # `readonly=True` enforces single-writer at the UI level — operators
    # see the value but cannot edit. The ORM still permits writes from
    # the syncer/ingestor service code (channel-sourced single writer).
    # Hard ACL (groups='base.group_system') was rejected because the
    # Order Dashboard (P1-01) needs salesmen to read payment_status to
    # filter unpaid orders. P0-17 will add tracking=True + mail.thread
    # audit so any non-syncer write is detectable.
    payment_status = fields.Selection(
        selection=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
        ],
        string='Etsy Payment Status', copy=False, index=True, readonly=True,
        help='Payment state mirrored from the Etsy receipt; updated on '
             'every API re-sync.')
    etsy_last_modified = fields.Datetime(
        string='Etsy Last Modified', copy=False, index=True, readonly=True,
        help='Mirrors the Etsy receipt last_modified timestamp. Used to '
             'distinguish stale re-syncs from genuine updates.')
    is_etsy_order = fields.Boolean(
        string='Is Etsy Order', compute='_compute_is_etsy_order', store=True)
    etsy_price_anomaly = fields.Boolean(
        string='Etsy Price Anomaly',
        compute='_compute_etsy_price_anomaly', store=True, index=True,
        help='True when an Etsy order has a non-positive amount_total — '
             'used by the migration wizard to quarantine bad data.')

    _sql_constraints = [
        ('etsy_order_id_unique', 'UNIQUE(etsy_order_id)',
         'Etsy Order ID must be unique!'),
    ]

    @api.depends('etsy_order_id')
    def _compute_is_etsy_order(self):
        for order in self:
            order.is_etsy_order = bool(order.etsy_order_id)

    @api.depends('amount_total', 'etsy_order_id')
    def _compute_etsy_price_anomaly(self):
        for order in self:
            order.etsy_price_anomaly = bool(order.etsy_order_id) and order.amount_total <= 0

    def _etsy_auto_confirm(self):
        """Confirm the order, force-validate its pickings, mark as invoiced.

        Per R5 in specs/002-etsy-config-fixes/research.md, Etsy orders are
        already paid by the buyer at checkout — Odoo should not create
        downstream invoices ("to invoice" is a phantom state for these). This
        helper walks the SO from draft → sale → done and writes
        ``invoice_status='invoiced'`` directly so the dashboards stop showing
        the order as awaiting invoicing.

        Idempotent: orders already in `sale`/`done` skip confirmation;
        already-validated pickings are skipped.
        Returns True on success, False on any failure (errors are logged, not
        raised, so a single bad order doesn't poison a batch).
        """
        for order in self:
            try:
                if order.state == 'draft':
                    order.action_confirm()
                pickings = order.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel'))
                if pickings:
                    pickings = pickings.with_context(
                        skip_immediate=True,
                        skip_backorder=True,
                        skip_sms=True,
                    )
                    for picking in pickings:
                        for move in picking.move_ids:
                            if move.state in ('done', 'cancel'):
                                continue
                            move.quantity = move.product_uom_qty
                            move.picked = True
                        picking._action_done()
                if order.invoice_status != 'invoiced':
                    order.write({'invoice_status': 'invoiced'})
            except Exception:
                _logger.exception(
                    'Auto-confirm failed for order %s (Etsy #%s)',
                    order.name, order.etsy_order_id)
                return False
        return True

    @api.model
    def _cron_fetch_etsy_emails(self):
        """Scheduled action: fetch and process Etsy order emails."""
        from ..services.gmail_client import GmailClient
        from ..services.email_parser import parse_etsy_email
        from ..services.order_creator import OrderCreator

        # Sudo required: reading system config parameters (gmail credentials)
        # not accessible to regular users via ACLs
        ICP = self.env['ir.config_parameter'].sudo()
        client_id = ICP.get_param('etsy_integration.gmail_client_id', '')
        client_secret = ICP.get_param('etsy_integration.gmail_client_secret', '')
        refresh_token = ICP.get_param('etsy_integration.gmail_refresh_token', '')
        label = ICP.get_param('etsy_integration.gmail_label', 'ordertest2')

        if not all([client_id, client_secret, refresh_token]):
            _logger.warning(
                'Etsy Integration: Gmail credentials not configured. '
                'Go to Settings > Etsy Integration to set them up.')
            return

        gmail = GmailClient(client_id, client_secret, refresh_token)
        if not gmail.authenticate():
            _logger.error('Etsy Integration: Gmail authentication failed.')
            return

        raw_emails = gmail.fetch_labeled_emails(label)
        if not raw_emails:
            _logger.info('Etsy Integration: No new emails found.')
            return

        _logger.info('Etsy Integration: Processing %d emails.', len(raw_emails))
        auto_confirm = ICP.get_param(
            'etsy_integration.auto_confirm_email', 'False') == 'True'
        creator = OrderCreator(self.env)
        processed_ids = []

        for raw_email in raw_emails:
            EmailLog = self.env['etsy.email.log']
            existing_log = EmailLog.search(
                [('gmail_message_id', '=', raw_email.message_id)], limit=1)
            if existing_log:
                _logger.info('Skipping already-processed email %s', raw_email.message_id)
                processed_ids.append(raw_email.message_id)
                continue

            log_vals = {
                'gmail_message_id': raw_email.message_id,
                'subject': raw_email.subject,
                'date_received': fields.Datetime.now(),
                'raw_body_text': raw_email.text_body,
                'raw_body_html': raw_email.html_body,
                'parse_status': 'failed',
            }

            result = parse_etsy_email(raw_email)

            if hasattr(result, 'error'):
                log_vals['error_message'] = result.error
                EmailLog.create(log_vals)
                _logger.warning(
                    'Etsy Integration: Parse failed for %s: %s',
                    raw_email.message_id, result.error)
                continue

            if creator.is_duplicate_order(result.order_id):
                log_vals['parse_status'] = 'skipped'
                log_vals['error_message'] = (
                    f'Duplicate order: {result.order_id}')
                EmailLog.create(log_vals)
                processed_ids.append(raw_email.message_id)
                continue

            email_log = EmailLog.create(log_vals)
            try:
                order = creator.process_parse_result(result, email_log.id)
                if order:
                    if auto_confirm:
                        order._etsy_auto_confirm()
                    email_log.write({
                        'parse_status': 'success',
                        'sale_order_id': order.id,
                    })
                    processed_ids.append(raw_email.message_id)
                    _logger.info(
                        'Etsy Integration: Created order %s from email %s',
                        order.name, raw_email.message_id)
                else:
                    email_log.write({
                        'parse_status': 'skipped',
                        'error_message': 'Order already exists',
                    })
                    processed_ids.append(raw_email.message_id)
            except Exception as e:
                email_log.write({'error_message': str(e)})
                _logger.exception(
                    'Etsy Integration: Failed to create order from %s',
                    raw_email.message_id)

        if processed_ids:
            try:
                gmail.remove_label(processed_ids, label)
                _logger.info(
                    'Etsy Integration: Removed label from %d emails.',
                    len(processed_ids))
            except Exception:
                _logger.exception(
                    'Etsy Integration: Failed to remove label from emails.')

        _logger.info(
            'Etsy Integration: Cycle complete. %d/%d emails processed.',
            len(processed_ids), len(raw_emails))

        self.env['etsy.email.log']._check_parse_failures()
