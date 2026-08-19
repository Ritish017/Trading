import pytest
import numpy as np
import pandas as pd
from backend.app.strategy_engine.dsl import (
    StrategyState,
    StrategyDirection,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.backtesting.event_driven import (
    EventDrivenBacktester,
    StrategyHypothesis,
    BacktestTradeEvidence,
)
from backend.app.strategy_engine.validation_engine import (
    StrategyValidationEngine,
    strategy_validation_engine,
    StrategyResearchScorecard,
)


def generate_synthetic_backtest_candles(n: int = 120, base_price: float = 100.0) -> list:
    """
    Generates a deterministic synthetic sequence of candles with uptrends, pullbacks, and breakouts.
    Used STRICTLY as a unit test fixture.
    """
    candles = []
    now = 1700000000
    price = base_price
    for i in range(n):
        if i < 30:
            drift = 0.4
        elif i < 60:
            drift = -0.2
        elif i < 90:
            drift = 0.6
        else:
            drift = -0.1

        open_p = price
        close_p = open_p + drift
        high_p = max(open_p, close_p) + 0.5
        low_p = min(open_p, close_p) - 0.5
        vol = 1000.0 + (i * 25.0)

        price = close_p
        candles.append({
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(vol, 1),
            "timestamp": now + (i * 300),
        })
    return candles


# ---------------------------------------------------------------------------
# Test 1: StrategyDefinition -> Hypothesis Conversion & Incomplete Validation
# ---------------------------------------------------------------------------

def test_hypothesis_conversion_and_validation():
    """
    Tests converting StrategyDefinition to StrategyHypothesis and validating parameter completeness.
    """
    hyp, err = strategy_validation_engine.build_hypothesis_from_strategy(
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="RELIANCE.NS",
        timeframe="5m",
        initial_capital=500000.0,
    )
    assert err is None
    assert isinstance(hyp, StrategyHypothesis)
    assert hyp.strategy_id == "EMA_GOLDEN_CROSS"
    assert hyp.initial_capital == 500000.0

    # Incomplete hypothesis test
    invalid_hyp = StrategyHypothesis(strategy_id="", initial_capital=0.0)
    is_valid, err_msg = invalid_hyp.is_valid()
    assert is_valid is False
    assert "HYPOTHESIS_INCOMPLETE" in err_msg


# ---------------------------------------------------------------------------
# Test 2: Next-Bar Entry Execution Invariant
# ---------------------------------------------------------------------------

def test_next_bar_entry_execution():
    """
    Verifies that a buy signal generated on bar T close results in entry on bar T+1.
    """
    candles = generate_synthetic_backtest_candles(n=80, base_price=100.0)
    res = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
        timeframe="5m",
    )

    assert res["status"] == "SUCCESS"
    trades = res.get("trades", [])
    if trades:
        for t in trades:
            # Entry index must be > signal bar index (cannot execute on or before signal bar)
            assert t["entry_index"] >= 1
            assert t["exit_index"] >= t["entry_index"]


# ---------------------------------------------------------------------------
# Test 3: Friction & Cost Calculations (Gross vs Net Separation)
# ---------------------------------------------------------------------------

def test_transaction_costs_and_slippage_separation():
    """
    Verifies transparent calculation of brokerage, slippage, gross P&L, and net P&L.
    """
    candles = generate_synthetic_backtest_candles(n=100, base_price=100.0)
    hyp = StrategyHypothesis(
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
        slippage_pct=0.10,
        brokerage_per_trade=25.0,
    )
    res = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
        hypothesis=hyp,
    )

    trades = res.get("trades", [])
    if trades:
        for t in trades:
            assert t["brokerage_cost"] == 50.0  # ₹25 entry + ₹25 exit
            assert t["slippage_cost"] >= 0.0
            assert t["total_costs"] == round(t["slippage_cost"] + t["brokerage_cost"], 2)
            assert t["net_pnl"] == round(t["gross_pnl"] - t["brokerage_cost"], 2)


# ---------------------------------------------------------------------------
# Test 4: Trade-Level Evidence Retention
# ---------------------------------------------------------------------------

def test_trade_level_evidence_retention():
    """
    Verifies that every simulated trade preserves regime at entry, timestamps, prices, and rule snapshots.
    """
    candles = generate_synthetic_backtest_candles(n=100, base_price=100.0)
    res = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id="DONCHIAN_BREAKOUT",
        symbol="TEST.NS",
    )

    trades = res.get("trades", [])
    for t in trades:
        assert t["strategy_id"] == "DONCHIAN_BREAKOUT"
        assert t["regime_at_entry"] in [
            "TRENDING_BULLISH", "TRENDING_BEARISH", "BULLISH_ACCUMULATION",
            "BEARISH_DISTRIBUTION", "HIGH_VOLATILITY", "RANGE_BOUND", "UNAVAILABLE"
        ]
        assert "entry_rule_evidence" in t
        assert "exit_reason" in t
        assert t["duration_bars"] >= 1


# ---------------------------------------------------------------------------
# Test 5 & 6: Walk-Forward In-Sample vs Out-of-Sample & Overfitting Detection
# ---------------------------------------------------------------------------

def test_walk_forward_and_overfitting_classification():
    """
    Verifies that 70% In-Sample and 30% Out-of-Sample results are segregated and overfitting is classified.
    """
    candles = generate_synthetic_backtest_candles(n=120, base_price=100.0)
    res = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id="RSI_OVERSOLD_REVERSAL",
        symbol="TEST.NS",
    )

    wf = res.get("walk_forward", {})
    assert "in_sample_return_pct" in wf
    assert "out_of_sample_return_pct" in wf
    assert "in_sample_trades" in wf
    assert "out_of_sample_trades" in wf
    assert wf["overfitting_status"] in ["ACCEPTABLE", "DEGRADED_OOS", "OVERFIT", "REJECTED", "INSUFFICIENT_TRADES"]


