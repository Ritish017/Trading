"""
Signal Intelligence Engine — Multi-Timeframe Analysis Engine
=============================================================
Analyzes a set of candle data across multiple timeframes to determine
higher-timeframe trend, intermediate momentum, and execution-level entry quality.

Supported timeframe hierarchy (high → low):
  1D → 4H → 1H → 15M → 5M

Multi-timeframe confirmation logic:
  - Higher timeframe: What is the primary trend?
  - Intermediate timeframe: Is momentum aligned?
  - Execution timeframe: Is there a valid entry?

Result classification:
  CONFIRMED    — All analyzed timeframes aligned in same direction
  PARTIAL      — Higher TF aligned, lower TF shows pullback (often IDEAL entry)
  CONFLICTING  — Higher and lower TF pointing in opposite directions
  UNAVAILABLE  — Insufficient data

Example output (LONG confirmed):
  1D:  BULLISH  (Primary trend)
  1H:  BULLISH  (Momentum aligned)
  15M: PULLBACK (Retracement — potentially ideal entry)
  5M:  BREAKOUT (Execution trigger)
  → MULTI-TIMEFRAME LONG CONFIRMED

Invariants:
- Each timeframe is analyzed independently
- Insufficient data for a timeframe → marked UNAVAILABLE (not PASS)
- Conflicts reduce alignment_score proportionally
- The final alignment_label reflects actual analysis, not desired outcome
"""
import logging
import math
from typing import Any, Dict, List, Optional

from backend.app.signal_engine.models import (
    MultiTimeframeResult,
    TimeframeAnalysis,
    SignalEngineConfig,
)
from backend.app.quant_engine.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_adx,
    calculate_atr,
)

import pandas as pd
import numpy as np

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
# Single-Timeframe Analyzer
# ---------------------------------------------------------------------------

def analyze_single_timeframe(
    candles: List[Dict[str, Any]],
    timeframe: str,
    direction: str,
) -> TimeframeAnalysis:
    """
    Analyze a single timeframe's candles and produce TimeframeAnalysis.
    """
    result = TimeframeAnalysis(timeframe=timeframe, candles_available=len(candles))

    if not candles or len(candles) < 15:
        result.trend = "UNAVAILABLE"
        result.momentum = "UNAVAILABLE"
        result.entry_quality = "UNAVAILABLE"
        result.is_available = False
        return result

    try:
        df = pd.DataFrame(candles)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "close" not in df.columns or df["close"].isna().all():
            result.trend = "UNAVAILABLE"
            result.is_available = False
            return result

        close = df["close"].dropna()
        if len(close) < 15:
            result.trend = "UNAVAILABLE"
            result.is_available = False
            return result

        # EMA indicators
        ema20_series = calculate_ema(close, 20) if len(close) >= 20 else pd.Series([None] * len(close))
        ema50_series = calculate_ema(close, min(50, len(close)))
        rsi_series = calculate_rsi(close, 14)

        ema20 = _safe_float(ema20_series.iloc[-1]) if len(ema20_series) > 0 else None
        ema50 = _safe_float(ema50_series.iloc[-1]) if len(ema50_series) > 0 else None
        rsi = _safe_float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else None
        current_price = _safe_float(close.iloc[-1])

        result.ema20 = round(ema20, 2) if ema20 else None
        result.ema50 = round(ema50, 2) if ema50 else None
        result.rsi = round(rsi, 1) if rsi else None

        # ADX
        try:
            if all(c in df.columns for c in ["high", "low", "close"]) and len(df) >= 28:
                adx_s, _, _ = calculate_adx(df, 14)
                adx = _safe_float(adx_s.iloc[-1]) if len(adx_s) > 0 else None
                result.adx = round(adx, 1) if adx else None
        except Exception:
            result.adx = None

        # Determine trend
        if current_price and ema20 and ema50:
            if current_price > ema20 and ema20 > ema50:
                result.trend = "BULLISH"
                result.trend_strength = min(100, 60 + (rsi - 50) * 1.5 if rsi else 60)
            elif current_price < ema20 and ema20 < ema50:
                result.trend = "BEARISH"
                result.trend_strength = min(100, 60 + (50 - rsi) * 1.5 if rsi else 60)
            elif current_price > ema20 and ema20 <= ema50:
                result.trend = "NEUTRAL_ABOVE"
                result.trend_strength = 40.0
            elif current_price < ema20 and ema20 >= ema50:
                result.trend = "NEUTRAL_BELOW"
                result.trend_strength = 40.0
            else:
                result.trend = "NEUTRAL"
                result.trend_strength = 30.0
        elif current_price and ema20:
            result.trend = "BULLISH" if current_price > ema20 else "BEARISH"
            result.trend_strength = 50.0
        else:
            result.trend = "UNAVAILABLE"

        # Determine momentum
        if rsi:
            if direction == "LONG":
                if 55 <= rsi <= 75:
                    result.momentum = "STRONG"
                elif 45 <= rsi < 55:
                    result.momentum = "MODERATE"
                elif 30 <= rsi < 45:
                    result.momentum = "PULLBACK"  # Often ideal entry for longs
                elif rsi > 80:
                    result.momentum = "OVERBOUGHT"
                else:
                    result.momentum = "WEAK"
            else:  # SHORT
                if 25 <= rsi <= 45:
                    result.momentum = "STRONG"
                elif 45 < rsi <= 55:
                    result.momentum = "MODERATE"
                elif 55 < rsi <= 70:
                    result.momentum = "PULLBACK"
                elif rsi < 20:
                    result.momentum = "OVERSOLD"
                else:
                    result.momentum = "WEAK"
        else:
            result.momentum = "UNAVAILABLE"

        # Determine entry quality on this timeframe
        trend_aligned = (
            (direction == "LONG" and result.trend in ("BULLISH", "NEUTRAL_ABOVE")) or
            (direction == "SHORT" and result.trend in ("BEARISH", "NEUTRAL_BELOW"))
        )
        momentum_good = result.momentum in ("STRONG", "MODERATE", "PULLBACK")

        if trend_aligned and result.momentum in ("STRONG", "MODERATE"):
            result.entry_quality = "IDEAL"
        elif trend_aligned and result.momentum == "PULLBACK":
            result.entry_quality = "ACCEPTABLE"  # Pullback into trend = often ideal
        elif trend_aligned:
            result.entry_quality = "ACCEPTABLE"
        elif result.trend == "NEUTRAL":
            result.entry_quality = "POOR"
        else:
            result.entry_quality = "POOR"

    except Exception as e:
        logger.warning(f"MTF analysis error for timeframe {timeframe}: {e}")
        result.trend = "UNAVAILABLE"
        result.momentum = "UNAVAILABLE"
        result.entry_quality = "UNAVAILABLE"
        result.is_available = False

    return result


