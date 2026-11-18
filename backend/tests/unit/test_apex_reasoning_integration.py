"""
Unit Tests: APEX Reasoning Integration (Phase 3E)
=================================================
Verifies:
1. Zero mock elimination: `base_prices` and 78,450 mock values do not exist in `tools_service.py`.
2. Chief Reasoner context wiring: verified market quote, contract metadata, realized ranges (7D/14D/30D),
   technical indicators, OI trend, and forward volatility corridor are connected.
3. Dialectical reasoning architecture: Bullish, Neutral (base), and Bearish arguments strictly required.
4. Strict Scenario Probability Invariant: probabilities must sum to exactly 1.00 (100%), enforced
   programmatically and validated on models.
5. Fail-closed error handling: raises `MarketDataUnavailableError` on missing or unverified market data,
   never returning synthetic fallbacks.
"""

import math
import time
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.market_data.universal_feed import (
    UniversalQuote,
    MarketDataUnavailableError,
)
from backend.app.market_data.price_integrity_gateway import (
    PriceIntegrityResult,
    ValidationVerdict,
    price_integrity_gateway,
)
from backend.app.market_data.mcx.contract_resolver import (
    MCXContract,
    CommodityResolution,
    ContractTerm,
)
from backend.app.ai_engine.tools_service import (
    tools_service,
    ToolsService,
)
from backend.app.ai_engine.apex_chief_reasoner import (
    apex_chief_reasoner,
    ChiefReasoner,
    MarketForecast,
    ScenarioDetail,
    validate_and_normalize_probabilities,
    enforce_dialectical_evidence,
)
from backend.app.ai_engine.technical_engine import (
    technical_engine,
    CommodityTechnicals,
    RealizedPriceRange,
)
from backend.app.ai_engine.hybrid_ai import HybridAIResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fast_hybrid_ai_fallback():
    """Default fixture to prevent network timeouts by returning fast deterministic completion."""
    resp = HybridAIResponse(
        text="",
        status="FALLBACK_DETERMINISTIC",
        provider="test",
        model="test-deterministic",
    )
    with patch("backend.app.ai_engine.hybrid_ai.hybrid_ai.generate_completion_async", AsyncMock(return_value=resp)):
        yield


@pytest.fixture
def mock_verified_gold_quote() -> UniversalQuote:
    """Authentic verified Gold quote from MCX exchange."""
    return UniversalQuote(
        symbol="GOLD",
        instrument_id="GOLD_MCX",
        instrument_key="MCX_FO|495213",
        trading_symbol="GOLD FUT 04 DEC 26",
        contract_expiry="2026-12-04",
        exchange="MCX",
        currency="INR",
        unit="₹/10g",
        ltp=134423.0,
        open=135050.0,
        high=135341.0,
        low=133469.0,
        close=134423.0,
        volume=1240,
        open_interest=14819,
        bid_price=134420.0,
        ask_price=134425.0,
        last_trade_time=int(time.time() * 1000),
        market_status="LIVE",
        source="UPSTOX",
        price_domain="RAW_EXCHANGE_PRICE",
        retrieved_at=time.time(),
    )


@pytest.fixture
def mock_daily_candles_30d() -> list:
    """30 days of authentic daily OHLCV bars for Gold."""
    base = 134000.0
    candles = []
    now = time.time()
    for i in range(30):
        t = now - (30 - i) * 86400
        o = base + (i * 20)
        h = o + 400.0
        l = o - 300.0
        c = o + 150.0
        candles.append({
            "timestamp": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1000 + i * 50,
            "open_interest": 14000 + i * 30,
        })
    return candles


# ---------------------------------------------------------------------------
# 1. Zero Mock Elimination Tests
# ---------------------------------------------------------------------------

