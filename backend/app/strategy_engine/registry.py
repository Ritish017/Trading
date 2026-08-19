"""
Strategy Lab — Strategy Library (Registry V3 Expansion)
=======================================================
Defines the canonical, extensible library of 20 systematic quantitative strategies.

Invariants
----------
- Each rule's condition_fn receives a Dict[str, Any] feature vector and returns:
    True  → PASS
    False → FAIL
    None  → UNAVAILABLE (dependency value is None/NaN)
- No fabricated values. Every condition tests a real computed indicator.
- Metadata is fully structured with StrategyCategory, StrategyVisualization, and StrategyDataRequirements.
"""

from typing import Dict, List, Optional, Set, Union
from backend.app.strategy_engine.dsl import (
    StrategyDefinition,
    StrategyRule,
    StrategyCategory,
    StrategyVisualization,
    StrategyDataRequirements,
    ResearchParameter,
)


def _v(fv: dict, key: str):
    """Safe extractor — returns the value or None if missing/NaN."""
    import math
    val = fv.get(key)
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _cond(fv: dict, *keys, fn):
    """Evaluate fn(*values) only if all keys are non-None."""
    vals = [_v(fv, k) for k in keys]
    if any(v is None for v in vals):
        return None
    return fn(*vals)


# ===========================================================================
# 1. TREND FOLLOWING STRATEGIES
# ===========================================================================

# Strategy 1 — EMA Golden Cross
EMA_GOLDEN_CROSS = StrategyDefinition(
    strategy_id="EMA_GOLDEN_CROSS",
    name="EMA Golden Cross",
    short_name="EMA CROSS",
    category=StrategyCategory.TREND,
    description=(
        "Classic trend-following setup: EMA20 crosses above EMA50 indicating "
        "a shift to bullish moving average alignment. RSI(14) < 70 confirms price is not overbought."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=55,
    requirements=StrategyDataRequirements(
        min_candles=55,
        requires_volume=False,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20", "ema50", "ema200"],
        subpanels=["rsi14"],
        color="#22d3ee",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="fast_period",
            name="Fast EMA Period",
            param_type="int",
            default_value=20,
            minimum=10,
            maximum=30,
            step=5,
            description="Lookback period for fast exponential moving average",
        ),
        ResearchParameter(
            parameter_id="slow_period",
            name="Slow EMA Period",
            param_type="int",
            default_value=50,
            minimum=40,
            maximum=100,
            step=10,
            description="Lookback period for slow baseline exponential moving average",
        ),
        ResearchParameter(
            parameter_id="max_rsi",
            name="Max Overbought RSI",
            param_type="float",
            default_value=70.0,
            minimum=60.0,
            maximum=80.0,
            step=5.0,
            description="Ceiling threshold for RSI(14) to avoid overextended entries",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="ema20_above_ema50",
            label="EMA20 > EMA50  (golden cross region)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="price_above_ema20",
            label="Price > EMA20  (price above short-term trend)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_not_overbought",
            label="RSI(14) < 70  (not overbought threshold)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=70.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 70.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="ema_death_cross",
            label="EMA20 < EMA50  (moving average reversal — strategy exit condition)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
    ],
    tags=["trend", "ema", "crossover", "swing"],
)

# Strategy 2 — Supertrend ATR Proxy
SUPERTREND_PROXY = StrategyDefinition(
    strategy_id="SUPERTREND_PROXY",
    name="Supertrend ATR Proxy",
    short_name="SUPERTREND PROXY",
    category=StrategyCategory.TREND,
    description=(
        "This strategy uses an ATR-based trend and dynamic support approximation (VWAP − 1.5×ATR) "
        "and is an ATR proxy, not the canonical multi-band Supertrend indicator. "
        "Price must remain above EMA50 and above the dynamic support level with RSI(14) > 50."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=50,
    requirements=StrategyDataRequirements(
        min_candles=50,
        requires_volume=True,
        requires_vwap=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema50", "vwap", "supertrend_band"],
        subpanels=["rsi14"],
        color="#a3e635",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="ema_period",
            name="Baseline Trend EMA Period",
            param_type="int",
            default_value=50,
            minimum=20,
            maximum=100,
            step=10,
            description="Lookback period for underlying trend filter",
        ),
        ResearchParameter(
            parameter_id="atr_multiplier",
            name="ATR Support Multiplier",
            param_type="float",
            default_value=1.5,
            minimum=1.0,
            maximum=3.0,
            step=0.5,
            description="Multiplier for dynamic support distance from VWAP",
        ),
        ResearchParameter(
            parameter_id="min_rsi",
            name="Minimum RSI Zone",
            param_type="float",
            default_value=50.0,
            minimum=40.0,
            maximum=60.0,
            step=5.0,
            description="Floor threshold for RSI(14) momentum",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="price_above_ema50_st",
            label="Price > EMA50  (primary trend is up)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_trend_zone",
            label="RSI(14) > 50  (bullish momentum zone)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
        StrategyRule(
            rule_id="atr_dynamic_support",
            label="Price > VWAP − 1.5×ATR  (above dynamic support band)",
            dependency_keys=["close", "vwap", "atr14"],
            operator=">",
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c > (v - 1.5 * a)
            ),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_atr_band",
            label="Price < VWAP − 1.5×ATR  (support level breached — strategy exit condition)",
            dependency_keys=["close", "vwap", "atr14"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c < (v - 1.5 * a)
            ),
        ),
    ],
    tags=["trend", "atr", "supertrend-proxy", "dynamic-support"],
)

# Strategy 3 — ADX Trend Strength
ADX_TREND_STRENGTH = StrategyDefinition(
    strategy_id="ADX_TREND_STRENGTH",
    name="ADX Trend Strength",
    short_name="ADX TREND",
    category=StrategyCategory.TREND,
    description=(
        "Identifies strong directional trend: ADX(14) > 25.0 confirms significant trend momentum, "
        "with +DI > -DI confirming bullish directional bias and Price > EMA50."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=40,
    requirements=StrategyDataRequirements(
        min_candles=40,
        requires_ohlc=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema50"],
        subpanels=["adx"],
        color="#06b6d4",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="min_adx",
            name="Minimum ADX Trend Level",
            param_type="float",
            default_value=25.0,
            minimum=20.0,
            maximum=35.0,
            step=5.0,
            description="Minimum ADX threshold for strong directional momentum",
        ),
        ResearchParameter(
            parameter_id="ema_trend",
            name="Trend Filter EMA Period",
            param_type="int",
            default_value=50,
            minimum=20,
            maximum=100,
            step=10,
            description="Lookback period for baseline trend filter",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="adx_strong_trend",
            label="ADX(14) > 25.0  (established trend strength)",
            dependency_keys=["adx"],
            operator=">",
            threshold=25.0,
            condition_fn=lambda fv: _cond(fv, "adx", fn=lambda a: a > 25.0),
        ),
        StrategyRule(
            rule_id="bullish_directional_movement",
            label="+DI > -DI  (positive directional movement)",
            dependency_keys=["plus_di", "minus_di"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "plus_di", "minus_di", fn=lambda p, m: p > m),
        ),
        StrategyRule(
            rule_id="price_above_trend_filter",
            label="Price > EMA50  (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="trend_weakening",
            label="ADX(14) < 20.0  (trend exhaustion — strategy exit condition)",
            dependency_keys=["adx"],
            operator="<",
            threshold=20.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "adx", fn=lambda a: a < 20.0),
        ),
        StrategyRule(
            rule_id="di_bearish_cross",
            label="+DI < -DI  (directional reversal — strategy exit condition)",
            dependency_keys=["plus_di", "minus_di"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "plus_di", "minus_di", fn=lambda p, m: p < m),
        ),
    ],
    tags=["trend", "adx", "dmi", "momentum"],
)

