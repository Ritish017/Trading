import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class NormalizedTick(BaseModel):
    instrument_id: Optional[str] = None
    symbol: str
    exchange: str = "NSE"
    timestamp: float = Field(default_factory=time.time)
    ltp: float
    volume: int = 0
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_quantity: Optional[int] = None
    ask_quantity: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    oi: Optional[int] = None
    oi_change: Optional[int] = None
    provider: str = "GENERIC"
    is_live: bool = True

class TickNormalizer:
    """
    Market Data Normalizer
    Transforms heterogeneous broker API payloads into standard NormalizedTick models.
    """

    @staticmethod
    def normalize_upstox_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("symbol", "RELIANCE.NS")
        ltp = payload.get("last_price", payload.get("ltp", 0.0))
        return NormalizedTick(
            symbol=symbol,
            exchange="NSE",
            timestamp=payload.get("timestamp", time.time()),
            ltp=float(ltp),
            volume=int(payload.get("volume", 0)),
            bid=float(payload.get("bid", ltp * 0.999)),
            ask=float(payload.get("ask", ltp * 1.001)),
            open=float(payload.get("open", ltp)),
            high=float(payload.get("high", ltp)),
            low=float(payload.get("low", ltp)),
            close=float(payload.get("close", ltp)),
            oi=int(payload.get("open_interest", 0)),
            provider="Upstox"
        )

    @staticmethod
    def normalize_dhan_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("tradingSymbol", "RELIANCE.NS")
        ltp = payload.get("lastPrice", 0.0)
        return NormalizedTick(
            symbol=symbol,
            exchange="NSE",
            timestamp=payload.get("timestamp", time.time()),
            ltp=float(ltp),
            volume=int(payload.get("volume", 0)),
            open=float(payload.get("open", ltp)),
            high=float(payload.get("high", ltp)),
            low=float(payload.get("low", ltp)),
            close=float(payload.get("close", ltp)),
            provider="Dhan"
        )
