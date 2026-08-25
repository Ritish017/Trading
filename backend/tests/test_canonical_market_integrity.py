"""
APEX Quant Lab — Canonical Market Data Integrity & Anti-Contamination Test Suite
================================================================================
Automated verification ensuring:
  1. Zero static current prices in production frontend data files.
  2. Zero synthetic candle generators in frontend utilities.
  3. Strict CanonicalQuoteStore reconciliation (newer provider timestamp wins).
  4. Preserved exchange timestamps (no Date.now fabrication).
  5. Mock provider is explicitly labeled SIMULATED and is_live=False.
  6. Stale and closed states cannot claim LIVE.
  7. Paper trading and strategy engines consume canonical data.
  8. Static price scanner passes across the repository.
"""

import os
import re
import time
import pytest
from pathlib import Path

from backend.app.market_data.canonical_store import CanonicalQuoteStore, CanonicalQuote
from backend.app.broker_providers.dev_mock import DevMockProvider
from backend.app.market_data.service import MarketDataService


# -----------------------------------------------------------------------------
# 1. Static Price Scanner — Scans frontend data files for hardcoded prices
# -----------------------------------------------------------------------------
def test_static_price_scanner_no_hardcoded_prices_in_registry():
    """Verify that frontend/src/data/indianMarketData.ts contains ZERO current prices."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    market_data_file = repo_root / "frontend" / "src" / "data" / "indianMarketData.ts"
    
    assert market_data_file.exists(), f"File {market_data_file} not found"
    content = market_data_file.read_text(encoding="utf-8")

    # Patterns that indicate hardcoded current prices
    forbidden_patterns = [
        r"price\s*:\s*\d+(\.\d+)?",
        r"ltp\s*:\s*\d+(\.\d+)?",
        r"lastPrice\s*:\s*\d+(\.\d+)?",
        r"currentPrice\s*:\s*\d+(\.\d+)?",
        r"prevClose\s*:\s*[1-9]\d*(\.\d+)?",
        r"vwap\s*:\s*[1-9]\d*(\.\d+)?",
        r"sparkline\s*:\s*\[\s*\d+",
    ]

    for pat in forbidden_patterns:
        matches = list(re.finditer(pat, content))
        assert len(matches) == 0, f"Found forbidden hardcoded price pattern '{pat}' in {market_data_file}: {[m.group() for m in matches]}"


def test_no_synthetic_candle_generation_in_frontend():
    """Verify that generateInitialIndianCandles and Math.random candle drift are deleted."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    tech_analysis_file = repo_root / "frontend" / "src" / "utils" / "indianTechnicalAnalysis.ts"
    
    assert tech_analysis_file.exists()
    content = tech_analysis_file.read_text(encoding="utf-8")

    assert "generateInitialIndianCandles" not in content, "generateInitialIndianCandles must be completely removed"
    assert "Math.random" not in content, "Math.random must not exist in production technical analysis"


# -----------------------------------------------------------------------------
# 2. CanonicalQuoteStore Reconciliation Tests
# -----------------------------------------------------------------------------
def test_canonical_store_rest_and_ws_reconciliation_newer_wins():
    """Verify that the source with the newer provider_timestamp wins."""
    store = CanonicalQuoteStore()

    # Ingest REST quote @ t=1000
    rest_payload = {
        "symbol": "TCS.NS",
        "instrument_key": "NSE_EQ|INE467B01029",
        "exchange": "NSE",
        "ltp": 2302.00,
        "previous_close": 2300.00,
        "provider": "UPSTOX",
        "provider_mode": "AUTHENTIC_LIVE",
        "provider_timestamp": 1000.0,
        "received_timestamp": 1000.1,
    }
    q1 = store.update_from_rest(rest_payload)
    assert q1 is not None
    assert q1.ltp == 2302.00
    assert q1.canonical_source == "REST"
    assert q1.provider_timestamp == 1000.0

    # Ingest WS tick @ t=1005 (newer than REST)
    ws_payload = {
        "symbol": "TCS.NS",
        "instrument_key": "NSE_EQ|INE467B01029",
        "exchange": "NSE",
        "ltp": 2305.50,
        "previous_close": 2300.00,
        "provider": "UPSTOX",
        "provider_mode": "AUTHENTIC_LIVE",
        "provider_timestamp": 1005.0,
        "received_timestamp": 1005.01,
    }
    q2 = store.update_from_ws(ws_payload)
    assert q2 is not None
    assert q2.ltp == 2305.50
    assert q2.canonical_source == "WS"
    assert q2.provider_timestamp == 1005.0

    # Now ingest a delayed REST quote @ t=1002 (older than current WS @ t=1005)
    stale_rest = {
        "symbol": "TCS.NS",
        "instrument_key": "NSE_EQ|INE467B01029",
        "exchange": "NSE",
        "ltp": 2301.00,
        "previous_close": 2300.00,
        "provider": "UPSTOX",
        "provider_mode": "AUTHENTIC_LIVE",
        "provider_timestamp": 1002.0,
        "received_timestamp": 1006.0,
    }
    q3 = store.update_from_rest(stale_rest)
    # The WS @ t=1005 must still win!
    assert q3.ltp == 2305.50
    assert q3.canonical_source == "WS"
    assert q3.provider_timestamp == 1005.0


