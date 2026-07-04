import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Spec 003 C-SO-001: shipping-destination fields locked while an
# address-change request is pending. Keep this set in lock-step with
# data-model.md §1.
_ADDRESS_LOCK_FIELDS = frozenset({
    'partner_shipping_id',
    'street', 'street2', 'city', 'zip',
    'state_id', 'country_id',
})


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
    etsy_discount_amount = fields.Float(
        string='Etsy Discount Amount', digits=(12, 2), readonly=True)
    etsy_subtotal = fields.Float(string='Etsy Subtotal', digits=(12, 2))
    etsy_tax_total = fields.Float(
        string='Etsy Tax Total', digits=(12, 2), readonly=True)
    etsy_receipt_status = fields.Char(string='Etsy Receipt Status', readonly=True)
    etsy_is_shipped = fields.Boolean(string='Etsy Shipped', readonly=True)
    etsy_needs_gift_wrap = fields.Boolean(string='Needs Gift Wrap', readonly=True)
    etsy_gift_wrap_price = fields.Float(
        string='Etsy Gift Wrap Price', digits=(12, 2), readonly=True)
    etsy_total_mismatch = fields.Boolean(
        string='Etsy Total Mismatch', readonly=True, index=True,
        help='Set when Odoo amount_total did not reconcile with the Etsy '
             'buyer-paid total (grandtotal minus marketplace-remitted tax). '
             'Review pricing/line mapping for this order.')
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

    # Spec 005 P1-12 (US3) — tracking-push-to-Etsy state. Written only by
    # services/etsy_tracking_pusher.EtsyTrackingPusher (webhook-triggered
    # per ADR decision D-A, on-demand button, or the 5-min fallback cron).
    # Not group-gated: the Etsy tab is a read-only mirror (owner directive
    # 2026-05-10 D4) so operators read these; the single writer is service
    # code, not the form.
    etsy_tracking_push_status = fields.Selection(
        selection=[
            ('none', 'Not Pushed'),
            ('pending', 'Pending'),
            ('pushed', 'Pushed'),
            ('failed', 'Failed'),
        ],
        string='Etsy Tracking Push Status',
        default='none', copy=False, index=True,
        help='Lifecycle of the tracking-number push to Etsy '
             '(POST receipts/{receipt_id}/tracking).')
    etsy_tracking_push_at = fields.Datetime(
        string='Etsy Tracking Pushed At', copy=False,
        help='Timestamp of the last successful tracking push to Etsy.')
    etsy_tracking_push_error = fields.Text(
        string='Etsy Tracking Push Error', copy=False,
        help='Error detail from the last failed tracking push; cleared '
             'on the next successful push.')

    # P1-04 (Spec 003 US4): address-change approval workflow.
    address_change_request_ids = fields.One2many(
        'etsy.address.change.request', 'order_id',
        string='Address Change Requests')
    has_pending_address_change = fields.Boolean(
        string='Has Pending Address Change',
        compute='_compute_has_pending_address_change',
        store=True, compute_sudo=True, index=True,
        help='True when at least one address-change request is in '
             "'requested' state. Locks shipping fields per C-SO-001.")

    _sql_constraints = [
        ('etsy_order_id_unique', 'UNIQUE(etsy_order_id)',
         'Etsy Order ID must be unique!'),
    ]

    def init(self):
        # P1-01a — composite index for the Tracking-Dashboard saved
        # search "Etsy orders with pending address change" per
        # data-model.md §1. `sales_channel` is in mhc, `has_pending_address_change`
        # is in this module — etsy_integration is the lowest-level
        # module where both columns are guaranteed to exist.
        super().init()
        tools.create_index(
            self.env.cr,
            'sale_order_sales_channel_pending_addr_idx',
            self._table,
            ['sales_channel', 'has_pending_address_change'],
        )
        # P0-13 — composite (etsy_shop_id, etsy_last_modified DESC) for the
        # OrderSyncer "since" cursor and dashboards that filter by shop + recency.
        # tools.create_index has no DESC affordance; use raw SQL with
        # CREATE INDEX IF NOT EXISTS for idempotent re-installs.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS sale_order_etsy_shop_last_modified_idx
                ON sale_order (etsy_shop_id, etsy_last_modified DESC)
        """)

    @api.depends('etsy_order_id')
    def _compute_is_etsy_order(self):
        for order in self:
            order.is_etsy_order = bool(order.etsy_order_id)

    @api.depends('amount_total', 'etsy_order_id')
    def _compute_etsy_price_anomaly(self):
        for order in self:
            order.etsy_price_anomaly = bool(order.etsy_order_id) and order.amount_total <= 0

    @api.depends('address_change_request_ids.state')
    def _compute_has_pending_address_change(self):
        for order in self:
            order.has_pending_address_change = any(
                req.state == 'requested'
                for req in order.address_change_request_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Flow 4 #1 — surface the Etsy buyer note in the order chatter.

        The note is stored in ``etsy_note_from_buyer`` by every ingestion
        path (email parser, API ingestor, import wizard). Posting it to the
        chatter on create lets Marketing see the buyer's message in the
        conversation thread instead of only as a read-only field. Posting
        from ``create`` (not the service) covers all three paths at once.
        """
        orders = super().create(vals_list)
        for order in orders:
            note = (order.etsy_note_from_buyer or '').strip()
            if order.etsy_order_id and note:
                order.message_post(
                    subject=_('Note from buyer (Etsy)'),
                    body=tools.plaintext2html(note),
                )
        return orders

    def write(self, vals):
        """C-SO-001: block destination-field writes while a request is pending.

        Bypass via context flag `approve_address_change=True` — set by
        `etsy.address.change.request.action_approve` only.
        """
        if (
            not self.env.context.get('approve_address_change')
            and any(f in vals for f in _ADDRESS_LOCK_FIELDS)
        ):
            blocked = self.filtered('has_pending_address_change')
            if blocked:
                raise UserError(_(
                    "Address change is pending approval on order(s) %s; "
                    "shipping fields are locked. Approve or reject the "
                    "request first."
                ) % ', '.join(blocked.mapped('name')))
        return super().write(vals)

    def action_request_address_change(self):
        """T060: open the etsy.address.change.request quick-create form
        pre-filled with the current order. Hidden when a request is
        already pending.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request address change'),
            'res_model': 'etsy.address.change.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            },
        }

    def action_pull_etsy_orders(self):
        """Manual Etsy API receipt pull scoped to the caller's shops."""
        Shop = self.env['etsy.shop']
        if (
            self.env.user.has_group('base.group_system')
            or self.env.user.has_group('sales_team.group_sale_manager')
        ):
            shops = Shop.search([('active_source', '=', 'api')])
        else:
            shops = Shop.search([
                ('active_source', '=', 'api'),
                ('user_id', '=', self.env.user.id),
            ])
        if not shops:
            return self._etsy_pull_notification(
                _('Pull Etsy Orders'),
                _('No Etsy shops assigned to you.'),
                'warning',
            )

        from ..services.etsy_order_syncer import EtsyOrderSyncer
        # sudo(): OAuth tokens and etsy_api_shop_id are system-only fields.
        # The user->shop search above is the authorization gate; elevation is
        # applied only after computing the allowed shops from env.user.
        syncer = EtsyOrderSyncer(self.sudo().env)
        totals = {'ingested': 0, 'audited': 0, 'errors': 0}
        for shop in shops:
            try:
                result = syncer.sync_shop_orders(shop.sudo())
            except Exception:
                totals['errors'] += 1
                _logger.exception(
                    'Manual Etsy pull failed for shop %s (id=%s)',
                    shop.name, shop.id,
                )
                continue
            for key in totals:
                totals[key] += int((result or {}).get(key, 0) or 0)
        message = _(
            'Pulled Etsy orders: %(ingested)s ingested, %(audited)s audited, '
            '%(errors)s errors.'
        ) % {
            'ingested': totals['ingested'],
            'audited': totals['audited'],
            'errors': totals['errors'],
        }
        level = 'warning' if totals['errors'] else 'success'
        return self._etsy_pull_notification(_('Pull Etsy Orders'), message, level)

    @staticmethod
    def _etsy_pull_notification(title, message, notification_type):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
        }

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

        # MF-E2E-2: observability checkpoint for the email ingest path
        # (spec 015 exit criterion — one health row per ingest path).
        Health = self.env['etsy.sync.health']

        gmail = GmailClient(client_id, client_secret, refresh_token)
        if not gmail.authenticate():
            _logger.error('Etsy Integration: Gmail authentication failed.')
            Health.report_run(
                'etsy_email_fetch', row_count=0, error_count=1,
                error_message='Gmail authentication failed', state='error',
            )
            return

        raw_emails = gmail.fetch_labeled_emails(label)
        if not raw_emails:
            _logger.info('Etsy Integration: No new emails found.')
            Health.report_run(
                'etsy_email_fetch', row_count=0, error_count=0, state='ok',
            )
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
            strip_label = ICP.get_param(
                'etsy_integration.gmail_strip_label_after_process',
                'True') == 'True'
            if strip_label:
                try:
                    gmail.remove_label(processed_ids, label)
                    _logger.info(
                        'Etsy Integration: Removed label from %d emails.',
                        len(processed_ids))
                except Exception:
                    _logger.exception(
                        'Etsy Integration: Failed to remove label from emails.')
            else:
                _logger.info(
                    "Etsy Integration: %d emails processed; label strip "
                    "DISABLED (ICP "
                    "'etsy_integration.gmail_strip_label_after_process'"
                    "='False'). Set ICP back to 'True' for production.",
                    len(processed_ids))

        _logger.info(
            'Etsy Integration: Cycle complete. %d/%d emails processed.',
            len(processed_ids), len(raw_emails))

        failed = len(raw_emails) - len(processed_ids)
        Health.report_run(
            'etsy_email_fetch',
            row_count=len(processed_ids),
            error_count=failed,
            state='error' if failed else 'ok',
        )

        self.env['etsy.email.log']._check_parse_failures()

    def action_push_tracking_to_etsy(self):
        """P1-12 T036 — on-demand tracking push from the sale.order form.

        Synchronous; returns a client notification action so the operator
        gets immediate feedback. The webhook path (D-A) is the primary
        trigger; this button is the manual retry/override.
        """
        self.ensure_one()
        # Defense-in-depth: the view `groups=` only hides the button;
        # mirror it at the method so an RPC call cannot trigger an
        # authenticated external Etsy push (system OAuth tokens) without
        # the production-team role (security review HIGH; FR-017 pattern).
        if not self.env.user._is_system() and not self.env.user.has_group(
                'multichannel_hub_core.group_production_team'):
            raise UserError(_(
                'Only the production/fulfillment team can push tracking '
                'to Etsy.'))
        from ..services.etsy_tracking_pusher import EtsyTrackingPusher
        ok = EtsyTrackingPusher(self.env).push(self)
        if ok:
            title, msg, kind = _('Tracking pushed'), _(
                'Tracking number was pushed to Etsy.'), 'success'
        else:
            title, msg, kind = _('Tracking push failed'), (
                self.etsy_tracking_push_error or _('Push failed.')), 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': msg, 'type': kind,
                       'sticky': False},
        }

    @api.model
    def _cron_push_tracking(self):
        """P1-12 T035 — fallback sweep: push tracking for Etsy orders that
        the webhook (D-A primary trigger) has not yet delivered.

        Picks Etsy orders whose push status is unresolved and that have a
        fulfillment carrying a tracking number. Per-order soft-fail so one
        bad order does not poison the batch.
        """
        from ..services.etsy_tracking_pusher import EtsyTrackingPusher

        candidates = self.search([
            ('etsy_order_id', '!=', False),
            ('etsy_shop_id', '!=', False),
            ('etsy_tracking_push_status', 'in', ('none', 'pending', 'failed')),
        ])
        if not candidates:
            return
        pusher = EtsyTrackingPusher(self.env)
        Fulfillment = self.env['sale.order.fulfillment']
        for order in candidates:
            fulfillment = Fulfillment.search(
                [('order_id', '=', order.id),
                 ('tracking_number', '!=', False)], limit=1)
            if not fulfillment:
                continue
            try:
                pusher.push(order)
            except Exception:  # noqa: BLE001 — batch isolation
                _logger.exception(
                    'P1-12: cron tracking push failed for %s (Etsy #%s)',
                    order.name, order.etsy_order_id)