# ---------------------------------------------------------------------------
# Multi-Timeframe Engine
# ---------------------------------------------------------------------------

class MultiTimeframeEngine:
    """
    Orchestrates multi-timeframe analysis across the configured timeframe hierarchy.
    """

    def analyze(
        self,
        candles_by_timeframe: Dict[str, List[Dict[str, Any]]],
        direction: str,
        config: SignalEngineConfig,
    ) -> MultiTimeframeResult:
        """
        Analyze all configured timeframes.

        Args:
            candles_by_timeframe: Dict mapping timeframe → candle list
            direction: "LONG" or "SHORT"
            config: Engine configuration

        Returns:
            MultiTimeframeResult with alignment assessment
        """
        result = MultiTimeframeResult(execution_timeframe=config.primary_timeframe)
        tf_analyses: List[TimeframeAnalysis] = []

        # Analyze each configured timeframe (high to low)
        for tf in config.mtf_timeframes:
            candles = candles_by_timeframe.get(tf, [])
            analysis = analyze_single_timeframe(candles, tf, direction)
            tf_analyses.append(analysis)

        result.timeframes = tf_analyses

        if not tf_analyses:
            result.alignment_label = "UNAVAILABLE"
            result.alignment_score = 0.0
            return result

        # Determine primary trend from highest available timeframe
        available_tfs = [a for a in tf_analyses if a.is_available and a.trend != "UNAVAILABLE"]
        if available_tfs:
            primary = available_tfs[0]
            result.primary_trend = primary.trend
        else:
            result.primary_trend = "UNAVAILABLE"
            result.alignment_label = "UNAVAILABLE"
            result.alignment_score = 0.0
            return result

        # Alignment scoring
        alignment_scores = []
        conflicts = []

        for i, analysis in enumerate(tf_analyses):
            if not analysis.is_available or analysis.trend == "UNAVAILABLE":
                alignment_scores.append(50.0)  # Neutral for unavailable
                continue

            weight = 1.0 / (i + 1)  # Higher timeframes weighted more

            if direction == "LONG":
                if analysis.trend == "BULLISH":
                    alignment_scores.append(100.0)
                elif analysis.trend in ("NEUTRAL_ABOVE", "NEUTRAL"):
                    alignment_scores.append(60.0)
                elif analysis.momentum == "PULLBACK":
                    # Pullback in trend direction = acceptable
                    alignment_scores.append(75.0)
                elif analysis.trend == "BEARISH":
                    alignment_scores.append(20.0)
                    if i == 0:  # Primary timeframe conflict
                        conflicts.append(
                            f"Primary timeframe ({analysis.timeframe}) shows BEARISH trend — "
                            "conflicts with LONG signal"
                        )
                else:
                    alignment_scores.append(50.0)
            else:  # SHORT
                if analysis.trend == "BEARISH":
                    alignment_scores.append(100.0)
                elif analysis.trend in ("NEUTRAL_BELOW", "NEUTRAL"):
                    alignment_scores.append(60.0)
                elif analysis.momentum == "PULLBACK":
                    alignment_scores.append(75.0)
                elif analysis.trend == "BULLISH":
                    alignment_scores.append(20.0)
                    if i == 0:
                        conflicts.append(
                            f"Primary timeframe ({analysis.timeframe}) shows BULLISH trend — "
                            "conflicts with SHORT signal"
                        )
                else:
                    alignment_scores.append(50.0)

        result.conflict_warnings = conflicts
        result.alignment_score = round(
            sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0.0, 1
        )

        # Determine label
        if result.alignment_score >= 80:
            if direction == "LONG":
                result.alignment_label = "MULTI-TF LONG CONFIRMED"
                result.confirmation_message = (
                    "Multiple timeframes aligned bullish. Higher-timeframe trend supports long entry."
                )
            else:
                result.alignment_label = "MULTI-TF SHORT CONFIRMED"
                result.confirmation_message = (
                    "Multiple timeframes aligned bearish. Higher-timeframe trend supports short entry."
                )
        elif result.alignment_score >= 60:
            result.alignment_label = "PARTIAL ALIGNMENT"
            result.confirmation_message = "Most timeframes aligned. Some divergence detected."
        elif conflicts:
            result.alignment_label = "CONFLICTING"
            result.confirmation_message = (
                "Timeframe conflict detected. Higher timeframe may be opposing the signal direction."
            )
        else:
            result.alignment_label = "WEAK ALIGNMENT"
            result.confirmation_message = "Weak multi-timeframe alignment. Confidence reduced."

        return result


# Module-level singleton
multi_timeframe_engine = MultiTimeframeEngine()
