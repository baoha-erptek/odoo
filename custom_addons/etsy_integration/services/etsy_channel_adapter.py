"""EtsyChannelAdapter Protocol + HealthStatus enum (P0-16a).

`EtsyChannelAdapter` is the duck-typed interface every channel-source
adapter satisfies. P0-16b's `EtsyApiAdapter` and the future
`EtsyEmailAdapter` (post-rename to `etsy_channel_email`) both implement
it. `EtsyOrderIngestor` (P0-16b) selects the adapter at run-time based
on `etsy.shop.sync_mode` (per ADR-002, two values: `email_only` /
`api_only`).

Marked `@runtime_checkable` so `isinstance(obj, EtsyChannelAdapter)` is
a cheap structural check during ingestor wiring; concrete adapters do
NOT inherit from this Protocol — they only need to expose the two
methods with matching shapes.

Module placement: lives in `etsy_integration/services/`. See
`specs/005-etsy-api-channel/findings.md` 2026-04-28 for why the spec's
original `multichannel_hub_core` placement was overruled.

Reference: `specs/005-etsy-api-channel/data-model.md` lines 260-269.
"""

from datetime import datetime
from enum import Enum
from typing import Iterator, Protocol, runtime_checkable

from .etsy_order_payload import EtsyOrderPayload


class HealthStatus(Enum):
    """Adapter-level liveness signal returned by `health_check`.

    `OK`: adapter can fetch new orders; recent calls succeeded.
    `DEGRADED`: adapter is reachable but rate-limited / returning warnings.
    `DOWN`: adapter cannot reach Etsy or is unauthorized; orchestrator
            should pause sync and surface to operator.
    """

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@runtime_checkable
class EtsyChannelAdapter(Protocol):
    """Channel-source adapter contract.

    Implementations fetch new orders since a watermark and report their
    own health. The orchestrator (`EtsyOrderSyncer`, P0-16c) is the only
    caller; do not invoke adapter methods directly from views or
    controllers.

    Note on `@runtime_checkable`: `isinstance(obj, EtsyChannelAdapter)`
    only verifies that `obj` exposes attributes named `fetch_new_orders`
    and `health_check` — Python does NOT validate the parameter or
    return signatures match. Concrete implementations MUST adhere to
    the signatures below; runtime-checking is a wiring sanity check, not
    a type contract.
    """

    def fetch_new_orders(
        self, shop_id: int, since: datetime
    ) -> Iterator[EtsyOrderPayload]:
        """Yield canonical payloads for receipts modified after `since`.

        Implementation may paginate internally and yield lazily; callers
        rely on the iterator semantics to advance the cursor only as
        each payload is consumed successfully.
        """
        ...

    def health_check(self, shop_id: int) -> HealthStatus:
        """Cheap liveness probe — does NOT fetch orders.

        Used by the recovery cron to flip a shop back online once the
        underlying source recovers.
        """
        ...
