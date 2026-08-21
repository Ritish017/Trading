import time
import logging
from typing import Dict, Any, Optional, Tuple
from backend.app.market_data.corporate_actions.models import (
    AnomalyClassification,
    CorporateActionType,
)
from backend.app.market_data.corporate_actions.registry import (
    CorporateActionRegistry,
    corporate_action_registry,
)

logger = logging.getLogger(__name__)

class MarketDataIntegrityGuard:
    """
    Market Data Integrity & Anomaly Classification Guard.
    Enforces strict timestamp freshness, provenance verification, price sanity, and corporate action validation.
    """

    FRESHNESS_THRESHOLD_SECONDS = 120.0 # 2 minutes for live ticks

    def __init__(self, registry: Optional[CorporateActionRegistry] = None):
        self.registry = registry or corporate_action_registry

    def calculate_data_age(self, provider_timestamp: float) -> float:
        """Calculate data age in seconds from current time."""
        now = time.time()
        if provider_timestamp > 1e11: # milliseconds
            provider_timestamp /= 1000.0
        return max(0.0, round(now - provider_timestamp, 2))

    def classify_price_movement(
        self,
        symbol: str,
        current_price: float,
        previous_close: Optional[float],
        timestamp: Optional[float] = None
    ) -> Tuple[AnomalyClassification, str]:
        """
        Classifies price movement against historical continuity to detect splits, bonuses, or corruption.
        """
        if previous_close is None or previous_close <= 0 or current_price <= 0:
            return AnomalyClassification.NORMAL_MARKET_MOVE, "No previous close available for comparison."

        ratio = current_price / previous_close
        pct_change = abs((current_price - previous_close) / previous_close) * 100.0

        # Normal market move within 20% circuit limit
        if 0.80 <= ratio <= 1.20:
            return AnomalyClassification.NORMAL_MARKET_MOVE, f"Normal intraday fluctuation ({pct_change:.2f}%)."

        # Check if symbol has an active corporate action around this timestamp
        actions = self.registry.get_actions(symbol)
        ts = timestamp or time.time()

        for act in actions:
            # Check if this jump matches the corporate action ratio
            expected_ratio = 1.0 / act.adjustment_factor
            if abs(ratio - expected_ratio) < 0.15:
                if act.action_type == CorporateActionType.BONUS:
                    return AnomalyClassification.BONUS, f"Detected 1:{int(act.adjustment_factor - 1)} Bonus Action matching {act.ex_date}."
                elif act.action_type == CorporateActionType.SPLIT:
                    return AnomalyClassification.SPLIT, f"Detected Stock Split matching {act.ex_date}."
                return AnomalyClassification.CORPORATE_ACTION, f"Corporate action {act.action_type} verified."

        # If price dropped by ~50% or doubled without corporate action, check for common errors
        if ratio < 0.60 or ratio > 1.60:
            logger.warning(f"[INTEGRITY GUARD ALERT] Severe unexplained price jump for {symbol}: prev={previous_close}, current={current_price}, ratio={ratio:.2f}")
            return AnomalyClassification.PRICE_INTEGRITY_ERROR, f"Severe price anomaly ({pct_change:.1f}%) with no corresponding corporate action."

        return AnomalyClassification.NORMAL_MARKET_MOVE, f"High volatility move ({pct_change:.1f}%)."

    def validate_live_claim(
        self,
        provider: str,
        is_provider_authenticated: bool,
        is_provider_connected: bool,
        provider_timestamp: float,
        current_price: float,
        previous_close: Optional[float]
    ) -> Dict[str, Any]:
        """
        Validates whether the UI is permitted to claim 'LIVE • UPSTOX'.
        Returns structured verification with honest display status.
        """
        data_age = self.calculate_data_age(provider_timestamp)
        is_fresh = data_age <= self.FRESHNESS_THRESHOLD_SECONDS

        # Classify price movement
        classification, reason = self.classify_price_movement(
            symbol="GENERIC",
            current_price=current_price,
            previous_close=previous_close,
            timestamp=provider_timestamp
        )

        is_simulated = provider.upper() in ("MOCK", "DEV_MOCK", "SIMULATED")
        is_anomaly = classification == AnomalyClassification.PRICE_INTEGRITY_ERROR

        if is_simulated:
            provenance_status = "DEV_MOCK"
            can_claim_live = False
            display_label = "SIMULATED • DEV MOCK"
        elif not is_provider_authenticated or not is_provider_connected:
            provenance_status = "DISCONNECTED"
            can_claim_live = False
            display_label = "DISCONNECTED"
        elif is_anomaly:
            provenance_status = "DATA_INTEGRITY_ERROR"
            can_claim_live = False
            display_label = "DATA INTEGRITY ERROR"
        elif not is_fresh:
            provenance_status = "STALE"
            can_claim_live = False
            display_label = "STALE FEED"
        else:
            provenance_status = "AUTHENTIC_LIVE"
            can_claim_live = True
            display_label = f"LIVE • {provider.upper()}"

        return {
            "can_claim_live": can_claim_live,
            "provenance_status": provenance_status,
            "display_label": display_label,
            "data_age_seconds": data_age,
            "is_fresh": is_fresh,
            "anomaly_classification": classification.value,
            "classification_reason": reason
        }

    def validate_cross_provider(
        self,
        symbol: str,
        primary_price: float,
        reference_price: Optional[float],
        tolerance_pct: float = 5.0
    ) -> Tuple[bool, str]:
        """
        Cross-validates primary provider price against independent reference.
        Used strictly as an integrity check without silently replacing the primary provider.
        """
        if reference_price is None or reference_price <= 0:
            return True, "No reference price available for cross-validation."

        diff_pct = abs(primary_price - reference_price) / reference_price * 100.0
        if diff_pct > tolerance_pct:
            # Check if this difference corresponds to an unadjusted vs adjusted corporate action
            actions = self.registry.get_actions(symbol)
            if actions:
                for act in actions:
                    adjusted_ref = reference_price / act.adjustment_factor
                    if abs(primary_price - adjusted_ref) / adjusted_ref * 100.0 <= tolerance_pct:
                        return True, f"Cross-validation matched with corporate action {act.action_type} factor."

            return False, f"Cross-provider price divergence: Primary={primary_price}, Reference={reference_price} (Divergence: {diff_pct:.2f}% > {tolerance_pct}%)."

        return True, f"Cross-provider validation passed (Divergence: {diff_pct:.2f}%)."

# Global instance
market_data_integrity_guard = MarketDataIntegrityGuard()
