import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class NormalizedTick(BaseModel):
    instrument_id: Optional[str] = None
    symbol: str
    exchange: str = "NSE"
    timestamp: float = Field(default_factory=time.time)
    received_at: float = Field(default_factory=lambda: time.time() * 1000.0)
    ltp: float
    previous_close: float = 0.0
    change: float = 0.0
    change_percent: float = 0.0
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
    provider: str = "UPSTOX"
    is_live: bool = True
    market_status: str = "LIVE"

class TickNormalizer:
    """
    Market Data Normalizer
    Transforms heterogeneous broker API payloads into standard NormalizedTick models.
    """

    @staticmethod
    def normalize_upstox_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("symbol", "RELIANCE.NS")
        ltp = float(payload.get("last_price", payload.get("ltp", 0.0)))
        prev_close = float(payload.get("previous_close", payload.get("prev_close", ltp)))
        if prev_close <= 0:
            prev_close = ltp
        change = round(ltp - prev_close, 2)
        change_pct = round((change / prev_close) * 100.0, 2) if prev_close > 0 else 0.0

        return NormalizedTick(
            symbol=symbol,
            exchange="NSE",
            timestamp=float(payload.get("timestamp", time.time())),
            received_at=time.time() * 1000.0,
            ltp=ltp,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            volume=int(payload.get("volume", 0)),
            bid=float(payload.get("bid", ltp * 0.999)) if payload.get("bid") is not None else None,
            ask=float(payload.get("ask", ltp * 1.001)) if payload.get("ask") is not None else None,
            open=float(payload.get("open", ltp)),
            high=float(payload.get("high", ltp)),
            low=float(payload.get("low", ltp)),
            close=float(payload.get("close", ltp)),
            oi=int(payload.get("open_interest", 0)),
            provider="UPSTOX",
            is_live=True
        )

    @staticmethod
    def normalize_dhan_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("tradingSymbol", "RELIANCE.NS")
        ltp = float(payload.get("lastPrice", 0.0))
        prev_close = float(payload.get("previousClose", ltp))
        change = round(ltp - prev_close, 2)
        change_pct = round((change / prev_close) * 100.0, 2) if prev_close > 0 else 0.0

        return NormalizedTick(
            symbol=symbol,
            exchange="NSE",
            timestamp=float(payload.get("timestamp", time.time())),
            received_at=time.time() * 1000.0,
            ltp=ltp,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            volume=int(payload.get("volume", 0)),
            open=float(payload.get("open", ltp)),
            high=float(payload.get("high", ltp)),
            low=float(payload.get("low", ltp)),
            close=float(payload.get("close", ltp)),
            provider="Dhan"
        )
