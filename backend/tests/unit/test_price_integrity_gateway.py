"""
APEX Price Integrity Gateway & MCX Session Engine — Unit Test Suite
===================================================================
Comprehensive unit testing covering:
1. MCX Session Engine:
   - Morning session (09:00 - 17:00 IST)
   - Afternoon / evening session (17:00 - 23:30/23:55 IST)
   - US Daylight Saving Time (DST) 23:30 vs Winter Standard Time 23:55 session close
   - Off-hours / night closure (e.g. 02:00, 08:30 IST)
   - Weekend closure (Saturday, Sunday)
   - Statutory exchange holiday closure
   - Timezone resilience (IST, UTC, naive)
   - Canonical quote store integration (evening trading not blocked by NSE 15:30)
2. Price Integrity Gateway (9-point validation pipeline):
   - Check 1: Non-positive price rejection (ltp <= 0, nan, inf)
   - Check 2: Zero-mock enforcement (78450.0, synthetic prices)
   - Check 3: Timestamp provenance (future timestamps >60s, authentic exchange tags)
   - Check 4: Token & contract match (MCX_FO| format, symbol match, active contract)
   - Check 5: MCX trading session awareness (open vs closed, allow_closed mode)
   - Check 6: Staleness check (configurable threshold, liquid 120s vs illiquid 900s)
   - Check 7: Bid/Ask crossed book sanity check (bid > ask)
   - Check 8: Bid-Ask spread limits (asset-specific 2% vs 5%, custom override)
   - Check 9: Circuit band deviation (>15% deviation, statutory commodity bounds)
   - Combination & edge case validations
"""

import os
import sys
import time
import math
import datetime
from unittest.mock import MagicMock
import pytest

# Ensure repository root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.market_data.mcx_session_engine import (
    MCXSessionEngine,
    mcx_session_engine,
    is_mcx_trading_session_open,
    get_mcx_session_info,
    IST,
    MCX_HOLIDAYS_2026,
)
from backend.app.market_data.price_integrity_gateway import (
    PriceIntegrityGateway,
    price_integrity_gateway,
    validate_price_integrity,
    ValidationVerdict,
    PriceIntegrityResult,
    KNOWN_SYNTHETIC_PRICES,
    COMMODITY_PRICE_BOUNDS,
    DEFAULT_STALENESS_SECONDS,
    DEFAULT_MAX_SPREAD_PCT,
)
from backend.app.market_data.universal_feed import UniversalQuote
from backend.app.market_data.canonical_store import (
    CanonicalQuote,
    is_market_session_open,
    _nse_cash_market_open,
)
from backend.app.market_data.mcx.models import MCXContract, ContractTerm


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def valid_gold_quote() -> UniversalQuote:
    """Authentic live Gold quote model for testing."""
    now = time.time()
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
        close=134000.0,
        volume=1250,
        open_interest=14819,
        bid_price=134420.0,
        ask_price=134425.0,
        last_trade_time=int((now - 15) * 1000),  # 15s ago
        market_status="LIVE",
        source="UPSTOX",
        price_domain="RAW_EXCHANGE_PRICE",
        retrieved_at=now,
    )


@pytest.fixture
def valid_crude_quote() -> UniversalQuote:
    """Authentic live Crude Oil quote model for testing."""
    now = time.time()
    return UniversalQuote(
        symbol="CRUDEOIL",
        instrument_id="CRUDEOIL_MCX",
        instrument_key="MCX_FO|573422",
        trading_symbol="CRUDEOIL FUT 19 NOV 26",
        contract_expiry="2026-11-19",
        exchange="MCX",
        currency="INR",
        unit="₹/bbl",
        ltp=8058.0,
        open=8000.0,
        high=8120.0,
        low=7980.0,
        close=8010.0,
        volume=8500,
        open_interest=9200,
        bid_price=8057.0,
        ask_price=8059.0,
        last_trade_time=int((now - 10) * 1000),
        market_status="LIVE",
        source="UPSTOX",
        price_domain="RAW_EXCHANGE_PRICE",
        retrieved_at=now,
    )


