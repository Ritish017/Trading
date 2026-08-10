import time
from typing import Dict, List, Any, Optional
from backend.app.broker_providers.base import NormalizedTick

class CandleAggregator:
    """
    Deterministic Candle Aggregator Engine.
    Aggregates high-frequency ticks into structured OHLCV candles.
    Interval map (seconds):
      1m  => 60
      3m  => 180
      5m  => 300
      15m => 900
      30m => 1800
      1h  => 3600
      1D  => 86400
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

    def __init__(self):
        # Store candles by symbol and interval: self.active_candles[symbol][interval]
        self.active_candles: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.completed_candles: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    def get_candle_timestamp(self, timestamp: float, interval_seconds: int) -> int:
        return (int(timestamp) // interval_seconds) * interval_seconds

    def process_tick(self, tick: NormalizedTick) -> Dict[str, Dict[str, Any]]:
        """
        Process incoming tick for all supported intervals.
        Returns a dict of updated candles for the tick's symbol.
        """
        symbol = tick.symbol
        price = tick.ltp
        vol = tick.volume
        ts = tick.timestamp

        if symbol not in self.active_candles:
            self.active_candles[symbol] = {}
            self.completed_candles[symbol] = {}

        updated = {}

        for timeframe, step in self.INTERVAL_SECONDS.items():
            candle_start = self.get_candle_timestamp(ts, step)
            current = self.active_candles[symbol].get(timeframe)

            if current is None or current["time"] != candle_start:
                # Store completed candle if existing
                if current is not None:
                    if timeframe not in self.completed_candles[symbol]:
                        self.completed_candles[symbol][timeframe] = []
                    self.completed_candles[symbol][timeframe].append(current)
                    # Limit historical array memory cap to 500 candles per timeframe
                    if len(self.completed_candles[symbol][timeframe]) > 500:
                        self.completed_candles[symbol][timeframe].pop(0)

                # Initialize new active candle
                new_candle = {
                    "time": candle_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": vol,
                    "vwap": price,
                    "cum_tp_vol": price * vol,
                    "cum_vol": vol,
                }
                self.active_candles[symbol][timeframe] = new_candle
                updated[timeframe] = new_candle
            else:
                # Update existing candle
                current["high"] = max(current["high"], price)
                current["low"] = min(current["low"], price)
                current["close"] = price
                current["volume"] += vol
                current["cum_tp_vol"] += price * vol
                current["cum_vol"] += vol
                if current["cum_vol"] > 0:
                    current["vwap"] = round(current["cum_tp_vol"] / current["cum_vol"], 2)
                updated[timeframe] = current

        return updated

    def get_history(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[Dict[str, Any]]:
        history = self.completed_candles.get(symbol, {}).get(timeframe, [])
        active = self.active_candles.get(symbol, {}).get(timeframe)
        res = list(history)
        if active:
            res.append(active)
        return res[-limit:]
