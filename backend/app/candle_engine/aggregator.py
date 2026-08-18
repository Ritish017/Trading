import time
import copy
from typing import Dict, List, Any, Optional
from backend.app.broker_providers.base import NormalizedTick

class CandleAggregator:
    """
    Canonical Deterministic Candle Aggregator Engine.
    Aggregates high-frequency ticks into structured OHLCV candles with mathematical VWAP.
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

    def __init__(self, max_history_per_interval: int = 500):
        self.max_history = max_history_per_interval
        # active_candles[symbol][interval] -> current active candle dict
        self.active_candles: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # completed_candles[symbol][interval] -> list of completed candle dicts
        self.completed_candles: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # last_tick_volume[symbol] -> last cumulative volume for computing tick delta
        self.last_tick_volume: Dict[str, int] = {}

    def get_candle_timestamp(self, timestamp: float, interval_seconds: int) -> int:
        return (int(timestamp) // interval_seconds) * interval_seconds

    def seed_historical_candles(self, symbol: str, interval: str, candles: List[Dict[str, Any]]):
        """Seed completed historical candles into aggregator buffer."""
        if symbol not in self.completed_candles:
            self.completed_candles[symbol] = {}
        # Format and store completed candles
        formatted = []
        for c in candles:
            item = dict(c)
            ts = item.get("timestamp") or item.get("time") or 0
            item["time"] = int(ts)
            item["timestamp"] = int(ts)
            item["is_closed"] = True
            formatted.append(item)
        self.completed_candles[symbol][interval] = formatted[-self.max_history:]

    def process_tick(self, tick: NormalizedTick) -> Dict[str, Dict[str, Any]]:
        """
        Process incoming tick for all supported intervals.
        Returns a dict of updated candles for the tick's symbol.
        """
        symbol = tick.symbol
        price = float(tick.ltp)
        raw_vol = int(tick.volume or 0)
        ts = float(tick.timestamp or time.time())
        source = tick.provider or "GENERIC"

        # Determine volume contribution for this tick
        if getattr(tick, "is_cumulative_volume", False):
            last_vol = self.last_tick_volume.get(symbol)
            if last_vol is None:
                # First tick of session: initialize baseline, no artificial jump
                self.last_tick_volume[symbol] = raw_vol
                delta_vol = 0
            elif raw_vol >= last_vol:
                delta_vol = raw_vol - last_vol
                self.last_tick_volume[symbol] = raw_vol
            else:
                # Session reset or rollover
                delta_vol = raw_vol if raw_vol > 0 else 0
                self.last_tick_volume[symbol] = raw_vol
        else:
            # Discrete per-tick trade volume
            delta_vol = raw_vol if raw_vol > 0 else 0

        if symbol not in self.active_candles:
            self.active_candles[symbol] = {}
            self.completed_candles[symbol] = {}

        updated = {}

        for timeframe, step in self.INTERVAL_SECONDS.items():
            candle_start = self.get_candle_timestamp(ts, step)
            current = self.active_candles[symbol].get(timeframe)

            if current is None or current["time"] != candle_start:
                # Finalize previous active candle and move to completed history
                if current is not None:
                    finalized = copy.deepcopy(current)
                    finalized["is_closed"] = True
                    if timeframe not in self.completed_candles[symbol]:
                        self.completed_candles[symbol][timeframe] = []
                    self.completed_candles[symbol][timeframe].append(finalized)
                    if len(self.completed_candles[symbol][timeframe]) > self.max_history:
                        self.completed_candles[symbol][timeframe] = self.completed_candles[symbol][timeframe][-self.max_history:]

                # Initialize new active candle
                turnover = price * delta_vol
                new_candle = {
                    "time": candle_start,
                    "timestamp": candle_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": delta_vol,
                    "vwap": round(price, 2) if delta_vol > 0 else None,
                    "cum_turnover": turnover,
                    "cum_vol": delta_vol,
                    "is_closed": False,
                    "source": source
                }
                self.active_candles[symbol][timeframe] = new_candle
                updated[timeframe] = new_candle
            else:
                # Update existing active candle
                current["high"] = max(current["high"], price)
                current["low"] = min(current["low"], price)
                current["close"] = price
                current["volume"] += delta_vol
                current["cum_turnover"] += price * delta_vol
                current["cum_vol"] += delta_vol
                if current["cum_vol"] > 0:
                    current["vwap"] = round(current["cum_turnover"] / current["cum_vol"], 2)
                else:
                    current["vwap"] = None
                current["is_closed"] = False
                current["source"] = source
                updated[timeframe] = current

        return updated

    def get_history(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> List[Dict[str, Any]]:
        history = self.completed_candles.get(symbol, {}).get(timeframe, [])
        active = self.active_candles.get(symbol, {}).get(timeframe)
        res = list(history)
        if active:
            res.append(active)
        return res[-limit:] if limit and len(res) > limit else res
