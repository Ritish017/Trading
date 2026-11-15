"""
Tests for APEX Institutional Circuit Breaker, Pre-Trade Discipline Gate & Backtest Quality Gate
==============================================================================================
Validates exact behavior adapted from `tradermonty/claude-trading-skills`.
"""

import time
import pytest
from backend.app.signal_engine.circuit_breaker import (
    InstitutionalCircuitBreaker,
    PreTradeDisciplineGate,
    CircuitBreakerStatus,
    DisciplineGateDecision,
)
from backend.app.signal_engine.backtest_gate import (
    evaluate_backtest_robustness,
    score_sample_size,
    score_expectancy,
    score_risk_management,
    score_robustness,
    score_execution_realism,
    calc_expectancy,
    calc_profit_factor,
)


def test_circuit_breaker_nominal_state():
    cb = InstitutionalCircuitBreaker(account_size=10000.0, max_daily_loss_pct=2.0)
    status, reason = cb.evaluate(current_day_pnl=0.0)
    assert status == CircuitBreakerStatus.TRADING_ALLOWED
    assert "nominal" in reason.lower()
    assert cb.consecutive_losses == 0


def test_circuit_breaker_daily_loss_halt():
    cb = InstitutionalCircuitBreaker(account_size=10000.0, max_daily_loss_pct=2.0)
    # Threshold is ₹200.00
    status, reason = cb.evaluate(current_day_pnl=-199.0)
    assert status == CircuitBreakerStatus.TRADING_ALLOWED

    status, reason = cb.evaluate(current_day_pnl=-200.0)
    assert status == CircuitBreakerStatus.HALTED_DAILY
    assert "Daily loss" in reason

    status, reason = cb.evaluate(current_day_pnl=-250.0)
    assert status == CircuitBreakerStatus.HALTED_DAILY


def test_circuit_breaker_consecutive_loss_cooldown():
    cb = InstitutionalCircuitBreaker(account_size=10000.0, losing_streak_threshold=2, cooldown_seconds=86400.0)
    
    # 1st loss: streak = 1
    cb.record_trade_exit("T1", "NIFTY 50", realized_pnl=-50.0)
    assert cb.consecutive_losses == 1
    status, _ = cb.evaluate(current_day_pnl=-50.0)
    assert status == CircuitBreakerStatus.TRADING_ALLOWED

    # 2nd loss: streak = 2 -> triggers 24h cooldown
    cb.record_trade_exit("T2", "NIFTY 50", realized_pnl=-60.0)
    assert cb.consecutive_losses == 2
    status, reason = cb.evaluate(current_day_pnl=-110.0)
    assert status == CircuitBreakerStatus.COOLDOWN
    assert "cooldown" in reason.lower() or "cooling-off" in reason.lower()


def test_circuit_breaker_win_resets_streak():
    cb = InstitutionalCircuitBreaker(account_size=10000.0, losing_streak_threshold=2)
    cb.record_trade_exit("T1", "NIFTY 50", realized_pnl=-50.0)
    assert cb.consecutive_losses == 1
    
    # Win resets counter
    cb.record_trade_exit("T2", "NIFTY 50", realized_pnl=120.0)
    assert cb.consecutive_losses == 0
    status, _ = cb.evaluate(current_day_pnl=70.0)
    assert status == CircuitBreakerStatus.TRADING_ALLOWED


def test_pre_trade_discipline_gate_checks():
    cb = InstitutionalCircuitBreaker(account_size=10000.0, max_position_debit=3500.0, max_lot_size=25)
    gate = PreTradeDisciplineGate(circuit_breaker=cb)

    # 1. Nominal trade passes
    decision, reason = gate.check_trade(
        strategy_name="IRON_CONDOR",
        symbol="NIFTY 50",
        order_intent="ENTRY_READY",
        entry_price=120.0,
        stop_price=100.0,
        quantity=25,
        estimated_debit=1500.0,
    )
    assert decision == DisciplineGateDecision.GO

    # 2. Undefined stop loss rejected
    decision, reason = gate.check_trade(
        strategy_name="NAKED_CALL",
        symbol="NIFTY 50",
        order_intent="ENTRY_READY",
        entry_price=120.0,
        stop_price=None,
        quantity=25,
        estimated_debit=1500.0,
    )
    assert decision == DisciplineGateDecision.NO_GO
    assert "stop loss" in reason.lower()

    # 3. Oversized debit rejected (Micro-cap protection)
    decision, reason = gate.check_trade(
        strategy_name="EXPENSIVE_SPREAD",
        symbol="NIFTY 50",
        order_intent="ENTRY_READY",
        entry_price=180.0,
        stop_price=160.0,
        quantity=25,
        estimated_debit=4200.0,  # > ₹3,500 limit
    )
    assert decision == DisciplineGateDecision.NO_GO
    assert "exceeds micro-cap limit" in reason.lower()

    # 4. Oversized lot quantity rejected (> 25 qty)
    decision, reason = gate.check_trade(
        strategy_name="MULTI_LOT",
        symbol="NIFTY 50",
        order_intent="ENTRY_READY",
        entry_price=120.0,
        stop_price=100.0,
        quantity=50,  # 2 lots
        estimated_debit=2000.0,
    )
    assert decision == DisciplineGateDecision.NO_GO
    assert "single-lot ceiling" in reason.lower()

    # 5. Circuit breaker halt propagates to veto trade
    cb.status = CircuitBreakerStatus.HALTED_DAILY
    cb.halt_reason = "Daily loss limit breached"
    decision, reason = gate.check_trade(
        strategy_name="IRON_CONDOR",
        symbol="NIFTY 50",
        order_intent="ENTRY_READY",
        entry_price=120.0,
        stop_price=100.0,
        quantity=25,
        estimated_debit=1000.0,
    )
    assert decision == DisciplineGateDecision.NO_GO
    assert "Circuit Breaker Gate Veto" in reason


def test_backtest_gate_scoring_and_red_flags():
    # Robust institutional strategy
    res_good = evaluate_backtest_robustness(
        total_trades=120,
        win_rate=65.0,
        avg_win_pct=2.2,
        avg_loss_pct=1.0,
        max_drawdown_pct=12.5,
        years_tested=5,
        num_parameters=3,
        slippage_tested=True,
    )
    assert res_good.total_score >= 70
    assert res_good.verdict == "Deploy"
    assert len(res_good.red_flags) == 0
    assert res_good.profit_factor > 2.0

    # Under-sampled overfitted strategy
    res_bad = evaluate_backtest_robustness(
        total_trades=15,          # < 30 minimum
        win_rate=80.0,
        avg_win_pct=1.5,
        avg_loss_pct=1.0,
        max_drawdown_pct=52.0,    # Catastrophic drawdown
        years_tested=1,
        num_parameters=9,         # Overfitted
        slippage_tested=False,
    )
    assert res_bad.verdict == "Abandon"
    assert any("insufficient sample size" in f.lower() for f in res_bad.red_flags)
    assert any("catastrophic drawdown" in f.lower() for f in res_bad.red_flags)
    assert any("overfitting" in f.lower() for f in res_bad.red_flags)
