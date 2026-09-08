"""
Unit tests for Master Evidence Logger & Sequential JSONL Ledger.
"""

import os
import shutil
import pytest
from backend.app.live_paper.master_evidence_logger import (
    MasterEvidenceLogger,
    EventType,
    get_current_timestamps,
)


@pytest.fixture
def test_log_dir():
    dir_path = os.path.join("logs", "test_evidence")
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)
    yield dir_path
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)


@pytest.mark.asyncio
async def test_sequential_logging_monotonicity(test_log_dir):
    logger = MasterEvidenceLogger(
        experiment_id="TEST-EXP-001",
        log_dir=test_log_dir,
        session_date="2026-09-10",
    )

    evt1 = await logger.log_event(EventType.SESSION_START, {"step": 1})
    evt2 = await logger.log_event(EventType.RAW_MARKET_TICK, {"step": 2})
    evt3 = await logger.log_event(EventType.CANDIDATE_CREATED, {"step": 3})

    assert evt1.sequence_number == 1
    assert evt2.sequence_number == 2
    assert evt3.sequence_number == 3

    assert evt1.git_commit
    assert evt1.config_hash
    assert evt1.engine_version

    assert os.path.exists(logger.log_file)
    with open(logger.log_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_crash_recovery_resumes_sequence(test_log_dir):
    # First process session
    logger1 = MasterEvidenceLogger(
        experiment_id="TEST-EXP-002",
        log_dir=test_log_dir,
        session_date="2026-09-10",
    )
    await logger1.log_event(EventType.SESSION_START, {"session": "start"})
    await logger1.log_event(EventType.CANDIDATE_CREATED, {"cand": 1})
    assert logger1.current_sequence_number == 2

    # Simulate crash and restart
    logger2 = MasterEvidenceLogger(
        experiment_id="TEST-EXP-002",
        log_dir=test_log_dir,
        session_date="2026-09-10",
    )
    assert logger2.current_sequence_number == 2
    assert logger2.counts["total_events"] == 2

    # Append new event on restarted logger
    evt3 = await logger2.log_event(EventType.PAPER_ORDER_CREATED, {"order": 1})
    assert evt3.sequence_number == 3

    with open(logger2.log_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_sha256_integrity_checksum(test_log_dir):
    logger = MasterEvidenceLogger(
        experiment_id="TEST-EXP-003",
        log_dir=test_log_dir,
        session_date="2026-09-10",
    )
    await logger.log_event(EventType.SESSION_START, {"test": True})
    checksum = logger.compute_sha256()
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)
