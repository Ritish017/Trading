"""
APEX Price Integrity Gateway
============================
Executes the mandatory 9-point validation pipeline on every inbound commodity quote
before it is admitted into the analytical reasoning engines, technical estimators,
or user interface.

Strict Invariants:
- Zero mock prices allowed. Detected synthetic values trigger immediate rejection.
- Zero silent fallbacks. Unvalidated or corrupt quotes return explicit error states.
- Rejection codes are strictly typed via ValidationVerdict enum.
"""

import time
import math
import logging
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.market_data.universal_feed import UniversalQuote
from backend.app.market_data.mcx_session_engine import mcx_session_engine

logger = logging.getLogger(__name__)

# Known legacy synthetic prices to be rejected unconditionally
KNOWN_SYNTHETIC_PRICES = {
    78450.0,   # Legacy Gold mock
    92300.0,   # Legacy Silver mock
    6120.0,    # Legacy Crude mock
    245.80,    # Legacy NatGas mock
    842.50,    # Legacy Copper mock
    24350.0,   # Static Nifty fallback
    84.42,     # Static USDINR fallback
}

# Statutory Price Range Boundaries for MCX Commodities (in INR)
COMMODITY_PRICE_BOUNDS: Dict[str, Dict[str, float]] = {
    "GOLD": {"min": 80000.0, "max": 250000.0},
    "GOLDM": {"min": 80000.0, "max": 250000.0},
    "SILVER": {"min": 90000.0, "max": 300000.0},
    "SILVERM": {"min": 90000.0, "max": 300000.0},
    "CRUDEOIL": {"min": 3500.0, "max": 20000.0},
    "CRUDEOILM": {"min": 3500.0, "max": 20000.0},
    "NATURALGAS": {"min": 80.0, "max": 1000.0},
    "NATGASMINI": {"min": 80.0, "max": 1000.0},
    "COPPER": {"min": 500.0, "max": 3000.0},
    "ALUMINIUM": {"min": 100.0, "max": 1000.0},
    "ZINC": {"min": 100.0, "max": 1000.0},
    "LEAD": {"min": 80.0, "max": 800.0},
    "NICKEL": {"min": 500.0, "max": 5000.0},
}

# Instrument-specific Staleness Thresholds (seconds)
# 120s for active/liquid commodities, 900s for illiquid commodities/base metals
DEFAULT_STALENESS_SECONDS: Dict[str, float] = {
    "GOLD": 120.0,
    "GOLDM": 120.0,
    "SILVER": 120.0,
    "SILVERM": 120.0,
    "CRUDEOIL": 120.0,
    "CRUDEOILM": 120.0,
    "NATURALGAS": 120.0,
    "NATGASMINI": 120.0,
    "COPPER": 900.0,
    "ALUMINIUM": 900.0,
    "ZINC": 900.0,
    "LEAD": 900.0,
    "NICKEL": 900.0,
}

# Instrument-specific Max Bid-Ask Spread Limits (fraction)
# 2% (0.02) for liquid bullion/crude, 5% (0.05) for nickel/base metals
DEFAULT_MAX_SPREAD_PCT: Dict[str, float] = {
    "GOLD": 0.02,
    "GOLDM": 0.02,
    "SILVER": 0.02,
    "SILVERM": 0.02,
    "CRUDEOIL": 0.02,
    "CRUDEOILM": 0.02,
    "NATURALGAS": 0.02,
    "NATGASMINI": 0.02,
    "COPPER": 0.05,
    "ALUMINIUM": 0.05,
    "ZINC": 0.05,
    "LEAD": 0.05,
    "NICKEL": 0.05,
}


