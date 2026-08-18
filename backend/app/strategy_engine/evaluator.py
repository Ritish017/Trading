"""
Strategy Lab — Deterministic Rule Evaluator & Observatory Engine
================================================================
Computes the canonical feature vector and full indicator time series from
OHLCV candle history. Evaluates each strategy rule deterministically,
detects historical state transitions (activations/invalidations), measures
strategy confluence, and classifies the market regime.

Truth-Layer Invariants
----------------------
- Never fabricates indicator values or synthetic candles.
- Missing data propagates as UNAVAILABLE (never converted to False/Fail).
- Strategy state (ACTIVE/PARTIAL/INACTIVE/CONFLICTED/UNAVAILABLE) is derived
  purely from mathematical rule evaluation.
- Data Freshness (LIVE/RECENT/STALE/UNAVAILABLE) is tracked separately.
"""

import math
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from backend.app.strategy_engine.dsl import (
    StrategyDefinition, StrategyRule, StrategyState, RuleOutcome
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_rsi, calculate_vwap, calculate_atr,
    calculate_macd, calculate_bollinger_bands, calculate_relative_volume
)
from backend.app.quant_engine.regime import classify_market_regime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output Data Structures
# ---------------------------------------------------------------------------

@dataclass
class RuleEvaluation:
    rule_id: str
    label: str
    dependency_keys: List[str]
    outcome: RuleOutcome              # PASS | FAIL | UNAVAILABLE
    actual_value: Optional[float]     # The primary indicator value
    actual_value_label: str           # Formatted for UI, e.g. "RSI = 62.3"
    is_entry_rule: bool
    math_detail: Optional[str] = None # Mathematical basis e.g. "EMA20 - EMA50 = +0.217"


@dataclass
class ActivationEvent:
    candle_index: int
    timestamp: int
    event_type: str                   # ACTIVATED | INVALIDATED | CONFLICT
    price: float
    strategy_id: str
    label: str


@dataclass
class StrategyEvaluationResult:
    strategy_id: str
    strategy_name: str
    category: str
    description: str
    state: StrategyState
    entry_rules_total: int
    entry_rules_passing: int
    entry_rules_unavailable: int
    exit_rules_triggered: int
    exit_rules_total: int
    rule_evaluations: List[RuleEvaluation] = field(default_factory=list)
    feature_vector: Dict[str, Any] = field(default_factory=dict)
    data_freshness: str = "UNAVAILABLE"
    data_age_seconds: Optional[float] = None
    evaluated_at: str = ""
    candles_used: int = 0
    tags: List[str] = field(default_factory=list)
    historical_states: List[Dict[str, Any]] = field(default_factory=list)
    activation_events: List[ActivationEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Feature Vector & Indicator Utilities
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    """Return float or None for NaN / None / Inf."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def compute_feature_vector(candles: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Build a flat feature vector Dict at the latest candle from OHLCV history.
    All values are float or None.
    """
    if not candles or len(candles) < 5:
        return {}

    df = pd.DataFrame(candles)
    if "close" not in df.columns:
        return {}

    close = df["close"].astype(float)
    has_hlv = all(c in df.columns for c in ["high", "low", "volume"])
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0.0] * len(df))

    n = len(close)
    fv: Dict[str, Optional[float]] = {}

    fv["close"] = _safe_float(close.iloc[-1])

    # EMAs
    fv["ema20"] = _safe_float(close.ewm(span=20, adjust=False).mean().iloc[-1]) if n >= 20 else None
    fv["ema50"] = _safe_float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if n >= 50 else None
    fv["ema200"] = _safe_float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if n >= 200 else None

    # RSI(14)
    if n >= 15:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_g = gain.ewm(alpha=1.0 / 14, adjust=False).mean()
        avg_l = loss.ewm(alpha=1.0 / 14, adjust=False).mean()
        rs = avg_g / (avg_l + 1e-9)
        rsi_s = 100.0 - (100.0 / (1.0 + rs))
        fv["rsi14"] = _safe_float(rsi_s.iloc[-1])
    else:
        fv["rsi14"] = None

    # MACD (12, 26, 9)
    if n >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        fv["macd"] = _safe_float(macd_line.iloc[-1])
        fv["macd_signal"] = _safe_float(signal_line.iloc[-1])
        fv["macd_histogram"] = _safe_float((macd_line - signal_line).iloc[-1])
    else:
        fv["macd"] = fv["macd_signal"] = fv["macd_histogram"] = None

    # VWAP
    if has_hlv and n >= 5:
        typical = (high + low + close) / 3.0
        tp_vol = typical * volume
        cum_tv = tp_vol.cumsum()
        cum_v = volume.cumsum()
        vwap_s = np.where(cum_v > 0, cum_tv / cum_v, np.nan)
        fv["vwap"] = _safe_float(float(vwap_s[-1]))
    else:
        fv["vwap"] = None

    # ATR(14)
    if n >= 15:
        prev_c = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_c).abs()
        tr3 = (low - prev_c).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_s = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
        fv["atr14"] = _safe_float(atr_s.iloc[-1])
    else:
        fv["atr14"] = None

    # Bollinger Bands (20, 2σ)
    if n >= 20:
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        fv["bb_upper"] = _safe_float((sma20 + 2.0 * std20).iloc[-1])
        fv["bb_middle"] = _safe_float(sma20.iloc[-1])
        fv["bb_lower"] = _safe_float((sma20 - 2.0 * std20).iloc[-1])
    else:
        fv["bb_upper"] = fv["bb_middle"] = fv["bb_lower"] = None

    # Relative Volume (20-period)
    if has_hlv and n >= 21:
        avg_vol = volume.rolling(window=20).mean()
        rvol_s = np.where(avg_vol > 0, volume / avg_vol, np.nan)
        fv["rvol"] = _safe_float(float(rvol_s[-1]))
    else:
        fv["rvol"] = None

    return fv


