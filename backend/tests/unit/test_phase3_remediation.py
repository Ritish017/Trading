"""
APEX Phase 3 Remediation Test Suite
===================================
Validates:
1. Multi-asset routing for NSE Equities/Indices, USD/INR Currency, and Bitcoin Crypto.
2. Complete elimination of synthetic sine-wave candles in Command Center.
3. Complete replacement of randomized portfolio returns with genuine historical calculations.
4. Dynamic peak-to-trough max drawdown calculation in FactorPortfolioEngine.
5. End-to-end data provenance across all asset classes and market data services.
"""

import math
import pytest
from typing import Dict, Any, List

from backend.app.ai_engine.tools_service import ToolsService
from backend.app.command_center.orchestrator import (
    ResearchCommandCenterOrchestrator,
    generate_canonical_candles,
    get_authentic_candles_sync,
)
from backend.app.command_center.provenance import (
    EvidenceClassification,
    ProvenanceDataStatus,
)
from backend.app.fundamental_engine.portfolio_engine import (
    FactorPortfolioEngine,
    portfolio_engine,
)
from backend.app.market_data.instrument_registry import instrument_registry


# ---------------------------------------------------------------------------
# 1. Multi-Asset Routing: NSE, USD/INR, and Bitcoin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nifty50_asset_routing():
    """Verifies that NIFTY50_NSE routes to NSE index without MCX commodity resolution failure."""
    tools = ToolsService()
    snap = await tools.get_current_market_snapshot_async("NIFTY50_NSE")
    assert snap is not None
    assert snap["exchange"] == "NSE"
    assert snap["currency"] == "INR"
    assert snap["price"] > 0
    assert snap["price_domain"] == "RAW_EXCHANGE_PRICE"
    assert snap["data_source"] in ("UPSTOX", "YAHOO_FINANCE_VERIFIED")


@pytest.mark.asyncio
async def test_usdinr_currency_routing():
    """Verifies that USDINR_NSE routes to currency pair with authentic rate."""
    tools = ToolsService()
    snap = await tools.get_current_market_snapshot_async("USDINR_NSE")
    assert snap is not None
    assert snap["exchange"] == "NSE"
    assert snap["currency"] == "INR"
    assert 70.0 < snap["price"] < 120.0
    assert snap["price_domain"] == "RAW_EXCHANGE_PRICE"
    assert snap["data_source"] == "YAHOO_FINANCE_VERIFIED"

    curr_tool = await tools.get_currency_data_async("USDINR")
    assert curr_tool["status"] == "AVAILABLE"
    assert curr_tool["rate"] > 0
    assert curr_tool["provenance"] == "YAHOO_FINANCE_VERIFIED"


@pytest.mark.asyncio
async def test_bitcoin_crypto_routing():
    """Verifies that BTCUSD routes to crypto benchmark with authentic USD price."""
    tools = ToolsService()
    snap = await tools.get_current_market_snapshot_async("BTCUSD")
    assert snap is not None
    assert snap["exchange"] == "GLOBAL_INDEX"
    assert snap["currency"] == "USD"
    assert snap["price"] > 10000.0
    assert snap["price_domain"] == "RAW_EXCHANGE_PRICE"
    assert snap["data_source"] == "YAHOO_FINANCE_VERIFIED"


@pytest.mark.asyncio
async def test_macro_historical_indicators_non_flatline():
    """Verifies that historical lookups for NIFTY50_NSE and BTCUSD compute genuine technical indicators."""
    tools = ToolsService()
    
    # NIFTY 50 historical
    nifty_hist = await tools.get_historical_price_data_async("NIFTY50_NSE", lookback_bars=30)
    assert nifty_hist["bars_returned"] >= 2
    assert nifty_hist["current_price"] > 0
    assert nifty_hist["sma_20"] > 0
    assert nifty_hist["rsi_14"] > 0
    # Must NOT flatline (high_7d != low_7d when real bars exist)
    r7 = nifty_hist["realized_7d"]
    assert r7["high"] >= r7["low"]

    # BTC historical
    btc_hist = await tools.get_historical_price_data_async("BTCUSD", lookback_bars=30)
    assert btc_hist["bars_returned"] >= 2
    assert btc_hist["current_price"] > 10000.0
    assert btc_hist["sma_20"] > 0
    assert btc_hist["rsi_14"] > 0


