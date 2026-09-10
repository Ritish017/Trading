"""
APEX Cloud Autonomy & Market-Close Finalization Test Suite
=========================================================
Verifies 100% cloud autonomy for Indian NSE equity and F&O paper trading sessions:
1. Durable audit_events and session_reports table persistence.
2. Master evidence logger asynchronous cloud dual-write and flush.
3. 15-minute scheduled checkpoint execution across 20 quantitative strategies.
4. Automated Equity Market Close (15:30 IST) finalization.
5. Automated F&O Market Close (15:40 IST) certification, SHA-256 seal, and report generation.
6. Cloud REST endpoints: /api/session/report, /api/session/checkpoints, /api/audit/events, /api/session/status.
7. Strict preservation of safety invariants and frozen research configuration hash.
"""

import asyncio
import os
import shutil
import time
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.config import settings
from backend.app.database.connection import init_db, AsyncSessionLocal
from backend.app.database.models import AuditEventModel, SessionReportModel
from backend.app.database.repositories.audit_repository import AuditRepository
from backend.app.database.repositories.worker_repository import WorkerRepository
from backend.app.live_paper.safety import LIVE_ORDER_ALLOWED, LivePaperSafetyGuard
from backend.app.live_paper.master_evidence_logger import MasterEvidenceLogger, EventType
from backend.app.live_paper.session_runner import LivePaperSessionRunner
from backend.app.signal_engine.version_freeze import CONFIGURATION_HASH
from backend.app.worker import worker_app
from backend.app.main import app as main_app


@pytest.mark.asyncio
async def test_audit_repository_and_table_persistence():
    """Verify durable audit event batching, pagination, and session report storage."""
    await init_db()
    test_date = f"2026-test-{int(time.time()*1000)}"

    t_now = int(time.time() * 1000)
    eid1 = f"EVT-TEST-{t_now}-1"
    eid2 = f"EVT-TEST-{t_now}-2"
    eid3 = f"EVT-TEST-{t_now}-3"

    async with AsyncSessionLocal() as session:
        repo = AuditRepository(session)

        # 1. Insert single event
        evt = await repo.insert_audit_event({
            "event_id": eid1,
            "experiment_id": f"TEST-EXP-{test_date}",
            "session_date": test_date,
            "event_type": "SESSION_START",
            "sequence_number": 1,
            "event_timestamp_utc": "2026-09-10T09:15:00.000Z",
            "event_timestamp_ist": "2026-09-10T14:45:00.000+05:30",
            "source": "TEST",
            "payload": {"status": "START"},
        })
        assert evt.id is not None
        assert evt.event_id == eid1

        # 2. Batch insert multiple events
        batch = [
            {
                "event_id": eid2,
                "experiment_id": f"TEST-EXP-{test_date}",
                "session_date": test_date,
                "event_type": "STRATEGY_EVALUATION",
                "sequence_number": 2,
                "event_timestamp_utc": "2026-09-10T09:16:00.000Z",
                "event_timestamp_ist": "2026-09-10T14:46:00.000+05:30",
                "symbol": "RELIANCE",
                "source": "STRATEGY_EVALUATOR",
                "payload": {"score": 85.0},
            },
            {
                "event_id": eid3,
                "experiment_id": f"TEST-EXP-{test_date}",
                "session_date": test_date,
                "event_type": "SESSION_CHECKPOINT",
                "sequence_number": 3,
                "event_timestamp_utc": "2026-09-10T09:30:00.000Z",
                "event_timestamp_ist": "2026-09-10T15:00:00.000+05:30",
                "source": "CHECKPOINT_RUNNER",
                "payload": {"checkpoint_id": "CHECKPOINT_15_00"},
            },
        ]
        inserted = await repo.insert_audit_events_batch(batch)
        assert inserted == 2

        # 3. Retrieve events with pagination
        events_resp = await repo.get_audit_events(session_date=test_date, limit=10)
        assert events_resp["total_returned"] == 3
        assert events_resp["events"][0]["sequence_number"] == 1
        assert events_resp["events"][2]["sequence_number"] == 3

        # 4. Upsert Session Report
        report = await repo.upsert_session_report(
            session_date=test_date,
            experiment_id=f"TEST-EXP-{test_date}",
            status="FINALIZED",
            report_markdown="# Test Session Report",
            master_log_sha256="abc123sha256seal",
            total_events=3,
            summary_metrics={"ticks": 100},
            checkpoints=[{"checkpoint_id": "CHECKPOINT_15_00"}],
            is_certified=True,
        )
        assert report.id is not None
        assert report.status == "FINALIZED"
        assert report.master_log_sha256 == "abc123sha256seal"

        # 5. Fetch Session Report
        fetched_report = await repo.get_session_report(test_date)
        assert fetched_report is not None
        assert fetched_report["session_date"] == test_date
        assert fetched_report["master_log_sha256"] == "abc123sha256seal"
        assert len(fetched_report["checkpoints"]) == 1

        # 6. Fetch Checkpoints
        cps = await repo.get_checkpoints(test_date)
        assert len(cps) == 1
        assert cps[0]["checkpoint_id"] == "CHECKPOINT_15_00"


