import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.config import settings
from backend.app.broker_providers.base import NormalizedTick
from backend.app.broker_providers.upstox import UpstoxProvider
from backend.app.broker_providers.upstox_client import UpstoxRESTClient
from backend.app.broker_providers.dev_mock import DevMockProvider
from backend.app.market_data.service import MarketDataService
from backend.app.market.instruments import get_instrument_key

@pytest.mark.asyncio
async def test_upstox_unauthenticated_connection_error():
    """Verify that UpstoxProvider fails gracefully when token is missing."""
    provider = UpstoxProvider(token="")
    connected = await provider.connect()
    assert connected is False
    assert provider.is_connected is False

@pytest.mark.asyncio
async def test_upstox_quote_normalization():
    """Verify quote normalization logic with mocked httpx response."""
    mock_resp = {
        "status": "success",
        "data": {
            "NSE_INDEX:Nifty 50": {
                "last_price": 24580.45,
                "volume": 125000,
                "oi": 0,
                "ohlc": {
                    "open": 24410.0,
                    "high": 24625.0,
                    "low": 24400.0,
                    "close": 24418.15
                }
            }
        }
    }

    client = UpstoxRESTClient(token="mock_token_123")
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        quote = await client.get_full_quote("NIFTY 50")
        
        assert quote["symbol"] == "NIFTY 50"
        assert quote["ltp"] == 24580.45
        assert quote["previous_close"] == 24418.15
        assert quote["source"] == "UPSTOX"
        assert quote["is_live"] is True
    await client.close()

@pytest.mark.asyncio
async def test_market_data_service_no_silent_mock_fallback():
    """Verify MarketDataService reports DISCONNECTED when Upstox fails and allow_mock_fallback is False."""
    with patch.object(settings, "upstox_analytics_token", None), \
         patch.object(settings, "upstox_access_token", None), \
         patch.object(settings, "allow_mock_fallback", False), \
         patch.object(settings, "active_broker_provider", "UPSTOX"):
        
        service = MarketDataService()
        init_ok = await service.initialize()
        
        assert init_ok is False
        assert service.status_code == "CONFIGURATION_ERROR"
        assert service.is_live is False
        
        health = service.get_health_status()
        assert health["status"] == "CONFIGURATION_ERROR"
        assert health["mode"] == "OFFLINE"
        assert health["is_live"] is False

@pytest.mark.asyncio
async def test_dev_mock_provider_full_interface():
    """Verify DevMockProvider implements interface methods correctly."""
    mock_p = DevMockProvider()
    await mock_p.connect()
    
    quote = await mock_p.get_quote("RELIANCE.NS")
    assert quote["symbol"] == "RELIANCE.NS"
    assert quote["source"] == "MOCK"
    
    candles = await mock_p.get_historical_candles("RELIANCE.NS", "5m", count=10)
    assert len(candles) == 10
    assert candles[0]["source"] == "MOCK"
    
    chain = await mock_p.get_option_chain("NIFTY 50")
    assert chain["underlying"] == "NIFTY 50"
    assert "pcr" in chain

    await mock_p.disconnect()