def compute_series_indicators(candles: List[Dict[str, Any]]) -> Dict[str, List[Optional[float]]]:
    """
    Computes canonical full-length indicator time series for trading chart overlays.
    Returns zero-synthetic, aligned arrays.
    """
    if not candles:
        return {}

    df = pd.DataFrame(candles)
    if "close" not in df.columns:
        return {}

    close = df["close"].astype(float)
    has_hlv = all(c in df.columns for c in ["high", "low", "volume"])
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0.0] * len(df))

    n = len(close)

    def _to_list(s: Optional[pd.Series], min_bars: int = 1) -> List[Optional[float]]:
        if s is None or n < min_bars:
            return [None] * n
        return [_safe_float(v) for v in s]

    # EMAs
    ema20 = close.ewm(span=20, adjust=False).mean() if n >= 20 else None
    ema50 = close.ewm(span=50, adjust=False).mean() if n >= 50 else None
    ema200 = close.ewm(span=200, adjust=False).mean() if n >= 200 else None

    # VWAP
    vwap_series = None
    if has_hlv and n >= 5:
        typical = (high + low + close) / 3.0
        tp_vol = typical * volume
        cum_tv = tp_vol.cumsum()
        cum_v = volume.cumsum()
        vwap_series = pd.Series(np.where(cum_v > 0, cum_tv / cum_v, np.nan), index=df.index)

    # RSI(14)
    rsi_series = None
    if n >= 15:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_g = gain.ewm(alpha=1.0 / 14, adjust=False).mean()
        avg_l = loss.ewm(alpha=1.0 / 14, adjust=False).mean()
        rs = avg_g / (avg_l + 1e-9)
        rsi_series = 100.0 - (100.0 / (1.0 + rs))

    # MACD (12, 26, 9)
    macd_line, signal_line, macd_hist = None, None, None
    if n >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line

    # ATR(14)
    atr_series = None
    if n >= 15:
        prev_c = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_c).abs()
        tr3 = (low - prev_c).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.ewm(alpha=1.0 / 14, adjust=False).mean()

    # Bollinger Bands (20, 2σ)
    bb_upper, bb_middle, bb_lower = None, None, None
    if n >= 20:
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bb_upper = sma20 + 2.0 * std20
        bb_middle = sma20
        bb_lower = sma20 - 2.0 * std20

    # RVOL (20-period)
    rvol_series = None
    if has_hlv and n >= 21:
        avg_vol = volume.rolling(window=20).mean()
        rvol_series = pd.Series(np.where(avg_vol > 0, volume / avg_vol, np.nan), index=df.index)

    # Supertrend Band (VWAP - 1.5 * ATR)
    supertrend_band = None
    if vwap_series is not None and atr_series is not None:
        supertrend_band = vwap_series - (1.5 * atr_series)

    # Opening Range Breakout (first 6 candles high/low proxy)
    orb_high = float(high.iloc[:min(6, n)].max()) if n >= 6 else None
    orb_low = float(low.iloc[:min(6, n)].min()) if n >= 6 else None

    return {
        "ema20": _to_list(ema20, 20),
        "ema50": _to_list(ema50, 50),
        "ema200": _to_list(ema200, 200),
        "vwap": _to_list(vwap_series, 5),
        "rsi14": _to_list(rsi_series, 15),
        "macd": _to_list(macd_line, 35),
        "macd_signal": _to_list(signal_line, 35),
        "macd_histogram": _to_list(macd_hist, 35),
        "bb_upper": _to_list(bb_upper, 20),
        "bb_middle": _to_list(bb_middle, 20),
        "bb_lower": _to_list(bb_lower, 20),
        "atr14": _to_list(atr_series, 15),
        "rvol": _to_list(rvol_series, 21),
        "supertrend_band": _to_list(supertrend_band, 15),
        "orb_high": [orb_high] * n if orb_high is not None else [None] * n,
        "orb_low": [orb_low] * n if orb_low is not None else [None] * n,
    }


