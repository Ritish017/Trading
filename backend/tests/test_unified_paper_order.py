import pytest
from backend.app.paper_trading.canonical_order import (
    CanonicalOrder,
    CanonicalFill,
    OrderState,
    validate_order_transition,
)
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.paper_engine.bridge import calculate_indian_equity_frictions


def test_canonical_order_state_transitions():
    """Verify valid state progression: CREATED -> VALIDATED -> ACCEPTED -> FILLED."""
    order = CanonicalOrder(
        order_id="ORD_STATE_01",
        symbol="RELIANCE.NS",
        side="BUY",
        quantity=10,
        requested_price=2500.0,
    )
    assert order.status == OrderState.CREATED

    order.transition_to(OrderState.VALIDATED)
    assert order.status == OrderState.VALIDATED

    order.transition_to(OrderState.ACCEPTED)
    assert order.status == OrderState.ACCEPTED

    order.transition_to(OrderState.FILLED)
    assert order.status == OrderState.FILLED
    assert order.filled_at is not None


def test_order_state_machine_illegal_transitions():
    """
    ORDER STATE MACHINE TEST:
    Verify that illegal state progressions are strictly rejected with ValueError.
    FILLED -> CREATED
    CANCELLED -> FILLED
    REJECTED -> ACCEPTED
    ACCEPTED -> CREATED
    """
    # 1. FILLED -> CREATED
    filled_order = CanonicalOrder(
        order_id="ORD_FILLED",
        symbol="INFY.NS",
        side="BUY",
        quantity=5,
        requested_price=1500.0,
        status=OrderState.FILLED
    )
    with pytest.raises(ValueError, match="Illegal order state transition"):
        filled_order.transition_to(OrderState.CREATED)

    with pytest.raises(ValueError, match="Illegal order state transition"):
        filled_order.transition_to(OrderState.ACCEPTED)

    # 2. CANCELLED -> FILLED
    cancelled_order = CanonicalOrder(
        order_id="ORD_CANCELLED",
        symbol="INFY.NS",
        side="BUY",
        quantity=5,
        requested_price=1500.0,
        status=OrderState.CANCELLED
    )
    with pytest.raises(ValueError, match="Illegal order state transition"):
        cancelled_order.transition_to(OrderState.FILLED)

    # 3. REJECTED -> ACCEPTED
    rejected_order = CanonicalOrder(
        order_id="ORD_REJECTED",
        symbol="INFY.NS",
        side="BUY",
        quantity=5,
        requested_price=1500.0,
        status=OrderState.REJECTED
    )
    with pytest.raises(ValueError, match="Illegal order state transition"):
        rejected_order.transition_to(OrderState.ACCEPTED)

    # 4. ACCEPTED -> CREATED
    accepted_order = CanonicalOrder(
        order_id="ORD_ACCEPTED",
        symbol="INFY.NS",
        side="BUY",
        quantity=5,
        requested_price=1500.0,
        status=OrderState.ACCEPTED
    )
    with pytest.raises(ValueError, match="Illegal order state transition"):
        accepted_order.transition_to(OrderState.CREATED)


