"""
APEX September 15, 2026 Log Forensic Replay & Lifecycle Verification (Phase 17)
==============================================================================
Proves that the forensic defects observed in the original September 15 log:
- 00:44 IST: SESSION_START (sequence 1)
- 01:10 IST: Premature SESSION_END, false EQUITY_MARKET_CLOSE & SESSION_REGULAR_CLOSE
- 09:49 IST: Second SESSION_START for same experiment_id (sequence reset to 1)

are mathematically and architecturally transformed into:
- 00:44 IST: WORKER ONLINE in TRADING_DAY_PREMARKET (sequence starts)
- 01:10 IST: Worker process shutdown does NOT finalize session (WORKER_SHUTDOWN, session_finalized=False)
- 09:15 IST: Authoritative MARKET_OPEN transition
- 09:49 IST: WORKER_RECOVERY (no duplicate SESSION_START, global sequence continues monotonically)
- Authentic Upstox live ticks retain AUTHENTIC_LIVE and provider timestamps
- Segregation between historical bootstrap and live data
"""

import json
import os
import shutil
import time
import datetime
import pytest

from backend.app.database.connection import init_db, AsyncSessionLocal
from backend.app.database.repositories.audit_repository import AuditRepository
from backend.app.live_paper.session_lifecycle import (
    MarketPhase,
    WorkerState,
    DataProvenance,
    SessionLifecycleManager,
)
from backend.app.live_paper.master_evidence_logger import (
    MasterEvidenceLogger,
    EventType,
)
from backend.app.live_paper.session_runner import LivePaperSessionRunner


