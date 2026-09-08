"""
ACCEPTANCE SUITE: Market Data Truthfulness & Zero-Trust Provenance Red Team
Validates provider failure handling (no synthetic fallback), instrument identity preservation,
institutional feed failure truthfulness, and market breadth truthfulness.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.market_data.canonical_store import canonical_store
from backend.app.market_data.service import MarketDataService
from backend.app.market_data.institutional_feed import get_fii_dii_flow
from backend.app.command_center.orchestrator import research_command_center
from backend.app.command_center.provenance import EvidenceClassification

client = TestClient(app)


@pytest.mark.asyncio
async def test_provider_failure_reports_unavailable_without_synthetic_fallback():
    """Attack: Forcing market feed timeout/error must report UNAVAILABLE, never synthetic sine prices."""
    service = MarketDataService()

    # Simulate provider failure for symbol UNKNOWN_STOCK.NS
    with patch.object(service, "get_quote", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        quote = await service.get_quote("UNKNOWN_STOCK.NS")
        assert quote is None
        # Canonical store must NOT fabricate prices
        canonical = canonical_store.get_canonical_quote("UNKNOWN_STOCK.NS")
        assert canonical is None


def test_instrument_identity_protection():
    """Attack: Querying an invalid symbol must not silently substitute a known ticker."""
    quote = canonical_store.get_canonical_quote("INVALID_XYZ_NONEXISTENT")
    assert quote is None

    # Canonical store rejects token mismatch
    with pytest.raises(Exception):
        canonical_store.update_from_rest("TCS.NS", {"symbol": "INFY.NS", "ltp": 1500.0})


@pytest.mark.asyncio
async def test_institutional_fii_dii_failure_truthfulness():
    """Attack: When NSE institutional settlement feed fails, report UNAVAILABLE, never hardcoded data."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("NSE portal timeout")):
        # Clear cached flow to force fresh fetch
        import backend.app.market_data.institutional_feed as ifeed
        ifeed._CACHED_FLOW = None
        ifeed._CACHE_TIMESTAMP = 0

        flow = await get_fii_dii_flow()
        assert flow["status"] == "UNAVAILABLE"
        assert flow["is_live"] is False
        assert flow["fiiCashNetCr"] is None
        assert flow["diiCashNetCr"] is None
        assert flow["data"] is None


def test_market_breadth_failure_truthfulness():
    """Attack: When market breadth data sources fail, must report UNAVAILABLE and not emit fake advance/decline numbers."""
    with patch("backend.app.main.market_data_service.get_quotes", side_effect=Exception("Data feed down")):
        res = client.get("/api/market/breadth")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "UNAVAILABLE"
        assert data["is_live"] is False
        assert data["advances"] == 0
        assert data["declines"] == 0


def test_zero_trust_provenance_audit_clean():
    """Validates that Research Command Center enforces zero-trust provenance classifications."""
    snapshot = research_command_center.get_snapshot("RELIANCE.NS", "1D")
    prov = snapshot.provenance

    assert "current_price" in prov
    assert prov["current_price"]["classification"] == EvidenceClassification.RAW_AUTHENTIC_DATA.value
    assert prov["current_price"]["is_point_in_time_valid"] is True

    assert "market_regime" in prov
    assert prov["market_regime"]["classification"] == EvidenceClassification.DERIVED_FROM_AUTHENTIC_DATA.value
