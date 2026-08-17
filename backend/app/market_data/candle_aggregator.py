import logging
from typing import Dict, List, Any, Optional
from backend.app.broker_providers.base import NormalizedTick
from backend.app.candle_engine.aggregator import CandleAggregator

logger = logging.getLogger(__name__)

class MarketCandleAggregator:
    """
    Compatibility & Orchestration Layer for Candle Aggregation.
    Delegates all OHLCV and VWAP aggregation directly to canonical CandleAggregator engine.
    """

    INTERVAL_SECONDS = CandleAggregator.INTERVAL_SECONDS

    def __init__(self, max_history_per_interval: int = 500):
        self._canonical_aggregator = CandleAggregator(max_history_per_interval=max_history_per_interval)

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
