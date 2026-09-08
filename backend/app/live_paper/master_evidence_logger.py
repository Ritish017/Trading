"""
APEX Master Evidence Logger — Single Append-Only JSONL Evidence Record
======================================================================
Provides the single, authoritative, immutable, append-only master record of the
entire live paper-trading session.

Key Invariants:
1. Exactly ONE primary append-only JSONL file for the entire session.
   Format: logs/live_paper/YYYY-MM-DD/APEX_YYYY-MM-DD_MASTER.jsonl
2. Every line is a self-contained JSON event with strictly increasing sequence_number.
3. Monotonic sequence numbering survives crashes: on restart, recovers max sequence number.
4. No event is ever silently overwritten or deleted.
5. End-of-session computes deterministic SHA-256 checksum of the master log file.
"""

import asyncio
import datetime
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.signal_engine.version_freeze import (
    STRATEGY_VERSION,
    SIGNAL_ENGINE_VERSION,
    COST_MODEL_VERSION,
    OPTIONS_ENGINE_VERSION,
    CONFIGURATION_HASH,
    GIT_COMMIT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authoritative Event Types (Prompt Section 4)
# ---------------------------------------------------------------------------

class EventType:
    # Session Lifecycle
    SESSION_START = "SESSION_START"
    SESSION_PREFLIGHT = "SESSION_PREFLIGHT"
    SESSION_REGULAR_OPEN = "SESSION_REGULAR_OPEN"
    SESSION_HEARTBEAT = "SESSION_HEARTBEAT"
    SESSION_REGULAR_CLOSE = "SESSION_REGULAR_CLOSE"
    SESSION_END = "SESSION_END"
    SESSION_SUMMARY = "SESSION_SUMMARY"

    # Market Connectivity & Data
    MARKET_CONNECTION = "MARKET_CONNECTION"
    MARKET_DISCONNECTION = "MARKET_DISCONNECTION"
    MARKET_RECONNECT = "MARKET_RECONNECT"
    MARKET_SUBSCRIPTION = "MARKET_SUBSCRIPTION"
    MARKET_DATA_ERROR = "MARKET_DATA_ERROR"
    RAW_MARKET_TICK = "RAW_MARKET_TICK"
    MARKET_SNAPSHOT = "MARKET_SNAPSHOT"
    CANDLE_CREATED = "CANDLE_CREATED"
    CANDLE_UPDATED = "CANDLE_UPDATED"
    UNIVERSE_SNAPSHOT = "UNIVERSE_SNAPSHOT"
    DATA_QUALITY_EVENT = "DATA_QUALITY_EVENT"

    # Market State & Multi-Timeframe
    REGIME_UPDATE = "REGIME_UPDATE"
    MTF_UPDATE = "MTF_UPDATE"

    # Strategy Evaluation
    STRATEGY_EVALUATION = "STRATEGY_EVALUATION"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    STRATEGY_NO_SIGNAL = "STRATEGY_NO_SIGNAL"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"

    # Candidate Pipeline
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    CANDIDATE_VALIDATED = "CANDIDATE_VALIDATED"

    # Validation & Risk Gates
    VALIDATION_GATE_RESULT = "VALIDATION_GATE_RESULT"
    CONFLUENCE_RESULT = "CONFLUENCE_RESULT"
    RISK_RESULT = "RISK_RESULT"
    ENTRY_RESULT = "ENTRY_RESULT"
    STOP_TARGET_RESULT = "STOP_TARGET_RESULT"

    # Signal Lifecycle
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_QUALIFIED = "SIGNAL_QUALIFIED"
    SIGNAL_INVALIDATED = "SIGNAL_INVALIDATED"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    SIGNAL_TRIGGERED = "SIGNAL_TRIGGERED"
    NO_QUALIFIED_SIGNAL = "NO_QUALIFIED_SIGNAL"

    # Paper Orders
    PAPER_ORDER_CREATED = "PAPER_ORDER_CREATED"
    PAPER_ORDER_VALIDATED = "PAPER_ORDER_VALIDATED"
    PAPER_ORDER_ACCEPTED = "PAPER_ORDER_ACCEPTED"
    PAPER_ORDER_REJECTED = "PAPER_ORDER_REJECTED"
    PAPER_ORDER_FILLED = "PAPER_ORDER_FILLED"
    PAPER_ORDER_CANCELLED = "PAPER_ORDER_CANCELLED"

    # Paper Positions & MTM
    PAPER_POSITION_OPENED = "PAPER_POSITION_OPENED"
    PAPER_POSITION_UPDATED = "PAPER_POSITION_UPDATED"
    PAPER_POSITION_CLOSED = "PAPER_POSITION_CLOSED"
    PAPER_MARK_TO_MARKET = "PAPER_MARK_TO_MARKET"
    PAPER_STOP_TRIGGERED = "PAPER_STOP_TRIGGERED"
    PAPER_TARGET_TRIGGERED = "PAPER_TARGET_TRIGGERED"
    PAPER_TRADE_OUTCOME = "PAPER_TRADE_OUTCOME"

    # Financial & Accounting
    COST_CALCULATION = "COST_CALCULATION"
    PNL_UPDATE = "PNL_UPDATE"

    # Audit, Research & Safety
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    RESEARCH_EVENT = "RESEARCH_EVENT"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SECURITY_BLOCKED_EVENT = "SECURITY_BLOCKED_EVENT"


# ---------------------------------------------------------------------------
# Event Schema (Prompt Section 3)
# ---------------------------------------------------------------------------

class MasterEvidenceEvent(BaseModel):
    """
    Self-contained event schema for master evidence JSONL records.
    """
    event_id: str
    experiment_id: str
    event_type: str
    event_timestamp_utc: str
    event_timestamp_ist: str
    sequence_number: int
    symbol: Optional[str] = None
    source: str
    data_provenance: str
    git_commit: str = GIT_COMMIT
    config_hash: str = CONFIGURATION_HASH
    engine_version: str = SIGNAL_ENGINE_VERSION
    payload: Dict[str, Any] = Field(default_factory=dict)


def get_current_timestamps() -> tuple[str, str]:
    """Returns (UTC_ISO, IST_ISO) timestamps."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Asia/Kolkata is UTC + 5:30
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = now_utc.astimezone(ist_tz)
    return now_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), now_ist.strftime("%Y-%m-%dT%H:%M:%S.%f+05:30")


# ---------------------------------------------------------------------------
# Master Evidence Logger
# ---------------------------------------------------------------------------

class MasterEvidenceLogger:
    """
    Append-only thread/async-safe logger writing strictly sequenced JSONL events.
    """

    def __init__(self, experiment_id: str, log_dir: Optional[str] = None, session_date: Optional[str] = None):
        self.experiment_id = experiment_id
        
        # Derive date string YYYY-MM-DD
        if not session_date:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            now_ist = now_utc.astimezone(ist_tz)
            session_date = now_ist.strftime("%Y-%m-%d")
        self.session_date = session_date

        if log_dir:
            self.log_dir = log_dir
        else:
            self.log_dir = os.path.join("logs", "live_paper", self.session_date)

        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"APEX_{self.session_date}_MASTER.jsonl")

        self._lock = asyncio.Lock()
        self._sequence_number = 0
        self._first_event_id: Optional[str] = None
        self._last_event_id: Optional[str] = None

        # Counters for integrity verification
        self._counts: Dict[str, int] = {
            "total_events": 0,
            "error_count": 0,
            "market_events": 0,
            "candidate_count": 0,
            "rejected_candidates": 0,
            "signal_count": 0,
            "paper_order_count": 0,
            "paper_fill_count": 0,
            "closed_trade_count": 0,
        }

        # Recover sequence number and stats if resuming an existing master file
        self._recover_state_if_exists()

    def _recover_state_if_exists(self) -> None:
        """Crash recovery: reads existing lines to recover max sequence_number."""
        if not os.path.exists(self.log_file):
            return

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        record = json.loads(line_str)
                        seq = record.get("sequence_number", 0)
                        if seq > self._sequence_number:
                            self._sequence_number = seq
                        
                        eid = record.get("event_id")
                        if self._first_event_id is None and eid:
                            self._first_event_id = eid
                        if eid:
                            self._last_event_id = eid

                        self._counts["total_events"] += 1
                        etype = record.get("event_type", "")
                        if "ERROR" in etype:
                            self._counts["error_count"] += 1
                        if "MARKET" in etype or "TICK" in etype or "CANDLE" in etype:
                            self._counts["market_events"] += 1
                        if "CANDIDATE" in etype:
                            self._counts["candidate_count"] += 1
                        if etype == EventType.CANDIDATE_REJECTED:
                            self._counts["rejected_candidates"] += 1
                        if "SIGNAL" in etype:
                            self._counts["signal_count"] += 1
                        if etype == EventType.PAPER_ORDER_CREATED:
                            self._counts["paper_order_count"] += 1
                        if etype == EventType.PAPER_ORDER_FILLED:
                            self._counts["paper_fill_count"] += 1
                        if etype in (EventType.PAPER_POSITION_CLOSED, EventType.PAPER_TRADE_OUTCOME):
                            self._counts["closed_trade_count"] += 1
                    except Exception:
                        continue
            logger.info(
                f"[MASTER LOGGER] Recovered session file: {self.log_file} "
                f"at sequence {self._sequence_number}, events: {self._counts['total_events']}"
            )
        except Exception as e:
            logger.error(f"[MASTER LOGGER] Crash recovery parse notice: {e}")

    @property
    def current_sequence_number(self) -> int:
        return self._sequence_number

    @property
    def counts(self) -> Dict[str, int]:
        return dict(self._counts)

    async def log_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        symbol: Optional[str] = None,
        source: str = "APEX_SIGNAL_ENGINE",
        data_provenance: str = "AUTHENTIC_LIVE",
        event_id: Optional[str] = None,
    ) -> MasterEvidenceEvent:
        """
        Atomically appends an event to the master JSONL file with sequential numbering.
        """
        import uuid

        utc_ts, ist_ts = get_current_timestamps()
        eid = event_id or f"EVT-{uuid.uuid4().hex[:12].upper()}"

        async with self._lock:
            self._sequence_number += 1
            seq = self._sequence_number

            event = MasterEvidenceEvent(
                event_id=eid,
                experiment_id=self.experiment_id,
                event_type=event_type,
                event_timestamp_utc=utc_ts,
                event_timestamp_ist=ist_ts,
                sequence_number=seq,
                symbol=symbol,
                source=source,
                data_provenance=data_provenance,
                git_commit=GIT_COMMIT,
                config_hash=CONFIGURATION_HASH,
                engine_version=SIGNAL_ENGINE_VERSION,
                payload=payload or {},
            )

            # Update counters
            self._counts["total_events"] += 1
            if self._first_event_id is None:
                self._first_event_id = eid
            self._last_event_id = eid

            if "ERROR" in event_type:
                self._counts["error_count"] += 1
            if "MARKET" in event_type or "TICK" in event_type or "CANDLE" in event_type:
                self._counts["market_events"] += 1
            if "CANDIDATE" in event_type:
                self._counts["candidate_count"] += 1
            if event_type == EventType.CANDIDATE_REJECTED:
                self._counts["rejected_candidates"] += 1
            if "SIGNAL" in event_type:
                self._counts["signal_count"] += 1
            if event_type == EventType.PAPER_ORDER_CREATED:
                self._counts["paper_order_count"] += 1
            if event_type == EventType.PAPER_ORDER_FILLED:
                self._counts["paper_fill_count"] += 1
            if event_type in (EventType.PAPER_POSITION_CLOSED, EventType.PAPER_TRADE_OUTCOME):
                self._counts["closed_trade_count"] += 1

            # Append to master file
            try:
                line = event.model_dump_json() + "\n"
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
            except Exception as e:
                logger.critical(f"[MASTER LOGGER] FATAL: Could not write to master evidence file: {e}")
                raise

        return event

    def compute_sha256(self) -> str:
        """Computes SHA-256 checksum of the entire master JSONL log file."""
        if not os.path.exists(self.log_file):
            return ""
        hasher = hashlib.sha256()
        with open(self.log_file, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def log_session_start(self, universe: List[str], metadata: Optional[Dict[str, Any]] = None) -> MasterEvidenceEvent:
        """Emits mandatory SESSION_START event recording frozen environment metadata."""
        utc_ts, ist_ts = get_current_timestamps()
        payload = {
            "experiment_id": self.experiment_id,
            "session_date": self.session_date,
            "utc_start_timestamp": utc_ts,
            "ist_start_timestamp": ist_ts,
            "git_commit": GIT_COMMIT,
            "configuration_hash": CONFIGURATION_HASH,
            "strategy_version": STRATEGY_VERSION,
            "signal_engine_version": SIGNAL_ENGINE_VERSION,
            "cost_model_version": COST_MODEL_VERSION,
            "options_engine_version": OPTIONS_ENGINE_VERSION,
            "python_version": "3.14",
            "environment": "LIVE_PAPER",
            "live_order_allowed": False,
            "broker_data_feed": "UPSTOX_V2_FEED",
            "market_data_provider": "UPSTOX",
            "universe_count": len(universe),
            "configured_universe": universe,
        }
        if metadata:
            payload.update(metadata)
        return await self.log_event(EventType.SESSION_START, payload=payload, source="SESSION_INITIALIZER")

    async def log_session_summary(self, summary_metrics: Optional[Dict[str, Any]] = None) -> MasterEvidenceEvent:
        """
        Emits mandatory SESSION_SUMMARY event with complete integrity and performance metrics.
        """
        sha256_hash = self.compute_sha256()
        payload = {
            "experiment_id": self.experiment_id,
            "session_date": self.session_date,
            "master_log_file": self.log_file,
            "master_log_sha256": sha256_hash,
            "first_event_id": self._first_event_id,
            "last_event_id": self._last_event_id,
            "event_counts": self.counts,
            "metrics": summary_metrics or {},
        }
        return await self.log_event(EventType.SESSION_SUMMARY, payload=payload, source="SESSION_FINALIZER")
