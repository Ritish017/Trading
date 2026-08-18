"""
Strategy Lab — Strategy Library (Registry)
==========================================
Defines the canonical library of systematic quantitative strategies.

Rules
-----
- Each rule's condition_fn receives a Dict[str, Any] feature vector and returns:
    True  → PASS
    False → FAIL
    None  → UNAVAILABLE (dependency value is None/NaN)
- No fabricated values. Every condition tests a real computed indicator.
- Adding new strategies: append to STRATEGY_REGISTRY only. Evaluator is decoupled.
"""

from typing import Dict
from backend.app.strategy_engine.dsl import StrategyDefinition, StrategyRule


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


# ---------------------------------------------------------------------------
# Strategy 1 — VWAP Momentum Breakout
# ---------------------------------------------------------------------------
VWAP_MOMENTUM = StrategyDefinition(
    strategy_id="VWAP_MOMENTUM",
    name="VWAP Momentum Breakout",
    category="Momentum",
    description=(
        "Long bias when price is above VWAP, EMA20 > EMA50 (trend aligned), "
        "RSI(14) > 55 (momentum), and Relative Volume ≥ 1.2 (institutional participation)."
    ),
    timeframe_hint="5m",
    min_candles=50,
    entry_rules=[
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP",
            dependency_keys=["close", "vwap"],
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="ema_trend_aligned",
            label="EMA20 > EMA50  (uptrend aligned)",
            dependency_keys=["ema20", "ema50"],
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="rsi_momentum",
            label="RSI(14) > 55  (momentum zone)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="volume_surge",
            label="Relative Volume ≥ 1.2  (above-average activity)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.2),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_ema20",
            label="Price < EMA20  (trend breaking down)",
            dependency_keys=["close", "ema20"],
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_weakness",
            label="RSI(14) < 45  (momentum fading)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 45.0),
        ),
    ],
    tags=["momentum", "vwap", "ema", "intraday"],
)


