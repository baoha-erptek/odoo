# Research: Operational Dashboard, Design File Workflow, Multi-Channel Foundation

## R1: Dashboard View Pattern -- Editable List vs Custom Widget

**Decision**: Use Odoo's standard `tree` view with `editable="top"` for inline editing of fulfillment fields (columns A-F).

**Rationale**: Odoo 19 tree views support inline editing natively. Fields marked as `readonly` in the view definition auto-populate from order data (columns G-T), while fulfillment fields remain editable. This avoids custom JavaScript widgets.

**Alternatives considered**:
- Custom OWL dashboard component: More flexible but breaks Odoo-native principle, harder to maintain, requires JS testing
- Separate form for fulfillment fields: Extra clicks for operators, slower workflow

## R2: Design File Storage -- ir.attachment vs Binary Field

**Decision**: Use a dedicated `order.design.file` model with Binary fields for design_file and preview_file, plus ir.attachment integration for download links.

**Rationale**: A dedicated model allows multiple files per order line, independent approval tracking per file, and query-efficient filtering (e.g., "all pending files"). Using Binary fields within the model keeps the data co-located with approval metadata, while Odoo automatically stores binary data in the filestore.

**Alternatives considered**:
- ir.attachment only (linked via res_model/res_id): No structured approval workflow, harder to track status per file
- External storage (S3/Google Drive): Adds complexity, requires credentials management, breaks offline capability

## R3: Design Approval Status Values

**Decision**: Use Vietnamese labels with English technical values: `cho_duyet` (Cho duyet / Pending Review), `duyet` (Duyet / Approved), `can_chinh_lai` (Can chinh lai / Needs Adjustment).

**Rationale**: Matches the business terminology from the system architecture diagram. Technical values use snake_case Vietnamese for consistency with the team's daily language.

**Alternatives considered**:
- English-only values (pending/approved/rejected): Team works in Vietnamese, creates cognitive mismatch
- Spec 002's values (pending/in_progress/completed): Different semantics -- "completed" implies production is done, but "approved" means design is reviewed

## R4: Sales Channel Implementation -- Selection Field vs Model

**Decision**: Use a Selection field on sale.order (`sales_channel`) with hardcoded values: etsy/amazon/website/other.

**Rationale**: Simplest approach for 3-4 known channels. No extra model, no joins, fast filtering. New channels can be added by extending the Selection field in future modules.

**Alternatives considered**:
- Many2one to channel.connector model: Over-engineering for 3-4 channels, adds a model to maintain
- Tags/labels: Not suitable for exclusive classification (an order comes from one channel)

## R5: Fulfillment Status -- Selection Field vs Workflow Engine

**Decision**: Use a Selection field on sale.order with 7 predefined statuses.

**Rationale**: The fulfillment workflow is linear and manually managed. No automated state transitions are needed (that's Spec 004 scope). A simple selection field with dashboard filters is sufficient.

**Alternatives considered**:
- Odoo's native sale.order state field: Cannot be extended in CE without conflicts; the existing states (draft/sent/sale/done/cancel) serve a different purpose
- Custom workflow engine: Over-engineering for a manually-managed status

## R6: Performance -- Handling 17,000+ Orders in Dashboard

**Decision**: Rely on Odoo's built-in server-side pagination (default 80 records/page) with database indexes on filter fields.

**Rationale**: Odoo's tree view handles pagination natively. Adding indexes on `fulfillment_status`, `sales_channel`, `pic_user_id`, and `order_priority` ensures filter/sort operations stay fast at 17K+ records.

**Alternatives considered**:
- Custom lazy-loading widget: Unnecessary complexity, Odoo handles this
- Archiving old orders: Would hide data from reports

## R7: Production Team Security Group

**Decision**: Create a new group `etsy_integration.group_production_team` under the Etsy Integration module category, inheriting from `base.group_user`.

**Rationale**: Separates design approval permissions from sales/admin roles. Production team members need to view orders and approve/reject designs but should not have full sales manager access.

**Alternatives considered**:
- Reuse sale_team.group_sale_manager: Too broad, gives access to all sales configurations
- No group (any user can approve): Breaks security-by-default principle
