import datetime
from typing import Dict, List, Optional
from backend.app.market_data.corporate_actions.models import (
    CorporateActionEvent,
    CorporateActionType,
)

def _date_to_epoch_start(date_str: str) -> float:
    """Convert YYYY-MM-DD string to epoch timestamp at 00:00:00 UTC."""
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0

class CorporateActionRegistry:
    """
    Central, generic registry of verified Corporate Action Events for NSE/BSE securities.
    Calculates point-in-time cumulative adjustment factors for historical price continuity.
    """

    def __init__(self):
        self._events: Dict[str, List[CorporateActionEvent]] = {}
        self._seed_known_corporate_actions()

    def _seed_known_corporate_actions(self):
        """Seed known historical corporate actions for NSE instruments."""
        # 1. HDFC Bank 1:1 Bonus (Ex-Date: 2025-08-26, 1 bonus share for every 1 share held -> factor = 2.0)
        self.register_action(
            CorporateActionEvent(
                symbol="HDFCBANK.NS",
                exchange="NSE",
                action_type=CorporateActionType.BONUS,
                announcement_date="2025-07-20",
                ex_date="2025-08-26",
                record_date="2025-08-27",
                ratio_before=1.0,
                ratio_after=1.0,
                adjustment_factor=2.0,
                source="NSE_CORPORATE_FILING",
                source_timestamp=1755648000.0,
                effective_timestamp=_date_to_epoch_start("2025-08-26"),
                status="COMPLETED",
            )
        )
        self.register_action(
            CorporateActionEvent(
                symbol="HDFCBANK",
                exchange="NSE",
                action_type=CorporateActionType.BONUS,
                announcement_date="2025-07-20",
                ex_date="2025-08-26",
                record_date="2025-08-27",
                ratio_before=1.0,
                ratio_after=1.0,
                adjustment_factor=2.0,
                source="NSE_CORPORATE_FILING",
                source_timestamp=1755648000.0,
                effective_timestamp=_date_to_epoch_start("2025-08-26"),
                status="COMPLETED",
            )
        )

    def register_action(self, event: CorporateActionEvent):
        """Register a generic corporate action event."""
        sym = event.symbol.upper()
        if sym not in self._events:
            self._events[sym] = []
        # Check if already registered to avoid duplicates
        existing = [e for e in self._events[sym] if e.ex_date == event.ex_date and e.action_type == event.action_type]
        if not existing:
            self._events[sym].append(event)
            # Keep sorted by effective_timestamp ascending
            self._events[sym].sort(key=lambda x: x.effective_timestamp)

    def get_actions(self, symbol: str) -> List[CorporateActionEvent]:
        """Return all corporate action events for a symbol."""
        sym = symbol.upper()
        return list(self._events.get(sym, []))

    def get_cumulative_factor(
        self,
        symbol: str,
        candle_timestamp: float,
        target_timestamp: Optional[float] = None
    ) -> float:
        """
        Calculate cumulative price divisor for historical data at candle_timestamp.
        If candle_timestamp is BEFORE an ex-date, price must be divided by the event's adjustment_factor.
        If candle_timestamp is AFTER the ex-date, the price is already in the post-action denomination (factor = 1.0).
        """
        actions = self.get_actions(symbol)
        if not actions:
            return 1.0

        cumulative_factor = 1.0
        ref_time = target_timestamp or datetime.datetime.now(datetime.timezone.utc).timestamp()

        for act in actions:
            # If the historical candle was generated BEFORE the corporate action became effective,
            # and the current reference time is AFTER the corporate action, apply the factor.
            if candle_timestamp < act.effective_timestamp <= ref_time:
                cumulative_factor *= act.adjustment_factor

        return cumulative_factor

# Global instance
corporate_action_registry = CorporateActionRegistry()
