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
        self.status_code: str = "INITIALIZING" # CONNECTED, DISCONNECTED, CONFIGURATION_ERROR, SIMULATED
        
        # Composite isolated cache: key format '{symbol}:{timeframe}:{mode}:{provider}'
        self._quote_cache: Dict[str, Dict[str, Any]] = {}
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
                    return True
                else:
                    self.active_provider = self.upstox_provider
                    self.is_live = False
                    self.status_code = "CONFIGURATION_ERROR"
                    return False
            
            connected = await self.upstox_provider.connect()
            if connected:
                self.active_provider = self.upstox_provider
                self.is_live = True
                self.status_code = "CONNECTED"
                logger.info("[MARKET DATA HUB] Successfully activated LIVE Upstox Provider.")
                return True
            else:
                if self.allow_mock_fallback:
                    logger.warning("[MARKET DATA HUB] Upstox connection failed. Falling back to DevMockProvider because ALLOW_MOCK_FALLBACK=true.")
                    self.active_provider = self.mock_provider
                    await self.mock_provider.connect()
                    self.is_live = False
                    self.status_code = "SIMULATED"
                    return True
                else:
                    self.active_provider = self.upstox_provider
                    self.is_live = False
                    self.status_code = "DISCONNECTED"
                    logger.error("[MARKET DATA HUB] Upstox connection failed and ALLOW_MOCK_FALLBACK=false. Setting status to DISCONNECTED.")
                    return False

        elif self.primary_provider_name == "DHAN":
            connected = await self.dhan_provider.connect()
            if connected:
                self.active_provider = self.dhan_provider
                self.is_live = True
                self.status_code = "CONNECTED"
                return True
            elif self.allow_mock_fallback:
                self.active_provider = self.mock_provider
                await self.mock_provider.connect()
                self.is_live = False
                self.status_code = "SIMULATED"
                return True
            else:
                self.active_provider = self.dhan_provider
                self.is_live = False
                self.status_code = "DISCONNECTED"
                return False

        # Default MOCK mode
        self.active_provider = self.mock_provider
        await self.mock_provider.connect()
        self.is_live = False
        self.status_code = "SIMULATED"
        logger.info("[MARKET DATA HUB] Operating in SIMULATED mode using DevMockProvider.")
        return True

    async def connect_websocket(self, tick_callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        async def _internal_cb(tick: NormalizedTick):
            self._last_tick_time = tick.timestamp
            cache_key = f"{tick.symbol}:QUOTE:{self.active_provider.provider_name}"
            self._quote_cache[cache_key] = tick.dict()
            await tick_callback(tick)

        if hasattr(self.active_provider, "connect_websocket"):
            return await self.active_provider.connect_websocket(_internal_cb)
        return False

    async def subscribe(self, symbols: List[str]):
        await self.active_provider.subscribe(symbols)

    async def unsubscribe(self, symbols: List[str]):
        await self.active_provider.unsubscribe(symbols)

    def _enrich_quote_integrity(self, quote: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Apply corporate action live quote semantics and integrity guard metadata."""
        validated = corporate_action_adjuster.validate_live_quote(quote, symbol)
        ts = float(validated.get("timestamp") or time.time())
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
        return validated

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        cache_key = f"{symbol}:QUOTE:{self.active_provider.provider_name}"
        try:
            raw_quote = await self.active_provider.get_quote(symbol)
            enriched = self._enrich_quote_integrity(raw_quote, symbol)
            self._quote_cache[cache_key] = enriched
            return enriched
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quote for {symbol}: {str(e)}")
            if self._quote_cache.get(cache_key):
                cached = dict(self._quote_cache[cache_key])
                cached["stale"] = True
                cached["provenance_status"] = "STALE"
                cached["is_live"] = False
                return cached
            raise e

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        try:
            raw_quotes = await self.active_provider.get_quotes(symbols)
            results = []
            for q in raw_quotes:
                if q and q.get("symbol"):
                    sym = q["symbol"]
                    cache_key = f"{sym}:QUOTE:{self.active_provider.provider_name}"
                    enriched = self._enrich_quote_integrity(q, sym)
                    self._quote_cache[cache_key] = enriched
                    results.append(enriched)
            return results
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quotes: {str(e)}")
            fallback = []
            for s in symbols:
                ck = f"{s}:QUOTE:{self.active_provider.provider_name}"
                if self._quote_cache.get(ck):
                    c = dict(self._quote_cache[ck])
                    c["stale"] = True
                    c["is_live"] = False
                    fallback.append(c)
                else:
                    fallback.append({"symbol": s, "stale": True, "is_live": False, "provenance_status": "DATA_INTEGRITY_ERROR"})
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
            return await self.active_provider.get_market_information("fii-dii")
        return {
            "status": "UNAVAILABLE",
            "fiiCashNetCr": None,
            "diiCashNetCr": None,
            "source": self.active_provider.provider_name,
            "is_live": False
        }

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
            "status": self.status_code,
            "mode": mode_str,
            "is_live": self.is_live and self.status_code == "CONNECTED",
            "last_tick_timestamp": self._last_tick_time,
            "latency_ms": latency_ms,
            "subscribed_count": len(getattr(self.active_provider, "subscribed_symbols", [])),
            "allow_mock_fallback": self.allow_mock_fallback,
            "websocket": {
                "connected": ws_conn,
                "reconnect_count": reconnects
            }
        }