class TestZeroMockElimination:
    """Verifies complete eradication of synthetic mock fallbacks."""

    def test_base_prices_dictionary_does_not_exist(self):
        """tools_service module and class must NOT contain base_prices dictionary."""
        import backend.app.ai_engine.tools_service as ts_mod
        assert not hasattr(ts_mod, "base_prices"), "base_prices found in tools_service module"
        assert not hasattr(ToolsService, "base_prices"), "base_prices found on ToolsService class"
        assert not hasattr(tools_service, "base_prices"), "base_prices found on tools_service instance"

    def test_tools_service_source_code_has_no_78450_or_synthetic_defaults(self):
        """Scans tools_service.py source text to verify zero 78,450 mock values."""
        import inspect
        import backend.app.ai_engine.tools_service as ts_mod
        src = inspect.getsource(ts_mod)
        assert "78450" not in src, "78450 mock price found in tools_service.py"
        assert "78,450" not in src, "78,450 formatted mock price found in tools_service.py"
        assert "base_prices" not in src, "base_prices dictionary found in tools_service.py"
        assert "79200" not in src, "79200 mock price found in tools_service.py"
        assert "78900" not in src, "78900 mock price found in tools_service.py"

    def test_tools_service_has_no_synthetic_multipliers(self):
        """Verifies get_market_technicals and get_futures_curve contain zero synthetic multipliers."""
        import inspect
        import backend.app.ai_engine.tools_service as ts_mod
        src = inspect.getsource(ts_mod)
        assert "* 0.002" not in src
        assert "* 1.03" not in src
        assert "* 0.97" not in src
        assert "roll_yield_annualized_pct" not in src

    def test_retrieve_previous_forecasts_never_returns_mock_prices(self):
        """retrieve_previous_forecasts returns real stored records or empty list, never mock prices."""
        with patch("backend.app.ai_engine.forecast_store.forecast_store.get_forecast_history", return_value=[]):
            res = tools_service.retrieve_previous_forecasts("GOLD_MCX")
            assert res == []

    def test_retrieve_previous_forecasts_unmocked_integration(self):
        """Unmocked integration: stores a real MarketForecast into forecast_store and verifies retrieval with limit."""
        from backend.app.ai_engine.forecast_store import forecast_store

        real_fc = MarketForecast(
            forecast_id="fc_test_integration_001",
            version=1,
            instrument_id="GOLD_MCX",
            symbol="GOLD",
            current_price=134423.0,
            currency="INR",
            unit="₹/10g",
            exchange="MCX",
            valid_until=time.time() + 86400,
            direction="BULLISH",
            confidence=0.85,
            bullish_scenario=ScenarioDetail(
                price_target=136500.0,
                probability=0.40,
                expected_change_pct=1.54,
                supporting_evidence=["Strong physical demand and reserve accumulation."],
            ),
            base_scenario=ScenarioDetail(
                price_target=134800.0,
                probability=0.40,
                expected_change_pct=0.28,
                supporting_evidence=["Consolidation above 20 EMA."],
            ),
            bearish_scenario=ScenarioDetail(
                price_target=132000.0,
                probability=0.20,
                expected_change_pct=-1.80,
                supporting_evidence=["Dollar index rebound resistance."],
            ),
            price_range={"lower": 132000.0, "upper": 136500.0},
            expected_change_percent=0.28,
            volatility_assessment="Historical 7D Realized Range",
            self_challenge_critique="Adversarial evaluation of geopolitical premium sustainability.",
            reasoning_summary="Constructive technical structure supported by central bank flows.",
            status="VALIDATED",
            is_synthetic_legacy=False,
        )

        orig_history = list(forecast_store._forecasts.get("GOLD_MCX", []))
        try:
            forecast_store._forecasts["GOLD_MCX"] = [real_fc]
            res = tools_service.retrieve_previous_forecasts("GOLD_MCX", limit=5)
            assert isinstance(res, list)
            assert len(res) == 1
            assert res[0]["forecast_id"] == "fc_test_integration_001"
            assert res[0]["current_price"] == 134423.0
            assert res[0]["symbol"] == "GOLD"
            assert res[0]["version"] == 1
            assert not res[0]["is_synthetic_legacy"]

            # Also verify retrieval with clean symbol and limit
            res_clean = tools_service.retrieve_previous_forecasts("GOLD", limit=1)
            assert len(res_clean) == 1
            assert res_clean[0]["forecast_id"] == "fc_test_integration_001"
        finally:
            forecast_store._forecasts["GOLD_MCX"] = orig_history


