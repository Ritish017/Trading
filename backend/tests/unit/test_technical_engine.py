"""
Unit Tests for APEX Commodity Historical & Technical Engine (Phase 3D)
=====================================================================
Validates:
1. Realized price range calculations (7D, 14D, 30D).
2. Indicator calculations (SMA 20/50/200, EMA 20/50, RSI 14, MACD 12/26/9, ATR 14, 20D volume avg).
3. Open Interest (OI) buildup classification across all 4 regimes + neutral.
4. Forward volatility corridor projection and mathematical separation from realized ranges.
5. Boundary and edge cases (empty lists, single candles, missing OI, NaN values, zero true range).
6. Dual-signature API compatibility and re-export parity.
7. UniversalMarketDataFeed and MarketDataService integration.
"""

import math
import pytest
from typing import List, Dict, Any

from backend.app.market_data.technical_engine import (
    RealizedPriceRange,
    CommodityTechnicals,
    TechnicalEngine,
    technical_engine,
    compute_realized_range,
    compute_technical_indicators,
)
from backend.app.ai_engine.technical_engine import (
    technical_engine as ai_technical_engine,
    CommodityTechnicals as AICommodityTechnicals,
)
from backend.app.market_data.universal_feed import UniversalQuote, universal_feed
from backend.app.market_data.service import MarketDataService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_30d_candles() -> List[Dict[str, Any]]:
    """
    30 daily candle bars with realistic MCX Gold prices.
    Low at 133,469.0 and High at 142,500.0.
    """
    bars = []
    base_price = 138000.0
    for i in range(1, 31):
        if i == 5:
            # Global 30D low
            h, l, c = 135000.0, 133469.0, 134200.0
        elif i == 18:
            # Global 30D high
            h, l, c = 142500.0, 140000.0, 141800.0
        else:
            jitter = (i % 5) * 500.0 - 1000.0
            c = base_price + jitter
            h = c + 400.0
            l = c - 400.0

        bars.append({
            "timestamp": f"2026-10-{i:02d}T00:00:00Z",
            "open": c - 100.0,
            "high": h,
            "low": l,
            "close": c,
            "volume": 1000 + i * 50,
            "open_interest": 10000 + i * 100,
        })
    return bars


@pytest.fixture
def sample_quote() -> UniversalQuote:
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
        volume=2500,
        open_interest=14819,
        bid_price=134420.0,
        ask_price=134425.0,
        last_trade_time=1763481600000,
        market_status="LIVE",
        source="UPSTOX",
        price_domain="RAW_EXCHANGE_PRICE",
    )


# ---------------------------------------------------------------------------
# 1. Realized Price Range Calculations
# ---------------------------------------------------------------------------

class TestRealizedPriceRanges:

    def test_realized_7d_calculation(self, mock_30d_candles):
        r7 = compute_realized_range(mock_30d_candles, days=7)
        assert r7.period_days == 7
        assert r7.high >= r7.low
        assert r7.range_span == pytest.approx(r7.high - r7.low, rel=1e-4)
        expected_pct = (r7.high - r7.low) / r7.low * 100.0
        assert r7.range_span_pct == pytest.approx(expected_pct, rel=1e-4)

    def test_realized_14d_calculation(self, mock_30d_candles):
        r14 = compute_realized_range(mock_30d_candles, days=14)
        assert r14.period_days == 14
        assert r14.high >= r14.low
        assert r14.range_span == round(r14.high - r14.low, 2)

    def test_realized_30d_calculation_matches_known_extrema(self, mock_30d_candles):
        r30 = compute_realized_range(mock_30d_candles, days=30)
        assert r30.period_days == 30
        assert r30.high == 142500.00
        assert r30.low == 133469.00
        assert r30.range_span == round(142500.00 - 133469.00, 2)
        expected_pct = (142500.00 - 133469.00) / 133469.00 * 100.0
        assert r30.range_span_pct == pytest.approx(expected_pct, rel=1e-4)

    def test_realized_range_monotonic_widening(self, mock_30d_candles):
        """A larger lookback window must have high >= smaller window and low <= smaller window."""
        r7 = compute_realized_range(mock_30d_candles, days=7)
        r14 = compute_realized_range(mock_30d_candles, days=14)
        r30 = compute_realized_range(mock_30d_candles, days=30)

        assert r30.high >= r14.high
        assert r30.low <= r14.low
        assert r30.range_span >= r14.range_span

    def test_realized_range_weekend_and_gaps(self):
        """Non-consecutive trading days should be sliced by bar count cleanly."""
        gap_bars = [
            {"high": 105.0, "low": 95.0, "close": 100.0},
            {"high": 110.0, "low": 98.0, "close": 108.0},
            {"high": 115.0, "low": 102.0, "close": 112.0},
        ]
        r = compute_realized_range(gap_bars, days=7)
        assert r.high == 115.0
        assert r.low == 95.0
        assert r.range_span == 20.0
        assert r.range_span_pct == pytest.approx(20.0 / 95.0 * 100.0, rel=1e-4)


