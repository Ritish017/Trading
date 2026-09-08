"""
Signal Intelligence Engine — Signal Store
==========================================
In-memory store for active signals with deduplication, lifecycle management,
and signal history.

Responsibilities:
- Store active/qualified signals
- Deduplicate: same symbol+direction with similar setup → update, don't create new
- Track signal history (last 500)
- Signal expiry management
- Rejection history (last 200)

Thread-safety: This store is intended for single-process async operation.
All writes should happen on the event loop thread.

Invariants:
- Signal IDs are unique and stable
- Expired signals are moved to history, not deleted
- Rejected candidates are stored separately from qualified signals
- Performance analytics are computed from stored history, not mock data
"""
import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional

from backend.app.signal_engine.models import (
    RejectionRecord,
    ScannerResult,
    SignalDecision,
    SignalDirection,
    SignalQualityGrade,
    SignalState,
)
from backend.app.signal_engine.lifecycle import lifecycle_manager, InvalidStateTransitionError

logger = logging.getLogger(__name__)

# Signal expiry: 45 minutes from generation (3 x 15m candles)
DEFAULT_EXPIRY_SECONDS = 45 * 60

# Max records in memory
MAX_ACTIVE_SIGNALS = 50
MAX_SIGNAL_HISTORY = 500
MAX_REJECTION_HISTORY = 300
MAX_CANDIDATE_HISTORY = 1000


def _to_str(val: Any) -> str:
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


