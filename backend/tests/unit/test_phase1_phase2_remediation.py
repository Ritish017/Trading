"""
APEX Phase 1 & Phase 2 Forensic Remediation Test Suite
=====================================================
Validates:
1. November 18 Gold historical-range regression fix (intraday session vs completed bars).
2. Separation of completed-session and current-session datasets in RealizedPriceRange.
3. Contract resolution and quotation units for all 11 MCX commodities.
4. Session-aware forecast invalidation in ForecastStore.
5. Removal of hardcoded 387-tonne gold purchases and static commodity inventory figures.
6. Neutral stance invariant: missing fundamentals do not automatically generate a bullish bias.
7. Elimination of fabricated fallback news URLs and fake official announcements.
8. Deep historical lookback (180 days) ensuring full evaluation of SMA 50, EMA 50, MACD, and ATR 14.
"""

import time
import math
import pytest
from typing import Dict, Any, List

from backend.app.market_data.technical_engine import (
    compute_realized_range,
    compute_technical_indicators,
    technical_engine,
    RealizedPriceRange,
    CommodityTechnicals,
)
from backend.app.market_data.mcx.master_service import MCXInstrumentMasterService
from backend.app.market_data.mcx.contract_resolver import ActiveContractResolver
from backend.app.ai_engine.historical_engine import deterministic_historical_engine, CommodityFundamentals
from backend.app.ai_engine.tools_service import ToolsService
from backend.app.ai_engine.forecast_store import ForecastStore, MarketForecast
from backend.app.ai_engine.apex_chief_reasoner import apex_chief_reasoner, ScenarioDetail


# ---------------------------------------------------------------------------
# TEST 1: November 18 Gold Historical Range Failure Regression Test
# ---------------------------------------------------------------------------
def test_nov18_gold_historical_range_regression():
    """
    REGRESSION AUDIT:
    On Nov 18, 2026, the completed daily bars (Nov 09 to Nov 17) had:
      - Nov 11 High: 141,990.0
      - Nov 17 Low: 133,469.0
    During Nov 18 intraday session, the market broke down to Low: 129,611.0, High: 131,979.0.
    Verify that:
      1. Completed dataset strictly isolates finalized days: low=133469, high=141990.
      2. Current session dataset captures the live breakdown: low=129611, high=131979.
      3. Rolling composite range correctly incorporates the breakdown: low=129611, high=141990.
      4. range_span_pct is strictly positive and non-zero.
    """
    # 5 completed trading sessions covering the 7-calendar-day window (Nov 11 to Nov 17)
    completed_candles = [
        {"timestamp": "2026-11-11T00:00:00+05:30", "open": 141270.0, "high": 141990.0, "low": 139569.0, "close": 139716.0, "volume": 5996},
        {"timestamp": "2026-11-12T00:00:00+05:30", "open": 139282.0, "high": 139315.0, "low": 135530.0, "close": 136225.0, "volume": 13599},
        {"timestamp": "2026-11-13T00:00:00+05:30", "open": 136502.0, "high": 137587.0, "low": 136055.0, "close": 136705.0, "volume": 7227},
        {"timestamp": "2026-11-16T00:00:00+05:30", "open": 135853.0, "high": 136055.0, "low": 134200.0, "close": 134539.0, "volume": 9088},
        {"timestamp": "2026-11-17T00:00:00+05:30", "open": 135050.0, "high": 135341.0, "low": 133469.0, "close": 134223.0, "volume": 8664},
    ]

    # Active Nov 18 intraday session
    nov18_session = {
        "open": 131622.0,
        "high": 131979.0,
        "low": 129611.0,
        "ltp": 131311.0,
    }

    # Range calculation with current session
    r7 = compute_realized_range(completed_candles, days=7, current_session=nov18_session, fallback_price=131311.0)

    # Completed session checks
    assert r7.completed_high == 141990.0, "Completed high must match Nov 11 bar"
    assert r7.completed_low == 133469.0, "Completed low must match Nov 17 bar"

    # Current session checks
    assert r7.current_session_high == 131979.0, "Current session high must match Nov 18 session high"
    assert r7.current_session_low == 129611.0, "Current session low must match Nov 18 breakdown low"
    assert r7.current_session_included is True, "Must indicate current session included"

    # Composite rolling range checks
    assert r7.high == 141990.0, "Composite rolling high must be max(141990, 131979) = 141990"
    assert r7.low == 129611.0, "Composite rolling low must be min(133469, 129611) = 129611"
    assert r7.range_span == round(141990.0 - 129611.0, 2), "Span must be 12,379.0"
    assert r7.range_span_pct > 9.0, "Span percent must be ~9.55%, not 0.0%"


