"""
APEX Live Paper Trading & Evidence Capture Package
==================================================
Provides real-market data observation, sequential master evidence logging,
and paper-trading execution with zero lookahead and zero live capital risk.
"""

from backend.app.live_paper.master_evidence_logger import (
    MasterEvidenceLogger,
    MasterEvidenceEvent,
    EventType,
    get_current_timestamps,
)

__all__ = [
    "MasterEvidenceLogger",
    "MasterEvidenceEvent",
    "EventType",
    "get_current_timestamps",
]
