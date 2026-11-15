"""
APEX E2E Test Suite — Tier 2: Boundary, Edge & Corner Cases
===========================================================
Adversarial and boundary verification covering invalid F&O inputs,
extreme parameters, edge cases, fail-closed security, and numeric bounds.
"""

import math
import uuid
import pytest
from typing import Dict, Any, List
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.paper_trading.engine import (
    PaperTradingEngine,
    PaperOrderRequest,
)
from backend.app.paper_trading.canonical_order import (
    CanonicalOrder,
    OrderState,
)
from backend.app.signal_engine.models import (
    AssetClass,
    SignalDirection,
    SignalEngineConfig,
    StopLossResult,
    TargetLevel,
    ValidationGateResult,
)
from backend.app.signal_engine.validation_gates import (
    gate_data_validation,
    gate_instrument_validation,
    gate_liquidity,
    gate_stop_determinable,
    gate_risk_reward,
    gate_portfolio_risk,
)
from backend.app.signal_engine.options_engine import (
    OptionsEngine,
    OptionAction,
    OptionContract,
    OptionType,
)
from backend.app.signal_engine.futures_engine import (
    FuturesEngine,
    FuturesAction,
)


# ============================================================================
# Tier 2 - Group 1: Order Parameter & Numeric Boundaries
# ============================================================================

def test_t2_zero_and_negative_quantity_rejection(clean_paper_engine: PaperTradingEngine):
    """Tier 2: Orders with quantity <= 0 must fail validation."""
    # Sub-case 1: Zero quantity
    with pytest.raises(Exception):
        PaperOrderRequest(symbol="INFY.NS", side="BUY", quantity=0, price=1500.0)

    # Sub-case 2: Negative quantity
    with pytest.raises(Exception):
        PaperOrderRequest(symbol="INFY.NS", side="BUY", quantity=-10, price=1500.0)

    # Sub-case 3: Extreme negative
    with pytest.raises(Exception):
        PaperOrderRequest(symbol="INFY.NS", side="BUY", quantity=-999999, price=1500.0)


def test_t2_zero_and_negative_price_rejection(clean_paper_engine: PaperTradingEngine):
    """Tier 2: Orders with price <= 0 must fail validation."""
    # Sub-case 1: Zero price
    with pytest.raises(Exception):
        PaperOrderRequest(symbol="TCS.NS", side="BUY", quantity=5, price=0.0)

    # Sub-case 2: Negative price
    with pytest.raises(Exception):
        PaperOrderRequest(symbol="TCS.NS", side="BUY", quantity=5, price=-100.0)


def test_t2_capital_exhaustion_and_overdraw(clean_paper_engine: PaperTradingEngine):
    """Tier 2: Orders requiring margin greater than available capital are rejected."""
    clean_paper_engine.capital = 10000.0

    # Order requires 100 * 2500 = 250,000 (exceeds 10,000)
    order = PaperOrderRequest(symbol="RELIANCE.NS", side="BUY", quantity=100, price=2500.0)
    res = clean_paper_engine.execute_order(order)

    assert res["status"] == "REJECTED"
    assert "Insufficient margin" in res["reason"]
    # Capital remains untouched
    assert clean_paper_engine.capital == 10000.0
    assert len(clean_paper_engine.positions) == 0


def test_t2_partial_and_excess_close_quantities(clean_paper_engine: PaperTradingEngine):
    """Tier 2: Position closure with valid partial, excess, and zero quantities."""
    order = PaperOrderRequest(symbol="SBIN.NS", side="BUY", quantity=50, price=800.0)
    res_fill = clean_paper_engine.execute_order(order)
    pos_id = res_fill["position"]["id"]

    # 1. Close excess quantity (60 > 50) -> Rejected
    res_excess = clean_paper_engine.close_position(pos_id, close_quantity=60)
    assert res_excess["status"] == "ERROR"
    assert "exceeds open quantity" in res_excess["reason"]
    assert clean_paper_engine.positions[pos_id]["quantity"] == 50

    # 2. Close negative quantity -> Rejected
    res_neg = clean_paper_engine.close_position(pos_id, close_quantity=-5)
    assert res_neg["status"] == "ERROR"

    # 3. Valid partial close (20 out of 50) -> PARTIALLY_CLOSED
    res_partial = clean_paper_engine.close_position(pos_id, close_price=820.0, close_quantity=20)
    assert res_partial["status"] == "PARTIALLY_CLOSED"
    assert res_partial["remaining_quantity"] == 30
    assert clean_paper_engine.positions[pos_id]["quantity"] == 30

    # 4. Close remaining 30 -> CLOSED
    res_full = clean_paper_engine.close_position(pos_id, close_price=825.0, close_quantity=30)
    assert res_full["status"] == "CLOSED"
    assert pos_id not in clean_paper_engine.positions


# ============================================================================
# Tier 2 - Group 2: Directional Geometry Violations
# ============================================================================

