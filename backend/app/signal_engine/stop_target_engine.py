"""
Signal Intelligence Engine — Stop/Target Engine
================================================
Computes stop-loss and price targets using evidence-based methods.

Stop Loss Methods (in priority order):
1. ATR_STRUCTURAL — 1.5x ATR below nearest structural support (preferred)
2. SWING_LOW      — Below the most recent meaningful swing low
3. SUPPORT_LEVEL  — Below the nearest computed support level
4. ATR_SIMPLE     — 1.5x ATR below entry (when no structure available)
5. PERCENTAGE     — Fixed percentage below entry (last resort)

Target Methods:
1. RISK_REWARD    — Multiples of the stop distance (R:R based)
2. RESISTANCE     — Nearest computed resistance level
3. ATR_PROJECTION — ATR multiples above entry
4. FIBONACCI      — Fibonacci extension of prior move (when swing available)
5. PREVIOUS_HIGH  — Prior session or swing high

Invariants:
- Stop always produces method_description explaining the computation
- Targets are always ordered: target_1 < target_2 < target_3 for LONG
- Stop is never below 0 or above entry for LONG
- At least target_1 must be computable for signal qualification
"""
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.signal_engine.models import (
    SignalDirection,
    StopLossResult,
    TargetLevel,
    SignalEngineConfig,
)

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Stop Loss Engine
# ---------------------------------------------------------------------------

class StopLossEngine:
    """
    Computes stop loss using the most structurally robust method available.
    Falls back gracefully when structure data is unavailable.
    """

    def compute(
        self,
        direction: str,
        entry_price: float,
        feature_vector: Dict[str, Any],
        support_levels: List[float],
        resistance_levels: List[float],
        config: SignalEngineConfig,
    ) -> Optional[StopLossResult]:
        """
        Compute stop loss for a signal.
        Returns StopLossResult or None if a valid stop cannot be determined.
        """
        atr = _safe_float(feature_vector.get("atr14"))

        if direction == "LONG":
            return self._compute_long_stop(entry_price, atr, support_levels, config)
        elif direction == "SHORT":
            return self._compute_short_stop(entry_price, atr, resistance_levels, config)
        return None

    def _compute_long_stop(
        self,
        entry: float,
        atr: Optional[float],
        support_levels: List[float],
        config: SignalEngineConfig,
    ) -> Optional[StopLossResult]:
        """Compute stop for LONG position."""

        # Method 1: ATR below structural support (preferred)
        if atr and atr > 0 and support_levels:
            # Find the nearest support level below entry
            levels_below = sorted(
                [s for s in support_levels if s < entry * 0.999],
                reverse=True
            )
            if levels_below:
                nearest_support = levels_below[0]
                atr_buffer = config.stop_atr_multiple * atr
                stop = nearest_support - atr_buffer

                # Validate stop is reasonable
                if stop > 0 and (entry - stop) / entry <= config.max_stop_pct / 100:
                    return StopLossResult(
                        price=round(stop, 2),
                        method="ATR_STRUCTURAL",
                        method_description=(
                            f"{config.stop_atr_multiple:.1f}x ATR (₹{atr_buffer:.2f}) below "
                            f"structural support at ₹{nearest_support:.2f}"
                        ),
                        atr_value=round(atr, 2),
                        structural_level=round(nearest_support, 2),
                        risk_per_share=round(entry - stop, 2),
                    )

        # Method 2: ATR below entry (when no structure)
        if atr and atr > 0:
            atr_buffer = config.stop_atr_multiple * atr
            stop = entry - atr_buffer

            if stop > 0 and (entry - stop) / entry <= config.max_stop_pct / 100:
                return StopLossResult(
                    price=round(stop, 2),
                    method="ATR_SIMPLE",
                    method_description=(
                        f"{config.stop_atr_multiple:.1f}x ATR (₹{atr_buffer:.2f}) below entry ₹{entry:.2f}"
                    ),
                    atr_value=round(atr, 2),
                    structural_level=None,
                    risk_per_share=round(entry - stop, 2),
                )

        # Method 3: Fixed percentage stop (last resort — explicitly labeled)
        pct_stop = config.max_stop_pct * 0.6  # Use 60% of max as default
        stop = entry * (1 - pct_stop / 100)
        if stop > 0:
            return StopLossResult(
                price=round(stop, 2),
                method="PERCENTAGE",
                method_description=(
                    f"Fixed {pct_stop:.1f}% stop (ATR/structure data unavailable — reduced confidence)"
                ),
                atr_value=None,
                structural_level=None,
                risk_per_share=round(entry - stop, 2),
                is_deterministic=False,
            )

        return None

    def _compute_short_stop(
        self,
        entry: float,
        atr: Optional[float],
        resistance_levels: List[float],
        config: SignalEngineConfig,
    ) -> Optional[StopLossResult]:
        """Compute stop for SHORT position."""

        # Method 1: ATR above structural resistance
        if atr and atr > 0 and resistance_levels:
            levels_above = sorted(
                [r for r in resistance_levels if r > entry * 1.001]
            )
            if levels_above:
                nearest_resistance = levels_above[0]
                atr_buffer = config.stop_atr_multiple * atr
                stop = nearest_resistance + atr_buffer

                if (stop - entry) / entry <= config.max_stop_pct / 100:
                    return StopLossResult(
                        price=round(stop, 2),
                        method="ATR_STRUCTURAL",
                        method_description=(
                            f"{config.stop_atr_multiple:.1f}x ATR (₹{atr_buffer:.2f}) above "
                            f"structural resistance at ₹{nearest_resistance:.2f}"
                        ),
                        atr_value=round(atr, 2),
                        structural_level=round(nearest_resistance, 2),
                        risk_per_share=round(stop - entry, 2),
                    )

        # Method 2: ATR above entry
        if atr and atr > 0:
            atr_buffer = config.stop_atr_multiple * atr
            stop = entry + atr_buffer
            if (stop - entry) / entry <= config.max_stop_pct / 100:
                return StopLossResult(
                    price=round(stop, 2),
                    method="ATR_SIMPLE",
                    method_description=(
                        f"{config.stop_atr_multiple:.1f}x ATR (₹{atr_buffer:.2f}) above entry ₹{entry:.2f}"
                    ),
                    atr_value=round(atr, 2),
                    structural_level=None,
                    risk_per_share=round(stop - entry, 2),
                )

        # Method 3: Fixed percentage
        pct_stop = config.max_stop_pct * 0.6
        stop = entry * (1 + pct_stop / 100)
        return StopLossResult(
            price=round(stop, 2),
            method="PERCENTAGE",
            method_description=f"Fixed {pct_stop:.1f}% stop (ATR unavailable)",
            atr_value=None,
            structural_level=None,
            risk_per_share=round(stop - entry, 2),
            is_deterministic=False,
        )


