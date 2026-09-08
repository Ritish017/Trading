"""
APEX Safety & Real-Capital Protection Subsystem
===============================================
Enforces non-negotiable safety invariants:
1. LIVE_ORDER_ALLOWED is permanently False.
2. Intercepts and blocks any attempt to submit live capital orders to broker APIs.
3. Forbids synthetic market-data fallback during live paper experiments.
4. Asserts research freeze configuration integrity before execution starts.
"""

import logging
from typing import Any, Dict, Optional
from backend.app.signal_engine.version_freeze import (
    CONFIGURATION_HASH,
    STRATEGY_VERSION,
    SIGNAL_ENGINE_VERSION,
    COST_MODEL_VERSION,
    compute_configuration_hash,
    FROZEN_RESEARCH_CONFIGURATION,
)

logger = logging.getLogger(__name__)

# Absolute constant: Live money orders are strictly forbidden
LIVE_ORDER_ALLOWED: bool = False
LIVE_TRADING_ENABLED: bool = False


class LiveOrderForbiddenSecurityError(RuntimeError):
    """Raised when any code path attempts to place a real-money broker order."""
    pass


class SyntheticDataForbiddenError(RuntimeError):
    """Raised when synthetic or random data is substituted during a live experiment."""
    pass


class ConfigurationDriftError(RuntimeError):
    """Raised when active configuration does not match the frozen research hash."""
    pass


class LivePaperSafetyGuard:
    """
    Guards the execution runtime against unauthorized real-capital deployment,
    unauthorized parameter changes, or synthetic market data masquerading.
    """

    @staticmethod
    def assert_paper_mode_enforced() -> None:
        """Asserts that live order execution is blocked."""
        if LIVE_ORDER_ALLOWED:
            raise LiveOrderForbiddenSecurityError(
                "CRITICAL SECURITY INVARIANT VIOLATION: LIVE_ORDER_ALLOWED is True. "
                "APEX Quant Lab is certified exclusively for paper-trading."
            )
        if LIVE_TRADING_ENABLED:
            raise LiveOrderForbiddenSecurityError(
                "CRITICAL SECURITY INVARIANT VIOLATION: LIVE_TRADING_ENABLED is True."
            )

    @staticmethod
    def block_live_broker_order(symbol: str, side: str, quantity: int, broker: str = "UPSTOX") -> None:
        """
        Hard block invoked by broker gateways to prevent live order submission.
        Raises LiveOrderForbiddenSecurityError immediately.
        """
        msg = (
            f"[SECURITY ALERT] Attempted live order execution blocked: "
            f"Broker={broker}, Symbol={symbol}, Side={side}, Qty={quantity}. "
            f"Live trading is strictly prohibited."
        )
        logger.critical(msg)
        raise LiveOrderForbiddenSecurityError(msg)

    @staticmethod
    def verify_frozen_configuration() -> Dict[str, Any]:
        """
        Validates that the current configuration matches the certified frozen hash.
        """
        computed_hash = compute_configuration_hash(FROZEN_RESEARCH_CONFIGURATION)
        if computed_hash != CONFIGURATION_HASH:
            raise ConfigurationDriftError(
                f"Configuration drift detected! Expected {CONFIGURATION_HASH}, got {computed_hash}"
            )
        return {
            "status": "VERIFIED_FROZEN",
            "configuration_hash": CONFIGURATION_HASH,
            "strategy_version": STRATEGY_VERSION,
            "signal_engine_version": SIGNAL_ENGINE_VERSION,
            "cost_model_version": COST_MODEL_VERSION,
        }

    @staticmethod
    def assert_authentic_market_data(data_provenance: str) -> None:
        """
        Verifies that market data is authentic. Forbids SYNTHETIC or DEV_MOCK
        during authentic live paper sessions.
        """
        if data_provenance in ("SYNTHETIC", "DEV_MOCK", "RANDOM"):
            raise SyntheticDataForbiddenError(
                f"Synthetic market data is strictly prohibited during live paper session. "
                f"Provenance received: {data_provenance}"
            )
