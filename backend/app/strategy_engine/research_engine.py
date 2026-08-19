"""
Strategy Engine — Historical Strategy Evaluation & Event Research Engine (Phase 4)
==================================================================================
Provides deterministic, point-in-time historical research replay, outcome measurement,
MAE/MFE excursions, forward observation windows, regime-conditional attribution,
confluence research, and descriptive distribution analytics.

Architecture & Invariants
-------------------------
1. Strategy Activation != Trade != Profitable Signal.
2. Activation at candle T uses ONLY context <= T (strict no-lookahead invariant).
3. Future candles T+1..T+H are used ONLY as observation targets for forward return / MAE / MFE.
4. Activations are state transitions (non-ACTIVE -> ACTIVE); continuous active bars do NOT
   inflate activation event counts.
5. Incomplete observations at dataset end boundaries are marked INCOMPLETE / CENSORED and
   excluded from horizon metrics (never fabricated or assumed as failures).
6. Descriptive statistics only. If sample count N < 5, flagged as LOW_SAMPLE.
"""

import math
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from backend.app.strategy_engine.dsl import (
    StrategyDefinition,
    StrategyRule,
    StrategyState,
    RuleOutcome,
    StrategyCategory,
    StrategyDirection,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY, registry_manager
from backend.app.strategy_engine.dependency_engine import DependencyEngine, normalize_dependency_key
from backend.app.quant_engine.regime import classify_market_regime


# ---------------------------------------------------------------------------
# Research Observation Contracts & Enums
# ---------------------------------------------------------------------------

class ObservationStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    INVALIDATED_EARLY = "INVALIDATED_EARLY"
    CENSORED = "CENSORED"


@dataclass
class ForwardObservation:
    """
    Measurement over a forward observation horizon (e.g. 1, 3, 5, 10, 20 candles).
    """
    horizon_candles: int
    forward_return_pct: Optional[float] = None
    direction_adjusted_return_pct: Optional[float] = None
    mae_pct: Optional[float] = None  # Maximum Adverse Excursion %
    mfe_pct: Optional[float] = None  # Maximum Favorable Excursion %
    is_complete: bool = False
    end_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None


@dataclass
class StrategyResearchObservation:
    """
    A single point-in-time historical strategy activation episode and its subsequent outcomes.
    """
    observation_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    direction: str

    # Activation details (Candle T)
    activation_index: int
    activation_timestamp: int
    activation_price: float

    # Invalidation details
    invalidation_index: Optional[int] = None
    invalidation_timestamp: Optional[int] = None
    invalidation_price: Optional[float] = None
    candles_to_invalidation: Optional[int] = None
    time_to_invalidation_seconds: Optional[float] = None

    # Context at Activation (Candle T)
    regime_at_activation: str = "UNKNOWN"
    regime_evidence: str = ""
    confluence_count: int = 0
    confluent_strategies: List[str] = field(default_factory=list)
    conflicting_strategies: List[str] = field(default_factory=list)

    # Point-in-time snapshots
    rule_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    indicator_snapshot: Dict[str, Any] = field(default_factory=dict)

    # Forward observation outcomes by horizon (e.g. "1", "3", "5", "10", "20")
    forward_observations: Dict[str, ForwardObservation] = field(default_factory=dict)
    observation_status: ObservationStatus = ObservationStatus.COMPLETE


@dataclass
class HorizonSummary:
    """
    Descriptive statistical distribution for a single forward observation horizon.
    """
    horizon: int
    sample_count: int
    mean_return_pct: Optional[float] = None
    median_return_pct: Optional[float] = None
    std_dev_pct: Optional[float] = None
    min_return_pct: Optional[float] = None
    max_return_pct: Optional[float] = None
    positive_return_pct: Optional[float] = None
    negative_return_pct: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    mean_mae_pct: Optional[float] = None
    median_mae_pct: Optional[float] = None
    mean_mfe_pct: Optional[float] = None
    median_mfe_pct: Optional[float] = None
    is_low_sample: bool = False


@dataclass
class StrategyResearchSummary:
    """
    Aggregated historical research dataset and distribution metrics for a strategy.
    """
    strategy_id: str
    strategy_name: str
    category: str
    direction: str
    symbol: str
    timeframe: str
    total_candles_analyzed: int

    # Activation Frequency & Duration Metrics
    total_activations: int
    active_episodes_count: int
    total_active_candles: int
    activation_frequency_pct: float
    avg_episode_duration_candles: float
    median_episode_duration_candles: float
    invalidation_count: int
    invalidation_frequency_pct: float

    # Outcome Distributions across Horizons
    horizons_summary: Dict[str, HorizonSummary] = field(default_factory=dict)

    # Contextual Breakdowns
    regime_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    confluence_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Detailed Observations
    observations: List[StrategyResearchObservation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Point-in-Time Historical Research Engine
# ---------------------------------------------------------------------------

class HistoricalResearchEngine:
    """
    Deterministic evaluation engine that replays historical candle series,
    detects continuous activation episodes, measures forward returns and excursions (MAE/MFE),
    and computes descriptive statistical distributions without lookahead bias.
    """

    DEFAULT_HORIZONS: List[int] = [1, 3, 5, 10, 20]
    MIN_SAMPLE_THRESHOLD: int = 5

    @classmethod
    def evaluate_strategy_research(
        cls,
        candles: List[Dict[str, Any]],
        strategy_id: str,
        symbol: str = "UNKNOWN",
        timeframe: str = "5m",
        horizons: Optional[List[int]] = None,
    ) -> StrategyResearchSummary:
        """
        Runs research evaluation for a single strategy over the provided historical candles.
        """
        all_summaries = cls.evaluate_all_strategies_research(
            candles=candles,
            strategy_ids=[strategy_id],
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
        )
        if strategy_id in all_summaries:
            return all_summaries[strategy_id]
        
        strat = STRATEGY_REGISTRY.get(strategy_id)
        name = strat.name if strat else strategy_id
        cat = (strat.category.value if isinstance(strat.category, StrategyCategory) else str(strat.category)) if strat else "Unknown"
        direction = (strat.direction.value if isinstance(strat.direction, StrategyDirection) else str(strat.direction)) if strat else "BULLISH"
        
        return StrategyResearchSummary(
            strategy_id=strategy_id,
            strategy_name=name,
            category=cat,
            direction=direction,
            symbol=symbol,
            timeframe=timeframe,
            total_candles_analyzed=len(candles) if candles else 0,
            total_activations=0,
            active_episodes_count=0,
            total_active_candles=0,
            activation_frequency_pct=0.0,
            avg_episode_duration_candles=0.0,
            median_episode_duration_candles=0.0,
            invalidation_count=0,
            invalidation_frequency_pct=0.0,
            horizons_summary={},
            regime_breakdown={},
            confluence_breakdown={},
            observations=[],
        )

    @classmethod
    def evaluate_all_strategies_research(
        cls,
        candles: List[Dict[str, Any]],
        strategy_ids: Optional[List[str]] = None,
        symbol: str = "UNKNOWN",
        timeframe: str = "5m",
        horizons: Optional[List[int]] = None,
    ) -> Dict[str, StrategyResearchSummary]:
        """
        Runs point-in-time historical research replay across all or specified strategies.
        Guarantees single calculation of indicator series and strict no-lookahead evaluation.
        """
        target_horizons = sorted(horizons or cls.DEFAULT_HORIZONS)
        n = len(candles) if candles else 0

        target_strategies = STRATEGY_REGISTRY
        if strategy_ids:
            target_strategies = {k: v for k, v in STRATEGY_REGISTRY.items() if k in strategy_ids}

        if n == 0:
            return {}

        df, has_hl, has_vol = DependencyEngine.extract_ohlcv_dataframe(candles)
        if df.empty or "close" not in df.columns:
            return {}

        # 1. Compute canonical dependency context across the entire historical series
        all_req_keys = registry_manager.get_all_required_dependencies(list(target_strategies.keys()))
        dep_ctx = DependencyEngine.compute_context(candles, requested_keys=all_req_keys, symbol=symbol, timeframe=timeframe)

        # 2. Extract price arrays for fast forward horizon evaluation
        close_arr = df["close"].to_numpy()
        high_arr = df["high"].to_numpy() if has_hl else close_arr
        low_arr = df["low"].to_numpy() if has_hl else close_arr

        # Timestamps
        ts_arr: List[int] = []
        for c in candles:
            t = c.get("timestamp") or c.get("time") or 0
            ts_arr.append(int(t if t < 1e11 else t // 1000))

        # 3. Point-in-time rolling state evaluation for each strategy
        # Map: strategy_id -> List of states for all bars 0..n-1
        states_matrix: Dict[str, List[StrategyState]] = {sid: [] for sid in target_strategies}
        rule_evals_matrix: Dict[str, List[List[Dict[str, Any]]]] = {sid: [] for sid in target_strategies}

        for i in range(n):
            # Construct feature vector at bar i
            bar_fv: Dict[str, Any] = {}
            for k, series in dep_ctx.series.items():
                if series and i < len(series):
                    bar_fv[k] = series[i]

            for sid, strat in target_strategies.items():
                if i + 1 < strat.min_candles:
                    states_matrix[sid].append(StrategyState.UNAVAILABLE)
                    rule_evals_matrix[sid].append([])
                    continue

                # Evaluate entry and exit rules
                entry_evals = []
                for r in strat.entry_rules:
                    res = r.condition_fn(bar_fv)
                    outcome = RuleOutcome.PASS if res is True else (RuleOutcome.FAIL if res is False else RuleOutcome.UNAVAILABLE)
                    entry_evals.append({"rule_id": r.rule_id, "label": r.label, "outcome": outcome, "is_entry": True})

                exit_evals = []
                for r in strat.exit_rules:
                    res = r.condition_fn(bar_fv)
                    outcome = RuleOutcome.PASS if res is True else (RuleOutcome.FAIL if res is False else RuleOutcome.UNAVAILABLE)
                    exit_evals.append({"rule_id": r.rule_id, "label": r.label, "outcome": outcome, "is_entry": False})

                # Determine state
                pass_count = sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.PASS)
                unavail_count = sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.UNAVAILABLE)
                total_entry = len(entry_evals)
                exit_triggered = any(e["outcome"] == RuleOutcome.PASS for e in exit_evals)

                if total_entry == 0:
                    state = StrategyState.UNAVAILABLE
                elif unavail_count > (total_entry / 2.0):
                    state = StrategyState.UNAVAILABLE
                elif pass_count == total_entry:
                    state = StrategyState.CONFLICTED if exit_triggered else StrategyState.ACTIVE
                elif pass_count >= math.ceil(total_entry / 2.0):
                    state = StrategyState.PARTIAL
                else:
                    state = StrategyState.INACTIVE

                states_matrix[sid].append(state)
                rule_evals_matrix[sid].append(entry_evals + exit_evals)

        # 4. Extract continuous activation episodes and build observations per strategy
        summaries: Dict[str, StrategyResearchSummary] = {}

        for sid, strat in target_strategies.items():
            states = states_matrix[sid]
            strat_direction = (
                strat.direction.value if isinstance(strat.direction, StrategyDirection)
                else str(strat.direction)
            ).upper()

            observations: List[StrategyResearchObservation] = []
            episodes_durations: List[int] = []

            in_active_episode = False
            current_obs: Optional[StrategyResearchObservation] = None
            current_episode_start = 0
            total_active_bars = 0
            invalidation_events_count = 0

            for i in range(n):
                st = states[i]
                prev_st = states[i - 1] if i > 0 else None

                if st == StrategyState.ACTIVE:
                    total_active_bars += 1

                # State Transition: Start of a new activation episode
                if st == StrategyState.ACTIVE and prev_st != StrategyState.ACTIVE:
                    in_active_episode = True
                    current_episode_start = i

                    # Capture regime at activation candle i
                    sub_df = df.iloc[: i + 1]
                    regime_res = classify_market_regime(sub_df)
                    regime_label = regime_res.get("regime", "UNKNOWN")
                    regime_ev = regime_res.get("evidence", "")

                    # Capture confluence at activation candle i
                    confluent_list: List[str] = []
                    conflicted_list: List[str] = []
                    for other_sid in target_strategies:
                        if other_sid != sid and i < len(states_matrix[other_sid]):
                            other_st = states_matrix[other_sid][i]
                            if other_st == StrategyState.ACTIVE:
                                confluent_list.append(other_sid)
                            elif other_st == StrategyState.CONFLICTED:
                                conflicted_list.append(other_sid)

                    # Snapshot point-in-time feature values
                    fv_snap: Dict[str, Any] = {}
                    for k, s_arr in dep_ctx.series.items():
                        if s_arr and i < len(s_arr) and s_arr[i] is not None:
                            fv_snap[k] = round(s_arr[i], 4)

                    obs_id = f"{sid}_{symbol}_{timeframe}_{ts_arr[i]}_{i}"
                    current_obs = StrategyResearchObservation(
                        observation_id=obs_id,
                        strategy_id=sid,
                        strategy_version=strat.version,
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=strat_direction,
                        activation_index=i,
                        activation_timestamp=ts_arr[i],
                        activation_price=float(close_arr[i]),
                        regime_at_activation=regime_label,
                        regime_evidence=regime_ev,
                        confluence_count=len(confluent_list),
                        confluent_strategies=confluent_list,
                        conflicting_strategies=conflicted_list,
                        rule_snapshot=rule_evals_matrix[sid][i],
                        indicator_snapshot=fv_snap,
                    )

                # State Transition: Invalidation of an active episode
                elif in_active_episode and st != StrategyState.ACTIVE:
                    in_active_episode = False
                    duration = i - current_episode_start
                    episodes_durations.append(duration)
                    invalidation_events_count += 1

                    if current_obs:
                        current_obs.invalidation_index = i
                        current_obs.invalidation_timestamp = ts_arr[i]
                        current_obs.invalidation_price = float(close_arr[i])
                        current_obs.candles_to_invalidation = duration
                        current_obs.time_to_invalidation_seconds = float(ts_arr[i] - current_obs.activation_timestamp)
                        current_obs.observation_status = ObservationStatus.INVALIDATED_EARLY
                        observations.append(current_obs)
                        current_obs = None

            # If an episode is still active at the end of the dataset
            if in_active_episode and current_obs:
                duration = n - current_episode_start
                episodes_durations.append(duration)
                current_obs.observation_status = ObservationStatus.CENSORED
                observations.append(current_obs)
                current_obs = None

            # 5. Measure Forward Observations (Returns, MAE, MFE) for each activation episode
            for obs in observations:
                act_idx = obs.activation_index
                p0 = obs.activation_price

                for h in target_horizons:
                    h_key = str(h)
                    target_idx = act_idx + h

                    # Dataset End Boundary Check: Incomplete horizon
                    if target_idx >= n:
                        obs.forward_observations[h_key] = ForwardObservation(
                            horizon_candles=h,
                            is_complete=False,
                        )
                        continue

                    # Complete horizon observation
                    pt = float(close_arr[target_idx])
                    raw_ret = ((pt - p0) / p0) * 100.0 if p0 > 0 else 0.0

                    # Direction adjustment
                    dir_ret = raw_ret if strat_direction == "BULLISH" else -raw_ret

                    # Future price excursions over the window [act_idx + 1 .. target_idx]
                    future_highs = high_arr[act_idx + 1 : target_idx + 1]
                    future_lows = low_arr[act_idx + 1 : target_idx + 1]

                    min_p = float(np.min(future_lows)) if len(future_lows) > 0 else pt
                    max_p = float(np.max(future_highs)) if len(future_highs) > 0 else pt

                    if strat_direction == "BULLISH":
                        mae = ((min_p - p0) / p0) * 100.0 if p0 > 0 else 0.0  # Typically negative or 0
                        mfe = ((max_p - p0) / p0) * 100.0 if p0 > 0 else 0.0  # Typically positive or 0
                    else:  # BEARISH
                        mae = ((p0 - max_p) / p0) * 100.0 if p0 > 0 else 0.0  # Adverse upward excursion
                        mfe = ((p0 - min_p) / p0) * 100.0 if p0 > 0 else 0.0  # Favorable downward excursion

                    obs.forward_observations[h_key] = ForwardObservation(
                        horizon_candles=h,
                        forward_return_pct=round(raw_ret, 3),
                        direction_adjusted_return_pct=round(dir_ret, 3),
                        mae_pct=round(mae, 3),
                        mfe_pct=round(mfe, 3),
                        is_complete=True,
                        end_price=round(pt, 2),
                        min_price=round(min_p, 2),
                        max_price=round(max_p, 2),
                    )

            # 6. Build Summary Aggregations
            summary = cls._aggregate_summary(
                strat=strat,
                symbol=symbol,
                timeframe=timeframe,
                total_candles=n,
                observations=observations,
                episodes_durations=episodes_durations,
                total_active_bars=total_active_bars,
                invalidation_count=invalidation_events_count,
                horizons=target_horizons,
            )
            summaries[sid] = summary

        return summaries

    @classmethod
    def _aggregate_summary(
        cls,
        strat: StrategyDefinition,
        symbol: str,
        timeframe: str,
        total_candles: int,
        observations: List[StrategyResearchObservation],
        episodes_durations: List[int],
        total_active_bars: int,
        invalidation_count: int,
        horizons: List[int],
    ) -> StrategyResearchSummary:
        """
        Computes distribution metrics, percentiles, regime breakdowns, and confluence analytics.
        """
        n_obs = len(observations)
        strat_cat = strat.category.value if isinstance(strat.category, StrategyCategory) else str(strat.category)
        strat_dir = (
            strat.direction.value if isinstance(strat.direction, StrategyDirection)
            else str(strat.direction)
        ).upper()

        avg_duration = float(np.mean(episodes_durations)) if episodes_durations else 0.0
        median_duration = float(np.median(episodes_durations)) if episodes_durations else 0.0
        act_freq_pct = (total_active_bars / total_candles * 100.0) if total_candles > 0 else 0.0
        inv_freq_pct = (invalidation_count / n_obs * 100.0) if n_obs > 0 else 0.0

        # Horizons Summaries
        horizons_summary: Dict[str, HorizonSummary] = {}
        for h in horizons:
            h_key = str(h)
            returns: List[float] = []
            maes: List[float] = []
            mfes: List[float] = []

            for obs in observations:
                fo = obs.forward_observations.get(h_key)
                if fo and fo.is_complete and fo.direction_adjusted_return_pct is not None:
                    returns.append(fo.direction_adjusted_return_pct)
                    if fo.mae_pct is not None:
                        maes.append(fo.mae_pct)
                    if fo.mfe_pct is not None:
                        mfes.append(fo.mfe_pct)

            count = len(returns)
            is_low = count < cls.MIN_SAMPLE_THRESHOLD

            if count > 0:
                mean_r = float(np.mean(returns))
                med_r = float(np.median(returns))
                std_r = float(np.std(returns)) if count > 1 else 0.0
                min_r = float(np.min(returns))
                max_r = float(np.max(returns))

                pos_count = sum(1 for r in returns if r > 0)
                neg_count = sum(1 for r in returns if r < 0)
                pos_freq = (pos_count / count) * 100.0
                neg_freq = (neg_count / count) * 100.0

                p10 = float(np.percentile(returns, 10))
                p25 = float(np.percentile(returns, 25))
                p50 = float(np.percentile(returns, 50))
                p75 = float(np.percentile(returns, 75))
                p90 = float(np.percentile(returns, 90))

                mean_mae = float(np.mean(maes)) if maes else None
                med_mae = float(np.median(maes)) if maes else None
                mean_mfe = float(np.mean(mfes)) if mfes else None
                med_mfe = float(np.median(mfes)) if mfes else None

                horizons_summary[h_key] = HorizonSummary(
                    horizon=h,
                    sample_count=count,
                    mean_return_pct=round(mean_r, 3),
                    median_return_pct=round(med_r, 3),
                    std_dev_pct=round(std_r, 3),
                    min_return_pct=round(min_r, 3),
                    max_return_pct=round(max_r, 3),
                    positive_return_pct=round(pos_freq, 1),
                    negative_return_pct=round(neg_freq, 1),
                    p10=round(p10, 3),
                    p25=round(p25, 3),
                    p50=round(p50, 3),
                    p75=round(p75, 3),
                    p90=round(p90, 3),
                    mean_mae_pct=round(mean_mae, 3) if mean_mae is not None else None,
                    median_mae_pct=round(med_mae, 3) if med_mae is not None else None,
                    mean_mfe_pct=round(mean_mfe, 3) if mean_mfe is not None else None,
                    median_mfe_pct=round(med_mfe, 3) if med_mfe is not None else None,
                    is_low_sample=is_low,
                )
            else:
                horizons_summary[h_key] = HorizonSummary(
                    horizon=h,
                    sample_count=0,
                    is_low_sample=True,
                )

        # Regime-Conditional Breakdown (using 5-candle default forward return as representative horizon)
        regimes_map: Dict[str, List[float]] = {}
        for obs in observations:
            reg = obs.regime_at_activation
            fo5 = obs.forward_observations.get("5")
            if fo5 and fo5.is_complete and fo5.direction_adjusted_return_pct is not None:
                regimes_map.setdefault(reg, []).append(fo5.direction_adjusted_return_pct)

        regime_breakdown: Dict[str, Dict[str, Any]] = {}
        for reg_k, r_vals in regimes_map.items():
            r_cnt = len(r_vals)
            regime_breakdown[reg_k] = {
                "activations": r_cnt,
                "median_5candle_return": round(float(np.median(r_vals)), 3) if r_cnt > 0 else 0.0,
                "mean_5candle_return": round(float(np.mean(r_vals)), 3) if r_cnt > 0 else 0.0,
                "positive_frequency_pct": round((sum(1 for v in r_vals if v > 0) / r_cnt * 100.0), 1) if r_cnt > 0 else 0.0,
                "is_low_sample": r_cnt < cls.MIN_SAMPLE_THRESHOLD,
            }

        # Confluence-Conditional Breakdown (using 5-candle forward return)
        confluence_map: Dict[str, List[float]] = {}
        for obs in observations:
            c_tier = "1 strategy (Solo)" if obs.confluence_count == 0 else (
                "2 strategies" if obs.confluence_count == 1 else (
                    "3 strategies" if obs.confluence_count == 2 else "4+ strategies"
                )
            )
            fo5 = obs.forward_observations.get("5")
            if fo5 and fo5.is_complete and fo5.direction_adjusted_return_pct is not None:
                confluence_map.setdefault(c_tier, []).append(fo5.direction_adjusted_return_pct)

        confluence_breakdown: Dict[str, Dict[str, Any]] = {}
        for c_tier, c_vals in confluence_map.items():
            c_cnt = len(c_vals)
            confluence_breakdown[c_tier] = {
                "activations": c_cnt,
                "median_5candle_return": round(float(np.median(c_vals)), 3) if c_cnt > 0 else 0.0,
                "positive_frequency_pct": round((sum(1 for v in c_vals if v > 0) / c_cnt * 100.0), 1) if c_cnt > 0 else 0.0,
                "is_low_sample": c_cnt < cls.MIN_SAMPLE_THRESHOLD,
            }

        return StrategyResearchSummary(
            strategy_id=strat.strategy_id,
            strategy_name=strat.name,
            category=strat_cat,
            direction=strat_dir,
            symbol=symbol,
            timeframe=timeframe,
            total_candles_analyzed=total_candles,
            total_activations=n_obs,
            active_episodes_count=len(episodes_durations),
            total_active_candles=total_active_bars,
            activation_frequency_pct=round(act_freq_pct, 2),
            avg_episode_duration_candles=round(avg_duration, 1),
            median_episode_duration_candles=round(median_duration, 1),
            invalidation_count=invalidation_count,
            invalidation_frequency_pct=round(inv_freq_pct, 1),
            horizons_summary=horizons_summary,
            regime_breakdown=regime_breakdown,
            confluence_breakdown=confluence_breakdown,
            observations=observations,
        )


# Global research engine instance
historical_research_engine = HistoricalResearchEngine()