class ValidationVerdict(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    MARKET_CLOSED = "MARKET_CLOSED"
    AMBIGUOUS_TOKEN = "AMBIGUOUS_TOKEN"
    SYNTHETIC_MOCK_DETECTED = "SYNTHETIC_MOCK_DETECTED"
    ZERO_OR_NEGATIVE_PRICE = "ZERO_OR_NEGATIVE_PRICE"
    EXCESSIVE_SPREAD = "EXCESSIVE_SPREAD"
    CROSSED_ORDER_BOOK = "CROSSED_ORDER_BOOK"
    OHLC_INCONSISTENT = "OHLC_INCONSISTENT"
    SOURCE_UNAUTHENTICATED = "SOURCE_UNAUTHENTICATED"


class PriceIntegrityResult(BaseModel):
    is_valid: bool
    verdict: ValidationVerdict
    error_message: Optional[str] = None
    quote: Optional[UniversalQuote] = None
    validation_timestamp: float = Field(default_factory=time.time)


class PriceIntegrityGateway:
    """Production 9-point validation gateway for commodity quotes."""

    def __init__(
        self,
        stale_threshold_seconds: float = 120.0,
        default_max_spread_pct: float = 0.05,
        circuit_limit_pct: float = 0.15,
    ):
        self.stale_threshold_seconds = stale_threshold_seconds
        self.default_max_spread_pct = default_max_spread_pct
        self.circuit_limit_pct = circuit_limit_pct

    def validate_quote(
        self,
        quote: UniversalQuote,
        session_open: Optional[bool] = None,
        max_staleness_sec: Optional[float] = None,
        max_spread_pct: Optional[float] = None,
        circuit_limit_pct: Optional[float] = None,
        expected_commodity: Optional[str] = None,
        active_contract: Optional[Any] = None,
        allow_closed: bool = False,
    ) -> PriceIntegrityResult:
        """
        Executes all 9 mandatory validation checks in order:
        1. Non-positive price rejection (ltp <= 0) -> ZERO_OR_NEGATIVE_PRICE
        2. Zero-mock enforcement (synthetic prices/multipliers) -> SYNTHETIC_MOCK_DETECTED
        3. Timestamp provenance & reality check (no future ts > 60s) -> OUT_OF_BOUNDS / SOURCE_UNAUTHENTICATED
        4. Token / contract match (MCX_FO| format, symbol match) -> AMBIGUOUS_TOKEN
        5. MCX session awareness (trading session open) -> MARKET_CLOSED
        6. Staleness check (age > max_staleness) -> STALE
        7. Bid / Ask sanity check (crossed book: bid > ask) -> CROSSED_ORDER_BOOK
        8. Bid-Ask spread limits (spread % exceeds limit) -> EXCESSIVE_SPREAD
        9. Circuit band deviation (>15% from close/open) -> OUT_OF_BOUNDS
        """
        now = time.time()
        clean_sym = quote.symbol.upper().replace("_MCX", "").replace(".MCX", "").strip()

        # Check 1: Non-positive price rejection
        if quote.ltp <= 0.0 or math.isnan(quote.ltp) or math.isinf(quote.ltp):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.ZERO_OR_NEGATIVE_PRICE,
                error_message=f"LTP must be strictly positive: got {quote.ltp}",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 2: Zero-mock enforcement
        if quote.ltp in KNOWN_SYNTHETIC_PRICES or any(abs(quote.ltp - p) < 1e-4 for p in KNOWN_SYNTHETIC_PRICES):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.SYNTHETIC_MOCK_DETECTED,
                error_message=f"Identified known legacy synthetic price {quote.ltp} for {quote.symbol}. Rejected under zero-mock policy.",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 3: Timestamp provenance checking (physically realistic, no future timestamps >60s)
        ltt_sec = quote.last_trade_time / 1000.0 if quote.last_trade_time > 1e11 else float(quote.last_trade_time)
        if ltt_sec > (now + 60.0):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.OUT_OF_BOUNDS,
                error_message=f"Future-dated last_trade_time detected: trade time {ltt_sec} exceeds current clock {now} by >60s",
                quote=quote,
                validation_timestamp=now,
            )
        if quote.retrieved_at > (now + 60.0):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.OUT_OF_BOUNDS,
                error_message=f"Future-dated retrieved_at detected: timestamp {quote.retrieved_at} exceeds current clock {now} by >60s",
                quote=quote,
                validation_timestamp=now,
            )
        if quote.source != "UPSTOX" or quote.price_domain != "RAW_EXCHANGE_PRICE":
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.SOURCE_UNAUTHENTICATED,
                error_message=f"Quote source '{quote.source}' or domain '{quote.price_domain}' violates authentic exchange requirement.",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 4: Token / contract match
        if not quote.instrument_key or not quote.instrument_key.startswith("MCX_FO|"):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.AMBIGUOUS_TOKEN,
                error_message=f"Instrument key '{quote.instrument_key}' is not an authoritative MCX_FO token.",
                quote=quote,
                validation_timestamp=now,
            )
        if expected_commodity:
            clean_expected = expected_commodity.upper().replace("_MCX", "").replace(".MCX", "").strip()
            if clean_sym != clean_expected:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.AMBIGUOUS_TOKEN,
                    error_message=f"Symbol mismatch: expected {expected_commodity}, got {quote.symbol}",
                    quote=quote,
                    validation_timestamp=now,
                )
        if active_contract is not None:
            expected_key = getattr(active_contract, "instrument_key", None)
            if expected_key and quote.instrument_key != expected_key:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.AMBIGUOUS_TOKEN,
                    error_message=f"Instrument key mismatch with active contract: expected {expected_key}, got {quote.instrument_key}",
                    quote=quote,
                    validation_timestamp=now,
                )
            expected_tsym = getattr(active_contract, "trading_symbol", None)
            if expected_tsym and quote.trading_symbol and quote.trading_symbol != expected_tsym:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.AMBIGUOUS_TOKEN,
                    error_message=f"Trading symbol mismatch with active contract: expected {expected_tsym}, got {quote.trading_symbol}",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Check 5: MCX session awareness
        is_session_active = session_open if session_open is not None else mcx_session_engine.is_mcx_trading_session_open()
        if not is_session_active:
            if not allow_closed:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.MARKET_CLOSED,
                    error_message="MCX trading session is closed",
                    quote=quote,
                    validation_timestamp=now,
                )
            quote.market_status = "CLOSED"
        else:
            quote.market_status = "LIVE"

        # Check 6: Staleness check
        effective_stale_threshold = max_staleness_sec
        if effective_stale_threshold is None:
            effective_stale_threshold = DEFAULT_STALENESS_SECONDS.get(clean_sym, self.stale_threshold_seconds)

        quote_age_sec = max(0.0, quote.retrieved_at - ltt_sec) if quote.retrieved_at else max(0.0, now - ltt_sec)
        if is_session_active and quote_age_sec > effective_stale_threshold:
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.STALE,
                error_message=f"Live session quote is stale: age {quote_age_sec:.1f}s exceeds threshold {effective_stale_threshold}s",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 7: Bid / Ask sanity checks (Crossed order book)
        if quote.bid_price > 0.0 and quote.ask_price > 0.0:
            if quote.bid_price > quote.ask_price:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.CROSSED_ORDER_BOOK,
                    error_message=f"Crossed order book anomaly: Bid {quote.bid_price} > Ask {quote.ask_price}",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Check 8: Bid-Ask spread limits
        if quote.bid_price > 0.0 and quote.ask_price > 0.0:
            effective_max_spread = max_spread_pct
            if effective_max_spread is None:
                effective_max_spread = DEFAULT_MAX_SPREAD_PCT.get(clean_sym, self.default_max_spread_pct)
            spread = quote.ask_price - quote.bid_price
            spread_pct = spread / quote.ltp
            if spread_pct > effective_max_spread:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.EXCESSIVE_SPREAD,
                    error_message=f"Bid-ask spread {spread_pct*100:.2f}% exceeds limit {effective_max_spread*100:.2f}%",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Check 9: Circuit band deviation & Statutory price bounds
        effective_circuit_limit = circuit_limit_pct if circuit_limit_pct is not None else self.circuit_limit_pct
        ref_price = quote.close if (quote.close and quote.close > 0) else (quote.open if (quote.open and quote.open > 0) else None)
        if ref_price and ref_price > 0:
            deviation = abs(quote.ltp - ref_price) / ref_price
            if deviation > effective_circuit_limit:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.OUT_OF_BOUNDS,
                    error_message=f"Price deviation {deviation*100:.2f}% exceeds circuit limit {effective_circuit_limit*100:.2f}% from reference {ref_price}",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Statutory Price Range Boundaries (if defined)
        bounds = COMMODITY_PRICE_BOUNDS.get(clean_sym)
        if bounds:
            if quote.ltp < bounds["min"] or quote.ltp > bounds["max"]:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.OUT_OF_BOUNDS,
                    error_message=f"Price {quote.ltp} for {quote.symbol} is outside statutory bounds [{bounds['min']}, {bounds['max']}].",
                    quote=quote,
                    validation_timestamp=now,
                )

        # OHLC Consistency
        if quote.low > quote.high:
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.OHLC_INCONSISTENT,
                error_message=f"Low {quote.low} > High {quote.high}",
                quote=quote,
                validation_timestamp=now,
            )
        eps = 0.01
        if quote.low > 0 and quote.high > 0:
            if quote.ltp < (quote.low - eps) or quote.ltp > (quote.high + eps):
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.OHLC_INCONSISTENT,
                    error_message=f"LTP {quote.ltp} falls outside daily OHLC bounds [{quote.low}, {quote.high}]",
                    quote=quote,
                    validation_timestamp=now,
                )

        # All statutory checks passed
        return PriceIntegrityResult(
            is_valid=True,
            verdict=ValidationVerdict.VALID,
            error_message=None,
            quote=quote,
            validation_timestamp=now,
        )


# Global singleton instance
price_integrity_gateway = PriceIntegrityGateway()


# Module-level convenience function
def validate_price_integrity(
    quote: UniversalQuote,
    session_open: Optional[bool] = None,
    max_staleness_sec: Optional[float] = None,
    max_spread_pct: Optional[float] = None,
    circuit_limit_pct: Optional[float] = None,
    expected_commodity: Optional[str] = None,
    active_contract: Optional[Any] = None,
    allow_closed: bool = False,
) -> PriceIntegrityResult:
    """Convenience functional interface to PriceIntegrityGateway."""
    return price_integrity_gateway.validate_quote(
        quote=quote,
        session_open=session_open,
        max_staleness_sec=max_staleness_sec,
        max_spread_pct=max_spread_pct,
        circuit_limit_pct=circuit_limit_pct,
        expected_commodity=expected_commodity,
        active_contract=active_contract,
        allow_closed=allow_closed,
    )
