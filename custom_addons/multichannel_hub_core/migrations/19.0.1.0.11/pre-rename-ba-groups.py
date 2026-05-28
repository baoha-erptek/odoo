# P1-04 followup (2026-05-03): BA-tier groups (group_marketing_user /
# group_ba_user / group_ba_lead) are promoted from etsy_integration to
# multichannel_hub_core per ADR-003 — they are channel-agnostic
# sales-ops roles consumed by the unified Operations Dashboard
# (P1-DASH-MERGE) and any future per-channel module.
#
# Pre-migration runs BEFORE mhc reloads its security XML. We rewrite
# the existing ir.model.data rows so the res.groups records keep their
# database IDs (and therefore their res.groups_users_rel rows — i.e.,
# user-group memberships survive the rename).
#
# After this script runs:
#   - mhc loads its security XML; ir.model.data lookup finds existing
#     rows pointing at the old res.groups records and just updates
#     fields. No new res.groups created. No memberships lost.
#   - etsy_integration upgrade (sequenced after mhc by Odoo's
#     dependency resolver) reloads ir.model.access.csv with the new
#     group_id refs (multichannel_hub_core.group_*) — those resolve
#     to the same renamed rows.

_GROUP_NAMES = ("group_marketing_user", "group_ba_user", "group_ba_lead")


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'multichannel_hub_core'
         WHERE module = 'etsy_integration'
           AND model = 'res.groups'
           AND name IN %s
        """,
        (_GROUP_NAMES,),
    )