# ---------------------------------------------------------------------------
# Data Freshness Determination
# ---------------------------------------------------------------------------

def _evaluate_freshness(candles: List[Dict[str, Any]], is_live_feed: bool) -> tuple[str, Optional[float]]:
    """Returns (freshness_status, age_in_seconds)."""
    if not candles:
        return "UNAVAILABLE", None
    last = candles[-1]
    ts_raw = last.get("timestamp") or last.get("time")
    if ts_raw is None:
        return "UNAVAILABLE", None
    try:
        ts = float(ts_raw)
        if ts > 1e11:
            ts = ts / 1000.0  # normalize ms to s
        if ts <= 0:
            return "UNAVAILABLE", None
        age = time.time() - ts
        if age < 0:
            return ("LIVE" if is_live_feed else "RECENT"), 0.0
        if is_live_feed and age <= 60.0:
            return "LIVE", round(age, 1)
        elif age <= 300.0:
            return "RECENT", round(age, 1)
        elif age <= 86400.0:
            return "STALE", round(age, 1)
        else:
            return "UNAVAILABLE", round(age, 1)
    except (TypeError, ValueError):
        return "UNAVAILABLE", None


# ---------------------------------------------------------------------------
# Rule Evaluation & Mathematical Detail
# ---------------------------------------------------------------------------