def test_t2_long_geometry_boundary_violations():
    """Tier 2: LONG geometry requires stop < entry < target_1 < target_2."""
    entry = 1000.0

    # Invariant check function
    def validate_long_geometry(stop: float, entry: float, t1: float, t2: float) -> bool:
        return (stop < entry) and (entry < t1) and (t1 < t2)

    # Violation 1: Stop equal to entry (zero risk distance)
    assert validate_long_geometry(1000.0, entry, 1050.0, 1100.0) is False

    # Violation 2: Stop above entry
    assert validate_long_geometry(1020.0, entry, 1050.0, 1100.0) is False

    # Violation 3: Target 1 equal to entry
    assert validate_long_geometry(950.0, entry, 1000.0, 1100.0) is False

    # Violation 4: Target 1 below entry
    assert validate_long_geometry(950.0, entry, 980.0, 1100.0) is False

    # Violation 5: Inverted targets (target 2 < target 1)
    assert validate_long_geometry(950.0, entry, 1100.0, 1050.0) is False

    # Happy path: Strictly valid
    assert validate_long_geometry(950.0, entry, 1050.0, 1100.0) is True


def test_t2_short_geometry_boundary_violations():
    """Tier 2: SHORT geometry requires target_2 < target_1 < entry < stop."""
    entry = 1000.0

    def validate_short_geometry(stop: float, entry: float, t1: float, t2: float) -> bool:
        return (entry < stop) and (t1 < entry) and (t2 < t1)

    # Violation 1: Stop equal to entry
    assert validate_short_geometry(1000.0, entry, 950.0, 900.0) is False

    # Violation 2: Stop below entry
    assert validate_short_geometry(980.0, entry, 950.0, 900.0) is False

    # Violation 3: Target 1 equal to entry
    assert validate_short_geometry(1050.0, entry, 1000.0, 900.0) is False

    # Violation 4: Target 1 above entry
    assert validate_short_geometry(1050.0, entry, 1020.0, 900.0) is False

    # Violation 5: Inverted targets (target 2 > target 1)
    assert validate_short_geometry(1050.0, entry, 900.0, 950.0) is False

    # Happy path: Strictly valid
    assert validate_short_geometry(1050.0, entry, 950.0, 900.0) is True


# ============================================================================
# Tier 2 - Group 3: Quantitative Gate Boundaries
# ============================================================================

def test_t2_risk_reward_gate_boundaries():
    """Tier 2: Risk/Reward gate rejects setups below min_risk_reward (1.5)."""
    config = SignalEngineConfig(min_risk_reward=1.5)

    # Case 1: None R:R -> FAIL
    res_none = gate_risk_reward(None, config)
    assert res_none.result == ValidationGateResult.FAIL

    # Case 2: Sub-threshold R:R (1.49) -> FAIL
    res_low = gate_risk_reward(1.49, config)
    assert res_low.result == ValidationGateResult.FAIL
    assert "below minimum" in res_low.reason

    # Case 3: Exactly threshold (1.50) -> PASS
    res_exact = gate_risk_reward(1.50, config)
    assert res_exact.result == ValidationGateResult.PASS

    # Case 4: Strong R:R (2.50) -> PASS
    res_strong = gate_risk_reward(2.50, config)
    assert res_strong.result == ValidationGateResult.PASS

    # Case 5: Negative R:R (-1.0) -> FAIL
    res_neg = gate_risk_reward(-1.0, config)
    assert res_neg.result == ValidationGateResult.FAIL


def test_t2_stop_determinable_gate_boundaries():
    """Tier 2: Stop determinable gate enforces maximum distance percentage (5.0%)."""
    config = SignalEngineConfig(max_stop_pct=5.0)

    # Case 1: Excessive stop distance (6.0% on entry 1000 -> stop 940) -> FAIL
    stop_excessive = StopLossResult(price=940.0, method="ATR", risk_per_share=60.0)
    res_excessive = gate_stop_determinable(stop_excessive, entry_price=1000.0, config=config)
    assert res_excessive.result == ValidationGateResult.FAIL
    assert "exceeds maximum" in res_excessive.reason

    # Case 2: Acceptable stop distance (4.0% on entry 1000 -> stop 960) -> PASS
    stop_valid = StopLossResult(price=960.0, method="ATR", risk_per_share=40.0)
    res_valid = gate_stop_determinable(stop_valid, entry_price=1000.0, config=config)
    assert res_valid.result == ValidationGateResult.PASS

    # Case 3: None stop result -> FAIL
    res_none = gate_stop_determinable(None, entry_price=1000.0, config=config)
    assert res_none.result == ValidationGateResult.FAIL


