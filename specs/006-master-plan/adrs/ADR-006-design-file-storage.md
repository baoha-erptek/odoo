# ADR-006: Design File Storage — Google Drive Primary, Filestore Fallback, 10 MB Cap

- **Status**: Accepted (Revised 2026-04-13)
- **Date**: 2026-04-10 (initial) · **Revised**: 2026-04-13 (owner confirmed GDrive is the primary store — see §0 below)
- **Sign-off**: 2026-04-13 (owner, both initial and revision)
- **Deciders**: Owner, architect, ops
- **Affects**: Spec 003 (order.design.file), Spec 004 (tracking file attachments), Spec 004a (GDrive polling for tracking Excel — separate use case but shares auth)
- **Related**: [devils-advocate.md §1.7](../agent-reports/devils-advocate.md), [MASTER_PLAN.md §5 R6](../MASTER_PLAN.md), [ADR-008](ADR-008-api-first-pivot.md)

## 0. Revision 2026-04-13 — Google Drive is the primary store

Owner answer to MASTER_PLAN Q4 (design file size reality): design files will live on **Google Drive**, not in the Odoo filestore or `ir_attachment.db_datas`. Odoo stores a **GDrive file reference** (file ID + preview URL) plus a small local thumbnail.

What changes from the initial (2026-04-10) version of this ADR:

- Section 3 (URL-based design file references) — **promoted from optional escape hatch to the default path**. `storage_mode='gdrive'` is added as the primary mode; `storage_mode='url'` stays as a generic-URL option for non-GDrive links (e.g., direct `etsystatic.com` CDN links captured from Etsy); `storage_mode='small'` stays for tiny on-filestore binaries.
- Section 2 (10 MB cap) — unchanged. The cap remains insurance against anyone bypassing the GDrive path and dumping a large file into `ir_attachment`.
- Section 4 (thumbnails local) — unchanged.
- New Section 6 — GDrive auth, folder structure, and polling policy shared with Spec 004a's logistics tracking imports.

What does **not** change:

- Filestore location stays `file` (the Odoo default) — section 1.
- 10 MB hard cap on `ir_attachment` writes for restricted models — section 2.
- Small thumbnails stored locally regardless of main-file mode — section 4.
- Upload UX guidance — section 5.

Rationale for the revision: (a) actual design files run 30–150 MB TIFF/PSD with 17K+ orders ⇒ 1.36 TB order-of-magnitude storage that Odoo shouldn't own; (b) GDrive already has org-level retention, versioning, and sharing that we do not want to re-invent; (c) the same GDrive account is being used for logistics partners' tracking-Excel uploads (Spec 004a per Q7 answer), so authenticating once and polling folders is cheaper than maintaining two storage backends.

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

### 3. Storage modes (revised 2026-04-13)

Extend `order.design.file` to support three storage modes with GDrive as the primary:

```
order.design.file
  storage_mode        Selection:
                        'gdrive' (DEFAULT for new orders — file lives in GDrive)
                        'url'    (external non-GDrive link, e.g. Etsy CDN)
                        'small'  (rare — small binary inside ir_attachment, <=10 MB)
  gdrive_file_id      Char                    # Google Drive file ID (required if storage_mode='gdrive')
  gdrive_preview_url  Char                    # GDrive preview/webViewLink (computed from file ID)
  gdrive_folder_id    Char                    # parent folder ID for context / policy enforcement
  file_url            Char                    # generic external URL (if storage_mode='url')
  design_file         Binary                  # only if storage_mode='small'
  preview_file        Binary                  # small thumbnail, always local, <=2 MB
  file_name           Char                    # original filename
  file_size           Integer                 # bytes, for display
  file_checksum       Char                    # SHA-256 for integrity
```

Form view renders the always-local thumbnail plus either a GDrive-aware viewer (`gdrive` mode — embedded preview + "Open in Drive" button), an external-link button (`url` mode), or an inline download (`small` mode).

**For new orders (Phase 1+)**: designer uploads the final design file via the Spec 003 wizard. The wizard uploads to the per-order GDrive folder via the GDrive API service account, captures the returned `file_id`, generates a thumbnail locally (resize to <=2 MB), and stores the record with `storage_mode='gdrive'`. No design bytes pass through Odoo's filestore.

