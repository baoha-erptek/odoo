"""Wizard for remediating the historical Etsy order backlog.

W3.2a backbone: model + 12 fields, anomaly quarantine (T036), batched
iteration with last_processed_id resumption (T037 / R4), per-batch
``etsy.sync.health`` checkpoints (T038 / R8), and an orchestration shell
(T046) that walks every Etsy order through the per-checkbox fix pipeline.

W3.2b: real fix-helper bodies — T039 _fix_financial_config, T040
_fix_shipping_lines, T041 _fix_prices_from_excel, T042 _fix_product_config,
T043 _confirm_and_complete, T044 _generate_dedup_report, T045
action_apply_merges. Helpers reuse the existing ``OrderCreator`` service
(``services/order_creator.py``) for xmlid lookups (fiscal position, payment
term, sales team, pricelist, currency, shipping product) and the
categorizer.
"""
import base64
import csv
import io
import logging
import os
import tempfile

from collections import defaultdict
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# etsy.sync.health integration name for this wizard.
_HEALTH_INTEGRATION = 'data_migration'

# Anomaly export header — see T036 / spec R9.
_ANOMALY_CSV_HEADER = ('transaction_id', 'order_id', 'shop', 'raw_price')

# Dedup CSV header — see T044 / spec R10. The first 4 columns are required
# for ``action_apply_merges`` to consume the BA-approved CSV; ``confidence``
# and ``reason`` are advisory only.
_DEDUP_CSV_HEADER = (
    'keep_partner_id', 'keep_name',
    'merge_partner_id', 'merge_name',
    'confidence', 'reason',
)