def test_t2_portfolio_risk_gate_boundaries():
    """Tier 2: Portfolio risk gate limits open positions and capital exposure."""
    config = SignalEngineConfig(max_positions=3, max_portfolio_exposure_pct=60.0, capital=1000000.0)

    # Case 1: Already at maximum positions (3 positions) -> FAIL
    portfolio_at_capacity = {"open_positions_count": 3, "positions": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
    res_cap = gate_portfolio_risk(portfolio_at_capacity, config)
    assert res_cap.result == ValidationGateResult.FAIL
    assert "Maximum open positions" in res_cap.reason

    # Case 2: Below maximum positions (2 positions) -> PASS
    portfolio_below_cap = {"open_positions_count": 2, "positions": [{"id": "1"}, {"id": "2"}]}
    res_below = gate_portfolio_risk(portfolio_below_cap, config)
    assert res_below.result == ValidationGateResult.PASS


# ============================================================================
# Tier 2 - Group 4: Derivatives (F&O) Boundary Conditions
# ============================================================================

def test_t2_options_chain_liquidity_boundaries():
    """Tier 2: Options contracts with wide spread, low OI, or low volume are rejected."""
    options_engine = OptionsEngine()

    # Case 1: Wide bid-ask spread (> 3%)
    contract_wide_spread = OptionContract(
        strike=24000.0,
        option_type=OptionType.CALL,
        expiry="2026-10-29",
        bid=100.0,
        ask=115.0,  # Spread 15 / 100 = 15% > 3%
        last_price=105.0,
        volume=1000,
        oi=5000,
        oi_change=100,
        iv=0.16,
    )
    decision_spread = options_engine.evaluate(
        symbol="NIFTY",
        spot_price=24000.0,
        underlying_direction="LONG",
        chain=[contract_wide_spread],
        capital=500000.0,
    )
    assert decision_spread.action in [OptionAction.NO_TRADE, OptionAction.OPTIONS_DATA_INSUFFICIENT]

    # Case 2: Zero OI
    contract_zero_oi = OptionContract(
        strike=24000.0,
        option_type=OptionType.CALL,
        expiry="2026-10-29",
        bid=100.0,
        ask=102.0,
        last_price=101.0,
        volume=1000,
        oi=0,  # Zero OI
        oi_change=0,
        iv=0.16,
    )
    decision_oi = options_engine.evaluate(
        symbol="NIFTY",
        spot_price=24000.0,
        underlying_direction="LONG",
        chain=[contract_zero_oi],
        capital=500000.0,
    )
    assert decision_oi.action in [OptionAction.NO_TRADE, OptionAction.OPTIONS_DATA_INSUFFICIENT]


# ============================================================================
# Tier 2 - Group 5: Authentication & Red Team Injection Attacks
# ============================================================================

def test_t2_authentication_boundary_and_injections(client: TestClient):
    """Tier 2: Malformed headers, SQL injections, and unicode tokens fail closed."""
    # Attack 1: Empty Authorization header
    res1 = client.post("/api/paper/order", headers={"Authorization": ""}, json={})
    assert res1.status_code == 401

    # Attack 2: Bearer with empty token
    res2 = client.post("/api/paper/order", headers={"Authorization": "Bearer "}, json={})
    assert res2.status_code == 401

    # Attack 3: SQL Injection payload in token
    res3 = client.post("/api/paper/order", headers={"Authorization": "Bearer ' OR '1'='1"}, json={})
    assert res3.status_code == 401

    # Attack 4: Long string buffer overflow attempt
    res4 = client.post("/api/paper/order", headers={"Authorization": f"Bearer {'A'*5000}"}, json={})
    assert res4.status_code == 401

    # Attack 5: Unicode and control characters
    res5 = client.post("/api/paper/order", headers={"Authorization": "Bearer \x00\x1f\xff\u202e_token"}, json={})
    assert res5.status_code == 401


def test_t2_cross_account_idor_prevention(client: TestClient, auth_headers: Dict[str, str], auth_headers_account_b: Dict[str, str]):
    """Tier 2: Token A is strictly blocked from placing orders or closing positions for Account B."""
    # Place order as Account B
    res_b = client.post(
        "/api/paper/order",
        headers=auth_headers_account_b,
        json={"symbol": "INFY.NS", "side": "BUY", "quantity": 5, "price": 1800.0, "account_id": "account_b"},
    )
    assert res_b.status_code == 200
    pos_b_id = res_b.json()["position"]["id"]

    # Attack: User A attempts to close User B's position -> HTTP 403 Forbidden
    res_attack = client.post(
        f"/api/paper/close/{pos_b_id}",
        headers=auth_headers,
        json={"account_id": "primary_personal_account"},
    )
    assert res_attack.status_code == 403
    assert "IDOR violation" in res_attack.json()["detail"]


# ============================================================================
# Tier 2 - Group 6: Mark-to-Market & Same-Bar Anomaly Handling
# ============================================================================

def test_t2_mtm_zero_and_negative_tick_protection(clean_paper_engine: PaperTradingEngine):
    """Tier 2: MTM processor rejects ticks with ltp <= 0 to avoid zero-division or corruption."""
    order = PaperOrderRequest(symbol="TCS.NS", side="BUY", quantity=10, price=3800.0)
    res = clean_paper_engine.execute_order(order)
    pos_id = res["position"]["id"]

    # Tick with ltp = 0.0 -> must be ignored
    clean_paper_engine.update_market_price("TCS.NS", 0.0)
    assert clean_paper_engine.positions[pos_id]["currentPrice"] == 3800.0 or clean_paper_engine.positions[pos_id]["currentPrice"] > 0

    # Tick with ltp = -100.0 -> must be ignored
    clean_paper_engine.update_market_price("TCS.NS", -100.0)
    assert clean_paper_engine.positions[pos_id]["currentPrice"] > 0
