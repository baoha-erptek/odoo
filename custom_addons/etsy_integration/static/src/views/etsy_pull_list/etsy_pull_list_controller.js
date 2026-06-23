import { useService } from "@web/core/utils/hooks";
import { SaleListView } from "@sale/views/sale_onboarding_list/sale_onboarding_list_view";

/**
 * Extends the Quotations/Orders onboarding list controller with a global
 * "Pull Etsy Orders" action. The button lives in the always-visible control
 * panel (next to "New"), not the row-selection action bar, so it is reachable
 * even on an empty list -- which is exactly when an operator wants to pull.
 */
export class EtsyPullListController extends SaleListView.Controller {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    async onPullEtsyOrders() {
        // action_pull_etsy_orders ignores any current selection; it pulls the
        // caller's Etsy shops and returns a display_notification client action.
        const action = await this.orm.call(
            "sale.order",
            "action_pull_etsy_orders",
            [[]],
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }
}