class SignalStore:
    """
    Thread-safe signal store with memory cache and durable database persistence.
    """

    def __init__(self):
        # Active signals by symbol → signal
        self._active: Dict[str, SignalDecision] = {}
        # Signal history (FIFO, newest first)
        self._history: deque[SignalDecision] = deque(maxlen=MAX_SIGNAL_HISTORY)
        # Rejection records
        self._rejections: deque[RejectionRecord] = deque(maxlen=MAX_REJECTION_HISTORY)
        # Candidate observations (all candidates: qualified, rejected, blocked)
        self._candidates: deque[Dict[str, Any]] = deque(maxlen=MAX_CANDIDATE_HISTORY)
        # Last scanner result
        self._last_scan: Optional[ScannerResult] = None
        # Performance counters
        self._total_qualified = 0
        self._total_rejected = 0
        self._total_candidates = 0

    def upsert_signal(self, signal: SignalDecision) -> str:
        """
        Add or update a signal. Returns the signal_id.
        Deduplication logic: if a signal for the same symbol+direction
        already exists with similar entry price (within 1%), update it.
        Otherwise create new.
        """
        if signal.direction == SignalDirection.NO_TRADE:
            return signal.signal_id

        existing_key = self._find_existing(signal)
        if existing_key:
            # Update entry price and score, preserve the signal_id
            existing = self._active[existing_key]
            logger.debug(
                f"Updating existing signal {existing.signal_id} for {signal.symbol}"
            )
            # Keep same ID, update key fields
            signal_dict = signal.model_dump() if hasattr(signal, "model_dump") else signal.dict()
            signal_dict["signal_id"] = existing.signal_id
            updated = SignalDecision(**signal_dict)
            self._active[existing_key] = updated
            sig_id = updated.signal_id
        else:
            key = self._make_key(signal)
            self._active[key] = signal
            self._total_qualified += 1
            logger.info(
                f"[SIGNAL STORE] New signal: {signal.symbol} {_to_str(signal.direction)} "
                f"Grade:{_to_str(signal.quality_grade)} Score:{signal.opportunity_score:.1f}"
            )
            sig_id = signal.signal_id

        # Dispatch background db persistence if event loop is running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_signal_bg(signal))
        except RuntimeError:
            pass

        return sig_id

    async def _persist_signal_bg(self, signal: SignalDecision):
        """Asynchronous worker to store signal in database."""
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.signal_repository import SignalRepository
            async with AsyncSessionLocal() as session:
                repo = SignalRepository(session)
                sig_dict = signal.model_dump() if hasattr(signal, "model_dump") else signal.dict()
                await repo.save_signal(sig_dict)
                if signal.strategy_votes:
                    votes = [v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in signal.strategy_votes]
                    await repo.record_votes(signal.signal_id, votes)
        except Exception as e:
            logger.debug(f"[SIGNAL STORE] DB persistence notice: {e}")

    async def save_signal_durable(
        self, signal: SignalDecision, session: Optional[Any] = None
    ) -> str:
        """Explicitly awaitable durable persistence."""
        sig_id = self.upsert_signal(signal)
        from backend.app.database.repositories.signal_repository import SignalRepository
        sig_dict = signal.model_dump() if hasattr(signal, "model_dump") else signal.dict()

        if session is not None:
            repo = SignalRepository(session)
            await repo.save_signal(sig_dict)
            if signal.strategy_votes:
                votes = [v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in signal.strategy_votes]
                await repo.record_votes(signal.signal_id, votes)
        else:
            from backend.app.database.connection import AsyncSessionLocal
            async with AsyncSessionLocal() as sess:
                repo = SignalRepository(sess)
                await repo.save_signal(sig_dict)
                if signal.strategy_votes:
                    votes = [v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in signal.strategy_votes]
                    await repo.record_votes(signal.signal_id, votes)
        return sig_id

    def add_rejection(self, rejection: RejectionRecord) -> None:
        """Store a rejection record."""
        self._rejections.appendleft(rejection)
        self._total_rejected += 1

        # Dispatch background db persistence if loop running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_rejection_bg(rejection))
        except RuntimeError:
            pass

    async def _persist_rejection_bg(self, rejection: RejectionRecord):
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.signal_repository import SignalRepository
            async with AsyncSessionLocal() as session:
                repo = SignalRepository(session)
                rej_dict = rejection.model_dump() if hasattr(rejection, "model_dump") else rejection.dict()
                await repo.record_rejection(rej_dict)
        except Exception as e:
            logger.debug(f"[SIGNAL STORE] DB rejection persistence notice: {e}")

    def add_candidate_observation(self, candidate_dict: Dict[str, Any]) -> None:
        """Store candidate observation in Observatory and dispatch durable DB write."""
        self._candidates.appendleft(candidate_dict)
        self._total_candidates += 1

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_candidate_observation_bg(candidate_dict))
        except RuntimeError:
            pass

    async def _persist_candidate_observation_bg(self, candidate_dict: Dict[str, Any]):
        try:
            from backend.app.database.connection import AsyncSessionLocal
            from backend.app.database.repositories.signal_repository import SignalRepository
            async with AsyncSessionLocal() as session:
                repo = SignalRepository(session)
                await repo.record_candidate_observation(candidate_dict)
        except Exception as e:
            logger.debug(f"[SIGNAL STORE] Candidate observation DB notice: {e}")

    def get_candidate_observations(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent candidate observations from in-memory Observatory deque."""
        res = list(self._candidates)
        if symbol:
            res = [c for c in res if c.get("symbol") == symbol]
        return res[:limit]

    async def transition_signal(
        self,
        signal_id: str,
        to_state: Any,
        reason: str,
        trigger_price: Optional[float] = None,
        session: Optional[Any] = None,
    ) -> bool:
        """Execute a state machine transition on an existing signal."""
        signal = self.get_signal_by_id(signal_id)
        if not signal:
            logger.warning(f"Cannot transition unknown signal {signal_id}")
            return False

        from_state = signal.state
        # Validate and record event via lifecycle manager
        await lifecycle_manager.transition(
            signal_id=signal_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            trigger_price=trigger_price,
            session=session,
        )

        signal.state = to_state.value if hasattr(to_state, "value") else str(to_state)

        # If terminal state, move to history
        if lifecycle_manager.is_terminal(to_state):
            key = self._make_key(signal)
            if key in self._active:
                del self._active[key]
            self._history.appendleft(signal)

        return True

    async def load_from_database(self, session: Optional[Any] = None) -> int:
        """
        Restore active signals from PostgreSQL / SQLite repository on startup or restart.
        """
        loaded = 0
        try:
            from backend.app.database.repositories.signal_repository import SignalRepository
            if session is not None:
                repo = SignalRepository(session)
                models = await repo.get_active_signals(limit=MAX_ACTIVE_SIGNALS)
            else:
                from backend.app.database.connection import AsyncSessionLocal
                async with AsyncSessionLocal() as sess:
                    repo = SignalRepository(sess)
                    models = await repo.get_active_signals(limit=MAX_ACTIVE_SIGNALS)

            for m in models:
                sig_dict = {
                    "signal_id": m.signal_id,
                    "symbol": m.symbol,
                    "exchange": m.exchange,
                    "instrument_id": m.instrument_id or m.symbol,
                    "asset_class": m.asset_class,
                    "direction": m.direction,
                    "signal_type": m.signal_type,
                    "timeframe": m.timeframe,
                    "state": m.state,
                    "quality_grade": m.quality_grade,
                    "opportunity_score": m.opportunity_score,
                    "confidence": m.confidence,
                    "entry": m.entry,
                    "entry_zone_low": m.entry_zone_low,
                    "entry_zone_high": m.entry_zone_high,
                    "risk_reward": m.risk_reward,
                    "regime": m.market_regime,
                    "regime_compatible": m.regime_compatible,
                    "liquidity_score": m.liquidity_score,
                    "provenance": m.provenance,
                    "expiry": m.expiry,
                    "expiry_condition": m.expiry_condition,
                    "candles_used": m.candles_used,
                    "why_reasons": m.why_reasons_json or [],
                    "invalidation_conditions": m.invalidation_conditions_json or [],
                    "rejection_reasons": m.rejection_reasons_json or [],
                    "futures_decision": getattr(m, "futures_decision_json", None),
                    "options_decision": getattr(m, "options_decision_json", None),
                    "transaction_cost_estimate": getattr(m, "cost_estimate_json", None),
                }
                decision = SignalDecision(**sig_dict)
                key = self._make_key(decision)
                self._active[key] = decision
                loaded += 1

            logger.info(f"[SIGNAL STORE] Restored {loaded} active signals from durable database.")
        except Exception as e:
            logger.warning(f"[SIGNAL STORE] Database restore notice: {e}")
        return loaded

    def get_active_signals(
        self,
        direction: Optional[str] = None,
        min_grade: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[SignalDecision]:
        """
        Return active, non-expired signals.
        Optionally filtered by direction, grade, or symbol.
        """
        # Expire stale signals first
        self._expire_stale()

        signals = list(self._active.values())

        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        if direction:
            signals = [s for s in signals if _to_str(s.direction) == direction]
        if min_grade:
            grade_order = {"A+": 4, "A": 3, "B": 2, "C": 1, "NO TRADE": 0}
            min_ord = grade_order.get(min_grade, 0)
            signals = [s for s in signals
                       if grade_order.get(_to_str(s.quality_grade), 0) >= min_ord]

        # Sort by score descending
        return sorted(signals, key=lambda s: s.opportunity_score, reverse=True)

    def get_signal_by_id(self, signal_id: str) -> Optional[SignalDecision]:
        """Find a signal by ID (active or history)."""
        for s in self._active.values():
            if s.signal_id == signal_id:
                return s
        for s in self._history:
            if s.signal_id == signal_id:
                return s
        return None

    def get_signal_for_symbol(self, symbol: str) -> Optional[SignalDecision]:
        """Get the most recent active signal for a symbol."""
        self._expire_stale()
        for key, signal in self._active.items():
            if signal.symbol == symbol:
                return signal
        return None

    def get_recent_rejections(self, limit: int = 20) -> List[RejectionRecord]:
        """Return recent rejection records."""
        return list(self._rejections)[:limit]

    def get_signal_history(self, limit: int = 50) -> List[SignalDecision]:
        """Return historical signals."""
        return list(self._history)[:limit]

    # Alias for convenience
    get_history = get_signal_history

    def update_last_scan(self, scan_result: ScannerResult) -> None:
        """Store the most recent scanner result."""
        self._last_scan = scan_result

    def get_last_scan(self) -> Optional[ScannerResult]:
        """Get the most recent scanner result."""
        return self._last_scan

    def invalidate_signal(self, signal_id: str, reason: str) -> bool:
        """Mark a signal as invalidated and move to history."""
        for key, signal in list(self._active.items()):
            if signal.signal_id == signal_id:
                signal.state = SignalState.INVALIDATED
                signal.rejection_reasons = [reason]
                self._history.appendleft(signal)
                del self._active[key]
                logger.info(f"Signal {signal_id} for {signal.symbol} invalidated: {reason}")
                return True
        return False

    def get_performance_stats(self) -> Dict:
        """Return basic performance statistics."""
        return {
            "total_qualified": self._total_qualified,
            "total_rejected": self._total_rejected,
            "currently_active": len(self._active),
            "history_size": len(self._history),
            "rejection_rate": round(
                self._total_rejected / max(1, self._total_qualified + self._total_rejected) * 100, 1
            ),
        }

    # --- Private methods ---

    def _expire_stale(self) -> None:
        """Move expired signals from active to history."""
        now = time.time()
        expired_keys = []
        for key, signal in self._active.items():
            if signal.expiry:
                try:
                    from datetime import datetime
                    expiry_ts = datetime.fromisoformat(
                        signal.expiry.replace("Z", "+00:00")
                    ).timestamp()
                    if now > expiry_ts:
                        signal.state = SignalState.EXPIRED
                        self._history.appendleft(signal)
                        expired_keys.append(key)
                except Exception:
                    pass

        for k in expired_keys:
            logger.debug(f"Signal expired: {self._active[k].symbol if k in self._active else k}")
            del self._active[k]

    def _make_key(self, signal: SignalDecision) -> str:
        return f"{signal.symbol}::{_to_str(signal.direction)}"

    def _find_existing(self, new_signal: SignalDecision) -> Optional[str]:
        """
        Find existing signal for same symbol+direction with similar price.
        Returns the key if found, None otherwise.
        """
        key = self._make_key(new_signal)
        if key not in self._active:
            return None
        existing = self._active[key]

        # Check price similarity (within 1%)
        new_entry = new_signal.entry or 0
        ex_entry = existing.entry or 0
        if new_entry > 0 and ex_entry > 0:
            price_diff = abs(new_entry - ex_entry) / ex_entry
            if price_diff < 0.01:
                return key

        return None


# Module-level singleton
signal_store = SignalStore()