def test_independent_friction_certification():
    """
    FRICTION CERTIFICATION:
    Independently verify all statutory Indian equity transaction friction formulas:
    Brokerage, STT, Exchange charges, SEBI fee, GST, Stamp duty, Slippage.
    """
    price = 2500.0
    quantity = 20
    turnover = price * quantity  # ₹50,000

    # BUY transaction
    frictions_buy = calculate_indian_equity_frictions(price, quantity, is_buy=True, slippage_pct=0.05)

    expected_brokerage = min(20.0, turnover * 0.0005)  # ₹20.0
    expected_stt = turnover * 0.001                      # ₹50.0 (0.1% delivery)
    expected_exchange = turnover * 0.0000345             # ₹1.725
    expected_sebi = turnover * 0.000001                  # ₹0.05
    expected_gst = (expected_brokerage + expected_exchange + expected_sebi) * 0.18  # ₹3.92
    expected_stamp = turnover * 0.00015                  # ₹7.50 (0.015% on buy)
    expected_slippage = (0.05 / 100.0) * turnover        # ₹25.0

    assert pytest.approx(frictions_buy["brokerage"], 0.01) == expected_brokerage
    assert pytest.approx(frictions_buy["stt"], 0.01) == expected_stt
    assert pytest.approx(frictions_buy["exchange_charges"], 0.01) == expected_exchange
    assert pytest.approx(frictions_buy["sebi_charges"], 0.01) == expected_sebi
    assert pytest.approx(frictions_buy["gst"], 0.01) == expected_gst
    assert pytest.approx(frictions_buy["stamp_duty"], 0.01) == expected_stamp
    assert pytest.approx(frictions_buy["slippage"], 0.01) == expected_slippage

    # SELL transaction (no stamp duty on sell in Indian equities)
    frictions_sell = calculate_indian_equity_frictions(price, quantity, is_buy=False, slippage_pct=0.05)
    assert frictions_sell["stamp_duty"] == 0.0


def test_accounting_profit_and_loss_lifecycle():
    """
    ACCOUNTING TESTS:
    Verify cash changes, position changes, fee deductions, and realized P&L
    across both winning and losing trades.
    """
    engine = PaperTradingEngine(initial_capital=500000.0)

    # 1. Profitable Trade: Buy 10 @ 1000, Sell 10 @ 1100
    buy_req = PaperOrderRequest(
        symbol="TATASTEEL.NS",
        productType="CNC",
        side="BUY",
        quantity=10,
        price=1000.0,
    )
    res_buy = engine.execute_order(buy_req)
    assert res_buy["status"] == "FILLED"
    pos_id = res_buy["position"]["id"]

    # Cash must decrease by margin + entry fees
    entry_frictions = res_buy["position"]["frictions"]
    expected_cash_after_buy = 500000.0 - 10000.0 - entry_frictions["total_fees"]
    assert pytest.approx(engine.capital, 0.05) == expected_cash_after_buy

    # Close with profit
    close_res = engine.close_position(pos_id, close_price=1100.0)
    assert close_res["status"] == "CLOSED"
    assert close_res["realized_pnl"] > 0
    # Gross profit was 10 * 100 = 1000, net profit is 1000 - entry_fees - exit_fees
    net_pnl = close_res["realized_pnl"]
    assert 900.0 < net_pnl < 1000.0

    # Final cash must exceed initial capital due to profit
    assert engine.capital > 500000.0

    # 2. Losing Trade: Buy 10 @ 2000, Sell 10 @ 1900
    cap_before_losing = engine.capital
    buy_req_2 = PaperOrderRequest(
        symbol="WIPRO.NS",
        productType="CNC",
        side="BUY",
        quantity=10,
        price=2000.0,
    )
    res_buy_2 = engine.execute_order(buy_req_2)
    pos_id_2 = res_buy_2["position"]["id"]

    close_res_2 = engine.close_position(pos_id_2, close_price=1900.0)
    assert close_res_2["status"] == "CLOSED"
    assert close_res_2["realized_pnl"] < -1000.0  # Loss includes gross loss -1000 minus frictions
    assert engine.capital < cap_before_losing


def test_unified_paper_engine_margin_rejection():
    """Verify paper engine rejects orders that exceed available cash."""
    engine = PaperTradingEngine(initial_capital=10000.0)

    req = PaperOrderRequest(
        symbol="RELIANCE.NS",
        productType="CNC",
        side="BUY",
        quantity=100,  # 100 * 2500 = 250,000 > 10,000
        price=2500.0,
    )
    res = engine.execute_order(req)
    assert res["status"] == "REJECTED"
    assert "Insufficient margin" in res["reason"]
    assert engine.capital == 10000.0