@pytest.mark.asyncio
async def test_master_evidence_logger_dual_write_and_recovery():
    """Verify MasterEvidenceLogger writes to JSONL and asynchronously commits to audit_events in DB."""
    await init_db()
    test_dir = f"logs/test_dual_write_{int(time.time()*1000)}"
    test_date = f"2026-dw-{int(time.time()*1000)}"

    try:
        logger = MasterEvidenceLogger(
            experiment_id=f"EXP-{test_date}",
            log_dir=test_dir,
            session_date=test_date,
        )

        evt1 = await logger.log_event(EventType.SESSION_START, {"phase": "START"})
        evt2 = await logger.log_event(EventType.SESSION_HEARTBEAT, {"cpu": 12.5})
        evt3 = await logger.log_event(EventType.RAW_MARKET_TICK, {"ltp": 2950.0}, symbol="RELIANCE")

        assert evt1.sequence_number == 1
        assert evt2.sequence_number == 2
        assert evt3.sequence_number == 3

        # Flush queued writes to database
        await logger.flush_db()

        # Verify in DB
        async with AsyncSessionLocal() as session:
            repo = AuditRepository(session)
            db_res = await repo.get_audit_events(session_date=test_date)
            assert db_res["total_returned"] == 3
            assert db_res["events"][0]["event_id"] == evt1.event_id
            assert db_res["events"][1]["event_id"] == evt2.event_id
            assert db_res["events"][2]["event_id"] == evt3.event_id

        # Verify SHA-256 computation
        sha256_hash = logger.compute_sha256()
        assert len(sha256_hash) == 64

        await logger.close()

        # Test crash recovery: start new logger on fresh dir but same date, recovering sequence from DB
        logger_recovered = MasterEvidenceLogger(
            experiment_id=f"EXP-{test_date}-RECOVERED",
            log_dir=test_dir + "_fresh",
            session_date=test_date,
        )
        await logger_recovered.recover_state_from_db_if_needed()
        assert logger_recovered.current_sequence_number == 3
        await logger_recovered.close()

    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)
        if os.path.exists(test_dir + "_fresh"):
            shutil.rmtree(test_dir + "_fresh", ignore_errors=True)


