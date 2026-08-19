import pytest
import time
import pandas as pd
from backend.app.strategy_engine.dsl import (
    StrategyState,
    RuleOutcome,
    StrategyCategory,
    StrategyHypothesis,
)
from backend.app.strategy_engine.registry import (
    STRATEGY_REGISTRY,
    registry_manager,
    ALL_CANONICAL_STRATEGIES,
)
from backend.app.strategy_engine.evaluator import (
    evaluate_all_strategies,
    compute_feature_vector,
    compute_series_indicators,
    compute_strategy_confluence,
    evaluate_strategies_observatory,
    _evaluate_freshness,
    _get_ist_market_status,
)
from backend.app.ai_engine.agents import StrategyCopilotAgent

def test_strategy_registry_completeness():
    assert len(STRATEGY_REGISTRY) == 20
    assert len(ALL_CANONICAL_STRATEGIES) == 20
    for sid, strat in STRATEGY_REGISTRY.items():
        assert strat.strategy_id == sid
        assert len(strat.entry_rules) > 0
        assert strat.min_candles >= 10
        assert strat.short_name is not None
        assert strat.version == "1.0.0"
        assert strat.requirements is not None
        assert strat.visualization is not None
        assert isinstance(strat.category, StrategyCategory)

def test_category_distribution():
    trend = registry_manager.list_by_category(StrategyCategory.TREND)
    assert len(trend) == 5
    
    momentum = registry_manager.list_by_category(StrategyCategory.MOMENTUM)
    assert len(momentum) == 4
    
    mean_rev = registry_manager.list_by_category(StrategyCategory.MEAN_REVERSION)
    assert len(mean_rev) == 3
    
    breakout = registry_manager.list_by_category(StrategyCategory.BREAKOUT)
    assert len(breakout) == 4
    
    volume = registry_manager.list_by_category(StrategyCategory.VOLUME)
    assert len(volume) == 3
    
    volatility = registry_manager.list_by_category(StrategyCategory.VOLATILITY)
    assert len(volatility) == 1

def test_strategy_registry_manager_queries():
    all_strats = registry_manager.list_all()
    assert len(all_strats) == 20

    enabled_strats = registry_manager.list_enabled()
    assert len(enabled_strats) == 20

    trend_strats = registry_manager.list_by_category(StrategyCategory.TREND)
    assert len(trend_strats) == 5
    assert any(s.strategy_id == "EMA_GOLDEN_CROSS" for s in trend_strats)
    assert any(s.strategy_id == "ADX_TREND_STRENGTH" for s in trend_strats)
    assert any(s.strategy_id == "MOVING_AVERAGE_MOMENTUM_STACK" for s in trend_strats)

    deps = registry_manager.get_all_required_dependencies(["EMA_GOLDEN_CROSS", "VWAP_MOMENTUM", "ADX_TREND_STRENGTH"])
    assert "ema20" in deps
    assert "ema50" in deps
    assert "vwap" in deps
    assert "rsi14" in deps
    assert "adx" in deps
    assert "plus_di" in deps

    vis = registry_manager.get_visualization("DONCHIAN_BREAKOUT")
    assert vis is not None
    assert "donchian_high" in vis.overlays

def test_evaluator_insufficient_candles():
    candles = [
        {"open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 1000, "timestamp": time.time()}
        for i in range(5)
    ]
    results = evaluate_all_strategies(candles)
    assert len(results) == 20
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
            "timestamp": now - (250 - i) * 60,
        }
        for i in range(250)
    ]
    results = evaluate_all_strategies(candles, is_live_feed=True)
    assert len(results) == 20
    for res in results:
        assert res.candles_used == 250
        assert res.state in [StrategyState.ACTIVE, StrategyState.PARTIAL, StrategyState.INACTIVE, StrategyState.CONFLICTED]

def test_ma_stack_insufficient_history():
    """
    Phase 12: Moving Average Momentum Stack requires 200 bars.
    When 60 bars are provided, it must evaluate to UNAVAILABLE.
    """
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
    ma_stack = next(r for r in results if r.strategy_id == "MOVING_AVERAGE_MOMENTUM_STACK")
    assert ma_stack.state == StrategyState.UNAVAILABLE

