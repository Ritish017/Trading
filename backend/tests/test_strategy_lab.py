import pytest
import time
from backend.app.strategy_engine.dsl import StrategyState, RuleOutcome
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.evaluator import (
    evaluate_all_strategies,
    compute_feature_vector,
    compute_series_indicators,
    compute_strategy_confluence,
    evaluate_strategies_observatory,
    _evaluate_freshness,
)
from backend.app.ai_engine.agents import StrategyCopilotAgent

def test_strategy_registry_completeness():
    assert len(STRATEGY_REGISTRY) >= 8
    for sid, strat in STRATEGY_REGISTRY.items():
        assert strat.strategy_id == sid
        assert len(strat.entry_rules) > 0
        assert strat.min_candles >= 10

def test_evaluator_insufficient_candles():
    candles = [
        {"open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 1000, "timestamp": time.time()}
        for i in range(5)
    ]
    results = evaluate_all_strategies(candles)
    for res in results:
        assert res.state == StrategyState.UNAVAILABLE
        assert res.entry_rules_unavailable > 0

def test_evaluator_sufficient_candles():
    now = time.time()
    candles = [
        {
            "open": 100.0 + (i * 0.5),
            "high": 101.0 + (i * 0.5),
            "low": 99.5 + (i * 0.5),
            "close": 100.8 + (i * 0.5),
            "volume": 5000 + (i * 50),
            "timestamp": now - (60 - i) * 60,
        }
        for i in range(60)
    ]
    results = evaluate_all_strategies(candles, is_live_feed=True)
    assert len(results) == len(STRATEGY_REGISTRY)
    for res in results:
        assert res.candles_used == 60
        assert res.state in [StrategyState.ACTIVE, StrategyState.PARTIAL, StrategyState.INACTIVE, StrategyState.CONFLICTED]

def test_freshness_separation_stale_data():
    """
    Ensures that stale data produces data_freshness='STALE' while the strategy
    state remains a purely mathematical outcome (e.g. ACTIVE, INACTIVE, etc.),
    verifying strict separation of data quality and mathematical rule evaluation.
    """
    seven_hours_ago = time.time() - (7 * 3600 + 12 * 60)
    candles = [
        {
            "open": 100.0 + (i * 0.5),
            "high": 101.0 + (i * 0.5),
            "low": 99.5 + (i * 0.5),
            "close": 100.8 + (i * 0.5),
            "volume": 5000 + (i * 50),
            "timestamp": seven_hours_ago + (i * 60),
        }
        for i in range(60)
    ]
    freshness, age = _evaluate_freshness(candles, is_live_feed=False)
    assert freshness == "STALE"
    assert age > 3600

    results = evaluate_all_strategies(candles, is_live_feed=False)
    for res in results:
        assert res.data_freshness == "STALE"
        # Strategy state is mathematical, NOT 'STALE'
        assert res.state in [StrategyState.ACTIVE, StrategyState.PARTIAL, StrategyState.INACTIVE, StrategyState.CONFLICTED, StrategyState.UNAVAILABLE]
        assert res.state.value != "STALE"

def test_series_indicators_computation():
    now = time.time()
    candles = [
        {
            "open": 100.0 + (i * 0.2),
            "high": 101.0 + (i * 0.2),
            "low": 99.0 + (i * 0.2),
            "close": 100.5 + (i * 0.2),
            "volume": 1000 + i * 10,
            "timestamp": now - (60 - i) * 60,
        }
        for i in range(60)
    ]
    series = compute_series_indicators(candles)
    assert "ema20" in series
    assert "ema50" in series
    assert "vwap" in series
    assert "bb_upper" in series
    assert "macd" in series
    assert len(series["ema20"]) == 60
    assert series["ema20"][-1] is not None
    assert series["vwap"][-1] is not None

def test_observatory_payload_structure():
    now = time.time()
    candles = [
        {
            "open": 100.0 + (i * 0.3),
            "high": 101.0 + (i * 0.3),
            "low": 99.5 + (i * 0.3),
            "close": 100.5 + (i * 0.3),
            "volume": 2000 + i * 20,
            "timestamp": now - (59 - i) * 60,
        }
        for i in range(60)
    ]
    obs = evaluate_strategies_observatory(candles, is_live_feed=True, timeframe="15m", provider="UPSTOX")
    assert "market_regime" in obs
    assert "confluence" in obs
    assert "strategies" in obs
    assert "chart_indicators" in obs
    assert "candles" in obs
    assert obs["data_freshness"] == "LIVE"
    assert obs["timeframe"] == "15m"
    assert obs["provider"] == "UPSTOX"
    assert len(obs["strategies"]) == len(STRATEGY_REGISTRY)
    assert len(obs["candles"]) == 60

def test_confluence_calculation():
    now = time.time()
    candles = [
        {
            "open": 100.0 + (i * 0.4),
            "high": 101.0 + (i * 0.4),
            "low": 99.5 + (i * 0.4),
            "close": 100.8 + (i * 0.4),
            "volume": 5000 + i * 50,
            "timestamp": now - (60 - i) * 60,
        }
        for i in range(60)
    ]
    results = evaluate_all_strategies(candles, is_live_feed=True)
    confluence = compute_strategy_confluence(results)
    assert "active_count" in confluence
    assert "alignment_score_pct" in confluence
    assert "bullish_confluence" in confluence
    assert "reversal_confluence" in confluence

def test_historical_activations_and_events():
    now = time.time()
    candles = [
        {
            "open": 100.0 + (i * 0.4),
            "high": 101.0 + (i * 0.4),
            "low": 99.5 + (i * 0.4),
            "close": 100.8 + (i * 0.4),
            "volume": 5000 + i * 50,
            "timestamp": now - (70 - i) * 60,
        }
        for i in range(70)
    ]
    results = evaluate_all_strategies(candles, is_live_feed=True)
    ema_strat = next(r for r in results if r.strategy_id == "EMA_GOLDEN_CROSS")
    assert len(ema_strat.historical_states) > 0
    # Every historical state has a valid mathematical state
    for hs in ema_strat.historical_states:
        assert hs["state"] in ["ACTIVE", "PARTIAL", "INACTIVE", "CONFLICTED", "UNAVAILABLE"]

@pytest.mark.asyncio
async def test_copilot_evidence_grounded_fallback():
    copilot = StrategyCopilotAgent(api_key=None)
    eval_res = {
        "strategy_id": "EMA_GOLDEN_CROSS",
        "strategy_name": "EMA Golden Cross",
        "category": "Trend Following",
        "state": "ACTIVE",
        "entry_rules_passing": 3,
        "entry_rules_total": 3,
        "data_freshness": "LIVE",
        "data_age_seconds": 12.5,
        "rule_evaluations": [
            {"label": "EMA20 > EMA50", "outcome": "PASS", "actual_value_label": "ema20 = 1323.15", "is_entry_rule": True, "math_detail": "EMA20 - EMA50 = +0.217"}
        ],
        "feature_vector": {"close": 1324.0, "ema20": 1323.15, "ema50": 1322.94}
    }
    ans = await copilot.answer("RELIANCE.NS", eval_res, "Why is this active?")
    assert "reply" in ans
    assert "EMA Golden Cross" in ans["reply"]
    assert "ACTIVE" in ans["reply"]
    assert len(ans["evidence_cited"]) > 0
