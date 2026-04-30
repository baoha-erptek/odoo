"""Tests for multichannel_hub_fulfillment module."""

from . import test_gearment_api_client
from . import test_phase1_install
# from . import test_phase1_db  # Disabled: P1-04 slice (out of P0-18b1 scope)
# from . import test_phase2_orm  # Disabled: depends on tracking.import.wizard (spec slice P1-05)
from . import test_gearment_api_log_db
# from . import test_gearment_adapter_orm  # Disabled: Phase 2 ORM tests (requires GEARMENT_* env vars)
# from . import test_gearment_adapter_phase1  # Disabled: Phase 3 live API tests (requires GEARMENT_* env vars + live API)

__all__ = [
    'test_gearment_api_client',
    'test_phase1_install',
    # 'test_phase1_db',  # Disabled: P1-04 slice (out of P0-18b1 scope)
    # 'test_phase2_orm',  # Disabled: depends on tracking.import.wizard (spec slice P1-05)
    'test_gearment_api_log_db',
    # 'test_gearment_adapter_orm',  # Disabled: Phase 2 ORM tests (requires GEARMENT_* env vars)
    # 'test_gearment_adapter_phase1',  # Disabled: Phase 3 live API tests (requires GEARMENT_* env vars + live API)
]
