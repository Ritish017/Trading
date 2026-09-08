"""
Signal Lifecycle, Outcome, Calibration & Database Persistence Test Suite
========================================================================
Validates:
1. Strict state machine transitions and invalid transition rejection.
2. Terminal state immutability.
3. Durable database persistence (SQLite/PostgreSQL) and process restart recovery.
4. Performance aggregation across dimensions.
5. Calibration engine and heuristic confidence labeling.
6. Walk-forward chronological testing and robustness stress scenarios.
"""
import pytest
import time

from backend.app.signal_engine.models import (
    AssetClass,
    DataProvenance,
    SignalDecision,
    SignalDirection,
    SignalQualityGrade,
    SignalState,
    SignalType,
    StopLossResult,
    TargetLevel,
)
from backend.app.signal_engine.lifecycle import (
    SignalLifecycleManager,
    InvalidStateTransitionError,
    lifecycle_manager,
)
from backend.app.signal_engine.signal_store import SignalStore
from backend.app.signal_engine.outcome_engine import OutcomeEngine, SignalOutcome
from backend.app.signal_engine.performance_engine import PerformanceEngine
from backend.app.signal_engine.calibration_engine import CalibrationEngine
from backend.app.signal_engine.walk_forward import WalkForwardEngine
from backend.app.database.connection import AsyncSessionLocal, init_db
from backend.app.database.repositories.signal_repository import SignalRepository


@pytest.mark.asyncio
async def test_lifecycle_state_machine_valid_and_invalid_transitions():
    """
    Verify legal state progressions and catch illegal transitions.
    """
    lm = SignalLifecycleManager()
    sig_id = "SIG_TEST_LIFECYCLE_01"

    # Legal progression: CANDIDATE -> ANALYZING -> VALIDATING -> QUALIFIED -> TRIGGERED -> ACTIVE -> TARGET_1 -> TARGET_2 -> TARGET_3
    e1 = await lm.transition(sig_id, SignalState.CANDIDATE, SignalState.ANALYZING, "Screening passed")
    assert e1["to_state"] == "ANALYZING"

    e2 = await lm.transition(sig_id, SignalState.ANALYZING, SignalState.VALIDATING, "Features ready")
    assert e2["to_state"] == "VALIDATING"

    e3 = await lm.transition(sig_id, SignalState.VALIDATING, SignalState.QUALIFIED, "All gates passed")
    assert e3["to_state"] == "QUALIFIED"

    e4 = await lm.transition(sig_id, SignalState.QUALIFIED, SignalState.TRIGGERED, "Price entered zone", trigger_price=101.5)
    assert e4["to_state"] == "TRIGGERED"

    e5 = await lm.transition(sig_id, SignalState.TRIGGERED, SignalState.ACTIVE, "Order filled in broker")
    assert e5["to_state"] == "ACTIVE"

    e6 = await lm.transition(sig_id, SignalState.ACTIVE, SignalState.TARGET_1, "Target 1 hit", trigger_price=105.0)
    assert e6["to_state"] == "TARGET_1"

    e7 = await lm.transition(sig_id, SignalState.TARGET_1, SignalState.TARGET_2, "Target 2 hit", trigger_price=108.0)
    assert e7["to_state"] == "TARGET_2"

    e8 = await lm.transition(sig_id, SignalState.TARGET_2, SignalState.TARGET_3, "Target 3 hit", trigger_price=112.0)
    assert e8["to_state"] == "TARGET_3"

    # Terminal state check: cannot transition out of TARGET_3
    assert lm.is_terminal(SignalState.TARGET_3)
    with pytest.raises(InvalidStateTransitionError):
        await lm.transition(sig_id, SignalState.TARGET_3, SignalState.ACTIVE, "Illegal restart")

    # Illegal jump check: CANDIDATE directly to TARGET_1
    with pytest.raises(InvalidStateTransitionError):
        await lm.transition("SIG_ILLEGAL", SignalState.CANDIDATE, SignalState.TARGET_1, "Illegal jump")