# ==============================================================================
# SECTION 1: MCX SESSION ENGINE TESTS
# ==============================================================================

class TestMCXSessionEngine:
    """Unit tests for MCXSessionEngine schedule, daylight savings, and holiday rules."""

    def test_morning_session_active(self):
        """Mon-Fri morning at 10:30 IST is active MCX trading hours."""
        # Wednesday 2026-11-18 10:30 IST
        dt = datetime.datetime(2026, 11, 18, 10, 30, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt) is True
        info = get_mcx_session_info(dt)
        assert info["is_open"] is True
        assert info["session_status"] == "MCX LIVE"
        assert info["market_status"] == "LIVE"
        assert info["is_weekend"] is False
        assert info["is_holiday"] is False

    def test_afternoon_session_active(self):
        """Mon-Fri afternoon at 14:30 IST is active MCX trading hours."""
        dt = datetime.datetime(2026, 11, 18, 14, 30, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt) is True

    def test_evening_session_active(self):
        """Mon-Fri evening at 20:00 IST is active MCX trading hours (past NSE 15:30 close)."""
        dt = datetime.datetime(2026, 11, 18, 20, 0, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt) is True
        assert mcx_session_engine.is_mcx_trading_session(dt) is True
        assert mcx_session_engine.get_session_status_label(dt) == "MCX LIVE"

    def test_late_evening_session_before_close(self):
        """Mon-Fri at 23:25 IST is active before the 23:30/23:55 close."""
        dt = datetime.datetime(2026, 11, 18, 23, 25, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt) is True

    def test_us_daylight_saving_and_winter_close_times(self):
        """
        During US DST (e.g. July), MCX closes at 23:30 IST.
        During US Standard Time (e.g. December), MCX closes at 23:55 IST.
        """
        # 1. July (Summer, US DST) - Wednesday 2026-07-15
        july_dst = datetime.datetime(2026, 7, 15, 12, 0, 0, tzinfo=IST)
        assert mcx_session_engine.is_daylight_saving_us(july_dst) is True
        start_t, close_t = mcx_session_engine.get_session_times(july_dst)
        assert close_t == datetime.time(23, 30, 0)

        # 23:31 in July is CLOSED
        dt_closed_july = datetime.datetime(2026, 7, 15, 23, 31, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt_closed_july) is False

        # 2. December (Winter, US Standard Time) - Wednesday 2026-12-16
        dec_winter = datetime.datetime(2026, 12, 16, 12, 0, 0, tzinfo=IST)
        assert mcx_session_engine.is_daylight_saving_us(dec_winter) is False
        start_t, close_t = mcx_session_engine.get_session_times(dec_winter)
        assert close_t == datetime.time(23, 55, 0)

        # 23:45 in December is OPEN
        dt_open_dec = datetime.datetime(2026, 12, 16, 23, 45, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt_open_dec) is True

        # 23:56 in December is CLOSED
        dt_closed_dec = datetime.datetime(2026, 12, 16, 23, 56, 0, tzinfo=IST)
        assert is_mcx_trading_session_open(dt_closed_dec) is False

    def test_extended_session_explicit_parameter(self):
        """extended_session=True forces 23:55 close; extended_session=False forces 23:30 close."""
        dt = datetime.datetime(2026, 7, 15, 23, 45, 0, tzinfo=IST)
        # In July normally closed at 23:45
        assert is_mcx_trading_session_open(dt, extended_session=False) is False
        # When explicitly extended to 23:55
        assert is_mcx_trading_session_open(dt, extended_session=True) is True

    def test_night_off_hours_closed(self):
        """Early morning hours (01:00, 05:00, 08:59 IST) are CLOSED."""
        dt_1am = datetime.datetime(2026, 11, 18, 1, 0, 0, tzinfo=IST)
        dt_5am = datetime.datetime(2026, 11, 18, 5, 0, 0, tzinfo=IST)
        dt_premarket = datetime.datetime(2026, 11, 18, 8, 59, 59, tzinfo=IST)
        assert is_mcx_trading_session_open(dt_1am) is False
        assert is_mcx_trading_session_open(dt_5am) is False
        assert is_mcx_trading_session_open(dt_premarket) is False
        assert mcx_session_engine.get_session_status_label(dt_1am) == "MCX CLOSED"

    def test_weekend_closed(self):
        """Saturday and Sunday are strictly CLOSED all day."""
        sat_morning = datetime.datetime(2026, 11, 21, 10, 30, 0, tzinfo=IST)
        sat_evening = datetime.datetime(2026, 11, 21, 20, 0, 0, tzinfo=IST)
        sun_morning = datetime.datetime(2026, 11, 22, 10, 30, 0, tzinfo=IST)
        sun_evening = datetime.datetime(2026, 11, 22, 20, 0, 0, tzinfo=IST)

        assert is_mcx_trading_session_open(sat_morning) is False
        assert is_mcx_trading_session_open(sat_evening) is False
        assert is_mcx_trading_session_open(sun_morning) is False
        assert is_mcx_trading_session_open(sun_evening) is False

        info = get_mcx_session_info(sat_morning)
        assert info["is_open"] is False
        assert info["is_weekend"] is True
        assert info["session_status"] == "MCX CLOSED"

    def test_statutory_exchange_holidays_closed(self):
        """Statutory exchange holidays in 2026 are strictly CLOSED."""
        republic_day = datetime.datetime(2026, 1, 26, 11, 0, 0, tzinfo=IST)
        independence_day = datetime.datetime(2026, 8, 15, 11, 0, 0, tzinfo=IST)
        christmas = datetime.datetime(2026, 12, 25, 11, 0, 0, tzinfo=IST)

        assert is_mcx_trading_session_open(republic_day) is False
        assert is_mcx_trading_session_open(independence_day) is False
        assert is_mcx_trading_session_open(christmas) is False

        info = get_mcx_session_info(republic_day)
        assert info["is_open"] is False
        assert info["is_holiday"] is True
        assert info["holiday_name"] == "Republic Day"

    def test_timezone_naive_and_utc_inputs(self):
        """Naive datetime is localized to IST, and UTC datetime is converted properly."""
        # 14:30 UTC = 20:00 IST on Wednesday Nov 18, 2026 (OPEN)
        dt_utc = datetime.datetime(2026, 11, 18, 14, 30, 0, tzinfo=datetime.timezone.utc)
        assert is_mcx_trading_session_open(dt_utc) is True

        # Naive datetime 20:00 is assumed to be 20:00 IST (OPEN)
        dt_naive = datetime.datetime(2026, 11, 18, 20, 0, 0)
        assert is_mcx_trading_session_open(dt_naive) is True


