# Seed the Hatafa brand palette into muk_web_colors (light mode).
#
# Token source: docs/design/HATAFA.design.md (primary #714B67, status strong tones).
# muk_web_colors persists colors as a customized SCSS asset (per-database
# ir.attachment via muk_web_colors.color_assets_editor), so branding is DB
# config, not module code. Run once per database; idempotent.
#
# Usage (local):
#   cat scripts/apply_hatafa_brand_colors.py | \
#     docker exec -i namco_odoo19 odoo shell -d namco_odoo19 --no-http
# Usage (staging): same via ssh + sudo docker exec -i esty19_odoo ... -d esty_odoo19

HATAFA_LIGHT = {
    'color_brand_light': '#714B67',
    'color_primary_light': '#714B67',
    'color_success_light': '#15803D',
    'color_info_light': '#1D4ED8',
    'color_warning_light': '#B45309',
    'color_danger_light': '#B91C1C',
}

settings = env['res.config.settings'].create({})
current = {key: settings[key] for key in HATAFA_LIGHT}
if current == HATAFA_LIGHT:
    print('Hatafa palette already applied — no change.')
else:
    settings.write(HATAFA_LIGHT)
    settings.set_values()
    env.cr.commit()
    print('Hatafa palette applied:', HATAFA_LIGHT)
