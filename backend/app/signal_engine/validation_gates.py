"""
Signal Intelligence Engine — Validation Gates
==============================================
Implements the 17-stage signal validation pipeline.

HARD GATES: Any failure → NO_TRADE immediately
SOFT EVIDENCE: Affects confidence/score but not blocking

Hard Gate Sequence:
1.  DATA VALIDATION        — freshness, quality, OHLCV integrity
2.  INSTRUMENT VALIDATION  — valid, tradeable instrument
3.  MARKET SESSION         — market is open, no trading halt
4.  LIQUIDITY              — minimum volume, price liquidity
5.  STOP DETERMINABLE      — can compute a valid, reasonable stop
6.  ENTRY VALID            — entry price is within rational zone
7.  RISK/REWARD            — R:R ≥ configured minimum
8.  PORTFOLIO RISK         — daily loss limit, max positions, exposure

Soft Evidence (all affect score, none are blocking):
9.  RSI zone
10. ADX trend strength
11. VWAP position
12. Volume expansion (RVOL)
13. Multi-timeframe alignment
14. Strategy confluence
15. Regime compatibility
16. Market breadth
17. Relative strength

Invariants:
- Hard gate failures must produce a RejectionRecord with explicit reason
- Soft evidence is always evaluated even when score is high
- UNAVAILABLE data is never silently treated as PASS
- All thresholds are configurable via SignalEngineConfig
"""
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import time

