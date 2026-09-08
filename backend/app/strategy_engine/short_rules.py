"""
Strategy Lab — Canonical Short Rules for All 20 Strategies
===========================================================
Defines deterministic, symmetric short entry and short exit rules for
every registered strategy in APEX Quant Lab, establishing full
dual LONG / SHORT / NEUTRAL directional capability.

Truth-Layer Invariants:
- Zero lookahead bias: condition_fn strictly evaluates current/past candle data.
- Missing data propagates as UNAVAILABLE (never converted to False/Fail).
- No synthetic or fabricated indicator values.
"""

from typing import Dict, List
from backend.app.strategy_engine.dsl import StrategyRule


def _v(fv: dict, key: str):
    """Safe extractor — returns the float value or None if missing/NaN."""
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
# Short Entry Rules
# ---------------------------------------------------------------------------

SHORT_ENTRY_RULES: Dict[str, List[StrategyRule]] = {
    # 1. EMA Golden Cross -> Death Cross Short
    "EMA_GOLDEN_CROSS": [
        StrategyRule(
            rule_id="ema20_below_ema50",
            label="EMA20 < EMA50 (death cross region)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
        StrategyRule(
            rule_id="price_below_ema20",
            label="Price < EMA20 (price below short-term trend)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_not_oversold",
            label="RSI(14) > 30 (not oversold threshold)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=30.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 30.0),
        ),
    ],

    # 2. Supertrend ATR Proxy -> Bearish ATR Dynamic Resistance
    "SUPERTREND_PROXY": [
        StrategyRule(
            rule_id="price_below_ema50_st",
            label="Price < EMA50 (primary trend is down)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_bearish_zone",
            label="RSI(14) < 50 (bearish momentum zone)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 50.0),
        ),
        StrategyRule(
            rule_id="atr_dynamic_resistance",
            label="Price < VWAP + 1.5×ATR (below dynamic resistance band)",
            dependency_keys=["close", "vwap", "atr14"],
            operator="<",
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c < (v + 1.5 * a)
            ),
        ),
    ],

    # 3. ADX Trend Strength -> Bearish Directional Movement
    "ADX_TREND_STRENGTH": [
        StrategyRule(
            rule_id="adx_strong_trend_short",
            label="ADX(14) > 25.0 (established trend strength)",
            dependency_keys=["adx"],
            operator=">",
            threshold=25.0,
            condition_fn=lambda fv: _cond(fv, "adx", fn=lambda a: a > 25.0),
        ),
        StrategyRule(
            rule_id="bearish_directional_movement",
            label="-DI > +DI (negative directional movement)",
            dependency_keys=["minus_di", "plus_di"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "minus_di", "plus_di", fn=lambda m, p: m > p),
        ),
        StrategyRule(
            rule_id="price_below_trend_filter",
            label="Price < EMA50 (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
    ],

    # 4. EMA Pullback -> Bearish Pullback to EMA20 from Below
    "EMA_PULLBACK": [
        StrategyRule(
            rule_id="ema_downtrend_context",
            label="EMA20 < EMA50 (established downtrend context)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
        StrategyRule(
            rule_id="pullback_to_ema20_short",
            label="High >= EMA20*0.995 & Close <= EMA20*1.005 (pullback to EMA20)",
            dependency_keys=["high", "close", "ema20"],
            condition_fn=lambda fv: _cond(
                fv, "high", "close", "ema20",
                fn=lambda h, c, e: (h >= e * 0.995) and (c <= e * 1.005)
            ),
        ),
        StrategyRule(
            rule_id="trend_filter_downtrend",
            label="Price < EMA50 (macro downtrend intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_pullback_range_short",
            label="35.0 <= RSI(14) <= 55.0 (bear pullback oscillator range)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 35.0 <= r <= 55.0),
        ),
    ],

    # 5. Moving Average Momentum Stack -> Bearish Triple EMA Alignment
    "MOVING_AVERAGE_MOMENTUM_STACK": [
        StrategyRule(
            rule_id="ema_fast_below_medium",
            label="EMA20 < EMA50 (fast trend below medium)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
        StrategyRule(
            rule_id="ema_medium_below_slow",
            label="EMA50 < EMA200 (medium trend below long-term baseline)",
            dependency_keys=["ema50", "ema200"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "ema50", "ema200", fn=lambda b, c: b < c),
        ),
        StrategyRule(
            rule_id="price_below_fast_ema",
            label="Price < EMA20 (price below fast moving average)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_bear_stack_alignment",
            label="25.0 <= RSI(14) <= 50.0 (bearish trend momentum band)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 25.0 <= r <= 50.0),
        ),
    ],

    # 6. VWAP Momentum -> Bearish VWAP Breakdown
    "VWAP_MOMENTUM": [
        StrategyRule(
            rule_id="price_below_vwap",
            label="Price < VWAP (below session volume-weighted baseline)",
            dependency_keys=["close", "vwap"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
        StrategyRule(
            rule_id="ema_downtrend_aligned",
            label="EMA20 < EMA50 (downtrend aligned)",
            dependency_keys=["ema20", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a < b),
        ),
        StrategyRule(
            rule_id="rsi_bearish_momentum",
            label="RSI(14) < 45 (bearish momentum zone)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=45.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 45.0),
        ),
        StrategyRule(
            rule_id="volume_surge_short",
            label="Relative Volume >= 1.2 (volume confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.2,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.2),
        ),
    ],

    # 7. MACD Crossover -> Bearish MACD Signal Cross
    "MACD_CROSSOVER": [
        StrategyRule(
            rule_id="macd_below_signal",
            label="MACD Line < Signal Line (bearish crossover)",
            dependency_keys=["macd", "macd_signal"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m < s),
        ),
        StrategyRule(
            rule_id="macd_histogram_negative",
            label="MACD Histogram < 0 (negative momentum)",
            dependency_keys=["macd_histogram"],
            operator="<",
            threshold=0.0,
            condition_fn=lambda fv: _cond(fv, "macd_histogram", fn=lambda h: h < 0),
        ),
        StrategyRule(
            rule_id="price_below_ema50",
            label="Price < EMA50 (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
    ],

    # 8. RSI Momentum -> Bearish Momentum Continuation
    "RSI_MOMENTUM": [
        StrategyRule(
            rule_id="rsi_bearish_momentum_zone",
            label="25.0 <= RSI(14) <= 45.0 (bearish acceleration band)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 25.0 <= r <= 45.0),
        ),
        StrategyRule(
            rule_id="price_below_ema50",
            label="Price < EMA50 (trend filter intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="macd_histogram_negative",
            label="MACD Histogram < 0 (negative momentum confirmation)",
            dependency_keys=["macd_histogram"],
            operator="<",
            threshold=0.0,
            condition_fn=lambda fv: _cond(fv, "macd_histogram", fn=lambda h: h < 0),
        ),
    ],

    # 9. ROC Momentum -> Negative Velocity Acceleration
    "ROC_MOMENTUM": [
        StrategyRule(
            rule_id="roc_deceleration",
            label="ROC(12) < -1.5% (downside velocity expansion)",
            dependency_keys=["roc12"],
            operator="<",
            threshold=-1.5,
            condition_fn=lambda fv: _cond(fv, "roc12", fn=lambda r: r < -1.5),
        ),
        StrategyRule(
            rule_id="price_below_ema20",
            label="Price < EMA20 (price below short-term trend)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="volume_confirmation_short",
            label="Relative Volume >= 1.2 (liquidity confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.2,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.2),
        ),
    ],

    # 10. RSI Oversold Reversal -> Overbought Reversal (Mean Reversion Short)
    "RSI_OVERSOLD_REVERSAL": [
        StrategyRule(
            rule_id="rsi_overbought",
            label="RSI(14) > 65 (overbought reversal zone)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=65.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 65.0),
        ),
        StrategyRule(
            rule_id="price_above_vwap",
            label="Price > VWAP (extended above session VWAP)",
            dependency_keys=["close", "vwap"],
            operator=">",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
        StrategyRule(
            rule_id="volume_flush_short",
            label="Relative Volume >= 1.5 (elevated volume on exhaustion)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],

    # 11. Bollinger Mean Reversion -> Upper Band Mean Reversion Short
    "BOLLINGER_MEAN_REVERSION": [
        StrategyRule(
            rule_id="price_at_upper_band",
            label="Price >= Bollinger Upper Band * 0.995 (upper band excursion)",
            dependency_keys=["close", "bb_upper"],
            condition_fn=lambda fv: _cond(fv, "close", "bb_upper", fn=lambda c, u: c >= u * 0.995),
        ),
        StrategyRule(
            rule_id="rsi_overbought_filter",
            label="RSI(14) > 60.0 (overbought oscillator confirmation)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=60.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 60.0),
        ),
    ],

    # 12. VWAP Mean Reversion -> Upside Extension Mean Reversion Short
    "VWAP_MEAN_REVERSION": [
        StrategyRule(
            rule_id="vwap_upside_stretch",
            label="Distance from VWAP >= +1.5% (upside extension)",
            dependency_keys=["vwap_distance_pct"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "vwap_distance_pct", fn=lambda d: d >= 1.5),
        ),
        StrategyRule(
            rule_id="rsi_overbought_confirmation",
            label="RSI(14) > 60.0 (overbought confirmation)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=60.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 60.0),
        ),
    ],

    # 13. Bollinger Band Squeeze -> Lower Band Breakdown Short
    "BOLLINGER_SQUEEZE": [
        StrategyRule(
            rule_id="price_below_bb_lower",
            label="Price < Bollinger Lower Band (downward band expansion)",
            dependency_keys=["close", "bb_lower"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "bb_lower", fn=lambda c, b: c < b),
        ),
        StrategyRule(
            rule_id="rsi_contracting_down",
            label="RSI(14) < 50.0 (bearish momentum confirmation)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 50.0),
        ),
        StrategyRule(
            rule_id="volume_confirmation_short",
            label="Relative Volume >= 1.3 (volume expansion confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.3,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.3),
        ),
    ],

    # 14. Opening Range Breakout (ORB) -> ORB Breakdown Short
    "ORB_BREAKOUT": [
        StrategyRule(
            rule_id="price_below_vwap_orb",
            label="Price < VWAP (breakdown below session reference level)",
            dependency_keys=["close", "vwap"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
        StrategyRule(
            rule_id="rsi_breakdown_weakness",
            label="RSI(14) < 45.0 (downside momentum confirms breakdown)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=45.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 45.0),
        ),
        StrategyRule(
            rule_id="orb_volume_short",
            label="Relative Volume >= 1.5 (elevated session volume)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],

    # 15. Donchian Channel Breakout -> Donchian Lower Breakdown Short
    "DONCHIAN_BREAKOUT": [
        StrategyRule(
            rule_id="donchian_channel_breakdown",
            label="Price < Donchian Lower (20) (breakdown below 20-period low)",
            dependency_keys=["close", "donchian_low"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "donchian_low", fn=lambda c, d: c < d),
        ),
        StrategyRule(
            rule_id="volume_expansion_short",
            label="Relative Volume >= 1.3 (volume expansion confirmation)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.3,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.3),
        ),
        StrategyRule(
            rule_id="trend_filter_downtrend",
            label="Price < EMA50 (downtrend alignment intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
    ],

    # 16. Previous Day High Breakout -> Previous Day Low Breakdown Short
    "PREVIOUS_DAY_BREAKOUT": [
        StrategyRule(
            rule_id="breakdown_below_pdl",
            label="Price < Previous Day Low (breakdown below prior session support)",
            dependency_keys=["close", "prev_day_low"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "prev_day_low", fn=lambda c, p: c < p),
        ),
        StrategyRule(
            rule_id="price_below_vwap",
            label="Price < VWAP (session trend alignment)",
            dependency_keys=["close", "vwap"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
        StrategyRule(
            rule_id="volume_surge_short",
            label="Relative Volume >= 1.5 (elevated volume expansion)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=1.5,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 1.5),
        ),
    ],

    # 17. Relative Volume Surge -> Distribution Volume Surge Short
    "RVOL_SURGE": [
        StrategyRule(
            rule_id="rvol_spike_short",
            label="Relative Volume >= 2.0× (abnormal volume spike)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=2.0,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 2.0),
        ),
        StrategyRule(
            rule_id="price_below_ema20_rvol",
            label="Price < EMA20 (price below short-term trend)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_distribution_zone",
            label="30.0 < RSI(14) < 55.0 (distribution momentum zone)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 30.0 < r < 55.0),
        ),
    ],

    # 18. Volume Breakout Confirmation -> Volume Breakdown Short
    "VOLUME_BREAKOUT_CONFIRMATION": [
        StrategyRule(
            rule_id="price_new_20_low",
            label="Price < Prior 20-Bar Lowest Close (price breakdown)",
            dependency_keys=["close", "lowest_low_20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "lowest_low_20", fn=lambda c, l: c < l),
        ),
        StrategyRule(
            rule_id="extreme_volume_surge_short",
            label="Relative Volume >= 2.0x (institutional volume surge)",
            dependency_keys=["rvol"],
            operator=">=",
            threshold=2.0,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r >= 2.0),
        ),
        StrategyRule(
            rule_id="trend_alignment_short",
            label="Price < EMA50 (macro trend alignment intact)",
            dependency_keys=["close", "ema50"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c < e),
        ),
    ],

    # 19. Price-Volume Divergence -> Capital Outflow (CMF Distribution) Short
    "PRICE_VOLUME_DIVERGENCE": [
        StrategyRule(
            rule_id="negative_money_flow_entry",
            label="CMF(20) < -0.10 (sustained capital outflow)",
            dependency_keys=["cmf20"],
            operator="<",
            threshold=-0.10,
            condition_fn=lambda fv: _cond(fv, "cmf20", fn=lambda m: m < -0.10),
        ),
        StrategyRule(
            rule_id="price_below_ema20",
            label="Price < EMA20 (price trend alignment)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_confirmation_short",
            label="30.0 <= RSI(14) <= 50.0 (bearish distribution momentum)",
            dependency_keys=["rsi14"],
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: 30.0 <= r <= 50.0),
        ),
    ],

    # 20. ATR Volatility Expansion -> Downward Volatility Expansion Short
    "ATR_VOLATILITY_EXPANSION": [
        StrategyRule(
            rule_id="atr_expansion_spike_short",
            label="ATR(14) > 1.3x ATR Baseline (20) (volatility expansion spike)",
            dependency_keys=["atr14", "atr_sma20"],
            condition_fn=lambda fv: _cond(fv, "atr14", "atr_sma20", fn=lambda a, b: a > 1.3 * b),
        ),
        StrategyRule(
            rule_id="price_below_short_trend",
            label="Price < EMA20 (price below short-term average)",
            dependency_keys=["close", "ema20"],
            operator="<",
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c < e),
        ),
        StrategyRule(
            rule_id="rsi_negative_momentum",
            label="RSI(14) < 50.0 (negative momentum confirmation)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=50.0,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 50.0),
        ),
    ],
}


# ---------------------------------------------------------------------------
# Short Exit Rules
# ---------------------------------------------------------------------------

SHORT_EXIT_RULES: Dict[str, List[StrategyRule]] = {
    "EMA_GOLDEN_CROSS": [
        StrategyRule(
            rule_id="ema_golden_cross_exit",
            label="EMA20 > EMA50 (moving average reversal — short exit condition)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
    ],

    "SUPERTREND_PROXY": [
        StrategyRule(
            rule_id="price_above_atr_band",
            label="Price > VWAP + 1.5×ATR (resistance level breached — short exit condition)",
            dependency_keys=["close", "vwap", "atr14"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(
                fv, "close", "vwap", "atr14",
                fn=lambda c, v, a: c > (v + 1.5 * a)
            ),
        ),
    ],

    "ADX_TREND_STRENGTH": [
        StrategyRule(
            rule_id="trend_weakening_short",
            label="ADX(14) < 20.0 (trend exhaustion — short exit condition)",
            dependency_keys=["adx"],
            operator="<",
            threshold=20.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "adx", fn=lambda a: a < 20.0),
        ),
        StrategyRule(
            rule_id="di_bullish_cross_exit",
            label="+DI > -DI (directional reversal — short exit condition)",
            dependency_keys=["plus_di", "minus_di"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "plus_di", "minus_di", fn=lambda p, m: p > m),
        ),
    ],

    "EMA_PULLBACK": [
        StrategyRule(
            rule_id="trend_breakout_short",
            label="Price > EMA50 (trend breakdown — short exit condition)",
            dependency_keys=["close", "ema50"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "ema50", fn=lambda c, e: c > e),
        ),
    ],

    "MOVING_AVERAGE_MOMENTUM_STACK": [
        StrategyRule(
            rule_id="ema_stack_invalidation_short",
            label="EMA20 > EMA50 (crossover breakdown — short exit condition)",
            dependency_keys=["ema20", "ema50"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "ema20", "ema50", fn=lambda a, b: a > b),
        ),
    ],

    "VWAP_MOMENTUM": [
        StrategyRule(
            rule_id="price_above_ema20",
            label="Price > EMA20 (trend breakdown — short exit condition)",
            dependency_keys=["close", "ema20"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "ema20", fn=lambda c, e: c > e),
        ),
        StrategyRule(
            rule_id="rsi_recovery",
            label="RSI(14) > 55 (momentum recovery — short exit condition)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=55.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 55.0),
        ),
    ],

    "MACD_CROSSOVER": [
        StrategyRule(
            rule_id="macd_bullish_cross_exit",
            label="MACD Line > Signal Line (bullish crossover — short exit condition)",
            dependency_keys=["macd", "macd_signal"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "macd", "macd_signal", fn=lambda m, s: m > s),
        ),
    ],

    "RSI_MOMENTUM": [
        StrategyRule(
            rule_id="rsi_loss_of_bearish_momentum",
            label="RSI(14) > 50.0 (momentum breakdown — short exit condition)",
            dependency_keys=["rsi14"],
            operator=">",
            threshold=50.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r > 50.0),
        ),
        StrategyRule(
            rule_id="rsi_oversold_exhaustion",
            label="RSI(14) < 20.0 (extreme oversold exhaustion — short exit condition)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=20.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 20.0),
        ),
    ],

    "ROC_MOMENTUM": [
        StrategyRule(
            rule_id="roc_bearish_momentum_loss",
            label="ROC(12) > 0.0% (momentum reversal — short exit condition)",
            dependency_keys=["roc12"],
            operator=">",
            threshold=0.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "roc12", fn=lambda r: r > 0.0),
        ),
    ],

    "RSI_OVERSOLD_REVERSAL": [
        StrategyRule(
            rule_id="rsi_normalized_short",
            label="RSI(14) < 45 (momentum normalized — short exit condition)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=45.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 45.0),
        ),
        StrategyRule(
            rule_id="price_below_vwap_exit",
            label="Price < VWAP (mean reversion target reached — short exit condition)",
            dependency_keys=["close", "vwap"],
            operator="<",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c < v),
        ),
    ],

    "BOLLINGER_MEAN_REVERSION": [
        StrategyRule(
            rule_id="target_middle_band_reached_short",
            label="Price <= Bollinger Middle Band (mean reversion target — short exit condition)",
            dependency_keys=["close", "bb_middle"],
            operator="<=",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "bb_middle", fn=lambda c, m: c <= m),
        ),
    ],

    "VWAP_MEAN_REVERSION": [
        StrategyRule(
            rule_id="vwap_reversion_target_short",
            label="Price <= VWAP (mean reversion target — short exit condition)",
            dependency_keys=["close", "vwap"],
            operator="<=",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c <= v),
        ),
    ],

    "BOLLINGER_SQUEEZE": [
        StrategyRule(
            rule_id="price_above_bb_middle_exit",
            label="Price > Bollinger Middle Band (re-entry above midline — short exit condition)",
            dependency_keys=["close", "bb_middle"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "bb_middle", fn=lambda c, b: c > b),
        ),
    ],

    "ORB_BREAKOUT": [
        StrategyRule(
            rule_id="price_back_above_vwap",
            label="Price > VWAP (breakout invalidation — short exit condition)",
            dependency_keys=["close", "vwap"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "vwap", fn=lambda c, v: c > v),
        ),
    ],

    "DONCHIAN_BREAKOUT": [
        StrategyRule(
            rule_id="channel_midpoint_exit_short",
            label="Price > Donchian Midpoint (exit above channel mean — short exit condition)",
            dependency_keys=["close", "donchian_mid"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "donchian_mid", fn=lambda c, m: c > m),
        ),
    ],

    "PREVIOUS_DAY_BREAKOUT": [
        StrategyRule(
            rule_id="reentry_above_pdl",
            label="Price > Previous Day Low (re-entry above breakdown level — short exit condition)",
            dependency_keys=["close", "prev_day_low"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "prev_day_low", fn=lambda c, p: c > p),
        ),
    ],

    "RVOL_SURGE": [
        StrategyRule(
            rule_id="rvol_normalized_short",
            label="Relative Volume < 1.0 (volume normalization — short exit condition)",
            dependency_keys=["rvol"],
            operator="<",
            threshold=1.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rvol", fn=lambda r: r < 1.0),
        ),
        StrategyRule(
            rule_id="rsi_oversold_exit",
            label="RSI(14) < 30 (oversold threshold — short exit condition)",
            dependency_keys=["rsi14"],
            operator="<",
            threshold=30.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "rsi14", fn=lambda r: r < 30.0),
        ),
    ],

    "VOLUME_BREAKOUT_CONFIRMATION": [
        StrategyRule(
            rule_id="reentry_above_breakdown",
            label="Price > Breakdown Level (breakdown failure — short exit condition)",
            dependency_keys=["close", "lowest_low_20"],
            operator=">",
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "close", "lowest_low_20", fn=lambda c, l: c > l),
        ),
    ],

    "PRICE_VOLUME_DIVERGENCE": [
        StrategyRule(
            rule_id="positive_money_flow_exit",
            label="CMF(20) > 0.0 (capital inflow reversal — short exit condition)",
            dependency_keys=["cmf20"],
            operator=">",
            threshold=0.0,
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "cmf20", fn=lambda m: m > 0.0),
        ),
    ],

    "ATR_VOLATILITY_EXPANSION": [
        StrategyRule(
            rule_id="volatility_compression_short",
            label="ATR(14) < ATR Baseline (volatility normalization — short exit condition)",
            dependency_keys=["atr14", "atr_sma20"],
            is_entry_rule=False,
            condition_fn=lambda fv: _cond(fv, "atr14", "atr_sma20", fn=lambda a, b: a < b),
        ),
    ],
}
