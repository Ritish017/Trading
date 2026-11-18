"""
APEX Universal Candle Aggregation & Multi-Timeframe Resampling Engine
====================================================================
Ingests raw historical daily candles and intraday 1m candle streams from Upstox API V2.
Reverses descending order candles to ascending chronological order, extracts all 7
candle elements [timestamp, open, high, low, close, volume, open_interest], and performs
client-side resampling of 1m candles into 5m, 15m, 30m, and 1h buckets.

Also maintains the MarketCandleAggregator compatibility layer for real-time tick-to-candle streaming.
"""

import datetime
import logging
import math
import time
import urllib.parse
from typing import Dict, List, Any, Optional, Union

from backend.app.broker_providers.base import NormalizedTick
from backend.app.broker_providers.upstox_client import UpstoxRESTClient
from backend.app.candle_engine.aggregator import CandleAggregator as CanonicalCandleAggregator

logger = logging.getLogger(__name__)

SUPPORTED_RESAMPLE_INTERVALS = {
    "1m": 60,
    "1min": 60,
    "1minute": 60,
    "5m": 300,
    "5min": 300,
    "5minute": 300,
    "15m": 900,
    "15min": 900,
    "15minute": 900,
    "30m": 1800,
    "30min": 1800,
    "30minute": 1800,
    "1h": 3600,
    "60m": 3600,
    "60min": 3600,
    "60minute": 3600,
    "1hour": 3600,
    "1d": 86400,
    "day": 86400,
    "1D": 86400,
}


def parse_upstox_candle(raw: list) -> Dict[str, Any]:
    """
    Parses a single 7-element Upstox API V2 raw candle bar:
    [timestamp, open, high, low, close, volume, open_interest]
    """
    if not isinstance(raw, (list, tuple)) or len(raw) < 5:
        raise ValueError(f"Invalid Upstox raw candle format: {raw}")

    return {
        "timestamp": raw[0],
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": int(raw[5]) if len(raw) > 5 else 0,
        "open_interest": int(raw[6]) if len(raw) > 6 else 0,
    }


def parse_iso_or_epoch_to_sec(ts_val: Any) -> int:
    """Normalize timestamp string or int/float to epoch seconds."""
    if isinstance(ts_val, (int, float)):
        return int(ts_val / 1000.0) if ts_val > 1e11 else int(ts_val)
    if isinstance(ts_val, str):
        try:
            val = float(ts_val)
            return int(val / 1000.0) if val > 1e11 else int(val)
        except ValueError:
            pass
        try:
            dt = datetime.datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception:
            pass
    return int(time.time())