# ==============================================================================
# SECTION 2: CANONICAL STORE INTEGRATION TESTS
# ==============================================================================

class TestCanonicalStoreMCXIntegration:
    """Verifies that CanonicalQuote and is_market_session_open recognize MCX evening sessions."""

    def test_is_market_session_open_for_mcx_vs_nse(self):
        """At 20:00 IST on a Wednesday, MCX is OPEN while NSE cash market is CLOSED."""
        wed_2000_ist = datetime.datetime(2026, 11, 18, 20, 0, 0, tzinfo=IST)

        # NSE equity is closed at 20:00 IST
        assert _nse_cash_market_open(wed_2000_ist) is False
        assert is_market_session_open("NSE", now=wed_2000_ist) is False
        assert is_market_session_open("RELIANCE", now=wed_2000_ist) is False

        # MCX commodity is open at 20:00 IST
        assert is_market_session_open("MCX", now=wed_2000_ist) is True
        assert is_market_session_open("MCX_FO|495213", now=wed_2000_ist) is True
        assert is_market_session_open("GOLD_MCX", now=wed_2000_ist) is True

    def test_canonical_quote_mcx_evening_session_property(self, valid_gold_quote):
        """CanonicalQuote with exchange='MCX' evaluates market_session_open correctly."""
        cq = CanonicalQuote(
            symbol="GOLD",
            instrument_key="MCX_FO|495213",
            exchange="MCX",
            ltp=134423.0,
            previous_close=134000.0,
            open=135050.0,
            high=135341.0,
            low=133469.0,
            volume=1250,
            bid=134420.0,
            ask=134425.0,
            provider="UPSTOX",
            provider_mode="AUTHENTIC_LIVE",
            provider_timestamp=time.time() - 10,
            received_timestamp=time.time(),
        )
        # CanonicalQuote property delegates to is_market_session_open
        # In current live time, this matches mcx_session_engine
        assert cq.market_session_open == mcx_session_engine.is_mcx_trading_session_open()