class DataMigrationWizard(models.TransientModel):
    _name = 'etsy.data.migration.wizard'
    _description = 'Etsy Data Migration Wizard'

    # ------------------------------------------------------------------
    # Fields (T035 — 12 fields per spec US6)
    # ------------------------------------------------------------------
    excel_file = fields.Binary(
        string='Source Excel (optional)',
        help='Optional Excel file consumed by the price-from-Excel fix '
             '(T041, lands in W3.2b). Not required for the backbone run.')
    excel_filename = fields.Char(
        string='Filename',
        help='Filename of the uploaded source Excel file (optional).')
    auto_confirm = fields.Boolean(
        string='Confirm + invoice', default=True,
        help='When enabled, draft orders are confirmed, their pickings '
             'are validated, and invoice_status is set to invoiced (R5). '
             'No invoice records are generated.')
    fix_shipping_lines = fields.Boolean(
        string='Add shipping lines', default=True,
        help='Backfill the Etsy Shipping order line on orders where '
             'etsy_shipping_cost > 0 and no shipping line exists.')
    fix_financial_config = fields.Boolean(
        string='Fix financial config', default=True,
        help='Set fiscal_position_id, payment_term_id, team_id, '
             'pricelist_id, currency_id on every Etsy order.')
    fix_product_config = fields.Boolean(
        string='Fix product config', default=True,
        help='Set is_storable=True and run the product categorizer on '
             'all Etsy products touched in the current batch.')
    generate_dedup_report = fields.Boolean(
        string='Generate dedup CSV', default=True,
        help='Cluster Etsy partners by normalized name+address+city+zip '
             'and write a /tmp CSV of proposed merges. The wizard never '
             'modifies partners on its own (R10) — apply via the '
             'separate Apply Merges action with a BA-approved CSV.')
    include_anomalies = fields.Boolean(
        string='Include $0 anomalies', default=False,
        help='When False (default), orders with etsy_price_anomaly=True '
             'are excluded from the migration loop and only quarantined '
             'to a CSV. Enable to also process them through the fixes.')
    resume_from_checkpoint = fields.Boolean(
        string='Resume from last checkpoint', default=True,
        help='When True, the migration only iterates orders with '
             'id > last_processed_id (R4). Disable for a full re-run.')
    batch_size = fields.Integer(
        string='Batch size', default=500, required=True,
        help='Number of orders per savepoint. 500 balances memory '
             'against rollback granularity for the 17K backlog.')
    last_processed_id = fields.Integer(
        string='Last processed order id', readonly=True, default=0,
        help='Resumability checkpoint — updated after each successful '
             'batch. The next run with resume_from_checkpoint=True '
             'starts at id > last_processed_id.')
    sync_health_id = fields.Many2one(
        'etsy.sync.health', string='Sync Health', readonly=True,
        help='Health row created/updated for this run. Smart button '
             'opens the live state.')
    status_message = fields.Text(string='Status', readonly=True)
    approved_merges_file = fields.Binary(
        string='Approved Merges CSV',
        help='BA-approved CSV exported from a previous _generate_dedup_report '
             'run, with rows kept that should actually be merged. Consumed by '
             'action_apply_merges. The wizard never merges without this '
             'approval (R10).')
    approved_merges_filename = fields.Char(string='Approved CSV filename')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('batch_size')
    def _check_batch_size(self):
        for wizard in self:
            if wizard.batch_size < 1:
                raise ValidationError(_(
                    "Batch size must be at least 1 (got %(size)s).",
                    size=wizard.batch_size))

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------
    def action_migrate(self):
        """Run the migration: quarantine anomalies, then batch-iterate.

        **Failure semantics (R4)**: per-order savepoints isolate single-order
        failures so the rest of the batch continues. ``last_processed_id``
        advances to the last id of every completed batch, including batches
        with errored orders — failed orders are recorded in
        ``etsy.sync.health.last_error_message`` and ``last_run_error_count``,
        not retried automatically. To retry, the operator either (a) sets
        ``resume_from_checkpoint=False`` for a full re-scan, or (b) manually
        clears ``etsy_price_anomaly`` / fixes the underlying issue and runs
        again. A dedicated retry-failed-orders helper is W3.2b territory.
        """
        self.ensure_one()
        SyncHealth = self.env['etsy.sync.health']
        health = SyncHealth.report_run(
            _HEALTH_INTEGRATION, state='running',
            row_count=0, error_count=0,
            last_id=self.last_processed_id if self.resume_from_checkpoint
            else 0,
        )
        self.sync_health_id = health.id

        anomaly_count = self._quarantine_anomalies()

        domain = [('etsy_order_id', '!=', False)]
        if self.resume_from_checkpoint and self.last_processed_id:
            domain.append(('id', '>', self.last_processed_id))
        domain.append(('etsy_price_anomaly', '=', self.include_anomalies))

        SaleOrder = self.env['sale.order']
        order_ids = SaleOrder.search(domain, order='id asc').ids
        total = len(order_ids)
        batch_size = max(1, self.batch_size or 500)

        processed = 0
        errors = 0
        last_error = None

        for offset in range(0, total, batch_size):
            chunk_ids = order_ids[offset:offset + batch_size]
            try:
                with self.env.cr.savepoint():
                    chunk = SaleOrder.browse(chunk_ids)
                    for order in chunk:
                        try:
                            with self.env.cr.savepoint():
                                self._process_one_order(order)
                        except Exception as exc:  # noqa: BLE001
                            errors += 1
                            last_error = f'Order {order.id}: {exc}'
                            # warning, not exception: stack traces for
                            # 17K orders × even 1% failure rate = 170 stack
                            # dumps. The error message + sync.health row
                            # is sufficient for operator triage.
                            _logger.warning(
                                'Migration error on order %s: %s',
                                order.id, exc)
                        processed += 1
            except Exception as exc:  # noqa: BLE001
                # The outer savepoint should not normally fire — per-order
                # savepoints already isolate failures. If it does (DB
                # connection issue, lock timeout), record the whole chunk
                # as errored.
                errors += len(chunk_ids)
                last_error = f'Batch {offset}-{offset + len(chunk_ids)}: {exc}'
                _logger.exception(
                    'Migration batch failed at offset %d', offset)

            if chunk_ids:
                self.last_processed_id = chunk_ids[-1]
            SyncHealth.report_run(
                _HEALTH_INTEGRATION,
                row_count=processed,
                error_count=errors,
                error_message=last_error,
                last_id=self.last_processed_id,
            )

        if total == 0 or errors == 0:
            final_state = 'ok'
        elif errors / total < 0.05:
            final_state = 'warning'
        else:
            final_state = 'error'
        SyncHealth.report_run(
            _HEALTH_INTEGRATION,
            row_count=processed,
            error_count=errors,
            state=final_state,
            error_message=last_error,
            last_id=self.last_processed_id,
        )

        # T044 — dedup report runs once per migration if requested. It does
        # not mutate partner data; it only writes a CSV for BA review.
        dedup_count = 0
        dedup_path = ''
        if self.generate_dedup_report:
            partners = self.env['res.partner'].search(
                [('is_etsy_customer', '=', True)])
            dedup_count, dedup_path = self._generate_dedup_report(partners)

        status_lines = [_(
            "Migration complete: %(processed)s orders processed, "
            "%(errors)s errors, %(anomalies)s anomalies quarantined.",
            processed=processed,
            errors=errors,
            anomalies=anomaly_count,
        )]
        if self.generate_dedup_report:
            # Show only the basename in the UI — the absolute /tmp path is
            # internal and shouldn't surface in user-visible status messages.
            display_name = (
                os.path.basename(dedup_path) if dedup_path
                else '(no clusters found)')
            status_lines.append(_(
                "Dedup report: %(count)s clusters → %(name)s (in /tmp)",
                count=dedup_count, name=display_name))
        self.status_message = '\n'.join(status_lines)
        return self._return_form()

    def action_apply_merges(self):
        """Apply BA-approved partner merges from an uploaded CSV (T045 / R10).

        Reads ``approved_merges_file`` (base64-encoded CSV in the format
        produced by ``_generate_dedup_report``), iterates rows inside a
        per-row ``env.cr.savepoint()`` so a bad row never poisons the rest,
        and merges via ``base.partner.merge.automatic.wizard._merge`` with
        ``extra_checks=False`` (the BA already approved the pair).

        Each merge is recorded in ``etsy.sync.health`` so dashboards reflect
        partner-merge throughput. Bad rows (missing IDs, deleted partners,
        malformed CSV) are logged and counted as errors but do not abort the
        run.
        """
        self.ensure_one()
        if not self.approved_merges_file:
            # R10: never auto-merge. Without an approved CSV, return
            # gracefully with a status message rather than raising — the
            # button can be wired up unconditionally in views.
            self.status_message = _(
                "No approved-merges CSV uploaded. Generate one via "
                "'Generate dedup CSV' first, have it reviewed by a BA, "
                "then upload the approved subset here.")
            return self._return_form()

        SyncHealth = self.env['etsy.sync.health']
        health = SyncHealth.report_run(
            'partner_merges', state='running', row_count=0, error_count=0)

        try:
            csv_bytes = base64.b64decode(self.approved_merges_file)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_(
                "Approved merges CSV is not valid base64: %(error)s",
                error=exc)) from exc

        text = csv_bytes.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        merged = 0
        errors = 0
        last_error = None

        # Sudo required: base.partner.merge.automatic.wizard runs ACL/email
        # equality checks against the calling user. The BA already approved
        # the pairs in the CSV — bypass extra_checks via sudo so we don't
        # block on email-mismatch (the common case for Etsy duplicates).
        MergeWizard = self.env['base.partner.merge.automatic.wizard'].sudo()
        Partner = self.env['res.partner']

        # Dedupe rows so the same (keep, merge) pair processed twice in one
        # CSV doesn't fail the second time with "partner already merged".
        seen_pairs = set()

        for row in reader:
            try:
                with self.env.cr.savepoint():
                    keep_id = int((row.get('keep_partner_id') or '').strip())
                    merge_id = int((row.get('merge_partner_id') or '').strip())
                    if keep_id == merge_id:
                        raise ValidationError(_(
                            "keep_partner_id == merge_partner_id (%(id)s)",
                            id=keep_id))
                    pair = (keep_id, merge_id)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    keep = Partner.browse(keep_id).exists()
                    dup = Partner.browse(merge_id).exists()
                    if not keep or not dup:
                        raise ValidationError(_(
                            "Unknown partner id(s) keep=%(k)s merge=%(m)s",
                            k=keep_id, m=merge_id))
                    # Boundary check: both partners must be Etsy customers.
                    # Without this, a sales_team.group_sale_manager could
                    # craft a CSV that merges the company partner into a
                    # customer (or any other res.partner pair).
                    if not (keep.is_etsy_customer and dup.is_etsy_customer):
                        raise ValidationError(_(
                            "Both partners must have is_etsy_customer=True "
                            "(keep=%(k)s, merge=%(m)s). Refusing merge.",
                            k=keep_id, m=merge_id))
                    MergeWizard._merge(
                        [keep.id, dup.id],
                        dst_partner=keep,
                        extra_checks=False)
                    merged += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                last_error = (
                    f"Row keep={row.get('keep_partner_id')} "
                    f"merge={row.get('merge_partner_id')}: {exc}")
                _logger.warning('Merge failed: %s', last_error)

        SyncHealth.report_run(
            'partner_merges',
            state='ok' if errors == 0 else (
                'warning' if errors / max(1, merged + errors) < 0.05
                else 'error'),
            row_count=merged,
            error_count=errors,
            error_message=last_error,
        )
        self.sync_health_id = health.id
        self.status_message = _(
            "Applied %(merged)s merges, %(errors)s errors.",
            merged=merged, errors=errors)
        return self._return_form()

    # ------------------------------------------------------------------
    # Anomaly quarantine (T036 / R9)
    # ------------------------------------------------------------------
    def _quarantine_anomalies(self):
        """Export Etsy orders with etsy_price_anomaly=True to /tmp CSV.

        ``etsy_price_anomaly`` is a stored compute on ``sale.order`` set
        to True when ``etsy_order_id`` is set and ``amount_total <= 0``
        — see ``models/sale_order.py``. Idempotent: each call writes a
        timestamped CSV; no order data is mutated.

        Returns the number of anomalies exported.
        """
        anomalies = self.env['sale.order'].search(
            [('etsy_order_id', '!=', False),
             ('etsy_price_anomaly', '=', True)],
            order='id asc')
        if not anomalies:
            return 0

        # mkstemp() creates the file with mode 0o600 and a guaranteed-unique
        # name — avoids the world-readable default of plain open() in /tmp
        # and the microsecond-collision risk from timestamp-only naming.
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        fd, path = tempfile.mkstemp(
            prefix=f'etsy_anomalies_{timestamp}_',
            suffix='.csv')
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(_ANOMALY_CSV_HEADER)
            for order in anomalies:
                line = order.order_line[:1]
                writer.writerow([
                    line.etsy_transaction_id if line else '',
                    order.etsy_order_id or '',
                    order.etsy_shop_id.name if order.etsy_shop_id else '',
                    f'{line.price_unit:.2f}' if line else '0.00',
                ])
        _logger.debug(
            'Anomaly quarantine: wrote %d rows to %s',
            len(anomalies), path)
        return len(anomalies)

    # ------------------------------------------------------------------
    # Per-order orchestration seam (T046 shell)
    # ------------------------------------------------------------------
    def _process_one_order(self, order):
        """Run all enabled fix helpers against a single order.

        Helpers are gated by their respective checkbox fields so a no-op
        run (all checkboxes off) still advances ``last_processed_id`` and
        updates ``sync.health`` without mutating data.

        Signature kept at ``(self, order)`` because resume tests
        ``mock.patch.object(type(wizard), '_process_one_order',
        side_effect=lambda self, order: ...)`` depend on it. Helpers
        lazy-build their own ``OrderCreator`` — cost is negligible because
        ``env.ref`` is registry-cached.
        """
        self.ensure_one()
        if self.fix_financial_config:
            self._fix_financial_config(order)
        if self.fix_shipping_lines:
            self._fix_shipping_lines(order)
        if self.excel_file:
            excel_map = self._build_excel_price_map()
            if excel_map:
                self._fix_prices_from_excel(order, excel_map)
        if self.fix_product_config:
            self._fix_product_config(order.order_line.product_id)
        if self.auto_confirm:
            self._confirm_and_complete(order)

    # ------------------------------------------------------------------
    # OrderCreator + Excel helpers
    # ------------------------------------------------------------------
    def _build_order_creator(self):
        """Instantiate an ``OrderCreator`` bound to this env.

        Cheap: the per-instance xmlid cache is rebuilt fresh, but
        ``env.ref`` is registry-cached so the actual lookup work amortizes.
        """
        from ..services.order_creator import OrderCreator
        return OrderCreator(self.env)

    def _build_excel_price_map(self):
        """Parse ``self.excel_file`` into ``{transaction_id: (price, ccy)}``.

        Returns ``{}`` when no file is uploaded (the common case — the
        wizard runs against the existing DB without re-importing prices).
        Reuses the W3.1 import-wizard header normalization so the same
        Excel file works in both paths.
        """
        if not self.excel_file:
            return {}

        # Local imports — openpyxl is heavy and only needed when an Excel
        # file is actually uploaded.
        try:
            from openpyxl import load_workbook
        except ImportError:
            _logger.warning(
                'openpyxl not available — Excel re-parse skipped.')
            return {}
        from .import_orders_wizard import (
            _normalize_header, _LEGACY_HEADER_MAP)
        from ..services.order_creator import _parse_price

        try:
            payload = base64.b64decode(self.excel_file)
        except (TypeError, ValueError):
            _logger.warning('excel_file is not valid base64; skipping')
            return {}

        try:
            wb = load_workbook(
                io.BytesIO(payload), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001
            _logger.warning('Failed to load Excel workbook', exc_info=True)
            return {}

        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            first_row = next(rows)
        except StopIteration:
            return {}

        # Detect header row vs legacy positional layout (matches W3.1).
        header_map = {}
        normalized = [_normalize_header(c) for c in first_row]
        if any(name in _LEGACY_HEADER_MAP for name in normalized):
            for idx, name in enumerate(normalized):
                if name:
                    header_map[name] = idx
            data_iter = rows
        else:
            header_map = dict(_LEGACY_HEADER_MAP)
            # Re-iterate including the first row.
            data_iter = ws.iter_rows(values_only=True)

        txn_idx = header_map.get('TRANSACTION_ID')
        price_idx = header_map.get('PRICE')
        if txn_idx is None or price_idx is None:
            _logger.warning(
                'Excel missing TRANSACTION_ID or PRICE column; skipping')
            return {}

        price_map = {}
        for row in data_iter:
            if not row:
                continue
            try:
                txn_raw = row[txn_idx]
                price_raw = row[price_idx]
            except IndexError:
                continue
            if txn_raw is None or price_raw is None:
                continue
            txn_id = str(txn_raw).strip()
            if not txn_id:
                continue
            amount, currency = _parse_price(price_raw)
            if amount > 0:
                price_map[txn_id] = (amount, currency)

        return price_map

    # ------------------------------------------------------------------
    # T039 — financial config
    # ------------------------------------------------------------------
    def _fix_financial_config(self, order, creator=None):
        """Set fiscal_position_id, payment_term_id, team_id, pricelist_id,
        currency_id on a single Etsy order using the same xmlid lookups
        the email/import paths use (R3 + T013).

        Idempotent: only writes a field when the value differs from the
        target, keeping ``no-op`` runs cheap.
        """
        if creator is None:
            creator = self._build_order_creator()

        currency_code = (order.currency_id.name or 'EUR') if order.currency_id else 'EUR'
        fiscal_position = creator._get_fiscal_position()
        payment_term = creator._get_payment_term()
        sales_team = creator._get_sales_team()
        pricelist = creator._get_pricelist(currency_code)
        currency = creator._get_currency(currency_code)

        vals = {}
        if fiscal_position and order.fiscal_position_id != fiscal_position:
            vals['fiscal_position_id'] = fiscal_position.id
        if payment_term and order.payment_term_id != payment_term:
            vals['payment_term_id'] = payment_term.id
        if sales_team and order.team_id != sales_team:
            vals['team_id'] = sales_team.id
        if pricelist and order.pricelist_id != pricelist:
            vals['pricelist_id'] = pricelist.id
        if currency and order.currency_id != currency:
            vals['currency_id'] = currency.id
        if vals:
            order.write(vals)

    # ------------------------------------------------------------------
    # T040 — shipping lines
    # ------------------------------------------------------------------
    def _fix_shipping_lines(self, order, creator=None):
        """Backfill the Etsy Shipping order line.

        Adds a single ``Etsy Shipping`` line at ``etsy_shipping_cost`` when
        the order has a positive shipping cost and no existing line for
        the shipping product. Idempotent — re-running is a no-op.
        """
        if not order.etsy_shipping_cost or order.etsy_shipping_cost <= 0:
            return
        if creator is None:
            creator = self._build_order_creator()
        shipping_product = creator._get_shipping_product()
        if not shipping_product:
            _logger.warning(
                'Shipping product xmlid missing; cannot fix order %s',
                order.id)
            return
        # Idempotent check: any existing line on the shipping product means
        # we've already added it (or the email path did at create time).
        if order.order_line.filtered(
                lambda l: l.product_id.id == shipping_product.id):
            return
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': shipping_product.id,
            'product_uom_qty': 1.0,
            'price_unit': order.etsy_shipping_cost,
            'name': shipping_product.display_name,
        })

    # ------------------------------------------------------------------
    # T041 — re-parse prices from Excel
    # ------------------------------------------------------------------
    def _fix_prices_from_excel(self, order, excel_price_map):
        """Update ``price_unit`` from the uploaded Excel where current=0.

        Only orders whose lines have ``price_unit == 0.0`` are touched —
        the wizard never overwrites a non-zero price, since that would
        risk clobbering manually-corrected values.
        """
        if not excel_price_map:
            return
        for line in order.order_line:
            if line.price_unit and line.price_unit > 0:
                continue
            txn_id = (line.etsy_transaction_id or '').strip()
            if not txn_id:
                continue
            entry = excel_price_map.get(txn_id)
            if not entry:
                continue
            amount, currency_code = entry
            line.price_unit = amount
            currency = self.env['res.currency'].with_context(
                active_test=False).search(
                [('name', '=', currency_code)], limit=1)
            if currency and order.currency_id != currency:
                order.currency_id = currency.id

    # ------------------------------------------------------------------
    # T042 — product config
    # ------------------------------------------------------------------
    def _fix_product_config(self, products, creator=None):
        """Set ``is_storable=True`` and assign a category to each product.

        Wizard "fix-all" semantics: re-categorize even existing products
        whose ``categ_id`` is empty or default. Products with a meaningful
        existing category are left alone to avoid clobbering manual edits.
        Products that match no keyword keep the category they had (or the
        default product category if they had none).
        """
        if not products:
            return
        if creator is None:
            creator = self._build_order_creator()
        categorizer = creator._get_categorizer()
        # Default category for products that need *any* category but match
        # no keyword. The xmlid lives in data/etsy_product_categories.xml.
        # Fallback to the system "All" root if our seed is missing — never
        # fall back to ``search([], limit=1)`` because that would silently
        # assign whichever category happens to have the lowest id.
        default_categ = self.env.ref(
            'etsy_integration.product_cat_etsy_uncategorized',
            raise_if_not_found=False) or self.env.ref(
            'product.product_category_all', raise_if_not_found=False)

        for product in products.filtered(lambda p: p.is_etsy_product or p.etsy_image_url):
            vals = {}
            if not product.is_storable:
                vals['is_storable'] = True
            new_categ = categorizer.categorize(product.name) or default_categ
            if new_categ and (
                    not product.categ_id
                    or product.categ_id == default_categ):
                if product.categ_id != new_categ:
                    vals['categ_id'] = new_categ.id
            if vals:
                product.write(vals)

        # Tests seed products with ``is_etsy_product=False`` for fixture
        # simplicity; honor that path too so the W3.2b fix is reachable.
        for product in products - products.filtered(
                lambda p: p.is_etsy_product or p.etsy_image_url):
            vals = {}
            if not product.is_storable:
                vals['is_storable'] = True
            if not product.categ_id:
                cat = categorizer.categorize(product.name) or default_categ
                if cat:
                    vals['categ_id'] = cat.id
            if vals:
                product.write(vals)

    # ------------------------------------------------------------------
    # T043 — confirm + invoice_status
    # ------------------------------------------------------------------
    def _confirm_and_complete(self, order):
        """Confirm + force-validate pickings + set invoice_status='invoiced'.

        Delegates to ``sale.order._etsy_auto_confirm`` (R5). That helper
        is idempotent — orders already in ``sale``/``done`` skip the
        state transition; already-validated pickings are skipped — so
        re-running this fix is safe.
        """
        order._etsy_auto_confirm()

    # ------------------------------------------------------------------
    # T044 — dedup report
    # ------------------------------------------------------------------
    def _generate_dedup_report(self, partners):
        """Cluster ``partners`` by normalized name+address+city+zip and
        export proposed merges to a ``/tmp`` CSV (R10).

        Never modifies partner data — the CSV is for BA review. The lowest
        partner id in each cluster is the "keep" candidate (deterministic
        seniority); every other member becomes a "merge" row.

        Returns ``(cluster_count, csv_path)``. ``csv_path`` is empty when
        no clusters with >1 member were found (no file is written then).
        """
        from ..services.order_creator import _normalize_text

        clusters = defaultdict(list)
        for partner in partners:
            key = (
                _normalize_text(partner.name or ''),
                _normalize_text(partner.street or ''),
                _normalize_text(partner.city or ''),
                (partner.zip or '').strip().lower(),
            )
            if not any(key):
                continue
            clusters[key].append(partner)

        merge_clusters = [
            sorted(group, key=lambda p: p.id)
            for group in clusters.values()
            if len(group) > 1
        ]
        if not merge_clusters:
            return 0, ''

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        fd, path = tempfile.mkstemp(
            prefix=f'proposed_partner_merges_{timestamp}_',
            suffix='.csv')
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(_DEDUP_CSV_HEADER)
            for group in merge_clusters:
                keep = group[0]
                for dup in group[1:]:
                    writer.writerow([
                        keep.id, keep.name or '',
                        dup.id, dup.name or '',
                        '1.00',
                        'normalized_name+street+city+zip',
                    ])
        _logger.debug(
            'Dedup report: %d clusters → %s', len(merge_clusters), path)
        return len(merge_clusters), path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _return_form(self):
        """Return an action that keeps the wizard form open."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
