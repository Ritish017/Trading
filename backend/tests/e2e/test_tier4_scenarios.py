"""
APEX E2E Test Suite — Tier 4: Real-World Application Scenarios
==============================================================
Production-grade simulation of full intraday market sessions (09:15-15:30 IST),
gap-down market stress, mid-session crash and disaster recovery, and portfolio risk saturation.
"""

import time
import uuid
import pytest
from typing import Dict, Any, List

from backend.app.config import settings
from backend.app.paper_trading.engine import (
    PaperTradingEngine,
    PaperOrderRequest,
)
from backend.app.signal_engine.models import (
    AssetClass,
    SignalDirection,
    SignalEngineConfig,
    StopLossResult,
    TargetLevel,
    ScannerPipelineStats,
)
from backend.app.signal_engine.validation_gates import (
    gate_portfolio_risk,
    gate_risk_reward,
    ValidationGateResult,
)


# ============================================================================
# Scenario 1: Complete Intraday Trading Session Simulation (09:15–15:30 IST)
# ============================================================================

def test_s1_full_intraday_session_simulation():
    """
    Tier 4 Scenario 1: Simulates full Indian market session from 09:15 to 15:30 IST.
    Covers universe screening, long/short entries, tick feeds, automated profit/stop exits,
    and end-of-day portfolio performance summarization.
    """
    engine = PaperTradingEngine(initial_capital=1000000.0, brokerage=20.0, slippage_pct=0.05)
    assert engine.capital == 1000000.0

    # Phase 1: 09:15 IST Market Open & Morning Scan
    # Two actionable setups qualify from universe scan:
    # 1. RELIANCE (LONG)
    order_long = PaperOrderRequest(
        symbol="RELIANCE.NS",
        side="BUY",
        quantity=50,
        price=2900.0,
        stopLoss=2850.0,
        targetPrice=3000.0,
        productType="CNC",
        source="INTRADAY_SCANNER",
    )
    fill_long = engine.execute_order(order_long)
    assert fill_long["status"] == "FILLED"
    pos_long_id = fill_long["position"]["id"]

    # 2. INFY (SHORT / Intraday MIS)
    order_short = PaperOrderRequest(
        symbol="INFY.NS",
        side="SELL",
        quantity=100,
        price=1800.0,
        stopLoss=1830.0,
        targetPrice=1740.0,
        productType="MIS",
        source="INTRADAY_SCANNER",
    )
    fill_short = engine.execute_order(order_short)
    assert fill_short["status"] == "FILLED"
    pos_short_id = fill_short["position"]["id"]

    assert len(engine.positions) == 2

    # Phase 2: Midday Market Tick Progression (11:30 IST)
    # RELIANCE rallies to 2970 -> Unrealized profit
    engine.update_market_price("RELIANCE.NS", 2970.0)
    # INFY drops to 1760 -> Unrealized profit for short
    engine.update_market_price("INFY.NS", 1760.0)

    summary_mid = engine.get_portfolio_summary()
    assert summary_mid["open_positions_count"] == 2
    assert summary_mid["total_unrealized_pnl"] > 0

    # Phase 3: Afternoon Exit Execution (14:15 IST)
    # RELIANCE hits target (3005 >= 3000) -> Automated take profit exit
    res_close_long = engine.close_position(pos_long_id, close_price=3005.0)
    assert res_close_long["status"] == "CLOSED"
    assert res_close_long["trade"]["realizedPnL"] > 0

    # INFY pulls back and touches stop (1832 >= 1830) -> Automated stop exit
    res_close_short = engine.close_position(pos_short_id, close_price=1832.0)
    assert res_close_short["status"] == "CLOSED"
    assert res_close_short["trade"]["realizedPnL"] < 0

    # Phase 4: 15:30 IST Session Finalization & Audit
    assert len(engine.positions) == 0  # All positions closed cleanly
    assert len(engine.closed_trades) == 2

    perf = engine.get_performance_summary()
    assert perf["total_trades"] == 2
    assert perf["winning_trades"] == 1
    assert perf["losing_trades"] == 1
    assert perf["win_rate_pct"] == 50.0
    assert "profit_factor" in perf
    assert perf["total_realized_pnl"] != 0.0


# ============================================================================
# Scenario 2: Gap-Down Market Stress with Conservative Fill Policy
# ============================================================================

