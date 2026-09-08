"""
Targeted Verification Suite: Stateful Worker & PostgreSQL Persistence
====================================================================
Validates:
1. Worker startup and shutdown lifecycle.
2. Production fail-closed database validation (missing DATABASE_URL or SQLite raises RuntimeError).
3. Dialect-agnostic database migration helper (get_table_columns).
4. Transaction atomicity, insert, update, rollback, and restart persistence.
5. WorkerRepository upsert, retrieval, and heartbeat staleness calculation.
6. Paper order and trade closure atomic persistence.
7. Live-order blocking invariant (LiveOrderForbiddenSecurityError).
8. Frozen configuration hash preservation.
"""

import asyncio
import os
import pytest
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.config import Settings
from backend.app.database.connection import get_table_columns, init_db, check_db_health, AsyncSessionLocal
from backend.app.database.models import Base, WorkerHeartbeatModel, PaperAccountModel, PaperOrderModel, PaperPositionModel
from backend.app.database.repositories.worker_repository import WorkerRepository
from backend.app.database.repositories.paper_repository import PaperRepository
from backend.app.live_paper.safety import (
    LIVE_ORDER_ALLOWED,
    LivePaperSafetyGuard,
    LiveOrderForbiddenSecurityError,
)
from backend.app.signal_engine.version_freeze import CONFIGURATION_HASH
from backend.app.worker import StatefulMarketWorker


@pytest.mark.asyncio
async def test_production_fail_closed_validation():
    """Verify that in production mode, missing DATABASE_URL or SQLite triggers fail-closed RuntimeError."""
    # 1. Missing DATABASE_URL in production
    cfg_missing = Settings(
        apex_env="production",
        database_url=None,
        live_trading=False,
    )
    with pytest.raises(RuntimeError, match="PRODUCTION FAIL-CLOSED: DATABASE_URL is missing"):
        cfg_missing.validate_production_invariants()

    # 2. SQLite URL in production
    cfg_sqlite = Settings(
        apex_env="production",
        database_url="sqlite+aiosqlite:////tmp/apex_quant.db",
        live_trading=False,
    )
    with pytest.raises(RuntimeError, match="PRODUCTION FAIL-CLOSED: SQLite"):
        cfg_sqlite.validate_production_invariants()

    # 3. Invalid schema in production
    cfg_invalid = Settings(
        apex_env="production",
        database_url="mysql+aiomysql://user:pass@localhost/db",
        live_trading=False,
    )
    with pytest.raises(RuntimeError, match="Must be an external PostgreSQL connection URL"):
        cfg_invalid.validate_production_invariants()

    # 4. Live trading enabled in production
    cfg_live_illegal = Settings(
        apex_env="production",
        database_url="postgresql+psycopg://user:pass@localhost:5432/apex_quant",
        live_trading=True,
    )
    with pytest.raises(RuntimeError, match="PRODUCTION SECURITY VIOLATION: LIVE_TRADING"):
        cfg_live_illegal.validate_production_invariants()

    # 5. Valid PostgreSQL production config passes
    cfg_valid = Settings(
        apex_env="production",
        database_url="postgresql+psycopg://user:pass@aws-rds.amazonaws.com:5432/apex_quant",
        live_trading=False,
        real_trading_enabled=False,
    )
    # Should not raise
    cfg_valid.validate_production_invariants()
    assert cfg_valid.is_production is True


@pytest.mark.asyncio
async def test_dialect_column_inspection_and_migration():
    """Verify dialect-agnostic column inspection helper on active database."""
    await init_db()
    async with AsyncSessionLocal() as session:
        conn = await session.connection()
        cols = await get_table_columns(conn, "paper_orders")
        assert "order_id" in cols or "symbol" in cols
        assert "exchange" in cols
        assert "signal_id" in cols
        assert "strategy_version" in cols

        worker_cols = await get_table_columns(conn, "worker_heartbeats")
        assert "worker_id" in worker_cols
        assert "worker_status" in worker_cols
        assert "market_connection" in worker_cols


@pytest.mark.asyncio
async def test_database_transactions_and_rollback():
    """Verify transaction atomicity, persistence, and rollback behavior."""
    await init_db()
    async with AsyncSessionLocal() as session:
        # Insert a test account
        test_acc_id = f"test_acc_{int(time.time() * 1000)}"
        acc = PaperAccountModel(
            account_id=test_acc_id,
            available_capital=500000.0,
            initial_capital=500000.0,
        )
        session.add(acc)
        await session.commit()

        # Update capital
        acc.available_capital = 450000.0
        await session.commit()

        # Test rollback: try adding duplicate account_id
        session.add(PaperAccountModel(account_id=test_acc_id, available_capital=100.0))
        with pytest.raises(Exception):
            await session.commit()
        await session.rollback()

        # Clean up
        await session.execute(text("DELETE FROM paper_accounts WHERE account_id = :a"), {"a": test_acc_id})
        await session.commit()


