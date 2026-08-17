import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick

logger = logging.getLogger(__name__)

class DhanProvider(MarketDataProvider):
    """
    Dhan HQ API Provider Adapter implementing MarketDataProvider interface.
    Ref: https://dhanhq.co/docs/v2/
    Truthful state: Reports UNAVAILABLE when credentials or active integration endpoints are not configured.
    """
    provider_name = "DHAN"

    def __init__(self, client_id: str = "", access_token: str = ""):
        self.client_id = client_id.strip()
        self.access_token = access_token.strip()
        self.is_connected = False
        self.subscribed_symbols: List[str] = []

    async def connect(self) -> bool:
        logger.info("[DHAN] Initializing Dhan HQ API Session...")
        if not self.access_token or not self.client_id:
            logger.warning("[DHAN] Dhan client_id or access_token not configured in environment.")
            self.is_connected = False
            return False
        
        # When credentials are provided, full live integration requires Dhan API v2 SDK
        self.is_connected = False
        logger.warning("[DHAN] Dhan Live REST integration is in unauthenticated/stub mode.")
        return False

    async def disconnect(self) -> None:
        self.is_connected = False
        logger.info("[DHAN] Dhan HQ Provider disconnected.")

    async def subscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols.extend(symbols)

    async def unsubscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "UNAVAILABLE",
            "exchange": "NSE",
            "ltp": None,
            "source": "DHAN",
            "is_live": False,
            "reason": "DHAN_PROVIDER_NOT_CONNECTED"
        }

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        return [await self.get_quote(s) for s in symbols]

    async def get_historical_candles(
        self, symbol: str, interval: str, count: int = 100, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return []

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        return {
            "status": "UNAVAILABLE",
            "reason": "DHAN_OPTION_CHAIN_NOT_CONFIGURED",
            "symbol": symbol,
            "pcr": None,
            "maxPainStrike": None,
            "atmStrike": None,
            "totalCallOI": None,
            "totalPutOI": None,
            "impliedVolatility": None,
            "source": "DHAN",
            "is_live": False,
            "strikes": []
        }

    async def get_market_information(self, info_type: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        return {
            "info_type": info_type,
            "symbol": symbol,
            "status": "UNAVAILABLE",
            "source": "DHAN",
            "is_live": False
        }

    async def connect_websocket(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        return False
