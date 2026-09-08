"""
F&O Decision Engine & Transaction Cost Unit & Invariant Tests
============================================================
Tests for:
1. Centralized TransactionCostCalculator across all 4 asset classes.
2. FuturesEngine decision rules (BUY_FUTURE, SELL_FUTURE, NO_TRADE).
3. OptionsEngine decision rules (BUY_CALL, BUY_PUT, SPREADS, OPTIONS_DATA_INSUFFICIENT).
4. Black-Scholes Greeks invariants (Delta, Gamma, Theta, Vega).
"""

import pytest
from backend.app.signal_engine.transaction_cost import (
    TransactionCostCalculator, AssetClass, OrderSide
)
from backend.app.signal_engine.futures_engine import (
    FuturesEngine, FuturesAction, OpenInterestPattern
)
from backend.app.signal_engine.options_engine import (
    OptionsEngine, OptionAction, calculate_black_scholes_greeks
)


# ---------------------------------------------------------------------------
# Transaction Cost Tests
# ---------------------------------------------------------------------------

def test_equity_delivery_costs():
    """Verify delivery costs: STT 0.1% on buy and sell, stamp duty 0.015% on buy."""
    cost = TransactionCostCalculator.calculate_roundtrip(
        asset_class=AssetClass.EQUITY_DELIVERY,
        entry_price=1000.0,
        exit_price=1100.0,
        quantity=100,
        is_long=True,
    )
    assert cost.turnover == 210000.0
    assert cost.brokerage == 40.0  # ₹20 * 2
    assert cost.stt == 210.0       # 0.1% of 210,000
    assert cost.stamp_duty == pytest.approx(15.0, 0.01) # 0.015% of 100,000 (buy leg)
    assert cost.gst > 0
    assert cost.total_cost > cost.brokerage


def test_equity_intraday_costs():
    """Verify intraday costs: STT only on sell leg (0.025%)."""
    cost = TransactionCostCalculator.calculate_roundtrip(
        asset_class=AssetClass.EQUITY_INTRADAY,
        entry_price=1000.0,
        exit_price=1050.0,
        quantity=100,
        is_long=True,
    )
    # Sell leg turnover = 105,000. STT = 105,000 * 0.00025 = 26.25
    assert cost.stt == pytest.approx(26.25, 0.01)
    assert cost.stamp_duty == pytest.approx(3.0, 0.01)  # 0.003% of 100,000


def test_futures_costs():
    """Verify futures costs: flat ₹20 brokerage, STT 0.02% on sell."""
    cost = TransactionCostCalculator.calculate_roundtrip(
        asset_class=AssetClass.FUTURES,
        entry_price=20000.0,
        exit_price=20200.0,
        quantity=50,  # 1 lot Nifty
        is_long=True,
    )
    assert cost.brokerage == 40.0
    # Sell leg = 20,200 * 50 = 1,010,000. STT = 1,010,000 * 0.0002 = 202.0
    assert cost.stt == pytest.approx(202.0, 0.01)
    assert cost.stamp_duty == pytest.approx(20.0, 0.01) # 0.002% of 1,000,000


def test_options_costs():
    """Verify options costs: STT on sell premium."""
    cost = TransactionCostCalculator.calculate_roundtrip(
        asset_class=AssetClass.OPTIONS,
        entry_price=150.0,
        exit_price=250.0,
        quantity=100,
        is_long=True,
    )
    assert cost.brokerage == 40.0
    # Sell leg premium = 250 * 100 = 25,000. STT = 25,000 * 0.001 = 25.0
    assert cost.stt == pytest.approx(25.0, 0.01)


# ---------------------------------------------------------------------------
# Futures Engine Tests
# ---------------------------------------------------------------------------

def test_futures_engine_buy_decision():
    """Verify qualified LONG underlying produces BUY_FUTURE."""
    decision = FuturesEngine.analyze(
        symbol="RELIANCE",
        underlying_direction="LONG",
        spot_price=2500.0,
        futures_price=2510.0,  # Mild contango (+0.4%)
        days_to_expiry=15,
        oi=50000,
        volume=50000,
        lot_size=250,
        underlying_stop=2460.0,
        underlying_target_1=2580.0,
        underlying_target_2=2620.0,
        oi_change_pct=5.0,     # Long buildup
        available_capital=1000000.0,
    )
    assert decision.action == FuturesAction.BUY_FUTURE
    assert decision.is_valid is True
    assert decision.recommended_lots >= 1
    assert decision.stop_loss == 2470.0  # Adjusted by basis
    assert decision.risk_reward_ratio >= 1.5


def test_futures_engine_sell_decision():
    """Verify qualified SHORT underlying produces SELL_FUTURE."""
    decision = FuturesEngine.analyze(
        symbol="TCS",
        underlying_direction="SHORT",
        spot_price=3500.0,
        futures_price=3495.0,
        days_to_expiry=12,
        oi=40000,
        volume=35000,
        lot_size=175,
        underlying_stop=3550.0,
        underlying_target_1=3400.0,
        underlying_target_2=3350.0,
        oi_change_pct=6.0,     # Short buildup
        available_capital=1000000.0,
    )
    assert decision.action == FuturesAction.SELL_FUTURE
    assert decision.is_valid is True
    assert decision.stop_loss > decision.entry_price