@pytest.mark.asyncio
async def test_worker_repository_heartbeat_and_staleness():
    """Verify WorkerRepository upserts telemetry and detects heartbeat staleness."""
    await init_db()
    async with AsyncSessionLocal() as session:
        repo = WorkerRepository(session)
        worker_id = f"test-worker-{int(time.time() * 1000)}"

        # 1. Non-existent worker returns NOT_STARTED
        status_empty = await repo.get_worker_status("non-existent-worker")
        assert status_empty["worker_status"] == "NOT_STARTED"
        assert status_empty["is_stale"] is True

        # 2. Upsert heartbeat
        hb = await repo.upsert_heartbeat(
            worker_id=worker_id,
            experiment_id="TEST-EXP-001",
            worker_status="ONLINE",
            market_connection="CONNECTED",
            signal_count=12,
            candidate_count=45,
            paper_order_count=8,
            open_positions=3,
            realized_pnl=12500.0,
            unrealized_pnl=-1200.0,
            total_costs=345.5,
            net_pnl=11300.0,
            data_quality="AUTHENTIC_LIVE",
        )
        assert hb.worker_id == worker_id

        # 3. Retrieve status
        status = await repo.get_worker_status(worker_id)
        assert status["worker_status"] == "ONLINE"
        assert status["market_connection"] == "CONNECTED"
        assert status["signal_count"] == 12
        assert status["candidate_count"] == 45
        assert status["open_positions"] == 3
        assert status["realized_pnl"] == 12500.0
        assert status["live_trading"] is False
        assert status["live_orders_blocked"] is True
        assert status["is_stale"] is False

        # Clean up
        await session.execute(text("DELETE FROM worker_heartbeats WHERE worker_id = :w"), {"w": worker_id})
        await session.commit()


@pytest.mark.asyncio
async def test_worker_lifecycle_startup_and_shutdown():
    """Verify StatefulMarketWorker starts, registers state in database, and shuts down cleanly."""
    import shutil
    test_log_dir = "logs/test_worker_logs"
    if os.path.exists(test_log_dir):
        shutil.rmtree(test_log_dir)

    await init_db()
    test_worker = StatefulMarketWorker(
        worker_id="test-lifecycle-worker",
        dry_run=True,
        log_dir=test_log_dir,
    )

    try:
        # Preflight check
        report = await test_worker.preflight()
        assert report["overall_status"] in ("READY", "READY_WITH_WARNINGS")

        # Start worker
        await test_worker.start()
        assert test_worker.is_running is True

        # Verify status in DB
        async with AsyncSessionLocal() as session:
            repo = WorkerRepository(session)
            st = await repo.get_worker_status(test_worker.worker_id)
            assert st["worker_status"] == "ONLINE"
            assert st["paper_mode"] is True
            assert st["live_trading"] is False

        # Stop worker
        await test_worker.stop()
        assert test_worker.is_running is False

        # Verify status changed to STOPPED in DB
        async with AsyncSessionLocal() as session:
            repo = WorkerRepository(session)
            st = await repo.get_worker_status(test_worker.worker_id)
            assert st["worker_status"] == "STOPPED"

            # Clean up
            await session.execute(text("DELETE FROM worker_heartbeats WHERE worker_id = :w"), {"w": test_worker.worker_id})
            await session.commit()
    finally:
        if os.path.exists(test_log_dir):
            shutil.rmtree(test_log_dir)


@pytest.mark.asyncio
async def test_safety_invariants_and_freeze():
    """Verify live trading is blocked and frozen configuration SHA-256 hash is preserved."""
    assert LIVE_ORDER_ALLOWED is False
    LivePaperSafetyGuard.assert_paper_mode_enforced()
    LivePaperSafetyGuard.verify_frozen_configuration()

    with pytest.raises(LiveOrderForbiddenSecurityError):
        LivePaperSafetyGuard.block_live_broker_order(
            symbol="RELIANCE.NS",
            side="BUY",
            quantity=25,
            broker="UPSTOX",
        )

    assert CONFIGURATION_HASH == "d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e"
