"""
Strategy Lab — Deterministic Rule Evaluator
============================================
Computes the feature vector from OHLCV candle history, evaluates each
strategy rule, and emits a StrategyEvaluationResult with a verifiable
state (ACTIVE / PARTIAL / INACTIVE / CONFLICTED / UNAVAILABLE / STALE).

Design invariants
-----------------
- Never fabricates indicator values. If computation is impossible
  (insufficient candles, missing columns, NaN), the value stays None.
- UNAVAILABLE propagates: a rule whose dependency value is None returns
  RuleOutcome.UNAVAILABLE — it does NOT count as FAIL.
- Strategy state degrades as UNAVAILABLE rule count grows.
- Data freshness is re-evaluated from the last candle timestamp. Stale
  data forces the strategy state to STALE regardless of rule outcomes.
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
    actual_value: Optional[float]     # The primary indicator value (display only)
    actual_value_label: str           # Formatted for UI, e.g. "RSI = 62.3"
    is_entry_rule: bool


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
    evaluated_at: str = ""
    candles_used: int = 0
    tags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Feature Vector Computation
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    """Return float or None for NaN / None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def compute_feature_vector(candles: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Build a flat feature vector Dict from OHLCV candles.
    All values are float or None. Never returns NaN.
    """
    if not candles or len(candles) < 5:
        return {}

    df = pd.DataFrame(candles)

    # Validate required columns
    if "close" not in df.columns:
        return {}

    close = df["close"].astype(float)
    has_hlv = all(c in df.columns for c in ["high", "low", "volume"])
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series([0.0] * len(df))

    n = len(close)
    fv: Dict[str, Optional[float]] = {}

    # Current close
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


# ---------------------------------------------------------------------------
# Data Freshness from last candle timestamp
# ---------------------------------------------------------------------------

def _evaluate_freshness(candles: List[Dict[str, Any]], is_live_feed: bool) -> str:
    if not candles:
        return "UNAVAILABLE"
    last = candles[-1]
    ts_raw = last.get("timestamp") or last.get("time")
    if ts_raw is None:
        return "UNAVAILABLE"
    try:
        ts = float(ts_raw)
        if ts <= 0:
            return "UNAVAILABLE"
        age = time.time() - ts
        if age < 0:
            return "LIVE" if is_live_feed else "RECENT"
        if is_live_feed and age <= 60.0:
            return "LIVE"
        elif age <= 300.0:
            return "RECENT"
        elif age <= 86400.0:
            return "STALE"
        else:
            return "UNAVAILABLE"
    except (TypeError, ValueError):
        return "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Rule Evaluator
# ---------------------------------------------------------------------------

def _format_value(fv: Dict, keys: List[str]) -> str:
    """Return a short string showing the primary indicator value for the UI."""
    if not keys:
        return "N/A"
    primary = keys[0]
    val = fv.get(primary)
    if val is None:
        return "UNAVAILABLE"
    try:
        return f"{float(val):.2f}"
    except (TypeError, ValueError):
        return "UNAVAILABLE"


def _evaluate_rule(rule: StrategyRule, fv: Dict, is_entry: bool) -> RuleEvaluation:
    """
    Evaluate a single rule against the feature vector.
    Returns RuleEvaluation with outcome PASS / FAIL / UNAVAILABLE.
    """
    # Check all dependency keys are present & non-None
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

    return RuleEvaluation(
        rule_id=rule.rule_id,
        label=rule.label,
        dependency_keys=rule.dependency_keys,
        outcome=outcome,
        actual_value=actual_val,
        actual_value_label=label_str,
        is_entry_rule=is_entry,
    )


# ---------------------------------------------------------------------------
# Strategy State Determination
# ---------------------------------------------------------------------------

def _determine_state(
    entry_evals: List[RuleEvaluation],
    exit_evals: List[RuleEvaluation],
    freshness: str,
) -> StrategyState:
    if freshness in ("STALE", "UNAVAILABLE"):
        return StrategyState.STALE

    n_entry = len(entry_evals)
    if n_entry == 0:
        return StrategyState.UNAVAILABLE

    n_pass = sum(1 for r in entry_evals if r.outcome == RuleOutcome.PASS)
    n_fail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.FAIL)
    n_unavail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.UNAVAILABLE)

    n_exit_triggered = sum(1 for r in exit_evals if r.outcome == RuleOutcome.PASS)

    # > 50% unavailable → can't assess
    if n_unavail > n_entry / 2:
        return StrategyState.UNAVAILABLE

    # All entry rules pass → ACTIVE
    if n_pass == n_entry:
        if n_exit_triggered > 0:
            return StrategyState.CONFLICTED
        return StrategyState.ACTIVE

    # ≥ 50% pass (excluding unavailable) → PARTIAL
    computable = n_pass + n_fail
    if computable > 0 and n_pass / computable >= 0.5:
        return StrategyState.PARTIAL

    return StrategyState.INACTIVE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_all_strategies(
    candles: List[Dict[str, Any]],
    is_live_feed: bool = False,
    strategy_ids: Optional[List[str]] = None,
) -> List[StrategyEvaluationResult]:
    """
    Evaluate every strategy in the registry against the provided candle history.

    Parameters
    ----------
    candles      : OHLCV candle list (dicts with 'open', 'high', 'low', 'close', 'volume')
    is_live_feed : True if the data comes from a live WebSocket feed
    strategy_ids : Optional subset of strategy IDs to evaluate (None = all)

    Returns
    -------
    List of StrategyEvaluationResult, one per strategy.
    """
    freshness = _evaluate_freshness(candles, is_live_feed)
    fv = compute_feature_vector(candles) if candles else {}
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results: List[StrategyEvaluationResult] = []

    registry = STRATEGY_REGISTRY
    if strategy_ids:
        registry = {k: v for k, v in STRATEGY_REGISTRY.items() if k in strategy_ids}

    for sid, strat in registry.items():
        n = len(candles) if candles else 0

        # If not enough candles for this strategy, mark UNAVAILABLE
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
                evaluated_at=now_str,
                candles_used=n,
                tags=strat.tags,
            ))
            continue

        # Evaluate entry rules
        entry_evals = [_evaluate_rule(r, fv, is_entry=True) for r in strat.entry_rules]
        # Evaluate exit rules
        exit_evals = [_evaluate_rule(r, fv, is_entry=False) for r in strat.exit_rules]

        state = _determine_state(entry_evals, exit_evals, freshness)

        n_pass = sum(1 for r in entry_evals if r.outcome == RuleOutcome.PASS)
        n_unavail = sum(1 for r in entry_evals if r.outcome == RuleOutcome.UNAVAILABLE)
        n_exit = sum(1 for r in exit_evals if r.outcome == RuleOutcome.PASS)

        # Expose a cleaned, serialisable feature vector (exclude None values for brevity)
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
            evaluated_at=now_str,
            candles_used=n,
            tags=strat.tags,
        ))

    return results