# Strategy 4 — EMA Pullback
EMA_PULLBACK = StrategyDefinition(
    strategy_id="EMA_PULLBACK",
    name="EMA Pullback Continuation",
    short_name="EMA PULLBACK",
    category=StrategyCategory.TREND,
    description=(
        "Identifies trend continuation entry: in an established uptrend (EMA20 > EMA50 and Price > EMA50), "
        "price pulls back toward the EMA20 support zone (Low <= EMA20 * 1.005 and Close >= EMA20 * 0.995) "
        "with RSI(14) in the 45-65 recovery zone."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=55,
    requirements=StrategyDataRequirements(
        min_candles=55,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20", "ema50"],
        subpanels=["rsi14"],
        color="#14b8a6",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="ema_uptrend_context",
            label="EMA20 > EMA50  (established uptrend context)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="pullback_to_ema20",
            label="Low <= EMA20*1.005 & Close >= EMA20*0.995  (pullback to 20-period average)",
            dependency_keys=["low", "close", "ema20"],
            condition_fn=lambda fv: _cond(
                fv, "low", "close", "ema20",
                fn=lambda l, c, e: (l <= e * 1.005) and (c >= e * 0.995)
            ),
        ),
        StrategyRule(
            rule_id="trend_filter_intact",
            label="Price > EMA50  (macro trend intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_pullback_range",
            label="45.0 <= RSI(14) <= 65.0  (healthy pullback oscillator range)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 45.0 <= r <= 65.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="trend_breakdown",
            label="Price < EMA50  (trend breakdown — strategy exit condition)",
            dependency_keys=["close", "ema50"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
    ],
    tags=["trend", "pullback", "ema", "continuation"],
)

# Strategy 5 — Moving Average Momentum Stack
MOVING_AVERAGE_MOMENTUM_STACK = StrategyDefinition(
    strategy_id="MOVING_AVERAGE_MOMENTUM_STACK",
    name="Moving Average Momentum Stack",
    short_name="MA STACK",
    category=StrategyCategory.TREND,
    description=(
        "Triple moving average trend stack: EMA20 > EMA50 AND EMA50 > EMA200 (perfect bullish moving average alignment) "
        "with Price > EMA20 and RSI(14) in 50-75 range. Requires 200+ candles; evaluates to UNAVAILABLE if EMA200 cannot be computed."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="1D",
    min_candles=200,
    requirements=StrategyDataRequirements(
        min_candles=200,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20", "ema50", "ema200"],
        subpanels=["rsi14"],
        color="#6366f1",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="ema_fast_above_medium",
            label="EMA20 > EMA50  (fast trend above medium)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="ema_medium_above_slow",
            label="EMA50 > EMA200  (medium trend above long-term baseline)",
            dependency_keys=["ema50", "ema200"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "ema50", "ema200", fn=lambda b, c: b > c),
        ),
        StrategyRule(
            rule_id="price_above_fast_ema",
            label="Price > EMA20  (price leading the stack)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_trend_alignment",
            label="50.0 <= RSI(14) <= 75.0  (bullish trend momentum band)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 50.0 <= r <= 75.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="ema_stack_invalidation",
            label="EMA20 < EMA50  (fast/medium crossover breakdown — strategy exit condition)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
    ],
    tags=["trend", "ma-stack", "ema200", "macro-trend"],
)


# ===========================================================================
# 2. MOMENTUM STRATEGIES
# ===========================================================================

# Strategy 6 — VWAP Momentum Breakout
VWAP_MOMENTUM = StrategyDefinition(
    strategy_id="VWAP_MOMENTUM",
    name="VWAP Momentum Breakout",
    short_name="VWAP MOM",
    category=StrategyCategory.MOMENTUM,
    description=(
        "Long bias when price is above VWAP, EMA20 > EMA50 (trend aligned), "
        "RSI(14) > 55 (momentum zone), and Relative Volume ≥ 1.2 (above-average trading volume)."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=50,
    requirements=StrategyDataRequirements(
        min_candles=50,
        requires_volume=True,
        requires_vwap=True,
        requires_intraday=True,
        supported_timeframes=["1m", "5m", "15m"],
    ),
    visualization=StrategyVisualization(
        overlays=["vwap", "ema20", "ema50"],
        subpanels=["rsi14"],
        color="#e879f9",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="min_rvol",
            name="Minimum Relative Volume",
            param_type="float",
            default_value=1.5,
            minimum=1.0,
            maximum=3.0,
            step=0.25,
            description="Minimum relative volume multiplier for momentum validation",
        ),
        ResearchParameter(
            parameter_id="min_rsi",
            name="Minimum Momentum RSI",
            param_type="float",
            default_value=55.0,
            minimum=50.0,
            maximum=65.0,
            step=5.0,
            description="Minimum RSI(14) threshold for momentum acceleration",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP",
            dependency_keys=["close", "vwap"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="ema_trend_aligned",
            label="EMA20 > EMA50  (uptrend aligned)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="rsi_momentum",
            label="RSI(14) > 55  (momentum zone)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=55.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="volume_surge",
            label="Relative Volume ≥ 1.2  (above-average volume)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.2,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.2),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_ema20",
            label="Price < EMA20  (trend breakdown — strategy exit condition)",
            dependency_keys=["close", "ema20"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_weakness",
            label="RSI(14) < 45  (momentum fading — strategy exit condition)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=45.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 45.0),
        ),
    ],
    tags=["momentum", "vwap", "ema", "intraday"],
)

# Strategy 7 — MACD Bullish Crossover
MACD_CROSSOVER = StrategyDefinition(
    strategy_id="MACD_CROSSOVER",
    name="MACD Bullish Crossover",
    short_name="MACD CROSS",
    category=StrategyCategory.MOMENTUM,
    description=(
        "MACD line crosses above the signal line (12, 26, 9), with a positive histogram "
        "and price positioned above EMA50 (trend filter)."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=40,
    requirements=StrategyDataRequirements(
        min_candles=40,
        requires_volume=False,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema50"],
        subpanels=["macd"],
        color="#38bdf8",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="macd_above_signal",
            label="MACD Line > Signal Line  (bullish crossover region)",
            dependency_keys=["macd", "macd_signal"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m > s),
        ),
        StrategyRule(
            rule_id="macd_histogram_positive",
            label="MACD Histogram > 0  (positive momentum)",
            dependency_keys=["macd_histogram"],
            operator=">",
            threshold=0.0,
            condition_fn=lambda fv: _cond(fv, "macd_histogram", fn=lambda h: h > 0),
        ),
        StrategyRule(
            rule_id="price_above_ema50",
            label="Price > EMA50  (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="macd_bearish_cross",
            label="MACD Line < Signal Line  (bearish crossover — strategy exit condition)",
            dependency_keys=["macd", "macd_signal"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m < s),
        ),
    ],
    tags=["momentum", "macd", "crossover", "trend"],
)

# Strategy 8 — RSI Momentum Continuation
RSI_MOMENTUM = StrategyDefinition(
    strategy_id="RSI_MOMENTUM",
    name="RSI Momentum Continuation",
    short_name="RSI MOMENTUM",
    category=StrategyCategory.MOMENTUM,
    description=(
        "Bullish momentum continuation: RSI(14) sustained in the 55.0 to 75.0 positive acceleration zone "
        "(distinct from oversold reversal), confirmed by Price > EMA50 and positive MACD histogram."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=50,
    requirements=StrategyDataRequirements(
        min_candles=50,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema50"],
        subpanels=["rsi14"],
        color="#ec4899",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="rsi_momentum_zone",
            label="55.0 <= RSI(14) <= 75.0  (positive momentum acceleration band)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 55.0 <= r <= 75.0),
        ),
        StrategyRule(
            rule_id="price_above_ema50",
            label="Price > EMA50  (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="macd_histogram_positive",
            label="MACD Histogram > 0  (positive momentum confirmation)",
            dependency_keys=["macd_histogram"],
            operator=">",
            threshold=0.0,
            condition_fn=lambda fv: _cond(fv, "macd_histogram", fn=lambda h: h > 0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="rsi_loss_of_momentum",
            label="RSI(14) < 50.0  (momentum breakdown — strategy exit condition)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=50.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 50.0),
        ),
        StrategyRule(
            rule_id="rsi_overbought_exhaustion",
            label="RSI(14) > 80.0  (extreme overbought exhaustion — strategy exit condition)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=80.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 80.0),
        ),
    ],
    tags=["momentum", "rsi", "continuation", "trend"],
)

# Strategy 9 — Rate of Change (ROC) Momentum
ROC_MOMENTUM = StrategyDefinition(
    strategy_id="ROC_MOMENTUM",
    name="Rate of Change Momentum",
    short_name="ROC MOMENTUM",
    category=StrategyCategory.MOMENTUM,
    description=(
        "Measures 12-period Rate of Change acceleration: ROC(12) > 1.5% confirms positive price velocity, "
        "supported by Price > EMA20 and Relative Volume >= 1.2."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=25,
    requirements=StrategyDataRequirements(
        min_candles=25,
        requires_volume=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20"],
        subpanels=["roc12"],
        color="#8b5cf6",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="roc_acceleration",
            label="ROC(12) > +1.5%  (velocity expansion)",
            dependency_keys=["roc12"],
            operator=">",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "roc12", fn=lambda r: r > 1.5),
        ),
        StrategyRule(
            rule_id="price_above_ema20",
            label="Price > EMA20  (price above short-term trend)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="volume_confirmation",
            label="Relative Volume >= 1.2  (liquidity confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.2,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.2),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="roc_momentum_loss",
            label="ROC(12) < 0.0%  (momentum reversal — strategy exit condition)",
            dependency_keys=["roc12"],
            operator="<",
            threshold=0.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "roc12", fn=lambda r: r < 0.0),
        ),
    ],
    tags=["momentum", "roc", "velocity"],
)


# ===========================================================================
# 3. MEAN REVERSION STRATEGIES
# ===========================================================================

# Strategy 10 — RSI Oversold Reversal
RSI_OVERSOLD_REVERSAL = StrategyDefinition(
    strategy_id="RSI_OVERSOLD_REVERSAL",
    name="RSI Oversold Reversal",
    short_name="RSI REVERSAL",
    category=StrategyCategory.MEAN_REVERSION,
    description=(
        "Counter-trend setup: price is below VWAP, RSI(14) < 35 indicates an oversold condition, "
        "and Relative Volume ≥ 1.5 indicates heightened liquidity during the move."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=30,
    requirements=StrategyDataRequirements(
        min_candles=30,
        requires_volume=True,
        requires_vwap=True,
        supported_timeframes=["1m", "5m", "15m"],
    ),
    visualization=StrategyVisualization(
        overlays=["vwap"],
        subpanels=["rsi14"],
        color="#f97316",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="oversold_threshold",
            name="Oversold RSI Floor",
            param_type="float",
            default_value=35.0,
            minimum=20.0,
            maximum=40.0,
            step=5.0,
            description="Oversold threshold for entry trigger",
        ),
        ResearchParameter(
            parameter_id="exit_rsi_threshold",
            name="Exit Target RSI",
            param_type="float",
            default_value=55.0,
            minimum=45.0,
            maximum=65.0,
            step=5.0,
            description="Normalized RSI threshold for strategy exit",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="rsi_oversold",
            label="RSI(14) < 35  (oversold reversal zone)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=35.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 35.0),
        ),
        StrategyRule(
            rule_id="price_below_vwap",
            label="Price < VWAP  (extended below session VWAP)",
            dependency_keys=["close", "vwap"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
        StrategyRule(
            rule_id="volume_flush",
            label="Relative Volume ≥ 1.5  (elevated volume condition)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="rsi_recovered",
            label="RSI(14) > 55  (momentum normalized — strategy exit condition)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=55.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP  (mean reversion target — strategy exit condition)",
            dependency_keys=["close", "vwap"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
    ],
    tags=["mean-reversion", "rsi", "reversal", "intraday"],
)

# Strategy 11 — Bollinger Mean Reversion
BOLLINGER_MEAN_REVERSION = StrategyDefinition(
    strategy_id="BOLLINGER_MEAN_REVERSION",
    name="Bollinger Mean Reversion",
    short_name="BB REVERSION",
    category=StrategyCategory.MEAN_REVERSION,
    description=(
        "Counter-trend mean reversion: Price stretches to or below the lower Bollinger Band (Close <= bb_lower * 1.005) "
        "with RSI(14) < 40.0 indicating short-term oversold extension. Exit target is the 20-period Middle Band."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=25,
    requirements=StrategyDataRequirements(
        min_candles=25,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["bb_upper", "bb_middle", "bb_lower"],
        subpanels=["rsi14"],
        color="#0ea5e9",
    ),
    research_parameters=[
        ResearchParameter(
            parameter_id="band_std",
            name="Bollinger Band Std Deviation",
            param_type="float",
            default_value=2.0,
            minimum=1.5,
            maximum=2.5,
            step=0.25,
            description="Standard deviation width for Bollinger envelope",
        ),
        ResearchParameter(
            parameter_id="min_rsi",
            name="Maximum Entry RSI",
            param_type="float",
            default_value=40.0,
            minimum=25.0,
            maximum=45.0,
            step=5.0,
            description="RSI ceiling for oversold Bollinger bounce",
        ),
    ],
    entry_rules=[
        StrategyRule(
            rule_id="price_at_lower_band",
            label="Price <= Bollinger Lower Band * 1.005  (band excursion)",
            dependency_keys=["close", "bb_lower"],
            condition_fn=lambda fv: _cond(fv, "close", "bb_lower", fn=lambda c, l: c <= l * 1.005),
        ),
        StrategyRule(
            rule_id="rsi_oversold_filter",
            label="RSI(14) < 40.0  (oversold oscillator confirmation)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=40.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 40.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="target_middle_band_reached",
            label="Price >= Bollinger Middle Band  (mean reversion target — strategy exit condition)",
            dependency_keys=["close", "bb_middle"],
            operator=">=",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "bb_middle", fn=lambda c, m: c >= m),
        ),
    ],
    tags=["mean-reversion", "bollinger", "reversal"],
)

# Strategy 12 — VWAP Mean Reversion
VWAP_MEAN_REVERSION = StrategyDefinition(
    strategy_id="VWAP_MEAN_REVERSION",
    name="VWAP Mean Reversion",
    short_name="VWAP REVERSION",
    category=StrategyCategory.MEAN_REVERSION,
    description=(
        "Session mean reversion: Price stretches >= 1.5% below session VWAP (vwap_distance_pct <= -1.5) "
        "with RSI(14) < 40.0. Strategy defines an excursion hypothesis toward VWAP midline."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=25,
    requirements=StrategyDataRequirements(
        min_candles=25,
        requires_volume=True,
        requires_vwap=True,
        requires_intraday=True,
        supported_timeframes=["1m", "5m", "15m"],
    ),
    visualization=StrategyVisualization(
        overlays=["vwap"],
        subpanels=["rsi14"],
        color="#d946ef",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="vwap_downside_stretch",
            label="Distance from VWAP <= -1.5%  (downside statistical extension)",
            dependency_keys=["vwap_distance_pct"],
            operator="<=",
            threshold=-1.5,
            condition_fn=lambda fv: _cond(fv, "vwap_distance_pct", fn=lambda d: d <= -1.5),
        ),
        StrategyRule(
            rule_id="rsi_oversold_confirmation",
            label="RSI(14) < 40.0  (oversold confirmation)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=40.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 40.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="vwap_reversion_target",
            label="Price >= VWAP  (mean reversion target — strategy exit condition)",
            dependency_keys=["close", "vwap"],
            operator=">=",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c >= v),
        ),
    ],
    tags=["mean-reversion", "vwap", "intraday"],
)


# ===========================================================================
# 4. BREAKOUT STRATEGIES
# ===========================================================================

# Strategy 13 — Bollinger Band Squeeze
BOLLINGER_SQUEEZE = StrategyDefinition(
    strategy_id="BOLLINGER_SQUEEZE",
    name="Bollinger Band Squeeze",
    short_name="BB SQUEEZE",
    category=StrategyCategory.BREAKOUT,
    description=(
        "Identifies volatility expansion: price crosses above the upper Bollinger Band (20, 2σ), "
        "confirmed by RSI(14) > 50 and Relative Volume ≥ 1.3."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=30,
    requirements=StrategyDataRequirements(
        min_candles=30,
        requires_volume=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["bb_upper", "bb_middle", "bb_lower"],
        subpanels=["rsi14"],
        color="#10b981",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="price_above_bb_upper",
            label="Price > Bollinger Upper Band  (band expansion)",
            dependency_keys=["close", "bb_upper"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "bb_upper", fn=lambda c, b: c > b),
        ),
        StrategyRule(
            rule_id="rsi_expanding",
            label="RSI(14) > 50  (positive momentum confirmation)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
        StrategyRule(
            rule_id="volume_confirmation",
            label="Relative Volume ≥ 1.3  (volume expansion confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.3,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.3),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_bb_middle",
            label="Price < Bollinger Middle Band  (re-entry below midline — strategy exit condition)",
            dependency_keys=["close", "bb_middle"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "bb_middle", fn=lambda c, b: c < b),
        ),
    ],
    tags=["breakout", "bollinger", "volatility", "squeeze"],
)

# Strategy 14 — Opening Range Breakout (ORB)
ORB_BREAKOUT = StrategyDefinition(
    strategy_id="ORB_BREAKOUT",
    name="Opening Range Breakout (ORB)",
    short_name="ORB BREAKOUT",
    category=StrategyCategory.BREAKOUT,
    description=(
        "Price breaks above session VWAP during early session trading, "
        "with RSI(14) > 55 and Relative Volume ≥ 1.5 confirming directional expansion."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=20,
    requirements=StrategyDataRequirements(
        min_candles=20,
        requires_volume=True,
        requires_vwap=True,
        requires_intraday=True,
        supported_timeframes=["1m", "5m", "15m"],
    ),
    visualization=StrategyVisualization(
        overlays=["vwap", "orb_high", "orb_low"],
        subpanels=["rsi14"],
        color="#fbbf24",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="price_above_vwap_orb",
            label="Price > VWAP  (breakout above session reference level)",
            dependency_keys=["close", "vwap"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="rsi_breakout_strength",
            label="RSI(14) > 55  (momentum confirms breakout)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=55.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="orb_volume",
            label="Relative Volume ≥ 1.5  (elevated session volume)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_back_below_vwap",
            label="Price < VWAP  (breakout invalidation — strategy exit condition)",
            dependency_keys=["close", "vwap"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
    ],
    tags=["breakout", "orb", "intraday", "momentum"],
)

# Strategy 15 — Donchian Channel Breakout
DONCHIAN_BREAKOUT = StrategyDefinition(
    strategy_id="DONCHIAN_BREAKOUT",
    name="Donchian Channel Breakout",
    short_name="DONCHIAN BREAK",
    category=StrategyCategory.BREAKOUT,
    description=(
        "20-period Turtle breakout system: Price exceeds the highest high of prior 20 bars (strictly prior candles, no lookahead), "
        "confirmed by Relative Volume >= 1.3 and Price > EMA50."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=30,
    requirements=StrategyDataRequirements(
        min_candles=30,
        requires_ohlc=True,
        requires_volume=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["donchian_high", "donchian_low", "ema50"],
        subpanels=["rsi14"],
        color="#eab308",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="donchian_channel_breakout",
            label="Price > Donchian Upper (20)  (breakout above 20-period high)",
            dependency_keys=["close", "donchian_high"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "donchian_high", fn=lambda c, d: c > d),
        ),
        StrategyRule(
            rule_id="volume_expansion",
            label="Relative Volume >= 1.3  (volume expansion confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.3,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.3),
        ),
        StrategyRule(
            rule_id="trend_filter",
            label="Price > EMA50  (trend alignment intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="channel_midpoint_exit",
            label="Price < Donchian Midpoint  (exit below channel mean — strategy exit condition)",
            dependency_keys=["close", "donchian_mid"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "donchian_mid", fn=lambda c, m: c < m),
        ),
    ],
    tags=["breakout", "donchian", "turtle", "trend"],
)

# Strategy 16 — Previous Day High/Low Breakout
PREVIOUS_DAY_BREAKOUT = StrategyDefinition(
    strategy_id="PREVIOUS_DAY_BREAKOUT",
    name="Previous Day High Breakout",
    short_name="PDH BREAKOUT",
    category=StrategyCategory.BREAKOUT,
    description=(
        "Intraday breakout above the previous trading day's factual high (calculated from prior session candles, not today's session), "
        "confirmed by Price > VWAP and Relative Volume >= 1.5. Evaluates as UNAVAILABLE on non-intraday or single-session datasets."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=25,
    requirements=StrategyDataRequirements(
        min_candles=25,
        requires_ohlc=True,
        requires_volume=True,
        requires_vwap=True,
        requires_intraday=True,
        supported_timeframes=["1m", "5m", "15m"],
    ),
    visualization=StrategyVisualization(
        overlays=["prev_day_high", "prev_day_low", "vwap"],
        subpanels=["rsi14"],
        color="#f59e0b",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="breakout_above_pdh",
            label="Price > Previous Day High  (breakout above prior session resistance)",
            dependency_keys=["close", "prev_day_high"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "prev_day_high", fn=lambda c, p: c > p),
        ),
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP  (session trend alignment)",
            dependency_keys=["close", "vwap"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="volume_surge",
            label="Relative Volume >= 1.5  (elevated volume expansion)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="reentry_below_pdh",
            label="Price < Previous Day High  (re-entry below breakout level — strategy exit condition)",
            dependency_keys=["close", "prev_day_high"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "prev_day_high", fn=lambda c, p: c < p),
        ),
    ],
    tags=["breakout", "pdh", "intraday", "levels"],
)


# ===========================================================================
# 5. VOLUME & VOLATILITY STRATEGIES
# ===========================================================================

# Strategy 17 — Relative Volume Surge
RVOL_SURGE = StrategyDefinition(
    strategy_id="RVOL_SURGE",
    name="Relative Volume Surge",
    short_name="RVOL SURGE",
    category=StrategyCategory.VOLUME,
    description=(
        "Flags when Relative Volume spikes ≥ 2.0× the 20-period average, price is above EMA20, "
        "and RSI is within the strategy's defined 45–70 range."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="5m",
    min_candles=25,
    requirements=StrategyDataRequirements(
        min_candles=25,
        requires_volume=True,
        supported_timeframes=["1m", "5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20"],
        subpanels=["rsi14"],
        color="#a855f7",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="rvol_spike",
            label="Relative Volume ≥ 2.0×  (unusually high volume relative to 20-period baseline)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=2.0,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 2.0),
        ),
        StrategyRule(
            rule_id="price_above_ema20_rvol",
            label="Price > EMA20  (price above short-term trend)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_accumulation_zone",
            label="45 < RSI(14) < 70  (strategy defined range, not overbought)",
            dependency_keys=["rsi14"],
            operator="between",
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 45.0 < r < 70.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="rvol_normalized",
            label="Relative Volume < 1.0  (volume normalization — strategy exit condition)",
            dependency_keys=["rvol"],
            operator="<",
            threshold=1.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r < 1.0),
        ),
        StrategyRule(
            rule_id="rsi_overbought_exit",
            label="RSI(14) > 70  (overbought threshold — strategy exit condition)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=70.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 70.0),
        ),
    ],
    tags=["volume", "rvol", "surge"],
)

# Strategy 18 — Volume Breakout Confirmation
VOLUME_BREAKOUT_CONFIRMATION = StrategyDefinition(
    strategy_id="VOLUME_BREAKOUT_CONFIRMATION",
    name="Volume Breakout Confirmation",
    short_name="VOL BREAKOUT",
    category=StrategyCategory.VOLUME,
    description=(
        "High-volume price breakout: Price breaks above the prior 20-period highest close (highest_high_20) "
        "confirmed by Relative Volume >= 2.0x baseline and Price > EMA50."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=30,
    requirements=StrategyDataRequirements(
        min_candles=30,
        requires_volume=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["highest_high_20", "ema50"],
        subpanels=["rsi14"],
        color="#10b981",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="price_new_20_high",
            label="Price > Prior 20-Bar Highest Close  (price breakout)",
            dependency_keys=["close", "highest_high_20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "highest_high_20", fn=lambda c, h: c > h),
        ),
        StrategyRule(
            rule_id="extreme_volume_surge",
            label="Relative Volume >= 2.0x  (abnormal institutional liquidity surge)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=2.0,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 2.0),
        ),
        StrategyRule(
            rule_id="trend_alignment",
            label="Price > EMA50  (macro trend alignment intact)",
            dependency_keys=["close", "ema50"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="reentry_below_breakout",
            label="Price < Breakout Level  (breakout failure — strategy exit condition)",
            dependency_keys=["close", "highest_high_20"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "highest_high_20", fn=lambda c, h: c < h),
        ),
    ],
    tags=["volume", "breakout", "rvol", "liquidity"],
)

# Strategy 19 — Price-Volume Divergence / Money Flow
PRICE_VOLUME_DIVERGENCE = StrategyDefinition(
    strategy_id="PRICE_VOLUME_DIVERGENCE",
    name="Price-Volume Divergence (CMF)",
    short_name="PV DIVERGENCE",
    category=StrategyCategory.VOLUME,
    description=(
        "Identifies positive money flow accumulation: Price remains above EMA20 while 20-period Chaikin Money Flow (CMF20) > +0.10 "
        "confirms positive capital inflow, supported by RSI(14) in 50-70 range."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=30,
    requirements=StrategyDataRequirements(
        min_candles=30,
        requires_ohlc=True,
        requires_volume=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20"],
        subpanels=["cmf20"],
        color="#84cc16",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="positive_money_flow",
            label="CMF(20) > +0.10  (sustained capital inflow)",
            dependency_keys=["cmf20"],
            operator=">",
            threshold=0.10,
            condition_fn=lambda fv: _cond(fv, "cmf20", fn=lambda m: m > 0.10),
        ),
        StrategyRule(
            rule_id="price_above_ema20",
            label="Price > EMA20  (price trend alignment)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_confirmation",
            label="50.0 <= RSI(14) <= 70.0  (stable accumulation momentum)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 50.0 <= r <= 70.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="negative_money_flow",
            label="CMF(20) < 0.0  (capital outflow — strategy exit condition)",
            dependency_keys=["cmf20"],
            operator="<",
            threshold=0.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "cmf20", fn=lambda m: m < 0.0),
        ),
    ],
    tags=["volume", "cmf", "money-flow", "accumulation"],
)

# Strategy 20 — ATR Volatility Expansion
ATR_VOLATILITY_EXPANSION = StrategyDefinition(
    strategy_id="ATR_VOLATILITY_EXPANSION",
    name="ATR Volatility Expansion",
    short_name="ATR EXPANSION",
    category=StrategyCategory.VOLATILITY,
    description=(
        "Detects volatility breakout expansion: Current ATR(14) exceeds 1.3x its 20-period baseline average (ATR_SMA20), "
        "with Price > EMA20 and RSI(14) > 50 confirming directional expansion."
    ),
    version="1.0.0",
    enabled=True,
    experimental=False,
    timeframe_hint="15m",
    min_candles=40,
    requirements=StrategyDataRequirements(
        min_candles=40,
        requires_ohlc=True,
        supported_timeframes=["5m", "15m", "1h", "1D"],
    ),
    visualization=StrategyVisualization(
        overlays=["ema20"],
        subpanels=["atr14"],
        color="#f43f5e",
    ),
    entry_rules=[
        StrategyRule(
            rule_id="atr_expansion_spike",
            label="ATR(14) > 1.3x ATR Baseline (20)  (volatility expansion spike)",
            dependency_keys=["atr14", "atr_sma20"],
            condition_fn=lambda fv: _cond(fv, "atr14", "atr_sma20", fn=lambda a, b: a > 1.3 * b),
        ),
        StrategyRule(
            rule_id="price_above_short_trend",
            label="Price > EMA20  (price above short-term average)",
            dependency_keys=["close", "ema20"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_positive_momentum",
            label="RSI(14) > 50.0  (positive momentum confirmation)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="volatility_compression",
            label="ATR(14) < ATR Baseline  (volatility normalization — strategy exit condition)",
            dependency_keys=["atr14", "atr_sma20"],
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "atr14", "atr_sma20", fn=lambda a, b: a < b),
        ),
    ],
    tags=["volatility", "atr", "expansion"],
)


# ---------------------------------------------------------------------------
# Extensible Strategy Registry (Single Source of Truth)
# ---------------------------------------------------------------------------

class StrategyRegistryManager:
    """
    Manages registration, discovery, dependency resolution, and visualization
    metadata for all 20 canonical quantitative strategies.
    """

    def __init__(self):
        self._strategies: Dict[str, StrategyDefinition] = {}

    def register(self, strategy: StrategyDefinition) -> None:
        """Register a strategy definition."""
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Optional[StrategyDefinition]:
        """Lookup a strategy by its ID."""
        return self._strategies.get(strategy_id)

    def list_all(self) -> List[StrategyDefinition]:
        """Return all registered strategy definitions."""
        return list(self._strategies.values())

    def list_enabled(self) -> List[StrategyDefinition]:
        """Return all active, non-deprecated strategies."""
        return [s for s in self._strategies.values() if s.enabled and not s.deprecated]

    def list_by_category(self, category: Union[StrategyCategory, str]) -> List[StrategyDefinition]:
        """Filter strategies by category."""
        target_val = category.value if isinstance(category, StrategyCategory) else str(category)
        return [
            s for s in self._strategies.values()
            if (s.category.value if isinstance(s.category, StrategyCategory) else str(s.category)).lower() == target_val.lower()
        ]

    def get_all_required_dependencies(self, strategy_ids: Optional[List[str]] = None) -> Set[str]:
        """
        Aggregate all indicator dependency keys across selected or all enabled strategies.
        Guarantees that shared indicators are calculated ONCE by the quant engine.
        """
        strats = [self.get(sid) for sid in strategy_ids] if strategy_ids else self.list_enabled()
        keys: Set[str] = {"close"}
        for s in strats:
            if s:
                for r in s.entry_rules + s.exit_rules + s.invalidation_rules:
                    keys.update(r.dependency_keys)
        return keys

    def get_visualization(self, strategy_id: str) -> Optional[StrategyVisualization]:
        """Retrieve visualization metadata for chart rendering."""
        strat = self.get(strategy_id)
        return strat.visualization if strat else None


# Canonical global instance
registry_manager = StrategyRegistryManager()

# Register all 20 canonical strategies across 5 categories
ALL_CANONICAL_STRATEGIES: List[StrategyDefinition] = [
    # 1. Trend Following
    EMA_GOLDEN_CROSS,
    SUPERTREND_PROXY,
    ADX_TREND_STRENGTH,
    EMA_PULLBACK,
    MOVING_AVERAGE_MOMENTUM_STACK,
    # 2. Momentum
    VWAP_MOMENTUM,
    MACD_CROSSOVER,
    RSI_MOMENTUM,
    ROC_MOMENTUM,
    # 3. Mean Reversion
    RSI_OVERSOLD_REVERSAL,
    BOLLINGER_MEAN_REVERSION,
    VWAP_MEAN_REVERSION,
    # 4. Breakout
    BOLLINGER_SQUEEZE,
    ORB_BREAKOUT,
    DONCHIAN_BREAKOUT,
    PREVIOUS_DAY_BREAKOUT,
    # 5. Volume & Volatility
    RVOL_SURGE,
    VOLUME_BREAKOUT_CONFIRMATION,
    PRICE_VOLUME_DIVERGENCE,
    ATR_VOLATILITY_EXPANSION,
]

for _strat in ALL_CANONICAL_STRATEGIES:
    registry_manager.register(_strat)

# Backward-compatible dictionary export
STRATEGY_REGISTRY: Dict[str, StrategyDefinition] = registry_manager._strategies