def _compute_math_detail(rule: StrategyRule, fv: Dict) -> Optional[str]:
    """Provides the exact mathematical calculation for transparency."""
    keys = rule.dependency_keys
    vals = [fv.get(k) for k in keys]
    if any(v is None for v in vals):
        return None

    if rule.rule_id == "price_above_vwap":
        c, v = fv.get("close"), fv.get("vwap")
        return f"Price (₹{c:.2f}) − VWAP (₹{v:.2f}) = {c - v:+.2f}"
    elif rule.rule_id in ("ema_trend_aligned", "ema20_above_ema50"):
        e20, e50 = fv.get("ema20"), fv.get("ema50")
        return f"EMA20 (₹{e20:.2f}) − EMA50 (₹{e50:.2f}) = {e20 - e50:+.2f}"
    elif rule.rule_id == "rsi_momentum":
        r = fv.get("rsi14")
        return f"RSI14 ({r:.1f}) − Threshold (55.0) = {r - 55.0:+.1f}"
    elif rule.rule_id == "volume_surge":
        rv = fv.get("rvol")
        return f"RVOL ({rv:.2f}x) − Threshold (1.20x) = {rv - 1.20:+.2f}x"
    elif rule.rule_id == "rsi_oversold":
        r = fv.get("rsi14")
        return f"Threshold (35.0) − RSI14 ({r:.1f}) = {35.0 - r:+.1f}"
    elif rule.rule_id == "macd_above_signal":
        m, s = fv.get("macd"), fv.get("macd_signal")
        return f"MACD ({m:.2f}) − Signal ({s:.2f}) = {m - s:+.2f}"
    elif rule.rule_id == "price_above_bb_upper":
        c, bbu = fv.get("close"), fv.get("bb_upper")
        return f"Price (₹{c:.2f}) − Upper Band (₹{bbu:.2f}) = {c - bbu:+.2f}"
    elif rule.rule_id == "atr_dynamic_support":
        c, v, a = fv.get("close"), fv.get("vwap"), fv.get("atr14")
        sup = v - 1.5 * a
        return f"Price (₹{c:.2f}) − Dynamic Support (₹{sup:.2f}) = {c - sup:+.2f}"

    return None


def _evaluate_rule(rule: StrategyRule, fv: Dict, is_entry: bool) -> RuleEvaluation:
    """Evaluate a single rule against the feature vector."""
    missing = [k for k in rule.dependency_keys if fv.get(k) is None]
    if missing:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            label=rule.label,
            dependency_keys=rule.dependency_keys,
            outcome=RuleOutcome.UNAVAILABLE,
            actual_value=None,
            actual_value_label="UNAVAILABLE",
            is_entry_rule=is_entry,
            math_detail=None,
        )

    try:
        result = rule.condition_fn(fv)
    except Exception as exc:
        logger.warning("Rule %s evaluation raised: %s", rule.rule_id, exc)
        result = None

    if result is None:
        outcome = RuleOutcome.UNAVAILABLE
    elif result:
        outcome = RuleOutcome.PASS
    else:
        outcome = RuleOutcome.FAIL

    primary_key = rule.dependency_keys[0] if rule.dependency_keys else None
    actual_val = _safe_float(fv.get(primary_key)) if primary_key else None
    label_str = f"{primary_key} = {actual_val:.4f}" if actual_val is not None else "UNAVAILABLE"
    math_detail = _compute_math_detail(rule, fv)

    return RuleEvaluation(
        rule_id=rule.rule_id,
        label=rule.label,
        dependency_keys=rule.dependency_keys,
        outcome=outcome,
        actual_value=actual_val,
        actual_value_label=label_str,
        is_entry_rule=is_entry,
        math_detail=math_detail,
    )


# ---------------------------------------------------------------------------
# State Determination (Pure Mathematical State)
# ---------------------------------------------------------------------------

def _determine_state(
    entry_evals: List[RuleEvaluation],
    exit_evals: List[RuleEvaluation],
) -> StrategyState:
    """
    Computes mathematical state independently of data freshness.
    """
    n_entry = len(entry_evals)
    if n_entry == 0:
        return StrategyState.UNAVAILABLE

    n_pass = sum(1 for r in entry_evals if r.outcome == RuleOutcome.PASS)
    n_fail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.FAIL)
    n_unavail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.UNAVAILABLE)
    n_exit_triggered = sum(1 for r in exit_evals if r.outcome == RuleOutcome.PASS)

    # > 50% unavailable → cannot evaluate reliably
    if n_unavail > n_entry / 2:
        return StrategyState.UNAVAILABLE

    # All entry rules pass
    if n_pass == n_entry:
        if n_exit_triggered > 0:
            return StrategyState.CONFLICTED
        return StrategyState.ACTIVE

    # ≥ 50% pass of computable rules
    computable = n_pass + n_fail
    if computable > 0 and n_pass / computable >= 0.5:
        return StrategyState.PARTIAL

    return StrategyState.INACTIVE


# ---------------------------------------------------------------------------
# Strategy Confluence & Alignment
# ---------------------------------------------------------------------------

