"""Gearment webhook topic-to-handler dispatch (P0-18b2c).

Routes verified webhook payloads to business-effect handlers. Builds on
P0-18b2a (audit log) + P0-18b2b (HMAC verify + replay defenses). The
controller invokes ``GearmentWebhookDispatcher(env).dispatch(topic, body)``
ONLY after ``signature_verified=True`` so handlers may trust the payload.

Out of scope (deferred):
- Etsy ship-notification pushback (P1-12; depends on Spec 005 OAuth)
- Stock-move integration on product_out_of_stock (Spec 007)
- Automatic Etsy refund on order_cancelled (P4-02 returns spec)

Key policies (security-reviewer must explicitly approve):

1. ALL ORM access runs via ``sudo()`` because the controller is
   ``auth='public'`` (HTTP routes for webhooks have no env.user with
   write perms). The webhook is the trust boundary — HMAC + replay
   defenses authenticate Gearment as the caller.

2. Fulfillment writes carry ``bypass_address_change_check=True`` context
   so FR-017's interactive-operator block does not drop legitimate
   inbound tracking. FR-017 stops humans from completing a ship while a
   manual address-change request is pending — it does NOT mean
   "throw away upstream tracking arrivals". If Gearment ships before an
   operator-raised address change is processed, the human resolves the
   conflict; we still record the tracking. Documented per P1-04
   findings.md.

3. ``markupsafe.escape()`` wraps every user-controlled string before
   chatter posts (prevents stored-XSS in the Odoo chatter UI).

4. Soft-fail strategy: if the order referenced by the webhook does not
   exist locally, return ``(False, 'order_not_found')``. The controller
   still returns 200 so Gearment does not retry. The audit row records
   the mismatch for operator triage.

5. Secret blast radius: ``GEARMENT_API_SECRET`` is the **single point of
   failure** for all webhook-triggered business writes. If the secret
   leaks, an attacker can mint valid signatures and write tracking /
   block production / roll back pipeline state on **any** order whose
   name they can guess (or enumerate by probing — see findings.md
   P0-18b2c §enumeration). On suspected leak: rotate the secret on
   Gearment dashboard immediately AND audit `gearment.api.log` for
   ``business_handled=True`` rows from unfamiliar source IPs since the
   suspected leak window.
"""
import logging

from markupsafe import Markup, escape

from odoo import _, fields

_logger = logging.getLogger(__name__)

# Topics that have no business effect and only post chatter (if order found).
_LOG_ONLY_TOPICS = frozenset({
    'shipping_address_verified',
    'shipping_address_unverified',
    'product_out_of_stock',
    'variant_created',
    'variant_updated',
})