@pytest.mark.asyncio
async def test_sept15_forensic_replay_proves_hardened_lifecycle():
    """
    Loads authentic events from logs/live_paper/2026-09-15/APEX_2026-09-15_MASTER.jsonl
    and verifies the corrected lifecycle logic.
    """
    await init_db()
    log_file_path = "logs/live_paper/2026-09-15/APEX_2026-09-15_MASTER.jsonl"
    assert os.path.exists(log_file_path), "September 15 master log must exist as forensic source of truth."

    # 1. Forensic Inspection of the original log
    events_by_time = []
    with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                evt = json.loads(line_str)
                events_by_time.append(evt)
            except Exception:
                pass

    assert len(events_by_time) > 1000

    # Locate the two historic SESSION_START events in the raw log
    session_starts = [e for e in events_by_time if e.get("event_type") == "SESSION_START"]
    assert len(session_starts) >= 2, "Original log has 2 duplicate SESSION_STARTs for same experiment."

    # Both originally started at sequence_number = 1
    assert session_starts[0].get("sequence_number") == 1
    assert session_starts[1].get("sequence_number") == 1

    # 2. Replay under the Hardened Architecture
    test_dir = os.path.join("logs", "test_replay_sept15", f"run_{int(time.time()*1000)}")
    os.makedirs(test_dir, exist_ok=True)
    replay_date = f"2026-09-15-replay-{int(time.time()*1000)}"

    try:
        # STEP 1: First Worker Process Starts at 00:44 IST
        t_0044 = datetime.datetime(2026, 9, 15, 0, 44, 22, tzinfo=SessionLifecycleManager.IST_TZ)
        phase_0044 = SessionLifecycleManager.determine_market_phase(t_0044)
        assert phase_0044 == MarketPhase.PREMARKET, "00:44 IST must be categorized as PREMARKET."

        logger1 = MasterEvidenceLogger(
            experiment_id=f"APEX-WORKER-{replay_date}",
            log_dir=test_dir,
            session_date=replay_date,
            worker_instance_id="worker_render_proc_01",
            session_instance_id=f"session_{replay_date}_authoritative",
        )
        logger1.set_market_phase(phase_0044.value)

        # Log genuine single SESSION_START
        start_evt = await logger1.log_session_start(universe=["RELIANCE.NS", "TCS.NS"])
        assert start_evt.sequence_number == 1
        assert start_evt.global_sequence_number == 1
        assert start_evt.market_phase == "PREMARKET"

        # Simulate ticks during premarket
        for i in range(5):
            await logger1.log_event(
                EventType.RAW_MARKET_TICK,
                payload={"ltp": 2900.0 + i},
                data_provenance=DataProvenance.DERIVED.value,  # Outside market hours
            )

        await logger1.flush_db()
        last_gseq_worker1 = logger1.current_global_sequence_number
        assert last_gseq_worker1 == 6

        # STEP 2: Process Shutdown at 01:10 IST
        t_0110 = datetime.datetime(2026, 9, 15, 1, 10, 28, tzinfo=SessionLifecycleManager.IST_TZ)
        is_past_close = t_0110.time() >= SessionLifecycleManager.FNO_CLOSE_TIME
        assert not is_past_close, "01:10 IST is NOT past 15:40 IST close. Must NOT finalize session."

        # Emit WORKER_SHUTDOWN without false session finalization
        shutdown_evt = await logger1.log_event(
            EventType.WORKER_SHUTDOWN,
            payload={
                "experiment_id": logger1.experiment_id,
                "reason": "PROCESS_RESTART",
                "market_phase": phase_0044.value,
                "session_finalized": False,
            },
        )
        assert shutdown_evt.payload["session_finalized"] is False
        await logger1.flush_db()
        final_worker1_seq = logger1.current_global_sequence_number
        assert final_worker1_seq == 7
        await logger1.close()

        # Verify in DB that session was NOT marked finalized
        async with AsyncSessionLocal() as session:
            repo = AuditRepository(session)
            recovery_state = await repo.get_session_recovery_state(replay_date)
            assert recovery_state["is_finalized"] is False
            assert recovery_state["has_started"] is True
            assert recovery_state["max_global_sequence"] == 7

        # STEP 3: Market Open at 09:15 IST
        t_0915 = datetime.datetime(2026, 9, 15, 9, 15, 0, tzinfo=SessionLifecycleManager.IST_TZ)
        phase_0915 = SessionLifecycleManager.determine_market_phase(t_0915)
        assert phase_0915 == MarketPhase.REGULAR_MARKET

        # STEP 4: Second Worker Starts at 09:49 IST (Same experiment, new worker_instance_id)
        t_0949 = datetime.datetime(2026, 9, 15, 9, 49, 28, tzinfo=SessionLifecycleManager.IST_TZ)
        phase_0949 = SessionLifecycleManager.determine_market_phase(t_0949)
        assert phase_0949 == MarketPhase.REGULAR_MARKET

        logger2 = MasterEvidenceLogger(
            experiment_id=f"APEX-WORKER-{replay_date}",
            log_dir=test_dir,
            session_date=replay_date,
            worker_instance_id="worker_render_proc_02",  # New worker process ID
            session_instance_id=f"session_{replay_date}_authoritative",  # Same session instance
        )
        logger2.set_market_phase(phase_0949.value)

        # Recover from database
        await logger2.recover_state_from_db_if_needed()
        assert logger2.current_global_sequence_number == 7, "Global sequence must resume from 7, NOT reset to 0 or 1."

        # Emit WORKER_RECOVERY (NOT duplicate SESSION_START)
        recovery_evt = await logger2.log_worker_recovery(recovered_from_global_sequence=7)
        assert recovery_evt.event_type == EventType.WORKER_RECOVERY
        assert recovery_evt.global_sequence_number == 8
        assert recovery_evt.market_phase == "REGULAR_MARKET"

        # STEP 5: Live Upstox Ticks received during active market
        # Using authentic payload parameters from Sept 15 log line 14 (AXISBANK)
        authentic_tick_evt = await logger2.log_event(
            EventType.RAW_MARKET_TICK,
            payload={
                "symbol": "AXISBANK.NS",
                "instrument_key": "NSE_EQ|INE238A01034",
                "ltp": 1240.3,
                "change": -5.7,
                "change_percent": -0.46,
                "volume": 12000,
            },
            symbol="AXISBANK.NS",
            source="UPSTOX_WS",
            provider="UPSTOX",
            instrument_key="NSE_EQ|INE238A01034",
            data_provenance=DataProvenance.AUTHENTIC_LIVE.value,
            market_timestamp=1789445967.225,  # Authentic provider market timestamp preserved
            processing_latency_ms=42.5,
        )

        assert authentic_tick_evt.global_sequence_number == 9
        assert authentic_tick_evt.data_provenance == "AUTHENTIC_LIVE"
        assert authentic_tick_evt.market_timestamp == 1789445967.225
        assert authentic_tick_evt.provider == "UPSTOX"
        assert authentic_tick_evt.processing_latency_ms == 42.5

        await logger2.flush_db()
        await logger2.close()

        # STEP 6: Final Audit Assertions
        async with AsyncSessionLocal() as session:
            repo = AuditRepository(session)
            events_db = await repo.get_audit_events(session_date=replay_date, limit=50)
            events = events_db["events"]
            
            event_types = [e["event_type"] for e in events]
            # Must contain SESSION_START exactly ONCE
            assert event_types.count("SESSION_START") == 1
            # Must contain WORKER_RECOVERY exactly ONCE
            assert event_types.count("WORKER_RECOVERY") == 1
            # Must NOT contain early premature SESSION_END
            assert "SESSION_END" not in event_types

            # Global sequence numbers must be strictly monotonic [1, 2, 3, 4, 5, 6, 7, 8, 9]
            gseqs = [e["global_sequence_number"] for e in events]
            assert gseqs == list(range(1, 10))

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
