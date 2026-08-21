import pytest
import datetime
from backend.app.market_data.session_engine import (
    MarketSessionEngine,
    MarketSessionState,
    market_session_engine,
    IST_TZ,
)
from backend.app.market.instruments import (
    get_instrument_key,
    get_instrument_metadata,
    INSTRUMENT_MAP,
)
from backend.app.market_data.service import MarketDataService

@pytest.mark.asyncio
async def test_canonical_instrument_resolution():
    """Verify that all major equity symbols resolve to verified NSE equity instruments."""
    universe = [
        ("RELIANCE.NS", "NSE_EQ|INE002A01018"),
        ("TCS.NS", "NSE_EQ|INE467B01029"),
        ("HDFCBANK.NS", "NSE_EQ|INE040A01034"),
        ("INFY.NS", "NSE_EQ|INE009A01021"),
        ("ICICIBANK.NS", "NSE_EQ|INE090A01021"),
        ("TATAMOTORS.NS", "NSE_EQ|INE155A01022"),
        ("SBIN.NS", "NSE_EQ|INE062A01020"),
    ]
    for symbol, expected_key in universe:
        key = get_instrument_key(symbol)
        assert key == expected_key, f"Failed for {symbol}: expected {expected_key}, got {key}"
        meta = get_instrument_metadata(symbol)
        assert meta["exchange"] == "NSE"
        assert meta["segment"] == "NSE_EQ"
        assert meta["instrument_type"] == "EQUITY"

def test_market_session_timing_and_1533_bug_prevention():
    """
    Test IST market session rules and verify that 15:33 is classified as invalid for continuous live trading.
    """
    # 1. 10:30 IST on a Wednesday (2026-08-19 10:30:00 IST)
    wed_1030 = datetime.datetime(2026, 8, 19, 10, 30, 0, tzinfo=IST_TZ).timestamp()
    assert market_session_engine.get_market_session_state(wed_1030) == MarketSessionState.LIVE
    assert market_session_engine.is_valid_equity_candle_timestamp(wed_1030) is True

    # 2. 15:33 IST on a Wednesday (2026-08-19 15:33:00 IST -> POST MARKET / Closed for continuous trading)
    wed_1533 = datetime.datetime(2026, 8, 19, 15, 33, 0, tzinfo=IST_TZ).timestamp()
    assert market_session_engine.get_market_session_state(wed_1533) == MarketSessionState.POST_MARKET
    # 15:33 must NOT be allowed as a live regular-session equity candle
    assert market_session_engine.is_valid_equity_candle_timestamp(wed_1533) is False

    # 3. Sunday (Weekend -> Closed)
    sun_1200 = datetime.datetime(2026, 8, 23, 12, 0, 0, tzinfo=IST_TZ).timestamp()
    assert market_session_engine.get_market_session_state(sun_1200) == MarketSessionState.MARKET_CLOSED
    assert market_session_engine.is_valid_equity_candle_timestamp(sun_1200) is False

@pytest.mark.asyncio
async def test_canonical_quotes_and_composite_cache():
    """Verify that MarketDataService quotes produce unified schema without legacy fallbacks."""
    service = MarketDataService()
    await service.initialize()

    quote = await service.get_quote("RELIANCE.NS")
    assert quote["symbol"] == "RELIANCE.NS"
    assert "ltp" in quote
    assert quote["price_domain"] == "CURRENT_EXCHANGE_PRICE"
    assert "provenance_status" in quote
    assert quote["provenance_status"] in ("AUTHENTIC_LIVE", "DEV_MOCK")
    assert "data_age_seconds" in quote

@pytest.mark.asyncio
async def test_diagnostic_audit_endpoint_data():
    """Verify diagnostic endpoint structures."""
    from backend.app.main import app
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/market/diagnostic")
        assert res.status_code == 200
        data = res.json()
        assert "diagnostic_timestamp" in data
        assert "market_session" in data
        assert "audit" in data
        assert len(data["audit"]) == 7
        symbols = [item["symbol"] for item in data["audit"]]
        assert "RELIANCE.NS" in symbols
        assert "TCS.NS" in symbols
        assert "TATAMOTORS.NS" in symbols
