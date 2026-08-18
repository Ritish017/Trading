import pytest
import time
from backend.app.strategy_engine.dsl import StrategyState, RuleOutcome
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.evaluator import evaluate_all_strategies, compute_feature_vector

def test_strategy_registry_completeness():
    assert len(STRATEGY_REGISTRY) >= 8
    for sid, strat in STRATEGY_REGISTRY.items():
        assert strat.strategy_id == sid
        assert len(strat.entry_rules) > 0
        assert strat.min_candles >= 10

def test_evaluator_insufficient_candles():
    # Only 5 candles when min_candles is 50
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
    # 60 candles with upward trend
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

def test_feature_vector_computation():
    candles = [
        {"open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for _ in range(30)
    ]
    fv = compute_feature_vector(candles)
    assert "close" in fv
    assert "ema20" in fv
    assert "rsi14" in fv
    assert "bb_upper" in fv