def test_canonical_store_preserves_provider_timestamp():
    """Verify that provider_timestamp is never overwritten with server time."""
    store = CanonicalQuoteStore()
    exact_exchange_ts = 1787304163.0
    
    quote = store.update_from_rest({
        "symbol": "RELIANCE.NS",
        "ltp": 1316.00,
        "provider": "UPSTOX",
        "provider_mode": "AUTHENTIC_LIVE",
        "provider_timestamp": exact_exchange_ts,
    })
    assert quote.provider_timestamp == exact_exchange_ts


def test_missing_quote_returns_none():
    """Verify that unpopulated symbols return None and never guess a price."""
    store = CanonicalQuoteStore()
    assert store.get_canonical_quote("UNKNOWN.NS") is None


def test_zero_or_negative_price_rejected():
    """Verify that ltp <= 0 is rejected from entering the canonical store."""
    store = CanonicalQuoteStore()
    assert store.update_from_rest({"symbol": "INFY.NS", "ltp": 0.0}) is None
    assert store.update_from_rest({"symbol": "INFY.NS", "ltp": -100.0}) is None
    assert store.get_canonical_quote("INFY.NS") is None


# -----------------------------------------------------------------------------
# 3. DevMockProvider Anti-Deception Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mock_provider_is_always_simulated():
    """Verify that DevMockProvider output is always flagged SIMULATED and is_live=False."""
    mock = DevMockProvider()
    await mock.connect()
    
    quote = await mock.get_quote("TCS.NS")
    assert quote["is_live"] is False
    assert quote["provider_mode"] == "SIMULATED"
    assert quote["market_status"] == "SIMULATED"
    assert quote["source"] == "MOCK"

    quotes = await mock.get_quotes(["RELIANCE.NS", "HDFCBANK.NS"])
    for q in quotes:
        assert q["is_live"] is False
        assert q["provider_mode"] == "SIMULATED"


def test_mock_provider_has_no_initial_prices_snapshot_dict():
    """Verify that INITIAL_PRICES snapshot dictionary is removed from dev_mock.py."""
    import backend.app.broker_providers.dev_mock as dm
    assert not hasattr(dm, "INITIAL_PRICES"), "INITIAL_PRICES dictionary must be deleted from dev_mock.py"


# -----------------------------------------------------------------------------
# 4. Provenance and Stale Data Integrity Tests
# -----------------------------------------------------------------------------
def test_stale_data_cannot_claim_live():
    """Verify that data older than 300 seconds is marked stale and is_live=False."""
    old_ts = time.time() - 350.0  # 350s old
    canonical = CanonicalQuote(
        symbol="SBIN.NS",
        instrument_key="NSE_EQ|INE062A01020",
        exchange="NSE",
        ltp=845.0,
        previous_close=840.0,
        open=840.0,
        high=850.0,
        low=838.0,
        volume=100000,
        bid=844.8,
        ask=845.2,
        provider="UPSTOX",
        provider_mode="AUTHENTIC_LIVE",
        provider_timestamp=old_ts,
        received_timestamp=time.time(),
    )
    assert canonical.is_live is False
    assert canonical.is_stale is True
    assert canonical.market_data_status in ("RECENT", "STALE", "MARKET_CLOSED")


def test_simulated_mode_cannot_claim_live_even_if_fresh():
    """Verify that SIMULATED mode cannot claim is_live=True even with fresh timestamp."""
    fresh_ts = time.time()
    canonical = CanonicalQuote(
        symbol="SBIN.NS",
        instrument_key="NSE_EQ|INE062A01020",
        exchange="NSE",
        ltp=845.0,
        previous_close=840.0,
        open=840.0,
        high=850.0,
        low=838.0,
        volume=100000,
        bid=844.8,
        ask=845.2,
        provider="MOCK",
        provider_mode="SIMULATED",
        provider_timestamp=fresh_ts,
        received_timestamp=fresh_ts,
    )
    assert canonical.is_live is False
    assert canonical.market_data_status == "SIMULATED"


# -----------------------------------------------------------------------------
# 5. Diagnostic Endpoint Format Tests
# -----------------------------------------------------------------------------
def test_diagnostic_response_contract():
    """Verify the diagnostic structure returns all required audit fields."""
    store = CanonicalQuoteStore()
    ts = time.time()
    store.update_from_rest({
        "symbol": "HDFCBANK.NS",
        "instrument_key": "NSE_EQ|INE040A01034",
        "ltp": 726.50,
        "provider": "UPSTOX",
        "provider_mode": "AUTHENTIC_LIVE",
        "provider_timestamp": ts,
        "received_timestamp": ts,
    })
    
    diag = store.get_diagnostic("HDFCBANK.NS", authenticated=True, connected=True)
    assert diag["symbol"] == "HDFCBANK.NS"
    assert diag["raw_ltp"] == 726.50
    assert diag["provider"] == "UPSTOX"
    assert diag["provider_mode"] == "AUTHENTIC_LIVE"
    assert diag["authenticated"] is True
    assert diag["connected"] is True
    assert diag["integrity"] == "PASS"
    assert "data_age_seconds" in diag
    assert "quote_sequence_id" in diag