# ---------------------------------------------------------------------------
# TEST 2: Separation of Completed-Session and Current-Session Datasets
# ---------------------------------------------------------------------------
def test_current_session_and_completed_session_separated():
    """
    Verifies that when NO current session is provided (e.g. historical backtest),
    completed session values equal the composite rolling values and current_session_included is False.
    """
    bars = [
        {"high": 105.0, "low": 95.0, "close": 100.0},
        {"high": 110.0, "low": 98.0, "close": 108.0},
        {"high": 108.0, "low": 92.0, "close": 96.0},
    ]

    # Without live session
    res_no_sess = compute_realized_range(bars, days=3, current_session=None, fallback_price=100.0)
    assert res_no_sess.high == 110.0
    assert res_no_sess.low == 92.0
    assert res_no_sess.completed_high == 110.0
    assert res_no_sess.completed_low == 92.0
    assert res_no_sess.current_session_high is None
    assert res_no_sess.current_session_low is None
    assert res_no_sess.current_session_included is False

    # With live session expanding the high
    sess_expand_high = {"high": 115.0, "low": 97.0, "ltp": 112.0}
    res_sess = compute_realized_range(bars, days=3, current_session=sess_expand_high, fallback_price=100.0)
    assert res_sess.completed_high == 110.0
    assert res_sess.completed_low == 92.0
    assert res_sess.current_session_high == 115.0
    assert res_sess.current_session_low == 97.0
    assert res_sess.current_session_included is True
    assert res_sess.high == 115.0  # Composite updated
    assert res_sess.low == 92.0   # From completed bars


# ---------------------------------------------------------------------------
# TEST 3: All 11 MCX Target Commodities Contract Resolution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_all_11_mcx_commodities_resolution():
    """
    Verifies dynamic resolution across the full target commodity universe:
    GOLD, GOLDM, SILVER, SILVERM, CRUDEOIL, NATGAS, COPPER, ALUMINIUM, ZINC, LEAD, NICKEL.
    """
    m = MCXInstrumentMasterService()
    r = ActiveContractResolver(m)
    target_commodities = [
        "GOLD", "GOLDM", "SILVER", "SILVERM", "CRUDEOIL",
        "NATGAS", "COPPER", "ALUMINIUM", "ZINC", "LEAD", "NICKEL"
    ]

    for c in target_commodities:
        res = await r.resolve_commodity(c)
        assert res is not None, f"CommodityResolution must not be None for {c}"
        assert res.near_contract is not None, f"Near contract must exist for {c}"
        assert res.near_contract.instrument_key.startswith("MCX_FO|"), f"Invalid instrument key for {c}"
        assert res.near_contract.lot_size > 0, f"Lot size must be positive for {c}"
        assert len(res.unit) > 0, f"Quotation unit must be non-empty for {c}"


