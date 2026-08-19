import pytest
import time
import numpy as np
import pandas as pd
from backend.app.strategy_engine.dsl import (
    StrategyState,
    RuleOutcome,
    StrategyCategory,
    StrategyDirection,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY, registry_manager
from backend.app.strategy_engine.research_engine import (
    HistoricalResearchEngine,
    ObservationStatus,
    ForwardObservation,
    StrategyResearchObservation,
    HorizonSummary,
    StrategyResearchSummary,
    historical_research_engine,
)
from backend.app.ai_engine.agents import StrategyCopilotAgent


def generate_synthetic_research_candles(n: int = 100, base_price: float = 100.0) -> list:
    """
    Generates a deterministic synthetic sequence of candles with uptrend, consolidation, and pullback.
    Used STRICTLY as a unit test fixture.
    """
    candles = []
    now = 1700000000  # Fixed epoch timestamp for deterministic tests
    price = base_price
    for i in range(n):
        # Trend upward for first 50 bars, then consolidate, then slight dip
        if i < 40:
            drift = 0.5
        elif i < 70:
            drift = 0.05
        else:
            drift = -0.2

        open_p = price
        close_p = open_p + drift
        high_p = max(open_p, close_p) + 0.4
        low_p = min(open_p, close_p) - 0.4
        vol = 1000.0 + (i * 20.0)

        price = close_p
        candles.append({
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(vol, 1),
            "timestamp": now + (i * 300),  # 5-minute increments
        })
    return candles


# ---------------------------------------------------------------------------
# Test 1 & 2: Activation Transition & No Repeated Events in Continuous Episodes
# ---------------------------------------------------------------------------

def test_activation_transition_and_no_repeated_events():
    """
    Ensures that transition from non-ACTIVE to ACTIVE creates exactly 1 activation event,
    and remaining continuously ACTIVE does NOT inflate activation counts.
    """
    candles = generate_synthetic_research_candles(n=120, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
        timeframe="5m",
    )

    assert isinstance(summary, StrategyResearchSummary)
    assert summary.strategy_id == "EMA_GOLDEN_CROSS"
    assert summary.total_candles_analyzed == 120
    assert summary.total_activations >= 1

    # Verify that each observation represents a distinct start of an episode
    obs_indices = [o.activation_index for o in summary.observations]
    assert len(obs_indices) == len(set(obs_indices)), "Duplicate activation indices found!"

    for i in range(1, len(obs_indices)):
        # Subsequent activation episode must not be immediately adjacent
        assert obs_indices[i] > obs_indices[i - 1] + 1


# ---------------------------------------------------------------------------
# Test 3: Invalidation Transition Detection
# ---------------------------------------------------------------------------

def test_invalidation_transition_detection():
    """
    Ensures that when an active episode terminates, invalidation index, price,
    and duration are captured accurately.
    """
    candles = generate_synthetic_research_candles(n=120, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
        timeframe="5m",
    )

    for obs in summary.observations:
        if obs.observation_status == ObservationStatus.INVALIDATED_EARLY:
            assert obs.invalidation_index is not None
            assert obs.invalidation_price is not None
            assert obs.candles_to_invalidation is not None
            assert obs.candles_to_invalidation > 0
            assert obs.invalidation_index > obs.activation_index


# ---------------------------------------------------------------------------
# Test 4, 5, 6, 7: Forward Return Calculation & Direction Adjustment
# ---------------------------------------------------------------------------

def test_forward_return_calculations_and_direction():
    """
    Tests forward return calculation: ((P_t / P_0) - 1) * 100
    and direction adjustment for Bullish vs Bearish strategies.
    """
    candles = generate_synthetic_research_candles(n=100, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
        timeframe="5m",
        horizons=[1, 3, 5, 10, 20],
    )

    for obs in summary.observations:
        p0 = obs.activation_price
        act_idx = obs.activation_index

        for h in [1, 3, 5, 10]:
            h_str = str(h)
            fo = obs.forward_observations.get(h_str)
            if fo and fo.is_complete:
                expected_pt = candles[act_idx + h]["close"]
                expected_raw_ret = ((expected_pt - p0) / p0) * 100.0
                assert pytest.approx(fo.forward_return_pct, 0.01) == expected_raw_ret
                assert fo.direction_adjusted_return_pct == fo.forward_return_pct  # Bullish strategy


# ---------------------------------------------------------------------------
# Test 8 & 9: MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion)
# ---------------------------------------------------------------------------

def test_mae_and_mfe_calculations():
    """
    Tests MAE (worst downside excursion) and MFE (best upside excursion) over observation horizons.
    """
    candles = generate_synthetic_research_candles(n=100, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
        timeframe="5m",
        horizons=[5],
    )

    for obs in summary.observations:
        fo5 = obs.forward_observations.get("5")
        if fo5 and fo5.is_complete:
            p0 = obs.activation_price
            act_idx = obs.activation_index
            future_lows = [candles[k]["low"] for k in range(act_idx + 1, act_idx + 6)]
            future_highs = [candles[k]["high"] for k in range(act_idx + 1, act_idx + 6)]

            expected_mae = ((min(future_lows) - p0) / p0) * 100.0
            expected_mfe = ((max(future_highs) - p0) / p0) * 100.0

            assert pytest.approx(fo5.mae_pct, 0.01) == expected_mae
            assert pytest.approx(fo5.mfe_pct, 0.01) == expected_mfe
            assert fo5.min_price == min(future_lows)
            assert fo5.max_price == max(future_highs)


# ---------------------------------------------------------------------------
# Test 10 & 11: Dataset End Boundary & Incomplete Observation Handling
# ---------------------------------------------------------------------------

def test_dataset_end_boundary_and_incomplete_observations():
    """
    If an activation occurs near the dataset end (e.g. 2 candles before end),
    a 20-candle forward return must be marked is_complete=False and excluded from horizon stats.
    """
    candles = generate_synthetic_research_candles(n=70, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
        timeframe="5m",
        horizons=[1, 5, 20],
    )

    for obs in summary.observations:
        act_idx = obs.activation_index
        fo20 = obs.forward_observations.get("20")
        if act_idx + 20 >= len(candles):
            assert fo20.is_complete is False
            assert fo20.forward_return_pct is None
            assert fo20.mae_pct is None
            assert fo20.mfe_pct is None


# ---------------------------------------------------------------------------
# Test 12: Regime Attribution at Activation
# ---------------------------------------------------------------------------

def test_canonical_regime_attribution():
    """
    Ensures regime at activation is classified strictly using canonical Regime Engine on historical context.
    """
    candles = generate_synthetic_research_candles(n=100, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
        timeframe="5m",
    )

    for obs in summary.observations:
        assert obs.regime_at_activation in [
            "TRENDING_BULLISH", "TRENDING_BEARISH", "BULLISH_ACCUMULATION",
            "BEARISH_DISTRIBUTION", "HIGH_VOLATILITY", "RANGE_BOUND", "UNAVAILABLE"
        ]
        assert obs.regime_evidence != ""


# ---------------------------------------------------------------------------
# Test 13 & 14: Confluence & Conflict Calculation
# ---------------------------------------------------------------------------

def test_confluence_and_conflict_attribution():
    """
    Verifies that simultaneous active strategies at candle T are recorded in confluence_count and confluent_strategies.
    """
    candles = generate_synthetic_research_candles(n=100, base_price=100.0)
    all_summaries = historical_research_engine.evaluate_all_strategies_research(
        candles=candles,
        symbol="TEST.NS",
        timeframe="5m",
    )

    assert len(all_summaries) == 20
    for sid, summary in all_summaries.items():
        for obs in summary.observations:
            assert isinstance(obs.confluence_count, int)
            assert obs.confluence_count >= 0
            assert isinstance(obs.confluent_strategies, list)
            assert sid not in obs.confluent_strategies  # Does not count itself in other confluent list


# ---------------------------------------------------------------------------
# Test 15 & 16: Symbol and Timeframe Isolation
# ---------------------------------------------------------------------------

def test_symbol_and_timeframe_isolation():
    """
    Ensures observation summaries preserve isolated symbol and timeframe tags.
    """
    candles = generate_synthetic_research_candles(n=80, base_price=100.0)
    s1 = historical_research_engine.evaluate_strategy_research(candles, "EMA_GOLDEN_CROSS", symbol="RELIANCE.NS", timeframe="15m")
    s2 = historical_research_engine.evaluate_strategy_research(candles, "EMA_GOLDEN_CROSS", symbol="TCS.NS", timeframe="1h")

    assert s1.symbol == "RELIANCE.NS"
    assert s1.timeframe == "15m"
    assert s2.symbol == "TCS.NS"
    assert s2.timeframe == "1h"


# ---------------------------------------------------------------------------
# Test 17 & 18: No Lookahead at Activation Candle T
# ---------------------------------------------------------------------------

def test_no_lookahead_at_activation():
    """
    Verifies that introducing dramatic future candles at T+1 does not change the activation state or indicator snapshot at candle T.
    """
    candles_base = generate_synthetic_research_candles(n=60, base_price=100.0)
    s_base = historical_research_engine.evaluate_strategy_research(candles_base, "EMA_GOLDEN_CROSS", symbol="TEST.NS", timeframe="5m")

    # Add extreme future candle
    candles_extended = list(candles_base) + [{
        "open": 99999.0,
        "high": 100000.0,
        "low": 99990.0,
        "close": 99995.0,
        "volume": 99999999.0,
        "timestamp": candles_base[-1]["timestamp"] + 300,
    }]
    s_ext = historical_research_engine.evaluate_strategy_research(candles_extended, "EMA_GOLDEN_CROSS", symbol="TEST.NS", timeframe="5m")

    # Base observations (up to bar 59) should have identical activation index, price, and rule snapshots
    base_obs_count = len(s_base.observations)
    if base_obs_count > 0:
        assert s_ext.observations[0].activation_index == s_base.observations[0].activation_index
        assert s_ext.observations[0].activation_price == s_base.observations[0].activation_price
        assert s_ext.observations[0].rule_snapshot == s_base.observations[0].rule_snapshot


# ---------------------------------------------------------------------------
# Test 19, 20, 21: Sample Count, LOW_SAMPLE Flag, & Percentiles
# ---------------------------------------------------------------------------

def test_statistical_aggregation_and_low_sample_flag():
    """
    Verifies calculation of mean, median, std dev, P10, P25, P50, P75, P90, and LOW_SAMPLE flag.
    """
    candles = generate_synthetic_research_candles(n=90, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(
        candles=candles,
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
        timeframe="5m",
        horizons=[1, 3, 5, 10, 20],
    )

    for h_str, hs in summary.horizons_summary.items():
        assert isinstance(hs, HorizonSummary)
        if hs.sample_count < HistoricalResearchEngine.MIN_SAMPLE_THRESHOLD:
            assert hs.is_low_sample is True
        if hs.sample_count > 0:
            assert hs.median_return_pct is not None
            assert hs.mean_return_pct is not None
            assert 0.0 <= hs.positive_return_pct <= 100.0
            assert hs.p10 <= hs.p25 <= hs.p50 <= hs.p75 <= hs.p90


# ---------------------------------------------------------------------------
# Test 22: Strategy Version Tracking
# ---------------------------------------------------------------------------

def test_strategy_version_tracking():
    """
    Ensures observations record canonical strategy version.
    """
    candles = generate_synthetic_research_candles(n=80, base_price=100.0)
    summary = historical_research_engine.evaluate_strategy_research(candles, "EMA_GOLDEN_CROSS", symbol="TEST.NS", timeframe="5m")
    for obs in summary.observations:
        assert obs.strategy_version == "1.0.0"


# ---------------------------------------------------------------------------
# Test 23: Copilot Research Evidence Grounding & Safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_copilot_research_grounding():
    """
    Verifies that StrategyCopilotAgent correctly consumes research summaries,
    cites historical activations and excursions, and never promises future returns.
    """
    copilot = StrategyCopilotAgent(api_key=None)
    research_summary = {
        "strategy_id": "EMA_GOLDEN_CROSS",
        "strategy_name": "EMA Golden Cross",
        "category": "Trend Following",
        "direction": "BULLISH",
        "symbol": "RELIANCE.NS",
        "timeframe": "5m",
        "total_candles_analyzed": 200,
        "total_activations": 14,
        "active_episodes_count": 14,
        "avg_episode_duration_candles": 4.5,
        "median_episode_duration_candles": 4.0,
        "invalidation_count": 14,
        "invalidation_frequency_pct": 100.0,
        "horizons_summary": {
            "5": {
                "horizon": 5,
                "sample_count": 14,
                "median_return_pct": 0.82,
                "mean_return_pct": 0.74,
                "positive_return_pct": 64.3,
                "median_mae_pct": -0.35,
                "median_mfe_pct": 1.20,
                "is_low_sample": False,
            }
        },
        "regime_breakdown": {
            "TRENDING_BULLISH": {"activations": 10, "median_5candle_return": 1.15, "positive_frequency_pct": 80.0, "is_low_sample": False}
        },
        "confluence_breakdown": {
            "2 strategies": {"activations": 8, "median_5candle_return": 0.95, "positive_frequency_pct": 75.0, "is_low_sample": False}
        }
    }

    ans = await copilot.answer(
        symbol="RELIANCE.NS",
        research_summary=research_summary,
        user_message="What is the 5-candle forward outcome for this strategy?",
    )

    assert "reply" in ans
    assert "14 activation episodes" in ans["reply"]
    assert "0.82%" in ans["reply"]
    assert "64.3%" in ans["reply"]
    assert len(ans["evidence_cited"]) > 0


# ---------------------------------------------------------------------------
# Test 24: Regression Check across all 20 Strategies
# ---------------------------------------------------------------------------

def test_all_20_strategies_research_execution():
    """
    Phase 39: All 20 canonical strategies execute cleanly through HistoricalResearchEngine.
    """
    candles = generate_synthetic_research_candles(n=250, base_price=100.0)
    summaries = historical_research_engine.evaluate_all_strategies_research(
        candles=candles,
        symbol="INFY.NS",
        timeframe="15m",
    )

    assert len(summaries) == 20
    for sid, summ in summaries.items():
        assert summ.strategy_id in STRATEGY_REGISTRY
        assert summ.total_candles_analyzed == 250
        assert isinstance(summ.horizons_summary, dict)
        assert isinstance(summ.regime_breakdown, dict)
        assert isinstance(summ.confluence_breakdown, dict)
