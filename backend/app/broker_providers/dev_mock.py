import random
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick

logger = logging.getLogger(__name__)

INITIAL_PRICES = {
    "RELIANCE.NS": 3045.50,
    "TCS.NS": 4280.10,
    "HDFCBANK.NS": 725.50,
    "ICICIBANK.NS": 1245.80,
    "INFY.NS": 1862.40,
    "NIFTY 50": 24580.00,
    "BANKNIFTY": 52400.00,
    "INDIA VIX": 13.45,
}

class DevMockProvider(MarketDataProvider):
    """
    Development Mock Provider used strictly for explicit SIMULATED testing mode.
    Generates structured ticks obeying financial invariants with explicit SIMULATED metadata.
    """
    provider_name = "MOCK"

    def __init__(self):
        self.prices = INITIAL_PRICES.copy()
        self.is_connected = False
        self.subscribed_symbols: List[str] = list(INITIAL_PRICES.keys())
        self._ws_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        self.is_connected = True
        logger.info("[MOCK PROVIDER] DevMockProvider connected in SIMULATED mode.")
        return True

    async def disconnect(self) -> None:
        self.is_connected = False
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None
        logger.info("[MOCK PROVIDER] DevMockProvider disconnected.")

    async def subscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols = list(set(self.subscribed_symbols + symbols))

    async def unsubscribe(self, symbols: List[str]) -> None:
        self.subscribed_symbols = [s for s in self.subscribed_symbols if s not in symbols]

    def generate_tick(self, symbol: str) -> NormalizedTick:
        base = self.prices.get(symbol, 1000.0)
        delta = (random.random() - 0.49) * (base * 0.0015)
        new_ltp = round(max(base + delta, 1.0), 2)
        self.prices[symbol] = new_ltp

        spread = round(new_ltp * 0.0004, 2)
        prev_close = round(base * 0.995, 2)
        change = round(new_ltp - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        return NormalizedTick(
            symbol=symbol,
            exchange="NSE",
            timestamp=time.time(),
            received_at=time.time() * 1000.0,
            last_trade_time=time.time(),
            ltp=new_ltp,
            open=round(new_ltp * 0.998, 2),
            high=round(new_ltp * 1.002, 2),
            low=round(new_ltp * 0.995, 2),
            close=new_ltp,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            volume=random.randint(100, 5000),
            bid=round(new_ltp - spread, 2),
            ask=round(new_ltp + spread, 2),
            provider="MOCK",
            is_live=False,
            market_status="SIMULATED",
        )

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        tick = self.generate_tick(symbol)
        return {
            "symbol": symbol,
            "exchange": tick.exchange,
            "instrument_type": "EQUITY" if ".NS" in symbol else "INDEX",
            "ltp": tick.ltp,
            "previous_close": tick.previous_close,
            "change": tick.change,
            "change_percent": tick.change_percent,
            "volume": tick.volume,
            "timestamp": tick.timestamp,
            "source": "MOCK",
            "is_live": False,
            "market_status": "SIMULATED",
        }

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        return [await self.get_quote(s) for s in symbols]

    async def get_historical_candles(
        self, symbol: str, interval: str, count: int = 100, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        current = self.prices.get(symbol, 1000.0)
        now_ts = int(time.time())
        step = 300 if interval == "5m" else (60 if interval == "1m" else 3600)
        candles = []

        base = current * 0.98
        for i in range(count, 0, -1):
            t = now_ts - i * step
            o = round(base + (random.random() - 0.48) * (base * 0.002), 2)
            c = round(o + (random.random() - 0.47) * (base * 0.002), 2)
            h = round(max(o, c) + random.random() * (base * 0.001), 2)
            l = round(min(o, c) - random.random() * (base * 0.001), 2)
            vol = random.randint(500, 10000)
            candles.append({
                "timestamp": t,
                "time": t,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": vol,
                "vwap": round((h + l + c) / 3, 2),
                "source": "MOCK",
                "is_live": False,
                "market_status": "SIMULATED"
            })
            base = c

        return candles

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        spot = self.prices.get(symbol, 24580.0)
        atm = round(spot / 50) * 50
        return {
            "status": "SIMULATED",
            "symbol": symbol,
            "underlying": symbol,
            "provider": "MOCK",
            "spotPrice": spot,
            "atmStrike": atm,
            "maxPainStrike": atm - 50,
            "pcr": 1.18,
            "totalCallOI": 4820000,
            "totalPutOI": 5680000,
            "impliedVolatility": 13.4,
            "expiryDate": expiry or "SIMULATED",
            "source": "MOCK",
            "is_live": False,
            "market_status": "SIMULATED",
            "strikes": []
        }

    async def get_market_information(self, info_type: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        if info_type == "fii-dii":
            return {
                "fiiCashNetCr": 1840.50,
                "diiCashNetCr": 1210.20,
                "timestamp": time.time(),
                "source": "MOCK",
                "is_live": False,
                "market_status": "SIMULATED"
            }
        elif info_type == "pcr":
            return {"symbol": symbol or "NIFTY", "pcr": 1.18, "source": "MOCK", "is_live": False, "market_status": "SIMULATED"}
        elif info_type == "max-pain":
            return {"symbol": symbol or "NIFTY", "maxPain": 24550.0, "source": "MOCK", "is_live": False, "market_status": "SIMULATED"}
        return {"info_type": info_type, "symbol": symbol, "source": "MOCK", "is_live": False, "market_status": "SIMULATED"}

    async def connect_websocket(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        self.is_connected = True
        async def _loop():
            while self.is_connected:
                for sym in self.subscribed_symbols:
                    tick = self.generate_tick(sym)
                    await callback(tick)
                await asyncio.sleep(1.2)
        self._ws_task = asyncio.create_task(_loop())
        return True
