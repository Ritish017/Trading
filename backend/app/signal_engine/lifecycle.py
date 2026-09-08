"""
Signal Intelligence Engine — Signal Lifecycle State Machine
=============================================================
Strict, deterministic lifecycle management for trading opportunities.

State Machine Flow:
  CANDIDATE
    │
    ▼
  ANALYZING
    │
    ▼
  VALIDATING
    │
    ▼
  QUALIFIED ───► EXPIRED / INVALIDATED / CANCELLED
    │
    ▼
  TRIGGERED ───► EXPIRED / CANCELLED
    │
    ▼
  ACTIVE
    │
    ├─► TARGET_1 ─► TARGET_2 ─► TARGET_3 (Terminal Success)
    │
    ├─► STOPPED (Terminal Loss)
    ├─► EXPIRED (Time Expiry)
    └─► CANCELLED (User / Circuit Breaker)

Invariants:
- Every state transition must be valid according to the transition matrix.
- Illegal transitions immediately raise InvalidStateTransitionError.
- Terminal states (TARGET_3, STOPPED, EXPIRED, INVALIDATED, REJECTED, CANCELLED) cannot be exited.
- All transitions produce an immutable, timestamped event record.
- Persisted to PostgreSQL / SQLite via SignalEventModel when session available.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Set

from backend.app.signal_engine.models import SignalState

logger = logging.getLogger(__name__)


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        msg = f"Invalid signal lifecycle transition: '{from_state}' -> '{to_state}'"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.from_state = from_state
        self.to_state = to_state


# State transition rules: Map of from_state -> set of legal to_states
VALID_TRANSITIONS: Dict[SignalState, Set[SignalState]] = {
    SignalState.CANDIDATE: {
        SignalState.ANALYZING,
        SignalState.REJECTED,
        SignalState.CANCELLED,
    },
    SignalState.ANALYZING: {
        SignalState.VALIDATING,
        SignalState.REJECTED,
        SignalState.CANCELLED,
    },
    SignalState.VALIDATING: {
        SignalState.QUALIFIED,
        SignalState.REJECTED,
        SignalState.CANCELLED,
    },
    SignalState.QUALIFIED: {
        SignalState.TRIGGERED,
        SignalState.EXPIRED,
        SignalState.INVALIDATED,
        SignalState.CANCELLED,
    },
    SignalState.TRIGGERED: {
        SignalState.ACTIVE,
        SignalState.EXPIRED,
        SignalState.CANCELLED,
    },
    SignalState.ACTIVE: {
        SignalState.TARGET_1,
        SignalState.TARGET_REACHED,
        SignalState.STOPPED,
        SignalState.EXPIRED,
        SignalState.CANCELLED,
    },
    SignalState.TARGET_1: {
        SignalState.TARGET_2,
        SignalState.TARGET_REACHED,
        SignalState.STOPPED,
        SignalState.EXPIRED,
        SignalState.CANCELLED,
    },
    SignalState.TARGET_2: {
        SignalState.TARGET_3,
        SignalState.TARGET_REACHED,
        SignalState.STOPPED,
        SignalState.EXPIRED,
        SignalState.CANCELLED,
    },
    # Terminal states
    SignalState.TARGET_3: set(),
    SignalState.TARGET_REACHED: set(),
    SignalState.STOPPED: set(),
    SignalState.EXPIRED: set(),
    SignalState.INVALIDATED: set(),
    SignalState.REJECTED: set(),
    SignalState.CANCELLED: set(),
}

TERMINAL_STATES: Set[SignalState] = {
    SignalState.TARGET_3,
    SignalState.TARGET_REACHED,
    SignalState.STOPPED,
    SignalState.EXPIRED,
    SignalState.INVALIDATED,
    SignalState.REJECTED,
    SignalState.CANCELLED,
}


def _to_enum(val: Any) -> SignalState:
    if isinstance(val, SignalState):
        return val
    try:
        return SignalState(str(val))
    except ValueError:
        raise ValueError(f"Unknown signal state: {val}")


class SignalLifecycleManager:
    """
    Manages deterministic signal lifecycle state transitions and audit logging.
    """

    def __init__(self):
        self._in_memory_events: Dict[str, List[Dict[str, Any]]] = {}

    def can_transition(self, from_state: Any, to_state: Any) -> bool:
        """Check if transition from `from_state` to `to_state` is legal."""
        try:
            f_enum = _to_enum(from_state)
            t_enum = _to_enum(to_state)
            return t_enum in VALID_TRANSITIONS.get(f_enum, set())
        except ValueError:
            return False

    def is_terminal(self, state: Any) -> bool:
        """Check if a state is terminal."""
        try:
            s_enum = _to_enum(state)
            return s_enum in TERMINAL_STATES
        except ValueError:
            return False

    def get_allowed_transitions(self, from_state: Any) -> List[str]:
        """Return list of legal next states from given state."""
        try:
            f_enum = _to_enum(from_state)
            return [s.value for s in VALID_TRANSITIONS.get(f_enum, set())]
        except ValueError:
            return []

    async def transition(
        self,
        signal_id: str,
        from_state: Any,
        to_state: Any,
        reason: str,
        trigger_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a state transition with validation and audit logging.

        Args:
            signal_id: Unique signal identifier
            from_state: Current state
            to_state: Requested next state
            reason: Mandatory human/system explanation for transition
            trigger_price: Price that triggered the transition (if market event)
            metadata: Additional contextual details
            session: Optional AsyncSession for durable database write

        Returns:
            Dictionary representing the created audit event.

        Raises:
            InvalidStateTransitionError: If the transition violates state machine rules.
        """
        f_enum = _to_enum(from_state)
        t_enum = _to_enum(to_state)

        if t_enum not in VALID_TRANSITIONS.get(f_enum, set()):
            allowed = [s.value for s in VALID_TRANSITIONS.get(f_enum, set())]
            raise InvalidStateTransitionError(
                from_state=f_enum.value,
                to_state=t_enum.value,
                reason=f"Allowed transitions from '{f_enum.value}': {allowed or 'NONE (terminal)'}",
            )

        event = {
            "signal_id": signal_id,
            "from_state": f_enum.value,
            "to_state": t_enum.value,
            "transition_reason": reason,
            "trigger_price": trigger_price,
            "event_timestamp": time.time(),
            "event_metadata": metadata or {},
        }

        # Track in memory
        if signal_id not in self._in_memory_events:
            self._in_memory_events[signal_id] = []
        self._in_memory_events[signal_id].append(event)

        logger.info(
            f"[LIFECYCLE] Signal {signal_id}: {f_enum.value} -> {t_enum.value} | Reason: {reason}"
        )

        # Persist to database if session provided
        if session is not None:
            try:
                from backend.app.database.repositories.signal_repository import SignalRepository
                repo = SignalRepository(session)
                await repo.record_event(
                    signal_id=signal_id,
                    from_state=f_enum.value,
                    to_state=t_enum.value,
                    reason=reason,
                    trigger_price=trigger_price,
                    metadata=metadata,
                )
            except Exception as e:
                logger.error(f"Failed to persist lifecycle event to DB for {signal_id}: {e}")

        return event

    def get_events(self, signal_id: str) -> List[Dict[str, Any]]:
        """Get in-memory audit trail of events for a signal."""
        return list(self._in_memory_events.get(signal_id, []))


# Global singleton
lifecycle_manager = SignalLifecycleManager()
