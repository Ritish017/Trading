"""
APEX E2E Testing Harness — Shared Configuration & Fixtures.
Provides isolated, deterministic, credential-free fixtures for all 4 test tiers.
"""

import os
import time
import tempfile
import pytest
from typing import Dict, Any, List
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.signal_engine.models import (
    AssetClass,
    SignalDirection,
    SignalEngineConfig,
    StopLossResult,
    TargetLevel,
)
from backend.app.signal_engine.options_engine import OptionContract, OptionType


# Configure deterministic test authentication environment
TEST_TOKEN_A = "apex_e2e_secret_token_primary"
TEST_TOKEN_B = "apex_e2e_secret_token_secondary"
TEST_CONFIG_AUTH = f"{TEST_TOKEN_A}:primary_personal_account,{TEST_TOKEN_B}:account_b"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configures global test settings: isolated DB, safe tokens, disabled live trading."""
    orig_token = settings.api_auth_token
    orig_env = settings.environment
    orig_capital = settings.default_paper_capital

    settings.api_auth_token = TEST_CONFIG_AUTH
    settings.environment = "testing"
    settings.default_paper_capital = 1000000.0

    yield

    settings.api_auth_token = orig_token
    settings.environment = orig_env
    settings.default_paper_capital = orig_capital


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Primary authenticated user headers."""
    return {"Authorization": f"Bearer {TEST_TOKEN_A}"}


@pytest.fixture
def auth_headers_account_b() -> Dict[str, str]:
    """Secondary authenticated user headers for tenant isolation testing."""
    return {"Authorization": f"Bearer {TEST_TOKEN_B}"}


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def clean_paper_engine() -> PaperTradingEngine:
    """Instantiates a fresh in-memory PaperTradingEngine."""
    engine = PaperTradingEngine(initial_capital=1000000.0, brokerage=20.0, slippage_pct=0.05)
    engine.reset_portfolio(1000000.0)
    return engine


@pytest.fixture
def sample_candles() -> List[Dict[str, Any]]:
    """Returns 30 completed 15m OHLCV bars for quantitative indicator calculation."""
    now = time.time()
    candles = []
    base_price = 2800.0
    for i in range(30):
        t = now - ((30 - i) * 900)
        o = base_price + (i * 2.0)
        h = o + 8.0
        l = o - 4.0
        c = o + 5.0
        v = 25000 + (i * 500)
        candles.append({
            "timestamp": t,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": v,
        })
    return candles


@pytest.fixture
def complete_option_chain() -> List[OptionContract]:
    """Complete, realistic option chain with all statutory contract parameters."""
    return [
        OptionContract(
            strike=24000.0,
            option_type=OptionType.CALL,
            expiry="2026-10-29",
            bid=250.0,
            ask=252.0,
            last_price=251.0,
            volume=5000,
            oi=25000,
            oi_change=1200,
            iv=0.15,
            delta=0.55,
            gamma=0.0012,
            theta=-12.5,
            vega=18.0,
            bid_ask_spread_pct=0.8,
        ),
        OptionContract(
            strike=24100.0,
            option_type=OptionType.CALL,
            expiry="2026-10-29",
            bid=180.0,
            ask=182.0,
            last_price=181.0,
            volume=4200,
            oi=32000,
            oi_change=2100,
            iv=0.152,
            delta=0.45,
            gamma=0.0014,
            theta=-11.8,
            vega=17.5,
            bid_ask_spread_pct=1.1,
        ),
        OptionContract(
            strike=24000.0,
            option_type=OptionType.PUT,
            expiry="2026-10-29",
            bid=210.0,
            ask=212.0,
            last_price=211.0,
            volume=6000,
            oi=28000,
            oi_change=-800,
            iv=0.155,
            delta=-0.45,
            gamma=0.0012,
            theta=-12.0,
            vega=18.0,
            bid_ask_spread_pct=0.95,
        ),
    ]


@pytest.fixture
def incomplete_option_chain() -> List[Dict[str, Any]]:
    """Defective option chain missing critical statutory parameters (IV, OI, Spread)."""
    return [
        {
            "strike": 24000.0,
            "option_type": "CE",
            # missing expiry, bid, ask, oi, volume, iv
        }
    ]
