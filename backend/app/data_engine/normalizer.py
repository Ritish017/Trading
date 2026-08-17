import time
from typing import Dict, Any, Optional
from backend.app.broker_providers.base import NormalizedTick

class TickNormalizer:
    """
    Market Data Normalizer
    Transforms heterogeneous broker API payloads into standard canonical NormalizedTick models.
    """

    @staticmethod
    def normalize_upstox_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("symbol", "RELIANCE.NS")
        ltp = float(payload.get("last_price", payload.get("ltp", 0.0)))
        prev_close_raw = payload.get("previous_close", payload.get("prev_close"))
        prev_close = float(prev_close_raw) if prev_close_raw is not None else None
        
        if prev_close is not None and prev_close > 0:
            change = round(ltp - prev_close, 2)
            change_pct = round((change / prev_close) * 100.0, 2)
        else:
            change = None
            change_pct = None

        raw_bid = payload.get("bid")
        raw_ask = payload.get("ask")
        raw_open = payload.get("open")
        raw_high = payload.get("high")
        raw_low = payload.get("low")
        raw_close = payload.get("close")
        raw_oi = payload.get("open_interest", payload.get("oi"))

        return NormalizedTick(
            symbol=symbol,
            instrument_key=payload.get("instrument_key"),
            exchange=payload.get("exchange", "NSE"),
            timestamp=float(payload.get("timestamp", time.time())),
            received_at=time.time() * 1000.0,
            last_trade_time=float(payload.get("last_trade_time", payload.get("timestamp", time.time()))),
            ltp=ltp,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            volume=int(payload.get("volume", 0)),
            bid=float(raw_bid) if raw_bid is not None else None,
            ask=float(raw_ask) if raw_ask is not None else None,
            open=float(raw_open) if raw_open is not None else None,
            high=float(raw_high) if raw_high is not None else None,
            low=float(raw_low) if raw_low is not None else None,
            close=float(raw_close) if raw_close is not None else None,
            open_interest=int(raw_oi) if raw_oi is not None else None,
            provider="UPSTOX",
            is_live=True,
            market_status="LIVE"
        )

    @staticmethod
    def normalize_dhan_feed(payload: Dict[str, Any]) -> NormalizedTick:
        symbol = payload.get("tradingSymbol", "RELIANCE.NS")
        ltp = float(payload.get("lastPrice", 0.0))
        prev_close_raw = payload.get("previousClose")
        prev_close = float(prev_close_raw) if prev_close_raw is not None else None
        
        if prev_close is not None and prev_close > 0:
            change = round(ltp - prev_close, 2)
            change_pct = round((change / prev_close) * 100.0, 2)
        else:
            change = None
            change_pct = None

        raw_open = payload.get("open")
        raw_high = payload.get("high")
        raw_low = payload.get("low")
        raw_close = payload.get("close")

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
            open=float(raw_open) if raw_open is not None else None,
            high=float(raw_high) if raw_high is not None else None,
            low=float(raw_low) if raw_low is not None else None,
            close=float(raw_close) if raw_close is not None else None,
            provider="DHAN",
            is_live=False,
            market_status="UNAVAILABLE"
        )