def resample_1m_candles(
    candles_1m: List[Dict[str, Any]],
    target_interval: str,
) -> List[Dict[str, Any]]:
    """
    Client-side aggregation of 1m candles into 5m, 15m, 30m, 1h buckets.
    Aggregation rules:
    - open = first candle's open
    - high = max high across the bucket
    - low = min low across the bucket
    - close = last candle's close
    - volume = sum of volumes
    - open_interest = last candle's open_interest
    - timestamp = bucket boundary start timestamp
    """
    if not candles_1m:
        return []

    interval_key = target_interval.lower()
    if interval_key in ("1m", "1min", "1minute"):
        return candles_1m

    step_sec = SUPPORTED_RESAMPLE_INTERVALS.get(interval_key)
    if not step_sec:
        raise ValueError(
            f"Unsupported resampling interval '{target_interval}'. Supported: 5m, 15m, 30m, 1h"
        )

    # Ensure candles are in ascending order before grouping
    candles_sorted = sorted(candles_1m, key=lambda c: parse_iso_or_epoch_to_sec(c["timestamp"]))

    aggregated: List[Dict[str, Any]] = []
    current_bucket: Optional[int] = None
    chunk: List[Dict[str, Any]] = []

    for c in candles_sorted:
        sec = parse_iso_or_epoch_to_sec(c["timestamp"])
        bucket_start = (sec // step_sec) * step_sec

        if current_bucket is None:
            current_bucket = bucket_start

        if bucket_start == current_bucket:
            chunk.append(c)
        else:
            if chunk:
                ts_out = chunk[0]["timestamp"] if isinstance(chunk[0]["timestamp"], str) else current_bucket
                aggregated.append({
                    "timestamp": ts_out,
                    "time": current_bucket,
                    "open": float(chunk[0]["open"]),
                    "high": max(float(x["high"]) for x in chunk),
                    "low": min(float(x["low"]) for x in chunk),
                    "close": float(chunk[-1]["close"]),
                    "volume": sum(int(x.get("volume", 0)) for x in chunk),
                    "open_interest": int(chunk[-1].get("open_interest", chunk[-1].get("oi", 0))),
                })
            current_bucket = bucket_start
            chunk = [c]

    if chunk and current_bucket is not None:
        ts_out = chunk[0]["timestamp"] if isinstance(chunk[0]["timestamp"], str) else current_bucket
        aggregated.append({
            "timestamp": ts_out,
            "time": current_bucket,
            "open": float(chunk[0]["open"]),
            "high": max(float(x["high"]) for x in chunk),
            "low": min(float(x["low"]) for x in chunk),
            "close": float(chunk[-1]["close"]),
            "volume": sum(int(x.get("volume", 0)) for x in chunk),
            "open_interest": int(chunk[-1].get("open_interest", chunk[-1].get("oi", 0))),
        })

    return aggregated


class CandleAggregator:
    """
    Production Candle Aggregator for MCX Commodity Data.
    Fetches raw daily & intraday candles via Upstox API V2, reverses descending order
    to ascending chronological order, and resamples 1m intraday candles to 5m, 15m, 30m, 1h buckets.
    """

    def __init__(self, client: Optional[UpstoxRESTClient] = None):
        self._client = client

    async def fetch_daily_candles(
        self,
        instrument_key: str,
        to_date: str,
        from_date: str,
        client: Optional[UpstoxRESTClient] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches daily historical candles via /v2/historical-candle/{key}/day/{to_date}/{from_date}.
        Reverses Upstox descending order (newest first) to chronological ascending order.
        Extracts all 7 elements: [timestamp, open, high, low, close, volume, open_interest].
        """
        rest_client = client or self._client
        if not rest_client:
            raise ValueError("UpstoxRESTClient must be provided to fetch daily candles")

        key_encoded = urllib.parse.quote(instrument_key, safe="")
        endpoint = f"/v2/historical-candle/{key_encoded}/day/{to_date}/{from_date}"
        res = await rest_client._request("GET", endpoint)
        raw_candles = res.get("data", {}).get("candles", [])

        candles = []
        for c in reversed(raw_candles):
            candles.append(parse_upstox_candle(c))
        return candles

    async def fetch_intraday_candles(
        self,
        instrument_key: str,
        interval: str = "1minute",
        client: Optional[UpstoxRESTClient] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches active session intraday 1m candles via /v2/historical-candle/intraday/{key}/1minute.
        Reverses Upstox descending order to ascending order and resamples to multi-timeframe buckets.
        """
        rest_client = client or self._client
        if not rest_client:
            raise ValueError("UpstoxRESTClient must be provided to fetch intraday candles")

        key_encoded = urllib.parse.quote(instrument_key, safe="")
        # Always query 1minute stream from Upstox to guarantee reliable source data
        endpoint = f"/v2/historical-candle/intraday/{key_encoded}/1minute"
        res = await rest_client._request("GET", endpoint)
        raw_candles = res.get("data", {}).get("candles", [])

        candles_1m = []
        for c in reversed(raw_candles):
            candles_1m.append(parse_upstox_candle(c))

        if interval.lower() in ("1m", "1min", "1minute"):
            return candles_1m

        # Resample 1m candles client-side into target interval
        return resample_1m_candles(candles_1m, target_interval=interval)

    def resample(
        self,
        candles_1m: List[Dict[str, Any]],
        target_interval: str,
    ) -> List[Dict[str, Any]]:
        """Resample a series of 1m candles to the target interval (5m, 15m, 30m, 1h)."""
        return resample_1m_candles(candles_1m, target_interval=target_interval)


class MarketCandleAggregator:
    """
    Compatibility & Orchestration Layer for Candle Aggregation.
    Delegates real-time tick-to-candle streaming to CanonicalCandleAggregator engine
    and provides historical multi-timeframe resampling.
    """

    INTERVAL_SECONDS = CanonicalCandleAggregator.INTERVAL_SECONDS

    def __init__(self, max_history_per_interval: int = 500, enforce_market_hours: bool = True):
        self._canonical_aggregator = CanonicalCandleAggregator(
            max_history_per_interval=max_history_per_interval,
            enforce_market_hours=enforce_market_hours,
        )
        self._commodity_aggregator = CandleAggregator()

    @property
    def active_candles(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return self._canonical_aggregator.active_candles

    @property
    def completed_candles(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        return self._canonical_aggregator.completed_candles

    def seed_historical_candles(self, symbol: str, interval: str, candles: List[Dict[str, Any]]):
        """Seed completed historical candles into canonical aggregator buffer."""
        self._canonical_aggregator.seed_historical_candles(symbol, interval, candles)

    def process_tick(self, tick: NormalizedTick) -> Dict[str, Dict[str, Any]]:
        """Process incoming tick through canonical aggregator engine."""
        return self._canonical_aggregator.process_tick(tick)

    def get_history(self, symbol: str, interval: str = "5m", count: int = 60) -> List[Dict[str, Any]]:
        """Returns completed candles merged with current active candle from canonical engine."""
        return self._canonical_aggregator.get_history(symbol, timeframe=interval, limit=count)

    def resample(self, candles_1m: List[Dict[str, Any]], target_interval: str) -> List[Dict[str, Any]]:
        """Resample 1m candles into 5m/15m/30m/1h."""
        return self._commodity_aggregator.resample(candles_1m, target_interval=target_interval)