@pytest.mark.asyncio
async def test_session_runner_autonomous_checkpoints_and_market_close():
    """Verify LivePaperSessionRunner executes checkpoints, equity close, F&O close, and seals report."""
    await init_db()
    t_ms = int(time.time() * 1000)
    test_dir = f"logs/test_runner_autonomy_{t_ms}"
    test_date = f"2026-run-{t_ms}"

    runner = LivePaperSessionRunner(
        experiment_id=f"APEX-AUTONOMY-{test_date}",
        session_date=test_date,
        dry_run=True,
        log_dir=test_dir,
        universe=["RELIANCE", "TCS"],
    )

    try:
        await runner.start()
        assert runner.is_running is True

        # 1. Execute scheduled checkpoint
        cp_result = await runner.execute_checkpoint("CHECKPOINT_14_45")
        assert cp_result["checkpoint_id"] == "CHECKPOINT_14_45"
        assert len(runner._checkpoints) == 1
        assert "CHECKPOINT_14_45" in runner._checkpoints_executed

        # 2. Execute Equity Market Close (15:30 IST)
        await runner.finalize_equity_close()
        assert runner._equity_finalized is True
        assert "CHECKPOINT_15_30" in runner._checkpoints_executed

        # 3. Execute F&O Market Close (15:40 IST) & Full Certification
        await runner.finalize_fno_and_session_close()
        assert runner._session_finalized is True
        assert runner.master_log_sha256 is not None
        assert len(runner.master_log_sha256) == 64
        assert runner.final_report_markdown is not None
        assert "100%_CLOUD_AUTONOMOUS_SESSION_COMPLETED_SUCCESSFULLY" in runner.final_report_markdown

        # 4. Verify durable session report in PostgreSQL
        async with AsyncSessionLocal() as session:
            repo = AuditRepository(session)
            rep = await repo.get_session_report(test_date)
            assert rep is not None
            assert rep["status"] == "FINALIZED"
            assert rep["master_log_sha256"] == runner.master_log_sha256
            assert len(rep["checkpoints"]) >= 2

            worker_repo = WorkerRepository(session)
            w_status = await worker_repo.get_worker_status("apex-market-worker")
            assert w_status["worker_status"] == "COMPLETED_FINALIZED"
            assert w_status["details"]["session_certified"] is True

    finally:
        await runner.stop()
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)
        report_disk_path = f"docs/live_sessions/{test_date}"
        if os.path.exists(report_disk_path):
            shutil.rmtree(report_disk_path, ignore_errors=True)


@pytest.mark.asyncio
async def test_cloud_session_rest_endpoints():
    """Verify cloud session report, checkpoints, audit events, and status endpoints via HTTP."""
    os.environ["WORKER_AUTO_START"] = "false"
    os.environ["VERCEL"] = "1"
    await init_db()
    t_ms = int(time.time() * 1000)
    test_date = f"2026-api-{t_ms}"
    from backend.app.worker import worker_instance
    worker_instance.target_date = test_date

    # Seed report in DB
    async with AsyncSessionLocal() as session:
        repo = AuditRepository(session)
        await repo.upsert_session_report(
            session_date=test_date,
            experiment_id=f"APEX-EXP-{test_date}",
            status="FINALIZED",
            report_markdown="# Certified Session Report\n100% Cloud Autonomous.",
            master_log_sha256="d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e",
            total_events=1867,
            checkpoints=[{"checkpoint_id": "CHECKPOINT_15_30", "timestamp_ist": "15:30:00 IST"}],
            is_certified=True,
        )

    # 1. Test worker probe endpoints
    transport = ASGITransport(app=worker_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/session/status
        status_res = await client.get("/api/session/status")
        assert status_res.status_code == 200
        assert status_res.json()["cloud_autonomous"] is True
        assert status_res.json()["live_orders_blocked"] is True

        # GET /api/session/report
        report_res = await client.get(f"/api/session/report?session_date={test_date}")
        assert report_res.status_code == 200
        assert report_res.json()["status"] == "FINALIZED"
        assert "Certified Session Report" in report_res.json()["report_markdown"]

        # GET /api/session/checkpoints
        cp_res = await client.get(f"/api/session/checkpoints?session_date={test_date}")
        assert cp_res.status_code == 200
        assert len(cp_res.json()) >= 1

        # GET /api/audit/events
        events_res = await client.get(f"/api/audit/events?session_date={test_date}&limit=10")
        assert events_res.status_code == 200
        assert "events" in events_res.json()

    # 2. Test Vercel main app endpoints
    main_transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=main_transport, base_url="http://test") as client:
        report_res = await client.get(f"/api/session/report?session_date={test_date}")
        assert report_res.status_code == 200
        assert report_res.json()["status"] == "FINALIZED"

        cp_res = await client.get(f"/api/session/checkpoints?session_date={test_date}")
        assert cp_res.status_code == 200
        assert len(cp_res.json()) >= 1


def test_safety_and_frozen_configuration_invariants():
    """Strictly assert safety invariants and immutable research configuration hash."""
    assert LIVE_ORDER_ALLOWED is False
    LivePaperSafetyGuard.assert_paper_mode_enforced()
    LivePaperSafetyGuard.verify_frozen_configuration()
    assert CONFIGURATION_HASH == "d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e"
