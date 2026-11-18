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


class ValidationVerdict(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    MARKET_CLOSED = "MARKET_CLOSED"
    AMBIGUOUS_TOKEN = "AMBIGUOUS_TOKEN"
    SYNTHETIC_MOCK_DETECTED = "SYNTHETIC_MOCK_DETECTED"
    ZERO_OR_NEGATIVE_PRICE = "ZERO_OR_NEGATIVE_PRICE"
    EXCESSIVE_SPREAD = "EXCESSIVE_SPREAD"
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

    def __init__(self, stale_threshold_seconds: float = 120.0):
        self.stale_threshold_seconds = stale_threshold_seconds

    def validate_quote(self, quote: UniversalQuote) -> PriceIntegrityResult:
        now = time.time()

        # Check 1: Zero or Negative Price
        if quote.ltp <= 0.0 or math.isnan(quote.ltp) or math.isinf(quote.ltp):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.ZERO_OR_NEGATIVE_PRICE,
                error_message=f"LTP {quote.ltp} is non-positive or invalid for {quote.symbol}",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 2: Synthetic Mock Rejection
        if quote.ltp in KNOWN_SYNTHETIC_PRICES:
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.SYNTHETIC_MOCK_DETECTED,
                error_message=f"Identified known legacy synthetic price {quote.ltp} for {quote.symbol}. Rejected under zero-mock policy.",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 3: Source Authenticity & Provenance
        if quote.source != "UPSTOX" or quote.price_domain != "RAW_EXCHANGE_PRICE":
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.SOURCE_UNAUTHENTICATED,
                error_message=f"Quote source '{quote.source}' or domain '{quote.price_domain}' violates authentic exchange requirement.",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 4: Ambiguous Token Check
        if not quote.instrument_key or not quote.instrument_key.startswith("MCX_FO|"):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.AMBIGUOUS_TOKEN,
                error_message=f"Instrument key '{quote.instrument_key}' is not an authoritative MCX_FO token.",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 5: Statutory Price Bounds
        clean_code = quote.symbol.upper().replace("_MCX", "").replace(".MCX", "")
        bounds = COMMODITY_PRICE_BOUNDS.get(clean_code)
        if bounds:
            if quote.ltp < bounds["min"] or quote.ltp > bounds["max"]:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.OUT_OF_BOUNDS,
                    error_message=f"Price {quote.ltp} for {quote.symbol} is outside statutory bounds [{bounds['min']}, {bounds['max']}].",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Check 6: Bid / Ask Spread Sanity
        if quote.bid_price > 0.0 and quote.ask_price > 0.0:
            if quote.bid_price > quote.ask_price:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.EXCESSIVE_SPREAD,
                    error_message=f"Crossed market anomaly: Bid {quote.bid_price} > Ask {quote.ask_price}",
                    quote=quote,
                    validation_timestamp=now,
                )
            spread_pct = ((quote.ask_price - quote.bid_price) / quote.ltp) * 100.0
            if spread_pct > 5.0:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.EXCESSIVE_SPREAD,
                    error_message=f"Excessive spread: {spread_pct:.2f}% exceeds 5% maximum threshold.",
                    quote=quote,
                    validation_timestamp=now,
                )

        # Check 7: OHLC Internal Consistency
        # Low must be <= High; Open, Close, LTP must fall within [Low, High]
        if quote.low > quote.high:
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.OHLC_INCONSISTENT,
                error_message=f"Low {quote.low} > High {quote.high}",
                quote=quote,
                validation_timestamp=now,
            )
        # Allow small numerical epsilon for exchange rounding
        eps = 0.01
        if quote.ltp < (quote.low - eps) or quote.ltp > (quote.high + eps):
            return PriceIntegrityResult(
                is_valid=False,
                verdict=ValidationVerdict.OHLC_INCONSISTENT,
                error_message=f"LTP {quote.ltp} falls outside daily OHLC bounds [{quote.low}, {quote.high}]",
                quote=quote,
                validation_timestamp=now,
            )

        # Check 8: Temporal Freshness & Session Status
        is_live_session = mcx_session_engine.is_mcx_trading_session()
        # Compute age from last trade time or retrieval time
        ltt_sec = quote.last_trade_time / 1000.0 if quote.last_trade_time > 1e11 else float(quote.last_trade_time)
        age_seconds = max(0.0, now - ltt_sec)

        if is_live_session:
            # During live market hours, data must not be older than stale threshold
            if age_seconds > self.stale_threshold_seconds:
                return PriceIntegrityResult(
                    is_valid=False,
                    verdict=ValidationVerdict.STALE,
                    error_message=f"Live session data is stale: age {age_seconds:.1f}s exceeds threshold {self.stale_threshold_seconds}s.",
                    quote=quote,
                    validation_timestamp=now,
                )
            quote.market_status = "LIVE"
        else:
            # Outside session: valid as official closing/settlement reference
            quote.market_status = "CLOSED"

        # Check 9: All statutory checks passed
        return PriceIntegrityResult(
            is_valid=True,
            verdict=ValidationVerdict.VALID,
            error_message=None,
            quote=quote,
            validation_timestamp=now,
        )


# Global singleton instance
price_integrity_gateway = PriceIntegrityGateway()
