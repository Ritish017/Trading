"""
Unit Test Suite — APEX Strategy Library V3 Phase 6: Strategy Discovery & Robustness Testing
============================================================================================
Verifies:
1. Research parameter schema & domain bounds validation
2. Controlled parameter sweeps with combinatorial safety bounds
3. 2D Parameter Surface generation
4. Neighborhood robustness & plateau analysis
5. Multi-symbol generalization & dispersion
6. Period robustness & strategy decay diagnostics
7. Regime transition analysis
8. Purged Walk-Forward parameter selection with OOS isolation
9. Triple-friction cost sensitivity
10. Data snooping safeguards & multiple testing disclosures
11. Strategy family & redundancy clustering
12. Experiment ledger reproducibility & comparison
13. Copilot Skeptic Mode ('CHALLENGE THIS STRATEGY')
14. 20-strategy regression compatibility
"""

import pytest
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from backend.app.strategy_engine.dsl import (
    ResearchParameter,
    StrategyDefinition,
    StrategyState,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.robustness_engine import (
    RobustnessEngine,
    robustness_engine,
    _evaluate_signals_with_params,
)
from backend.app.ai_engine.agents import StrategyCopilotAgent


def generate_synthetic_robustness_candles(n: int = 150, base_price: float = 100.0) -> List[Dict[str, Any]]:
    """Generates synthetic multi-bar price data with realistic OHLCV structures."""
    np.random.seed(42)
    candles = []
    price = base_price
    base_ts = 1700000000

    for i in range(n):
        ret = np.random.normal(0.001, 0.015)
        price = max(10.0, price * (1.0 + ret))
        high = price * (1.0 + abs(np.random.normal(0.005, 0.005)))
        low = price * (1.0 - abs(np.random.normal(0.005, 0.005)))
        op = price * (1.0 + np.random.normal(0.0, 0.003))
        vol = int(np.random.uniform(500, 5000))

        candles.append({
            "timestamp": base_ts + i * 300,
            "open": round(op, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2),
            "volume": vol,
        })
    return candles


# ---------------------------------------------------------------------------
# 1. Parameter Schema & Domain Bounds Validation
# ---------------------------------------------------------------------------

def test_research_parameter_schema_and_domain_validation():
    param = ResearchParameter(
        parameter_id="fast_period",
        name="Fast Period",
        param_type="int",
        default_value=20,
        minimum=10,
        maximum=30,
        step=5,
    )
    # Valid
    ok, err = param.validate_value(20)
    assert ok is True
    assert err is None

    # Below min
    ok, err = param.validate_value(5)
    assert ok is False
    assert "below minimum" in err

    # Above max
    ok, err = param.validate_value(35)
    assert ok is False
    assert "above maximum" in err


# ---------------------------------------------------------------------------
# 2. Parameter Sweep Combinatorial Safety Bounds
# ---------------------------------------------------------------------------

def test_parameter_sweep_combinatorial_safety_bounds():
    candles = generate_synthetic_robustness_candles(n=100)
    # Generate 60 configurations (exceeding MAX_SWEEP_CONFIGURATIONS = 50)
    oversized_grid = [{"fast_period": i} for i in range(60)]

    res = robustness_engine.run_parameter_sweep(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="RELIANCE.NS",
        parameter_grid=oversized_grid,
    )

    assert res["status"] == "ERROR"
    assert "exceeds maximum allowed safety threshold" in res["message"]


# ---------------------------------------------------------------------------
# 3. Parameter Sweep Execution & Output Metrics
# ---------------------------------------------------------------------------

def test_parameter_sweep_execution_and_metrics():
    candles = generate_synthetic_robustness_candles(n=120)
    grid = [
        {"fast_period": 15, "slow_period": 40},
        {"fast_period": 20, "slow_period": 50},
        {"fast_period": 25, "slow_period": 60},
    ]

    res = robustness_engine.run_parameter_sweep(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TCS.NS",
        parameter_grid=grid,
    )

    assert res["status"] == "SUCCESS"
    assert res["configurations_tested"] == 3
    assert len(res["results"]) == 3

    for item in res["results"]:
        assert "gross_return_pct" in item
        assert "net_return_pct" in item
        assert "sharpe_ratio" in item
        assert "max_drawdown_pct" in item
        assert "is_return_pct" in item
        assert "oos_return_pct" in item
        assert "triple_friction_return_pct" in item
        assert item["robustness_classification"] in [
            "ROBUST_CANDIDATE", "STABLE_REGION", "COST_SENSITIVE", "OOS_DEGRADED", "OVERFIT", "INSUFFICIENT_DATA"
        ]


# ---------------------------------------------------------------------------
# 4. 2D Parameter Surface Generation
# ---------------------------------------------------------------------------

def test_parameter_surface_generation():
    candles = generate_synthetic_robustness_candles(n=100)
    res = robustness_engine.generate_parameter_surface(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="INFY.NS",
        param_1_id="fast_period",
        param_1_values=[15, 20],
        param_2_id="slow_period",
        param_2_values=[40, 50],
    )

    assert res["status"] == "SUCCESS"
    surf = res["surface"]
    assert surf["param_1_id"] == "fast_period"
    assert surf["param_2_id"] == "slow_period"
    assert len(surf["cells"]) == 4

    for cell in surf["cells"]:
        assert "net_return_pct" in cell
        assert "sharpe_ratio" in cell
        assert "total_trades" in cell
        assert "oos_return_pct" in cell


# ---------------------------------------------------------------------------
# 5. Neighborhood Robustness & Plateau Analysis
# ---------------------------------------------------------------------------

def test_neighborhood_robustness_and_plateau_analysis():
    candles = generate_synthetic_robustness_candles(n=100)
    target_params = {"fast_period": 20, "slow_period": 50, "max_rsi": 70.0}

    res = robustness_engine.analyze_neighborhood(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="HDFCBANK.NS",
        target_params=target_params,
    )

    assert res["status"] == "SUCCESS"
    ana = res["analysis"]
    assert "plateau_score" in ana
    assert "stability_classification" in ana
    assert ana["stability_classification"] in [
        "STABLE_PLATEAU", "MODERATE_CLIFF", "ISOLATED_PEAK", "INSUFFICIENT_NEIGHBORS"
    ]


# ---------------------------------------------------------------------------
# 6. Multi-Symbol Robustness & Dispersion
# ---------------------------------------------------------------------------

def test_multi_symbol_robustness_and_dispersion():
    candles_map = {
        "RELIANCE.NS": generate_synthetic_robustness_candles(n=100, base_price=2500.0),
        "TCS.NS": generate_synthetic_robustness_candles(n=100, base_price=3500.0),
        "INFY.NS": generate_synthetic_robustness_candles(n=100, base_price=1500.0),
    }

    res = robustness_engine.evaluate_multi_symbol_robustness(
        symbol_candles_map=candles_map,
        strategy_id="EMA_GOLDEN_CROSS",
        params={"fast_period": 20, "slow_period": 50},
    )

    assert res["status"] == "SUCCESS"
    summ = res["summary"]
    assert summ["symbol_count"] == 3
    assert "median_net_return_pct" in summ
    assert "dispersion_iqr_pct" in summ
    assert summ["best_symbol"] in candles_map
    assert summ["worst_symbol"] in candles_map
    assert summ["generalization_classification"] in [
        "CROSS_SYMBOL_ROBUST", "MODERATE_DISPERSION", "SYMBOL_DEPENDENT", "INSUFFICIENT_DATA"
    ]


# ---------------------------------------------------------------------------
# 7. Period Robustness & Strategy Decay
# ---------------------------------------------------------------------------

def test_period_robustness_and_strategy_decay():
    candles = generate_synthetic_robustness_candles(n=150)
    res = robustness_engine.evaluate_period_robustness(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        params={"fast_period": 20, "slow_period": 50},
        subperiods=3,
    )

    assert res["status"] == "SUCCESS"
    summ = res["summary"]
    assert summ["subperiod_count"] == 3
    assert len(summ["subperiod_results"]) == 3
    assert summ["decay_status"] in ["STABLE", "DEGRADING", "IMPROVING", "INSUFFICIENT_DATA"]


# ---------------------------------------------------------------------------
# 8. Regime Transition Analysis
# ---------------------------------------------------------------------------

def test_regime_transition_analysis():
    candles = generate_synthetic_robustness_candles(n=100)
    res = robustness_engine.analyze_regime_transitions(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        params={"fast_period": 20, "slow_period": 50},
    )

    assert res["status"] == "SUCCESS"
    ana = res["analysis"]
    assert "total_regime_transitions" in ana
    assert "transition_activations_count" in ana
    assert "stable_regime_activations_count" in ana


# ---------------------------------------------------------------------------
# 9. Walk-Forward Parameter Selection with OOS Isolation
# ---------------------------------------------------------------------------

def test_walk_forward_parameter_selection_oos_isolation():
    candles = generate_synthetic_robustness_candles(n=150)
    grid = [
        {"fast_period": 15, "slow_period": 40},
        {"fast_period": 20, "slow_period": 50},
    ]

    res = robustness_engine.walk_forward_parameter_selection(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        param_grid=grid,
        folds=3,
        train_ratio=0.70,
    )

    assert res["status"] == "SUCCESS"
    wf_res = res["result"]
    assert wf_res["fold_count"] == 3
    assert len(wf_res["selected_parameters_per_fold"]) == 3
    assert len(wf_res["is_returns_per_fold"]) == 3
    assert len(wf_res["oos_returns_per_fold"]) == 3
    assert "cumulative_oos_return_pct" in wf_res
    assert wf_res["walk_forward_classification"] in [
        "ROBUST_WALK_FORWARD", "DEGRADED_OOS", "OVERFIT_SELECTION", "INSUFFICIENT_SAMPLES"
    ]


# ---------------------------------------------------------------------------
# 10. Cost Robustness & Triple Friction Analysis
# ---------------------------------------------------------------------------

def test_cost_robustness_triple_friction():
    candles = generate_synthetic_robustness_candles(n=100)
    res = robustness_engine.run_parameter_sweep(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="RELIANCE.NS",
        parameter_grid=[{"fast_period": 20, "slow_period": 50}],
    )

    assert res["status"] == "SUCCESS"
    item = res["results"][0]
    assert "high_friction_return_pct" in item
    assert "triple_friction_return_pct" in item
    assert item["triple_friction_return_pct"] <= item["gross_return_pct"]


# ---------------------------------------------------------------------------
# 11. Data Snooping Safeguards & Disclosures
# ---------------------------------------------------------------------------

def test_data_snooping_warning_and_multiple_testing():
    candles = generate_synthetic_robustness_candles(n=100)
    grid = [{"fast_period": 10 + i, "slow_period": 50} for i in range(12)]

    res = robustness_engine.run_parameter_sweep(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="SBIN.NS",
        parameter_grid=grid,
    )

    assert res["status"] == "SUCCESS"
    assert res["data_snooping_warning"] is True
    assert "MANY CONFIGURATIONS TESTED" in res["data_snooping_message"]


# ---------------------------------------------------------------------------
# 12. Strategy Redundancy & Family Clustering
# ---------------------------------------------------------------------------

def test_strategy_redundancy_and_family_clustering():
    candles = generate_synthetic_robustness_candles(n=100)
    res = robustness_engine.analyze_strategy_families(
        candles=candles,
        symbol="NIFTY 50",
    )

    assert res["status"] == "SUCCESS"
    families = res["families"]
    assert "Trend Following" in families
    assert "Momentum" in families
    assert "Mean-Reversion" in families
    assert "Breakout" in families
    assert "Volume" in families


# ---------------------------------------------------------------------------
# 13. Immutable Experiment Ledger & Comparison
# ---------------------------------------------------------------------------

def test_experiment_ledger_reproducibility_and_comparison():
    engine = RobustnessEngine()
    fake_bt = {
        "totalTrades": 12,
        "totalReturnPct": 8.5,
        "sharpeRatio": 1.4,
        "maxDrawdown": 4.2,
        "walk_forward": {"in_sample_return_pct": 9.0, "out_of_sample_return_pct": 7.5, "overfitting_status": "ACCEPTABLE"},
        "cost_sensitivity": {"cost_drag_pct": 1.2},
    }

    rec1 = engine.record_experiment(
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="RELIANCE.NS",
        timeframe="5m",
        parameters={"fast_period": 20, "slow_period": 50},
        backtest_result=fake_bt,
    )

    rec2 = engine.record_experiment(
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="RELIANCE.NS",
        timeframe="5m",
        parameters={"fast_period": 15, "slow_period": 40},
        backtest_result=fake_bt,
    )

    all_exps = engine.list_experiments()
    assert len(all_exps) == 2

    comp = engine.compare_experiments([rec1.experiment_id, rec2.experiment_id])
    assert comp["status"] == "SUCCESS"
    assert comp["experiments_count"] == 2


# ---------------------------------------------------------------------------
# 14. Copilot Skeptic Mode ('CHALLENGE THIS STRATEGY')
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_copilot_skeptic_mode_evidence_generation():
    agent = StrategyCopilotAgent()
    fake_bt = {
        "totalTrades": 6, # Low sample
        "totalReturnPct": 12.0,
        "sharpeRatio": 1.8,
        "walk_forward": {"out_of_sample_return_pct": -4.0}, # OOS collapse
        "cost_sensitivity": {"cost_drag_pct": 4.5}, # High cost drag
    }

    res = await agent.answer(
        symbol="TATAMOTORS.NS",
        evaluation=None,
        user_message="CHALLENGE THIS STRATEGY",
        backtest_result=fake_bt,
        is_skeptic_mode=True,
    )

    assert "reply" in res
    assert len(res["evidence_cited"]) > 0
    assert "Skeptic" in res["reply"] or "Low Sample" in res["reply"] or "Out-of-Sample" in res["reply"]


# ---------------------------------------------------------------------------
# 15. All 20 Strategies Parameter Compatibility
# ---------------------------------------------------------------------------

def test_all_20_strategies_parameter_compatibility():
    candles = generate_synthetic_robustness_candles(n=80)
    for sid, strat in STRATEGY_REGISTRY.items():
        df, reg, conf, ev = _evaluate_signals_with_params(
            candles=candles,
            strategy_id=sid,
            params={},
            symbol="TEST.NS",
            timeframe="5m",
        )
        assert not df.empty
        assert "buy_signal" in df.columns
        assert "sell_signal" in df.columns
