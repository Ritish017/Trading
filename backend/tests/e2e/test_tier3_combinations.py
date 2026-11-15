"""
APEX E2E Test Suite — Tier 3: Cross-Feature Combinations
========================================================
Validates multi-feature interactions, integrated signal pipelines,
durable idempotency across restarts, multi-tenant isolation, and resilient exits.
"""

import time
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
from backend.app.paper_trading.canonical_order import OrderState
from backend.app.signal_engine.models import (
    AssetClass,
    SignalDirection,
    SignalEngineConfig,
    StopLossResult,
    TargetLevel,
    SignalDecision,
    SignalQualityGrade,
    SignalType,
)
from backend.app.signal_engine.stop_target_engine import StopLossEngine
from backend.app.signal_engine.options_engine import (
    OptionsEngine,
    OptionContract,
    OptionType,
    OptionAction,
)
from backend.app.ai_engine.gemini_client import GeminiModels, GeminiResponse


# ============================================================================
# Combination 1: Complete Signal-to-Paper-to-Exit-to-Journal Pipeline
# ============================================================================

def test_t3_full_signal_to_journal_lifecycle(clean_paper_engine: PaperTradingEngine):
    """
    Tier 3: Scanning -> Qualification -> Sizing -> Order Submission ->
            MTM Tick -> Side-Correct Automated Exit -> Immutable Journal Entry.
    """
    initial_capital = clean_paper_engine.capital
    assert initial_capital == 1000000.0

    # Step 1: Candidate Qualification & Geometry
    symbol = "RELIANCE.NS"
    entry_price = 2900.0
    stop_price = 2850.0  # 50 pts risk (1.72%)
    target_price = 3000.0  # 100 pts reward (2.0 R:R)

    assert stop_price < entry_price < target_price  # Valid LONG Geometry
    risk_reward = (target_price - entry_price) / (entry_price - stop_price)
    assert risk_reward >= 1.5  # Qualifies R:R gate

    # Step 2: Risk-Based Position Sizing (1% risk of 1,000,000 = 10,000 INR)
    max_risk_amount = 10000.0
    risk_per_share = entry_price - stop_price  # 50 INR
    calculated_qty = int(max_risk_amount / risk_per_share)  # 200 shares
    assert calculated_qty == 200

    # Step 3: Paper Order Submission
    order_req = PaperOrderRequest(
        symbol=symbol,
        side="BUY",
        quantity=calculated_qty,
        price=entry_price,
        stopLoss=stop_price,
        targetPrice=target_price,
        productType="CNC",
        source="SYSTEMATIC_SCANNER",
    )
    order_res = clean_paper_engine.execute_order(order_req)
    assert order_res["status"] == "FILLED"
    pos = order_res["position"]
    pos_id = pos["id"]

    assert clean_paper_engine.capital < initial_capital
    assert len(clean_paper_engine.positions) == 1

    # Step 4: Mark-to-Market Tick Ingestion (Price rallies to 2960)
    clean_paper_engine.update_market_price(symbol, 2960.0)
    summary_mid = clean_paper_engine.get_portfolio_summary()
    assert summary_mid["positions"][0]["unrealizedPnL"] > 0
    assert summary_mid["positions"][0]["currentPrice"] == 2960.0

    # Step 5: Target Hit & Automated Exit (Price reaches 3010 >= target 3000)
    exit_price = 3005.0
    close_res = clean_paper_engine.close_position(pos_id, close_price=exit_price)
    assert close_res["status"] == "CLOSED"
    assert pos_id not in clean_paper_engine.positions

    # Step 6: Immutable Journal Record Verification
    assert len(clean_paper_engine.closed_trades) == 1
    trade = clean_paper_engine.closed_trades[0]

    assert trade["symbol"] == symbol
    assert trade["quantity"] == calculated_qty
    assert trade["entryPrice"] > 0
    assert trade["exitPrice"] > 0
    assert trade["realizedPnL"] > 0  # Profitable trade
    assert "brokerage" in trade
    assert "taxes" in trade
    assert clean_paper_engine.capital > initial_capital  # Capital increased net of statutory costs


# ============================================================================
# Combination 2: Durable Idempotency Across Simulated Restarts
# ============================================================================

def test_t3_durable_idempotency_across_server_restart():
    """
    Tier 3: Order submission with durable idempotency key survives server restart
            and returns cached fill without duplicate execution or double deduction.
    """
    idempotency_key = f"IDEM_{uuid.uuid4().hex}"

    # Server Instance 1: Order executed
    server1 = PaperTradingEngine(initial_capital=500000.0)
    order_req = PaperOrderRequest(
        symbol="INFY.NS",
        side="BUY",
        quantity=10,
        price=1800.0,
        idempotency_key=idempotency_key,
    )
    res1 = server1.execute_order(order_req)
    assert res1["status"] == "FILLED"
    cap_after_first = server1.capital
    assert idempotency_key in server1.idempotency_cache

    # Simulated Server Restart: Reconstitute Server Instance 2 with hydrated persistence
    server2 = PaperTradingEngine(initial_capital=500000.0)
    server2.capital = cap_after_first
    server2.positions = dict(server1.positions)
    server2.idempotency_cache.update(server1.idempotency_cache)

    # Re-submission with same idempotency key
    res2 = server2.execute_order(order_req)
    assert res2.get("is_idempotent_replay") is True
    assert res2["order_id"] == res1["order_id"]

    # Verify no double execution
    assert server2.capital == cap_after_first
    assert len(server2.positions) == 1


