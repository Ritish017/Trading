"""
ACCEPTANCE SUITE: Paper Trading & Accounting Red Team
Validates controlled trades (buy 1, buy 100, partial sell, full sell),
accounting invariants, duplicate execution idempotency, and margin rejection.
"""

import pytest
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.paper_engine.bridge import calculate_indian_equity_frictions


def test_controlled_trades_and_partial_close_lifecycle():
    """Validates buy 1, buy 100, partial close, and remaining close."""
    engine = PaperTradingEngine(initial_capital=1000000.0, slippage_pct=0.05)

    # 1. Buy 1 share of RELIANCE at ₹2500
    req1 = PaperOrderRequest(
        symbol="RELIANCE.NS",
        side="BUY",
        quantity=1,
        price=2500.0,
        productType="CNC",
    )
    res1 = engine.execute_order(req1)
    assert res1["status"] == "FILLED"
    pos1_id = res1["position"]["id"]
    assert engine.positions[pos1_id]["quantity"] == 1

    # 2. Buy 100 shares of INFY at ₹1500
    req2 = PaperOrderRequest(
        symbol="INFY.NS",
        side="BUY",
        quantity=100,
        price=1500.0,
        productType="CNC",
    )
    res2 = engine.execute_order(req2)
    assert res2["status"] == "FILLED"
    pos2_id = res2["position"]["id"]
    assert engine.positions[pos2_id]["quantity"] == 100

    capital_before_partial = engine.capital

    # 3. Partial sell: Close 40 out of 100 shares of INFY at ₹1600 (Profit)
    close_partial = engine.close_position(pos2_id, close_price=1600.0, close_quantity=40)
    assert close_partial["status"] == "PARTIALLY_CLOSED"
    assert close_partial["closed_quantity"] == 40
    assert close_partial["remaining_quantity"] == 60
    assert engine.positions[pos2_id]["quantity"] == 60
    assert close_partial["realized_pnl"] > 0
    assert engine.capital > capital_before_partial

    capital_before_full = engine.capital

    # 4. Full sell: Close remaining 60 shares of INFY at ₹1550
    close_full = engine.close_position(pos2_id, close_price=1550.0, close_quantity=60)
    assert close_full["status"] == "CLOSED"
    assert close_full["remaining_quantity"] == 0
    assert pos2_id not in engine.positions
    assert close_full["realized_pnl"] > 0
    assert engine.capital > capital_before_full

    # Close pos1
    engine.close_position(pos1_id, close_price=2600.0)
    assert len(engine.positions) == 0
    assert len(engine.closed_trades) == 3


def test_accounting_invariants_and_friction_deductions():
    """Validates accounting invariants for winning and losing trades."""
    engine = PaperTradingEngine(initial_capital=500000.0, slippage_pct=0.0)

    # Place buy order
    buy_order = PaperOrderRequest(
        symbol="TCS.NS",
        side="BUY",
        quantity=10,
        price=3500.0,
        productType="CNC",
    )
    buy_res = engine.execute_order(buy_order)
    assert buy_res["status"] == "FILLED"
    pos_id = buy_res["position"]["id"]
    entry_fees = buy_res["fill"]["fees"]

    # Sell at loss (₹3400)
    close_res = engine.close_position(pos_id, close_price=3400.0)
    assert close_res["status"] == "CLOSED"
    trade = close_res["trade"]

    # Gross loss = (3400 - 3500) * 10 = -1000.0
    assert trade["grossPnL"] == -1000.0
    # Net realized PnL = grossPnL - exit_fees
    assert trade["realizedPnL"] == round(-1000.0 - trade["exit_frictions"]["total_fees"], 2)


def test_order_idempotency_prevents_duplicate_execution():
    """Attack: Retrying the exact same order with idempotency_key must return cached fill and never double debit."""
    engine = PaperTradingEngine(initial_capital=500000.0)
    idempotency_key = "idemp_test_retry_key_9999"

    req = PaperOrderRequest(
        symbol="HDFCBANK.NS",
        side="BUY",
        quantity=10,
        price=1600.0,
        productType="CNC",
        idempotency_key=idempotency_key,
    )

    # First attempt
    res1 = engine.execute_order(req)
    assert res1["status"] == "FILLED"
    capital_after_first = engine.capital
    assert len(engine.positions) == 1

    # Second attempt with same idempotency key (simulating network retry)
    res2 = engine.execute_order(req)
    assert res2["status"] == "FILLED"
    assert res2.get("is_idempotent_replay") is True
    assert res2["order_id"] == res1["order_id"]
    assert res2["fill_id"] == res1["fill_id"]

    # Invariant: capital must NOT be debited twice
    assert engine.capital == capital_after_first
    # Invariant: no duplicate position created
    assert len(engine.positions) == 1


def test_margin_rejection_when_capital_insufficient():
    """Attack: Ordering more than available capital must be rejected cleanly without exception."""
    engine = PaperTradingEngine(initial_capital=10000.0)

    # Attempt to buy ₹1,00,000 worth with only ₹10,000 capital
    req = PaperOrderRequest(
        symbol="MRF.NS",
        side="BUY",
        quantity=1,
        price=100000.0,
        productType="CNC",
    )
    res = engine.execute_order(req)
    assert res["status"] == "REJECTED"
    assert "Insufficient margin" in res["reason"]
    assert engine.capital == 10000.0
    assert len(engine.positions) == 0