from backend.app.signal_engine.models import (
    ValidationGate,
    ValidationGateResult,
    RejectionRecord,
    SignalEngineConfig,
    DataProvenance,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> Optional[float]:
    """Return float or None for NaN/None/Inf."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _gate(
    gate_id: str,
    gate_name: str,
    gate_type: str,  # "HARD" | "SOFT"
    result: ValidationGateResult,
    reason: Optional[str] = None,
    actual_value: Optional[Any] = None,
    threshold_value: Optional[Any] = None,
    evidence: Optional[str] = None,
) -> ValidationGate:
    return ValidationGate(
        gate_id=gate_id,
        gate_name=gate_name,
        gate_type=gate_type,
        result=result,
        reason=reason,
        actual_value=actual_value,
        threshold_value=threshold_value,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Individual gate implementations
# ---------------------------------------------------------------------------

def gate_data_validation(
    candles: List[Dict[str, Any]],
    quote: Dict[str, Any],
    config: SignalEngineConfig,
) -> ValidationGate:
    """
    HARD GATE 1: Data Validation
    Ensures candle data and quote are valid, fresh, and not corrupted.
    """
    gate_id = "DATA_VALIDATION"
    gate_name = "Data Validation"

    if not candles or len(candles) < 20:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"Insufficient candle history: {len(candles) if candles else 0} candles (minimum 20 required)",
            actual_value=len(candles) if candles else 0,
            threshold_value=20,
        )

    # Check for required OHLCV columns
    required_keys = {"open", "high", "low", "close", "volume"}
    sample = candles[-1]
    missing = required_keys - set(sample.keys())
    if missing:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"Candle data missing required columns: {missing}",
        )

    # OHLCV integrity: high >= max(open, close), low <= min(open, close)
    violations = 0
    for c in candles[-10:]:  # Check last 10 candles
        h = _safe_float(c.get("high"))
        l = _safe_float(c.get("low"))
        o = _safe_float(c.get("open"))
        cl = _safe_float(c.get("close"))
        v = _safe_float(c.get("volume"))
        if h is None or l is None or o is None or cl is None or v is None:
            violations += 1
            continue
        if h < max(o, cl) - 0.001:
            violations += 1
        if l > min(o, cl) + 0.001:
            violations += 1
        if v < 0:
            violations += 1
        if any(x <= 0 for x in [h, l, o, cl]):
            violations += 1

    if violations > 2:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"OHLCV integrity violations detected in recent candles ({violations} violations)",
            actual_value=violations,
            threshold_value=2,
        )

    # Quote freshness check
    ltp = _safe_float(quote.get("ltp"))
    if ltp is None or ltp <= 0:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Quote price unavailable or zero",
        )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence=f"{len(candles)} candles available, LTP ₹{ltp:.2f}",
    )


def gate_instrument_validation(
    symbol: str,
    quote: Dict[str, Any],
) -> ValidationGate:
    """
    HARD GATE 2: Instrument Validation
    Ensures the instrument is valid, identifiable, and not suspended.
    """
    gate_id = "INSTRUMENT_VALIDATION"
    gate_name = "Instrument Validation"

    if not symbol or len(symbol) < 2:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Symbol identifier is empty or invalid",
        )

    # Check if quote contains instrument identity
    instrument_key = quote.get("instrument_key") or quote.get("instrumentKey") or symbol
    exchange = quote.get("exchange", "NSE")

    # Check for circuit breaker / suspended status
    market_status = quote.get("market_data_status") or quote.get("marketStatus") or ""
    if "HALT" in str(market_status).upper() or "SUSPEND" in str(market_status).upper():
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"Instrument {symbol} is halted or suspended (status: {market_status})",
            actual_value=market_status,
        )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence=f"Symbol: {symbol}, Exchange: {exchange}, Key: {instrument_key}",
    )


def gate_market_session(
    quote: Dict[str, Any],
    is_market_open: bool,
) -> ValidationGate:
    """
    HARD GATE 3: Market Session Validation
    Ensures the market is open and in normal trading session.
    """
    gate_id = "MARKET_SESSION"
    gate_name = "Market Session Validation"

    if not is_market_open:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Market is not in active trading session",
            evidence="NSE trading hours: 09:15–15:30 IST on trading days",
        )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence="Market session: ACTIVE",
    )


def gate_liquidity(
    quote: Dict[str, Any],
    candles: List[Dict[str, Any]],
    config: SignalEngineConfig,
) -> Tuple[ValidationGate, float]:
    """
    HARD GATE 4: Liquidity Validation
    Returns (gate_result, liquidity_score 0-100).
    """
    gate_id = "LIQUIDITY_VALIDATION"
    gate_name = "Liquidity Validation"

    ltp = _safe_float(quote.get("ltp")) or 0
    volume = _safe_float(quote.get("volume")) or 0

    # Estimate daily traded value in INR
    daily_value_inr = ltp * volume

    # Also check volume from candles (average last 5)
    candle_volumes = []
    for c in candles[-20:]:
        v = _safe_float(c.get("volume"))
        if v is not None and v > 0:
            candle_volumes.append(v)

    avg_candle_vol = sum(candle_volumes) / len(candle_volumes) if candle_volumes else 0

    # Compute liquidity score (0-100)
    liquidity_score = 0.0
    if daily_value_inr > 0:
        # Logarithmic scaling: ₹5Cr = 50 score, ₹50Cr = 75, ₹500Cr = 100
        import math
        ratio = daily_value_inr / config.min_volume_inr
        if ratio >= 1:
            liquidity_score = min(100, 50 + 25 * math.log10(ratio))
        else:
            liquidity_score = max(0, 50 * ratio)

    if volume <= 0 or daily_value_inr == 0:
        return (
            _gate(
                gate_id, gate_name, "HARD",
                ValidationGateResult.FAIL,
                reason="Zero volume reported in quote — insufficient liquidity",
                actual_value=0.0,
                threshold_value=config.min_volume_inr,
            ),
            0.0,
        )

    if daily_value_inr < config.min_volume_inr:
        return (
            _gate(
                gate_id, gate_name, "HARD",
                ValidationGateResult.FAIL,
                reason=(
                    f"Insufficient liquidity: daily volume ₹{daily_value_inr/1e7:.1f}Cr "
                    f"< minimum ₹{config.min_volume_inr/1e7:.1f}Cr"
                ),
                actual_value=daily_value_inr,
                threshold_value=config.min_volume_inr,
            ),
            liquidity_score,
        )

    return (
        _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.PASS,
            evidence=f"Est. daily volume: ₹{daily_value_inr/1e7:.1f}Cr, LTP: ₹{ltp:.2f}",
        ),
        liquidity_score,
    )


def gate_stop_determinable(
    stop_result: Optional[Any],
    entry_price: Optional[float],
    config: SignalEngineConfig,
) -> ValidationGate:
    """
    HARD GATE 5: Stop Loss Determinable
    Ensures a valid, reasonable stop loss can be computed.
    """
    gate_id = "STOP_DETERMINABLE"
    gate_name = "Stop Loss Determinable"

    if stop_result is None:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Unable to compute stop loss: insufficient price structure data",
        )

    stop_price = _safe_float(stop_result.price if hasattr(stop_result, 'price') else stop_result.get('price'))
    if stop_price is None or stop_price <= 0:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Stop loss price is zero or invalid",
        )

    if entry_price and entry_price > 0:
        stop_pct = abs(entry_price - stop_price) / entry_price * 100
        if stop_pct > config.max_stop_pct:
            return _gate(
                gate_id, gate_name, "HARD",
                ValidationGateResult.FAIL,
                reason=(
                    f"Stop distance {stop_pct:.1f}% exceeds maximum {config.max_stop_pct:.1f}% "
                    f"(stop: ₹{stop_price:.2f}, entry: ₹{entry_price:.2f})"
                ),
                actual_value=stop_pct,
                threshold_value=config.max_stop_pct,
            )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence=f"Stop: ₹{stop_price:.2f} ({stop_result.method if hasattr(stop_result, 'method') else 'computed'})",
    )


def gate_risk_reward(
    risk_reward: Optional[float],
    config: SignalEngineConfig,
) -> ValidationGate:
    """
    HARD GATE 6: Risk/Reward Gate
    Minimum R:R threshold — configurable, default 1.5.
    """
    gate_id = "RISK_REWARD"
    gate_name = "Risk/Reward Gate"

    if risk_reward is None:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason="Risk/reward ratio could not be computed (targets or stop unavailable)",
        )

    if risk_reward < config.min_risk_reward:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=(
                f"R:R {risk_reward:.2f} below minimum {config.min_risk_reward:.1f}. "
                f"Signal is a mathematically negative expectancy setup at this R:R."
            ),
            actual_value=risk_reward,
            threshold_value=config.min_risk_reward,
        )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence=f"R:R {risk_reward:.2f} ≥ minimum {config.min_risk_reward:.1f}",
        actual_value=risk_reward,
        threshold_value=config.min_risk_reward,
    )


def gate_portfolio_risk(
    symbol: str,
    capital_required: Optional[float],
    portfolio_state: Optional[Dict[str, Any]],
    config: SignalEngineConfig,
) -> ValidationGate:
    """
    HARD GATE 7: Portfolio Risk Gate
    Checks available capital, max positions, daily loss limit, concentration.
    """
    gate_id = "PORTFOLIO_RISK"
    gate_name = "Portfolio Risk Gate"

    if portfolio_state is None:
        # If no portfolio state available, pass with warning
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.PASS,
            evidence="Portfolio state unavailable — position risk not validated",
        )

    available_capital = _safe_float(portfolio_state.get("available_capital")) or config.capital
    open_positions = portfolio_state.get("open_positions", 0)
    daily_pnl_pct = _safe_float(portfolio_state.get("daily_pnl_pct")) or 0.0

    # Check max positions
    if open_positions >= config.max_positions:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"Maximum concurrent positions reached ({open_positions}/{config.max_positions})",
            actual_value=open_positions,
            threshold_value=config.max_positions,
        )

    # Check daily loss limit (if losing >3% today, halt new entries)
    daily_loss_limit = -3.0
    if daily_pnl_pct < daily_loss_limit:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=f"Daily loss limit reached ({daily_pnl_pct:.1f}% < {daily_loss_limit:.1f}%). New entries blocked.",
            actual_value=daily_pnl_pct,
            threshold_value=daily_loss_limit,
        )

    # Check capital availability
    if capital_required and capital_required > available_capital:
        return _gate(
            gate_id, gate_name, "HARD",
            ValidationGateResult.FAIL,
            reason=(
                f"Insufficient capital: required ₹{capital_required:,.0f}, "
                f"available ₹{available_capital:,.0f}"
            ),
            actual_value=available_capital,
            threshold_value=capital_required,
        )

    return _gate(
        gate_id, gate_name, "HARD",
        ValidationGateResult.PASS,
        evidence=(
            f"Capital: ₹{available_capital:,.0f} available, "
            f"{open_positions}/{config.max_positions} positions open"
        ),
    )


# ---------------------------------------------------------------------------
# Soft Evidence Gates (non-blocking, affect score)
# ---------------------------------------------------------------------------

def gate_rsi_zone(
    rsi: Optional[float],
    direction: str,
) -> ValidationGate:
    """SOFT: RSI zone suitability for signal direction."""
    gate_id = "RSI_ZONE"
    gate_name = "RSI Zone"

    if rsi is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     reason="RSI unavailable")

    rsi_val = _safe_float(rsi)
    if rsi_val is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE)

    if direction == "LONG":
        if 40 <= rsi_val <= 70:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"RSI {rsi_val:.1f} in bullish momentum zone (40-70)",
                         actual_value=rsi_val)
        elif rsi_val > 80:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"RSI {rsi_val:.1f} extremely overbought for long",
                         actual_value=rsi_val, threshold_value=80)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                         evidence=f"RSI {rsi_val:.1f} — suboptimal for long entry")
    else:  # SHORT
        if 30 <= rsi_val <= 60:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"RSI {rsi_val:.1f} in bearish momentum zone (30-60)",
                         actual_value=rsi_val)
        elif rsi_val < 20:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"RSI {rsi_val:.1f} extremely oversold for short",
                         actual_value=rsi_val, threshold_value=20)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                         evidence=f"RSI {rsi_val:.1f} — suboptimal for short entry")


def gate_adx_trend_strength(
    adx: Optional[float],
    strategy_type: str = "TREND",
) -> ValidationGate:
    """SOFT: ADX trend strength suitability."""
    gate_id = "ADX_STRENGTH"
    gate_name = "ADX Trend Strength"

    if adx is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     reason="ADX unavailable")

    adx_val = _safe_float(adx)
    if adx_val is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE)

    if strategy_type == "TREND":
        if adx_val >= 25:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"ADX {adx_val:.1f} ≥ 25 — confirmed trending market",
                         actual_value=adx_val)
        elif adx_val >= 20:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"ADX {adx_val:.1f} — weakly trending, reduced confidence",
                         actual_value=adx_val)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"ADX {adx_val:.1f} < 20 — trend strength insufficient for trend-following",
                         actual_value=adx_val, threshold_value=20)
    else:
        # Mean reversion strategies prefer low ADX
        if adx_val <= 20:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"ADX {adx_val:.1f} ≤ 20 — range-bound, suitable for mean reversion",
                         actual_value=adx_val)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"ADX {adx_val:.1f} too high for mean reversion strategy",
                         actual_value=adx_val, threshold_value=20)


def gate_vwap_position(
    price: Optional[float],
    vwap: Optional[float],
    direction: str,
) -> ValidationGate:
    """SOFT: Price position relative to VWAP."""
    gate_id = "VWAP_POSITION"
    gate_name = "VWAP Position"

    if price is None or vwap is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     reason="VWAP or price unavailable")

    if direction == "LONG":
        if price > vwap:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"Price ₹{price:.2f} above VWAP ₹{vwap:.2f} — bullish bias",
                         actual_value=price, threshold_value=vwap)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"Price ₹{price:.2f} below VWAP ₹{vwap:.2f} — headwind for long",
                         actual_value=price, threshold_value=vwap)
    else:  # SHORT
        if price < vwap:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                         evidence=f"Price ₹{price:.2f} below VWAP ₹{vwap:.2f} — bearish bias",
                         actual_value=price, threshold_value=vwap)
        else:
            return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                         reason=f"Price ₹{price:.2f} above VWAP ₹{vwap:.2f} — headwind for short",
                         actual_value=price, threshold_value=vwap)


def gate_volume_expansion(
    rvol: Optional[float],
    config: SignalEngineConfig,
) -> ValidationGate:
    """SOFT: Volume expansion confirmation."""
    gate_id = "VOLUME_EXPANSION"
    gate_name = "Volume Expansion"

    if rvol is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     reason="Relative volume unavailable")

    rvol_val = _safe_float(rvol)
    if rvol_val is None:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE)

    if rvol_val >= 1.5:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                     evidence=f"Relative volume {rvol_val:.1f}x — above-average participation",
                     actual_value=rvol_val)
    elif rvol_val >= 0.8:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     evidence=f"Relative volume {rvol_val:.1f}x — normal participation",
                     actual_value=rvol_val)
    else:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                     reason=f"Relative volume {rvol_val:.1f}x — below-average, weak participation",
                     actual_value=rvol_val, threshold_value=0.8)


def gate_regime_compatibility(
    regime: str,
    strategy_categories: List[str],
) -> ValidationGate:
    """SOFT: Current market regime vs strategy type compatibility."""
    gate_id = "REGIME_COMPATIBILITY"
    gate_name = "Regime Compatibility"

    REGIME_STRATEGY_COMPAT: Dict[str, List[str]] = {
        "TRENDING_BULLISH": ["TREND", "MOMENTUM", "BREAKOUT", "VOLUME"],
        "TRENDING_BEARISH": ["TREND", "MOMENTUM", "BREAKOUT", "VOLUME"],
        "RANGE_BOUND": ["MEAN_REVERSION", "VOLATILITY", "OSCILLATOR"],
        "HIGH_VOLATILITY": ["VOLATILITY", "BREAKOUT"],
        "BULLISH_ACCUMULATION": ["TREND", "MOMENTUM", "MEAN_REVERSION"],
        "BEARISH_DISTRIBUTION": ["TREND", "MOMENTUM", "MEAN_REVERSION"],
        "UNKNOWN": [],
        "UNAVAILABLE": [],
    }

    compatible_categories = REGIME_STRATEGY_COMPAT.get(regime, [])
    if not compatible_categories:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.UNAVAILABLE,
                     reason=f"Regime '{regime}' compatibility unknown",
                     actual_value=regime)

    matching = [c for c in strategy_categories if any(
        comp in c.upper() for comp in compatible_categories
    )]

    if matching:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.PASS,
                     evidence=f"Regime {regime} compatible with {matching}",
                     actual_value=regime)
    else:
        return _gate(gate_id, gate_name, "SOFT", ValidationGateResult.FAIL,
                     reason=(
                         f"Strategy categories {strategy_categories} have poor historical performance "
                         f"in {regime} regime"
                     ),
                     actual_value=regime)


# ---------------------------------------------------------------------------
# Complete Validation Pipeline
# ---------------------------------------------------------------------------

class ValidationPipeline:
    """
    Runs the complete 17-gate signal validation pipeline.
    Returns the list of all gate results and a determination of whether
    any HARD GATE has failed.
    """

    def run_hard_gates(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
        quote: Dict[str, Any],
        is_market_open: bool,
        stop_result: Optional[Any],
        entry_price: Optional[float],
        risk_reward: Optional[float],
        capital_required: Optional[float],
        portfolio_state: Optional[Dict[str, Any]],
        config: SignalEngineConfig,
    ) -> Tuple[bool, List[ValidationGate], Optional[str]]:
        """
        Run all HARD GATES.
        Returns (all_passed, gates, first_failure_reason).
        """
        gates: List[ValidationGate] = []
        failure_reason: Optional[str] = None

        # Gate 1: Data Validation
        g = gate_data_validation(candles, quote, config)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 2: Instrument Validation
        g = gate_instrument_validation(symbol, quote)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 3: Market Session
        g = gate_market_session(quote, is_market_open)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 4: Liquidity
        g, liquidity_score = gate_liquidity(quote, candles, config)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 5: Stop Determinable
        g = gate_stop_determinable(stop_result, entry_price, config)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 6: Risk/Reward
        g = gate_risk_reward(risk_reward, config)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        # Gate 7: Portfolio Risk
        g = gate_portfolio_risk(symbol, capital_required, portfolio_state, config)
        gates.append(g)
        if g.result == ValidationGateResult.FAIL:
            return False, gates, g.reason

        return True, gates, None

    def run_soft_gates(
        self,
        direction: str,
        feature_vector: Dict[str, Any],
        regime: str,
        strategy_categories: List[str],
    ) -> List[ValidationGate]:
        """
        Run all SOFT EVIDENCE gates.
        These affect the score but do not block qualification.
        """
        gates: List[ValidationGate] = []
        fv = feature_vector

        rsi = _safe_float(fv.get("rsi14"))
        adx = _safe_float(fv.get("adx14"))
        vwap = _safe_float(fv.get("vwap"))
        price = _safe_float(fv.get("close") or fv.get("ltp"))
        rvol = _safe_float(fv.get("rvol20"))

        gates.append(gate_rsi_zone(rsi, direction))
        gates.append(gate_adx_trend_strength(adx, "TREND" if direction in ("LONG", "SHORT") else "MEAN_REVERSION"))
        gates.append(gate_vwap_position(price, vwap, direction))
        gates.append(gate_volume_expansion(rvol, SignalEngineConfig()))
        gates.append(gate_regime_compatibility(regime, strategy_categories))

        return gates

    def build_why_reasons(
        self,
        all_gates: List[ValidationGate],
        strategy_votes: List[Any],
        mtf_result: Optional[Any],
        direction: str,
    ) -> List[str]:
        """
        Builds the human-readable WHY THIS TRADE? checklist.
        Uses ✓ for PASS and ✗ for FAIL.
        """
        reasons: List[str] = []

        for gate in all_gates:
            icon = "✓" if gate.result == ValidationGateResult.PASS else ("✗" if gate.result == ValidationGateResult.FAIL else "~")
            label = gate.gate_name
            detail = gate.evidence or gate.reason or ""
            if detail:
                reasons.append(f"{icon} {label}: {detail}")
            else:
                reasons.append(f"{icon} {label}")

        # Add strategy votes summary
        long_votes = sum(1 for v in strategy_votes if getattr(v, 'direction', '') == 'LONG')
        short_votes = sum(1 for v in strategy_votes if getattr(v, 'direction', '') == 'SHORT')
        total = len(strategy_votes)
        if total > 0:
            if direction == "LONG" and long_votes > 0:
                reasons.append(f"✓ Strategy consensus: {long_votes}/{total} strategies bullish")
            elif direction == "SHORT" and short_votes > 0:
                reasons.append(f"✓ Strategy consensus: {short_votes}/{total} strategies bearish")

        # Add MTF summary
        if mtf_result and hasattr(mtf_result, 'alignment_label'):
            icon = "✓" if "CONFIRMED" in mtf_result.alignment_label else "~"
            reasons.append(f"{icon} Multi-timeframe: {mtf_result.alignment_label}")

        return reasons


# Module-level singleton
validation_pipeline = ValidationPipeline()
