"""
Signal Intelligence Engine — NO-TRADE Classification Engine
============================================================
Handles deterministic NO-TRADE classification, explicit audit trail generation,
and rejection intelligence.

Principles:
- NO-TRADE is an active, first-class decision, never a silent omission or error
- Every rejection records the specific gate failed, threshold, and actual metric
- Categorizes failure reasons into structured categories for dashboard analytics
- Formulates constructive advice on what condition must change for the setup to qualify
"""
from collections import Counter
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.signal_engine.models import (
    DataProvenance,
    RejectionRecord,
    SignalDecision,
    SignalDirection,
    SignalQualityGrade,
    SignalState,
    SignalType,
    StrategyVote,
    ValidationGate,
)

logger = logging.getLogger(__name__)


class NoTradeCategory:
    DATA_INTEGRITY = "DATA_INTEGRITY"
    RISK_REWARD = "RISK_REWARD"
    LIQUIDITY = "LIQUIDITY"
    REGIME_MISALIGNMENT = "REGIME_MISALIGNMENT"
    STRATEGY_CONFLICT = "STRATEGY_CONFLICT"
    MTF_DISCORD = "MTF_DISCORD"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    ENTRY_STOP_INVALID = "ENTRY_STOP_INVALID"


class NoTradeEngine:
    """
    Classifies rejected setups, produces structured RejectionRecords,
    and aggregates rejection analytics.
    """

    def __init__(self):
        self._rejection_reasons_counter: Counter[str] = Counter()
        self._category_counter: Counter[str] = Counter()

    def classify_gate_failure(
        self,
        gate_id: str,
    ) -> str:
        """Categorize a validation gate failure into an analytics bucket."""
        if "DATA" in gate_id or "FRESHNESS" in gate_id:
            return NoTradeCategory.DATA_INTEGRITY
        elif "RISK_REWARD" in gate_id:
            return NoTradeCategory.RISK_REWARD
        elif "LIQUIDITY" in gate_id:
            return NoTradeCategory.LIQUIDITY
        elif "REGIME" in gate_id:
            return NoTradeCategory.REGIME_MISALIGNMENT
        elif "CONFLUENCE" in gate_id or "STRATEGY" in gate_id:
            return NoTradeCategory.STRATEGY_CONFLICT
        elif "MTF" in gate_id or "TIMEFRAME" in gate_id:
            return NoTradeCategory.MTF_DISCORD
        elif "DRAWDOWN" in gate_id or "LOSS" in gate_id:
            return NoTradeCategory.CIRCUIT_BREAKER
        else:
            return NoTradeCategory.ENTRY_STOP_INVALID

    def build_no_trade_decision(
        self,
        symbol: str,
        gate_id: str,
        reason: str,
        actual_value: Optional[Any] = None,
        threshold_value: Optional[Any] = None,
        strategy_votes: Optional[List[StrategyVote]] = None,
        confluence_result: Optional[Any] = None,
        validation_gates: Optional[List[ValidationGate]] = None,
        timeframe: str = "15m",
    ) -> Tuple[SignalDecision, RejectionRecord]:
        """
        Creates a pair of (SignalDecision(NO_TRADE), RejectionRecord) with complete explainability.
        """
        category = self.classify_gate_failure(gate_id)
        self._category_counter[category] += 1
        self._rejection_reasons_counter[gate_id] += 1

        advice = self._generate_actionable_advice(gate_id, actual_value, threshold_value)

        rejection_reason_str = f"[{category}] {gate_id}: {reason}"
        if advice:
            rejection_reason_str += f" — Action: {advice}"

        rejection_rec = RejectionRecord(
            symbol=symbol,
            gate_failed=gate_id,
            gate_type="HARD",
            reason=reason,
            evidence=advice,
            actual_value=actual_value,
            threshold_value=threshold_value,
            validation_gates=validation_gates or [],
        )

        decision = SignalDecision(
            symbol=symbol,
            exchange="NSE",
            direction=SignalDirection.NO_TRADE,
            signal_type=SignalType.NO_TRADE,
            timeframe=timeframe,
            state=SignalState.REJECTED,
            quality_grade=SignalQualityGrade.NO_TRADE,
            opportunity_score=0.0,
            confidence=0.0,
            strategy_votes=strategy_votes or [],
            confluence_result=confluence_result,
            validation_gates=validation_gates or [],
            rejection_reasons=[rejection_reason_str],
            provenance=DataProvenance.UNAVAILABLE,
        )

        return decision, rejection_rec

    def _generate_actionable_advice(
        self,
        gate_id: str,
        actual: Optional[Any],
        threshold: Optional[Any],
    ) -> str:
        """Provides trader advice on what market condition would resolve the rejection."""
        if "RISK_REWARD" in gate_id:
            return "Wait for price retracement into entry zone to achieve required 1.5+ R:R."
        elif "LIQUIDITY" in gate_id:
            return "Avoid trading illiquid counter to prevent slippage and wide spreads."
        elif "DATA" in gate_id:
            return "Verify data feed provider connection and candle freshness."
        elif "REGIME" in gate_id:
            return "Strategy direction conflicts with macro market regime. Wait for regime alignment."
        elif "CONFLUENCE" in gate_id:
            return "Independent strategy votes do not satisfy minimum 3 independent families."
        elif "MTF" in gate_id:
            return "Higher timeframe trend opposes setup direction. Await multi-timeframe synchronization."
        return "Monitor for structural setup evolution."

    def get_rejection_analytics(self) -> Dict[str, Any]:
        """Returns top rejection categories and frequencies."""
        return {
            "by_category": dict(self._category_counter),
            "by_gate": dict(self._rejection_reasons_counter),
            "total_rejections": sum(self._category_counter.values()),
        }


# Global singleton
no_trade_engine = NoTradeEngine()
