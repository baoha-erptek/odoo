# Etsy Integration - User Guide

**Module**: etsy_integration v19.0.1.0.0
**Platform**: Odoo 19 CE
**URL**: https://odoo.hatafax.com

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Navigating the Etsy Menu](#2-navigating-the-etsy-menu)
3. [Viewing Orders](#3-viewing-orders)
4. [Managing Shops](#4-managing-shops)
5. [Customer Lookup](#5-customer-lookup)
6. [Product Catalog](#6-product-catalog)
7. [Design Queue](#7-design-queue)
8. [Email Log and Troubleshooting](#8-email-log-and-troubleshooting)
9. [Dashboard and Reporting](#9-dashboard-and-reporting)
10. [Importing Historical Orders](#10-importing-historical-orders)
11. [Settings and Configuration](#11-settings-and-configuration)
12. [How It Works](#12-how-it-works)
13. [FAQ](#13-faq)

---

## 1. Getting Started

### Login

1. Open https://odoo.hatafax.com in your browser.
2. Enter your username and password.
3. Click the **Etsy** menu item in the top navigation bar.

### What happens automatically

Once configured, the system checks Gmail every 10 minutes for new Etsy order notification emails with the label `ordertest2`. Each email is parsed and converted into an Odoo sale order with:

- Customer (res.partner) created or matched
- Product(s) created or matched
- Shop assigned (auto-created if new)
- All order details (personalisation, shipping, gift message, etc.)

No manual action is needed for day-to-day order ingestion.

---

## 2. Navigating the Etsy Menu

The top-level **Etsy** menu contains:

| Menu Item | Purpose |
|-----------|---------|
| **Dashboard** | Graph and pivot views of order volume and revenue by shop |
| **Orders** | All Etsy sale orders (list and form views) |
| **Shops** | Etsy shop records with order counts and revenue |
| **Design Queue** | Orders requiring design work (personalisation or gift message) |
| **Email Log** | Processing history for every email fetched |
| **Import Orders** | Wizard for bulk-importing orders from Excel |

---

## 3. Viewing Orders

### Order List

Navigate to **Etsy > Orders** to see all Etsy sale orders.

- Orders are filtered to show only Etsy orders (not regular Odoo orders).
- Use the search bar to find orders by Etsy Order ID, customer name, or date.
- Group by **Etsy Shop** to see orders organized by shop.

### Order Form

Click any order to open the detail form. The form has a dedicated **Etsy** tab showing:

**Etsy Order section:**
- Etsy Order ID (unique identifier from the notification email)
- Etsy Shop (links to the shop record)
- Source Email (links to the email log entry)

**Shipping section:**
- Shipping Service (e.g., Standard, Express)
- Processing Time (e.g., "9-10 business days")
- Shipping Cost

**Pricing section:**
- Discount Code (if any)
- Etsy Subtotal

**Notes section:**
- Note from Buyer
- Gift Message

**Order Lines** include Etsy-specific columns (hidden by default, use the column selector):
- Transaction ID
- Personalisation text
- Color, Size, Option

### Order Status

All orders are created in **Draft** (Quotation) state. Your team manually confirms orders after reviewing them.

---

## 4. Managing Shops

Navigate to **Etsy > Shops** to view all Etsy shops.

Each shop record shows:
- **Order Count** stat button -- click to see that shop's orders
- **Total Revenue** -- sum of all order amounts
- **Orders tab** -- list of orders linked to this shop

Shops are created automatically when a new shop name appears in an Etsy email. Current shops: Viktor, Julien, Carina, Sven (and more as new emails arrive).

---

## 5. Customer Lookup

Etsy buyers are created as Odoo contacts (res.partner) with the flag **Is Etsy Customer** = True.

### Finding a customer

1. Go to **Contacts** (main Odoo menu).
2. Use the **Etsy Customers** filter in the search bar.
3. Click a customer to see their details and the **Etsy Orders** smart button showing their order count.

### Customer deduplication

The system prevents duplicate contacts:
1. First checks by **email address** (exact match).
2. If no email, checks by **name + ZIP code**.
3. Only creates a new contact if no match is found.

---

## 6. Product Catalog

Products are auto-created from order line data. Each product has:
- Product name (from the Etsy listing title)
- **Is Etsy Product** flag
- **Etsy Image URL** (link to the listing image on etsystatic.com)

### Finding Etsy products

1. Go to **Sales > Products** (or **Inventory > Products**).
2. Use the **Etsy Products** filter in the search bar.

### Product matching

Products are matched by exact name. Different options (size, color) of the same product are NOT separate products -- they are recorded as attributes on the sale order line.

---

## 7. Design Queue

Navigate to **Etsy > Design Queue** to see orders that require design work.

This view shows order lines where:
- **Personalisation** text is present, OR
- **Gift Message** is present on the parent order

Columns displayed:
- Order reference
- Product name
- Personalisation text
- Color, Size, Option
- Gift Message
- Image URL (link to product image)

Use this view to track which orders need custom design work before fulfillment.

---

## 8. Email Log and Troubleshooting

Navigate to **Etsy > Email Log** to see the processing history.

### Status indicators

| Status | Meaning |
|--------|---------|
| **Success** (green) | Email parsed and order created |
| **Failed** (red) | Email could not be parsed -- see error message |
| **Skipped** (grey) | Duplicate email -- order already exists |

### Investigating failures

1. Click a failed log entry.
2. Read the **Error Message** field for details.
3. Use the **Raw Body (Text)** and **Raw Body (HTML)** tabs to inspect the original email content.
4. Click **Retry Parse** to attempt reprocessing after a fix.

### Automatic failure alerts

If 5 or more consecutive emails fail to parse, the system creates an **Activity** (warning) on the most recent failed record, assigned to the admin user. This alerts you that Etsy may have changed their email format.

---

## 9. Dashboard and Reporting

Navigate to **Etsy > Dashboard** to see order analytics.

### Graph View

Bar chart showing order revenue over time (grouped by month). Use the **Group By** options to segment by:
- **Shop** -- compare revenue across shops
- **Date (Month)** -- see monthly trends

### Pivot View

Switch to pivot view (toggle in the top-right) for a cross-tabulation of:
- Rows: Etsy Shop
- Columns: Order Date (by month)
- Measure: Total Amount

You can drag and drop fields to customize the pivot layout.

---

## 10. Importing Historical Orders

To bulk-import orders from an Excel file (e.g., exported from Google Sheets):

1. Navigate to **Etsy > Import Orders**.
2. Click **Upload** and select your .xlsx file.
3. Click **Import Orders**.
4. The status field shows progress: imported count, skipped (duplicates), and errors.

### Excel format

The file must have 34 columns matching the original Google Sheets layout:

| Column | Field |
|--------|-------|
| A (0) | Transaction ID |
| B (1) | Image URL |
| C (2) | Image formula (ignored) |
| D (3) | Date |
| E (4) | Note from Buyer |
| F (5) | Gift Message |
| G (6) | Personalisation |
| H (7) | SKU |
| I (8) | Shop |
| J (9) | Order ID |
| K-S (10-18) | Shipping: Name, Address1, Address2, City, State, ZIP, Country, Phone, Email |
| T (19) | Product Name |
| U-Y (20-24) | Option, Color, Size, Side, Face Mask Size |
| Z (25) | Quantity |
| AA-AB (26-27) | Design Link Front, Design Link Back |
| AC-AF (28-33) | Shipping Service, Processing Time, Shipping Cost, Price, Discount Code, Subtotal |

### Notes

- A header row is automatically detected and skipped.
- Duplicate orders (by Order ID) are skipped.
- Rows are grouped by Order ID -- multiple rows with the same Order ID become multiple order lines on one sale order.
- EUR prices are parsed automatically (handles comma decimals, euro sign).

---

## 11. Settings and Configuration

Navigate to **Settings** and scroll to (or search for) **Etsy Integration**.

### Gmail Connection

| Setting | Description | Default |
|---------|-------------|---------|
| Gmail Label | Gmail label that marks Etsy order emails | `ordertest2` |
| Gmail Client ID | OAuth2 Client ID from Google Cloud Console | (required) |
| Gmail Client Secret | OAuth2 Client Secret | (required) |
| Gmail Refresh Token | Auto-filled after authorization | (auto) |

### Buttons

- **Authorize Gmail** -- Starts the OAuth2 flow for first-time Gmail setup. Redirects to Google, then back to Odoo with the refresh token stored automatically.
- **Test Connection** -- Verifies the stored credentials work. Shows the connected email address on success.

### Cron Schedule

The fetch interval (default: 10 minutes) is configured in:
**Settings > Technical > Automation > Scheduled Actions > "Etsy: Fetch Order Emails"**

---

## 12. How It Works

### Email Processing Pipeline

```
Gmail Inbox (label:ordertest2)
    |
    v  [Every 10 minutes]
Gmail API: fetch emails with label
    |
    v
Email Parser: extract 34 fields per transaction
    |
    v
Order Creator:
    - Find or create customer (by email > name+zip)
    - Find or create product (by name)
    - Find or create shop (by name)
    - Create sale.order + order lines
    |
    v
Email Log: record result (success/failed/skipped)
    |
    v
Gmail API: remove label from processed emails
```

### Multi-Item Orders

When an Etsy order contains multiple items, the email has multiple "Transaction ID" blocks. The parser splits these and creates one sale.order.line per transaction. Example:

- **Order #3710809073** (Shop: Sven)
  - Line 1: Bow And Arrow Couple Fake Tattoo (Transaction 4627028509)
  - Line 2: Bow And Arrow Couple Fake Tattoo (Transaction 4610631464)

### Label Management

After processing, the Gmail label is automatically removed from emails. This means:
- Emails are only processed once.
- If you re-apply the label to an email, it will be fetched again but skipped (deduplication by Transaction ID prevents duplicates).

---

## 13. FAQ

**Q: An order is missing. What do I check?**
A: Go to **Etsy > Email Log** and look for the email. If status is "failed", read the error message. If the email isn't listed at all, verify the Gmail label is correct in Settings.

**Q: Can I re-process a failed email?**
A: Yes. Open the failed email log entry and click **Retry Parse**.

**Q: How do I add a new Etsy shop?**
A: Shops are created automatically when a new shop name appears in an order email. No manual setup needed.

**Q: What happens if Gmail is temporarily unavailable?**
A: The cron logs a warning and retries on the next cycle (10 minutes later). No data is lost.

**Q: Can I import orders from the old Google Sheets?**
A: Yes. Export the sheet as .xlsx and use **Etsy > Import Orders**. Duplicates are automatically skipped.

**Q: Why are some prices showing as 0.00?**
A: The price extraction depends on specific email format patterns. If the "Item price:" line is formatted differently in some emails, the regex may not match. Check the raw email body in the Email Log to diagnose.

**Q: How do I stop the automatic email fetching?**
A: Go to **Settings > Technical > Automation > Scheduled Actions**, find "Etsy: Fetch Order Emails", and uncheck **Active**.

**Q: Who can access Etsy data?**
A: All internal Odoo users can view Etsy orders, shops, and email log summaries. Only **Sales Managers** can modify shop/log records, access raw email content, or run the import wizard.
