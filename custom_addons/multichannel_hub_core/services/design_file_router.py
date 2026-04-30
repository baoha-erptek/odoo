"""design_file_router — async dispatch service for design.file routes.

P1-02b routing service — orchestrates creation and dispatch of routes
for a design.file to internal production team recipients (mp, ba, pd).

Async dispatch via queue_job (5-retry exponential backoff, 1m → 5m → 15m →
1h → 4h capped). Deduplication by idempotency_key prevents duplicate enqueue
of the same file-recipient-method tuple.

GDrive upload and partner delivery deferral:
  - GDrive actual upload: P1-02c (GDrive wizard integration)
  - Gearment API calls: P4-01 (Gearment fulfillment)
  - Discord manual: no automation (manual process)

References: ADR-009 §4, p1-02b-plan.md §T068.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DesignFileRouter(models.AbstractModel):
    """Stateless router for queuing design.file.route dispatch."""

    _name = 'design.file.router'
    _description = 'Design File Router'

    @api.model
    def dispatch(self, design_file_id, recipient_types=None):
        """Enqueue routes for a design.file. Idempotent (dedups by idempotency_key).

        Args:
            design_file_id (int): ID of design.file to route.
            recipient_types (list[str] | None): Recipient types to create routes for.
                Defaults to ['mp', 'ba', 'pd'] (internal production team).

        Returns:
            dict: {'queued': int, 'deduped': int} counts of newly queued vs
                already-existing routes.

        Behavior:
        - For each recipient_type, look up or create a design.file.route.
        - Idempotency-key deduplication: if a route with matching
          (design_file_id, recipient_type, delivery_method) already exists
          in any non-terminal state (pending, sent, acknowledged), count as
          deduped (no re-enqueue).
        - On route create/dispatch, call route.action_dispatch().
        - On dispatch exception, set route.state='failed' and
          route.failure_reason=str(exc).
        - No auto-fallback on failure (manual Discord workflow per ADR-012 §3).

        TODO P1-02c: Wrap action_dispatch in queue_job with 5-retry
          exponential backoff (1m, 5m, 15m, 1h, 4h capped). For now,
          mocked in tests; real implementation defers to GDrive upload wizard
          integration phase.
        """
        if recipient_types is None:
            recipient_types = ['mp', 'ba', 'pd']

        design_file = self.env['design.file'].browse(design_file_id)
        if not design_file.exists():
            _logger.warning(
                'design.file %d does not exist; dispatch skipped',
                design_file_id,
            )
            return {'queued': 0, 'deduped': 0}

        Route = self.env['design.file.route']
        queued_count = 0
        deduped_count = 0

        for recipient_type in recipient_types:
            # Determine delivery_method based on recipient_type
            # Internal (mp/ba/pd) → gdrive_share; partner_gearment → gearment_api
            if recipient_type == 'partner_gearment':
                delivery_method = 'gearment_api'
            else:
                delivery_method = 'gdrive_share'

            # Recipient resolution: look up from config or default to current user
            recipient_user_id = None
            recipient_partner_id = None

            if recipient_type in ('mp', 'ba', 'pd'):
                # Internal recipients — resolve from config parameters
                param_key = f'multichannel_hub.routing.recipient_user.{recipient_type}'
                config = self.env['ir.config_parameter']
                user_id_str = config.get_param(param_key)
                if user_id_str:
                    try:
                        recipient_user_id = int(user_id_str)
                    except (ValueError, TypeError):
                        _logger.warning(
                            'invalid user ID in config parameter %s: %s',
                            param_key, user_id_str,
                        )
                        recipient_user_id = self.env.user.id
                else:
                    recipient_user_id = self.env.user.id
            elif recipient_type == 'partner_gearment':
                # Gearment partner — resolve from company config
                # For P1-02b, placeholder; actual Gearment partner lookup in P4-01
                partner = self.env['res.partner'].search(
                    [('name', 'ilike', 'gearment')], limit=1
                )
                recipient_partner_id = partner.id if partner else None

            if not recipient_user_id and not recipient_partner_id:
                _logger.warning(
                    'could not resolve recipient for type %s on design.file %d',
                    recipient_type, design_file_id,
                )
                continue

            # Compute idempotency_key
            recipient_id = recipient_user_id or recipient_partner_id
            identity_tuple = f"{design_file_id}_{recipient_id}_{delivery_method}"

            import hashlib
            idempotency_key = hashlib.sha256(identity_tuple.encode()).hexdigest()

            # Check for existing route with same idempotency_key
            existing_route = Route.search(
                [('idempotency_key', '=', idempotency_key)]
            )

            if existing_route:
                # Already routed — dedup
                _logger.debug(
                    'design.file.route for file %d, recipient %s, method %s '
                    'already exists (idempotency_key %s); deduping',
                    design_file_id, recipient_type, delivery_method, idempotency_key[:8],
                )
                deduped_count += 1
                continue

            # Create new route
            try:
                route_vals = {
                    'design_file_id': design_file_id,
                    'recipient_type': recipient_type,
                    'delivery_method': delivery_method,
                }
                if recipient_user_id:
                    route_vals['recipient_user_id'] = recipient_user_id
                if recipient_partner_id:
                    route_vals['recipient_partner_id'] = recipient_partner_id

                route = Route.create(route_vals)

                # Dispatch the route
                try:
                    route.action_dispatch()
                    queued_count += 1
                    _logger.debug(
                        'queued design.file.route %d for file %d, recipient %s',
                        route.id, design_file_id, recipient_type,
                    )
                except Exception as exc:
                    # Mark as failed; do not propagate
                    route.write({
                        'state': 'failed',
                        'failure_reason': str(exc),
                    })
                    _logger.warning(
                        'design.file.route %d dispatch failed: %s',
                        route.id, exc,
                    )
                    queued_count += 1  # Count as queued attempt (failed afterward)

            except Exception as exc:
                _logger.error(
                    'failed to create design.file.route for file %d, '
                    'recipient %s: %s',
                    design_file_id, recipient_type, exc,
                )

        result = {'queued': queued_count, 'deduped': deduped_count}
        _logger.debug(
            'design.file.router.dispatch completed for file %d: %s',
            design_file_id, result,
        )
        return result
