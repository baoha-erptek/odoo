"""Audit + apply staging E2E config for demo_esty.

Run inside the container's odoo shell:

    docker exec -it esty19_odoo odoo shell -d demo_esty < scripts/staging_recheck_e2e_config.py

Reports the state of every ICP/seed required for the e2e_demo_drop_ship_ordertest2
runner. Secrets are reported as length-only ("set, 24 chars"), never echoed.
The only mutation is on `logistics.partner` (GKE) when GKE_INBOX_FOLDER_ID
below is non-empty AND the row is currently unset.
"""
from datetime import datetime

# ---------------------------------------------------------------- inputs
GKE_INBOX_FOLDER_ID = '1-cY65RDkUGqpUxs8gPrvzV8xuLv56ogW'  # owner-supplied
GKE_ARCHIVE_FOLDER_ID = ''  # FILL ONCE archive folder created in same Drive

# ---------------------------------------------------------------- audit
ICP = env['ir.config_parameter'].sudo()


def _redact(val):
    if not val:
        return 'NOT SET'
    return f'set, {len(val)} chars (redacted)'


print('\n=== STAGING E2E CONFIG AUDIT ===')
print(f'Time: {datetime.utcnow().isoformat()}Z')
print(f'DB: {env.cr.dbname}')

# 1. Gmail OAuth (etsy_integration email parser path)
print('\n[1] Gmail OAuth ICPs')
for key in ('etsy_integration.gmail_client_id',
            'etsy_integration.gmail_client_secret',
            'etsy_integration.gmail_refresh_token'):
    print(f'  {key:50s} = {_redact(ICP.get_param(key))}')

# 2. GDrive design-file folder (P1-DESIGN-AUTO-GDRIVE)
print('\n[2] GDrive design-file folder ICP')
folder = ICP.get_param('multichannel_hub.design_file_default_gdrive_folder_id')
print(f'  multichannel_hub.design_file_default_gdrive_folder_id = '
      f'{folder or "NOT SET"}')
print(f'  multichannel_hub.design_gdrive_auto_sync_enabled       = '
      f'{ICP.get_param("multichannel_hub.design_gdrive_auto_sync_enabled")}')

# 3. Logistics partner (P2-06 GKE polling)
print('\n[3] logistics.partner (GKE)')
gke = env['logistics.partner'].search([('code', '=', 'gke')], limit=1)
if not gke:
    print('  GKE row missing — seed XML may not have run; '
          'try -u multichannel_hub_fulfillment')
else:
    print(f'  name              = {gke.name}')
    print(f'  is_active         = {gke.is_active}')
    print(f'  inbox_folder_id   = {gke.gdrive_inbox_folder_id or "NOT SET"}')
    print(f'  archive_folder_id = {gke.gdrive_archive_folder_id or "NOT SET"}')
    print(f'  poll_interval     = {gke.poll_interval_minutes} min')
    print(f'  last_poll_at      = {gke.last_poll_at}')
    print(f'  last_success_at   = {gke.last_success_poll_at}')

# 4. Gearment API creds (env vars, not ICP)
import os
print('\n[4] Gearment API env vars (process-level)')
for key in ('GEARMENT_API_BASE_URL', 'GEARMENT_API_KEY',
            'GEARMENT_API_SECRET'):
    val = os.environ.get(key, '')
    print(f'  {key:30s} = {_redact(val)}')

# 5. P1-DROP-SEED — Gearment vendor partner exists, products mapped
print('\n[5] Gearment dropship seed')
gearment = env.ref('multichannel_hub_fulfillment.partner_gearment_vendor',
                   raise_if_not_found=False)
print(f'  partner_gearment_vendor = '
      f'{gearment.display_name if gearment else "NOT SET"}')
mapped = env['product.template'].search_count(
    [('x_gearment_sku', '!=', False)])
print(f'  products with x_gearment_sku = {mapped}')

# 6. P1-IMG-CRON-WIRE — newly landed cron exists
print('\n[6] P1-IMG-CRON-WIRE (new today)')
cron = env.ref('etsy_integration.ir_cron_download_pending_etsy_images',
               raise_if_not_found=False)
if cron:
    print(f'  cron found, active={cron.active}, '
          f'interval={cron.interval_number}{cron.interval_type[0]}, '
          f'user={cron.user_id.login}')
else:
    print('  cron NOT FOUND — this slice not deployed; rsync + '
          '-u etsy_integration first')

# 7. ordertest2 label — only verifiable via gmail_client; report config only
print('\n[7] Gmail label gating')
print('  This audit cannot reach Gmail directly. Verify in Gmail UI:')
print('  label "ordertest2" exists on the mailbox tied to gmail_refresh_token')

# ---------------------------------------------------------------- apply
print('\n=== APPLY ===')
if not gke:
    print('  Skipping GKE folder write — partner row missing.')
elif gke.gdrive_inbox_folder_id and not GKE_INBOX_FOLDER_ID:
    print('  GKE inbox already set; no override requested. Skipping.')
elif GKE_INBOX_FOLDER_ID:
    vals = {}
    if not gke.gdrive_inbox_folder_id:
        vals['gdrive_inbox_folder_id'] = GKE_INBOX_FOLDER_ID
    if GKE_ARCHIVE_FOLDER_ID and not gke.gdrive_archive_folder_id:
        vals['gdrive_archive_folder_id'] = GKE_ARCHIVE_FOLDER_ID
    if vals:
        gke.sudo().write(vals)
        env.cr.commit()
        print(f'  WROTE {vals} to logistics.partner({gke.id})')
    else:
        print('  GKE folder fields already populated — no write needed.')
else:
    print('  GKE_INBOX_FOLDER_ID empty — nothing to apply.')

print('\n=== DONE — paste output back to operator ===\n')
