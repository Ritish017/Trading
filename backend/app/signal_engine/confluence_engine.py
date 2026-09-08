"""
Signal Intelligence Engine — Confluence Engine
===============================================
Aggregates evidence from multiple strategies into a correlation-aware
confluence score, preventing false confidence from correlated signals.

Key principle: 5 correlated strategies confirming the same phenomenon
(e.g. EMA CROSS + MACD + SMA CROSS all measuring trend via moving averages)
do NOT constitute 5 independent confirmations. They constitute 1 evidence family.

Architecture:
1. Categorize strategies into evidence FAMILIES (not just categories)
2. Determine dominant direction per family
3. Count independent families, not raw votes
4. Apply directional weighting by confidence
5. Return correlation-adjusted confluence score

Evidence Families (grouped by what they measure):
- TREND_MOVING_AVERAGE: EMA crossovers, SMA crossovers, MACD trend (all MA-based)
- TREND_ADX: ADX/DI-based trend (independent of MA)
- MOMENTUM_OSCILLATOR: RSI, ROC, Stochastic (oscillators)
- MOMENTUM_MACD: MACD histogram (semi-independent from MA-based)
- VOLUME_ANALYSIS: OBV, CMF, RVOL (purely volume-based)
- VOLATILITY_STRUCTURE: Bollinger, ATR, Donchian (volatility)
- PRICE_STRUCTURE: Support/Resistance, Swing Breakout (structure)
- VWAP_CONTEXT: VWAP-based strategies (separate from above)
"""
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.signal_engine.models import (
    ConfluenceResult,
    SignalDirection,
    StrategyVote,
    StrategyVoteDirection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence Family Definitions
# ---------------------------------------------------------------------------

# Maps strategy_id → evidence_family
# Strategies in the same family measure the same underlying phenomenon
STRATEGY_EVIDENCE_FAMILIES: Dict[str, str] = {
    "EMA_GOLDEN_CROSS":          "TREND_MOVING_AVERAGE",
    "SMA_TREND_FOLLOWING":       "TREND_MOVING_AVERAGE",
    "EMA_RIBBON":                "TREND_MOVING_AVERAGE",
    "MACD_TREND":                "TREND_MOVING_AVERAGE",      # MACD is also MA-derived
    "ADX_TREND_FILTER":          "TREND_ADX",                 # Independent: directional movement
    "RSI_MOMENTUM":              "MOMENTUM_OSCILLATOR",
    "ROC_MOMENTUM":              "MOMENTUM_OSCILLATOR",       # ROC and RSI both momentum oscillators
    "STOCHASTIC_OSCILLATOR":     "MOMENTUM_OSCILLATOR",
    "MACD_CROSSOVER":            "MOMENTUM_MACD",             # MACD crossover is different from MACD trend
    "OBV_TREND":                 "VOLUME_ANALYSIS",
    "RVOL_BREAKOUT":             "VOLUME_ANALYSIS",
    "CMF_FLOW":                  "VOLUME_ANALYSIS",
    "BOLLINGER_BREAKOUT":        "VOLATILITY_STRUCTURE",
    "ATR_BREAKOUT":              "VOLATILITY_STRUCTURE",
    "DONCHIAN_BREAKOUT":         "VOLATILITY_STRUCTURE",
    "SUPPORT_RESISTANCE_BREAK":  "PRICE_STRUCTURE",
    "SWING_BREAKOUT":            "PRICE_STRUCTURE",
    "VWAP_REVERSION":            "VWAP_CONTEXT",
    "VWAP_BREAKOUT":             "VWAP_CONTEXT",
    "RSI_MEAN_REVERSION":        "MEAN_REVERSION",
    "BOLLINGER_REVERSION":       "MEAN_REVERSION",
}

# Which families are considered independent of each other
# (non-overlapping information)
INDEPENDENT_FAMILY_GROUPS: List[Set[str]] = [
    {"TREND_MOVING_AVERAGE"},     # MA trend
    {"TREND_ADX"},                # Directional movement (independent)
    {"MOMENTUM_OSCILLATOR"},      # Price momentum oscillators
    {"MOMENTUM_MACD"},            # MACD-specific signal
    {"VOLUME_ANALYSIS"},          # Volume-based (independent of price)
    {"VOLATILITY_STRUCTURE"},     # Volatility-based
    {"PRICE_STRUCTURE"},          # S/R, swing structure
    {"VWAP_CONTEXT"},             # VWAP (intraday benchmark)
    {"MEAN_REVERSION"},           # Mean reversion strategies
]


def _get_family(strategy_id: str) -> str:
    """Get the evidence family for a strategy ID."""
    # Try exact match first
    if strategy_id in STRATEGY_EVIDENCE_FAMILIES:
        return STRATEGY_EVIDENCE_FAMILIES[strategy_id]

    # Try category-based fallback
    sid_upper = strategy_id.upper()
    if "EMA" in sid_upper or "SMA" in sid_upper or "MA" in sid_upper:
        return "TREND_MOVING_AVERAGE"
    if "ADX" in sid_upper:
        return "TREND_ADX"
    if "RSI" in sid_upper and "REVERSION" in sid_upper:
        return "MEAN_REVERSION"
    if "RSI" in sid_upper or "ROC" in sid_upper or "STOCH" in sid_upper:
        return "MOMENTUM_OSCILLATOR"
    if "MACD" in sid_upper:
        return "MOMENTUM_MACD"
    if "OBV" in sid_upper or "CMF" in sid_upper or "RVOL" in sid_upper or "VOLUME" in sid_upper:
        return "VOLUME_ANALYSIS"
    if "BOLLINGER" in sid_upper or "ATR" in sid_upper or "DONCHIAN" in sid_upper:
        return "VOLATILITY_STRUCTURE"
    if "SUPPORT" in sid_upper or "RESISTANCE" in sid_upper or "SWING" in sid_upper or "BREAKOUT" in sid_upper:
        return "PRICE_STRUCTURE"
    if "VWAP" in sid_upper:
        return "VWAP_CONTEXT"

    return "UNCATEGORIZED"


# ---------------------------------------------------------------------------
# Confluence Engine
# ---------------------------------------------------------------------------

class ConfluenceEngine:
    """
    Correlation-aware evidence aggregation engine.

    Invariants:
    - Returns ConfluenceResult, never raises
    - Strategy confidence is weighted, not just counted
    - Correlated strategies are grouped into families
    - Independence is measured by evidence family, not strategy count
    """

    def evaluate(
        self,
        strategy_votes: List[StrategyVote],
        feature_vector: Optional[Dict[str, Any]] = None,
    ) -> ConfluenceResult:
        """
        Main evaluation method.
        Takes strategy votes and returns a ConfluenceResult.
        """
        if not strategy_votes:
            return ConfluenceResult(
                confluence_label="NO_STRATEGIES",
                confluence_direction=SignalDirection.NO_TRADE,
                strategies_unavailable=0,
                strategies_evaluated=0,
            )

        result = ConfluenceResult()
        result.strategies_evaluated = len(strategy_votes)

        # 1. Count raw votes
        for vote in strategy_votes:
            if vote.direction == StrategyVoteDirection.LONG:
                result.raw_long_votes += 1
            elif vote.direction == StrategyVoteDirection.SHORT:
                result.raw_short_votes += 1
            elif vote.direction == StrategyVoteDirection.NEUTRAL:
                result.raw_neutral_votes += 1
            else:
                result.strategies_unavailable += 1

        # 2. Group by evidence family
        family_votes: Dict[str, List[StrategyVote]] = {}
        for vote in strategy_votes:
            family = _get_family(vote.strategy_id)
            if family not in family_votes:
                family_votes[family] = []
            family_votes[family].append(vote)

        # Detect correlated clusters (families with >1 strategy)
        correlated_clusters: List[List[str]] = []
        for family, votes in family_votes.items():
            if len(votes) > 1:
                correlated_clusters.append([v.strategy_id for v in votes])

        result.correlated_strategy_clusters = correlated_clusters

        # 3. Determine family-level direction (majority within family)
        family_directions: Dict[str, Tuple[str, float]] = {}  # family → (direction, confidence)
        for family, votes in family_votes.items():
            long_conf = sum(v.confidence for v in votes if v.direction == StrategyVoteDirection.LONG)
            short_conf = sum(v.confidence for v in votes if v.direction == StrategyVoteDirection.SHORT)
            neutral_conf = sum(v.confidence for v in votes if v.direction == StrategyVoteDirection.NEUTRAL)

            if long_conf > short_conf and long_conf > neutral_conf:
                # Normalize to single-strategy equivalent (prevent double counting)
                norm_conf = long_conf / len(votes)
                family_directions[family] = ("LONG", norm_conf)
            elif short_conf > long_conf and short_conf > neutral_conf:
                norm_conf = short_conf / len(votes)
                family_directions[family] = ("SHORT", norm_conf)
            else:
                family_directions[family] = ("NEUTRAL", 0.0)

        # 4. Count independent evidence
        independent_long = 0
        independent_short = 0
        independent_long_conf = 0.0
        independent_short_conf = 0.0

        for family, (direction, confidence) in family_directions.items():
            if direction == "LONG":
                independent_long += 1
                independent_long_conf += confidence
            elif direction == "SHORT":
                independent_short += 1
                independent_short_conf += confidence

        result.independent_long_signals = independent_long
        result.independent_short_signals = independent_short

        # 5. Compute correlation discount
        total_raw = result.raw_long_votes + result.raw_short_votes
        total_independent = independent_long + independent_short
        if total_raw > 0 and total_independent < total_raw:
            result.correlation_discount = (total_raw - total_independent) / total_raw * 100

        # 6. Determine direction and score
        total_families = independent_long + independent_short
        if total_families == 0:
            result.confluence_direction = SignalDirection.NO_TRADE
            result.confluence_label = "NO_EVIDENCE"
            result.confluence_score = 0.0
        elif independent_long > independent_short:
            result.confluence_direction = SignalDirection.LONG
            # Score = average confidence of long families, scaled by breadth
            avg_long_conf = independent_long_conf / independent_long if independent_long > 0 else 0
            breadth_factor = min(1.0, independent_long / 4)  # Full breadth at 4+ independent families
            result.confluence_score = avg_long_conf * (0.6 + 0.4 * breadth_factor)

            if independent_long >= 4:
                result.confluence_label = "STRONG_LONG"
            elif independent_long >= 3:
                result.confluence_label = "MODERATE_LONG"
            elif independent_long >= 2:
                result.confluence_label = "WEAK_LONG"
            else:
                result.confluence_label = "INSUFFICIENT"
                result.confluence_direction = SignalDirection.NO_TRADE

        elif independent_short > independent_long:
            result.confluence_direction = SignalDirection.SHORT
            avg_short_conf = independent_short_conf / independent_short if independent_short > 0 else 0
            breadth_factor = min(1.0, independent_short / 4)
            result.confluence_score = avg_short_conf * (0.6 + 0.4 * breadth_factor)

            if independent_short >= 4:
                result.confluence_label = "STRONG_SHORT"
            elif independent_short >= 3:
                result.confluence_label = "MODERATE_SHORT"
            elif independent_short >= 2:
                result.confluence_label = "WEAK_SHORT"
            else:
                result.confluence_label = "INSUFFICIENT"
                result.confluence_direction = SignalDirection.NO_TRADE
        else:
            result.confluence_direction = SignalDirection.NO_TRADE
            result.confluence_label = "CONFLICTING"
            result.confluence_score = 0.0

        # 7. Add correlation warning if significant
        if result.correlation_discount > 30:
            result.correlation_warning = (
                f"Correlation discount applied: {result.correlation_discount:.0f}% of votes are correlated "
                f"({result.raw_long_votes + result.raw_short_votes} raw → "
                f"{independent_long + independent_short} independent). "
                f"Not all strategies represent independent evidence."
            )

        # 8. Evidence breakdown by category
        result.trend_evidence = _family_evidence_label(family_directions, ["TREND_MOVING_AVERAGE", "TREND_ADX"])
        result.momentum_evidence = _family_evidence_label(family_directions, ["MOMENTUM_OSCILLATOR", "MOMENTUM_MACD"])
        result.volume_evidence = _family_evidence_label(family_directions, ["VOLUME_ANALYSIS"])
        result.structure_evidence = _family_evidence_label(family_directions, ["PRICE_STRUCTURE"])
        result.volatility_evidence = _family_evidence_label(family_directions, ["VOLATILITY_STRUCTURE"])

        # Mark correlated strategy IDs on votes
        for vote in strategy_votes:
            fam = _get_family(vote.strategy_id)
            sibling_ids = [v.strategy_id for v in family_votes.get(fam, []) if v.strategy_id != vote.strategy_id]
            vote.is_correlated_with = sibling_ids

        return result

    def get_vote_summary(self, votes: List[StrategyVote]) -> Dict[str, Any]:
        """Returns a simple summary dict for display."""
        confluence = self.evaluate(votes)
        return {
            "direction": confluence.confluence_direction,
            "label": confluence.confluence_label,
            "score": round(confluence.confluence_score, 1),
            "independent_long": confluence.independent_long_signals,
            "independent_short": confluence.independent_short_signals,
            "raw_long": confluence.raw_long_votes,
            "raw_short": confluence.raw_short_votes,
            "correlation_discount": round(confluence.correlation_discount, 1),
            "warning": confluence.correlation_warning,
        }


def _family_evidence_label(
    family_directions: Dict[str, Tuple[str, float]],
    families: List[str],
) -> Optional[str]:
    """Returns aggregate direction label across specified families."""
    matching = [(d, c) for fam, (d, c) in family_directions.items() if fam in families]
    if not matching:
        return None
    longs = sum(1 for d, _ in matching if d == "LONG")
    shorts = sum(1 for d, _ in matching if d == "SHORT")
    if longs > shorts:
        return "BULLISH"
    if shorts > longs:
        return "BEARISH"
    if longs == shorts and longs > 0:
        return "MIXED"
    return "NEUTRAL"


# Module-level singleton
confluence_engine = ConfluenceEngine()