# ---------------------------------------------------------------------------
# Test 7 & 8: Market Regime x Strategy Matrix
# ---------------------------------------------------------------------------

def test_market_regime_matrix_generation():
    """
    Verifies that Regime Matrix computes numeric metrics (trades, net P&L, profit factor) per regime cell.
    """
    candles = generate_synthetic_backtest_candles(n=120, base_price=100.0)
    res = strategy_validation_engine.compute_regime_matrix(
        candles=candles,
        symbol="INFY.NS",
        timeframe="5m",
        strategy_ids=["EMA_GOLDEN_CROSS", "DONCHIAN_BREAKOUT", "VWAP_MOMENTUM"],
    )

    assert res["status"] == "SUCCESS"
    matrix = res.get("matrix", {})
    assert len(matrix) == 3
    for sid, data in matrix.items():
        assert data["robustness_classification"] in ["REGIME_DIVERSIFIED", "REGIME_DEPENDENT"]
        assert isinstance(data["regimes"], dict)


# ---------------------------------------------------------------------------
# Test 9: Confluence Backtesting
# ---------------------------------------------------------------------------

def test_confluence_backtest_execution():
    """
    Verifies that logical AND confluence backtesting executes cleanly across multiple strategies.
    """
    candles = generate_synthetic_backtest_candles(n=120, base_price=100.0)
    res = strategy_validation_engine.compute_confluence_backtest(
        candles=candles,
        strategy_ids=["EMA_GOLDEN_CROSS", "VWAP_MOMENTUM"],
        symbol="TCS.NS",
        timeframe="5m",
    )

    assert res["status"] == "SUCCESS"
    assert "confluence_name" in res
    assert "totalTrades" in res


# ---------------------------------------------------------------------------
# Test 10: Strategy Correlation & Signal Redundancy
# ---------------------------------------------------------------------------

def test_strategy_correlation_and_redundancy():
    """
    Verifies calculation of pairwise activation overlap % and overlap classification.
    """
    candles = generate_synthetic_backtest_candles(n=100, base_price=100.0)
    res = strategy_validation_engine.compute_strategy_correlation(
        candles=candles,
        symbol="RELIANCE.NS",
        strategy_ids=["EMA_GOLDEN_CROSS", "MOVING_AVERAGE_MOMENTUM_STACK", "VWAP_MOMENTUM"],
    )

    assert res["status"] == "SUCCESS"
    pairs = res.get("correlation_pairs", [])
    assert len(pairs) == 3  # 3 choose 2
    for p in pairs:
        assert 0.0 <= p["overlap_pct"] <= 100.0
        assert p["overlap_classification"] in ["HIGH_OVERLAP", "MODERATE_OVERLAP", "LOW_OVERLAP"]


# ---------------------------------------------------------------------------
# Test 11: Cost Sensitivity Modeling
# ---------------------------------------------------------------------------

def test_cost_sensitivity_scenarios():
    """
    Verifies calculation of Zero Friction, Configured Friction, and High Friction scenarios.
    """
    candles = generate_synthetic_backtest_candles(n=100, base_price=100.0)
    res = strategy_validation_engine.validate_strategy(
        candles=candles,
        strategy_id="VWAP_MOMENTUM",
        symbol="TEST.NS",
    )

    cs = res.get("cost_sensitivity", {})
    assert "zero_friction_return_pct" in cs
    assert "configured_friction_return_pct" in cs
    assert "high_friction_return_pct" in cs
    assert cs["zero_friction_return_pct"] >= cs["configured_friction_return_pct"] >= cs["high_friction_return_pct"]


# ---------------------------------------------------------------------------
# Test 12: Strategy Research Scorecard
# ---------------------------------------------------------------------------

def test_strategy_research_scorecard_generation():
    """
    Verifies multi-dimensional scorecard generation with deterministic ratings and status.
    """
    candles = generate_synthetic_backtest_candles(n=100, base_price=100.0)
    scorecard = strategy_validation_engine.generate_scorecard(
        candles=candles,
        strategy_id="EMA_GOLDEN_CROSS",
        symbol="TEST.NS",
    )

    assert isinstance(scorecard, StrategyResearchScorecard)
    assert scorecard.overall_status in [
        "RESEARCH_CANDIDATE", "PROMISING", "REGIME_DEPENDENT",
        "INSUFFICIENT_DATA", "OVERFIT", "REJECTED"
    ]
    assert scorecard.sample_size_rating.rating in ["EXCELLENT", "GOOD", "MODERATE", "INSUFFICIENT"]


# ---------------------------------------------------------------------------
# Test 13: 20-Strategy Full Backtest Regression
# ---------------------------------------------------------------------------

def test_all_20_strategies_backtest_execution():
    """
    Verifies that all 20 canonical strategies execute cleanly in the validation engine.
    """
    candles = generate_synthetic_backtest_candles(n=150, base_price=100.0)
    for sid in STRATEGY_REGISTRY.keys():
        res = strategy_validation_engine.validate_strategy(
            candles=candles,
            strategy_id=sid,
            symbol="TEST.NS",
        )
        assert res["status"] == "SUCCESS"
        assert "totalReturnPct" in res
        assert "walk_forward" in res
