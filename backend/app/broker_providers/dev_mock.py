"""
DevMockProvider — Explicit SIMULATED Market Data for Tests/Dev Only
====================================================================
IMPORTANT RULES:
  - provider_mode is ALWAYS "SIMULATED"
  - is_live is ALWAYS False
  - market_status is ALWAYS "SIMULATED"
  - The UI MUST display "🟠 DEV MOCK / SIMULATED" — NEVER "🟢 LIVE"

Price generation:
  - Prices are derived from a deterministic hash of the symbol name.
  - This gives a stable, reproducible price for each symbol in tests.
  - There are NO real-world snapshot values here.
  - These prices do NOT represent any current or historical market price.
  - They exist solely to exercise the UI rendering pipeline.

This provider MUST NEVER be activated when:
  ALLOW_MOCK_FALLBACK = false  (the production setting)
"""
import hashlib
import random
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from backend.app.broker_providers.base import MarketDataProvider, NormalizedTick

logger = logging.getLogger(__name__)

PROVIDER_MODE = "SIMULATED"


def _symbol_basis(symbol: str) -> float:
    """
    Derive a deterministic, reproducible price basis from the symbol string.
    This is NOT a real price — it is a stable test value in the range [100, 5000].
    """
    h = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
    return round(100.0 + (h % 4900), 2)


class DevMockProvider(MarketDataProvider):
    """
    Development Mock Provider — SIMULATED mode only.

    Generates structurally valid but clearly fake tick data.
    All output is labeled provider_mode=SIMULATED, is_live=False.
    """
    provider_name = "MOCK"

    def __init__(self):
        # Runtime price walk starts from symbol basis; no snapshot values stored.
        self._runtime_prices: Dict[str, float] = {}
        self.is_connected = False
        self.subscribed_symbols: List[str] = []
        self._ws_task: Optional[asyncio.Task] = None

    def _get_or_init_price(self, symbol: str) -> float:
        if symbol not in self._runtime_prices:
            self._runtime_prices[symbol] = _symbol_basis(symbol)
        return self._runtime_prices[symbol]

    async def connect(self) -> bool:
        self.is_connected = True
        logger.info("[MOCK PROVIDER] DevMockProvider connected — SIMULATED mode. NOT live market data.")
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

    def _generate_tick(self, symbol: str) -> NormalizedTick:
        base = self._get_or_init_price(symbol)
        # Small random walk — 0.1% volatility
        delta = (random.random() - 0.49) * (base * 0.001)
        new_ltp = round(max(base + delta, 1.0), 2)
        self._runtime_prices[symbol] = new_ltp

        spread = round(new_ltp * 0.0004, 2)
        prev_close = round(base * 0.998, 2)
        change = round(new_ltp - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 4) if prev_close > 0 else 0.0

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
        tick = self._generate_tick(symbol)
        return {
            "symbol": symbol,
            "exchange": "NSE",
            "instrument_type": "EQUITY" if ".NS" in symbol else "INDEX",
            "ltp": tick.ltp,
            "previous_close": tick.previous_close,
            "change": tick.change,
            "change_percent": tick.change_percent,
            "volume": tick.volume,
            "provider_timestamp": tick.timestamp,
            "received_timestamp": tick.timestamp,
            "source": "MOCK",
            "provider": "MOCK",
            "provider_mode": PROVIDER_MODE,
            "is_live": False,
            "market_status": "SIMULATED",
        }

    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        return [await self.get_quote(s) for s in symbols]

    async def get_historical_candles(
        self, symbol: str, interval: str, count: int = 100,
        from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        current = self._get_or_init_price(symbol)
        now_ts = int(time.time())
        step = 300 if interval == "5m" else (60 if interval == "1m" else 3600)
        candles = []
        base = current * 0.98
        rng = random.Random(symbol + interval)  # deterministic per symbol+interval
        for i in range(count, 0, -1):
            t = now_ts - i * step
            o = round(base + (rng.random() - 0.48) * (base * 0.002), 2)
            c = round(o + (rng.random() - 0.47) * (base * 0.002), 2)
            h = round(max(o, c) + rng.random() * (base * 0.001), 2)
            l = round(min(o, c) - rng.random() * (base * 0.001), 2)
            vol = rng.randint(500, 10000)
            candles.append({
                "timestamp": t, "time": t,
                "open": o, "high": h, "low": l, "close": c, "volume": vol,
                "vwap": round((h + l + c) / 3, 2),
                "source": "MOCK",
                "provider_mode": PROVIDER_MODE,
                "is_live": False,
                "market_status": "SIMULATED",
            })
            base = c
        return candles

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        spot = self._get_or_init_price(symbol)
        atm = round(spot / 50) * 50
        return {
            "status": "SIMULATED", "symbol": symbol, "underlying": symbol, "provider": "MOCK",
            "provider_mode": PROVIDER_MODE, "spotPrice": spot, "atmStrike": atm,
            "maxPainStrike": atm - 50, "pcr": 1.18, "totalCallOI": 4820000,
            "totalPutOI": 5680000, "impliedVolatility": 13.4,
            "expiryDate": expiry or "SIMULATED", "source": "MOCK",
            "is_live": False, "market_status": "SIMULATED", "strikes": [],
        }

    async def get_market_information(self, info_type: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        base = {"source": "MOCK", "provider_mode": PROVIDER_MODE, "is_live": False, "market_status": "SIMULATED"}
        if info_type == "fii-dii":
            import datetime
            return {
                **base,
                "date": datetime.datetime.now().strftime("%d %b %Y"),
                "fiiCashNetCr": -1245.8,
                "diiCashNetCr": 2830.4,
                "fiiIndexFuturesCr": 380.5,
                "fiiIndexOptionsCr": 1420.0,
                "fiiStockFuturesCr": -210.0,
                "timestamp": time.time(),
                "status": "AVAILABLE"
            }
        if info_type == "pcr":
            return {**base, "symbol": symbol or "NIFTY", "pcr": None}
        if info_type == "max-pain":
            return {**base, "symbol": symbol or "NIFTY", "maxPain": None}
        return {**base, "info_type": info_type, "symbol": symbol}

    async def connect_websocket(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        self.is_connected = True

        async def _loop():
            while self.is_connected:
                for sym in list(self.subscribed_symbols):
                    tick = self._generate_tick(sym)
                    await callback(tick)
                await asyncio.sleep(1.5)

        self._ws_task = asyncio.create_task(_loop())
        logger.info("[MOCK PROVIDER] WebSocket simulation loop started — SIMULATED mode.")
        return True