def test_freshness_separation_stale_data():
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
    assert "adx" in series
    assert "donchian_high" in series
    assert "roc12" in series
    assert "cmf20" in series
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
    obs = evaluate_strategies_observatory(
        candles,
        is_live_feed=True,
        timeframe="15m",
        provider="UPSTOX",
        symbol="TCS.NS"
    )
    assert obs["symbol"] == "TCS.NS"
    assert "market_status" in obs
    assert "market_regime" in obs
    assert "confluence" in obs
    assert "strategies" in obs
    assert "chart_indicators" in obs
    assert "candles" in obs
    assert obs["data_freshness"] == "LIVE"
    assert obs["timeframe"] == "15m"
    assert obs["provider"] == "UPSTOX"
    assert len(obs["strategies"]) == 20
    assert len(obs["candles"]) == 60
    
    # Check V3 Metadata serialized
    strat0 = obs["strategies"][0]
    assert "short_name" in strat0
    assert "requirements" in strat0
    assert "visualization" in strat0
    assert "version" in strat0

def test_confluence_calculation_and_invariants():
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
    
    total = (
        confluence["active_count"]
        + confluence["partial_count"]
        + confluence["inactive_count"]
        + confluence["unavailable_count"]
        + confluence["conflicted_count"]
    )
    assert total == len(results)
    assert confluence["total_strategies"] == len(results)
    assert 0.0 <= confluence["alignment_score_pct"] <= 100.0

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
    for hs in ema_strat.historical_states:
        assert hs["state"] in ["ACTIVE", "PARTIAL", "INACTIVE", "CONFLICTED", "UNAVAILABLE"]

def test_lookahead_prevention():
    now = time.time()
    base_candles = [
        {
            "open": 100.0 + (i * 0.3),
            "high": 101.0 + (i * 0.3),
            "low": 99.0 + (i * 0.3),
            "close": 100.5 + (i * 0.3),
            "volume": 1000 + (i * 10),
            "timestamp": now - (60 - i) * 60,
        }
        for i in range(50)
    ]
    
    fv1 = compute_feature_vector(base_candles)
    
    future_candles = list(base_candles) + [
        {
            "open": 9999.0,
            "high": 10000.0,
            "low": 9990.0,
            "close": 9995.0,
            "volume": 9999999,
            "timestamp": now + 60,
        }
    ]
    
    fv_sliced = compute_feature_vector(future_candles[:50])
    assert fv1["close"] == fv_sliced["close"]
    assert fv1["ema20"] == fv_sliced["ema20"]
    assert fv1["vwap"] == fv_sliced["vwap"]

def test_zero_volume_vwap_contract():
    candles = [
        {
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 0.0,
            "timestamp": time.time() - (10 - i) * 60,
        }
        for i in range(10)
    ]
    fv = compute_feature_vector(candles)
    assert fv["vwap"] is None

def test_market_status_detection():
    assert _get_ist_market_status("MOCK") == "SIMULATED"
    assert _get_ist_market_status("DEV_MOCK") == "SIMULATED"
    status = _get_ist_market_status("UPSTOX")
    assert status in ["OPEN", "CLOSED", "PRE_OPEN"]

def test_backtest_hypothesis_evaluation():
    data = {
        "open": [100.0 + i for i in range(50)],
        "high": [102.0 + i for i in range(50)],
        "low": [99.0 + i for i in range(50)],
        "close": [101.5 + i for i in range(50)],
        "volume": [10000 + i * 100 for i in range(50)],
    }
    df = pd.DataFrame(data)
    hypothesis = StrategyHypothesis(name="VWAP_Momentum_Breakout")
    evaluated_df = hypothesis.evaluate_signals(df)
    assert "buy_signal" in evaluated_df.columns
    assert "sell_signal" in evaluated_df.columns
    assert len(evaluated_df) == 50

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
