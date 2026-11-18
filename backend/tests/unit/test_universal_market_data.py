"""
Unit and Integration Tests: Universal Market Data Layer
=======================================================
Phase 3B Verification Suite covering:
1. UniversalQuote Data Model (validation, fields, finite prices, provenance, raw payload preservation)
2. UniversalMarketDataFeed (live MCX quote retrieval, contract resolution, batch queries, OI extraction)
3. Historical Daily Candles (parsing 7-element Upstox candles, chronological reversal, OI preservation)
4. Intraday Multi-Timeframe Resampling (1m -> 5m, 15m, 30m, 1h bucket aggregation)
5. Upstox Client MCX Hardening (interval mapping '1D' -> 'day', strict Yahoo fallback elimination for MCX)
6. MarketDataService Zero-Mock Enforcement (strict routing, no DevMockProvider fallback for commodities)
"""

import os
import sys
import time
import math
import datetime
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.market_data.universal_feed import (
    UniversalQuote,
    UniversalMarketDataFeed,
    UniversalFeedService,
    universal_feed,
    MarketDataUnavailableError,
)
from backend.app.market_data.candle_aggregator import (
    CandleAggregator,
    MarketCandleAggregator,
    parse_upstox_candle,
    resample_1m_candles,
    parse_iso_or_epoch_to_sec,
    SUPPORTED_RESAMPLE_INTERVALS,
)
from backend.app.market_data.mcx.models import (
    ContractTerm,
    MCXContract,
    CommodityResolution,
)
from backend.app.market_data.mcx.contract_resolver import (
    ActiveContractResolver,
    active_contract_resolver,
)
from backend.app.broker_providers.upstox_client import (
    UpstoxRESTClient,
    is_mcx_instrument,
)
from backend.app.market_data.service import MarketDataService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_gold_contract() -> MCXContract:
    return MCXContract(
        instrument_key="MCX_FO|495213",
        exchange_token="495213",
        trading_symbol="GOLD FUT 04 DEC 26",
        commodity_symbol="GOLD",
        term=ContractTerm.NEAR_MONTH,
        expiry_timestamp=1796322600000,
        expiry_date="2026-12-04",
        last_trading_date="2026-12-04 23:30:00",
        days_to_expiry=16,
        is_in_rollover_window=False,
        lot_size=1,
        qty_multiplier=1.0,
        price_quote_unit="GRMS",
        tick_size=100.0,
        tick_size_rupees=1.0,
    )


@pytest.fixture
def sample_crude_contract() -> MCXContract:
    return MCXContract(
        instrument_key="MCX_FO|573422",
        exchange_token="573422",
        trading_symbol="CRUDEOIL FUT 19 NOV 26",
        commodity_symbol="CRUDEOIL",
        term=ContractTerm.NEAR_MONTH,
        expiry_timestamp=1795026600000,
        expiry_date="2026-11-19",
        last_trading_date="2026-11-19 23:30:00",
        days_to_expiry=1,
        is_in_rollover_window=True,
        lot_size=100,
        qty_multiplier=1.0,
        price_quote_unit="BBL",
        tick_size=100.0,
        tick_size_rupees=1.0,
    )


@pytest.fixture
def sample_upstox_gold_quote_payload() -> Dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "MCX_FO:495213": {
                "ohlc": {
                    "open": 135050.0,
                    "high": 135341.0,
                    "low": 133469.0,
                    "close": 134423.0,
                },
                "depth": {
                    "buy": [{"quantity": 10, "price": 134420.0, "orders": 2}],
                    "sell": [{"quantity": 15, "price": 134425.0, "orders": 3}],
                },
                "timestamp": "2026-11-18T19:30:00+05:30",
                "instrument_token": "MCX_FO|495213",
                "symbol": "GOLD FUT 04 DEC 26",
                "last_price": 134423.0,
                "volume": 14819,
                "average_price": 134380.0,
                "oi": 14819,
                "net_change": 250.0,
                "total_buy_quantity": 450,
                "total_sell_quantity": 520,
                "lower_circuit_limit": 126000.0,
                "upper_circuit_limit": 142000.0,
                "last_trade_time": 1795000000000,
            }
        }
    }


