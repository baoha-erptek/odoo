# Etsy Integration

Import Etsy orders from Gmail notification emails into Odoo 19 CE sale orders.

## Features

- **Automated Email Ingestion** -- Polls a Gmail inbox via OAuth2 for Etsy order
  notification emails and creates sale orders automatically.
- **Historical Import** -- Bulk-import past orders from an Excel spreadsheet
  using the Import Orders wizard.
- **Multi-Shop Support** -- Tracks multiple Etsy shops; each sale order links
  back to its originating shop.
- **Customer Management** -- Deduplicates customers by email address first,
  then by name + ZIP code fallback.
- **Product Catalog** -- Auto-creates products from parsed order data with
  optional Etsy listing image download.
- **Dashboard** -- Shop-level order counts and revenue totals for quick
  operational visibility.
- **Design Queue** -- Flags personalized orders that require design work before
  fulfillment.

## Dependencies

### Odoo Modules

| Module | Purpose |
|--------|---------|
| `sale_management` | Sale order management |
| `stock` | Warehouse and inventory |
| `contacts` | Partner management |
| `mail` | Messaging and activity tracking |

### Python Packages

| Package | Purpose |
|---------|---------|
| `openpyxl` | Excel file parsing for historical import |

## Installation

1. Add `custom_addons/` to your Odoo `addons_path` in `odoo.conf`.
2. Restart the Odoo server.
3. Navigate to **Apps**, search for "Etsy Integration", and click **Install**.

## Configuration

### Gmail OAuth2

1. Open **Settings > Technical > Etsy Integration**.
2. Enter the Gmail address to monitor.
3. Provide OAuth2 credentials (Client ID, Client Secret, Refresh Token)
   obtained from the Google Cloud Console.
4. Click **Test Connection** to verify.

### Cron Schedule

The email polling cron runs every 10 minutes by default. Adjust the interval
under **Settings > Technical > Automation > Scheduled Actions** by editing
the "Etsy: Fetch Order Emails" entry.

## Usage

### Automated Email Processing

Once configured, the cron job fetches new Etsy order emails, parses them with
regex patterns, deduplicates customers and products, and creates confirmed
sale orders. Processing logs are visible under **Etsy > Email Logs**.

### Import Orders Wizard

To import historical orders:

1. Navigate to **Etsy > Import Orders**.
2. Upload an Excel file (.xlsx) containing order data.
3. Select the target Etsy shop.
4. Click **Import** to process.

### Design Queue

Orders with personalization text are automatically flagged. Review them under
**Etsy > Design Queue** and mark them as completed once the design work is
done.

## Technical Notes

### Parser Isolation

The email parser (`services/email_parser.py`) is a pure-function module with
no ORM dependency. It accepts raw email text and returns structured dataclasses,
making it independently testable without an Odoo environment.

### Deduplication Strategy

- **Customers**: Match first by email address (exact). If no email is
  available, fall back to buyer name + shipping ZIP code.
- **Orders**: Deduplicate by Etsy receipt ID stored on the sale order.
  Duplicate emails for the same receipt are logged and skipped.
- **Products**: Match by Etsy listing ID stored on the product template.

### Image Downloading

Product images are downloaded from Etsy listing URLs at order-creation time.
Downloads are non-blocking; failures are logged but do not prevent order
creation.

## License

LGPL-3
