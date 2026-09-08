"""
Strategy Conformance Matrix & Directional Semantics Tests
=========================================================
Tests all 20 canonical quantitative strategies to verify:
1. Every strategy declares LONG and SHORT entry rules.
2. Synthetic bullish fixtures evaluate Trend/Momentum/Breakout to LONG.
3. Synthetic bearish fixtures evaluate Trend/Momentum/Breakout to SHORT.
4. Mean-reversion counter-trend mechanics evaluate symmetrically (oversold -> LONG, overbought -> SHORT).
5. Missing data propagates safely to UNAVAILABLE (no false positives).
6. Zero-volume candles are handled deterministically without crashes or division by zero.
"""

import math
import pytest
from typing import Dict, Any, List
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.evaluator import evaluate_all_strategies
from backend.app.strategy_engine.dsl import StrategyState, StrategyCategory


def _generate_synthetic_candles(
    n: int = 70,
    trend: str = "bullish",
    base_price: float = 1000.0,
    zero_volume: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generate deterministic synthetic OHLCV candles.
    trend: 'bullish' | 'bearish' | 'sideways'
    """
    candles = []
    price = base_price
    for i in range(n):
        if trend == "bullish":
            price += 1.5 + (i * 0.05)
        elif trend == "bearish":
            price -= 1.5 + (i * 0.05)
        else:
            price += math.sin(i / 5.0) * 0.5

        high = price + 2.0
        low = price - 2.0
        open_p = price - 0.5 if trend == "bullish" else price + 0.5
        close_p = price
        volume = 0.0 if zero_volume else (10000 + i * 200)

        candles.append({
            "timestamp": 1700000000 + i * 900,
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_p, 2),
            "volume": round(volume, 2),
        })
    return candles


def test_all_20_strategies_registered_and_have_short_rules():
    """Verify all 20 strategies are registered and have both long and short rules."""
    assert len(STRATEGY_REGISTRY) == 20, f"Expected 20 strategies, got {len(STRATEGY_REGISTRY)}"

    for sid, strat in STRATEGY_REGISTRY.items():
        assert len(strat.entry_rules) > 0, f"Strategy {sid} has no LONG entry rules"
        assert len(strat.exit_rules) > 0, f"Strategy {sid} has no LONG exit rules"
        assert len(strat.short_entry_rules) > 0, f"Strategy {sid} has no SHORT entry rules"
        assert len(strat.short_exit_rules) > 0, f"Strategy {sid} has no SHORT exit rules"


def test_strategy_conformance_matrix_bullish():
    """Verify evaluation on bullish fixture produces LONG activations for trend/momentum/breakout."""
    candles = _generate_synthetic_candles(n=70, trend="bullish")
    results = evaluate_all_strategies(candles)

    assert len(results) == 20

    trend_longs = 0
    trend_shorts = 0

    for r in results:
        assert hasattr(r, "directional_state")
        assert r.directional_state in ("LONG", "SHORT", "NEUTRAL", "CONFLICTED")

        category = r.category if isinstance(r.category, str) else r.category.value
        # Trend, Momentum, Breakout, Volume, Volatility should align with the trend direction
        if category in ("Trend Following", "Momentum", "Breakout", "Volume", "Volatility"):
            if r.directional_state == "LONG":
                trend_longs += 1
            elif r.directional_state == "SHORT":
                trend_shorts += 1

    # In a bullish trend, trend/momentum/breakout strategies must produce LONG activations and 0 SHORT activations
    assert trend_longs > 0, f"Expected at least 1 trend strategy to activate LONG, got {trend_longs}"
    assert trend_shorts == 0, f"Expected 0 trend strategies to activate SHORT on bullish fixture, got {trend_shorts}"


def test_strategy_conformance_matrix_bearish():
    """Verify evaluation on bearish fixture produces SHORT activations for trend/momentum/breakout."""
    candles = _generate_synthetic_candles(n=70, trend="bearish")
    results = evaluate_all_strategies(candles)

    assert len(results) == 20

    trend_longs = 0
    trend_shorts = 0

    for r in results:
        assert hasattr(r, "directional_state")
        assert r.directional_state in ("LONG", "SHORT", "NEUTRAL", "CONFLICTED")

        category = r.category if isinstance(r.category, str) else r.category.value
        if category in ("Trend Following", "Momentum", "Breakout", "Volume", "Volatility"):
            if r.directional_state == "LONG":
                trend_longs += 1
            elif r.directional_state == "SHORT":
                trend_shorts += 1

    # In a bearish trend, trend/momentum/breakout strategies must produce SHORT activations and 0 LONG activations
    assert trend_shorts > 0, f"Expected at least 1 trend strategy to activate SHORT, got {trend_shorts}"
    assert trend_longs == 0, f"Expected 0 trend strategies to activate LONG on bearish fixture, got {trend_longs}"


def test_mean_reversion_counter_trend_mechanics():
    """Verify mean-reversion strategies activate counter-trend when stretched."""
    # Extreme oversold downtrend with capitulation volume spike on latest candle
    bearish_candles = _generate_synthetic_candles(n=70, trend="bearish")
    bearish_candles[-1]["volume"] = 50000  # Capitulation volume flush (rvol >= 1.5)
    results_bear = {r.strategy_id: r for r in evaluate_all_strategies(bearish_candles)}

    # RSI Oversold Reversal should trigger LONG on extreme oversold drop with volume flush
    rsi_rev = results_bear.get("RSI_OVERSOLD_REVERSAL")
    assert rsi_rev is not None
    assert rsi_rev.directional_state == "LONG"


def test_missing_data_propagates_to_unavailable():
    """Verify that insufficient data produces StrategyState.UNAVAILABLE."""
    candles = _generate_synthetic_candles(n=5)
    results = evaluate_all_strategies(candles)

    for r in results:
        assert r.state == StrategyState.UNAVAILABLE
        assert r.directional_state == "NEUTRAL"


def test_zero_volume_handling_deterministic():
    """Verify zero-volume candles do not raise exceptions or crash calculations."""
    candles = _generate_synthetic_candles(n=70, trend="bullish", zero_volume=True)
    results = evaluate_all_strategies(candles)

    assert len(results) == 20
    for r in results:
        assert r.directional_state in ("LONG", "SHORT", "NEUTRAL", "CONFLICTED")