# ============================================================================
# 1. UniversalQuote Data Model Tests
# ============================================================================

class TestUniversalQuoteModel:
    def test_valid_instantiation_and_field_integrity(self):
        q = UniversalQuote(
            symbol="GOLD",
            instrument_id="GOLD_MCX",
            instrument_key="MCX_FO|495213",
            trading_symbol="GOLD FUT 04 DEC 26",
            exchange="MCX",
            currency="INR",
            unit="₹/10g",
            ltp=134423.00,
            open=135050.00,
            high=135341.00,
            low=133469.00,
            close=134423.00,
            volume=14819,
            open_interest=14819,
            bid_price=134420.00,
            ask_price=134425.00,
            last_trade_time=1795000000000,
            market_status="LIVE",
            source="UPSTOX",
            price_domain="RAW_EXCHANGE_PRICE",
            raw_data={"test": "payload"},
        )
        assert q.symbol == "GOLD"
        assert q.instrument_id == "GOLD_MCX"
        assert q.instrument_key == "MCX_FO|495213"
        assert q.trading_symbol == "GOLD FUT 04 DEC 26"
        assert q.exchange == "MCX"
        assert q.currency == "INR"
        assert q.unit == "₹/10g"
        assert q.ltp == 134423.00
        assert q.open == 135050.00
        assert q.high == 135341.00
        assert q.low == 133469.00
        assert q.close == 134423.00
        assert q.volume == 14819
        assert q.open_interest == 14819
        assert q.bid_price == 134420.00
        assert q.ask_price == 134425.00
        assert q.last_trade_time == 1795000000000
        assert q.market_status == "LIVE"
        assert q.source == "UPSTOX"
        assert q.price_domain == "RAW_EXCHANGE_PRICE"
        assert q.raw_data == {"test": "payload"}
        assert q.raw_response == {"test": "payload"}

    def test_raw_data_and_raw_response_synchronization(self):
        # Supplying raw_response syncs to raw_data
        q1 = UniversalQuote(
            symbol="SILVER",
            instrument_id="SILVER_MCX",
            instrument_key="MCX_FO|495214",
            trading_symbol="SILVER FUT 04 DEC 26",
            unit="₹/kg",
            ltp=170111.0,
            open=170000.0,
            high=171000.0,
            low=169000.0,
            close=170111.0,
            last_trade_time=1795000000000,
            raw_response={"raw": "res"},
        )
        assert q1.raw_data == {"raw": "res"}
        assert q1.raw_response == {"raw": "res"}

        # Supplying raw_data syncs to raw_response
        q2 = UniversalQuote(
            symbol="CRUDEOIL",
            instrument_id="CRUDEOIL_MCX",
            instrument_key="MCX_FO|573422",
            trading_symbol="CRUDEOIL FUT 19 NOV 26",
            unit="₹/bbl",
            ltp=8058.0,
            open=8000.0,
            high=8100.0,
            low=7950.0,
            close=8058.0,
            last_trade_time=1795000000000,
            raw_data={"raw": "data"},
        )
        assert q2.raw_data == {"raw": "data"}
        assert q2.raw_response == {"raw": "data"}

    def test_missing_mandatory_fields_raises_validation_error(self):
        with pytest.raises(ValidationError):
            # Missing ltp
            UniversalQuote(
                symbol="GOLD",
                instrument_id="GOLD_MCX",
                instrument_key="MCX_FO|495213",
                trading_symbol="GOLD FUT 04 DEC 26",
                unit="₹/10g",
                open=135050.0,
                high=135341.0,
                low=133469.0,
                close=134423.0,
                last_trade_time=1795000000000,
            )

        with pytest.raises(ValidationError):
            # Missing symbol
            UniversalQuote(
                instrument_id="GOLD_MCX",
                instrument_key="MCX_FO|495213",
                trading_symbol="GOLD FUT 04 DEC 26",
                unit="₹/10g",
                ltp=134423.0,
                open=135050.0,
                high=135341.0,
                low=133469.0,
                close=134423.0,
                last_trade_time=1795000000000,
            )

    def test_finite_price_validation_rejects_nan_and_inf(self):
        with pytest.raises(ValueError, match="finite numbers"):
            UniversalQuote(
                symbol="GOLD",
                instrument_id="GOLD_MCX",
                instrument_key="MCX_FO|495213",
                trading_symbol="GOLD FUT 04 DEC 26",
                unit="₹/10g",
                ltp=float("nan"),
                open=135050.0,
                high=135341.0,
                low=133469.0,
                close=134423.0,
                last_trade_time=1795000000000,
            )

        with pytest.raises(ValueError, match="finite numbers"):
            UniversalQuote(
                symbol="GOLD",
                instrument_id="GOLD_MCX",
                instrument_key="MCX_FO|495213",
                trading_symbol="GOLD FUT 04 DEC 26",
                unit="₹/10g",
                ltp=float("inf"),
                open=135050.0,
                high=135341.0,
                low=133469.0,
                close=134423.0,
                last_trade_time=1795000000000,
            )