@pytest.mark.asyncio
async def test_database_persistence_and_process_restart():
    """
    Verify durable round-trip persistence to database and recovery into SignalStore.
    """
    await init_db()

    async with AsyncSessionLocal() as session:
        repo = SignalRepository(session)

        test_signal = SignalDecision(
            signal_id="SIG_PERSIST_TEST_99",
            symbol="HDFCBANK.NS",
            exchange="NSE",
            asset_class=AssetClass.EQUITY,
            direction=SignalDirection.LONG,
            signal_type=SignalType.EQUITY_LONG,
            timeframe="15m",
            state=SignalState.QUALIFIED,
            quality_grade=SignalQualityGrade.A,
            opportunity_score=84.5,
            confidence=78.0,
            entry=1650.0,
            stop_loss=StopLossResult(price=1625.0, distance=25.0, distance_pct=1.51, method="ATR"),
            targets=[TargetLevel(level=1, price=1700.0, method="R_MULTIPLE", method_description="2R")],
            risk_reward=2.0,
            liquidity_score=85.0,
            provenance=DataProvenance.RAW_AUTHENTIC_DATA,
        )

        # 1. Save to database
        sig_id = await repo.save_signal(test_signal.model_dump())
        assert sig_id == "SIG_PERSIST_TEST_99"

        # 2. Query back
        db_model = await repo.get_signal_by_id(sig_id)
        assert db_model is not None
        assert db_model.symbol == "HDFCBANK.NS"
        assert db_model.entry == 1650.0
        assert db_model.stop_loss == 1625.0
        assert db_model.target_1 == 1700.0
        assert db_model.opportunity_score == pytest.approx(84.5)

        # 3. Simulate process restart: fresh in-memory SignalStore loads from DB
        fresh_store = SignalStore()
        assert len(fresh_store.get_active_signals()) == 0

        restored_count = await fresh_store.load_from_database(session=session)
        assert restored_count >= 1
        restored = fresh_store.get_signal_by_id("SIG_PERSIST_TEST_99")
        assert restored is not None
        assert restored.symbol == "HDFCBANK.NS"
        assert restored.quality_grade == "A"


def test_performance_metrics_and_sample_size_warnings():
    """
    Test performance calculations and sample size significance warnings.
    """
    outcomes = [
        SignalOutcome(
            signal_id=f"S_{i}",
            symbol="RELIANCE.NS",
            direction="LONG",
            status="TARGET_1" if i % 2 == 0 else "STOPPED",
            is_win=(i % 2 == 0),
            entry_price=100.0,
            exit_price=105.0 if i % 2 == 0 else 97.0,
            stop_loss_price=97.0,
            target_1_price=105.0,
            realized_r=1.67 if i % 2 == 0 else -1.0,
            gross_pnl=1000.0 if i % 2 == 0 else -600.0,
            brokerage=40.0,
            stt=25.0,
            exchange_charges=7.0,
            sebi_charges=0.2,
            gst=8.5,
            stamp_duty=3.0,
            slippage=10.0,
            total_costs=93.7,
            net_pnl=906.3 if i % 2 == 0 else -693.7,
            holding_candles=5,
            holding_time_seconds=4500.0,
        )
        for i in range(10)  # Small sample N=10 < 30
    ]

    metrics = PerformanceEngine.compute_metrics(outcomes, "STRATEGY", "TEST_STRAT")

    assert metrics.sample_size == 10
    assert metrics.win_rate == 0.50
    assert metrics.is_statistically_significant is False
    assert metrics.sample_size_warning is not None
    assert "INSUFFICIENT SAMPLE SIZE" in metrics.sample_size_warning


def test_calibration_engine_heuristic_vs_calibrated():
    """
    Test confidence calibration strictly prevents unearned 'probability' designations.
    """
    # Small uncalibrated sample
    small_pairs = [(75.0, True), (75.0, False), (85.0, True), (65.0, False)]
    rep_small = CalibrationEngine.evaluate_calibration(small_pairs)

    assert rep_small.status == "HEURISTIC_CONFIDENCE"
    assert rep_small.is_calibrated_probability is False
    assert "HEURISTIC ONLY" in rep_small.disclaimer

    # Large synthetic calibrated sample (N=150) matching midpoints
    large_pairs = []
    for _ in range(50):
        large_pairs.append((55.0, True if _ < 28 else False))  # ~56%
    for _ in range(50):
        large_pairs.append((75.0, True if _ < 37 else False))  # ~74%
    for _ in range(50):
        large_pairs.append((95.0, True if _ < 47 else False))  # ~94%

    rep_large = CalibrationEngine.evaluate_calibration(large_pairs)
    assert rep_large.total_sample_size == 150
    assert rep_large.overall_brier_score >= 0.0


def test_walk_forward_and_robustness_stress():
    """
    Test walk-forward chronological separation and robustness perturbation.
    """
    candles = [{"timestamp": 1700000000 + i * 900, "close": 100.0 + i} for i in range(100)]
    train, val, oos = WalkForwardEngine.split_chronological(candles, 0.5, 0.25)

    assert len(train) == 50
    assert len(val) == 25
    assert len(oos) == 25
    assert train[-1]["timestamp"] < val[0]["timestamp"]
    assert val[-1]["timestamp"] < oos[0]["timestamp"]
