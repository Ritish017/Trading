"""
Signal Intelligence Engine — Opportunity Scoring Engine
========================================================
Computes the 0-100 opportunity score for a signal candidate.

The score is composed of 11 weighted components. Weights are documented
and configurable. The score is NOT a guarantee of profitability —
it represents the degree of favorable evidence alignment.

Components and default weights (must sum to 100):
  trend_alignment       15%  Trend direction agreement across timeframes
  momentum_quality      10%  Momentum indicator quality (RSI zone, ROC, Stochastic)
  volume_confirmation   10%  Volume expansion and OBV confirmation
  market_structure      10%  S/R levels, swing structure, breakout quality
  volatility_suitability 8%  ATR suitable for stop placement, not excessive
  regime_compatibility  12%  Strategy historically performs in current regime
  strategy_consensus    15%  Correlation-adjusted strategy agreement
  mtf_alignment         10%  Multi-timeframe direction alignment
  liquidity_quality      5%  Volume and price spread quality
  risk_reward_quality   10%  R:R above minimum and quality
  historical_edge        5%  Historical performance in comparable setups

Quality Grades:
  90+ → A+ (Exceptional)
  80+ → A  (Strong)
  70+ → B  (Valid but weaker)
  60+ → C  (Interesting but insufficient)
  <60 → NO TRADE

Transparency invariant: every component score and weight is included in the
output so users can see EXACTLY what drove the final score.
"""
import logging
import math
from typing import Any, Dict, List, Optional

