import logging
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from backend.app.config import settings
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick
from backend.app.broker_providers.upstox import UpstoxProvider
from backend.app.broker_providers.dhan import DhanProvider
from backend.app.broker_providers.dev_mock import DevMockProvider

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Provider-agnostic Market Data Hub & Orchestration Service.
    Handles provider selection, fallback logic, quote caching, stale data detection, and health state reporting.
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
        
        self._quote_cache: Dict[str, Dict[str, Any]] = {}
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
            self._quote_cache[tick.symbol] = tick.dict()
            await tick_callback(tick)

        if hasattr(self.active_provider, "connect_websocket"):
            return await self.active_provider.connect_websocket(_internal_cb)
        return False

    async def subscribe(self, symbols: List[str]):
        await self.active_provider.subscribe(symbols)

    async def unsubscribe(self, symbols: List[str]):
        await self.active_provider.unsubscribe(symbols)

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        try:
            quote = await self.active_provider.get_quote(symbol)
            self._quote_cache[symbol] = quote
            return quote
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quote for {symbol}: {str(e)}")
            if self._quote_cache.get(symbol):
                cached = self._quote_cache[symbol]
                cached["stale"] = True
                return cached
            raise e

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        try:
            quotes = await self.active_provider.get_quotes(symbols)
            for q in quotes:
                if q and q.get("symbol"):
                    self._quote_cache[q["symbol"]] = q
            return quotes
        except Exception as e:
            logger.error(f"[MARKET DATA HUB] Failed to fetch quotes: {str(e)}")
            return [self._quote_cache.get(s, {"symbol": s, "stale": True}) for s in symbols]

    async def get_candles(self, symbol: str, interval: str = "5m", count: int = 60) -> List[Dict[str, Any]]:
        return await self.active_provider.get_historical_candles(symbol, interval, count=count)

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