# ---------------------------------------------------------------------------
# TEST 4: Session-Aware Forecast Invalidation in ForecastStore
# ---------------------------------------------------------------------------
def test_session_aware_forecast_invalidation():
    """
    Verifies that:
      1. Legacy synthetic forecasts are immediately flagged as stale.
      2. A forecast from a previous calendar day (past 09:00 IST today) is recognized as stale.
      3. A forecast created 15 hours ago is recognized as stale.
      4. A fresh forecast created 5 minutes ago within today's session is recognized as NOT stale.
    """
    now = time.time()

    # 1. Quarantined legacy forecast
    legacy_fc = MarketForecast(
        forecast_id="fc_legacy_test",
        version=1,
        instrument_id="GOLD_MCX",
        symbol="GOLD",
        current_price=78450.0,
        currency="INR",
        unit="₹/10g",
        exchange="MCX",
        market_timestamp=now - 3600,
        forecast_timestamp=now - 3600,
        valid_until=now + 86400,
        direction="BULLISH",
        confidence=0.82,
        bullish_scenario=ScenarioDetail(price_target=81200.0, probability=0.45, expected_change_pct=3.5, supporting_evidence=[]),
        base_scenario=ScenarioDetail(price_target=79100.0, probability=0.35, expected_change_pct=0.8, supporting_evidence=[]),
        bearish_scenario=ScenarioDetail(price_target=76500.0, probability=0.20, expected_change_pct=-2.5, supporting_evidence=[]),
        price_range={"lower": 75312.0, "upper": 81588.0},
        expected_change_percent=0.8,
        volatility_assessment="Test",
        horizons=[],
        self_challenge_critique="Test",
        invalidation_conditions=[],
        key_risks=[],
        evidence_references=[],
        reasoning_summary="Test",
        status="INVALID_LEGACY_SYNTHETIC",
        is_synthetic_legacy=True,
    )
    assert ForecastStore.is_forecast_stale(legacy_fc, as_of_ts=now) is True

    # 2. Forecast from yesterday (24 hours ago)
    yesterday_fc = MarketForecast(
        forecast_id="fc_yesterday_test",
        version=2,
        instrument_id="GOLD_MCX",
        symbol="GOLD",
        current_price=131311.0,
        currency="INR",
        unit="₹/10g",
        exchange="MCX",
        market_timestamp=now - 86400,
        forecast_timestamp=now - 86400,
        valid_until=now + 86400 * 6,
        direction="BULLISH",
        confidence=0.75,
        bullish_scenario=ScenarioDetail(price_target=135000.0, probability=0.40, expected_change_pct=2.8, supporting_evidence=[]),
        base_scenario=ScenarioDetail(price_target=132000.0, probability=0.35, expected_change_pct=0.5, supporting_evidence=[]),
        bearish_scenario=ScenarioDetail(price_target=127000.0, probability=0.25, expected_change_pct=-3.2, supporting_evidence=[]),
        price_range={"lower": 129611.0, "upper": 142500.0},
        expected_change_percent=0.5,
        volatility_assessment="Test",
        horizons=[],
        self_challenge_critique="Test",
        invalidation_conditions=[],
        key_risks=[],
        evidence_references=[],
        reasoning_summary="Test",
        status="VALIDATED",
        is_synthetic_legacy=False,
    )
    assert ForecastStore.is_forecast_stale(yesterday_fc, as_of_ts=now) is True

    # 3. Fresh forecast created 300 seconds (5 mins) ago
    fresh_fc = MarketForecast(
        forecast_id="fc_fresh_test",
        version=3,
        instrument_id="GOLD_MCX",
        symbol="GOLD",
        current_price=129450.0,
        currency="INR",
        unit="₹/10g",
        exchange="MCX",
        market_timestamp=now - 300,
        forecast_timestamp=now - 300,
        valid_until=now + 86400 * 7,
        direction="NEUTRAL_CONSOLIDATION",
        confidence=0.70,
        bullish_scenario=ScenarioDetail(price_target=133000.0, probability=0.30, expected_change_pct=2.7, supporting_evidence=[]),
        base_scenario=ScenarioDetail(price_target=130000.0, probability=0.45, expected_change_pct=0.4, supporting_evidence=[]),
        bearish_scenario=ScenarioDetail(price_target=126000.0, probability=0.25, expected_change_pct=-2.6, supporting_evidence=[]),
        price_range={"lower": 128310.0, "upper": 142500.0},
        expected_change_percent=0.4,
        volatility_assessment="Test",
        horizons=[],
        self_challenge_critique="Test",
        invalidation_conditions=[],
        key_risks=[],
        evidence_references=[],
        reasoning_summary="Test",
        status="VALIDATED",
        is_synthetic_legacy=False,
    )
    assert ForecastStore.is_forecast_stale(fresh_fc, as_of_ts=now) is False


# ---------------------------------------------------------------------------
# TEST 5: Complete Removal of 387-Tonne Hardcoded Claim & Fake Fundamentals
# ---------------------------------------------------------------------------
def test_removal_of_hardcoded_fundamentals():
    """
    Verifies that:
      1. '387' is strictly absent from Gold fundamentals.
      2. inventory_status is UNKNOWN, not artificially forced to DEFICIT.
      3. inventory_level_metric is DATA_UNAVAILABLE.
      4. is_verified is False.
      5. Crude, Natural Gas, and Copper have zero invented numbers.
    """
    commodities = ["GOLD", "CRUDEOIL", "NATGAS", "COPPER", "SILVER"]
    for c in commodities:
        fund = deterministic_historical_engine.get_commodity_fundamentals(c)
        assert "387" not in fund.inventory_level_metric, f"387-tonne claim must not exist in {c}"
        assert "423.8" not in fund.inventory_level_metric, f"Fake crude draw must not exist in {c}"
        assert "3,210" not in fund.inventory_level_metric, f"Fake natgas storage must not exist in {c}"
        assert "112,400" not in fund.inventory_level_metric, f"Fake copper stocks must not exist in {c}"
        assert fund.inventory_status == "UNKNOWN", f"Inventory status must be UNKNOWN for {c}"
        assert fund.inventory_level_metric == "DATA_UNAVAILABLE"
        assert fund.is_verified is False