**For API-captured CDN links (Spec 005)**: when the Etsy API returns a design listing image URL (`etsystatic.com` CDN), it is stored with `storage_mode='url'` + `file_url=<cdn link>`. If the designer uploads a replacement / refined file, a new record is created with `storage_mode='gdrive'` and the old CDN-URL record is archived (not deleted — preserves audit trail).

**For the historical 17K orders (Spec 002 migration)**: reuse the existing `DESIGN_LINK_FRONT`/`DESIGN_LINK_BACK` URLs from the source Excel. Migration wizard populates `storage_mode='url'` + `file_url` from those columns. **No download, no re-upload, no GDrive migration** — historical URLs are preserved as-is to avoid 17K GDrive API calls and associated quota consumption. A one-off later task can bulk-copy historical designs to GDrive if the CDN URLs start expiring.

### 4. Preview thumbnails are always stored locally

Small thumbnails (<=2 MB) are stored in `preview_file` (Binary) regardless of the main file's storage mode. Thumbnails are cheap, always visible in list views, and the chatter panel.

### 5. Upload UX guidance

Design file upload wizards (Spec 003) must show:
- Current file size as user uploads (JS file input event)
- Default upload target: **GDrive via service account** (`storage_mode='gdrive'`)
- Visible progress for uploads > 10 MB (GDrive upload can take minutes on slow networks)
- Fallback affordance: paste-an-external-URL input for `storage_mode='url'` (e.g., a designer who already has the file hosted elsewhere)
- The 10 MB cap is enforced only on the rare `storage_mode='small'` path (not surfaced in the default UX)

### 6. Google Drive integration policy (new 2026-04-13)

Single GDrive organisation account, shared by design-file storage (this ADR) and logistics-partner tracking Excel ingestion (Spec 004a). Authentication and folder conventions are owned by `multichannel_hub_core`:

**Auth**:
- Service-account JSON key stored in an `ir.config_parameter` row (`multichannel_hub.gdrive_service_account_json`), admin-only read ACL, never logged.
- Scopes: `https://www.googleapis.com/auth/drive.file` (minimum — app-created files only) for design uploads; `https://www.googleapis.com/auth/drive.readonly` for logistics-folder polling. Two separate service accounts if necessary to minimise blast radius.
- Token refresh handled by the `google-auth` library; refresh failures surface on `etsy.sync.health` (`name='gdrive_integration'`).

**Folder structure** (canonical):
```
GDrive root /
  Multichannel Hub /
    Design Files /
      <etsy_shop_code> /
        <YYYY> /
          <order_number>_<design_role>.{tiff,psd,jpg}   # e.g. ETSY1234_front.tiff
    Logistics Inbox /
      GKE /
        <YYYY-MM-DD>_GKE_tracking.xlsx                  # polled by Spec 004a cron
      UniUni /
      YunExpress /
      USPS /
    Logistics Archive /                                 # poller moves processed files here
      GKE / <YYYY> / <filename>.xlsx
```

**Write policy (design files)**:
- Designs are written under `Design Files/<shop>/<year>/`. The write is done by the service account. The path's `folder_id` is cached on the shop record (`etsy.shop.gdrive_design_folder_id`) to avoid a folder-lookup call per upload.
- Deletes from Odoo do not delete from GDrive (soft delete only — preserves design-file audit trail).

**Read policy (logistics inbox)** — Spec 004a owns the consumer:
- Cron poll cadence per partner (default: every 15 min for GKE, configurable).
- Poller lists files in the partner's `Logistics Inbox/<partner>/` folder, filters by `modifiedTime > last_run_at`, imports each new file via the tracking-import wizard, moves the processed file to `Logistics Archive/<partner>/<year>/` on success, and writes an error marker alongside on failure.
- Idempotent: if the poller sees a `file_id` it has already processed (tracked in `tracking.import.log.source_gdrive_file_id`), it skips.

**Quota & rate limits**:
- GDrive API: 1,000 requests per 100 seconds per user. The poller and the upload path share the same service account; both respect the project-wide rate limiter from Spec 005's `multichannel_hub_core/utils/rate_limiter.py`.
- Upload thresholds: resumable uploads mandatory for files > 5 MB (Google's own recommendation); single-shot for smaller.

**Observability**:
- `etsy.sync.health` row `name='gdrive_integration'` tracks: `last_successful_auth_at`, `last_upload_at`, `last_poll_at`, `upload_error_count_24h`, `poll_error_count_24h`, `quota_used_ratio`.
- Dashboard tile (Spec 002 / ADR-008) surfaces red on auth failure or >10% error rate in the last hour.

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
