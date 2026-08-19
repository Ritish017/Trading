"""
Unit Test Suite — APEX Paper Trading Bridge & Data Validation (Phase 8)
=======================================================================
Verifies:
1. Deterministic PaperSignal generation from canonical StrategyResult.
2. Next-bar execution semantics & cash balance accounting.
3. Indian equity transaction frictions (STT, Brokerage, Exchange, SEBI, GST, Slippage).
4. Mark-to-market position updates & Stop Loss / Take Profit triggers.
5. PaperTradeAudit forensic log creation upon closing.
6. Research lifecycle transitions & validation promotion gates.
7. Model drift detection & warning thresholds.
8. Backtest vs Paper Replay equivalence verification.
9. Data health monitoring states & zero-mock leakage.
10. Paper Copilot interrogation & Skeptic Mode.
"""

import pytest
import time
from backend.app.paper_engine.models import (
    ResearchLifecycleState,
    OrderSide,
    PositionStatus,
    ExitReason,
    PaperSignal,
)
from backend.app.paper_engine.bridge import (
    PaperTradingBridge,
    calculate_indian_equity_frictions,
)
from backend.app.paper_engine.drift_engine import (
    ModelDriftDetector,
    PaperBacktestReplayValidator,
)
from backend.app.paper_engine.lifecycle_manager import (
    ResearchLifecycleManager,
)
from backend.app.data_engine.health_monitor import (
    DataHealthMonitor,
    FeedState,
)
from backend.app.strategy_engine.dsl import StrategyState
from backend.app.ai_engine.agents import PaperCopilotAgent


# ---------------------------------------------------------------------------
# 1. Indian Equity Transaction Frictions
# ---------------------------------------------------------------------------

def test_indian_equity_frictions_calculation():
    # Buy 100 shares of RELIANCE at ₹2500 -> Turnover = ₹250,000
    frictions = calculate_indian_equity_frictions(price=2500.0, quantity=100, is_buy=True, slippage_pct=0.05)
    assert frictions["turnover"] == 250000.0
    assert frictions["brokerage"] == 20.0  # Capped at ₹20
    assert frictions["stt"] == 250.0       # 0.1% of turnover
    assert frictions["exchange_charges"] > 0
    assert frictions["sebi_charges"] > 0
    assert frictions["gst"] > 0            # 18% on fees
    assert frictions["stamp_duty"] > 0     # 0.015% on buy
    assert frictions["slippage"] == 125.0  # 0.05% of turnover
    assert frictions["total_friction"] > 0


# ---------------------------------------------------------------------------
# 2. Deterministic Paper Signal Generation
# ---------------------------------------------------------------------------

def test_paper_signal_generation_from_strategy():
    bridge = PaperTradingBridge(initial_capital=500000.0)

    strat_res = {
        "strategy_id": "EMA_TREND_MOMENTUM",
        "symbol": "RELIANCE.NS",
        "timeframe": "1D",
        "state": StrategyState.ACTIVE,
        "version": "1.0.0",
        "timestamp": 1700000000,
        "matched_rules": [
            {
                "rule_id": "R1",
                "name": "EMA Fast > Slow",
                "condition": "GREATER_THAN",
                "indicator_a": "EMA_9",
                "indicator_b": "EMA_21",
                "rule_type": "ENTRY",
                "description": "Fast EMA above Slow EMA",
            }
        ],
        "primary_stop": 2450.0,
        "primary_target": 2600.0,
    }

    sig = bridge.generate_signal_from_strategy(
        strategy_result=strat_res,
        current_price=2500.0,
        confluence_state="HIGH_CONVICTION_LONG",
        fundamental_state="STRONG",
        regime="BULL_TREND",
        stop_loss=2450.0,
        take_profit=2600.0,
    )

    assert sig is not None
    assert sig.symbol == "RELIANCE.NS"
    assert sig.strategy_id == "EMA_TREND_MOMENTUM"
    assert sig.side == OrderSide.BUY
    assert sig.intended_price == 2500.0
    assert sig.stop_loss == 2450.0
    assert sig.take_profit == 2600.0
    assert len(sig.rule_evidence) == 1
    assert "EMA Fast > Slow" in sig.rule_evidence[0]


# ---------------------------------------------------------------------------
# 3. Next-Bar Execution Semantics & Position Mark-to-Market
# ---------------------------------------------------------------------------

def test_next_bar_execution_and_stop_loss_trigger():
    bridge = PaperTradingBridge(initial_capital=500000.0)

    sig = PaperSignal(
        signal_id="SIG_001",
        timestamp=1700000000,
        symbol="TCS.NS",
        timeframe="1D",
        strategy_id="RSI_MEAN_REVERSION",
        strategy_version="1.0.0",
        strategy_state="ACTIVE",
        side=OrderSide.BUY,
        intended_price=3500.0,
        stop_loss=3400.0,
        take_profit=3700.0,
    )

    # Next bar opens at ₹3510 on ts: 1700086400
    pos = bridge.execute_next_bar_entry(
        signal=sig,
        next_bar_open=3510.0,
        next_bar_timestamp=1700086400,
        allocation_amount=100000.0,
    )

    assert pos is not None
    assert pos.status == PositionStatus.OPEN
    assert pos.quantity == 28
    assert pos.entry_price > 3510.0  # Includes slippage
    assert bridge.available_cash < 500000.0

    # Bar 2 price dips below stop loss (Low: ₹3390)
    audits = bridge.update_positions_mark_to_market(
        symbol="TCS.NS",
        current_candle_high=3520.0,
        current_candle_low=3390.0,
        current_candle_close=3395.0,
        current_timestamp=1700172800,
    )

    assert len(audits) == 1
    audit = audits[0]
    assert audit.exit_reason == ExitReason.STOP_LOSS
    assert audit.net_pnl < 0
    assert pos.status == PositionStatus.CLOSED
    assert len(bridge.trade_audits) == 1