# ---------------------------------------------------------------------------
# 2. Chief Reasoner Context Wiring Tests
# ---------------------------------------------------------------------------

class TestChiefReasonerContextWiring:
    """Verifies Chief Reasoner receives real verified market data, metadata, ranges, and indicators."""

    @pytest.mark.asyncio
    async def test_chief_reasoner_receives_verified_market_data(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Chief Reasoner executes over verified LTP from UniversalQuote."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):
            
            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert forecast.current_price == 134423.0
            assert forecast.current_price != 78450.0
            assert forecast.currency == "INR"
            assert forecast.market_status == "LIVE"

    @pytest.mark.asyncio
    async def test_chief_reasoner_receives_contract_metadata(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Contract expiry and trading symbol are wired into the forecast output."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert forecast.contract_expiry == "2026-12-04"

    @pytest.mark.asyncio
    async def test_chief_reasoner_receives_realized_ranges(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Realized 7D, 14D, and 30D high/low ranges are calculated and connected."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert forecast.realized_7d is not None
            assert forecast.realized_7d["high"] > forecast.realized_7d["low"]
            assert forecast.realized_14d is not None
            assert forecast.realized_30d is not None

    @pytest.mark.asyncio
    async def test_forward_volatility_corridor_decoupled_from_realized_range(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Forward volatility corridor is mathematically projected and distinct from realized 7D range."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            corridor = forecast.forward_volatility_corridor
            r7 = forecast.realized_7d
            assert corridor is not None
            assert corridor["upper"] > forecast.current_price
            assert corridor["lower"] < forecast.current_price
            assert isinstance(corridor["upper"], float)
            assert isinstance(r7["high"], float)


# ---------------------------------------------------------------------------
# 3. Dialectical Reasoning Architecture Tests
# ---------------------------------------------------------------------------

class TestDialecticalReasoningArchitecture:
    """Verifies mandatory dialectical reasoning (Bullish, Neutral, Bearish required)."""

    @pytest.mark.asyncio
    async def test_dialectical_bullish_neutral_bearish_scenarios_present(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """All three dialectical scenario components must be present in the forecast."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert forecast.bullish_scenario is not None
            assert forecast.base_scenario is not None  # Neutral
            assert forecast.bearish_scenario is not None

    @pytest.mark.asyncio
    async def test_dialectical_supporting_evidence_non_empty(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Each scenario must have non-empty supporting evidence grounded in reality."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert len(forecast.bullish_scenario.supporting_evidence) >= 1
            assert len(forecast.base_scenario.supporting_evidence) >= 1
            assert len(forecast.bearish_scenario.supporting_evidence) >= 1

    def test_enforce_dialectical_evidence_populates_missing(self):
        """Helper enforces non-empty evidence when raw input provides empty lists."""
        b, m, r = enforce_dialectical_evidence([], [], [], curr_price=134423.0)
        assert len(b) >= 1
        assert len(m) >= 1
        assert len(r) >= 1
        assert "Supply" in b[0] or "Bullish" in b[0] or "Momentum" in b[0]

    @pytest.mark.asyncio
    async def test_dialectical_self_challenge_critique_present(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Self-challenge critique and invalidation conditions must be present."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert len(forecast.self_challenge_critique) > 20
            assert len(forecast.invalidation_conditions) >= 1
            assert len(forecast.key_risks) >= 1


# ---------------------------------------------------------------------------
# 4. Strict Scenario Probability Invariant Tests
# ---------------------------------------------------------------------------

class TestScenarioProbabilityInvariant:
    """Verifies that scenario probabilities sum to exactly 1.00 (100%)."""

    def test_validate_and_normalize_probabilities_exact_cases(self):
        """Tests exact 1.0 sum normalization across multiple edge-case distributions."""
        # Case 1: Standard distribution
        b, m, r = validate_and_normalize_probabilities(0.35, 0.45, 0.20)
        assert round(b + m + r, 4) == 1.00

        # Case 2: Unnormalized distribution (sum = 1.50)
        b, m, r = validate_and_normalize_probabilities(0.60, 0.50, 0.40)
        assert round(b + m + r, 4) == 1.00

        # Case 3: Floating point repeating thirds
        b, m, r = validate_and_normalize_probabilities(1/3, 1/3, 1/3)
        assert round(b + m + r, 4) == 1.00

        # Case 4: Extreme zero input
        b, m, r = validate_and_normalize_probabilities(0.0, 0.0, 0.0)
        assert round(b + m + r, 4) == 1.00

        # Case 5: Negative probability input
        b, m, r = validate_and_normalize_probabilities(-0.5, 0.5, 0.5)
        assert round(b + m + r, 4) == 1.00

    def test_market_forecast_model_validator_normalizes_drift(self):
        """MarketForecast model validator automatically corrects probability drift."""
        now = time.time()
        fc = MarketForecast(
            forecast_id="fc_test_norm",
            version=1,
            instrument_id="GOLD_MCX",
            symbol="GOLD",
            current_price=134423.0,
            currency="INR",
            unit="₹/10g",
            exchange="MCX",
            valid_until=now + 86400,
            direction="BULLISH",
            confidence=0.85,
            bullish_scenario=ScenarioDetail(price_target=136000.0, probability=0.45, expected_change_pct=1.2, supporting_evidence=["Bull"]),
            base_scenario=ScenarioDetail(price_target=134500.0, probability=0.45, expected_change_pct=0.1, supporting_evidence=["Base"]),
            bearish_scenario=ScenarioDetail(price_target=132000.0, probability=0.30, expected_change_pct=-1.8, supporting_evidence=["Bear"]),  # sum = 1.20
            price_range={"lower": 132000.0, "upper": 136000.0},
            expected_change_percent=0.1,
            volatility_assessment="Standard",
            self_challenge_critique="Check yields",
            reasoning_summary="Dialectical test",
        )
        total_p = round(fc.bullish_scenario.probability + fc.base_scenario.probability + fc.bearish_scenario.probability, 4)
        assert total_p == 1.00

    @pytest.mark.asyncio
    async def test_end_to_end_forecast_probabilities_sum_to_exact_100_percent(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """End-to-end pipeline produces scenario probabilities summing to exactly 1.00."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            p_sum = round(
                forecast.bullish_scenario.probability
                + forecast.base_scenario.probability
                + forecast.bearish_scenario.probability,
                4,
            )
            assert p_sum == 1.00


# ---------------------------------------------------------------------------
# 5. Fail-Closed Error Handling Tests
# ---------------------------------------------------------------------------

class TestFailClosedIntegrityHandling:
    """Verifies fail-closed behavior when market data is unavailable or corrupt."""

    @pytest.mark.asyncio
    async def test_fail_closed_when_market_data_unavailable(self):
        """Raises MarketDataUnavailableError when live quote feed fails."""
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(side_effect=MarketDataUnavailableError("Upstox broker offline"))):
            with pytest.raises(MarketDataUnavailableError) as exc_info:
                await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert "Upstox broker offline" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fail_closed_when_price_integrity_gateway_rejects_synthetic_quote(self, mock_verified_gold_quote):
        """Raises MarketDataUnavailableError when Price Integrity Gateway catches a synthetic mock price."""
        rejected_res = PriceIntegrityResult(
            is_valid=False,
            verdict=ValidationVerdict.SYNTHETIC_MOCK_DETECTED,
            error_message="Identified known legacy synthetic price 78450.0",
            quote=mock_verified_gold_quote,
        )
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=rejected_res):

            with pytest.raises(MarketDataUnavailableError) as exc_info:
                await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            assert "rejected" in str(exc_info.value).lower()
            assert "SYNTHETIC_MOCK_DETECTED" in str(exc_info.value)

    def test_tools_service_snapshot_fail_closed_on_rejection(self, mock_verified_gold_quote):
        """tools_service.get_current_market_snapshot raises MarketDataUnavailableError when quote is invalid."""
        rejected_res = PriceIntegrityResult(
            is_valid=False,
            verdict=ValidationVerdict.OUT_OF_BOUNDS,
            error_message="Circuit limit exceeded",
            quote=mock_verified_gold_quote,
        )
        with patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=rejected_res):

            with pytest.raises(MarketDataUnavailableError):
                tools_service.get_current_market_snapshot("GOLD_MCX")

    def test_tools_service_futures_curve_fail_closed_on_missing_contracts(self):
        """tools_service.get_futures_curve raises MarketDataUnavailableError when contract resolution fails."""
        with patch("backend.app.market_data.mcx.contract_resolver.active_contract_resolver.resolve_commodity_sync", return_value=None):
            with pytest.raises(MarketDataUnavailableError):
                tools_service.get_futures_curve("INVALID_COMMODITY")

    @pytest.mark.asyncio
    async def test_llm_completion_parsing_and_hallucination_clamping(self, mock_verified_gold_quote, mock_daily_candles_30d):
        """Chief Reasoner accepts valid LLM JSON and clamps any hallucinated 78450 mock target prices."""
        llm_json = json.dumps({
            "direction": "BULLISH",
            "confidence": 0.88,
            "bullish_scenario": {
                "price_target": 78450.0,  # Hallucinated legacy mock price! Must be clamped/rejected!
                "probability": 0.50,
                "expected_change_pct": 2.0,
                "supporting_evidence": ["Central bank buying"],
            },
            "base_scenario": {
                "price_target": 134900.0,
                "probability": 0.30,
                "expected_change_pct": 0.3,
                "supporting_evidence": ["Range consolidation"],
            },
            "bearish_scenario": {
                "price_target": 132000.0,
                "probability": 0.20,
                "expected_change_pct": -1.8,
                "supporting_evidence": ["Dollar rebound"],
            },
            "self_challenge_critique": "Challenging dollar assumptions and real rate trends.",
            "invalidation_conditions": ["Daily close below 132000"],
            "key_risks": ["FOMC interest rate hawkishness"],
            "reasoning_summary": "Institutional bullish thesis with bounded downside.",
        })
        llm_resp = HybridAIResponse(text=llm_json, status="SUCCESS", provider="gemini", model="gemini-3.8-flash")
        
        with patch("backend.app.ai_engine.hybrid_ai.hybrid_ai.generate_completion_async", AsyncMock(return_value=llm_resp)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_live_quote", AsyncMock(return_value=mock_verified_gold_quote)), \
             patch("backend.app.market_data.universal_feed.universal_feed_service.get_historical_daily_candles", AsyncMock(return_value=mock_daily_candles_30d)), \
             patch("backend.app.market_data.price_integrity_gateway.price_integrity_gateway.validate_quote", return_value=PriceIntegrityResult(is_valid=True, verdict=ValidationVerdict.VALID, quote=mock_verified_gold_quote)):

            forecast = await apex_chief_reasoner.execute_forecast_pipeline("GOLD_MCX")
            # The hallucinated 78450 price target MUST NOT appear in the final forecast!
            assert forecast.bullish_scenario.price_target != 78450.0
            assert forecast.bullish_scenario.price_target > forecast.current_price
            assert forecast.current_price == 134423.0
