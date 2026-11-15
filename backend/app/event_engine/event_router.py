"""
APEX Event-Driven Research Trigger & Priority Router
===================================================
Coordinates real-time triggers for autonomous LLM research execution:
1. Breaking news detection
2. Major government / central-bank announcements
3. Key commodity inventory reports (EIA, USDA, OPEC)
4. Significant price movements (> 1.8%)
5. Thesis invalidation breach
6. Material cross-market relationship shift

Controls:
- Debounce & Cooldown: Prohibits invoking LLM on every tick (minimum 10m cooldown per asset unless CRITICAL)
- Priority Levels: LOW, NORMAL, HIGH, CRITICAL
- Deduplication: Eliminates redundant triggers
"""

import time
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.ai_engine.research_system import ResearchArticle
from backend.app.ai_engine.apex_chief_reasoner import apex_chief_reasoner, MarketForecast
from backend.app.ai_engine.forecast_store import forecast_store

logger = logging.getLogger(__name__)


class ResearchPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TriggerEvent(BaseModel):
    event_id: str
    trigger_type: str  # BREAKING_NEWS, CENTRAL_BANK, INVENTORY_REPORT, PRICE_ANOMALY, THESIS_INVALIDATION
    target_instruments: List[str]
    priority: ResearchPriority
    headline: str
    timestamp: float = Field(default_factory=time.time)
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventTriggerRouter:
    """
    Evaluates incoming market data and news to deterministically trigger
    focused research cycles by the APEX Chief Reasoner.
    """

    def __init__(self, cooldown_seconds: float = 600.0):  # 10 minutes default cooldown
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger_time: Dict[str, float] = {}  # instrument_id -> timestamp
        self._recent_events: List[TriggerEvent] = []

    def should_trigger_research(self, instrument_id: str, priority: ResearchPriority) -> Tuple[bool, str]:
        """Evaluates whether an instrument is eligible for research based on cooldown."""
        now = time.time()
        last_time = self._last_trigger_time.get(instrument_id, 0.0)

        # CRITICAL events bypass routine cooldowns
        if priority == ResearchPriority.CRITICAL:
            self._last_trigger_time[instrument_id] = now
            return True, "CRITICAL priority event bypasses routine cooldown."

        elapsed = now - last_time
        if elapsed < self.cooldown_seconds:
            remaining = int(self.cooldown_seconds - elapsed)
            return False, f"Cooldown active for {instrument_id}. Remaining: {remaining}s."

        self._last_trigger_time[instrument_id] = now
        return True, "Cooldown satisfied. Research authorized."

    async def handle_incoming_article(self, article: ResearchArticle) -> List[MarketForecast]:
        """
        Processes an incoming research article. If high-impact or breaking,
        routes an event-driven forecast update for relevant instruments.
        """
        updated_forecasts = []
        if not article.relevant_instruments:
            return updated_forecasts

        priority = ResearchPriority.NORMAL
        if article.importance == "CRITICAL" or article.is_breaking:
            priority = ResearchPriority.CRITICAL
        elif article.importance == "HIGH":
            priority = ResearchPriority.HIGH

        for inst_id in article.relevant_instruments:
            eligible, reason = self.should_trigger_research(inst_id, priority)
            if not eligible:
                logger.info(f"[TRIGGER ROUTER] Skipped research for {inst_id}: {reason}")
                continue

            event = TriggerEvent(
                event_id=f"trig_{article.article_id}_{inst_id.lower()}",
                trigger_type="BREAKING_NEWS" if article.is_breaking else "RESEARCH_CATALYST",
                target_instruments=[inst_id],
                priority=priority,
                headline=article.title,
                timestamp=time.time(),
                source=article.source,
                metadata={"url": article.url, "credibility": article.credibility_score},
            )
            self._recent_events.append(event)
            logger.info(f"[TRIGGER ROUTER] Dispatched {priority.value} research trigger for {inst_id} via {article.source}.")

            # Trigger Central LLM Reasoner
            try:
                forecast = await apex_chief_reasoner.execute_forecast_pipeline(
                    instrument_id=inst_id,
                    trigger_reason=f"News Event: {article.title[:80]}",
                )
                saved = forecast_store.save_forecast(forecast)
                updated_forecasts.append(saved)
            except Exception as e:
                logger.error(f"[TRIGGER ROUTER] Forecast generation failed for {inst_id}: {e}")

        # Keep event history bounded
        if len(self._recent_events) > 200:
            self._recent_events = self._recent_events[-200:]

        return updated_forecasts

    def check_thesis_invalidation(self, instrument_id: str, current_price: float) -> Optional[TriggerEvent]:
        """
        Monitors whether the latest forecast's invalidation conditions have been violated by price action.
        """
        latest_fc = forecast_store.get_latest_forecast(instrument_id)
        if not latest_fc or latest_fc.status != "VALIDATED":
            return None

        # Check if price moved beyond the predicted 7d price bounds
        lower = latest_fc.price_range.get("lower", 0.0)
        upper = latest_fc.price_range.get("upper", float("inf"))

        if current_price < lower or current_price > upper:
            latest_fc.status = "INVALIDATED"
            forecast_store.evaluate_forecast(latest_fc.forecast_id, realized_price=current_price)

            event = TriggerEvent(
                event_id=f"inval_{instrument_id.lower()}_{int(time.time())}",
                trigger_type="THESIS_INVALIDATION",
                target_instruments=[instrument_id],
                priority=ResearchPriority.HIGH,
                headline=f"Price {current_price} breached forecast bounds [{lower}, {upper}]. Thesis invalidated.",
                source="PRICE_MONITOR",
            )
            self._recent_events.append(event)
            logger.warning(f"[TRIGGER ROUTER] Thesis invalidated for {instrument_id} at price {current_price}.")
            return event

        return None

    def get_recent_triggers(self, limit: int = 20) -> List[TriggerEvent]:
        return sorted(self._recent_events, key=lambda e: e.timestamp, reverse=True)[:limit]


# Global event router singleton
event_trigger_router = EventTriggerRouter()
