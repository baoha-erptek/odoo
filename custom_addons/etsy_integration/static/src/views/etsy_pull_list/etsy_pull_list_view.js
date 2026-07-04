import { registry } from "@web/core/registry";
import { SaleListView } from "@sale/views/sale_onboarding_list/sale_onboarding_list_view";
import { EtsyPullListController } from "./etsy_pull_list_controller";

// Reuse the full sale onboarding list view (Renderer, model, file-upload
// behaviour) and only swap in our controller + button template. js_class
// "etsy_pull_list" is applied to the quotations/orders list via view XML.
export const etsyPullListView = {
    ...SaleListView,
    Controller: EtsyPullListController,
    buttonTemplate: "etsy_integration.EtsyPullListView.Buttons",
};

registry.category("views").add("etsy_pull_list", etsyPullListView);
