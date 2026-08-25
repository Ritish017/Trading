import logging
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from backend.app.config import settings
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick
from backend.app.broker_providers.upstox import UpstoxProvider
from backend.app.broker_providers.dhan import DhanProvider
from backend.app.broker_providers.dev_mock import DevMockProvider
from backend.app.market_data.corporate_actions.models import PriceAdjustmentMode
from backend.app.market_data.corporate_actions.adjuster import corporate_action_adjuster
from backend.app.market_data.corporate_actions.integrity_guard import market_data_integrity_guard
from backend.app.market_data.canonical_store import canonical_store, CanonicalQuote

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Provider-agnostic Market Data Hub & Orchestration Service.
    Handles provider selection, fallback logic, corporate-action-aware quote caching,
    stale data detection, and mathematical health state reporting.
    """

    def __init__(self):
        self.primary_provider_name = settings.active_broker_provider.upper()
        self.allow_mock_fallback = settings.allow_mock_fallback
        
        self.mock_provider = DevMockProvider()
        self.upstox_provider = UpstoxProvider(
            token=settings.get_upstox_token or "",
            base_url=settings.upstox_base_url
        )
        self.dhan_provider = DhanProvider(
            client_id=settings.dhan_client_id or "",
            access_token=settings.dhan_access_token or ""
        )

        self.active_provider: MarketDataProvider = self.mock_provider
        self.is_live: bool = False
        self.status_code: str = "INITIALIZING"
        self.provider_mode: str = "UNAVAILABLE"  # AUTHENTIC_LIVE | SIMULATED | UNAVAILABLE

        # Lightweight per-provider cache (keyed by symbol) — canonical truth is in canonical_store
        self._candle_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._last_tick_time: Optional[float] = None
        self._ws_reconnect_count: int = 0

    async def initialize(self) -> bool:
        """Initialize and connect the active provider based on configuration."""
        logger.info(f"[MARKET DATA HUB] Initializing Market Data Service (Configured Primary: {self.primary_provider_name}, Fallback Allowed: {self.allow_mock_fallback})...")

        if self.primary_provider_name == "UPSTOX":
            if not settings.get_upstox_token:
                logger.error("[MARKET DATA HUB] UPSTOX selected but UPSTOX_ANALYTICS_TOKEN is missing!")
                if self.allow_mock_fallback:
                    logger.warning("[MARKET DATA HUB] Falling back to SIMULATED DevMockProvider because ALLOW_MOCK_FALLBACK=true.")
                    self.active_provider = self.mock_provider
                    await self.mock_provider.connect()
                    self.is_live = False
                    self.status_code = "SIMULATED"
                    self.provider_mode = "SIMULATED"
                    return True
                else:
                    self.active_provider = self.upstox_provider
                    self.is_live = False
                    self.status_code = "CONFIGURATION_ERROR"
                    self.provider_mode = "UNAVAILABLE"
                    return False

            connected = await self.upstox_provider.connect()
            if connected:
                self.active_provider = self.upstox_provider
                self.is_live = True
                self.status_code = "CONNECTED"
                self.provider_mode = "AUTHENTIC_LIVE"
                logger.info("[MARKET DATA HUB] Successfully activated LIVE Upstox Provider.")
                return True
            else:
                if self.allow_mock_fallback:
                    logger.warning("[MARKET DATA HUB] Upstox connection failed. Falling back to DevMockProvider because ALLOW_MOCK_FALLBACK=true.")
                    self.active_provider = self.mock_provider
                    await self.mock_provider.connect()
                    self.is_live = False
                    self.status_code = "SIMULATED"
                    self.provider_mode = "SIMULATED"
                    return True
                else:
                    self.active_provider = self.upstox_provider
                    self.is_live = False
                    self.status_code = "DISCONNECTED"
                    self.provider_mode = "UNAVAILABLE"
                    logger.error("[MARKET DATA HUB] Upstox connection failed and ALLOW_MOCK_FALLBACK=false.")
                    return False

        elif self.primary_provider_name == "DHAN":
            connected = await self.dhan_provider.connect()
            if connected:
                self.active_provider = self.dhan_provider
                self.is_live = True
                self.status_code = "CONNECTED"
                self.provider_mode = "AUTHENTIC_LIVE"
                return True
            elif self.allow_mock_fallback:
                self.active_provider = self.mock_provider
                await self.mock_provider.connect()
                self.is_live = False
                self.status_code = "SIMULATED"
                self.provider_mode = "SIMULATED"
                return True
            else:
                self.active_provider = self.dhan_provider
                self.is_live = False
                self.status_code = "DISCONNECTED"
                self.provider_mode = "UNAVAILABLE"
                return False

        # Default MOCK mode
        self.active_provider = self.mock_provider
        await self.mock_provider.connect()
        self.is_live = False
        self.status_code = "SIMULATED"
        self.provider_mode = "SIMULATED"
        logger.info("[MARKET DATA HUB] Operating in SIMULATED mode using DevMockProvider.")
        return True

    async def connect_websocket(self, tick_callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        async def _internal_cb(tick: NormalizedTick):
            self._last_tick_time = tick.timestamp
            # Push into canonical store as WS source
            ws_raw = {
                "symbol": tick.symbol,
                "instrument_key": getattr(tick, "instrument_key", tick.symbol),
                "exchange": tick.exchange,
                "ltp": tick.ltp,
                "previous_close": tick.previous_close,
                "open": tick.open,
                "high": tick.high,
                "low": tick.low,
                "volume": tick.volume,
                "bid": tick.bid,
                "ask": tick.ask,
                "provider": tick.provider or self.active_provider.provider_name,
                "provider_mode": self.provider_mode,
                "provider_timestamp": tick.timestamp,
                "received_timestamp": time.time(),
                "source": tick.provider or self.active_provider.provider_name,
            }
            canonical_store.update_from_ws(ws_raw)
            await tick_callback(tick)

        if hasattr(self.active_provider, "connect_websocket"):
            return await self.active_provider.connect_websocket(_internal_cb)
        return False

    async def subscribe(self, symbols: List[str]):
        await self.active_provider.subscribe(symbols)

    async def unsubscribe(self, symbols: List[str]):
        await self.active_provider.unsubscribe(symbols)

    def _enrich_and_canonicalize(self, raw_quote: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Apply corporate-action live-quote validation, then push to canonical store."""
        # Corporate action guard — ONLY validates, never modifies live LTP
        validated = corporate_action_adjuster.validate_live_quote(raw_quote, symbol)
        ts = float(validated.get("provider_timestamp") or validated.get("timestamp") or time.time())
        ltp = float(validated.get("ltp") or 0.0)
        p_close = float(validated.get("previous_close") or ltp) if validated.get("previous_close") else None

        integrity_info = market_data_integrity_guard.validate_live_claim(
            provider=self.active_provider.provider_name,
            is_provider_authenticated=self.is_live,
            is_provider_connected=self.status_code == "CONNECTED",
            provider_timestamp=ts,
            current_price=ltp,
            previous_close=p_close,
        )
        validated["data_age_seconds"] = integrity_info["data_age_seconds"]
        validated["provenance_status"] = integrity_info["provenance_status"]
        validated["display_label"] = integrity_info["display_label"]
        validated["is_live"] = integrity_info["can_claim_live"]
        validated["anomaly_classification"] = integrity_info["anomaly_classification"]
        validated["classification_reason"] = integrity_info["classification_reason"]
        validated["provider_mode"] = self.provider_mode
        validated["provider_timestamp"] = ts
        validated["received_timestamp"] = time.time()

        # Push to canonical store as REST source
        canonical_store.update_from_rest(validated)
        return validated

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        try:
            raw_quote = await self.active_provider.get_quote(symbol)
            return self._enrich_and_canonicalize(raw_quote, symbol)
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quote for {symbol}: {str(e)}")
            # Check canonical store for a recent quote rather than silently serving stale data
            canonical = canonical_store.get_canonical_quote(symbol)
            if canonical and not canonical.is_stale:
                result = canonical.to_api_dict()
                result["stale"] = False
                return result
            elif canonical:
                result = canonical.to_api_dict()
                result["stale"] = True
                result["provenance_status"] = "STALE"
                result["is_live"] = False
                return result
            # No data at all — raise, never fabricate
            raise e

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        try:
            raw_quotes = await self.active_provider.get_quotes(symbols)
            results = []
            for q in raw_quotes:
                if q and q.get("symbol"):
                    sym = q["symbol"]
                    enriched = self._enrich_and_canonicalize(q, sym)
                    results.append(enriched)
            return results
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quotes: {str(e)}")
            # Return canonical store data (marked stale) rather than fabricating
            fallback = []
            for s in symbols:
                canonical = canonical_store.get_canonical_quote(s)
                if canonical:
                    result = canonical.to_api_dict()
                    result["stale"] = True
                    result["is_live"] = False
                    result["provenance_status"] = "STALE"
                    fallback.append(result)
                else:
                    fallback.append({"symbol": s, "ltp": None, "is_live": False, "provenance_status": "UNAVAILABLE", "provider_mode": "UNAVAILABLE"})
            return fallback

    async def get_candles(
        self,
        symbol: str,
        interval: str = "5m",
        count: int = 60,
        mode: PriceAdjustmentMode = PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE
    ) -> List[Dict[str, Any]]:
        cache_key = f"{symbol}:{interval}:{mode.value}:{self.active_provider.provider_name}"
        raw_candles = await self.active_provider.get_historical_candles(symbol, interval, count=count)
        adjusted_candles = corporate_action_adjuster.adjust_candle_series(raw_candles, symbol, mode=mode)
        self._candle_cache[cache_key] = adjusted_candles
        return adjusted_candles

    async def get_option_chain(self, symbol: str) -> Dict[str, Any]:
        return await self.active_provider.get_option_chain(symbol)

    async def get_fii_dii(self) -> Dict[str, Any]:
        if hasattr(self.active_provider, "get_market_information"):
            data = await self.active_provider.get_market_information("fii-dii")
            if data and data.get("fiiCashNetCr") is not None:
                return data
        from backend.app.market_data.institutional_feed import get_fii_dii_flow
        return await get_fii_dii_flow()

    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        if hasattr(self.active_provider, "get_market_information"):
            return await self.active_provider.get_market_information("oi", symbol)
        return {
            "symbol": symbol,
            "status": "UNAVAILABLE",
            "open_interest": None,
            "source": self.active_provider.provider_name
        }

    async def get_pcr(self, symbol: str) -> Dict[str, Any]:
        chain = await self.get_option_chain(symbol)
        pcr_val = chain.get("pcr")
        return {
            "symbol": symbol,
            "pcr": pcr_val,
            "status": "AVAILABLE" if pcr_val is not None else "UNAVAILABLE",
            "source": chain.get("source", self.active_provider.provider_name)
        }

    async def get_max_pain(self, symbol: str) -> Dict[str, Any]:
        chain = await self.get_option_chain(symbol)
        mp_val = chain.get("maxPainStrike") or chain.get("maxPain")
        return {
            "symbol": symbol,
            "maxPain": mp_val,
            "status": "AVAILABLE" if mp_val is not None else "UNAVAILABLE",
            "source": chain.get("source", self.active_provider.provider_name)
        }

    def get_canonical_quote(self, symbol: str):
        """Return the canonical quote for a symbol, or None if no data."""
        return canonical_store.get_canonical_quote(symbol)

    def get_diagnostic(self, symbol: str) -> Dict[str, Any]:
        """Full provenance diagnostic for a symbol."""
        return canonical_store.get_diagnostic(
            symbol=symbol,
            authenticated=self.is_live,
            connected=self.status_code == "CONNECTED"
        )

    def get_health_status(self) -> Dict[str, Any]:
        ws_conn = False
        reconnects = 0
        if isinstance(self.active_provider, UpstoxProvider) and self.active_provider.ws_client:
            ws_conn = self.active_provider.ws_client.is_connected
            reconnects = self.active_provider.ws_client.reconnect_count
        elif isinstance(self.active_provider, DevMockProvider):
            ws_conn = self.active_provider.is_connected

        mode_str = "LIVE" if (self.is_live and self.status_code == "CONNECTED") else ("SIMULATED" if self.status_code == "SIMULATED" else "OFFLINE")

        latency_ms = None
        if self._last_tick_time:
            latency_ms = round((time.time() - self._last_tick_time) * 1000, 1)

        return {
            "active_provider": self.active_provider.provider_name,
            "configured_primary": self.primary_provider_name,
            "provider_mode": self.provider_mode,
            "status": self.status_code,
            "mode": mode_str,
            "is_live": self.is_live and self.status_code == "CONNECTED",
            "last_tick_timestamp": self._last_tick_time,
            "latency_ms": latency_ms,
            "subscribed_count": len(getattr(self.active_provider, "subscribed_symbols", [])),
            "canonical_symbols_tracked": len(canonical_store.get_all_canonical()),
            "allow_mock_fallback": self.allow_mock_fallback,
            "websocket": {
                "connected": ws_conn,
                "reconnect_count": reconnects
            }
        }
