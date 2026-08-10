import time
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MarketEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    symbol: str
    event_type: str
    severity: str = "INFO" # INFO, WARNING, CRITICAL
    evidence: str
    confidence: int = 80

class EventEngine:
    """
    Real-time Quantitative Event Detector Engine
    Evaluates streaming ticks and candles against market thresholds.
    """

    @staticmethod
    def detect_tick_events(symbol: str, current_price: float, prev_price: float, vwap: float, volume: int, avg_volume: int) -> List[MarketEvent]:
        events = []
        
        # 1. VWAP Crossover
        if prev_price < vwap and current_price >= vwap:
            events.append(MarketEvent(
                symbol=symbol,
                event_type="VWAP_CROSS_BULLISH",
                severity="INFO",
                evidence=f"Price crossed above VWAP line (₹{vwap:.2f}) to ₹{current_price:.2f}",
                confidence=85
            ))
        elif prev_price > vwap and current_price <= vwap:
            events.append(MarketEvent(
                symbol=symbol,
                event_type="VWAP_CROSS_BEARISH",
                severity="WARNING",
                evidence=f"Price broke below VWAP line (₹{vwap:.2f}) to ₹{current_price:.2f}",
                confidence=85
            ))

        # 2. Volume Surge Event
        if avg_volume > 0 and volume > (avg_volume * 2.5):
            events.append(MarketEvent(
                symbol=symbol,
                event_type="VOLUME_SPIKE",
                severity="WARNING",
                evidence=f"Volume surge detected ({volume} shares, {volume / avg_volume:.1f}x of 20-period average)",
                confidence=90
            ))

        return events