# ---------------------------------------------------------------------------
# 2. Indicator Calculations
# ---------------------------------------------------------------------------

class TestTechnicalIndicators:

    def test_sma_20_arithmetic_mean(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        last_20_closes = [b["close"] for b in mock_30d_candles[-20:]]
        expected_sma20 = sum(last_20_closes) / 20.0
        assert ind["sma_20"] == pytest.approx(expected_sma20, rel=1e-2)

    def test_sma_thresholds_missing_if_insufficient(self):
        bars_15 = [{"close": 100.0 + i, "high": 105.0 + i, "low": 95.0 + i} for i in range(15)]
        ind = compute_technical_indicators(bars_15)
        assert ind["sma_20"] is None
        assert ind["sma_50"] is None
        assert ind["sma_200"] is None

    def test_sma_50_and_200_with_sufficient_bars(self):
        bars_250 = [{"close": 100.0 + (i % 20), "high": 125.0, "low": 90.0, "volume": 500} for i in range(250)]
        ind = compute_technical_indicators(bars_250)
        assert ind["sma_20"] is not None
        assert ind["sma_50"] is not None
        assert ind["sma_200"] is not None
        assert ind["ema_20"] is not None
        assert ind["ema_50"] is not None

    def test_ema_20_weighting(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        assert ind["ema_20"] is not None
        assert 130000.0 <= ind["ema_20"] <= 145000.0

    def test_rsi_14_boundedness(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        assert ind["rsi_14"] is not None
        assert 0.0 <= ind["rsi_14"] <= 100.0

    def test_rsi_monotonic_gains_equals_100(self):
        monotonic_up = [
            {"close": 100.0 + i, "high": 105.0 + i, "low": 95.0 + i, "volume": 100}
            for i in range(20)
        ]
        ind = compute_technical_indicators(monotonic_up)
        assert ind["rsi_14"] == pytest.approx(100.0, abs=1e-2)

    def test_rsi_monotonic_losses_equals_0(self):
        monotonic_down = [
            {"close": 200.0 - i, "high": 205.0 - i, "low": 195.0 - i, "volume": 100}
            for i in range(20)
        ]
        ind = compute_technical_indicators(monotonic_down)
        assert ind["rsi_14"] == pytest.approx(0.0, abs=1e-2)

    def test_rsi_flat_equals_50(self):
        flat_bars = [
            {"close": 100.0, "high": 100.0, "low": 100.0, "volume": 100}
            for _ in range(20)
        ]
        ind = compute_technical_indicators(flat_bars)
        assert ind["rsi_14"] == 50.0

    def test_macd_formula_consistency(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        assert ind["macd"] is not None
        assert ind["macd_signal"] is not None
        assert ind["macd_hist"] is not None
        # Hist must strictly equal macd - macd_signal
        assert ind["macd_hist"] == pytest.approx(ind["macd"] - ind["macd_signal"], abs=1e-3)

    def test_macd_flat_converges_to_zero(self):
        flat_30 = [
            {"close": 150.0, "high": 150.0, "low": 150.0, "volume": 100}
            for _ in range(30)
        ]
        ind = compute_technical_indicators(flat_30)
        assert ind["macd"] == pytest.approx(0.0, abs=1e-4)
        assert ind["macd_signal"] == pytest.approx(0.0, abs=1e-4)
        assert ind["macd_hist"] == pytest.approx(0.0, abs=1e-4)

    def test_atr_14_positive_and_calculated(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        assert ind["atr_14"] is not None
        assert ind["atr_14"] > 0

    def test_atr_zero_true_range_flat_bars(self):
        flat_20 = [
            {"close": 100.0, "high": 100.0, "low": 100.0, "volume": 100}
            for _ in range(20)
        ]
        ind = compute_technical_indicators(flat_20)
        assert ind["atr_14"] == pytest.approx(0.0, abs=1e-4)

    def test_volume_20d_avg(self, mock_30d_candles):
        ind = compute_technical_indicators(mock_30d_candles)
        expected_vol = sum(b["volume"] for b in mock_30d_candles[-20:]) / 20.0
        assert ind["volume_20d_avg"] == pytest.approx(expected_vol, rel=1e-2)


# ---------------------------------------------------------------------------
# 3. Open Interest (OI) Trend Classification
# ---------------------------------------------------------------------------

class TestOpenInterestClassification:

    def test_long_buildup(self):
        """Price up & OI up -> LONG_BUILDUP"""
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 105.0, "high": 107.0, "low": 101.0, "open_interest": 1200},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "LONG_BUILDUP"

    def test_short_buildup(self):
        """Price down & OI up -> SHORT_BUILDUP"""
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 95.0, "high": 99.0, "low": 94.0, "open_interest": 1200},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "SHORT_BUILDUP"

    def test_long_unwinding(self):
        """Price down & OI down -> LONG_UNWINDING"""
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 95.0, "high": 99.0, "low": 94.0, "open_interest": 800},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "LONG_UNWINDING"

    def test_short_covering(self):
        """Price up & OI down -> SHORT_COVERING"""
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 105.0, "high": 107.0, "low": 101.0, "open_interest": 800},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "SHORT_COVERING"

    def test_neutral_when_price_unchanged(self):
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1200},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "NEUTRAL"

    def test_neutral_when_oi_unchanged(self):
        candles = [
            {"close": 100.0, "high": 102.0, "low": 99.0, "open_interest": 1000},
            {"close": 105.0, "high": 107.0, "low": 101.0, "open_interest": 1000},
        ]
        ind = compute_technical_indicators(candles)
        assert ind["oi_trend"] == "NEUTRAL"

    def test_neutral_on_single_candle_or_missing_oi(self):
        single = [{"close": 100.0, "high": 102.0, "low": 99.0}]
        assert compute_technical_indicators(single)["oi_trend"] == "NEUTRAL"

        no_oi = [
            {"close": 100.0, "high": 102.0, "low": 99.0},
            {"close": 105.0, "high": 107.0, "low": 101.0},
        ]
        assert compute_technical_indicators(no_oi)["oi_trend"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# 4. Forward Volatility Corridor & Separation from Realized Ranges
# ---------------------------------------------------------------------------

class TestForwardVolatilityCorridor:

    def test_corridor_strictly_separated_from_realized_7d(self, mock_30d_candles):
        curr_price = 134423.0
        tech = technical_engine.compute_technicals(
            candles=mock_30d_candles,
            current_price=curr_price,
            instrument_id="GOLD_MCX",
        )

        assert tech.forward_corridor_lower < tech.verified_price
        assert tech.forward_corridor_upper > tech.verified_price

        # Realized 7D range and forward corridor must have independent, non-identical values
        assert tech.realized_7d.high != tech.forward_corridor_upper
        assert tech.realized_7d.low != tech.forward_corridor_lower

    def test_corridor_proportional_to_atr(self, mock_30d_candles):
        curr_price = 134423.0
        tech = technical_engine.compute_technicals(mock_30d_candles, curr_price, "GOLD_MCX")
        atr = tech.atr_14
        assert atr is not None and atr > 0

        expected_lower = round(max(0.01, curr_price - (2.0 * atr)), 2)
        expected_upper = round(curr_price + (2.0 * atr), 2)

        assert tech.forward_corridor_lower == pytest.approx(expected_lower, abs=1e-2)
        assert tech.forward_corridor_upper == pytest.approx(expected_upper, abs=1e-2)

    def test_corridor_non_negative(self):
        cheap_candle = [{"close": 0.50, "high": 1.0, "low": 0.10, "volume": 100} for _ in range(20)]
        tech = technical_engine.compute_technicals(cheap_candle, 0.50, "CHEAP_COMMODITY")
        assert tech.forward_corridor_lower >= 0.01


# ---------------------------------------------------------------------------
# 5. Boundary & Edge Cases
# ---------------------------------------------------------------------------

class TestBoundaryAndEdgeCases:

    def test_empty_candle_list(self):
        tech = technical_engine.compute_technicals([], 100.0, "EMPTY_MCX")
        assert tech.verified_price == 100.0
        assert tech.realized_7d.high == 100.0
        assert tech.realized_7d.low == 100.0
        assert tech.realized_7d.range_span == 0.0
        assert tech.realized_7d.range_span_pct == 0.0
        assert tech.sma_20 is None
        assert tech.rsi_14 is None
        assert tech.macd is None
        assert tech.atr_14 is None
        assert tech.oi_trend == "NEUTRAL"
        assert tech.forward_corridor_lower > 0
        assert tech.forward_corridor_upper > tech.forward_corridor_lower

    def test_single_candle(self):
        single = [{"close": 5000.0, "high": 5100.0, "low": 4900.0, "volume": 50, "open_interest": 100}]
        tech = technical_engine.compute_technicals(single, 5000.0, "SINGLE_MCX")
        assert tech.realized_7d.high == 5100.0
        assert tech.realized_7d.low == 4900.0
        assert tech.realized_7d.range_span == 200.0
        assert tech.sma_20 is None
        assert tech.oi_trend == "NEUTRAL"

    def test_exact_14_bar_boundary(self):
        bars_14 = [
            {"close": 100.0 + i, "high": 102.0 + i, "low": 99.0 + i, "volume": 100, "open_interest": 100}
            for i in range(14)
        ]
        tech = technical_engine.compute_technicals(bars_14, 113.0, "EXACT_14")
        assert tech.rsi_14 is not None
        assert tech.atr_14 is not None
        assert tech.sma_20 is None  # Needs 20 bars

    def test_nan_and_corrupt_candle_handling(self):
        corrupt_bars = [
            {"close": float("nan"), "high": 105.0, "low": 95.0},
            {"close": 100.0, "high": None, "low": 95.0},
            {"close": "invalid", "high": 105.0, "low": 95.0},
            {"close": 102.0, "high": 106.0, "low": 98.0, "volume": 200, "open_interest": 500},
            {"close": 104.0, "high": 108.0, "low": 100.0, "volume": 300, "open_interest": 600},
        ]
        tech = technical_engine.compute_technicals(corrupt_bars, 104.0, "CORRUPT_MCX")
        assert tech.verified_price == 104.0
        assert tech.realized_7d.high >= 104.0
        assert tech.oi_trend == "LONG_BUILDUP"


# ---------------------------------------------------------------------------
# 6. API Signatures & Re-export Parity
# ---------------------------------------------------------------------------

class TestAPISignaturesAndReexports:

    def test_positional_quote_and_candles(self, sample_quote, mock_30d_candles):
        tech = technical_engine.compute_technicals(sample_quote, mock_30d_candles)
        assert tech.instrument_id == "GOLD_MCX"
        assert tech.verified_price == 134423.0
        assert isinstance(tech, CommodityTechnicals)

    def test_positional_candles_price_instrument(self, mock_30d_candles):
        tech = technical_engine.compute_technicals(mock_30d_candles, 134423.0, "GOLD_MCX")
        assert tech.instrument_id == "GOLD_MCX"
        assert tech.verified_price == 134423.0

    def test_ai_engine_reexport_parity(self, mock_30d_candles):
        tech1 = technical_engine.compute_technicals(mock_30d_candles, 134423.0, "GOLD_MCX")
        tech2 = ai_technical_engine.compute_technicals(mock_30d_candles, 134423.0, "GOLD_MCX")
        assert tech1.model_dump() == tech2.model_dump()
        assert isinstance(tech2, AICommodityTechnicals)


# ---------------------------------------------------------------------------
# 7. Integration with UniversalMarketDataFeed & MarketDataService
# ---------------------------------------------------------------------------

class TestFeedAndServiceIntegration:

    @pytest.mark.asyncio
    async def test_universal_feed_get_technicals_with_mocked_exchange(self, mock_30d_candles, sample_quote, monkeypatch):
        """Verifies UniversalMarketDataFeed.get_technicals fetches quote and candles then returns CommodityTechnicals."""
        async def fake_get_live_quote(self, commodity_input, term=None):
            return sample_quote

        async def fake_get_historical_daily_candles(self, commodity_input, lookback_days=30, term=None):
            return mock_30d_candles

        monkeypatch.setattr(universal_feed, "get_live_quote", fake_get_live_quote.__get__(universal_feed))
        monkeypatch.setattr(universal_feed, "get_historical_daily_candles", fake_get_historical_daily_candles.__get__(universal_feed))

        tech = await universal_feed.get_technicals("GOLD")
        assert isinstance(tech, CommodityTechnicals)
        assert tech.verified_price == 134423.0
        assert tech.realized_30d.high == 142500.0
        assert tech.realized_30d.low == 133469.0
        assert tech.atr_14 is not None

    @pytest.mark.asyncio
    async def test_market_data_service_get_commodity_technicals(self, mock_30d_candles, sample_quote, monkeypatch):
        """Verifies MarketDataService.get_commodity_technicals delegates seamlessly."""
        async def fake_get_technicals(self, commodity_input, lookback_days=30, term=None):
            return technical_engine.compute_technicals(sample_quote, mock_30d_candles)

        service = MarketDataService()
        monkeypatch.setattr(service.universal_feed, "get_technicals", fake_get_technicals.__get__(service.universal_feed))

        tech = await service.get_commodity_technicals("GOLD")
        assert isinstance(tech, CommodityTechnicals)
        assert tech.instrument_id == "GOLD_MCX"
        assert tech.verified_price == 134423.0