# ---------------------------------------------------------------------------
# 4. Research Lifecycle Promotion Gates
# ---------------------------------------------------------------------------

def test_research_lifecycle_promotion_gates():
    mgr = ResearchLifecycleManager()
    cand = mgr.get_candidate("CAND_EMA_TREND_MOMENTUM")
    assert cand is not None
    assert cand.lifecycle_state == ResearchLifecycleState.RESEARCH_CANDIDATE

    # Transition from RESEARCH_CANDIDATE to PAPER_TESTING succeeds because Sharpe=1.45 > 0.5
    ok, msg = mgr.transition_state(cand.candidate_id, ResearchLifecycleState.PAPER_TESTING, reason="Passed OOS testing")
    assert ok is True
    assert cand.lifecycle_state == ResearchLifecycleState.PAPER_TESTING

    # Attempting invalid jump from PAPER_TESTING to DRAFT fails
    ok_invalid, _ = mgr.transition_state(cand.candidate_id, ResearchLifecycleState.DRAFT)
    assert ok_invalid is False


# ---------------------------------------------------------------------------
# 5. Model Drift Detection
# ---------------------------------------------------------------------------

def test_model_drift_detection():
    bridge = PaperTradingBridge(initial_capital=500000.0)

    # Simulate 5 paper trades with degraded win rate
    for i in range(5):
        sig = PaperSignal(
            signal_id=f"SIG_{i}", timestamp=1700000000 + i*86400, symbol="INFY.NS", timeframe="1D",
            strategy_id="TEST_STRAT", strategy_version="1.0.0", strategy_state="ACTIVE",
            side=OrderSide.BUY, intended_price=1500.0, stop_loss=1400.0, take_profit=1600.0
        )
        pos = bridge.execute_next_bar_entry(sig, 1500.0, 1700000000 + i*86400, quantity=10)
        # Close with loss
        bridge.close_position(pos.position_id, exit_price=1450.0, exit_timestamp=1700000000 + i*86400 + 3600, exit_reason=ExitReason.STOP_LOSS)

    report = ModelDriftDetector.evaluate_drift(
        strategy_id="TEST_STRAT",
        backtest_metrics={"win_rate_pct": 60.0, "sharpe_ratio": 1.5, "avg_slippage": 20.0},
        paper_trades=bridge.trade_audits,
    )

    assert report.sample_size == 5
    assert report.overall_status in ["MODEL_DRIFT_ALERT", "MINOR_DRIFT"]
    assert len(report.metrics) > 0


# ---------------------------------------------------------------------------
# 6. Backtest vs Paper Replay Equivalence
# ---------------------------------------------------------------------------

def test_backtest_paper_replay_equivalence():
    bridge = PaperTradingBridge(initial_capital=500000.0)
    sig = PaperSignal(
        signal_id="SIG_REP_01", timestamp=1700000000, symbol="HDFCBANK.NS", timeframe="1D",
        strategy_id="EMA_TREND_MOMENTUM", strategy_version="1.0.0", strategy_state="ACTIVE",
        side=OrderSide.BUY, intended_price=1600.0
    )
    pos = bridge.execute_next_bar_entry(sig, 1600.0, 1700086400, quantity=50)
    audit = bridge.close_position(pos.position_id, 1650.0, 1700172800, ExitReason.TAKE_PROFIT)

    backtest_mock_trades = [
        {"symbol": "HDFCBANK.NS", "side": "BUY", "entry_price": 1600.0, "exit_price": 1650.0}
    ]

    res = PaperBacktestReplayValidator.verify_equivalence(
        backtest_trades=backtest_mock_trades,
        paper_trades=[audit],
    )

    assert res["is_equivalent"] is True
    assert res["status"] == "DETERMINISTIC_EQUIVALENCE_VERIFIED"


# ---------------------------------------------------------------------------
# 7. Data Health Monitoring
# ---------------------------------------------------------------------------

def test_data_health_monitor():
    rep = DataHealthMonitor.get_health_report(
        active_market_provider="UPSTOX",
        active_fundamental_provider="AUTHENTIC_FIXTURE_HUB",
        is_live_feed=True,
    )
    assert rep.overall_market_feed_state == FeedState.LIVE
    assert rep.active_market_provider == "UPSTOX"
    assert rep.tracked_symbols_count > 0
    assert "RELIANCE.NS" in rep.symbol_statuses


# ---------------------------------------------------------------------------
# 8. Paper Copilot Interrogation & Skeptic Mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paper_copilot_skeptic_mode():
    agent = PaperCopilotAgent()
    res = await agent.answer(
        symbol="RELIANCE.NS",
        user_message="CHALLENGE THIS SIGNAL",
        position={"entry_price": 2500.0, "fees_paid": 65.0, "slippage_paid": 50.0, "unrealized_pnl": 120.0},
        signal={"strategy_id": "EMA_TREND_MOMENTUM", "strategy_version": "1.0.0", "strategy_state": "ACTIVE", "regime": "SIDEWAYS"},
        drift_report={"overall_status": "MODEL_DRIFT_ALERT"},
        is_skeptic_mode=True,
    )
    assert "reply" in res
    assert "Skeptic" in res["reply"] or "Friction" in res["reply"] or "Drift" in res["reply"]
