# ADR-006: Design File Storage — Filestore/URL Only, 10 MB Cap

- **Status**: Proposed (awaiting owner sign-off)
- **Date**: 2026-04-10
- **Deciders**: Owner, architect, ops
- **Affects**: Spec 003 (order.design.file), Spec 004 (tracking file attachments)
- **Related**: [devils-advocate.md §1.7](../agent-reports/devils-advocate.md), [MASTER_PLAN.md §5 R6](../MASTER_PLAN.md)

## Context

The project handles **print-on-demand design files**: high-resolution artwork for products like ceramic dishes, wooden plates, mugs, temporary tattoos, etc. At print-resolution (300 DPI, typical print sizes 6"–20"), these files are typically:

- Front-design TIFF/PSD: **30–150 MB**
- Back-design TIFF/PSD: **30–150 MB**
- Mockup/preview JPEG: 200 KB – 2 MB

Spec 003 currently specifies `order.design.file` with `design_file` Binary and `preview_file` Binary fields. In Odoo 19, `Binary` fields default to `attachment=True`, meaning the data is stored in the `ir.attachment` table, which in turn can be configured to store on filesystem (filestore) or in the database.

**Default Odoo filestore behavior**: bytes are written to disk under `~/.local/share/Odoo/filestore/<db>/<hash>` and `ir_attachment` holds a metadata row with the checksum. **This is correct.** Disk is fine.

**The risk**: Odoo allows forcing `ir_attachment` to use `db_datas` (in-row storage) via the `ir_attachment.location` parameter. If that parameter is set (or if the filestore is misconfigured), 17K orders × ~80 MB average = **~1.36 TB** stored inside PostgreSQL's `ir_attachment.db_datas` column. Consequences:

- `pg_dump` runtime explodes from minutes to hours.
- Backup sizes multiply by ~100x.
- Replication lag becomes unmanageable.
- Any table scan on `ir_attachment` becomes unusable.

Devil's advocate review flagged this as an **un-sized risk that nobody on the team has verified**.

Additionally, the current email-based workflow already has design files as **URLs in the Etsy data** (`DESIGN_LINK_FRONT`, `DESIGN_LINK_BACK` columns in the source Excel). Re-hosting them in Odoo is a choice, not a requirement.

## Decision

Commit to the following storage policy for all design files and large attachments:

### 1. Filesystem storage only

`ir_attachment.location` MUST remain `file` (the Odoo default). A Phase 0 verification step asserts this on the target environment via:

```
SELECT value FROM ir_config_parameter WHERE key = 'ir_attachment.location';
-- expected: 'file' or NULL (default = 'file')
```

Documented as a prerequisite in the `multichannel_hub_core` module's `post_init_hook` (logs a warning if misconfigured).

### 2. 10 MB hard cap on `ir_attachment` writes for binary file fields

Override `ir.attachment.create()` via model inheritance in `multichannel_hub_core` to raise a `ValidationError` if `datas` exceeds 10 MB AND the attachment is attached to an Etsy or fulfillment model (to avoid breaking unrelated Odoo attachments like emails with PDFs).

Pseudocode:

```
class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    _LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB
    _RESTRICTED_RES_MODELS = {'order.design.file', 'sale.order', 'tracking.import.line'}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            res_model = vals.get('res_model')
            size = len(vals.get('datas') or b'')
            if res_model in self._RESTRICTED_RES_MODELS and size > self._LARGE_FILE_THRESHOLD_BYTES:
                raise ValidationError(_(
                    "Design file exceeds 10 MB limit. Upload to Google Drive / S3 / "
                    "filestore and link via URL instead. File: %s (%.1f MB)"
                ) % (vals.get('name', '?'), size / 1024 / 1024))
        return super().create(vals_list)
```

The threshold is configurable via `ir.config_parameter` (`multichannel_hub.large_file_threshold_bytes`) with a sensible default.

### 3. URL-based design file references

Extend `order.design.file` to support **URL-mode** storage alongside small-file mode:

```
order.design.file
  storage_mode        Selection: 'small' (default, up to 10 MB binary), 'url' (external link)
  design_file         Binary                  # only if storage_mode='small'
  preview_file        Binary                  # small preview/thumbnail, <= 2 MB
  file_url            Char                    # Google Drive / S3 / etc. link, if storage_mode='url'
  file_name           Char                    # original filename
  file_size           Integer                 # bytes, for display
  file_checksum       Char                    # SHA-256 for integrity
```