class GearmentWebhookDispatcher:
    """Dispatch verified Gearment webhooks to per-topic handlers.

    Stateless: a fresh instance per request. ``env`` is the controller's
    ``request.env`` (public-user env; helpers below call ``sudo()``).
    """

    def __init__(self, env):
        self.env = env

    # --------------------------------------------------------- public API
    def dispatch(self, topic, body):
        """Return ``(handled, summary)``.

        ``handled`` is True when a topic-specific handler ran (including
        soft-fails like 'order_not_found' — those still count because the
        topic was recognised). False for unknown topics or internal
        handler exceptions (so the controller can flag them in audit).
        ``summary`` is a short human-readable result for the audit row.
        """
        if not isinstance(body, dict):
            return False, 'invalid_body_shape'

        try:
            if topic == 'order_completed':
                return True, self._handle_order_completed(body)
            if topic == 'order_cancelled':
                return True, self._handle_order_cancelled(body)
            if topic == 'tracking_order_updated':
                return True, self._handle_tracking_order_updated(body)
            if topic == 'order_on_hold':
                return True, self._handle_order_on_hold(body)
            if topic in _LOG_ONLY_TOPICS:
                return True, self._handle_log_only(topic, body)
            return False, f'unknown_topic:{topic}'[:200]
        except Exception as exc:  # noqa: BLE001 — never re-raise to controller
            _logger.error(
                "P0-18b2c: handler raised for topic=%r — soft-failing",
                topic, exc_info=True,
            )
            return False, f'handler_error:{type(exc).__name__}'[:200]

    # --------------------------------------------------------- helpers
    def _find_order_and_fulfillment(self, body):
        """Return (order, fulfillment, summary_or_none).

        summary_or_none is set to a soft-fail string when lookup fails;
        callers should return that string up to dispatch().
        """
        reference = (body.get('order') or {}).get('reference', '')
        if not reference:
            return None, None, 'no_reference'
        # sudo: public env; read-only search to find the order.
        order = self.env['sale.order'].sudo().search(
            [('name', '=', reference)], limit=1,
        )
        if not order:
            _logger.warning(
                "P0-18b2c: order reference not found: %r", reference,
            )
            return None, None, 'order_not_found'
        fulfillment = order.fulfillment_id
        if not fulfillment:
            _logger.warning(
                "P0-18b2c: order %r has no fulfillment sibling", order.name,
            )
            return order, None, 'no_fulfillment'
        return order, fulfillment, None

    def _post_chatter(self, order, message_text):
        """Post a chatter notification with all interpolated values escaped.

        message_text MUST already wrap user-controlled values via escape().
        sudo: production-team users may not hold direct sale.order write
        ACL but the system-trusted webhook may still post audit chatter.
        """
        order.sudo().message_post(
            body=Markup(message_text),
            message_type='notification',
        )

    def _write_fulfillment(self, fulfillment, vals):
        """Apply a fulfillment write under the documented policy context.

        sudo + bypass_address_change_check=True: webhook is system-trusted
        inbound; FR-017 protects against interactive operator races, not
        upstream tracking arrivals. See module docstring policy #2.
        """
        fulfillment.sudo().with_context(
            bypass_address_change_check=True,
        ).write(vals)

    def _inbound_stamp(self, topic):
        """D#8 — vals fragment recording which inbound webhook last touched
        this fulfillment. Merged into each business handler's write so the
        Fulfillment Tracking Detail form shows last-webhook provenance.
        Neither field is in the fulfillment model's bus-trigger or address-
        lock sets, so stamping carries no extra side effects.
        """
        return {
            'gearment_last_webhook_at': fields.Datetime.now(),
            # Bounded write — callers pass hardcoded topic literals, but cap
            # the length defensively so no future caller can persist an
            # unbounded value into this audit field via the public webhook.
            'gearment_last_webhook_topic': (topic or '')[:64],
        }

    # --------------------------------------------------------- handlers
    def _handle_order_completed(self, body):
        order, fulfillment, fail = self._find_order_and_fulfillment(body)
        if fail:
            return fail
        tracking = body.get('tracking') or {}
        carrier = (tracking.get('company') or '')[:120]
        number = (tracking.get('number') or '')[:120]
        url = (tracking.get('url') or '')[:255]
        vals = {'tracking_state': 'shipped',
                'shipping_date': fields.Date.context_today(fulfillment),
                **self._inbound_stamp('order_completed')}
        if number:
            vals['tracking_number'] = number
        if url:
            vals['tracking_url'] = url
        self._write_fulfillment(fulfillment, vals)
        self._post_chatter(order, _(
            "Gearment marked order completed (carrier %(c)s, tracking %(n)s)."
        ) % {'c': escape(carrier or 'unknown'),
              'n': escape(number or 'unknown')})
        _logger.debug(
            "P0-18b2c: order_completed processed %s tracking=%s carrier=%s",
            order.name, number, carrier,
        )
        return f'order_completed:tracking_set:{carrier or "unknown"}'[:200]

    def _handle_order_cancelled(self, body):
        order, fulfillment, fail = self._find_order_and_fulfillment(body)
        if fail:
            return fail
        status = ((body.get('order') or {}).get('status') or 'cancelled')[:120]
        block_reason = f"Gearment cancelled: {status}"[:240]
        self._write_fulfillment(
            fulfillment,
            {'production_blocked': True, 'block_reason': block_reason,
             **self._inbound_stamp('order_cancelled')},
        )
        # Roll back pipeline state if currently in gearment_pod/confirmed.
        # Helper signature: _write_pipeline_state(state_record, note, change_type)
        if order.x_pipeline_id and order.x_pipeline_id.code == 'gearment_pod':
            quoted_state = self.env.ref(
                'multichannel_hub_core.state_gearment_quoted',
                raise_if_not_found=False,
            )
            current_state = order.x_pipeline_state_id
            if quoted_state and current_state and current_state.code != 'quoted':
                try:
                    order.sudo()._write_pipeline_state(
                        quoted_state,
                        note=f"Gearment cancelled webhook (status={status})",
                        change_type='rollback',
                    )
                except Exception as exc:  # noqa: BLE001 — soft-fail
                    # ERROR (not WARNING) so operator alerting catches the
                    # divergence: fulfillment is now production_blocked but
                    # pipeline state was NOT rolled back. Operator must
                    # reconcile manually. Security review M1 escalation.
                    _logger.error(
                        "P0-18b2c: CRITICAL — pipeline rollback FAILED for %s "
                        "(fulfillment blocked but pipeline still %s): %s",
                        order.name,
                        current_state.code if current_state else '(none)',
                        exc,
                    )
        self._post_chatter(order, _(
            "Gearment cancelled order (status: %(s)s). Production blocked."
        ) % {'s': escape(status)})
        _logger.debug("P0-18b2c: order_cancelled processed %s", order.name)
        return 'order_cancelled:blocked_and_rolled_back'

    def _handle_tracking_order_updated(self, body):
        order, fulfillment, fail = self._find_order_and_fulfillment(body)
        if fail:
            return fail
        tracking = body.get('tracking') or {}
        carrier = (tracking.get('company') or '')[:120]
        number = (tracking.get('number') or '')[:120]
        url = (tracking.get('url') or '')[:255]
        # Always stamp last-webhook provenance even when the payload carries
        # no number/url (D#8); ship-state transitions still belong to other
        # topics, so tracking_state is deliberately left untouched here.
        vals = self._inbound_stamp('tracking_order_updated')
        if number:
            vals['tracking_number'] = number
        if url:
            vals['tracking_url'] = url
        self._write_fulfillment(fulfillment, vals)
        # P1-12 (ADR decision D-A): the Gearment webhook is the primary,
        # low-latency trigger for the Etsy tracking pushback. Soft-fail —
        # tracking is already persisted locally above and the webhook must
        # still 200; the 5-min _cron_push_tracking sweep retries any push
        # that fails here.
        if number and order.etsy_order_id and order.etsy_shop_id:
            try:
                from odoo.addons.etsy_integration.services.\
                    etsy_tracking_pusher import EtsyTrackingPusher
                # sudo: this runs in the PUBLIC webhook env (auth='public'),
                # which has no ACL on sale.order.fulfillment — the push
                # soft-failed on AccessError on EVERY live webhook and
                # silently deferred to the 5-min cron (MF-E2E-3b
                # 2026-07-04). The webhook is HMAC-verified upstream and
                # the elevation is bounded to this single tracking push.
                EtsyTrackingPusher(self.env(su=True)).push(order.sudo())
                # D#8 — record the successful pushback for the detail form.
                self._write_fulfillment(fulfillment, {
                    'etsy_tracking_pushed': True,
                    'etsy_tracking_pushed_at': fields.Datetime.now(),
                })
            except ValueError as exc:
                # Permanent auth/config failure (missing or revoked OAuth
                # token, refresh failed). ERROR so operator alerting catches
                # it — the cron sweep will keep retrying but cannot self-heal
                # a revoked token.
                _logger.error(
                    "P1-12: Etsy tracking push permanent failure for "
                    "%s (OAuth/config): %s", order.name, exc,
                )
            except Exception as exc:  # noqa: BLE001 — soft-fail (transient)
                _logger.warning(
                    "P1-12: Etsy tracking push soft-failed for %s: %s",
                    order.name, exc,
                )
        _logger.debug(
            "P0-18b2c: tracking_order_updated processed %s number=%s",
            order.name, number,
        )
        return f'tracking_order_updated:refreshed:{carrier or "unknown"}'[:200]

    def _handle_order_on_hold(self, body):
        order, fulfillment, fail = self._find_order_and_fulfillment(body)
        if fail:
            return fail
        status = ((body.get('order') or {}).get('status') or 'on_hold')[:120]
        block_reason = f"Gearment on hold: {status}"[:240]
        self._write_fulfillment(
            fulfillment,
            {'production_blocked': True, 'block_reason': block_reason,
             **self._inbound_stamp('order_on_hold')},
        )
        self._post_chatter(order, _(
            "Gearment placed order on hold (status: %(s)s)."
        ) % {'s': escape(status)})
        _logger.debug("P0-18b2c: order_on_hold processed %s", order.name)
        return 'order_on_hold:blocked'

    def _handle_log_only(self, topic, body):
        order, _fulfillment, fail = self._find_order_and_fulfillment(body)
        if fail:
            return f'log_only:{fail}'
        status = ((body.get('order') or {}).get('status') or '')[:120]
        msg = _("Gearment event %(t)s") % {'t': escape(topic)}
        if status:
            msg += _(" (status: %(s)s)") % {'s': escape(status)}
        self._post_chatter(order, msg)
        _logger.debug(
            "P0-18b2c: log_only processed topic=%s order=%s",
            topic, order.name,
        )
        return f'log_only:{topic}'[:200]
