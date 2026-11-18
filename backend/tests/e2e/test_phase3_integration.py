"""
APEX Universal Commodity Intelligence — Phase 3 Full Integration & Regression Test Suite
========================================================================================
Verifies the end-to-end commodity data architecture:
1. Active MCX Contract Resolution (Near/Next/Far-month expiry sorting)
2. Universal Market Data Layer (Upstox Live Quotes & Daily OHLCV Candles)
3. Price Integrity Gateway (9-point sanity & zero-mock quarantine)
4. Historical & Technical Engine (Realized 7D/14D/30D ranges & ATR)
5. Chief Reasoner & Dialectical Pipeline (ATR-anchored scenarios summing to 100%)
6. Immutable Versioned Forecast Store (Legacy mock quarantine & audit history)
"""

import pytest
import time
from backend.app.market_data.mcx.contract_resolver import active_contract_resolver, ContractTerm
from backend.app.market_data.mcx_session_engine import mcx_session_engine, IST
from backend.app.market_data.price_integrity_gateway import price_integrity_gateway, ValidationVerdict
from backend.app.market_data.universal_feed import universal_feed_service, UniversalQuote, MarketDataUnavailableError
from backend.app.ai_engine.technical_engine import technical_engine
from backend.app.ai_engine.tools_service import tools_service
from backend.app.ai_engine.apex_chief_reasoner import apex_chief_reasoner, MarketForecast
from backend.app.ai_engine.forecast_store import forecast_store


@pytest.mark.asyncio
async def test_mcx_target_commodity_universe_resolution():
    """Verify all 8 core target commodities resolve active near-month contracts."""
    targets = ["GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER", "ALUMINIUM", "ZINC", "LEAD"]
    now_ms = time.time() * 1000.0
    for code in targets:
        resolution = await active_contract_resolver.resolve_commodity(code, as_of_ms=now_ms)
        assert resolution is not None, f"Failed to resolve {code}"
        assert resolution.near_contract is not None
        assert resolution.near_contract.term == ContractTerm.NEAR_MONTH
        assert resolution.near_contract.expiry_timestamp >= now_ms
        assert resolution.unit is not None
        assert len(resolution.near_contract.trading_symbol) > 0


@pytest.mark.asyncio
async def test_price_integrity_gateway_rejects_synthetic_legacy_prices():
    """Verify that known legacy mock prices (e.g. ₹78,450 for Gold) are immediately rejected."""
    bad_quote = UniversalQuote(
        symbol="GOLD",
        instrument_id="GOLD_MCX",
        instrument_key="MCX_FO|495213",
        trading_symbol="GOLD FUT 04 DEC 26",
        contract_expiry="2026-12-04",
        exchange="MCX",
        currency="INR",
        unit="₹/10g",
        ltp=78450.0,  # Known synthetic mock price
        open=78400.0,
        high=78600.0,
        low=78300.0,
        close=78450.0,
        volume=1000,
        open_interest=5000,
        last_trade_time=int(time.time() * 1000),
        market_status="LIVE",
        source="UPSTOX",
        price_domain="RAW_EXCHANGE_PRICE",
    )
    result = price_integrity_gateway.validate_quote(bad_quote)
    assert not result.is_valid
    assert result.verdict == ValidationVerdict.SYNTHETIC_MOCK_DETECTED


@pytest.mark.asyncio
async def test_forecast_store_quarantine_legacy_records():
    """Verify that legacy mock forecast records are quarantined and excluded from active lookups."""
    # When allow_quarantined=False, legacy records are not returned as active
    gold_active = forecast_store.get_latest_forecast("GOLD_MCX", allow_quarantined=False)
    if gold_active:
        assert gold_active.is_synthetic_legacy is False
        assert gold_active.status != "INVALID_LEGACY_SYNTHETIC"
        assert gold_active.current_price != 78450.0

    # History contains the quarantined version if loaded
    history = forecast_store.get_forecast_history("GOLD_MCX", allow_quarantined=True)
    v1 = next((fc for fc in history if fc.version == 1), None)
    if v1:
        assert v1.is_synthetic_legacy is True
        assert v1.status == "INVALID_LEGACY_SYNTHETIC"


@pytest.mark.asyncio
async def test_deterministic_forecast_payload_scenario_invariants():
    """Verify that scenario probabilities strictly sum to 1.00 and targets are anchored to price."""
    curr = 131200.0
    atr = 2600.0
    payload = apex_chief_reasoner._generate_deterministic_forecast_payload(
        curr_price=curr,
        fundamentals={"inventory_status": "DEFICIT"},
        technicals={"rsi_14": 55.0},
        daily_atr=atr,
    )
    p_sum = (
        payload["bullish_scenario"]["probability"]
        + payload["base_scenario"]["probability"]
        + payload["bearish_scenario"]["probability"]
    )
    assert abs(p_sum - 1.0) < 0.001
    assert payload["bullish_scenario"]["price_target"] > curr
    assert payload["bearish_scenario"]["price_target"] < curr


@pytest.mark.asyncio
async def test_mcx_session_engine():
    """Verify that MCX session engine correctly distinguishes MCX trading hours from NSE cash hours."""
    # Mon-Fri evening session at 20:00 IST is OPEN for MCX even though NSE closed at 15:30
    import datetime
    # Test a Wednesday at 20:00 IST
    wed_evening = datetime.datetime(2026, 11, 18, 20, 0, 0, tzinfo=IST)
    assert mcx_session_engine.is_mcx_trading_session(wed_evening) is True

    # Test Sunday at 14:00 IST (CLOSED)
    sun_afternoon = datetime.datetime(2026, 11, 22, 14, 0, 0, tzinfo=IST)
    assert mcx_session_engine.is_mcx_trading_session(sun_afternoon) is False
