"""
APEX Universal Commodity Market Data Feed
=========================================
Ingests authentic, real-time exchange quotes, historical daily candles,
and intraday candle streams for MCX Commodities via Upstox API V2.

Invariants:
- Zero mock prices. Zero synthetic fallback dictionaries.
- Preserves raw exchange responses, timestamps, and quotation units.
- Operates under strict provenance: `source: "UPSTOX"`, `price_domain: "RAW_EXCHANGE_PRICE"`.
- If broker is unreachable, offline, or returns invalid data, raises
  `MarketDataUnavailableError` (fail-closed).
"""

import time
import math
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.config import settings
from backend.app.broker_providers.upstox_client import UpstoxRESTClient
from backend.app.market_data.mcx.contract_resolver import (
    ActiveContractResolver,
    active_contract_resolver,
    ContractTerm,
    MCXContract,
    CommodityResolution,
    TARGET_COMMODITIES,
)
from backend.app.market_data.candle_aggregator import (
    CandleAggregator,
    parse_upstox_candle,
    resample_1m_candles,
)

logger = logging.getLogger(__name__)


class MarketDataUnavailableError(Exception):
    """Raised when authentic exchange market data cannot be retrieved."""
    pass


class UniversalQuote(BaseModel):
    """Authoritative normalized commodity market quote."""
    symbol: str = Field(..., description="Canonical commodity code, e.g. 'GOLD'")
    instrument_id: str = Field(..., description="Platform instrument id, e.g. 'GOLD_MCX'")
    instrument_key: str = Field(..., description="Exchange unique key, e.g. 'MCX_FO|495213'")
    trading_symbol: str = Field(..., description="Exchange trading symbol, e.g. 'GOLD FUT 04 DEC 26'")
    contract_expiry: Optional[str] = Field(None, description="Contract expiry date, e.g. '2026-12-04'")
    exchange: str = "MCX"
    currency: str = "INR"
    unit: str = Field(..., description="Quotation unit, e.g. '₹/10g', '₹/kg', '₹/bbl'")
    ltp: float = Field(..., description="Last traded price from exchange")
    open: float = Field(..., description="Day's opening price")
    high: float = Field(..., description="Day's high price")
    low: float = Field(..., description="Day's low price")
    close: float = Field(..., description="Previous session close or current close")
    volume: int = Field(0, description="Session volume in contracts")
    open_interest: int = Field(0, description="Current open interest")
    bid_price: float = Field(0.0, description="Top bid price")
    ask_price: float = Field(0.0, description="Top ask price")
    last_trade_time: int = Field(..., description="Exchange execution trade timestamp in ms")
    market_status: str = Field("LIVE", description="'LIVE' or 'CLOSED'")
    source: str = "UPSTOX"
    price_domain: str = "RAW_EXCHANGE_PRICE"
    retrieved_at: float = Field(default_factory=time.time)
    raw_data: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None

    @field_validator("ltp", "open", "high", "low", "close", "bid_price", "ask_price", mode="before")
    @classmethod
    def check_finite(cls, v: Any) -> Any:
        if v is not None:
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                raise ValueError("Price values must be finite numbers")
            return val
        return v

    @model_validator(mode="before")
    @classmethod
    def sync_raw_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw = data.get("raw_data") if data.get("raw_data") is not None else data.get("raw_response")
            if raw is not None:
                if "raw_data" not in data or data["raw_data"] is None:
                    data["raw_data"] = raw
                if "raw_response" not in data or data["raw_response"] is None:
                    data["raw_response"] = raw
        return data


