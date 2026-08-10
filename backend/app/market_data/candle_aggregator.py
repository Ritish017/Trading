import time
import logging
from typing import Dict, List, Any, Optional
from backend.app.broker_providers.base import NormalizedTick

logger = logging.getLogger(__name__)

class MarketCandleAggregator:
    """
    Deterministic Real-Time Candle Aggregator.
    Aggregates high-frequency ticks into structured OHLCV candles for 1m, 3m, 5m, 15m, 30m, 1h, and 1D intervals.
    """

    INTERVAL_SECONDS = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "1D": 86400,
    }

    def __init__(self, max_history_per_interval: int = 500):
        self.max_history = max_history_per_interval
        # active_candles[symbol][interval] -> current active candle dict
        self.active_candles: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # completed_candles[symbol][interval] -> list of completed candle dicts
        self.completed_candles: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def _get_candle_start(self, timestamp: float, interval_seconds: int) -> int:
        """Align timestamp to the start of the interval window."""
        return (int(timestamp) // interval_seconds) * interval_seconds

    def seed_historical_candles(self, symbol: str, interval: str, candles: List[Dict[str, Any]]):
        """Seed completed historical candles into aggregator buffer."""
        if symbol not in self.completed_candles:
            self.completed_candles[symbol] = {}
        self.completed_candles[symbol][interval] = list(candles)

    def process_tick(self, tick: NormalizedTick) -> Dict[str, Dict[str, Any]]:
        """
        Processes incoming tick for all supported intervals.
        Returns a dict of updated candles for the symbol.
        """
        symbol = tick.symbol
        price = tick.ltp
        vol = tick.volume
        ts = tick.timestamp

        if symbol not in self.active_candles:
            self.active_candles[symbol] = {}
            self.completed_candles[symbol] = {}

        updated_candles = {}

        for tf, step in self.INTERVAL_SECONDS.items():
            candle_start = self._get_candle_start(ts, step)
            current = self.active_candles[symbol].get(tf)

            if current is None or current["time"] != candle_start:
                # If a candle just completed, finalize it and move to completed history
                if current is not None:
                    if tf not in self.completed_candles[symbol]:
                        self.completed_candles[symbol][tf] = []
                    self.completed_candles[symbol][tf].append(current)
                    # Enforce max history buffer limit
                    if len(self.completed_candles[symbol][tf]) > self.max_history:
                        self.completed_candles[symbol][tf] = self.completed_candles[symbol][tf][-self.max_history:]

                # Start new active candle
                current = {
                    "timestamp": candle_start,
                    "time": candle_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": vol,
                    "vwap": price,
                    "is_closed": False,
                    "source": tick.provider
                }
                self.active_candles[symbol][tf] = current
            else:
                # Update existing active candle
                current["high"] = max(current["high"], price)
                current["low"] = min(current["low"], price)
                current["close"] = price
                current["volume"] += vol
                current["vwap"] = round((current["high"] + current["low"] + price) / 3.0, 2)

            updated_candles[tf] = current

        return updated_candles

    def get_history(self, symbol: str, interval: str = "5m", count: int = 60) -> List[Dict[str, Any]]:
        """Returns completed candles merged with current active candle."""
        completed = self.completed_candles.get(symbol, {}).get(interval, [])
        active = self.active_candles.get(symbol, {}).get(interval)

        res = list(completed)
        if active:
            res.append(active)

        return res[-count:] if len(res) > count else res
