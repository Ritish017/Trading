"""
Unit tests for Live Paper Safety Invariants & Live Order Interception.
"""

import pytest
from backend.app.live_paper.safety import (
    LIVE_ORDER_ALLOWED,
    LivePaperSafetyGuard,
    LiveOrderForbiddenSecurityError,
    SyntheticDataForbiddenError,
)
from backend.app.signal_engine.version_freeze import (
    CONFIGURATION_HASH,
    STRATEGY_VERSION,
)


def test_live_order_allowed_permanently_false():
    assert LIVE_ORDER_ALLOWED is False
    LivePaperSafetyGuard.assert_paper_mode_enforced()


def test_live_broker_order_interception_raises_security_error():
    with pytest.raises(LiveOrderForbiddenSecurityError):
        LivePaperSafetyGuard.block_live_broker_order("RELIANCE.NS", "BUY", 50, broker="UPSTOX")


def test_frozen_configuration_integrity():
    res = LivePaperSafetyGuard.verify_frozen_configuration()
    assert res["status"] == "VERIFIED_FROZEN"
    assert res["configuration_hash"] == CONFIGURATION_HASH
    assert res["strategy_version"] == STRATEGY_VERSION


def test_synthetic_data_forbidden_during_live_experiment():
    with pytest.raises(SyntheticDataForbiddenError):
        LivePaperSafetyGuard.assert_authentic_market_data("SYNTHETIC")

    with pytest.raises(SyntheticDataForbiddenError):
        LivePaperSafetyGuard.assert_authentic_market_data("DEV_MOCK")

    # Authentic provenance should pass without error
    LivePaperSafetyGuard.assert_authentic_market_data("AUTHENTIC_LIVE")
    LivePaperSafetyGuard.assert_authentic_market_data("AUTHENTIC_HISTORICAL")