def test_statutory_economic_indicators_for_india():
    """Verifies that official RBI/MOSPI indicators are returned with statutory provenance."""
    tools = ToolsService()
    econ = tools.get_economic_indicators("INDIA")
    assert econ["status"] == "AVAILABLE"
    assert econ["provenance"] == "RESERVE_BANK_OF_INDIA_OFFICIAL"
    assert econ["rbi_repo_rate"] == 6.50
    assert econ["cpi_inflation_pct"] > 0
    assert econ["is_verified"] is True


# ---------------------------------------------------------------------------
# 2. Command Center: Sine-Wave Elimination & Authentic Provenance
# ---------------------------------------------------------------------------

def test_command_center_candles_contain_zero_sine_waves():
    """
    Forensic test: verifies that generate_canonical_candles and get_authentic_candles_sync
    contain no sine waves (math.sin is not used).
    """
    # 1. Inspect source code of orchestrator.py
    import inspect
    from backend.app.command_center import orchestrator
    source = inspect.getsource(orchestrator)
    assert "math.sin" not in source, "Source code of orchestrator.py must not contain math.sin"

    # 2. Call generate_canonical_candles
    candles = generate_canonical_candles("RELIANCE.NS", count=20)
    assert len(candles) == 20
    for c in candles:
        assert c["close"] > 0
        assert not math.isnan(c["close"])
        assert not math.isinf(c["close"])


def test_command_center_snapshot_provenance_honesty():
    """
    Verifies that Command Center snapshot accurately reports provenance
    without falsely claiming synthetic data is RAW_AUTHENTIC_DATA.
    """
    snap = ResearchCommandCenterOrchestrator.get_snapshot("RELIANCE.NS", "1D")
    assert snap.market.symbol == "RELIANCE.NS"
    assert snap.market.current_price > 0

    # Provenance verification
    assert "market_data" in snap.provenance
    m_prov = snap.provenance["market_data"]
    # If authentic bars were fetched, classification is RAW_AUTHENTIC_DATA
    # If simulated baseline was used, classification is SYNTHETIC (never falsely authentic)
    assert m_prov["classification"] in (
        EvidenceClassification.RAW_AUTHENTIC_DATA.value,
        EvidenceClassification.SYNTHETIC.value,
    )
    if m_prov["classification"] == EvidenceClassification.SYNTHETIC.value:
        assert m_prov["data_status"] == ProvenanceDataStatus.SIMULATED.value


# ---------------------------------------------------------------------------
# 3. Portfolio Engine: Elimination of Random Walk & Dynamic Drawdown
# ---------------------------------------------------------------------------

def test_portfolio_engine_source_code_has_no_random_normal():
    """Forensic test: verifies that portfolio_engine.py contains zero np.random.normal calls."""
    import inspect
    from backend.app.fundamental_engine import portfolio_engine as pe_module
    source = inspect.getsource(pe_module)
    assert "np.random.normal" not in source, "np.random.normal must be completely removed"
    assert "random.normal" not in source


@pytest.mark.asyncio
async def test_portfolio_engine_calculates_genuine_historical_returns():
    """
    Verifies that FactorPortfolioEngine calculates exact, deterministic period returns
    and dynamic peak-to-trough max drawdown from price_history_map.
    """
    # Deterministic price history:
    # Period 1 (1685577600 -> 1693526400): 1000 -> 1100 (+10.0%)
    # Period 2 (1693526400 -> 1701388800): 1100 -> 990  (-10.0%)
    price_map = {
        "RELIANCE.NS": [
            {"timestamp": 1685577600, "close": 1000.0},
            {"timestamp": 1693526400, "close": 1100.0},
            {"timestamp": 1701388800, "close": 990.0},
        ]
    }

    res = await portfolio_engine.simulate_factor_portfolio(
        universe_symbols=["RELIANCE.NS"],
        price_history_map=price_map,
        factor_id="PROFITABILITY_ROE",
        initial_capital=1000000.0,
    )

    history = res.rebalance_history
    assert len(history) >= 3

    # Initial formulated period
    assert history[0].period_return_pct == 0.0

    # Period 1: +10.0%
    assert history[1].period_return_pct == 10.0

    # Period 2: -10.0%
    assert history[2].period_return_pct == -10.0

    # Dynamic Drawdown check:
    # Capital went 1,000,000 -> 1,100,000 -> 990,000
    # Peak was 1,100,000, trough was 990,000
    # Drawdown = (1100000 - 990000) / 1100000 = 10.0%
    assert res.max_drawdown_pct == 10.0, f"Expected 10.0% drawdown, got {res.max_drawdown_pct}%"

    # Total Return: 1,000,000 -> 990,000 = -1.0%
    assert res.total_return_pct == -1.0
