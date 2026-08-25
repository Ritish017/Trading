import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick
from backend.app.broker_providers.upstox_client import UpstoxRESTClient
from backend.app.broker_providers.upstox_websocket import UpstoxWebSocketClient

logger = logging.getLogger(__name__)

class UpstoxProvider(MarketDataProvider):
    """
    Upstox V3 Market Data Provider implementing MarketDataProvider interface.
    Ingests read-only market quotes, historical candles, option chains, and live WebSocket streams.
    """
    provider_name = "UPSTOX"

    def __init__(self, token: str = "", base_url: str = "https://api.upstox.com"):
        self.token = token.strip()
        self.base_url = base_url
        self.is_connected = False
        self.subscribed_symbols: List[str] = []
        
        self.rest_client: Optional[UpstoxRESTClient] = None
        self.ws_client: Optional[UpstoxWebSocketClient] = None
        self.ws_callback: Optional[Callable[[NormalizedTick], Awaitable[None]]] = None
        self.last_tick_time: Optional[float] = None

    async def connect(self) -> bool:
        """Authenticate and initialize Upstox REST & WebSocket clients."""
        logger.info("[UPSTOX] Initializing Upstox Market Data Session...")
        if not self.token:
            logger.error("[UPSTOX CONFIGURATION ERROR] UPSTOX_ANALYTICS_TOKEN is missing or empty in .env. Upstox Provider cannot authenticate.")
            self.is_connected = False
            return False

        try:
            self.rest_client = UpstoxRESTClient(token=self.token, base_url=self.base_url)
            # Test token validity by requesting WS auth URL
            ws_url = await self.rest_client.get_ws_authorize_url()
            logger.info("[UPSTOX] Successfully authenticated read-only Upstox Analytics Token with Upstox API.")
            
            self.ws_client = UpstoxWebSocketClient(
                token=self.token,
                get_ws_url_fn=self.rest_client.get_ws_authorize_url
            )
            self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"[UPSTOX AUTH FAILED] Authentication or endpoint verification failed: {str(e)}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        self.is_connected = False
        if self.ws_client:
            await self.ws_client.stop()
            self.ws_client = None
        if self.rest_client:
            await self.rest_client.close()
            self.rest_client = None
        logger.info("[UPSTOX] Upstox Provider disconnected.")

    async def connect_websocket(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        if not self.is_connected or not self.ws_client:
            logger.warning("[UPSTOX] Cannot start WebSocket stream because provider is not connected.")
            return False
        
        self.ws_callback = callback
        async def _wrapped_cb(tick: NormalizedTick):
            self.last_tick_time = tick.timestamp
            if self.ws_callback:
                await self.ws_callback(tick)

        ws_ok = await self.ws_client.start(_wrapped_cb)
        if ws_ok and self.subscribed_symbols:
            await self.ws_client.subscribe(self.subscribed_symbols)
        return ws_ok

    async def subscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols = list(set(self.subscribed_symbols + symbols))
        if self.ws_client and self.ws_client.is_connected:
            await self.ws_client.subscribe(symbols)

    async def unsubscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]
        if self.ws_client and self.ws_client.is_connected:
            await self.ws_client.unsubscribe(symbols)

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        if not self.rest_client or not self.is_connected:
            raise RuntimeError("Upstox REST client not connected.")
        return await self.rest_client.get_full_quote(symbol)

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        if not self.rest_client or not self.is_connected:
            raise RuntimeError("Upstox REST client not connected.")
        return await self.rest_client.get_multi_quotes(symbols)

    async def get_historical_candles(
        self, symbol: str, interval: str, count: int = 100, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not self.rest_client or not self.is_connected:
            raise RuntimeError("Upstox REST client not connected.")
        candles = await self.rest_client.get_historical_candles(symbol, interval, to_date=to_date, from_date=from_date)
        return candles[-count:] if count and len(candles) > count else candles

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        if not self.rest_client or not self.is_connected:
            raise RuntimeError("Upstox REST client not connected.")
        return await self.rest_client.get_option_chain(symbol, expiry_date=expiry)

    async def get_market_information(self, info_type: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        if not self.rest_client or not self.is_connected:
            raise RuntimeError("Upstox REST client not connected.")
        
        if info_type == "option-chain":
            return await self.get_option_chain(symbol or "NIFTY")
        
        if info_type == "fii-dii":
            from backend.app.market_data.institutional_feed import get_fii_dii_flow
            return await get_fii_dii_flow()
        
        # Market info structure
        quote = await self.get_quote(symbol or "NIFTY 50")
        return {
            "symbol": symbol or "NIFTY 50",
            "info_type": info_type,
            "open_interest": quote.get("open_interest", 0),
            "volume": quote.get("volume", 0),
            "source": "UPSTOX"
        }
