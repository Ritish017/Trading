"""
Unit & Regression Tests: Strategy Dependency Engine & Indicator Registry Hardening (V3 Phase 2)
================================================================================================
Validates:
- Single-calculation invariant per evaluation context.
- Dependency key normalization and alias resolution.
- Parameterized indicator separation (e.g. EMA20 vs EMA50 vs EMA200).
- Minimum history enforcement and warmup null alignment.
- Data sufficiency vs freshness independence.
- Strict zero vs missing data contract.
- Lookahead prevention across all indicators.
- Symbol and timeframe isolation.
- Complete strategy dependency resolution against IndicatorSpec.
"""

import time
import pytest
import numpy as np
import pandas as pd

from backend.app.strategy_engine.dependency_engine import (
    dependency_engine,
    normalize_dependency_key,
    INDICATOR_SPECS,
    DependencyEvaluationContext,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY, registry_manager
from backend.app.strategy_engine.evaluator import (
    evaluate_all_strategies,
    compute_feature_vector,
    compute_series_indicators,
    evaluate_strategies_observatory,
    _evaluate_freshness,
)
from backend.app.strategy_engine.dsl import StrategyState, RuleOutcome


def generate_synthetic_candles(n: int = 60, base_price: float = 100.0, zero_volume: bool = False, missing_volume: bool = False):
    """Helper to generate clean synthetic OHLCV candles."""
    now = time.time()
    candles = []
    for i in range(n):
        px = base_price + (i * 0.25)
        c = {
            "time": int(now - (n - i) * 60),
            "open": px - 0.1,
            "high": px + 0.5,
            "low": px - 0.4,
            "close": px,
        }
        if not missing_volume:
            c["volume"] = 0.0 if zero_volume else float(1000 + i * 25)
        candles.append(c)
    return candles


# ---------------------------------------------------------------------------
# 1. Single-Calculation Invariant
# ---------------------------------------------------------------------------

def test_single_calculation_invariant():
    """
    Phase 2: Prove that shared indicators are calculated exactly once per evaluation context.
    """
    candles = generate_synthetic_candles(n=60)
    
    # Request multiple strategies that all need EMA20, EMA50, RSI14, VWAP
    ctx = dependency_engine.compute_context(
        candles,
        symbol="RELIANCE.NS",
        timeframe="5m"
    )
    
    # Every shared indicator must have a calculation count of exactly 1
    assert ctx.calculation_counts["ema20"] == 1
    assert ctx.calculation_counts["ema50"] == 1
    assert ctx.calculation_counts["rsi14"] == 1
    assert ctx.calculation_counts["vwap"] == 1
    assert ctx.calculation_counts["atr14"] == 1
    assert ctx.calculation_counts["macd"] == 1
    assert ctx.calculation_counts["bb_upper"] == 1
    assert ctx.calculation_counts["rvol"] == 1


# ---------------------------------------------------------------------------
# 2. Dependency Key Normalization
# ---------------------------------------------------------------------------

def test_dependency_key_normalization():
    """
    Phase 3: Ensure key normalization handles aliases, case insensitivity, and whitespace.
    """
    assert normalize_dependency_key("EMA_20") == "ema20"
    assert normalize_dependency_key("  ema20  ") == "ema20"
    assert normalize_dependency_key("EMA20") == "ema20"
    assert normalize_dependency_key("RSI_14") == "rsi14"
    assert normalize_dependency_key("rsi14") == "rsi14"
    assert normalize_dependency_key("relative_volume") == "rvol"
    assert normalize_dependency_key("rvol_20") == "rvol"
    assert normalize_dependency_key("bb_top") == "bb_upper"
    assert normalize_dependency_key("supertrend") == "supertrend_band"
    assert normalize_dependency_key("VWAP") == "vwap"


# ---------------------------------------------------------------------------
# 3. Parameterized Indicator Separation
# ---------------------------------------------------------------------------

def test_parameterized_indicators_separation():
    """
    Phase 4: Ensure parameterized indicators (EMA20, EMA50, EMA200) remain strictly distinct.
    """
    candles = generate_synthetic_candles(n=250)
    ctx = dependency_engine.compute_context(candles)
    
    ema20_val = ctx.feature_vector["ema20"]
    ema50_val = ctx.feature_vector["ema50"]
    ema200_val = ctx.feature_vector["ema200"]
    
    assert ema20_val is not None
    assert ema50_val is not None
    assert ema200_val is not None
    # For monotonically increasing price, EMA20 > EMA50 > EMA200
    assert ema20_val > ema50_val > ema200_val


# ---------------------------------------------------------------------------
# 4. Minimum History Requirements & Warmup Null Alignment
# ---------------------------------------------------------------------------

def test_minimum_history_requirements():
    """
    Phase 5 & 16: Ensure insufficient history produces None / UNAVAILABLE, not fabricated values.
    """
    # 10 candles: enough for basic price, but NOT for EMA20, EMA50, EMA200, MACD
    candles = generate_synthetic_candles(n=10)
    ctx = dependency_engine.compute_context(candles)
    
    assert ctx.feature_vector["close"] is not None
    assert ctx.feature_vector["ema20"] is None
    assert ctx.feature_vector["ema50"] is None
    assert ctx.feature_vector["ema200"] is None
    assert ctx.feature_vector["macd"] is None
    assert ctx.feature_vector["rvol"] is None
    
    # Check series warm-up null alignment
    ema20_series = ctx.series["ema20"]
    assert len(ema20_series) == 10
    assert all(v is None for v in ema20_series)


def test_series_warmup_alignment_at_boundary():
    """
    Phase 15: Warm-up nulls must populate up to min_bars - 1, and first valid value appears at min_bars - 1.
    """
    candles = generate_synthetic_candles(n=25)
    ctx = dependency_engine.compute_context(candles)
    
    ema20_series = ctx.series["ema20"]
    assert len(ema20_series) == 25
    # First 19 bars (0..18) must be None
    assert all(ema20_series[i] is None for i in range(19))
    # 20th bar (index 19) onwards must be valid floats
    assert all(ema20_series[i] is not None for i in range(19, 25))


# ---------------------------------------------------------------------------
# 5. Data Sufficiency vs Freshness Independence
# ---------------------------------------------------------------------------

def test_data_sufficiency_vs_freshness():
    """
    Phase 6: Mathematical sufficiency (candle count) is strictly decoupled from data freshness (timestamp age).
    """
    # Scenario A: 200 valid historical candles from yesterday (STALE, but SUFFICIENT)
    old_time = time.time() - 86400
    stale_candles = [
        {"time": int(old_time + i * 60), "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 1000}
        for i in range(200)
    ]
    freshness, age = _evaluate_freshness(stale_candles, is_live_feed=False)
    ctx_stale = dependency_engine.compute_context(stale_candles)
    
    assert freshness == "STALE"
    assert age > 3600
    assert ctx_stale.feature_vector["ema200"] is not None  # Mathematically computable!

    # Scenario B: 5 candles from 1 second ago (LIVE, but INSUFFICIENT)
    recent_time = time.time()
    live_short_candles = [
        {"time": int(recent_time - (5 - i)), "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 1000}
        for i in range(5)
    ]
    freshness_live, age_live = _evaluate_freshness(live_short_candles, is_live_feed=True)
    ctx_live = dependency_engine.compute_context(live_short_candles)
    
    assert freshness_live == "LIVE"
    assert ctx_live.feature_vector["ema200"] is None  # Mathematically insufficient!


# ---------------------------------------------------------------------------
# 6. Zero vs Missing Data Contract
# ---------------------------------------------------------------------------

def test_zero_vs_missing_volume():
    """
    Phase 12 & 13: Strict distinction between zero volume and missing volume.
    """
    # 1. Missing volume column
    candles_no_vol = generate_synthetic_candles(n=50, missing_volume=True)
    ctx_no_vol = dependency_engine.compute_context(candles_no_vol)
    assert ctx_no_vol.feature_vector["rvol"] is None
    assert ctx_no_vol.feature_vector["vwap"] is None

    # 2. Zero volume recorded (all volume = 0.0)
    candles_zero_vol = generate_synthetic_candles(n=50, zero_volume=True)
    ctx_zero_vol = dependency_engine.compute_context(candles_zero_vol)
    assert ctx_zero_vol.feature_vector["vwap"] is None  # Cumulative volume is 0 -> VWAP is None, NOT close!
    assert ctx_zero_vol.feature_vector["rvol"] is None  # Average volume is 0 -> RVOL is None, NOT 1.0 or 0.0!


# ---------------------------------------------------------------------------
# 7. Strict Lookahead Bias Prevention
# ---------------------------------------------------------------------------

def test_lookahead_prevention_across_all_indicators():
    """
    Phase 8 & 13: Changing future candle T+1 has 0.0% impact on indicator values at candle T.
    """
    base_candles = generate_synthetic_candles(n=60, base_price=100.0)
    ctx_base = dependency_engine.compute_context(base_candles)
    
    # Dataset with wild future candles appended
    future_candles = list(base_candles) + [
        {"time": int(time.time() + 60), "open": 9999.0, "high": 10000.0, "low": 9900.0, "close": 9950.0, "volume": 9999999},
        {"time": int(time.time() + 120), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0, "volume": 1},
    ]
    ctx_future = dependency_engine.compute_context(future_candles)
    
    # Compare every indicator series at index 59 (the last bar of base_candles)
    for key in ["close", "ema20", "ema50", "rsi14", "vwap", "atr14", "macd", "bb_upper", "rvol"]:
        base_val = ctx_base.series[key][59]
        future_val = ctx_future.series[key][59]
        if base_val is None:
            assert future_val is None
        else:
            assert abs(base_val - future_val) < 1e-9, f"Lookahead detected in {key}: {base_val} != {future_val}"


# ---------------------------------------------------------------------------
# 8. Symbol & Timeframe Isolation
# ---------------------------------------------------------------------------

def test_symbol_and_timeframe_isolation():
    """
    Phase 9 & 10: Calculations are strictly bound to symbol and timeframe context.
    """
    candles_rel = generate_synthetic_candles(n=60, base_price=1300.0)
    candles_tcs = generate_synthetic_candles(n=60, base_price=3400.0)
    
    ctx_rel = dependency_engine.compute_context(candles_rel, symbol="RELIANCE.NS", timeframe="5m")
    ctx_tcs = dependency_engine.compute_context(candles_tcs, symbol="TCS.NS", timeframe="1h")
    
    assert ctx_rel.symbol == "RELIANCE.NS"
    assert ctx_rel.timeframe == "5m"
    assert ctx_rel.feature_vector["close"] < 2000.0
    
    assert ctx_tcs.symbol == "TCS.NS"
    assert ctx_tcs.timeframe == "1h"
    assert ctx_tcs.feature_vector["close"] > 3000.0


# ---------------------------------------------------------------------------
# 9. Complete Strategy Dependency Audit
# ---------------------------------------------------------------------------

def test_strategy_dependency_declarations_against_specs():
    """
    Phase 18: Every dependency declared by the 8 canonical strategies is registered in INDICATOR_SPECS.
    """
    for strat in registry_manager.list_all():
        for rule in strat.entry_rules + strat.exit_rules + strat.invalidation_rules:
            for dep in rule.dependency_keys:
                canon = normalize_dependency_key(dep)
                assert canon in INDICATOR_SPECS, f"Strategy {strat.strategy_id} uses unknown dependency: {dep}"


def test_strategy_evaluation_with_hardened_dependency_engine():
    """
    Phase 25: All 8 existing strategies evaluate cleanly and deterministically with the hardened engine.
    """
    candles = generate_synthetic_candles(n=60, base_price=100.0)
    results = evaluate_all_strategies(candles, is_live_feed=True)
    
    assert len(results) == 8
    for res in results:
        assert res.strategy_id in STRATEGY_REGISTRY
        assert res.state in [StrategyState.ACTIVE, StrategyState.PARTIAL, StrategyState.INACTIVE, StrategyState.CONFLICTED]
        assert len(res.rule_evaluations) > 0
        for re in res.rule_evaluations:
            assert re.outcome in [RuleOutcome.PASS, RuleOutcome.FAIL, RuleOutcome.UNAVAILABLE]