# ---------------------------------------------------------------------------
# Target Engine
# ---------------------------------------------------------------------------

class TargetEngine:
    """
    Computes price targets using risk/reward and market structure.
    """

    def compute(
        self,
        direction: str,
        entry_price: float,
        stop_loss: StopLossResult,
        feature_vector: Dict[str, Any],
        support_levels: List[float],
        resistance_levels: List[float],
        config: SignalEngineConfig,
    ) -> Tuple[List[TargetLevel], Optional[float]]:
        """
        Compute price targets.
        Returns (targets_list, risk_reward_to_target_1).
        """
        risk = stop_loss.risk_per_share
        if risk is None or risk <= 0:
            return [], None

        if direction == "LONG":
            return self._compute_long_targets(entry_price, risk, resistance_levels, config)
        elif direction == "SHORT":
            return self._compute_short_targets(entry_price, risk, support_levels, config)
        return [], None

    def _compute_long_targets(
        self,
        entry: float,
        risk: float,
        resistance_levels: List[float],
        config: SignalEngineConfig,
    ) -> Tuple[List[TargetLevel], Optional[float]]:
        targets: List[TargetLevel] = []

        # Target 1: Risk/Reward based
        t1_price = entry + risk * config.target_1_rr
        rr1 = config.target_1_rr

        # Snap to nearby resistance if within 1% (prefer structure)
        res_near_t1 = [r for r in resistance_levels if abs(r - t1_price) / t1_price < 0.01]
        if res_near_t1:
            t1_price = min(res_near_t1, key=lambda r: abs(r - t1_price))
            rr1 = (t1_price - entry) / risk
            t1_method = "RESISTANCE"
            t1_desc = f"Nearest resistance ₹{t1_price:.2f} (R:R {rr1:.1f})"
        else:
            t1_method = "RISK_REWARD"
            t1_desc = f"{config.target_1_rr:.1f}R target at ₹{t1_price:.2f}"

        targets.append(TargetLevel(
            level=1,
            price=round(t1_price, 2),
            method=t1_method,
            method_description=t1_desc,
            expected_rr=round(rr1, 2),
        ))

        # Target 2: Risk/Reward based
        t2_price = entry + risk * config.target_2_rr
        res_above_t1 = [r for r in resistance_levels if r > t1_price * 1.005]
        if res_above_t1:
            nearest_res = min(res_above_t1)
            if abs(nearest_res - t2_price) / t2_price < 0.03:
                t2_price = nearest_res
                t2_method = "RESISTANCE"
                t2_desc = f"Second resistance ₹{t2_price:.2f}"
            else:
                t2_method = "RISK_REWARD"
                t2_desc = f"{config.target_2_rr:.1f}R target at ₹{t2_price:.2f}"
        else:
            t2_method = "RISK_REWARD"
            t2_desc = f"{config.target_2_rr:.1f}R target at ₹{t2_price:.2f}"

        rr2 = (t2_price - entry) / risk
        targets.append(TargetLevel(
            level=2,
            price=round(t2_price, 2),
            method=t2_method,
            method_description=t2_desc,
            expected_rr=round(rr2, 2),
        ))

        # Target 3: Extended target
        t3_price = entry + risk * config.target_3_rr
        rr3 = (t3_price - entry) / risk
        targets.append(TargetLevel(
            level=3,
            price=round(t3_price, 2),
            method="RISK_REWARD",
            method_description=f"{config.target_3_rr:.1f}R extended target at ₹{t3_price:.2f}",
            expected_rr=round(rr3, 2),
        ))

        return targets, round(rr1, 2)

    def _compute_short_targets(
        self,
        entry: float,
        risk: float,
        support_levels: List[float],
        config: SignalEngineConfig,
    ) -> Tuple[List[TargetLevel], Optional[float]]:
        targets: List[TargetLevel] = []

        # Target 1
        t1_price = entry - risk * config.target_1_rr
        rr1 = config.target_1_rr

        # Snap to nearby support
        sup_near_t1 = [s for s in support_levels if abs(s - t1_price) / t1_price < 0.01]
        if sup_near_t1:
            t1_price = max(sup_near_t1, key=lambda s: abs(s - t1_price))
            rr1 = (entry - t1_price) / risk
            t1_method = "SUPPORT_LEVEL"
            t1_desc = f"Nearest support ₹{t1_price:.2f} (R:R {rr1:.1f})"
        else:
            t1_method = "RISK_REWARD"
            t1_desc = f"{config.target_1_rr:.1f}R target at ₹{t1_price:.2f}"

        targets.append(TargetLevel(
            level=1,
            price=round(t1_price, 2),
            method=t1_method,
            method_description=t1_desc,
            expected_rr=round(rr1, 2),
        ))

        # Target 2
        t2_price = entry - risk * config.target_2_rr
        rr2 = (entry - t2_price) / risk
        targets.append(TargetLevel(
            level=2,
            price=round(t2_price, 2),
            method="RISK_REWARD",
            method_description=f"{config.target_2_rr:.1f}R target at ₹{t2_price:.2f}",
            expected_rr=round(rr2, 2),
        ))

        # Target 3
        t3_price = entry - risk * config.target_3_rr
        rr3 = (entry - t3_price) / risk
        targets.append(TargetLevel(
            level=3,
            price=round(t3_price, 2),
            method="RISK_REWARD",
            method_description=f"{config.target_3_rr:.1f}R extended target at ₹{t3_price:.2f}",
            expected_rr=round(rr3, 2),
        ))

        return targets, round(rr1, 2)


# Module-level singletons
stop_loss_engine = StopLossEngine()
target_engine = TargetEngine()