from backend.app.signal_engine.models import (
    ConfluenceResult,
    MultiTimeframeResult,
    SignalQualityGrade,
    ScoringWeights,
    SignalEngineConfig,
    StrategyVote,
    StrategyVoteDirection,
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


class ScoringEngine:
    """
    Deterministic opportunity scoring engine.
    Given the same inputs, always produces the same score.
    """

    def score(
        self,
        direction: str,
        feature_vector: Dict[str, Any],
        regime: str,
        regime_confidence: float,
        strategy_votes: List[StrategyVote],
        confluence_result: Optional[ConfluenceResult],
        mtf_result: Optional[MultiTimeframeResult],
        risk_reward: Optional[float],
        liquidity_score: float,
        historical_win_rate: Optional[float],
        historical_expectancy: Optional[float],
        support_levels: List[float],
        resistance_levels: List[float],
        config: SignalEngineConfig,
        weights: Optional[ScoringWeights] = None,
    ) -> Dict[str, Any]:
        """
        Compute the full opportunity score.
        Returns a dict with total_score, component_scores, quality_grade.
        """
        w = weights or ScoringWeights()

        components: Dict[str, Dict[str, Any]] = {}
        total_score = 0.0

        # --- 1. Trend Alignment ---
        trend_score = self._score_trend_alignment(direction, feature_vector, regime)
        components["trend_alignment"] = {
            "score": trend_score,
            "weight": w.trend_alignment,
            "weighted": trend_score * w.trend_alignment / 100,
        }
        total_score += trend_score * w.trend_alignment / 100

        # --- 2. Momentum Quality ---
        momentum_score = self._score_momentum(direction, feature_vector)
        components["momentum_quality"] = {
            "score": momentum_score,
            "weight": w.momentum_quality,
            "weighted": momentum_score * w.momentum_quality / 100,
        }
        total_score += momentum_score * w.momentum_quality / 100

        # --- 3. Volume Confirmation ---
        volume_score = self._score_volume(feature_vector)
        components["volume_confirmation"] = {
            "score": volume_score,
            "weight": w.volume_confirmation,
            "weighted": volume_score * w.volume_confirmation / 100,
        }
        total_score += volume_score * w.volume_confirmation / 100

        # --- 4. Market Structure ---
        structure_score = self._score_structure(direction, feature_vector, support_levels, resistance_levels)
        components["market_structure"] = {
            "score": structure_score,
            "weight": w.market_structure,
            "weighted": structure_score * w.market_structure / 100,
        }
        total_score += structure_score * w.market_structure / 100

        # --- 5. Volatility Suitability ---
        vol_suit_score = self._score_volatility_suitability(feature_vector)
        components["volatility_suitability"] = {
            "score": vol_suit_score,
            "weight": w.volatility_suitability,
            "weighted": vol_suit_score * w.volatility_suitability / 100,
        }
        total_score += vol_suit_score * w.volatility_suitability / 100

        # --- 6. Regime Compatibility ---
        regime_score = self._score_regime_compatibility(direction, regime, regime_confidence)
        components["regime_compatibility"] = {
            "score": regime_score,
            "weight": w.regime_compatibility,
            "weighted": regime_score * w.regime_compatibility / 100,
        }
        total_score += regime_score * w.regime_compatibility / 100

        # --- 7. Strategy Consensus ---
        consensus_score = self._score_strategy_consensus(direction, strategy_votes, confluence_result)
        components["strategy_consensus"] = {
            "score": consensus_score,
            "weight": w.strategy_consensus,
            "weighted": consensus_score * w.strategy_consensus / 100,
        }
        total_score += consensus_score * w.strategy_consensus / 100

        # --- 8. MTF Alignment ---
        mtf_score = self._score_mtf_alignment(mtf_result)
        components["mtf_alignment"] = {
            "score": mtf_score,
            "weight": w.mtf_alignment,
            "weighted": mtf_score * w.mtf_alignment / 100,
        }
        total_score += mtf_score * w.mtf_alignment / 100

        # --- 9. Liquidity Quality ---
        liq_score = min(100, liquidity_score)
        components["liquidity_quality"] = {
            "score": liq_score,
            "weight": w.liquidity_quality,
            "weighted": liq_score * w.liquidity_quality / 100,
        }
        total_score += liq_score * w.liquidity_quality / 100

        # --- 10. Risk/Reward Quality ---
        rr_score = self._score_risk_reward(risk_reward, config.min_risk_reward)
        components["risk_reward_quality"] = {
            "score": rr_score,
            "weight": w.risk_reward_quality,
            "weighted": rr_score * w.risk_reward_quality / 100,
        }
        total_score += rr_score * w.risk_reward_quality / 100

        # --- 11. Historical Edge ---
        edge_score = self._score_historical_edge(historical_win_rate, historical_expectancy)
        components["historical_edge"] = {
            "score": edge_score,
            "weight": w.historical_edge,
            "weighted": edge_score * w.historical_edge / 100,
        }
        total_score += edge_score * w.historical_edge / 100

        total_score = round(min(100.0, max(0.0, total_score)), 1)

        # Determine quality grade
        grade = self._grade(total_score, config)

        # Compute confidence (correlated to score but separate concept)
        confidence = self._compute_confidence(total_score, strategy_votes, mtf_result, direction)

        return {
            "opportunity_score": total_score,
            "quality_grade": grade,
            "confidence": round(confidence, 1),
            "components": components,
            "weights_used": w.model_dump(),
            "disclaimer": (
                "Opportunity Score reflects the degree of favorable evidence alignment. "
                "It does not predict outcome. Historical edge is reported separately."
            ),
        }

    # --- Component Scorers ---

    def _score_trend_alignment(
        self, direction: str, fv: Dict[str, Any], regime: str
    ) -> float:
        score = 50.0  # Neutral baseline

        ema20 = _safe_float(fv.get("ema20"))
        ema50 = _safe_float(fv.get("ema50"))
        price = _safe_float(fv.get("close") or fv.get("ltp"))
        adx = _safe_float(fv.get("adx14"))

        if ema20 is None or ema50 is None or price is None:
            return 40.0  # Data unavailable

        if direction == "LONG":
            if price > ema20 > ema50:
                score = 85.0
                if adx and adx > 25:
                    score = 95.0
            elif price > ema20:
                score = 70.0
            elif price < ema20 < ema50:
                score = 20.0
            else:
                score = 45.0
        else:  # SHORT
            if price < ema20 < ema50:
                score = 85.0
                if adx and adx > 25:
                    score = 95.0
            elif price < ema20:
                score = 70.0
            elif price > ema20 > ema50:
                score = 20.0
            else:
                score = 45.0

        # Regime alignment bonus
        if direction == "LONG" and "BULL" in regime:
            score = min(100, score + 5)
        elif direction == "SHORT" and "BEAR" in regime:
            score = min(100, score + 5)

        return score

    def _score_momentum(self, direction: str, fv: Dict[str, Any]) -> float:
        rsi = _safe_float(fv.get("rsi14"))
        if rsi is None:
            return 40.0

        if direction == "LONG":
            if 55 <= rsi <= 70:
                return 90.0
            elif 45 <= rsi < 55:
                return 70.0
            elif 40 <= rsi < 45:
                return 55.0
            elif rsi > 75:
                return 30.0  # Overbought
            else:
                return 40.0
        else:  # SHORT
            if 30 <= rsi <= 45:
                return 90.0
            elif 45 < rsi <= 55:
                return 70.0
            elif 55 < rsi <= 60:
                return 55.0
            elif rsi < 25:
                return 30.0  # Oversold
            else:
                return 40.0

    def _score_volume(self, fv: Dict[str, Any]) -> float:
        rvol = _safe_float(fv.get("rvol20"))
        if rvol is None:
            return 40.0

        if rvol >= 2.0:
            return 95.0
        elif rvol >= 1.5:
            return 80.0
        elif rvol >= 1.0:
            return 60.0
        elif rvol >= 0.7:
            return 40.0
        else:
            return 20.0

    def _score_structure(
        self,
        direction: str,
        fv: Dict[str, Any],
        support_levels: List[float],
        resistance_levels: List[float],
    ) -> float:
        price = _safe_float(fv.get("close") or fv.get("ltp"))
        if price is None:
            return 40.0

        score = 50.0

        if direction == "LONG":
            # Is price near a support level (within 1%)?
            near_support = any(abs(price - s) / price < 0.01 for s in support_levels)
            # Is nearest resistance far enough (>2%)?
            res_above = [r for r in resistance_levels if r > price]
            room_to_run = (res_above[0] - price) / price if res_above else 0.05

            if near_support:
                score += 20
            if room_to_run > 0.03:
                score += 20
            elif room_to_run > 0.015:
                score += 10
        else:  # SHORT
            # Near resistance?
            near_resistance = any(abs(price - r) / price < 0.01 for r in resistance_levels)
            # Support below (room to fall)?
            sup_below = [s for s in support_levels if s < price]
            room_to_fall = (price - sup_below[0]) / price if sup_below else 0.05

            if near_resistance:
                score += 20
            if room_to_fall > 0.03:
                score += 20
            elif room_to_fall > 0.015:
                score += 10

        return min(100, score)

    def _score_volatility_suitability(self, fv: Dict[str, Any]) -> float:
        atr_pct = _safe_float(fv.get("atr_pct"))
        if atr_pct is None:
            atr = _safe_float(fv.get("atr14"))
            price = _safe_float(fv.get("close") or fv.get("ltp"))
            if atr and price and price > 0:
                atr_pct = atr / price * 100
            else:
                return 50.0  # Neutral when unavailable

        # Ideal range: 0.5% - 2.5% ATR
        if 0.5 <= atr_pct <= 2.5:
            return 85.0
        elif 2.5 < atr_pct <= 4.0:
            return 65.0  # High but manageable
        elif atr_pct > 4.0:
            return 35.0  # Extreme volatility, hard to stop
        elif 0.2 <= atr_pct < 0.5:
            return 60.0  # Low volatility, small moves
        else:
            return 40.0  # Very low volatility

    def _score_regime_compatibility(
        self, direction: str, regime: str, regime_confidence: float
    ) -> float:
        compatible_long_regimes = {"TRENDING_BULLISH", "BULLISH_ACCUMULATION", "BREAKOUT"}
        compatible_short_regimes = {"TRENDING_BEARISH", "BEARISH_DISTRIBUTION", "BREAKDOWN"}
        neutral_regimes = {"RANGE_BOUND", "HIGH_VOLATILITY", "LOW_VOLATILITY"}

        if regime == "UNAVAILABLE" or regime == "UNKNOWN":
            return 40.0

        confidence_factor = min(1.0, regime_confidence / 100)

        if direction == "LONG" and regime in compatible_long_regimes:
            return round(70 + 25 * confidence_factor, 1)
        elif direction == "SHORT" and regime in compatible_short_regimes:
            return round(70 + 25 * confidence_factor, 1)
        elif regime in neutral_regimes:
            return 50.0
        else:
            # Regime is against signal direction
            return round(20 + 10 * confidence_factor, 1)

    def _score_strategy_consensus(
        self,
        direction: str,
        strategy_votes: List[StrategyVote],
        confluence: Optional[ConfluenceResult],
    ) -> float:
        if not strategy_votes:
            return 0.0

        if confluence:
            # Use the correlation-adjusted score from confluence engine
            return min(100.0, confluence.confluence_score)

        # Fallback: simple vote counting
        total = len(strategy_votes)
        if direction == "LONG":
            aligned = sum(1 for v in strategy_votes if v.direction == StrategyVoteDirection.LONG)
        else:
            aligned = sum(1 for v in strategy_votes if v.direction == StrategyVoteDirection.SHORT)

        if total == 0:
            return 0.0
        ratio = aligned / total
        avg_conf = sum(v.confidence for v in strategy_votes if v.direction == StrategyVoteDirection.LONG) / max(1, aligned)
        return round(ratio * avg_conf, 1)

    def _score_mtf_alignment(self, mtf_result: Optional[MultiTimeframeResult]) -> float:
        if mtf_result is None:
            return 40.0
        return min(100.0, mtf_result.alignment_score)

    def _score_risk_reward(
        self, risk_reward: Optional[float], min_rr: float
    ) -> float:
        if risk_reward is None:
            return 0.0

        if risk_reward < min_rr:
            return 0.0  # Already blocked by hard gate but score reflects it
        elif risk_reward >= 3.0:
            return 100.0
        elif risk_reward >= 2.5:
            return 90.0
        elif risk_reward >= 2.0:
            return 80.0
        elif risk_reward >= 1.75:
            return 70.0
        elif risk_reward >= 1.5:
            return 60.0
        else:
            return 50.0

    def _score_historical_edge(
        self,
        win_rate: Optional[float],
        expectancy: Optional[float],
    ) -> float:
        if win_rate is None or expectancy is None:
            return 50.0  # No history → neutral (not penalized)

        # Combine win rate and expectancy
        # Good: win_rate > 55% AND expectancy > 0.3R
        wr_score = min(100, max(0, (win_rate - 30) * 2))
        exp_score = min(100, max(0, expectancy * 100))  # 0.5R → 50 points

        return round((wr_score + exp_score) / 2, 1)

    def _grade(self, score: float, config: SignalEngineConfig) -> SignalQualityGrade:
        if score >= config.a_plus_score_threshold:
            return SignalQualityGrade.A_PLUS
        elif score >= config.a_score_threshold:
            return SignalQualityGrade.A
        elif score >= config.b_score_threshold:
            return SignalQualityGrade.B
        elif score >= config.c_score_threshold:
            return SignalQualityGrade.C
        else:
            return SignalQualityGrade.NO_TRADE

    def _compute_confidence(
        self,
        opportunity_score: float,
        strategy_votes: List[StrategyVote],
        mtf_result: Optional[MultiTimeframeResult],
        direction: str,
    ) -> float:
        """
        Confidence is related to score but is a separate concept.
        It reflects agreement between independent evidence sources.
        """
        base = opportunity_score * 0.8  # Score drives ~80% of confidence

        # Agreement bonus: are strategies pointing the same direction?
        if strategy_votes:
            if direction == "LONG":
                aligned = sum(1 for v in strategy_votes if v.direction == StrategyVoteDirection.LONG)
            else:
                aligned = sum(1 for v in strategy_votes if v.direction == StrategyVoteDirection.SHORT)
            agreement_ratio = aligned / len(strategy_votes)
            base += agreement_ratio * 10

        # MTF confirmation bonus
        if mtf_result and mtf_result.alignment_score > 70:
            base += 5

        return min(95.0, max(0.0, base))


# Module-level singleton
scoring_engine = ScoringEngine()