# ---------------------------------------------------------------------------
# Strategy 2 — EMA Golden Cross
# ---------------------------------------------------------------------------
EMA_GOLDEN_CROSS = StrategyDefinition(
    strategy_id="EMA_GOLDEN_CROSS",
    name="EMA Golden Cross",
    category="Trend Following",
    description=(
        "Classic trend-following setup: EMA20 crosses above EMA50 indicating "
        "a shift to bullish momentum. RSI must confirm, not overbought (< 70)."
    ),
    timeframe_hint="15m",
    min_candles=55,
    entry_rules=[
        StrategyRule(
            rule_id="ema20_above_ema50",
            label="EMA20 > EMA50  (golden cross region)",
            dependency_keys=["ema20", "ema50"],
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
        StrategyRule(
            rule_id="price_above_ema20",
            label="Price > EMA20  (price above short-term trend)",
            dependency_keys=["close", "ema20"],
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_not_overbought",
            label="RSI(14) < 70  (not overbought)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 70.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="ema_death_cross",
            label="EMA20 < EMA50  (death cross — exit signal)",
            dependency_keys=["ema20", "ema50"],
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
    ],
    tags=["trend", "ema", "crossover", "swing"],
)


# ---------------------------------------------------------------------------
# Strategy 3 — RSI Oversold Reversal
# ---------------------------------------------------------------------------
RSI_OVERSOLD_REVERSAL = StrategyDefinition(
    strategy_id="RSI_OVERSOLD_REVERSAL",
    name="RSI Oversold Reversal",
    category="Mean-Reversion",
    description=(
        "Counter-trend: price is below VWAP (oversold territory), RSI(14) < 35 "
        "suggesting exhaustion, with a Relative Volume spike confirming the flush."
    ),
    timeframe_hint="5m",
    min_candles=30,
    entry_rules=[
        StrategyRule(
            rule_id="rsi_oversold",
            label="RSI(14) < 35  (oversold — potential reversal zone)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 35.0),
        ),
        StrategyRule(
            rule_id="price_below_vwap",
            label="Price < VWAP  (extended below fair value)",
            dependency_keys=["close", "vwap"],
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
        StrategyRule(
            rule_id="volume_flush",
            label="Relative Volume ≥ 1.5  (capitulation volume)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="rsi_recovered",
            label="RSI(14) > 55  (momentum recovered — take profit)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP  (mean reversion complete)",
            dependency_keys=["close", "vwap"],
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
    ],
    tags=["mean-reversion", "rsi", "reversal", "intraday"],
)


# ---------------------------------------------------------------------------
# Strategy 4 — Bollinger Band Squeeze
# ---------------------------------------------------------------------------
BOLLINGER_SQUEEZE = StrategyDefinition(
    strategy_id="BOLLINGER_SQUEEZE",
    name="Bollinger Band Squeeze",
    category="Breakout",
    description=(
        "Identifies compression (price near Bollinger midline, bands contracting). "
        "Entry when price breaks above upper band with momentum (RSI > 50). "
        "ATR bandwidth proxy: price > bb_upper indicates expansion."
    ),
    timeframe_hint="15m",
    min_candles=30,
    entry_rules=[
        StrategyRule(
            rule_id="price_above_bb_upper",
            label="Price > Bollinger Upper Band  (breakout from compression)",
            dependency_keys=["close", "bb_upper"],
            condition_fn=lambda fv: _cond(fv, "close", "bb_upper", fn=lambda c, b: c > b),
        ),
        StrategyRule(
            rule_id="rsi_expanding",
            label="RSI(14) > 50  (momentum confirms breakout direction)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
        StrategyRule(
            rule_id="volume_confirmation",
            label="Relative Volume ≥ 1.3  (volume confirms expansion)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.3),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_bb_middle",
            label="Price < Bollinger Middle Band  (compression re-entry)",
            dependency_keys=["close", "bb_middle"],
            condition_fn=lambda fv: _cond(fv, "close", "bb_middle", fn=lambda c, b: c < b),
        ),
    ],
    tags=["breakout", "bollinger", "volatility", "squeeze"],
)


# ---------------------------------------------------------------------------
# Strategy 5 — MACD Bullish Crossover
# ---------------------------------------------------------------------------
MACD_CROSSOVER = StrategyDefinition(
    strategy_id="MACD_CROSSOVER",
    name="MACD Bullish Crossover",
    category="Momentum",
    description=(
        "MACD line crosses above signal line (bullish crossover), histogram positive "
        "and expanding. Price must remain above EMA50 (trend filter)."
    ),
    timeframe_hint="15m",
    min_candles=40,
    entry_rules=[
        StrategyRule(
            rule_id="macd_above_signal",
            label="MACD Line > Signal Line  (bullish crossover region)",
            dependency_keys=["macd", "macd_signal"],
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m > s),
        ),
        StrategyRule(
            rule_id="macd_histogram_positive",
            label="MACD Histogram > 0  (positive momentum)",
            dependency_keys=["macd_histogram"],
            condition_fn=lambda fv: _cond(fv, "macd_histogram", fn=lambda h: h > 0),
        ),
        StrategyRule(
            rule_id="price_above_ema50",
            label="Price > EMA50  (longer-term trend intact)",
            dependency_keys=["close", "ema50"],
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="macd_bearish_cross",
            label="MACD Line < Signal Line  (bearish crossover — exit)",
            dependency_keys=["macd", "macd_signal"],
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m < s),
        ),
    ],
    tags=["momentum", "macd", "crossover", "trend"],
)


# ---------------------------------------------------------------------------
# Strategy 6 — Opening Range Breakout (ORB)
# ---------------------------------------------------------------------------
ORB_BREAKOUT = StrategyDefinition(
    strategy_id="ORB_BREAKOUT",
    name="Opening Range Breakout (ORB)",
    category="Breakout",
    description=(
        "Price breaks above the VWAP (a proxy for the session value area) in the "
        "first segment of the trading day, with RSI > 55 and Relative Volume ≥ 1.5."
    ),
    timeframe_hint="5m",
    min_candles=20,
    entry_rules=[
        StrategyRule(
            rule_id="price_above_vwap_orb",
            label="Price > VWAP  (breakout above session fair value)",
            dependency_keys=["close", "vwap"],
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="rsi_breakout_strength",
            label="RSI(14) > 55  (momentum confirms breakout)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
        StrategyRule(
            rule_id="orb_volume",
            label="Relative Volume ≥ 1.5  (institutional-grade opening volume)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_back_below_vwap",
            label="Price < VWAP  (breakout failed — exit)",
            dependency_keys=["close", "vwap"],
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
    ],
    tags=["breakout", "orb", "intraday", "momentum"],
)


# ---------------------------------------------------------------------------
# Strategy 7 — Supertrend Proxy (ATR-based)
# ---------------------------------------------------------------------------
SUPERTREND_PROXY = StrategyDefinition(
    strategy_id="SUPERTREND_PROXY",
    name="Supertrend ATR Proxy",
    category="Trend Following",
    description=(
        "Uses ATR as a volatility proxy for a Supertrend-equivalent filter. "
        "Price must be > EMA50 (trend) and > (VWAP - 1.5 × ATR/price) interpreted as "
        "remaining above a dynamic support band. RSI > 50 confirms."
    ),
    timeframe_hint="15m",
    min_candles=50,
    entry_rules=[
        StrategyRule(
            rule_id="price_above_ema50_st",
            label="Price > EMA50  (primary trend is up)",
            dependency_keys=["close", "ema50"],
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_trend_zone",
            label="RSI(14) > 50  (not in bearish territory)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
        StrategyRule(
            rule_id="atr_dynamic_support",
            label="Price > VWAP − 1.5×ATR  (within dynamic support band)",
            dependency_keys=["close", "vwap", "atr14"],
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c > (v - 1.5 * a)
            ),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="price_below_atr_band",
            label="Price < VWAP − 1.5×ATR  (broke below dynamic support)",
            dependency_keys=["close", "vwap", "atr14"],
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c < (v - 1.5 * a)
            ),
        ),
    ],
    tags=["trend", "atr", "supertrend", "dynamic-support"],
)


# ---------------------------------------------------------------------------
# Strategy 8 — Relative Volume Surge
# ---------------------------------------------------------------------------
RVOL_SURGE = StrategyDefinition(
    strategy_id="RVOL_SURGE",
    name="Relative Volume Surge",
    category="Volume",
    description=(
        "Flags when Relative Volume spikes ≥ 2.0× the 20-period average, "
        "price is trending (above EMA20), and RSI is in the 45–70 zone "
        "— a typical institutional accumulation / distribution signal."
    ),
    timeframe_hint="5m",
    min_candles=25,
    entry_rules=[
        StrategyRule(
            rule_id="rvol_spike",
            label="Relative Volume ≥ 2.0×  (significant institutional participation)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 2.0),
        ),
        StrategyRule(
            rule_id="price_above_ema20_rvol",
            label="Price > EMA20  (price in uptrend)",
            dependency_keys=["close", "ema20"],
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_accumulation_zone",
            label="45 < RSI(14) < 70  (accumulation zone, not overbought)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 45.0 < r < 70.0),
        ),
    ],
    exit_rules=[
        StrategyRule(
            rule_id="rvol_normalized",
            label="Relative Volume < 1.0  (volume dried up — exit)",
            dependency_keys=["rvol"],
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r < 1.0),
        ),
        StrategyRule(
            rule_id="rsi_overbought_exit",
            label="RSI(14) > 70  (overbought — take profit)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 70.0),
        ),
    ],
    tags=["volume", "rvol", "accumulation", "institutional"],
)


# ---------------------------------------------------------------------------
# Strategy Registry — single source of truth
# ---------------------------------------------------------------------------
STRATEGY_REGISTRY: Dict[str, StrategyDefinition] = {
    s.strategy_id: s
    for s in [
        VWAP_MOMENTUM,
        EMA_GOLDEN_CROSS,
        RSI_OVERSOLD_REVERSAL,
        BOLLINGER_SQUEEZE,
        MACD_CROSSOVER,
        ORB_BREAKOUT,
        SUPERTREND_PROXY,
        RVOL_SURGE,
    ]
}