# ============================================================================
# 2. UniversalMarketDataFeed Live Quote Retrieval Tests
# ============================================================================

class TestUniversalMarketDataFeed:
    @pytest.mark.asyncio
    async def test_live_quote_retrieval_success(
        self,
        sample_gold_contract,
        sample_upstox_gold_quote_payload,
    ):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = sample_gold_contract
        mock_resolver.get_commodity_config.return_value = {
            "unit": "₹/10g",
            "instrument_id": "GOLD_MCX",
        }

        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = sample_upstox_gold_quote_payload

        feed = UniversalMarketDataFeed(
            token="test_token",
            client=mock_client,
            resolver=mock_resolver,
        )

        quote = await feed.get_live_quote("GOLD")

        assert isinstance(quote, UniversalQuote)
        assert quote.symbol == "GOLD"
        assert quote.instrument_id == "GOLD_MCX"
        assert quote.instrument_key == "MCX_FO|495213"
        assert quote.trading_symbol == "GOLD FUT 04 DEC 26"
        assert quote.ltp == 134423.0
        assert quote.open == 135050.0
        assert quote.high == 135341.0
        assert quote.low == 133469.0
        assert quote.close == 134423.0
        assert quote.volume == 14819
        assert quote.open_interest == 14819
        assert quote.bid_price == 134420.0
        assert quote.ask_price == 134425.0
        assert quote.unit == "₹/10g"
        assert quote.source == "UPSTOX"
        assert quote.price_domain == "RAW_EXCHANGE_PRICE"
        assert quote.raw_data is not None

        mock_resolver.get_active_contract.assert_called_once_with("GOLD", term=ContractTerm.NEAR_MONTH)
        mock_client._request.assert_called_once_with("GET", "/v2/market-quote/quotes?instrument_key=MCX_FO|495213")

    @pytest.mark.asyncio
    async def test_live_quote_pipe_and_colon_key_matching(
        self,
        sample_gold_contract,
    ):
        # When Upstox returns keys formatted with pipe instead of colon
        payload_with_pipe = {
            "status": "success",
            "data": {
                "MCX_FO|495213": {
                    "last_price": 134423.0,
                    "ohlc": {"open": 135000.0, "high": 135500.0, "low": 133000.0, "close": 134423.0},
                    "volume": 12000,
                    "oi": 15000,
                    "last_trade_time": 1795000000000,
                }
            }
        }
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = sample_gold_contract
        mock_resolver.get_commodity_config.return_value = {"unit": "₹/10g", "instrument_id": "GOLD_MCX"}

        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = payload_with_pipe

        feed = UniversalMarketDataFeed(
            token="test_token",
            client=mock_client,
            resolver=mock_resolver,
        )

        quote = await feed.get_live_quote("GOLD_MCX")
        assert quote.ltp == 134423.0
        assert quote.volume == 12000
        assert quote.open_interest == 15000

    @pytest.mark.asyncio
    async def test_live_quotes_batch_retrieval(
        self,
        sample_gold_contract,
        sample_crude_contract,
    ):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.side_effect = lambda sym, term: (
            sample_gold_contract if "GOLD" in sym else sample_crude_contract
        )
        mock_resolver.get_commodity_config.side_effect = lambda sym: {
            "GOLD": {"unit": "₹/10g", "instrument_id": "GOLD_MCX"},
            "CRUDEOIL": {"unit": "₹/bbl", "instrument_id": "CRUDEOIL_MCX"},
        }.get(sym, {})

        batch_payload = {
            "status": "success",
            "data": {
                "MCX_FO:495213": {
                    "last_price": 134423.0,
                    "ohlc": {"open": 135000.0, "high": 135500.0, "low": 133000.0, "close": 134423.0},
                    "volume": 14000,
                    "oi": 14819,
                    "last_trade_time": 1795000000000,
                },
                "MCX_FO:573422": {
                    "last_price": 8058.0,
                    "ohlc": {"open": 8000.0, "high": 8100.0, "low": 7950.0, "close": 8058.0},
                    "volume": 8500,
                    "oi": 9200,
                    "last_trade_time": 1795000000000,
                },
            }
        }

        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = batch_payload

        feed = UniversalMarketDataFeed(
            token="test_token",
            client=mock_client,
            resolver=mock_resolver,
        )

        quotes = await feed.get_live_quotes(["GOLD", "CRUDEOIL"])
        assert len(quotes) == 2
        assert quotes[0].symbol == "GOLD"
        assert quotes[0].ltp == 134423.0
        assert quotes[1].symbol == "CRUDEOIL"
        assert quotes[1].ltp == 8058.0

    @pytest.mark.asyncio
    async def test_live_quote_unresolvable_commodity_raises_error(self):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = None

        feed = UniversalMarketDataFeed(
            token="test_token",
            resolver=mock_resolver,
        )

        with pytest.raises(MarketDataUnavailableError, match="Could not resolve active"):
            await feed.get_live_quote("UNKNOWN_COIN")

    @pytest.mark.asyncio
    async def test_live_quote_missing_token_fails_closed(self):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = MagicMock()

        feed = UniversalMarketDataFeed(token="", resolver=mock_resolver)
        with pytest.raises(MarketDataUnavailableError, match="UPSTOX_ANALYTICS_TOKEN is not configured"):
            await feed.get_live_quote("GOLD")

    @pytest.mark.asyncio
    async def test_live_quote_non_positive_or_missing_ltp_raises_error(self, sample_gold_contract):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = sample_gold_contract

        invalid_payload = {
            "status": "success",
            "data": {
                "MCX_FO:495213": {
                    "last_price": 0.0,  # Invalid zero price
                    "ohlc": {"open": 0, "high": 0, "low": 0, "close": 0},
                }
            }
        }
        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = invalid_payload

        feed = UniversalMarketDataFeed(
            token="test_token",
            client=mock_client,
            resolver=mock_resolver,
        )

        with pytest.raises(MarketDataUnavailableError, match="invalid LTP"):
            await feed.get_live_quote("GOLD")