class UniversalMarketDataFeed:
    """Production market data feed orchestrator for MCX commodities."""

    def __init__(
        self,
        token: Optional[str] = None,
        client: Optional[UpstoxRESTClient] = None,
        resolver: Optional[ActiveContractResolver] = None,
        candle_aggregator: Optional[CandleAggregator] = None,
    ):
        self._token = token
        self._client = client
        self._resolver = resolver or active_contract_resolver
        self._candle_aggregator = candle_aggregator or CandleAggregator()

    @property
    def token(self) -> str:
        if self._token is not None:
            return self._token
        tok = settings.get_upstox_token
        if tok:
            return tok
        # Check environment
        import os
        return os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")

    def _get_client(self) -> UpstoxRESTClient:
        if self._client:
            return self._client
        tok = self.token
        if not tok:
            raise MarketDataUnavailableError(
                "UPSTOX_ANALYTICS_TOKEN is not configured. Live exchange quotes cannot be fetched."
            )
        return UpstoxRESTClient(token=tok, base_url=settings.upstox_base_url)

    def _parse_quote_dict(
        self,
        data: Dict[str, Any],
        contract: MCXContract,
        commodity_input: str,
    ) -> UniversalQuote:
        inst_key = contract.instrument_key
        quote_body = None
        key_colon = inst_key.replace("|", ":")
        key_pipe = inst_key.replace(":", "|")
        for k, v in data.items():
            v_token = str(v.get("instrument_token") or v.get("instrument_key") or "")
            if (
                k in (key_colon, key_pipe)
                or v_token in (inst_key, contract.exchange_token)
                or v_token.replace(":", "|") == inst_key
            ):
                quote_body = v
                break

        if not quote_body and len(data) == 1:
            quote_body = list(data.values())[0]

        if not quote_body:
            for k, v in data.items():
                tsym = str(v.get("symbol") or v.get("trading_symbol") or "").replace(" ", "").upper()
                if tsym and (
                    tsym == contract.trading_symbol.replace(" ", "").upper()
                    or contract.trading_symbol.replace(" ", "").upper().startswith(tsym)
                ):
                    quote_body = v
                    break

        if not quote_body:
            raise MarketDataUnavailableError(
                f"Exchange returned no quote data for contract '{contract.trading_symbol}' ({inst_key})"
            )

        ltp = quote_body.get("last_price")
        if ltp is None or float(ltp) <= 0:
            raise MarketDataUnavailableError(
                f"Exchange returned invalid LTP ({ltp}) for '{contract.trading_symbol}'"
            )
        ltp = float(ltp)

        ohlc = quote_body.get("ohlc", {}) or {}
        depth = quote_body.get("depth", {}) or {}
        bids = depth.get("buy", []) or []
        asks = depth.get("sell", []) or []

        bid_price = float(bids[0].get("price", 0.0)) if bids and bids[0].get("price") is not None else ltp
        ask_price = float(asks[0].get("price", 0.0)) if asks and asks[0].get("price") is not None else ltp

        open_px = float(ohlc.get("open") if ohlc.get("open") is not None else ltp)
        high_px = float(ohlc.get("high") if ohlc.get("high") is not None else ltp)
        low_px = float(ohlc.get("low") if ohlc.get("low") is not None else ltp)
        close_px = float(ohlc.get("close") if ohlc.get("close") is not None else (quote_body.get("previous_close") or ltp))

        # Volume and Open Interest
        volume = int(quote_body.get("volume", 0) or 0)
        open_interest = int(quote_body.get("oi", 0) or 0)

        # Execution timestamp
        ltt = quote_body.get("last_trade_time") or quote_body.get("timestamp")
        if ltt:
            try:
                ltt_val = int(float(ltt))
                ltt_ms = ltt_val if ltt_val > 1e11 else int(ltt_val * 1000)
            except (ValueError, TypeError):
                ltt_ms = int(time.time() * 1000)
        else:
            ltt_ms = int(time.time() * 1000)

        # Standardized display unit & instrument ID
        canon = self._resolver.get_commodity_config(commodity_input) or {}
        unit_label = canon.get("unit", contract.price_quote_unit or "₹/unit")
        instrument_id = canon.get("instrument_id", f"{contract.commodity_symbol}_MCX")

        return UniversalQuote(
            symbol=contract.commodity_symbol,
            instrument_id=instrument_id,
            instrument_key=contract.instrument_key,
            trading_symbol=contract.trading_symbol,
            contract_expiry=contract.expiry_date,
            exchange="MCX",
            currency="INR",
            unit=unit_label,
            ltp=ltp,
            open=open_px,
            high=high_px,
            low=low_px,
            close=close_px,
            volume=volume,
            open_interest=open_interest,
            bid_price=bid_price,
            ask_price=ask_price,
            last_trade_time=ltt_ms,
            market_status="LIVE",
            source="UPSTOX",
            price_domain="RAW_EXCHANGE_PRICE",
            retrieved_at=time.time(),
            raw_data=quote_body,
            raw_response=quote_body,
        )

    async def get_live_quote(
        self,
        commodity_input: str,
        term: ContractTerm = ContractTerm.NEAR_MONTH,
    ) -> UniversalQuote:
        """
        Fetch verified real-time quote for an MCX commodity.
        Resolves the active near/next/far-month contract, queries Upstox REST API,
        and normalizes into UniversalQuote.
        """
        contract = self._resolver.get_active_contract(commodity_input, term=term)
        if not contract:
            raise MarketDataUnavailableError(
                f"Could not resolve active {term.value} contract for commodity '{commodity_input}'"
            )

        client = self._get_client()
        should_close = (self._client is None)
        try:
            inst_key = contract.instrument_key
            endpoint = f"/v2/market-quote/quotes?instrument_key={inst_key}"
            res = await client._request("GET", endpoint)
            data = res.get("data", {})
            return self._parse_quote_dict(data, contract, commodity_input)
        except MarketDataUnavailableError:
            raise
        except Exception as e:
            raise MarketDataUnavailableError(
                f"Failed to fetch live quote for '{commodity_input}' ({contract.instrument_key}): {str(e)}"
            ) from e
        finally:
            if should_close:
                await client.close()

    async def get_live_quotes(
        self,
        commodity_inputs: List[str],
        term: ContractTerm = ContractTerm.NEAR_MONTH,
    ) -> List[UniversalQuote]:
        """
        Batch query quotes for multiple commodity instruments via /v2/market-quote/quotes.
        Batches up to 20 instruments per API request.
        """
        if not commodity_inputs:
            return []

        resolved_pairs: List[Tuple[str, MCXContract]] = []
        for inp in commodity_inputs:
            contract = self._resolver.get_active_contract(inp, term=term)
            if not contract:
                raise MarketDataUnavailableError(
                    f"Could not resolve active {term.value} contract for commodity '{inp}'"
                )
            resolved_pairs.append((inp, contract))

        client = self._get_client()
        should_close = (self._client is None)
        results: List[UniversalQuote] = []
        try:
            # Chunk in batches of 20
            for i in range(0, len(resolved_pairs), 20):
                chunk = resolved_pairs[i:i + 20]
                keys_param = ",".join(c.instrument_key for _, c in chunk)
                endpoint = f"/v2/market-quote/quotes?instrument_key={keys_param}"
                res = await client._request("GET", endpoint)
                data = res.get("data", {})
                for inp, contract in chunk:
                    quote = self._parse_quote_dict(data, contract, inp)
                    results.append(quote)
            return results
        except MarketDataUnavailableError:
            raise
        except Exception as e:
            raise MarketDataUnavailableError(
                f"Failed to fetch batch quotes for commodities: {str(e)}"
            ) from e
        finally:
            if should_close:
                await client.close()

    async def get_historical_daily_candles(
        self,
        commodity_input: str,
        lookback_days: int = 30,
        term: ContractTerm = ContractTerm.NEAR_MONTH,
    ) -> List[Dict[str, Any]]:
        """
        Fetch verified daily historical candles for an MCX commodity.
        Returns a chronologically ascending list of candles:
        [{ "timestamp": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ..., "open_interest": ... }]
        """
        contract = self._resolver.get_active_contract(commodity_input, term=term)
        if not contract:
            raise MarketDataUnavailableError(
                f"Could not resolve active {term.value} contract for '{commodity_input}'"
            )

        client = self._get_client()
        should_close = (self._client is None)
        try:
            import datetime
            now = datetime.datetime.now()
            from_dt = now - datetime.timedelta(days=lookback_days + 15)
            to_str = now.strftime("%Y-%m-%d")
            from_str = from_dt.strftime("%Y-%m-%d")

            candles = await self._candle_aggregator.fetch_daily_candles(
                instrument_key=contract.instrument_key,
                to_date=to_str,
                from_date=from_str,
                client=client,
            )

            if not candles:
                raise MarketDataUnavailableError(
                    f"No historical daily candles returned by exchange for {contract.trading_symbol}"
                )

            return candles
        except MarketDataUnavailableError:
            raise
        except Exception as e:
            raise MarketDataUnavailableError(
                f"Failed to fetch historical daily candles for '{commodity_input}': {str(e)}"
            ) from e
        finally:
            if should_close:
                await client.close()

    async def get_intraday_candles(
        self,
        commodity_input: str,
        interval: str = "1minute",
        term: ContractTerm = ContractTerm.NEAR_MONTH,
    ) -> List[Dict[str, Any]]:
        """
        Fetch intraday candle stream for the active session, resampled to desired timeframe if needed.
        """
        contract = self._resolver.get_active_contract(commodity_input, term=term)
        if not contract:
            raise MarketDataUnavailableError(
                f"Could not resolve active contract for '{commodity_input}'"
            )

        client = self._get_client()
        should_close = (self._client is None)
        try:
            candles = await self._candle_aggregator.fetch_intraday_candles(
                instrument_key=contract.instrument_key,
                interval=interval,
                client=client,
            )
            return candles
        except MarketDataUnavailableError:
            raise
        except Exception as e:
            raise MarketDataUnavailableError(
                f"Failed to fetch intraday candles for '{commodity_input}': {str(e)}"
            ) from e
        finally:
            if should_close:
                await client.close()


UniversalFeedService = UniversalMarketDataFeed
universal_market_data_feed = UniversalMarketDataFeed()
universal_feed_service = universal_market_data_feed
universal_feed = universal_market_data_feed
