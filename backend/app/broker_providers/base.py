from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Callable, Awaitable
import time

class NormalizedTick(BaseModel):
    symbol: str
    instrument_key: Optional[str] = None
    exchange: str = "NSE"
    timestamp: float = Field(default_factory=time.time)
    received_at: float = Field(default_factory=lambda: time.time() * 1000.0)
    last_trade_time: Optional[float] = None
    ltp: float
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: int = 0
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_quantity: Optional[int] = None
    ask_quantity: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    open_interest: Optional[int] = None
    oi_change: Optional[int] = None
    provider: str = "GENERIC"
    is_live: bool = True
    market_status: str = "LIVE"

    @property
    def instrument_id(self) -> Optional[str]:
        return self.instrument_key

    @property
    def oi(self) -> Optional[int]:
        return self.open_interest

    @property
    def buy_qty(self) -> Optional[int]:
        return self.bid_quantity

    @property
    def sell_qty(self) -> Optional[int]:
        return self.ask_quantity

class MarketDataProvider(ABC):
    provider_name: str = "GENERIC"
    is_connected: bool = False
    subscribed_symbols: List[str] = []

    @abstractmethod
    async def connect(self) -> bool:
        """Establish session & WebSocket connections"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect streams"""
        pass

    @abstractmethod
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time normalized quote snapshot for a symbol"""
        pass

    @abstractmethod
    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch real-time normalized quotes for multiple symbols"""
        pass

    @abstractmethod
    async def get_historical_candles(
        self, symbol: str, interval: str, count: int = 100, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical candles normalized to {timestamp, open, high, low, close, volume, source}"""
        pass

    @abstractmethod
    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Fetch normalized option chain data"""
        pass

    @abstractmethod
    async def get_market_information(self, info_type: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch institutional flows (FII/DII), OI analysis, PCR, Max Pain"""
        pass

    @abstractmethod
    async def connect_websocket(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        """Connect WebSocket and stream normalized ticks to callback"""
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to live symbol stream"""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from live symbol stream"""
        pass

    # Legacy backward compatibility aliases
    async def fetch_historical_candles(self, symbol: str, interval: str, count: int = 100) -> List[Dict[str, Any]]:
        return await self.get_historical_candles(symbol, interval, count=count)

    async def fetch_option_chain(self, symbol: str) -> Dict[str, Any]:
        return await self.get_option_chain(symbol)