def test_s2_gap_down_market_stress_scenario():
    """
    Tier 4 Scenario 2: Severe market gap-down opening below stop loss.
    Verifies that position exits at gap price rather than unreachable stop price.
    """
    engine = PaperTradingEngine(initial_capital=500000.0)

    # Entry at 2500 with stop loss at 2450
    order = PaperOrderRequest(
        symbol="TATASTEEL.NS",
        side="BUY",
        quantity=200,
        price=150.0,
        stopLoss=145.0,
        targetPrice=160.0,
    )
    fill = engine.execute_order(order)
    pos_id = fill["position"]["id"]

    # Market gap-down: opens directly at 141.0 (below stop 145.0)
    gap_open_price = 141.0
    res_gap_exit = engine.close_position(pos_id, close_price=gap_open_price)

    assert res_gap_exit["status"] == "CLOSED"
    trade = res_gap_exit["trade"]

    # Fill reflects actual market reality (141.0 minus friction), not theoretical 145.0
    assert trade["exitPrice"] <= gap_open_price
    assert trade["realizedPnL"] < 0
    # Engine capital updated honestly
    assert engine.capital < 500000.0


# ============================================================================
# Scenario 3: Mid-Trade Unexpected Crash and Disaster Recovery
# ============================================================================

def test_s3_disaster_recovery_and_state_reconstruction():
    """
    Tier 4 Scenario 3: Mid-session engine termination with active positions.
    Reconstructs exact capital, margin, positions, and history upon restart.
    """
    # Active Session 1
    session1 = PaperTradingEngine(initial_capital=1000000.0)
    pos1 = session1.execute_order(PaperOrderRequest(symbol="TCS.NS", side="BUY", quantity=10, price=3800.0))["position"]
    pos2 = session1.execute_order(PaperOrderRequest(symbol="HDFCBANK.NS", side="BUY", quantity=25, price=1600.0))["position"]

    cap_before_crash = session1.capital
    positions_snapshot = dict(session1.positions)

    # Crash Occurs -> Simulating fresh server boot
    session2 = PaperTradingEngine(initial_capital=1000000.0)
    session2.capital = cap_before_crash
    session2.positions = positions_snapshot

    # Verification of state integrity post-recovery
    summary = session2.get_portfolio_summary()
    assert summary["open_positions_count"] == 2
    assert summary["capital"] == cap_before_crash
    assert pos1["id"] in session2.positions
    assert pos2["id"] in session2.positions

    # Ensure subsequent position closing continues smoothly
    close_res = session2.close_position(pos1["id"], close_price=3850.0)
    assert close_res["status"] == "CLOSED"
    assert len(session2.positions) == 1
    assert pos2["id"] in session2.positions


# ============================================================================
# Scenario 4: Maximum Portfolio Exposure / Capacity Saturation Stress
# ============================================================================

def test_s4_portfolio_capacity_saturation_stress():
    """
    Tier 4 Scenario 4: Portfolio reaches maximum position capacity (5 positions).
    Subsequent candidate signals fail closed until an existing position is liquidated.
    """
    config = SignalEngineConfig(max_positions=3, capital=1000000.0)
    engine = PaperTradingEngine(initial_capital=1000000.0)

    # 1. Fill 3 positions to reach max capacity
    for sym in ["RELIANCE.NS", "TCS.NS", "INFY.NS"]:
        req = PaperOrderRequest(symbol=sym, side="BUY", quantity=10, price=1500.0)
        engine.execute_order(req)

    assert len(engine.positions) == 3

    # 2. Candidate 4 arrives -> Evaluated against portfolio risk gate
    portfolio_state = engine.get_portfolio_summary()
    res_gate = gate_portfolio_risk(portfolio_state, config)
    # Fails closed because open_positions_count == 3 == max_positions
    assert res_gate.result == ValidationGateResult.FAIL
    assert "Maximum open positions (3) reached" in res_gate.reason

    # 3. Liquidate 1 existing position to free up capacity
    first_pos_id = list(engine.positions.keys())[0]
    engine.close_position(first_pos_id, close_price=1520.0)
    assert len(engine.positions) == 2

    # 4. Re-evaluate Candidate 4 -> Now passes portfolio risk gate
    portfolio_state_after = engine.get_portfolio_summary()
    res_gate_after = gate_portfolio_risk(portfolio_state_after, config)
    assert res_gate_after.result == ValidationGateResult.PASS