# ============================================================================
# 3. Historical Daily Candles & Ordering Tests
# ============================================================================

class TestCandleAggregatorDaily:
    def test_parse_upstox_candle_7_elements(self):
        raw = ["2026-11-18T00:00:00+05:30", 135000.0, 135500.0, 133200.0, 134423.0, 14819, 15200]
        parsed = parse_upstox_candle(raw)

        assert parsed["timestamp"] == "2026-11-18T00:00:00+05:30"
        assert parsed["open"] == 135000.0
        assert parsed["high"] == 135500.0
        assert parsed["low"] == 133200.0
        assert parsed["close"] == 134423.0
        assert parsed["volume"] == 14819
        assert parsed["open_interest"] == 15200

    def test_parse_upstox_candle_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid Upstox raw candle format"):
            parse_upstox_candle(["2026-11-18", 100.0])  # Less than 5 elements

    @pytest.mark.asyncio
    async def test_fetch_daily_candles_reverses_descending_order(self):
        # Upstox returns newest first: Nov 18, Nov 17, Nov 16
        raw_descending = [
            ["2026-11-18T00:00:00+05:30", 135000.0, 135500.0, 133200.0, 134423.0, 14819, 15200],
            ["2026-11-17T00:00:00+05:30", 134500.0, 135200.0, 134000.0, 135000.0, 12000, 14900],
            ["2026-11-16T00:00:00+05:30", 134000.0, 134800.0, 133500.0, 134500.0, 11000, 14500],
        ]

        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = {"status": "success", "data": {"candles": raw_descending}}

        aggregator = CandleAggregator(client=mock_client)
        candles = await aggregator.fetch_daily_candles(
            instrument_key="MCX_FO|495213",
            to_date="2026-11-18",
            from_date="2026-11-16",
        )

        assert len(candles) == 3
        # Must be reversed to chronological ascending order: Nov 16, Nov 17, Nov 18
        assert candles[0]["timestamp"] == "2026-11-16T00:00:00+05:30"
        assert candles[1]["timestamp"] == "2026-11-17T00:00:00+05:30"
        assert candles[2]["timestamp"] == "2026-11-18T00:00:00+05:30"

        # Check OHLC integrity and OI preservation
        for c in candles:
            assert c["high"] >= c["low"]
            assert c["high"] >= c["open"]
            assert c["high"] >= c["close"]
            assert c["low"] <= c["open"]
            assert c["low"] <= c["close"]
            assert c["volume"] > 0
            assert c["open_interest"] > 0

    @pytest.mark.asyncio
    async def test_feed_historical_daily_candles_success(self, sample_gold_contract):
        mock_resolver = MagicMock()
        mock_resolver.get_active_contract.return_value = sample_gold_contract

        raw_descending = [
            ["2026-11-18T00:00:00+05:30", 135000.0, 135500.0, 133200.0, 134423.0, 14819, 15200],
            ["2026-11-17T00:00:00+05:30", 134500.0, 135200.0, 134000.0, 135000.0, 12000, 14900],
        ]
        mock_client = AsyncMock(spec=UpstoxRESTClient)
        mock_client._request.return_value = {"status": "success", "data": {"candles": raw_descending}}

        feed = UniversalMarketDataFeed(
            token="test_token",
            client=mock_client,
            resolver=mock_resolver,
        )

        candles = await feed.get_historical_daily_candles("GOLD", lookback_days=2)
        assert len(candles) == 2
        assert candles[0]["timestamp"] == "2026-11-17T00:00:00+05:30"
        assert candles[1]["timestamp"] == "2026-11-18T00:00:00+05:30"


