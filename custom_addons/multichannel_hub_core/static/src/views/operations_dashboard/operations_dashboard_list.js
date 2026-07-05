/** @odoo-module **/
// P-KPI-01 — Operations Dashboard KPI band (mockup-v3 plan).
// js_class list view: standard ListRenderer with a KPI card band above the
// table. Counts come from sale.order.get_operations_dashboard_kpis()
// (ACL-scoped server side).
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class OperationsKpiBand extends Component {
    static template = "multichannel_hub_core.OperationsKpiBand";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ kpis: [] });
        onWillStart(async () => {
            this.state.kpis = await this.orm.call(
                "sale.order",
                "get_operations_dashboard_kpis",
                []
            );
        });
    }
}

export class OperationsDashboardListRenderer extends ListRenderer {
    static template = "multichannel_hub_core.OperationsDashboardListRenderer";
    static components = {
        ...ListRenderer.components,
        OperationsKpiBand,
    };
}

export const operationsDashboardListView = {
    ...listView,
    Renderer: OperationsDashboardListRenderer,
};

registry
    .category("views")
    .add("operations_dashboard_list", operationsDashboardListView);
