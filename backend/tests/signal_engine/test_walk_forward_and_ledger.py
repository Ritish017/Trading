"""
Tests for Rolling Walk-Forward Engine, Non-Parametric Statistics,
Research Ledger, and Options Rule Audit Classification.
"""
import os
import pytest
from backend.app.signal_engine.walk_forward import (
    WalkForwardEngine,
    wilson_score_interval,
    bootstrap_expectancy_ci,
    calculate_sortino,
    calculate_tail_metrics,
    get_sample_size_classification,
    RollingWalkForwardResult,
    RollingWalkForwardWindow,
)
from backend.app.signal_engine.outcome_engine import SignalOutcome
from backend.app.signal_engine.research_ledger import ResearchExperiment, ResearchLedger
from backend.app.signal_engine.options_engine import OptionsEngine
from backend.app.signal_engine.transaction_cost import COST_MODEL_VERSION, COST_MODEL_METADATA
from backend.app.signal_engine.signal_store import signal_store


def test_wilson_score_interval():
    assert wilson_score_interval(0, 0) == (0.0, 0.0)
    low, high = wilson_score_interval(50, 100)
    assert 40.0 < low < 50.0
    assert 50.0 < high < 60.0
    assert low < high


def test_bootstrap_expectancy_ci():
    assert bootstrap_expectancy_ci([]) == (0.0, 0.0)
    r_list = [1.5, 2.0, 0.8, 1.2, 2.5, -1.0, 1.1, -0.9, 1.8, 2.2] * 5
    low, high = bootstrap_expectancy_ci(r_list, n_bootstraps=500)
    assert low > 0.0
    assert high > low


def test_calculate_sortino_and_tail_metrics():
    r_list = [1.5, -0.5, 2.0, -1.0, 1.0, 3.0, -0.8]
    sortino = calculate_sortino(r_list)
    assert sortino > 0.0

    tail = calculate_tail_metrics(r_list)
    assert "tail_win_r" in tail
    assert "tail_loss_r" in tail
    assert "tail_ratio" in tail
    assert tail["tail_ratio"] > 0.0


def test_sample_size_classification():
    assert get_sample_size_classification(15) == "INSUFFICIENT"
    assert get_sample_size_classification(45) == "PRELIMINARY"
    assert get_sample_size_classification(150) == "DEVELOPING"
    assert get_sample_size_classification(300) == "STRONGER_EMPIRICAL_SAMPLE"


def test_generate_rolling_windows():
    candles = [{"timestamp": i * 60, "close": 100 + i} for i in range(120)]
    windows = WalkForwardEngine.generate_rolling_windows(candles, window_size=50, step_size=25)
    assert len(windows) >= 3
    assert windows[0]["window_id"] == 1
    assert len(windows[0]["train"]) == 25
    assert len(windows[0]["val"]) == 12
    assert len(windows[0]["oos"]) == 13


def test_evaluate_rolling_walk_forward():
    outcomes = []
    for i in range(80):
        is_win = (i % 3 != 0)
        r = 1.5 if is_win else -1.0
        outcomes.append(
            SignalOutcome(
                signal_id=f"SIG_{i}",
                symbol="RELIANCE.NS",
                asset_class="EQUITY",
                direction="LONG" if i % 2 == 0 else "SHORT",
                status="TARGET_1" if is_win else "STOPPED",
                is_win=is_win,
                entry_price=100.0,
                exit_price=101.5 if is_win else 99.0,
                stop_loss_price=99.0,
                target_1_price=101.5,
                realized_r=r,
                gross_pnl=r * 100,
                net_pnl=r * 98,
            )
        )

    res = WalkForwardEngine.evaluate_rolling_walk_forward(outcomes, window_size=40, step_size=20)
    assert isinstance(res, RollingWalkForwardResult)
    assert res.total_trades == 80
    assert len(res.windows) >= 3
    assert res.overall_expectancy_r > 0
    assert res.sample_size_gate in ("PRELIMINARY", "DEVELOPING")
    assert "LONG" in res.windows[0].directional_breakdown
    assert "SHORT" in res.windows[0].directional_breakdown
    assert "EQUITY" in res.windows[0].asset_breakdown


def test_research_ledger():
    test_file = "docs/TEST_EXPERIMENT_LEDGER.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    ledger = ResearchLedger(ledger_file=test_file)
    exp = ResearchExperiment(
        hypothesis_id="HYP_EMA_CROSS_01",
        hypothesis="EMA 9/20 crossover yields positive expectancy in trending regimes",
        strategy_id="TREND_MOMENTUM_EMA",
        training_period="2024-01-01 to 2024-06-30",
        validation_period="2024-07-01 to 2024-09-30",
        test_period="2024-10-01 to 2024-12-31",
        sample_size=120,
        win_rate=0.58,
        expectancy_r=0.42,
        profit_factor=1.85,
        max_drawdown_r=2.1,
        sharpe_ratio=1.4,
        is_statistically_significant=True,
        result_status="ACCEPTED",
        conclusion="Positive edge maintained in out-of-sample trending period.",
    )
    ledger.record_experiment(exp)
    assert len(ledger.get_all_experiments()) == 1
    summary = ledger.get_summary()
    assert summary["total_experiments_recorded"] == 1
    assert summary["accepted_hypotheses"] == 1

    if os.path.exists(test_file):
        os.remove(test_file)


def test_options_rules_classification():
    rules = OptionsEngine.get_options_rules_classification()
    assert "BLACK_SCHOLES_PRICING" in rules
    assert rules["BLACK_SCHOLES_PRICING"]["classification"] == "EMPIRICALLY VALIDATED"
    assert rules["LIQUIDITY_VALIDATION"]["classification"] == "MARKET-CONSTRAINT"
    assert rules["TIME_DECAY_EXCLUSION"]["classification"] == "HEURISTIC"


def test_cost_model_metadata():
    assert COST_MODEL_VERSION == "NSE-STATUTORY-2026-V1"
    assert "statutory_rates" in COST_MODEL_METADATA
    assert COST_MODEL_METADATA["statutory_rates"]["gst_rate"] == 0.18


def test_candidate_observatory_deque():
    cand_obs = {
        "candidate_id": "CAND_TEST_999",
        "symbol": "TCS.NS",
        "evaluation_status": "QUALIFIED",
        "direction": "LONG",
        "opportunity_score": 78.5,
    }
    signal_store.add_candidate_observation(cand_obs)
    obs_list = signal_store.get_candidate_observations(symbol="TCS.NS")
    assert any(c.get("candidate_id") == "CAND_TEST_999" for c in obs_list)