# ============================================================================
# 4. Intraday Multi-Timeframe Resampling Tests
# ============================================================================

class TestIntradayResampling:
    def test_resample_1m_to_5m_buckets(self):
        # 15 minutes of 1m candles starting at 09:15:00
        base_sec = 1763437500  # aligned to 5m boundary
        candles_1m = []
        for i in range(15):
            o = 134000.0 + (i * 10.0)
            h = o + 25.0
            l = o - 15.0
            c = o + 5.0
            v = 100 + i
            oi = 14000 + i
            candles_1m.append({
                "timestamp": base_sec + (i * 60),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "open_interest": oi,
            })

        resampled = resample_1m_candles(candles_1m, target_interval="5m")

        assert len(resampled) == 3

        # Bucket 0: minute 0 to 4
        b0 = resampled[0]
        assert b0["open"] == candles_1m[0]["open"]
        assert b0["high"] == max(c["high"] for c in candles_1m[0:5])
        assert b0["low"] == min(c["low"] for c in candles_1m[0:5])
        assert b0["close"] == candles_1m[4]["close"]
        assert b0["volume"] == sum(c["volume"] for c in candles_1m[0:5])
        assert b0["open_interest"] == candles_1m[4]["open_interest"]

        # Bucket 1: minute 5 to 9
        b1 = resampled[1]
        assert b1["open"] == candles_1m[5]["open"]
        assert b1["close"] == candles_1m[9]["close"]
        assert b1["volume"] == sum(c["volume"] for c in candles_1m[5:10])
        assert b1["open_interest"] == candles_1m[9]["open_interest"]

        # Bucket 2: minute 10 to 14
        b2 = resampled[2]
        assert b2["open"] == candles_1m[10]["open"]
        assert b2["close"] == candles_1m[14]["close"]
        assert b2["volume"] == sum(c["volume"] for c in candles_1m[10:15])
        assert b2["open_interest"] == candles_1m[14]["open_interest"]

    def test_resample_1m_to_15m_buckets(self):
        base_sec = 1763437500
        candles_1m = []
        for i in range(30):
            candles_1m.append({
                "timestamp": base_sec + (i * 60),
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 95.0 + i,
                "close": 102.0 + i,
                "volume": 50,
                "open_interest": 1000 + i,
            })

        resampled = resample_1m_candles(candles_1m, target_interval="15m")
        assert len(resampled) == 2
        assert resampled[0]["open"] == 100.0
        assert resampled[0]["close"] == candles_1m[14]["close"]
        assert resampled[0]["volume"] == 50 * 15
        assert resampled[0]["open_interest"] == candles_1m[14]["open_interest"]
        assert resampled[1]["open"] == candles_1m[15]["open"]
        assert resampled[1]["close"] == candles_1m[29]["close"]

    def test_resample_1m_to_1h_buckets(self):
        base_sec = 1763434800  # aligned to 1h (1763434800 % 3600 == 0)
        candles_1m = []
        for i in range(60):
            candles_1m.append({
                "timestamp": base_sec + (i * 60),
                "open": 500.0 + i,
                "high": 510.0 + i,
                "low": 490.0 + i,
                "close": 505.0 + i,
                "volume": 20,
                "open_interest": 5000 + i,
            })

        resampled = resample_1m_candles(candles_1m, target_interval="1h")
        assert len(resampled) == 1
        assert resampled[0]["open"] == 500.0
        assert resampled[0]["close"] == candles_1m[59]["close"]
        assert resampled[0]["volume"] == 20 * 60
        assert resampled[0]["open_interest"] == candles_1m[59]["open_interest"]

    def test_resample_1m_identity(self):
        candles_1m = [{"timestamp": 1000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 10}]
        assert resample_1m_candles(candles_1m, "1m") == candles_1m
        assert resample_1m_candles(candles_1m, "1minute") == candles_1m

    def test_resample_single_candle_boundary(self):
        single = [{"timestamp": 1763437500, "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 50, "open_interest": 1000}]
        resampled = resample_1m_candles(single, "5m")
        assert len(resampled) == 1
        assert resampled[0]["open"] == 100.0
        assert resampled[0]["high"] == 105.0
        assert resampled[0]["low"] == 95.0
        assert resampled[0]["close"] == 102.0
        assert resampled[0]["volume"] == 50
        assert resampled[0]["open_interest"] == 1000

    def test_resample_empty_candles_returns_empty(self):
        assert resample_1m_candles([], "5m") == []

    def test_resample_unsupported_interval_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported resampling interval"):
            resample_1m_candles([{"timestamp": 1000, "open": 1}], target_interval="7m")


# ============================================================================
# 5. Upstox Client MCX Hardening Tests
# ============================================================================

class TestUpstoxClientMCXHardening:
    def test_is_mcx_instrument_detection(self):
        assert is_mcx_instrument("GOLD") is True
        assert is_mcx_instrument("GOLD_MCX") is True
        assert is_mcx_instrument("GOLDM") is True
        assert is_mcx_instrument("SILVER") is True
        assert is_mcx_instrument("SILVER_MCX") is True
        assert is_mcx_instrument("CRUDEOIL") is True
        assert is_mcx_instrument("NATURALGAS") is True
        assert is_mcx_instrument("COPPER") is True
        assert is_mcx_instrument("ALUMINIUM") is True
        assert is_mcx_instrument("ZINC") is True
        assert is_mcx_instrument("LEAD") is True
        assert is_mcx_instrument("NICKEL") is True
        assert is_mcx_instrument("MCX_FO|495213") is True

        # Non-MCX equities
        assert is_mcx_instrument("RELIANCE") is False
        assert is_mcx_instrument("TCS") is False
        assert is_mcx_instrument("INFY") is False
        assert is_mcx_instrument("NIFTY 50") is False

    @pytest.mark.asyncio
    async def test_get_full_quote_mcx_failure_blocks_yahoo_fallback(self):
        client = UpstoxRESTClient(token="mock_token")
        # Mock _request to fail for MCX
        client._request = AsyncMock(side_effect=RuntimeError("Exchange unreachable"))
        client._fetch_yahoo_batch_quotes = AsyncMock(return_value=[{"ltp": 99999.0}])

        with pytest.raises(ValueError, match="Yahoo fallback strictly prohibited"):
            await client.get_full_quote("GOLD")

        # Confirm Yahoo fallback was NEVER called
        client._fetch_yahoo_batch_quotes.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_multi_quotes_mcx_missing_blocks_yahoo_fallback(self):
        client = UpstoxRESTClient(token="mock_token")
        client._request = AsyncMock(return_value={"status": "success", "data": {}})
        client._fetch_yahoo_batch_quotes = AsyncMock(return_value=[])

        # Mix of an equity and an MCX commodity
        quotes = await client.get_multi_quotes(["TCS", "GOLD"])

        # TCS can be passed to Yahoo, but GOLD must be excluded
        if client._fetch_yahoo_batch_quotes.called:
            called_symbols = client._fetch_yahoo_batch_quotes.call_args[0][0]
            assert "GOLD" not in called_symbols
            assert "GOLD_MCX" not in called_symbols

    @pytest.mark.asyncio
    async def test_historical_candles_1D_mapping_and_oi_preservation(self):
        client = UpstoxRESTClient(token="mock_token")
        raw_candles = [
            ["2026-11-18T00:00:00+05:30", 135000.0, 135500.0, 133200.0, 134423.0, 14819, 15200],
            ["2026-11-17T00:00:00+05:30", 134500.0, 135200.0, 134000.0, 135000.0, 12000, 14900],
        ]
        client._request = AsyncMock(return_value={"status": "success", "data": {"candles": raw_candles}})

        with patch("backend.app.broker_providers.upstox_client.get_instrument_key", return_value="MCX_FO|495213"):
            candles = await client.get_historical_candles(
                symbol="GOLD",
                interval="1D",
                to_date="2026-11-18",
                from_date="2026-11-17",
            )

            # Check mapping to 'day' in endpoint
            client._request.assert_called_once()
            endpoint = client._request.call_args[0][1]
            assert "/day/" in endpoint

            # Check reversal to chronological ascending
            assert len(candles) == 2
            assert candles[0]["open_interest"] == 14900
            assert candles[1]["open_interest"] == 15200

    @pytest.mark.asyncio
    async def test_historical_candles_mcx_prohibits_yahoo_fallback(self):
        client = UpstoxRESTClient(token="mock_token")
        client._request = AsyncMock(side_effect=Exception("Failed query"))

        with patch("backend.app.broker_providers.upstox_client.get_instrument_key", return_value="MCX_FO|495213"):
            candles = await client.get_historical_candles("GOLD", interval="5m")
            # Must return empty list rather than falling back to Yahoo Finance
            assert candles == []


# ============================================================================
# 6. MarketDataService Zero-Mock Enforcement Tests
# ============================================================================

class TestMarketDataServiceZeroMockEnforcement:
    @pytest.mark.asyncio
    async def test_service_routes_commodity_to_universal_feed(self, sample_gold_contract):
        service = MarketDataService()
        mock_quote = UniversalQuote(
            symbol="GOLD",
            instrument_id="GOLD_MCX",
            instrument_key="MCX_FO|495213",
            trading_symbol="GOLD FUT 04 DEC 26",
            unit="₹/10g",
            ltp=134423.0,
            open=135050.0,
            high=135341.0,
            low=133469.0,
            close=134423.0,
            volume=14819,
            open_interest=14819,
            last_trade_time=1795000000000,
            market_status="LIVE",
            source="UPSTOX",
            price_domain="RAW_EXCHANGE_PRICE",
        )
        service.universal_feed.get_live_quote = AsyncMock(return_value=mock_quote)

        quote = await service.get_quote("GOLD")
        assert quote["symbol"] == "GOLD"
        assert quote["ltp"] == 134423.0
        assert quote["source"] == "UPSTOX"
        assert quote["price_domain"] == "RAW_EXCHANGE_PRICE"
        service.universal_feed.get_live_quote.assert_called_once_with("GOLD")

    @pytest.mark.asyncio
    async def test_service_zero_mock_fallback_for_commodities_even_when_allowed(self):
        service = MarketDataService()
        service.allow_mock_fallback = True  # Mock fallback explicitly enabled in config
        service.universal_feed.get_live_quote = AsyncMock(
            side_effect=MarketDataUnavailableError("Exchange connection offline")
        )

        with pytest.raises(MarketDataUnavailableError, match="Mock fallback strictly prohibited"):
            await service.get_quote("GOLD")

        # Under NO circumstances should mock provider prices be returned
        with pytest.raises(MarketDataUnavailableError):
            await service.get_quote("CRUDEOIL")

    @pytest.mark.asyncio
    async def test_service_batch_quotes_commodity_zero_mock(self):
        service = MarketDataService()
        service.allow_mock_fallback = True
        service.universal_feed.get_live_quotes = AsyncMock(
            side_effect=MarketDataUnavailableError("Batch quotes unavailable")
        )

        with pytest.raises(MarketDataUnavailableError, match="Mock fallback strictly prohibited"):
            await service.get_quotes(["GOLD", "SILVER"])

    @pytest.mark.asyncio
    async def test_service_commodity_candles_routing(self):
        service = MarketDataService()
        sample_candles = [
            {"timestamp": 1000, "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 50, "open_interest": 500}
        ]
        service.universal_feed.get_historical_daily_candles = AsyncMock(return_value=sample_candles)
        service.universal_feed.get_intraday_candles = AsyncMock(return_value=sample_candles)

        # Daily
        daily = await service.get_candles("GOLD", interval="1d", count=30)
        assert daily == sample_candles
        service.universal_feed.get_historical_daily_candles.assert_called_once_with("GOLD", lookback_days=30)

        # Intraday
        intraday = await service.get_candles("GOLD", interval="5m", count=30)
        assert intraday == sample_candles
        service.universal_feed.get_intraday_candles.assert_called_once_with("GOLD", interval="5m")