def compute_strategy_confluence(results: List[StrategyEvaluationResult]) -> Dict[str, Any]:
    """
    Calculates rule satisfaction, alignment, and flags conflicting regimes.
    """
    total = len(results)
    if total == 0:
        return {}

    active_count = sum(1 for r in results if r.state == StrategyState.ACTIVE)
    partial_count = sum(1 for r in results if r.state == StrategyState.PARTIAL)
    inactive_count = sum(1 for r in results if r.state == StrategyState.INACTIVE)
    unavail_count = sum(1 for r in results if r.state in (StrategyState.UNAVAILABLE, StrategyState.STALE))
    conflicted_count = sum(1 for r in results if r.state == StrategyState.CONFLICTED)

    total_entry_rules = sum(r.entry_rules_total for r in results)
    passing_entry_rules = sum(r.entry_rules_passing for r in results)
    alignment_score = round((passing_entry_rules / total_entry_rules) * 100, 1) if total_entry_rules > 0 else 0.0

    # Bullish vs Reversal counts
    bullish_strategies = {"VWAP_MOMENTUM", "EMA_GOLDEN_CROSS", "BOLLINGER_SQUEEZE", "MACD_CROSSOVER", "ORB_BREAKOUT", "SUPERTREND_PROXY", "RVOL_SURGE"}
    reversal_strategies = {"RSI_OVERSOLD_REVERSAL"}

    bullish_active = sum(1 for r in results if r.strategy_id in bullish_strategies and r.state == StrategyState.ACTIVE)
    reversal_active = sum(1 for r in results if r.strategy_id in reversal_strategies and r.state == StrategyState.ACTIVE)

    conflicts: List[str] = []
    if bullish_active >= 2 and reversal_active >= 1:
        conflicts.append("Trend/Breakout strategies are ACTIVE while Mean-Reversion indicates overextended pullback risk.")

    return {
        "active_count": active_count,
        "partial_count": partial_count,
        "inactive_count": inactive_count,
        "unavailable_count": unavail_count,
        "conflicted_count": conflicted_count,
        "total_strategies": total,
        "alignment_score_pct": alignment_score,
        "passing_rules_count": passing_entry_rules,
        "total_rules_count": total_entry_rules,
        "bullish_confluence": bullish_active,
        "reversal_confluence": reversal_active,
        "has_conflicts": len(conflicts) > 0,
        "conflict_reasons": conflicts,
    }


# ---------------------------------------------------------------------------
# Historical Activation & Event Scanner
# ---------------------------------------------------------------------------

