"""
Unit tests for Live Paper Session Runner end-to-end workflow with test fixtures.
"""

import os
import shutil
import time
import pytest

from backend.app.broker_providers.base import NormalizedTick
from backend.app.live_paper.session_runner import LivePaperSessionRunner
from backend.app.live_paper.cli import verify_log_command
from backend.app.signal_engine.models import (
    SignalDecision,
    SignalDirection,
    StopLossResult,
    TargetLevel,
    PositionSizing,
)


@pytest.fixture
def test_session_dir():
    dir_path = os.path.join("logs", "test_runner")
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)
    yield dir_path
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)


@pytest.mark.asyncio
async def test_session_runner_lifecycle_and_tick_processing(test_session_dir):
    runner = LivePaperSessionRunner(
        experiment_id="TEST-RUNNER-001",
        session_date="2026-09-10",
        log_dir=test_session_dir,
        universe=["RELIANCE.NS", "TCS.NS"],
        initial_capital=500000.0,
        dry_run=True,
    )

    await runner.initialize_session()
    assert runner.evidence_logger.current_sequence_number >= 2

    # Feed ticks
    now = time.time()
    tick1 = NormalizedTick(
        symbol="RELIANCE.NS",
        ltp=2950.0,
        volume=1000,
        high=2955.0,
        low=2945.0,
        close=2948.0,
        bid=2949.5,
        ask=2950.5,
        timestamp=now,
    )
    await runner.on_tick_received(tick1)
    assert runner.session_stats["ticks_received"] == 1

    # Simulate paper trade execution from signal
    dummy_signal = SignalDecision(
        signal_id="SIG_TEST_001",
        candidate_id="CAND_TEST_001",
        symbol="RELIANCE.NS",
        direction=SignalDirection.LONG,
        entry=2950.0,
        stop_loss=StopLossResult(price=2920.0, method="ATR_STRUCTURAL", method_description="1.5x ATR"),
        targets=[TargetLevel(level=1, price=3000.0, method="RISK_REWARD", method_description="R:R 1.67", expected_rr=1.67)],
        position_size=PositionSizing(
            method="FIXED_RISK",
            capital=500000.0,
            risk_per_trade_pct=1.0,
            max_risk_amount=5000.0,
            entry_price=2950.0,
            stop_price=2920.0,
            risk_per_share=30.0,
            quantity=10,
            capital_required=29500.0,
            maximum_loss=300.0,
        ),
        opportunity_score=85.0,
        confidence=80.0,
    )

    await runner._execute_paper_trade(dummy_signal)
    assert runner.session_stats["paper_fills"] == 1
    assert runner.session_stats["positions_opened"] == 1
    assert len(runner.paper_engine.positions) == 1

    # Feed tick hitting target price 3000.0
    tick_target = NormalizedTick(
        symbol="RELIANCE.NS",
        ltp=3005.0,
        volume=1200,
        high=3010.0,
        low=2990.0,
        close=2995.0,
        timestamp=now + 60,
    )
    await runner.on_tick_received(tick_target)

    # Position should be closed on target hit
    assert runner.session_stats["positions_closed"] == 1
    assert runner.session_stats["winning_trades"] == 1
    assert runner.session_stats["gross_pnl"] > 0

    # Stop runner
    await runner.stop()

    # Verify master log file
    master_file = runner.evidence_logger.log_file
    assert os.path.exists(master_file)
    verify_code = verify_log_command(master_file)
    assert verify_code == 0