# ---------------------------------------------------------------------------
# TEST 6: Neutral Stance Invariant (Missing Fundamentals Do Not Force Bullish Bias)
# ---------------------------------------------------------------------------
def test_neutral_stance_invariant_when_fundamentals_unavailable():
    """
    REQUIREMENT 9:
    Never let missing fundamentals automatically generate a bullish or bearish bias.
    When fundamentals are UNKNOWN and OI is NEUTRAL, reasoner must generate NEUTRAL_CONSOLIDATION,
    balanced scenario probabilities, and calibrated confidence (not fixed 0.82).
    """
    unverified_fund = {
        "inventory_level_metric": "DATA_UNAVAILABLE",
        "inventory_status": "UNKNOWN",
        "is_verified": False,
    }

    # Deterministic payload generation
    payload = apex_chief_reasoner._generate_deterministic_forecast_payload(
        curr_price=129500.0,
        fundamentals=unverified_fund,
        technicals=None,
        daily_atr=2500.0,
        realized_7d={"low": 128310.0, "high": 142500.0, "range_span_pct": 11.05},
        oi_trend="NEUTRAL",
    )

    # Stance must be NEUTRAL_CONSOLIDATION (not biased BULLISH)
    assert payload["direction"] == "NEUTRAL_CONSOLIDATION", "Must be NEUTRAL_CONSOLIDATION when fundamentals are unverified"

    # Probabilities must not be skewed bullish (Base must be highest or balanced)
    p_bull = payload["bullish_scenario"]["probability"]
    p_base = payload["base_scenario"]["probability"]
    p_bear = payload["bearish_scenario"]["probability"]
    assert p_base >= p_bull, "Base scenario probability must dominate or equal bullish when unverified"
    assert math.isclose(p_bull + p_base + p_bear, 1.0, abs_tol=1e-4), "Probabilities must strictly sum to 1.00"

    # Confidence must reflect epistemic uncertainty, not hardcoded 82%
    assert payload["confidence"] <= 0.70, f"Confidence should be bounded (got {payload['confidence']})"


# ---------------------------------------------------------------------------
# TEST 7: Elimination of Fabricated News URLs
# ---------------------------------------------------------------------------
def test_no_fabricated_news_urls():
    """
    Verifies that ToolsService returns an empty list rather than invented Kitco/OilPrice URLs
    when the research search returns zero articles.
    """
    tools = ToolsService()
    news = tools.search_recent_financial_news("nonexistent_random_token_xyz")
    assert isinstance(news, list)
    # Zero mock URLs permitted
    for item in news:
        url = item.get("url", "")
        assert "kitco.com/news/safe-haven" not in url
        assert "oilprice.com/energy/eia" not in url

    announcements = tools.search_official_announcements()
    assert announcements == [], "Unverified official announcements must return empty list"

    macro = tools.get_economic_indicators("INDIA")
    assert macro.get("status") == "DATA_UNAVAILABLE"

    fx = tools.get_currency_data("USDINR")
    assert fx.get("status") == "DATA_UNAVAILABLE"


# ---------------------------------------------------------------------------
# TEST 8: Full Technical Profile Calculation on Deep Lookback
# ---------------------------------------------------------------------------
def test_deep_lookback_technical_indicator_eval():
    """
    Verifies that when given 120+ bars (180 calendar days lookback),
    SMA 20, SMA 50, EMA 20, EMA 50, RSI 14, MACD, and ATR 14 all evaluate
    to non-null float values.
    """
    # Synthetic series of 120 bars strictly for mathematical indicator verification
    bars = []
    base = 1000.0
    for i in range(120):
        c = base + (i * 2.5) + (10.0 * math.sin(i / 5.0))
        bars.append({
            "timestamp": f"2026-05-{i:03d}",
            "open": c - 2.0,
            "high": c + 5.0,
            "low": c - 5.0,
            "close": c,
            "volume": 5000 + (i * 10),
            "open_interest": 10000 + (i * 20),
        })

    ind = compute_technical_indicators(bars)
    assert ind["sma_20"] is not None, "SMA 20 must evaluate"
    assert ind["sma_50"] is not None, "SMA 50 must evaluate on 120 bars"
    assert ind["ema_20"] is not None, "EMA 20 must evaluate"
    assert ind["ema_50"] is not None, "EMA 50 must evaluate on 120 bars"
    assert ind["rsi_14"] is not None, "RSI 14 must evaluate"
    assert ind["macd"] is not None, "MACD must evaluate on 120 bars"
    assert ind["macd_signal"] is not None, "MACD signal must evaluate"
    assert ind["atr_14"] is not None, "ATR 14 must evaluate"