# ==============================================================================
# SECTION 3: PRICE INTEGRITY GATEWAY — 9 STRICT VALIDATION CHECKS
# ==============================================================================

class TestPriceIntegrityGatewayNineChecks:
    """Rigorous unit verification of all 9 checks implemented in PriceIntegrityGateway."""

    # --------------------------------------------------------------------------
    # Check 1: Non-positive price rejection
    # --------------------------------------------------------------------------
    def test_check1_reject_zero_ltp(self, valid_gold_quote):
        """LTP of 0.0 is strictly rejected with ZERO_OR_NEGATIVE_PRICE."""
        bad_quote = valid_gold_quote.model_copy(update={"ltp": 0.0})
        res = validate_price_integrity(bad_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.ZERO_OR_NEGATIVE_PRICE
        assert "strictly positive" in res.error_message

    def test_check1_reject_negative_ltp(self, valid_gold_quote):
        """Negative LTP (-500.0) is rejected with ZERO_OR_NEGATIVE_PRICE."""
        bad_quote = valid_gold_quote.model_copy(update={"ltp": -500.0})
        res = validate_price_integrity(bad_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.ZERO_OR_NEGATIVE_PRICE

    # --------------------------------------------------------------------------
    # Check 2: Zero-mock enforcement
    # --------------------------------------------------------------------------
    def test_check2_reject_legacy_gold_mock_78450(self, valid_gold_quote):
        """LTP = 78450.0 legacy synthetic price is strictly caught and rejected."""
        mock_quote = valid_gold_quote.model_copy(update={"ltp": 78450.0})
        res = validate_price_integrity(mock_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.SYNTHETIC_MOCK_DETECTED
        assert "78450" in res.error_message

    def test_check2_reject_all_known_synthetic_prices(self, valid_gold_quote):
        """Every known synthetic mock price is rejected under zero-mock policy."""
        for mock_price in KNOWN_SYNTHETIC_PRICES:
            q = valid_gold_quote.model_copy(update={"ltp": mock_price})
            res = validate_price_integrity(q, session_open=True)
            assert res.is_valid is False
            assert res.verdict == ValidationVerdict.SYNTHETIC_MOCK_DETECTED

    # --------------------------------------------------------------------------
    # Check 3: Timestamp provenance & physical reality
    # --------------------------------------------------------------------------
    def test_check3_reject_future_last_trade_time(self, valid_gold_quote):
        """Future-dated last_trade_time (> 60s ahead of local clock) is rejected."""
        now = time.time()
        future_trade_ms = int((now + 120.0) * 1000)
        future_quote = valid_gold_quote.model_copy(update={"last_trade_time": future_trade_ms})
        res = validate_price_integrity(future_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.OUT_OF_BOUNDS
        assert "Future-dated last_trade_time" in res.error_message

    def test_check3_reject_future_retrieved_at(self, valid_gold_quote):
        """Future-dated retrieved_at (> 60s ahead of local clock) is rejected."""
        now = time.time()
        future_quote = valid_gold_quote.model_copy(update={"retrieved_at": now + 120.0})
        res = validate_price_integrity(future_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.OUT_OF_BOUNDS
        assert "Future-dated retrieved_at" in res.error_message

    def test_check3_reject_unauthenticated_source(self, valid_gold_quote):
        """Quotes originating from non-UPSTOX or simulated price domains are rejected."""
        bad_source = valid_gold_quote.model_copy(update={"source": "YAHOO"})
        res = validate_price_integrity(bad_source, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.SOURCE_UNAUTHENTICATED

        bad_domain = valid_gold_quote.model_copy(update={"price_domain": "SIMULATED_FEED"})
        res2 = validate_price_integrity(bad_domain, session_open=True)
        assert res2.is_valid is False
        assert res2.verdict == ValidationVerdict.SOURCE_UNAUTHENTICATED

    # --------------------------------------------------------------------------
    # Check 4: Token & Contract Matching
    # --------------------------------------------------------------------------
    def test_check4_reject_invalid_instrument_key_format(self, valid_gold_quote):
        """Instrument keys missing MCX_FO| exchange prefix are rejected as AMBIGUOUS_TOKEN."""
        bad_key = valid_gold_quote.model_copy(update={"instrument_key": "NSE_FO|12345"})
        res = validate_price_integrity(bad_key, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.AMBIGUOUS_TOKEN

    def test_check4_reject_expected_commodity_symbol_mismatch(self, valid_gold_quote):
        """When checking a Gold contract, passing a Silver quote triggers AMBIGUOUS_TOKEN."""
        res = validate_price_integrity(valid_gold_quote, expected_commodity="SILVER", session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.AMBIGUOUS_TOKEN
        assert "Symbol mismatch" in res.error_message

    def test_check4_active_contract_key_and_symbol_match(self, valid_gold_quote):
        """Validates matching against an active MCXContract model."""
        matching_contract = MCXContract(
            instrument_key="MCX_FO|495213",
            exchange_token="495213",
            trading_symbol="GOLD FUT 04 DEC 26",
            commodity_symbol="GOLD",
            term=ContractTerm.NEAR_MONTH,
            expiry_timestamp=1796342400000,
            expiry_date="2026-12-04",
            last_trading_date="2026-12-04 23:30:00",
            days_to_expiry=16,
            is_in_rollover_window=False,
            lot_size=100,
            qty_multiplier=1.0,
            price_quote_unit="GRMS",
            tick_size=100.0,
            tick_size_rupees=1.0,
        )
        res = validate_price_integrity(
            valid_gold_quote,
            active_contract=matching_contract,
            session_open=True,
        )
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID

        # Mismatched contract key triggers AMBIGUOUS_TOKEN
        mismatched_contract = matching_contract.model_copy(update={"instrument_key": "MCX_FO|999999"})
        res_mismatch = validate_price_integrity(
            valid_gold_quote,
            active_contract=mismatched_contract,
            session_open=True,
        )
        assert res_mismatch.is_valid is False
        assert res_mismatch.verdict == ValidationVerdict.AMBIGUOUS_TOKEN

    # --------------------------------------------------------------------------
    # Check 5: MCX Session Awareness
    # --------------------------------------------------------------------------
    def test_check5_reject_quote_when_session_closed(self, valid_gold_quote):
        """When trading session is closed and allow_closed=False, returns MARKET_CLOSED."""
        res = validate_price_integrity(valid_gold_quote, session_open=False, allow_closed=False)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.MARKET_CLOSED
        assert "closed" in res.error_message.lower()

    def test_check5_allow_closed_mode_marks_quote_status_closed(self, valid_gold_quote):
        """When allow_closed=True, closed session passes validation with market_status='CLOSED'."""
        res = validate_price_integrity(valid_gold_quote, session_open=False, allow_closed=True)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID
        assert res.quote.market_status == "CLOSED"

    # --------------------------------------------------------------------------
    # Check 6: Staleness Check
    # --------------------------------------------------------------------------
    def test_check6_reject_stale_quote_during_live_session(self, valid_gold_quote):
        """A quote older than the staleness threshold (e.g. 120s for Gold) is rejected with STALE."""
        now = time.time()
        stale_ltt_ms = int((now - 300.0) * 1000)  # 300s old
        stale_quote = valid_gold_quote.model_copy(
            update={"last_trade_time": stale_ltt_ms, "retrieved_at": now}
        )
        res = validate_price_integrity(stale_quote, session_open=True, max_staleness_sec=120.0)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.STALE
        assert "exceeds threshold" in res.error_message

    def test_check6_accept_fresh_quote(self, valid_gold_quote):
        """A quote 15s old passes staleness check against 120s threshold."""
        now = time.time()
        fresh_quote = valid_gold_quote.model_copy(
            update={"last_trade_time": int((now - 15) * 1000), "retrieved_at": now}
        )
        res = validate_price_integrity(fresh_quote, session_open=True, max_staleness_sec=120.0)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID

    def test_check6_illiquid_commodity_higher_staleness_threshold(self, valid_gold_quote):
        """Copper / base metals allow up to 900s staleness by default."""
        now = time.time()
        copper_quote = valid_gold_quote.model_copy(
            update={
                "symbol": "COPPER",
                "instrument_id": "COPPER_MCX",
                "ltp": 1279.25,
                "close": 1275.0,
                "open": 1270.0,
                "high": 1285.0,
                "low": 1265.0,
                "bid_price": 1279.0,
                "ask_price": 1279.5,
                "last_trade_time": int((now - 400) * 1000),  # 400s old (stale for Gold, fresh for Copper)
                "retrieved_at": now,
            }
        )
        res = validate_price_integrity(copper_quote, session_open=True)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID

    # --------------------------------------------------------------------------
    # Check 7: Bid / Ask Sanity Check (Crossed Order Book)
    # --------------------------------------------------------------------------
    def test_check7_reject_crossed_order_book(self, valid_gold_quote):
        """Crossed market where bid_price > ask_price is strictly rejected with CROSSED_ORDER_BOOK."""
        crossed_quote = valid_gold_quote.model_copy(
            update={"bid_price": 135000.0, "ask_price": 134000.0}
        )
        res = validate_price_integrity(crossed_quote, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.CROSSED_ORDER_BOOK
        assert "Crossed order book" in res.error_message

    def test_check7_zero_bid_or_ask_does_not_trigger_crossed_book(self, valid_gold_quote):
        """When ask is 0.0 (e.g. upper circuit lock), crossed book check does not falsely trigger."""
        circuit_locked = valid_gold_quote.model_copy(update={"bid_price": 134420.0, "ask_price": 0.0})
        res = validate_price_integrity(circuit_locked, session_open=True)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID

    # --------------------------------------------------------------------------
    # Check 8: Bid-Ask Spread Limits
    # --------------------------------------------------------------------------
    def test_check8_reject_excessive_spread(self, valid_gold_quote):
        """Excessive bid-ask spread exceeding threshold (e.g. 5% or asset limit) returns EXCESSIVE_SPREAD."""
        # LTP = 134423, Bid = 125000, Ask = 140000 -> Spread = 15000 / 134423 = 11.1%
        wide_quote = valid_gold_quote.model_copy(
            update={"bid_price": 125000.0, "ask_price": 140000.0}
        )
        res = validate_price_integrity(wide_quote, session_open=True, max_spread_pct=0.05)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.EXCESSIVE_SPREAD
        assert "exceeds limit" in res.error_message

    def test_check8_accept_tight_spread(self, valid_gold_quote):
        """Tight spread (e.g. ₹5 on ₹1,34,423 = 0.0037%) passes spread check."""
        res = validate_price_integrity(valid_gold_quote, session_open=True, max_spread_pct=0.02)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID

    # --------------------------------------------------------------------------
    # Check 9: Circuit Band Deviation & Statutory Price Bounds
    # --------------------------------------------------------------------------
    def test_check9_reject_circuit_band_deviation_over_15_percent(self, valid_gold_quote):
        """Price deviating > 15% from close without circuit expansion returns OUT_OF_BOUNDS."""
        # Close = 134000, LTP = 160000 (deviation = 19.4%)
        wild_quote = valid_gold_quote.model_copy(
            update={
                "close": 134000.0,
                "ltp": 160000.0,
                "high": 161000.0,
                "low": 133000.0,
            }
        )
        res = validate_price_integrity(wild_quote, session_open=True, circuit_limit_pct=0.15)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.OUT_OF_BOUNDS
        assert "circuit limit" in res.error_message

    def test_check9_reject_statutory_bounds_violation(self, valid_gold_quote):
        """Price outside statutory commodity boundaries returns OUT_OF_BOUNDS."""
        # Gold statutory min is 80,000 INR
        too_low_gold = valid_gold_quote.model_copy(
            update={"ltp": 50000.0, "close": 50000.0, "open": 50000.0, "high": 51000.0, "low": 49000.0}
        )
        res = validate_price_integrity(too_low_gold, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.OUT_OF_BOUNDS
        assert "statutory bounds" in res.error_message

    def test_ohlc_consistency_checks(self, valid_gold_quote):
        """Checks for low > high or LTP falling outside daily low/high."""
        inverted_ohlc = valid_gold_quote.model_copy(update={"low": 140000.0, "high": 130000.0})
        res1 = validate_price_integrity(inverted_ohlc, session_open=True)
        assert res1.is_valid is False
        assert res1.verdict == ValidationVerdict.OHLC_INCONSISTENT

        outside_ohlc = valid_gold_quote.model_copy(
            update={"low": 133000.0, "high": 135000.0, "ltp": 136000.0, "close": 134000.0}
        )
        res2 = validate_price_integrity(outside_ohlc, session_open=True)
        assert res2.is_valid is False
        assert res2.verdict == ValidationVerdict.OHLC_INCONSISTENT


# ==============================================================================
# SECTION 4: COMBINATION & REAL COMMODITY UNIVERSE TESTS
# ==============================================================================

class TestPriceIntegrityGatewayUniverseAndCombinations:
    """Verifies gateway behavior across all target commodities and multi-condition combinations."""

    def test_valid_crudeoil_quote(self, valid_crude_quote):
        """Verifies full validation pipeline on Crude Oil."""
        res = validate_price_integrity(valid_crude_quote, session_open=True, expected_commodity="CRUDEOIL")
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID
        assert res.quote.ltp == 8058.0

    def test_multiple_flaws_priority_order(self, valid_gold_quote):
        """
        When quote has both a non-positive price AND crossed book,
        non-positive price takes deterministic precedence as check 1.
        """
        double_bad = valid_gold_quote.model_copy(
            update={"ltp": -10.0, "bid_price": 135000.0, "ask_price": 134000.0}
        )
        res = validate_price_integrity(double_bad, session_open=True)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.ZERO_OR_NEGATIVE_PRICE

    def test_synthetic_price_takes_precedence_over_session(self, valid_gold_quote):
        """A synthetic mock price (78450.0) is rejected even when session is closed."""
        synthetic_closed = valid_gold_quote.model_copy(update={"ltp": 78450.0})
        res = validate_price_integrity(synthetic_closed, session_open=False)
        assert res.is_valid is False
        assert res.verdict == ValidationVerdict.SYNTHETIC_MOCK_DETECTED

    def test_custom_gateway_instance_configuration(self, valid_gold_quote):
        """Verifies custom instance thresholds work as expected."""
        custom_gw = PriceIntegrityGateway(
            stale_threshold_seconds=60.0,
            default_max_spread_pct=0.01,
            circuit_limit_pct=0.10,
        )
        # Valid quote with 15s age passes 60s threshold
        res = custom_gw.validate_quote(valid_gold_quote, session_open=True)
        assert res.is_valid is True
        assert res.verdict == ValidationVerdict.VALID