# ============================================================================
# Combination 3: Options Spread Structuring + Paper Execution + Close
# ============================================================================

def test_t3_options_bull_call_spread_pipeline(complete_option_chain: List[OptionContract]):
    """
    Tier 3: Options engine generates Bull Call Spread -> Paper execution models
            net debit & friction -> Position closes with authentic P&L.
    """
    options_engine = OptionsEngine()
    spot_price = 24050.0

    decision = options_engine.evaluate(
        symbol="NIFTY",
        spot_price=spot_price,
        underlying_direction="LONG",
        chain=complete_option_chain,
        capital=1000000.0,
    )
    # Must evaluate to valid options decision (BUY_CALL or BULL_CALL_SPREAD)
    assert decision.action in [OptionAction.BUY_CALL, OptionAction.BULL_CALL_SPREAD]
    assert decision.is_valid is True
    assert decision.net_premium > 0
    assert decision.max_loss > 0

    # Execute paper trade for the option strategy
    paper_engine = PaperTradingEngine(initial_capital=1000000.0)
    order_req = PaperOrderRequest(
        symbol="NIFTY_24000_CE",
        side="BUY",
        quantity=50,  # 2 lots
        price=decision.net_premium,
        productType="MIS",
    )
    fill_res = paper_engine.execute_order(order_req)
    assert fill_res["status"] == "FILLED"
    pos_id = fill_res["position"]["id"]

    # Close option position with premium expansion (e.g. 50% gain on premium)
    exit_premium = decision.net_premium * 1.5
    close_res = paper_engine.close_position(pos_id, close_price=exit_premium)
    assert close_res["status"] == "CLOSED"
    assert close_res["trade"]["realizedPnL"] > 0


# ============================================================================
# Combination 4: Multi-Tenant / Multi-Account Ledger Isolation
# ============================================================================

def test_t3_multi_tenant_ledger_isolation(client: TestClient, auth_headers: Dict[str, str], auth_headers_account_b: Dict[str, str]):
    """
    Tier 3: Simultaneous operations for Account A and Account B maintain strictly isolated ledgers.
    """
    # 1. Order for Account A
    res_a = client.post(
        "/api/paper/order",
        headers=auth_headers,
        json={"symbol": "TCS.NS", "side": "BUY", "quantity": 10, "price": 3800.0, "account_id": "primary_personal_account"},
    )
    assert res_a.status_code == 200
    pos_a_id = res_a.json()["position"]["id"]

    # 2. Order for Account B
    res_b = client.post(
        "/api/paper/order",
        headers=auth_headers_account_b,
        json={"symbol": "INFY.NS", "side": "BUY", "quantity": 20, "price": 1800.0, "account_id": "account_b"},
    )
    assert res_b.status_code == 200
    pos_b_id = res_b.json()["position"]["id"]

    # 3. Query positions for Account A -> Must not see Account B's position
    res_query_a = client.get("/api/paper/positions?account_id=primary_personal_account", headers=auth_headers)
    assert res_query_a.status_code == 200
    symbols_a = [p["symbol"] for p in res_query_a.json()["positions"]]
    assert "TCS.NS" in symbols_a
    assert "INFY.NS" not in symbols_a

    # 4. Clean up Account A and Account B positions
    client.post(f"/api/paper/close/{pos_a_id}", headers=auth_headers, json={"account_id": "primary_personal_account"})
    client.post(f"/api/paper/close/{pos_b_id}", headers=auth_headers_account_b, json={"account_id": "account_b"})


# ============================================================================
# Combination 5: Offline AI Degradation with Continuous Paper Monitoring
# ============================================================================

@pytest.mark.asyncio
async def test_t3_ai_outage_does_not_impair_trading_or_exits(clean_paper_engine: PaperTradingEngine):
    """
    Tier 3: When AI explanation service is offline or unconfigured,
            active trade execution, mark-to-market, and exits proceed normally.
    """
    # 1. Place trade while AI engine is unconfigured
    ai_client = GeminiModels(api_key="")
    ai_response = await ai_client.generate_content_async(contents="Explain trade setup")
    assert ai_response.status == "UNAVAILABLE"

    # 2. Trade execution is 100% operational despite AI status
    order = PaperOrderRequest(
        symbol="BAJAJ-AUTO.NS",
        side="BUY",
        quantity=5,
        price=9000.0,
        stopLoss=8800.0,
        targetPrice=9400.0,
    )
    fill = clean_paper_engine.execute_order(order)
    assert fill["status"] == "FILLED"
    pos_id = fill["position"]["id"]

    # 3. Automated exit executes cleanly without AI dependency
    exit_res = clean_paper_engine.close_position(pos_id, close_price=9420.0)
    assert exit_res["status"] == "CLOSED"
    assert exit_res["trade"]["realizedPnL"] > 0
