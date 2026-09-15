"""
APEX Session Lifecycle & Provenance State Machine
=================================================
Defines the authoritative state machine for Indian Equities and F&O trading sessions:
1. Distinction between Worker Process Lifecycle and Trading Session Lifecycle.
2. Authoritative NSE Session Windows (Premarket, Regular Market, Equity Close, F&O Finalization, Finalized).
3. Explicit Data Provenance taxonomy.
4. Structured Anomaly definitions for quantitative audit trails.
"""

from enum import Enum
import datetime
from typing import Optional, Dict, Any, Tuple


class MarketPhase(str, Enum):
    """
    Authoritative Indian Exchange (NSE) Market Phases.
    """
    PREMARKET = "PREMARKET"                   # Before 09:15 IST (system ready, warmup, no intraday execution)
    MARKET_OPEN = "MARKET_OPEN"               # 09:15 IST transition
    REGULAR_MARKET = "REGULAR_MARKET"         # 09:15–15:30 IST (continuous trading & paper execution)
    EQUITY_CLOSE = "EQUITY_CLOSE"             # 15:30 IST (equity close, intraday squaring, no new entries)
    FNO_FINALIZATION = "FNO_FINALIZATION"     # 15:30–15:40 IST (F&O settlement & reconciliation)
    FINALIZED = "FINALIZED"                   # 15:40+ IST (terminal state: certified report & SHA-256 seal)


class WorkerState(str, Enum):
    """
    Worker Process Lifecycle states (independent of the single trading day session).
    """
    STARTING = "STARTING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class DataProvenance(str, Enum):
    """
    Strict Data Lineage and Provenance Classification.
    Never mislabel historical/bootstrap data as AUTHENTIC_LIVE.
    """
    AUTHENTIC_LIVE = "AUTHENTIC_LIVE"                 # Live tick received via WebSocket during active market
    AUTHENTIC_HISTORICAL = "AUTHENTIC_HISTORICAL"     # Authentically fetched from Upstox REST historical API
    BOOTSTRAP_HISTORICAL = "BOOTSTRAP_HISTORICAL"     # Historical bars used exclusively for indicator warmup
    REPLAY = "REPLAY"                                 # Simulated historical replay feed
    PAPER_SIMULATED = "PAPER_SIMULATED"               # Synthetic / mock simulation
    DERIVED = "DERIVED"                               # Computed technical indicators, regimes, candles
    UNKNOWN = "UNKNOWN"                               # Unverified source
    NOT_VERIFIABLE = "NOT_VERIFIABLE"                 # Source cannot be independently corroborated


class SessionAnomalyType(str, Enum):
    """
    Structured quantitative audit anomaly types.
    """
    SESSION_DUPLICATE = "SESSION_DUPLICATE"
    SEQUENCE_RESET = "SEQUENCE_RESET"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    TIMESTAMP_REGRESSION = "TIMESTAMP_REGRESSION"
    TIMESTAMP_FUTURE = "TIMESTAMP_FUTURE"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    LIVE_DATA_OUTSIDE_SESSION = "LIVE_DATA_OUTSIDE_SESSION"
    HISTORICAL_DATA_MARKED_LIVE = "HISTORICAL_DATA_MARKED_LIVE"
    DUPLICATE_FINALIZATION = "DUPLICATE_FINALIZATION"
    CHECKPOINT_DUPLICATE = "CHECKPOINT_DUPLICATE"
    DATABASE_SEQUENCE_CONFLICT = "DATABASE_SEQUENCE_CONFLICT"
    WORKER_RECOVERY = "WORKER_RECOVERY"


class SessionLifecycleManager:
    """
    Manages deterministic phase transitions and trading permissions for a given trading day.
    Indian Standard Time (IST = UTC + 5:30) is the exchange clock.
    """

    IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
    IST_TZ = datetime.timezone(IST_OFFSET)

    PREMARKET_START = datetime.time(0, 0)
    MARKET_OPEN_TIME = datetime.time(9, 15)
    EQUITY_CLOSE_TIME = datetime.time(15, 30)
    FNO_CLOSE_TIME = datetime.time(15, 40)

    @classmethod
    def get_ist_now(cls) -> datetime.datetime:
        """Returns current time in Indian Standard Time."""
        return datetime.datetime.now(cls.IST_TZ)

    @classmethod
    def determine_market_phase(cls, dt_ist: Optional[datetime.datetime] = None) -> MarketPhase:
        """
        Determines the authoritative market phase based on IST clock:
        - 00:00 to 09:15 IST -> PREMARKET
        - 09:15 to 15:30 IST -> REGULAR_MARKET
        - 15:30 to 15:40 IST -> FNO_FINALIZATION
        - 15:40 to 23:59 IST -> FINALIZED (if session close executed)
        """
        now = dt_ist or cls.get_ist_now()
        t = now.time()

        if t < cls.MARKET_OPEN_TIME:
            return MarketPhase.PREMARKET
        elif t < cls.EQUITY_CLOSE_TIME:
            return MarketPhase.REGULAR_MARKET
        elif t < cls.FNO_CLOSE_TIME:
            return MarketPhase.FNO_FINALIZATION
        else:
            return MarketPhase.FINALIZED

    @classmethod
    def get_market_phase(cls, dt_ist: Optional[datetime.datetime] = None) -> MarketPhase:
        """Alias for determine_market_phase."""
        return cls.determine_market_phase(dt_ist)

    @classmethod
    def is_intraday_order_allowed(cls, phase: MarketPhase) -> bool:
        """
        Hard guard: New paper intraday orders are ONLY permitted during REGULAR_MARKET.
        Blocked in PREMARKET, EQUITY_CLOSE, FNO_FINALIZATION, and FINALIZED.
        """
        return phase == MarketPhase.REGULAR_MARKET

    @classmethod
    def is_valid_phase_transition(cls, current: MarketPhase, next_phase: MarketPhase) -> bool:
        """
        Validates forward progression of market phases.
        Transitions must be monotonic: PREMARKET -> MARKET_OPEN -> REGULAR_MARKET -> EQUITY_CLOSE -> FNO_FINALIZATION -> FINALIZED.
        """
        if current == next_phase:
            return True
        
        allowed_transitions = {
            MarketPhase.PREMARKET: [MarketPhase.MARKET_OPEN, MarketPhase.REGULAR_MARKET, MarketPhase.FINALIZED],
            MarketPhase.MARKET_OPEN: [MarketPhase.REGULAR_MARKET, MarketPhase.EQUITY_CLOSE, MarketPhase.FINALIZED],
            MarketPhase.REGULAR_MARKET: [MarketPhase.EQUITY_CLOSE, MarketPhase.FNO_FINALIZATION, MarketPhase.FINALIZED],
            MarketPhase.EQUITY_CLOSE: [MarketPhase.FNO_FINALIZATION, MarketPhase.FINALIZED],
            MarketPhase.FNO_FINALIZATION: [MarketPhase.FINALIZED],
            MarketPhase.FINALIZED: [],  # Terminal state
        }
        return next_phase in allowed_transitions.get(current, [])