Form view renders a preview (thumbnail always stored locally) and either an inline download link (`small` mode) or an external link (`url` mode).

**For the historical 17K orders**: reuse the existing `DESIGN_LINK_FRONT`/`DESIGN_LINK_BACK` URLs from the source Excel. Migration wizard (Spec 002) populates `storage_mode='url'` + `file_url` from those columns. No download, no re-upload.

**For new orders** (API-sourced via Spec 005 or email-sourced via Spec 001): parser captures the CDN URL (Etsy `etsystatic.com` links) and stores as `storage_mode='url'` by default. Only flip to `small` mode if the designer manually uploads a local file after review.

### 4. Preview thumbnails are always stored locally

Small thumbnails (<=2 MB) are stored in `preview_file` (Binary) regardless of the main file's storage mode. Thumbnails are cheap, always visible in list views, and the chatter panel.

### 5. Upload UX guidance

Design file upload wizards (Spec 003) must show:
- Current file size as user uploads (JS file input event)
- The 10 MB cap as a form hint
- A link to "Use URL instead" that switches to the URL input mode when the file is large

This prevents the user from wasting time uploading a 100 MB TIFF only to see an error.

## Consequences

### Positive
- **Bounded database growth**: `ir_attachment` never stores design files > 10 MB. Postgres stays healthy.
- **Backup-friendly**: `pg_dump` runtime is dominated by metadata, not binary blobs.
- **Reuses existing Etsy CDN URLs**: no need to download and re-host 17K historical files (saves weeks of ops).
- **Forward-compatible**: when someone later wants to add Google Drive / S3 auto-sync, the `file_url` field already exists.
- **Enforces discipline**: the hard cap fails loudly instead of silently accepting a 200 MB file.

### Negative
- **External URL dependency**: if Etsy ever takes down the `etsystatic.com` CDN URLs, historical designs become unretrievable from within Odoo. Mitigation: a Phase 4 "archive designs to local backup" task that downloads all historical URLs to a filestore outside the DB.
- **Manual upload for large files**: the 10 MB cap blocks the most natural UX (drag-and-drop a 100 MB TIFF into Odoo). Operators must instead upload to Drive/S3 and paste the URL. Workflow friction. Mitigated by the "Use URL instead" link in the wizard.
- **Checksum verification complexity**: verifying a URL-mode file's integrity requires a background job that downloads and hashes it. Defer this until it becomes a real problem.

### Neutral
- The 10 MB threshold is conservative. If it proves too tight for legitimate cases, raise it via the `ir.config_parameter` without code changes.

## Alternatives considered

1. **No cap, trust the filestore** — rejected. `ir_attachment.location` could be misconfigured on any deployment; the cap is insurance against operator error. Also, even with filestore, a 1.7 TB directory tree has its own operational cost (backup, monitoring, disk alerts).
2. **100 MB cap** — rejected. Still allows 17K × 80 MB = 1.36 TB worst case. 10 MB forces the designer to think about hosting.
3. **No binary storage at all, URL-only** — rejected. Small preview files and legitimately-small mockup JPEGs (a few hundred KB) are fine inside `ir_attachment`; forcing everything external is over-correction.
4. **Use Odoo's `documents_google_drive` module** — rejected per [ADR-004](ADR-004-enterprise-alternatives.md) (Enterprise-only).
5. **Integrate with MinIO / local S3-compatible blob store** — interesting long-term, deferred. Adds deployment complexity that isn't justified until the URL-mode approach hits a real pain point.
6. **Content-hash-based deduplication** (multiple orders referencing the same design file share one storage slot) — deferred. Worth revisiting in a later phase, especially if the historical data has repeated designs. Not a day-one requirement.

## Implementation notes

- Land the `ir.attachment.create()` override in `multichannel_hub_core` during Phase 1 (Spec 003 rewrite).
- Update `specs/003-dashboard-design-multichannel/data-model.md` to add `storage_mode`, `file_url`, `file_checksum`, and the 10 MB rule.
- Update Spec 002's migration wizard to populate `storage_mode='url'` + `file_url` from the historical Excel's `DESIGN_LINK_FRONT`/`DESIGN_LINK_BACK` columns.
- Add a test that attempts to create an `ir.attachment` with 15 MB datas on a restricted model and asserts `ValidationError`.
- Add a post-migration verification query to count `order.design.file` records by `storage_mode` and surface any `small` records approaching the cap.
- Document the "Use URL instead" UX affordance in the design file upload wizard's form view help text.