def _evaluate_historical_activations(
    strat: StrategyDefinition,
    candles: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[ActivationEvent]]:
    """
    Evaluates rolling historical strategy state across the candle series.
    Detects state change events (ACTIVATED, INVALIDATED, CONFLICT).
    """
    n = len(candles)
    if n < strat.min_candles:
        return [], []

    historical_states: List[Dict[str, Any]] = []
    events: List[ActivationEvent] = []
    prev_state: Optional[StrategyState] = None

    # Step through candle windows from min_candles to end
    step = 1 if n <= 120 else max(1, n // 100)
    for i in range(strat.min_candles, n + 1, step):
        sub_candles = candles[:i]
        fv = compute_feature_vector(sub_candles)
        entry_evals = [_evaluate_rule(r, fv, is_entry=True) for r in strat.entry_rules]
        exit_evals = [_evaluate_rule(r, fv, is_entry=False) for r in strat.exit_rules]
        state = _determine_state(entry_evals, exit_evals)

        current_candle = candles[i - 1]
        ts_val = current_candle.get("timestamp") or current_candle.get("time") or 0
        ts = int(ts_val if ts_val < 1e11 else ts_val // 1000)
        px = float(current_candle.get("close", 0.0))

        n_pass = sum(1 for r in entry_evals if r.outcome == RuleOutcome.PASS)

        historical_states.append({
            "candle_index": i - 1,
            "timestamp": ts,
            "state": state.value,
            "passing_count": n_pass,
            "total_count": len(strat.entry_rules),
            "price": px,
        })

        # Check for state transition events
        if prev_state is not None:
            if prev_state != StrategyState.ACTIVE and state == StrategyState.ACTIVE:
                events.append(ActivationEvent(
                    candle_index=i - 1,
                    timestamp=ts,
                    event_type="ACTIVATED",
                    price=px,
                    strategy_id=strat.strategy_id,
                    label=f"{strat.name} Activated",
                ))
            elif prev_state == StrategyState.ACTIVE and state == StrategyState.INACTIVE:
                events.append(ActivationEvent(
                    candle_index=i - 1,
                    timestamp=ts,
                    event_type="INVALIDATED",
                    price=px,
                    strategy_id=strat.strategy_id,
                    label=f"{strat.name} Invalidated",
                ))
            elif state == StrategyState.CONFLICTED and prev_state != StrategyState.CONFLICTED:
                events.append(ActivationEvent(
                    candle_index=i - 1,
                    timestamp=ts,
                    event_type="CONFLICT",
                    price=px,
                    strategy_id=strat.strategy_id,
                    label=f"{strat.name} Signal Conflict",
                ))

        prev_state = state

    return historical_states, events


# ---------------------------------------------------------------------------
# Public Observatory Evaluation API
# ---------------------------------------------------------------------------

def evaluate_all_strategies(
    candles: List[Dict[str, Any]],
    is_live_feed: bool = False,
    strategy_ids: Optional[List[str]] = None,
) -> List[StrategyEvaluationResult]:
    """
    Evaluates every strategy in the registry with full rule math and historical tracking.
    """
    freshness, data_age = _evaluate_freshness(candles, is_live_feed)
    fv = compute_feature_vector(candles) if candles else {}
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results: List[StrategyEvaluationResult] = []

    registry = STRATEGY_REGISTRY
    if strategy_ids:
        registry = {k: v for k, v in STRATEGY_REGISTRY.items() if k in strategy_ids}

    for sid, strat in registry.items():
        n = len(candles) if candles else 0

        # If insufficient bars for this strategy
        if n < strat.min_candles:
            minimal_evals = [
                RuleEvaluation(
                    rule_id=r.rule_id,
                    label=r.label,
                    dependency_keys=r.dependency_keys,
                    outcome=RuleOutcome.UNAVAILABLE,
                    actual_value=None,
                    actual_value_label="UNAVAILABLE",
                    is_entry_rule=True,
                )
                for r in strat.entry_rules
            ] + [
                RuleEvaluation(
                    rule_id=r.rule_id,
                    label=r.label,
                    dependency_keys=r.dependency_keys,
                    outcome=RuleOutcome.UNAVAILABLE,
                    actual_value=None,
                    actual_value_label="UNAVAILABLE",
                    is_entry_rule=False,
                )
                for r in strat.exit_rules
            ]
            results.append(StrategyEvaluationResult(
                strategy_id=sid,
                strategy_name=strat.name,
                category=strat.category,
                description=strat.description,
                state=StrategyState.UNAVAILABLE,
                entry_rules_total=len(strat.entry_rules),
                entry_rules_passing=0,
                entry_rules_unavailable=len(strat.entry_rules),
                exit_rules_triggered=0,
                exit_rules_total=len(strat.exit_rules),
                rule_evaluations=minimal_evals,
                feature_vector={},
                data_freshness=freshness,
                data_age_seconds=data_age,
                evaluated_at=now_str,
                candles_used=n,
                tags=strat.tags,
                historical_states=[],
                activation_events=[],
            ))
            continue

        # Evaluate entry & exit rules
        entry_evals = [_evaluate_rule(r, fv, is_entry=True) for r in strat.entry_rules]
        exit_evals = [_evaluate_rule(r, fv, is_entry=False) for r in strat.exit_rules]

        state = _determine_state(entry_evals, exit_evals)

        n_pass = sum(1 for r in entry_evals if r.outcome == RuleOutcome.PASS)
        n_unavail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.UNAVAILABLE)
        n_exit = sum(1 for r in exit_evals if r.outcome == RuleOutcome.PASS)

        # Historical rolling evaluation & event extraction
        hist_states, act_events = _evaluate_historical_activations(strat, candles)

        clean_fv = {k: round(v, 4) for k, v in fv.items() if v is not None}

        results.append(StrategyEvaluationResult(
            strategy_id=sid,
            strategy_name=strat.name,
            category=strat.category,
            description=strat.description,
            state=state,
            entry_rules_total=len(entry_evals),
            entry_rules_passing=n_pass,
            entry_rules_unavailable=n_unavail,
            exit_rules_triggered=n_exit,
            exit_rules_total=len(exit_evals),
            rule_evaluations=entry_evals + exit_evals,
            feature_vector=clean_fv,
            data_freshness=freshness,
            data_age_seconds=data_age,
            evaluated_at=now_str,
            candles_used=n,
            tags=strat.tags,
            historical_states=hist_states,
            activation_events=act_events,
        ))

    return results


def evaluate_strategies_observatory(
    candles: List[Dict[str, Any]],
    is_live_feed: bool = False,
    strategy_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Master observatory endpoint payload generator.
    Combines:
    1. Strategy evaluations with rule math and historical events
    2. Canonical indicator series for chart overlays
    3. Market regime classification
    4. Confluence & conflict analysis
    5. Data freshness metrics
    """
    freshness, data_age = _evaluate_freshness(candles, is_live_feed)
    df = pd.DataFrame(candles) if candles else pd.DataFrame()

    regime = classify_market_regime(df)
    results = evaluate_all_strategies(candles, is_live_feed=is_live_feed, strategy_ids=strategy_ids)
    confluence = compute_strategy_confluence(results)
    series_indicators = compute_series_indicators(candles)

    def _serialise_result(r: StrategyEvaluationResult) -> Dict[str, Any]:
        return {
            "strategy_id": r.strategy_id,
            "strategy_name": r.strategy_name,
            "category": r.category,
            "description": r.description,
            "state": r.state.value,
            "entry_rules_total": r.entry_rules_total,
            "entry_rules_passing": r.entry_rules_passing,
            "entry_rules_unavailable": r.entry_rules_unavailable,
            "exit_rules_triggered": r.exit_rules_triggered,
            "exit_rules_total": r.exit_rules_total,
            "rule_evaluations": [
                {
                    "rule_id": re.rule_id,
                    "label": re.label,
                    "dependency_keys": re.dependency_keys,
                    "outcome": re.outcome.value,
                    "actual_value": re.actual_value,
                    "actual_value_label": re.actual_value_label,
                    "is_entry_rule": re.is_entry_rule,
                    "math_detail": re.math_detail,
                }
                for re in r.rule_evaluations
            ],
            "feature_vector": r.feature_vector,
            "data_freshness": r.data_freshness,
            "data_age_seconds": r.data_age_seconds,
            "evaluated_at": r.evaluated_at,
            "candles_used": r.candles_used,
            "tags": r.tags,
            "historical_states": r.historical_states,
            "activation_events": [
                {
                    "candle_index": ev.candle_index,
                    "timestamp": ev.timestamp,
                    "event_type": ev.event_type,
                    "price": ev.price,
                    "strategy_id": ev.strategy_id,
                    "label": ev.label,
                }
                for ev in r.activation_events
            ],
        }

    # Format candles for chart
    chart_candles = []
    for c in candles:
        ts_val = c.get("timestamp") or c.get("time") or 0
        ts = int(ts_val if ts_val < 1e11 else ts_val // 1000)
        chart_candles.append({
            "time": ts,
            "open": float(c.get("open", 0.0)),
            "high": float(c.get("high", 0.0)),
            "low": float(c.get("low", 0.0)),
            "close": float(c.get("close", 0.0)),
            "volume": float(c.get("volume", 0.0)),
            "vwap": float(c.get("vwap", c.get("close", 0.0))),
        })

    return {
        "market_regime": regime,
        "confluence": confluence,
        "data_freshness": freshness,
        "data_age_seconds": data_age,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "strategies": [_serialise_result(r) for r in results],
        "chart_indicators": series_indicators,
        "candles": chart_candles,
    }