def test_futures_engine_rejects_on_low_liquidity():
    """Verify rejection when volume/OI is insufficient."""
    decision = FuturesEngine.analyze(
        symbol="ILLIQUID",
        underlying_direction="LONG",
        spot_price=500.0,
        futures_price=502.0,
        days_to_expiry=10,
        oi=100,                # Insufficient OI
        volume=20,             # Insufficient volume
        lot_size=100,
        underlying_stop=490.0,
        underlying_target_1=520.0,
        underlying_target_2=530.0,
    )
    assert decision.action == FuturesAction.NO_TRADE
    assert decision.rejection_reason == "LOW_FUTURES_LIQUIDITY"


def test_futures_engine_rejects_on_expiry_day():
    """Verify rejection when DTE < 2 (physical delivery & pin risk)."""
    decision = FuturesEngine.analyze(
        symbol="NIFTY",
        underlying_direction="LONG",
        spot_price=22000.0,
        futures_price=22010.0,
        days_to_expiry=1,      # Too close to expiry
        oi=500000,
        oi_change_pct=2.0,
        volume=100000,
        lot_size=50,
        underlying_stop=21900.0,
        underlying_target_1=22200.0,
        underlying_target_2=22300.0,
    )
    assert decision.action == FuturesAction.NO_TRADE
    assert decision.rejection_reason == "EXPIRY_CYCLE_RESTRICTION"


# ---------------------------------------------------------------------------
# Options Engine Tests
# ---------------------------------------------------------------------------

def test_black_scholes_greeks_invariants():
    """Verify fundamental option Greek invariants."""
    call_greeks = calculate_black_scholes_greeks(
        spot=100.0, strike=100.0, dte_days=30, volatility=0.20, is_call=True
    )
    put_greeks = calculate_black_scholes_greeks(
        spot=100.0, strike=100.0, dte_days=30, volatility=0.20, is_call=False
    )

    # Invariants
    assert 0.0 < call_greeks["delta"] < 1.0
    assert -1.0 < put_greeks["delta"] < 0.0
    assert call_greeks["gamma"] > 0.0
    assert put_greeks["gamma"] > 0.0
    assert call_greeks["theta"] < 0.0  # Time decay is negative
    assert put_greeks["theta"] < 0.0
    assert call_greeks["vega"] > 0.0
    assert put_greeks["vega"] > 0.0


def test_options_engine_buy_call():
    """Verify normal IV produces BUY_CALL on liquid ATM contract."""
    mock_chain = [
        {"strike": 950.0, "option_type": "CE", "bid": 60.0, "ask": 61.0, "volume": 500, "oi": 2000, "iv": 0.18},
        {"strike": 1000.0, "option_type": "CE", "bid": 25.0, "ask": 25.5, "volume": 1200, "oi": 5000, "iv": 0.18},
        {"strike": 1050.0, "option_type": "CE", "bid": 8.0, "ask": 8.5, "volume": 800, "oi": 3000, "iv": 0.18},
    ]
    decision = OptionsEngine.evaluate(
        symbol="TEST_STOCK",
        underlying_direction="LONG",
        spot_price=1000.0,
        option_chain=mock_chain,
        days_to_expiry=14,
        iv_percentile=35.0,  # Low/normal IV -> Naked Call
    )
    assert decision.action == OptionAction.BUY_CALL
    assert decision.is_valid is True
    assert decision.structure == "NAKED_LONG_CALL"
    assert decision.legs[0]["strike"] == 1000.0  # Selected ATM call


def test_options_engine_bull_call_spread():
    """Verify high IV produces BULL_CALL_SPREAD to mitigate theta/vega."""
    mock_chain = [
        {"strike": 1000.0, "option_type": "CE", "bid": 40.0, "ask": 41.0, "volume": 1500, "oi": 6000, "iv": 0.35},
        {"strike": 1040.0, "option_type": "CE", "bid": 18.5, "ask": 19.0, "volume": 1200, "oi": 4000, "iv": 0.35},
    ]
    decision = OptionsEngine.evaluate(
        symbol="TEST_STOCK",
        underlying_direction="LONG",
        spot_price=1000.0,
        option_chain=mock_chain,
        days_to_expiry=14,
        iv_percentile=80.0,  # High IV -> Spread
    )
    assert decision.action == OptionAction.BULL_CALL_SPREAD
    assert decision.is_valid is True
    assert len(decision.legs) == 2
    assert decision.legs[0]["action"] == "BUY"
    assert decision.legs[1]["action"] == "SELL"


def test_options_engine_insufficient_data():
    """Verify missing chain data returns OPTIONS_DATA_INSUFFICIENT."""
    decision = OptionsEngine.evaluate(
        symbol="NO_DATA",
        underlying_direction="LONG",
        spot_price=100.0,
        option_chain=[],
        days_to_expiry=10,
    )
    assert decision.action == OptionAction.OPTIONS_DATA_INSUFFICIENT
    assert decision.is_valid is False
