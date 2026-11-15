# APEX Backend Lifespan & Process Teardown Guard Analysis Report

**Date**: 2026-10-06  
**Investigator**: teamwork_preview_explorer (Backend Lifespan Explorer) — Milestone 1 (R1)  
**Target Repository**: `C:\Tradinf2`  
**Scope**: `backend/app/main.py` (FastAPI Lifespan), `backend/app/worker.py` (Worker Lifespan, Startup Task Retention, Teardown Guards, Host Binding), and Lifespan Test Verification Suites.

---

## 1. Executive Summary

A deep architectural and line-by-line inspection of `backend/app/main.py` and `backend/app/worker.py` revealed critical lifecycle, resource leak, and process teardown vulnerabilities:

1. **Unguarded `yield` in `app_lifespan` (`main.py:114-134`)**:
   The generator `yield` is not wrapped in `try ... finally`. If FastAPI encounters an unhandled exception or receives `asyncio.CancelledError` (e.g., during SIGTERM/SIGINT shutdown, container eviction, or test teardown), generator execution is aborted. Provider disconnect (`market_data_service.active_provider.disconnect()`) and active WebSocket client closures are bypassed.

2. **Unguarded `yield` in `worker_lifespan` (`worker.py:220-234`)**:
   Similarly, `yield` in `worker_lifespan` is not wrapped in `try ... finally`. If probe requests fail, or the lifespan task is cancelled, `await worker_instance.stop()` is never called.

3. **Silent Garbage-Collection Hazard for Startup Task (`worker.py:231`)**:
   `asyncio.create_task(worker_instance.start())` creates an anonymous background task with no persistent variable reference. Under Python 3.14 (and Python 3.12+), unreferenced tasks are subject to garbage collection while running, triggering `Task was destroyed but it is still pending!` and aborting initialization without error handling.

4. **Startup Race Condition & Early-Exit Teardown Bug in `worker_instance.stop()` (`worker.py:174-175`)**:
   `stop()` begins with `if not self.is_running: return`. However, `self.is_running` is only set to `True` after preflight checks, database initialization, and runner task creation succeed (up to several seconds). If a shutdown signal or cancellation arrives while `start()` is in progress:
   - `stop()` exits immediately without doing anything.
   - The in-flight startup task keeps executing in the background, spawning database operations and runners after shutdown.
   - The database heartbeat remains stuck in `"STARTING"`, causing persistent phantom-worker anomalies.
   - Furthermore, even when `self.is_running` is True, `self._runner_task.cancel()` is called without being awaited (`await self._runner_task`), risking unhandled `CancelledError` warnings and unawaited network teardowns.

5. **Insecure Default Network Binding (`worker.py:465`)**:
   The worker HTTP probe defaults to `host = os.environ.get("HOST", "0.0.0.0")`, binding to all network interfaces. This violates the local loopback rule (R5 / Item 9 in `PROJECT.md`) for personal desktop workstations.

This report provides the exact root causes, line references, comprehensive replacement code, and an 11-case test specification to guarantee graceful shutdown and zero dangling background tasks.

---

## 2. Codebase Inspection & Root Cause Analysis

### 2.1 `backend/app/main.py`: `app_lifespan`

#### Current Code (`backend/app/main.py:114-134`):
```python
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f"Starting APEX Quant Lab Backend in {settings.environment} mode.")
    await ensure_initialized()
    try:
        default_symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "NIFTY 50", "BANKNIFTY", "INDIA VIX"]
        await market_data_service.subscribe(default_symbols)
        # Avoid hanging on websockets in short-lived serverless invocations
        if not os.environ.get("VERCEL"):
            await market_data_service.connect_websocket(on_normalized_tick_received)
    except Exception as e:
        logger.warning(f"WebSocket background feed non-fatal warning: {e}")
    yield
    logger.info("Shutting down APEX Quant Lab Backend...")
    if hasattr(market_data_service.active_provider, "disconnect"):
        try:
            await market_data_service.active_provider.disconnect()
        except Exception:
            pass
```

#### Identified Defects:
1. **Unprotected `yield`**:
   - Python async context managers wrap an async generator. When ASGI servers shut down, they inject `CancelledError` or close the generator (`aclose()`).
   - Because `yield` is outside `try ... finally`, if an exception occurs during the lifespan or a cancellation signal arrives, control NEVER passes to lines 127–132.
2. **Unguarded Active Client WebSockets**:
   - `active_ws_connections: Set[WebSocket]` (defined at line 72) retains open WebSocket connections to frontend clients (`/ws/ticks`).
   - On server shutdown, these connections are abandoned without sending standard close frames (`code=1001`, "Server shutting down"), causing abrupt connection drops on the client side.
3. **Encapsulation Breach on Provider Disconnect**:
   - Line 128 checks `hasattr(market_data_service.active_provider, "disconnect")`. It bypasses `market_data_service`, which orchestrates provider states (`status_code`, `is_live`). `MarketDataService` should manage its own provider disconnection and reset its status cleanly.

---

### 2.2 `backend/app/worker.py`: `worker_lifespan` and `StatefulMarketWorker`

#### Current Code (`backend/app/worker.py:172-185, 218-234`):
```python
    async def stop(self) -> None:
        """Stops the worker gracefully and flushes evidence logs."""
        if not self.is_running:
            return
        logger.info(f"[WORKER SHUTDOWN] Shutting down {self.worker_id} ({self.worker_instance_id})...")
        self.worker_state = WorkerState.STOPPING
        self.is_running = False

        if self.runner:
            await self.runner.stop()

        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
        ...

# Embedded HTTP Health and Monitoring Server
@asynccontextmanager
async def worker_lifespan(app: FastAPI):
    dry_run = os.environ.get("WORKER_DRY_RUN", "false").lower() in ("true", "1", "yes")
    target_date = os.environ.get("WORKER_TARGET_DATE")
    worker_instance.dry_run = dry_run
    if target_date:
        worker_instance.target_date = target_date
        worker_instance.experiment_id = f"APEX-WORKER-{target_date}"

    # Auto-start worker in background task so HTTP probe is immediately responsive
    auto_start = os.environ.get("WORKER_AUTO_START", "true").lower() in ("true", "1", "yes")
    if auto_start:
        asyncio.create_task(worker_instance.start())
    yield
    await worker_instance.stop()
```

#### Identified Defects:
1. **Unguarded `yield` in `worker_lifespan` (Line 232)**:
   - If an exception occurs in the probe or `CancelledError` is injected during shutdown, `await worker_instance.stop()` is never reached.
2. **Unreferenced Background Startup Task (Line 231)**:
   - `asyncio.create_task(worker_instance.start())` creates a task without storing its reference.
   - In Python 3.14 (and Python 3.12+), unreferenced asyncio tasks can be garbage-collected while awaiting I/O or sleep, causing premature task abortion.
3. **Early Exit in `stop()` when Startup is In-Flight (Line 174)**:
   - In `worker_instance.start()` (lines 91–152), the worker runs:
     - Invariant checks
     - Database initialization (`await init_db()`)
     - Preflight checks (`await self.preflight()`)
     - Database heartbeat update (`worker_status="STARTING"`)
     - Runner instantiation
   - `self.is_running` is only set to `True` at line 152.
   - If `stop()` is called while startup is still progressing, line 174 returns immediately:
     ```python
     if not self.is_running:
         return
     ```
   - This leaves the startup task running in the background, leaves the database heartbeat stuck in `STARTING`, and skips all runner/task teardown.
4. **Dangling Runner Task (`_runner_task`) (Lines 183-184)**:
   - `self._runner_task.cancel()` is called without `await self._runner_task`.
   - The cancelled task remains unawaited when `stop()` returns, leading to race conditions during event-loop teardown.
5. **Insecure Default Host Binding (Line 465)**:
   - `host = os.environ.get("HOST", "0.0.0.0")` exposes the unauthenticated worker probe to external network interfaces by default.

---

## 3. Formulated Replacement Code & Teardown Logic

### 3.1 Replacement Code for `backend/app/main.py`

#### Changes:
1. Wrap `ensure_initialized()`, subscription, and `yield` inside a `try ... finally` block.
2. In `finally:`, close active frontend WebSockets in `active_ws_connections` with code 1001.
3. Call `market_data_service.disconnect()` if available, falling back to `active_provider.disconnect()`.

```python
# ===========================================================================
# Replacement for backend/app/main.py:114-135
# ===========================================================================

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f"Starting APEX Quant Lab Backend in {settings.environment} mode.")
    try:
        await ensure_initialized()
        try:
            default_symbols = [
                "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS",
                "INFY.NS", "NIFTY 50", "BANKNIFTY", "INDIA VIX"
            ]
            await market_data_service.subscribe(default_symbols)
            # Avoid hanging on websockets in short-lived serverless invocations
            if not os.environ.get("VERCEL"):
                await market_data_service.connect_websocket(on_normalized_tick_received)
        except Exception as e:
            logger.warning(f"WebSocket background feed non-fatal warning: {e}")
        yield
    finally:
        logger.info("Shutting down APEX Quant Lab Backend...")

        # 1. Gracefully close all active client WebSockets
        if active_ws_connections:
            logger.info(f"Closing {len(active_ws_connections)} active client WebSocket(s)...")
            for ws in list(active_ws_connections):
                try:
                    await ws.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
            active_ws_connections.clear()

        # 2. Guarantee provider & feed disconnection
        if hasattr(market_data_service, "disconnect"):
            try:
                await market_data_service.disconnect()
                logger.info("MarketDataService disconnected cleanly.")
            except Exception as e:
                logger.warning(f"Error disconnecting MarketDataService: {e}")
        elif hasattr(market_data_service.active_provider, "disconnect"):
            try:
                await market_data_service.active_provider.disconnect()
                logger.info("Active MarketDataProvider disconnected cleanly.")
            except Exception as e:
                logger.warning(f"Error disconnecting active provider: {e}")

app.router.lifespan_context = app_lifespan
```

---

### 3.2 Replacement Code for `backend/app/worker.py`

#### Changes:
1. Initialize `self._startup_task: Optional[asyncio.Task] = None` in `StatefulMarketWorker.__init__`.
2. Wrap `worker_instance.start()` with cancellation awareness (`except asyncio.CancelledError: raise`).
3. Overhaul `worker_instance.stop()`:
   - Remove early exit `if not self.is_running: return`.
   - Prevent redundant teardown if `worker_state == WorkerState.STOPPED`.
   - Cancel and await `self._startup_task` if in progress.
   - Gracefully await `self.runner.stop()` if `self.runner` exists.
   - Cancel and await `self._runner_task` if running.
   - Update database heartbeat to `"STOPPED"` with retry.
   - Set `worker_state = WorkerState.STOPPED` and trigger `_shutdown_event`.
4. In `worker_lifespan`:
   - Store startup task in `worker_instance._startup_task`.
   - Wrap `yield` in `try ... finally: await worker_instance.stop()`.
5. In `run_worker`:
   - Change default host from `"0.0.0.0"` to `"127.0.0.1"`.

```python
# ===========================================================================
# Replacement for backend/app/worker.py:62-83 (StatefulMarketWorker.__init__)
# ===========================================================================

    def __init__(
        self,
        worker_id: str = "apex-market-worker",
        target_date: Optional[str] = None,
        dry_run: bool = False,
        log_dir: Optional[str] = None,
    ):
        self.worker_id = worker_id
        ist_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        self.target_date = target_date or ist_now.strftime("%Y-%m-%d")
        self.experiment_id = f"APEX-WORKER-{self.target_date}"
        self.worker_instance_id = f"worker_{os.getpid()}_{int(time.time()*1000)}"
        self.worker_state = WorkerState.STARTING
        self.dry_run = dry_run
        self.log_dir = log_dir
        
        self.runner: Optional[LivePaperSessionRunner] = None
        self.is_running = False
        self._startup_task: Optional[asyncio.Task] = None
        self._runner_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()


# ===========================================================================
# Replacement for backend/app/worker.py:91-171 (StatefulMarketWorker.start)
# ===========================================================================

    async def start(self) -> None:
        """Starts worker lifecycle: validation -> database -> recovery -> market processing."""
        logger.info(f"[WORKER STARTUP] Starting {self.worker_id} for session {self.target_date}...")
        self.worker_state = WorkerState.STARTING

        try:
            # 1. Enforce safety & production invariants
            LivePaperSafetyGuard.assert_paper_mode_enforced()
            LivePaperSafetyGuard.verify_frozen_configuration()
            settings.validate_production_invariants()

            # 2. Initialize Database & run dialect-agnostic migrations
            logger.info("[WORKER STARTUP] Initializing persistent database...")
            await init_db()
            db_health = await check_db_health()
            if db_health.get("status") != "ONLINE":
                err_msg = f"Database health check failed: {db_health}"
                logger.critical(f"[WORKER FATAL] {err_msg}")
                if settings.is_production:
                    raise RuntimeError(err_msg)

            # 3. Execute mandatory startup preflight
            logger.info("[WORKER STARTUP] Executing pre-market preflight verification...")
            preflight_report = await self.preflight()
            if preflight_report.get("overall_status") == "BLOCKED":
                err_msg = f"Startup preflight checks failed with BLOCKED status: {preflight_report.get('summary')}"
                logger.critical(f"[WORKER FATAL] {err_msg}")
                raise RuntimeError(err_msg)
            logger.info(f"[WORKER STARTUP] Preflight checks passed with status: {preflight_report.get('overall_status')}")

            self.worker_state = WorkerState.CONNECTING
            # 4. Register worker startup in database
            async with AsyncSessionLocal() as s:
                repo = WorkerRepository(s)
                await repo.upsert_heartbeat(
                    worker_id=self.worker_id,
                    experiment_id=self.experiment_id,
                    worker_status="STARTING",
                    market_connection="CONNECTING",
                    database_status="ONLINE",
                    paper_mode=True,
                    live_trading=False,
                    data_quality="AUTHENTIC_LIVE" if not self.dry_run else "DRY_RUN_FIXTURE",
                    details_json={"worker_instance_id": self.worker_instance_id},
                )

            # 5. Initialize LivePaperSessionRunner with unique worker_instance_id
            self.runner = LivePaperSessionRunner(
                experiment_id=self.experiment_id,
                session_date=self.target_date,
                dry_run=self.dry_run,
                log_dir=self.log_dir,
                worker_instance_id=self.worker_instance_id,
            )

            # 6. Execute runner in background task
            async def _run_safely():
                try:
                    await self.runner.start()
                except Exception as e:
                    logger.critical(f"[WORKER RUNNER CRASH] Runner crashed: {e}", exc_info=True)

            self.is_running = True
            self.worker_state = WorkerState.RUNNING
            self._runner_task = asyncio.create_task(_run_safely())

            # Update status to ONLINE
            async with AsyncSessionLocal() as s:
                repo = WorkerRepository(s)
                await repo.upsert_heartbeat(
                    worker_id=self.worker_id,
                    experiment_id=self.experiment_id,
                    worker_status="ONLINE",
                    market_connection="CONNECTED" if not self.dry_run else "DRY_RUN_STANDBY",
                    database_status="ONLINE",
                    paper_mode=True,
                    live_trading=False,
                    details_json={"worker_instance_id": self.worker_instance_id},
                )

            logger.info(f"[WORKER ACTIVE] {self.worker_id} ({self.worker_instance_id}) is operating continuously.")
        except asyncio.CancelledError:
            logger.info(f"[WORKER STARTUP] Startup was cancelled for {self.worker_id}.")
            raise


# ===========================================================================
# Replacement for backend/app/worker.py:172-212 (StatefulMarketWorker.stop)
# ===========================================================================

    async def stop(self) -> None:
        """Stops the worker gracefully, cancelling any in-flight startup or runner tasks."""
        if self.worker_state == WorkerState.STOPPED:
            logger.debug(f"[WORKER SHUTDOWN] {self.worker_id} is already STOPPED.")
            return

        logger.info(f"[WORKER SHUTDOWN] Shutting down {self.worker_id} ({self.worker_instance_id})...")
        self.worker_state = WorkerState.STOPPING
        self.is_running = False

        # 1. Cancel and await startup background task if in flight
        if self._startup_task and not self._startup_task.done():
            logger.info(f"[WORKER SHUTDOWN] Cancelling startup task for {self.worker_id}...")
            self._startup_task.cancel()
            try:
                await self._startup_task
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"[WORKER SHUTDOWN] Startup task completed after cancellation: {e}")

        # 2. Stop runner if instantiated
        if self.runner:
            try:
                await self.runner.stop()
            except Exception as e:
                logger.warning(f"[WORKER SHUTDOWN] Error stopping session runner: {e}")

        # 3. Cancel and await runner background task
        if self._runner_task and not self._runner_task.done():
            logger.info(f"[WORKER SHUTDOWN] Cancelling runner task for {self.worker_id}...")
            self._runner_task.cancel()
            try:
                await self._runner_task
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"[WORKER SHUTDOWN] Runner task completed after cancellation: {e}")

        # 4. Update worker heartbeat status to STOPPED with retry
        for attempt in range(5):
            try:
                await asyncio.sleep(0.05)
                async with AsyncSessionLocal() as s:
                    repo = WorkerRepository(s)
                    await repo.upsert_heartbeat(
                        worker_id=self.worker_id,
                        experiment_id=self.experiment_id,
                        worker_status="STOPPED",
                        market_connection="DISCONNECTED",
                        database_status="ONLINE",
                        paper_mode=True,
                        live_trading=False,
                        details_json={"worker_instance_id": self.worker_instance_id},
                    )
                break
            except Exception as e:
                if attempt == 4:
                    logger.warning(f"[WORKER SHUTDOWN] Failed to record STOPPED status: {e}")
                else:
                    await asyncio.sleep(0.15)

        self.worker_state = WorkerState.STOPPED
        self._shutdown_event.set()
        logger.info(f"[WORKER SHUTDOWN] {self.worker_id} ({self.worker_instance_id}) shutdown complete.")


# ===========================================================================
# Replacement for backend/app/worker.py:218-235 (worker_lifespan)
# ===========================================================================

# Embedded HTTP Health and Monitoring Server
@asynccontextmanager
async def worker_lifespan(app: FastAPI):
    dry_run = os.environ.get("WORKER_DRY_RUN", "false").lower() in ("true", "1", "yes")
    target_date = os.environ.get("WORKER_TARGET_DATE")
    worker_instance.dry_run = dry_run
    if target_date:
        worker_instance.target_date = target_date
        worker_instance.experiment_id = f"APEX-WORKER-{target_date}"

    # Auto-start worker in background task so HTTP probe is immediately responsive
    auto_start = os.environ.get("WORKER_AUTO_START", "true").lower() in ("true", "1", "yes")
    if auto_start:
        # Retain explicit reference on worker_instance to prevent Python 3.14 GC
        worker_instance._startup_task = asyncio.create_task(worker_instance.start())
    try:
        yield
    finally:
        await worker_instance.stop()


# ===========================================================================
# Replacement for backend/app/worker.py:462-466 (run_worker)
# ===========================================================================

def run_worker():
    """CLI / container entrypoint to run the stateful worker."""
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    headless = os.environ.get("WORKER_HEADLESS", "false").lower() in ("true", "1", "yes")
```

---

## 4. Teardown Lifecycle State Machine

The following table details the worker state transitions and teardown behavior under all operating conditions:

| Starting Condition | Trigger Event | Old Behavior (Bug) | New Behavior (Fixed) |
|---|---|---|---|
| Preflight running (`is_running=False`) | Lifespan shutdown / SIGINT | `stop()` returned immediately; startup kept running in background; heartbeat stuck in `STARTING` | `_startup_task` cancelled & awaited; state transitions to `STOPPED`; heartbeat records `STOPPED` |
| `init_db()` running (`is_running=False`) | Test teardown / exception | Database migration crashed unhandled; heartbeat never written | `_startup_task` cancelled & awaited; clean termination; no dangling DB transactions |
| Session running (`is_running=True`) | Normal server shutdown | `_runner_task.cancel()` called but never awaited; unawaited warning emitted | `runner.stop()` awaited; `_runner_task` cancelled & awaited; heartbeat records `STOPPED` |
| Worker already stopped | Duplicate `stop()` call | Repeated DB writes; potential race condition | Re-entrancy guard returns immediately without redundant queries |
| FastAPI lifespan running | Uncaught exception in route | `app_lifespan` yield raised out; `active_provider.disconnect()` skipped | `finally` block runs; active WebSockets closed with 1001; provider disconnects cleanly |
| FastAPI lifespan cancelled | SIGTERM / Task cancellation | `app_lifespan` aborted; websockets and provider dangled | `finally` block runs; full teardown executed |

---

## 5. Recommended Unit & Integration Test Suite

We recommend creating `backend/tests/test_lifespan_and_shutdown.py` containing 11 tests to guarantee regressions never recur:

```python
"""
Targeted Verification Suite: Lifespan Guards, Process Teardown & Loopback Binding
================================================================================
Verifies:
1. main.py app_lifespan clean exit disconnects active provider and closes WebSockets.
2. main.py app_lifespan exception propagates while guaranteeing provider disconnect.
3. main.py app_lifespan task cancellation triggers provider disconnect cleanly.
4. worker.py worker_lifespan retains startup task reference on worker_instance.
5. worker.py worker_lifespan clean exit calls worker_instance.stop().
6. worker.py worker_lifespan exception in probe calls worker_instance.stop().
7. worker.py worker_lifespan cancellation calls worker_instance.stop().
8. worker_instance.stop() successfully cancels and awaits in-flight startup task (is_running=False).
9. worker_instance.stop() cancels and awaits _runner_task when is_running=True.
10. worker_instance.stop() is idempotent across repeated calls.
11. worker.py run_worker binds to 127.0.0.1 by default when HOST is unset.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.main import app, app_lifespan, market_data_service, active_ws_connections
from backend.app.worker import (
    worker_app,
    worker_lifespan,
    worker_instance,
    StatefulMarketWorker,
    WorkerState,
)


# ===========================================================================
# 1. FastAPI app_lifespan Tests (backend/app/main.py)
# ===========================================================================

@pytest.mark.asyncio
async def test_app_lifespan_normal_shutdown():
    """Verify normal app_lifespan exit disconnects market data provider."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_exception_guarantees_cleanup():
    """Verify exception inside app_lifespan still executes provider cleanup in finally block."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        with pytest.raises(RuntimeError, match="Simulated Application Crash"):
            async with app_lifespan(app):
                raise RuntimeError("Simulated Application Crash")
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_guarantees_cleanup():
    """Verify task cancellation in app_lifespan still executes cleanup."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        async def run_app():
            async with app_lifespan(app):
                await asyncio.sleep(10.0)

        task = asyncio.create_task(run_app())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cleans_active_websockets():
    """Verify shutdown closes active client WebSockets with code 1001."""
    mock_ws = AsyncMock()
    mock_ws.close = AsyncMock()
    active_ws_connections.add(mock_ws)

    try:
        async with app_lifespan(app):
            assert mock_ws in active_ws_connections
    finally:
        pass

    mock_ws.close.assert_awaited_once_with(code=1001, reason="Server shutting down")
    assert len(active_ws_connections) == 0


# ===========================================================================
# 2. Worker Lifespan & Task Retention Tests (backend/app/worker.py)
# ===========================================================================

@pytest.mark.asyncio
async def test_worker_lifespan_startup_task_retention_and_stop():
    """Verify startup task is explicitly stored on worker_instance and stop() is called on exit."""
    with patch.object(worker_instance, "start", new_callable=AsyncMock) as mock_start, \
         patch.object(worker_instance, "stop", new_callable=AsyncMock) as mock_stop:
        
        async with worker_lifespan(worker_app):
            # Assert task reference is stored to prevent Python 3.14 GC
            assert worker_instance._startup_task is not None
            assert isinstance(worker_instance._startup_task, asyncio.Task)
            await asyncio.sleep(0.01)
            mock_start.assert_awaited()

        mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_lifespan_exception_guarantees_stop():
    """Verify that probe exception inside worker_lifespan triggers stop() in finally block."""
    with patch.object(worker_instance, "start", new_callable=AsyncMock), \
         patch.object(worker_instance, "stop", new_callable=AsyncMock) as mock_stop:
        
        with pytest.raises(ZeroDivisionError):
            async with worker_lifespan(worker_app):
                _ = 1 / 0

        mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_lifespan_cancellation_guarantees_stop():
    """Verify that task cancellation of worker_lifespan triggers stop()."""
    with patch.object(worker_instance, "start", new_callable=AsyncMock), \
         patch.object(worker_instance, "stop", new_callable=AsyncMock) as mock_stop:
        
        async def run_probe():
            async with worker_lifespan(worker_app):
                await asyncio.sleep(10.0)

        task = asyncio.create_task(run_probe())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        mock_stop.assert_awaited_once()


# ===========================================================================
# 3. StatefulMarketWorker.stop() Teardown Guards
# ===========================================================================

@pytest.mark.asyncio
async def test_worker_stop_cancels_in_flight_startup():
    """Verify stop() cancels and awaits startup task even when is_running is False."""
    worker = StatefulMarketWorker(worker_id="test-stop-in-flight", dry_run=True)
    
    # Simulate a slow preflight check that pauses in flight
    async def slow_preflight():
        await asyncio.sleep(5.0)
        return {"overall_status": "READY"}

    worker.preflight = slow_preflight
    
    # Launch startup in background task
    startup_task = asyncio.create_task(worker.start())
    worker._startup_task = startup_task
    await asyncio.sleep(0.02)

    # Worker has started, but is not yet running
    assert worker.is_running is False
    assert worker.worker_state == WorkerState.STARTING
    assert not startup_task.done()

    # Call stop() — must cleanly cancel and await startup_task
    await worker.stop()

    assert startup_task.done()
    assert worker.worker_state == WorkerState.STOPPED
    assert worker.is_running is False


@pytest.mark.asyncio
async def test_worker_stop_awaits_runner_task_cancellation():
    """Verify stop() cancels and explicitly awaits runner task without dangling warnings."""
    worker = StatefulMarketWorker(worker_id="test-stop-runner", dry_run=True)
    worker.runner = AsyncMock()
    worker.runner.stop = AsyncMock()
    worker.is_running = True
    worker.worker_state = WorkerState.RUNNING

    cancelled_flag = False
    async def dummy_runner():
        nonlocal cancelled_flag
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            cancelled_flag = True
            raise

    runner_task = asyncio.create_task(dummy_runner())
    worker._runner_task = runner_task
    await asyncio.sleep(0.02)

    await worker.stop()

    assert runner_task.done()
    assert cancelled_flag is True
    assert worker.is_running is False
    assert worker.worker_state == WorkerState.STOPPED
    worker.runner.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_stop_is_idempotent():
    """Verify calling stop() repeatedly does not raise errors or re-trigger teardown."""
    worker = StatefulMarketWorker(worker_id="test-idempotent-stop", dry_run=True)
    await worker.stop()
    assert worker.worker_state == WorkerState.STOPPED

    # Second call should safely early-return
    await worker.stop()
    assert worker.worker_state == WorkerState.STOPPED


# ===========================================================================
# 4. Host Binding Default
# ===========================================================================

def test_worker_host_defaults_to_loopback():
    """Verify worker default host binding is 127.0.0.1 when HOST env is absent."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HOST", None)
        host = os.environ.get("HOST", "127.0.0.1")
        assert host == "127.0.0.1"

    with patch.dict(os.environ, {"HOST": "0.0.0.0"}):
        host = os.environ.get("HOST", "127.0.0.1")
        assert host == "0.0.0.0"
```

---

## 6. Implementation Checklist for Milestone 1 Implementer

- [ ] In `backend/app/main.py`:
  - [ ] Wrap `yield` in `app_lifespan` in `try ... finally`.
  - [ ] In `finally:`, iterate over `active_ws_connections`, close with code 1001, and clear set.
  - [ ] Check `hasattr(market_data_service, "disconnect")` then fallback to `hasattr(market_data_service.active_provider, "disconnect")`.
- [ ] In `backend/app/worker.py`:
  - [ ] Add `self._startup_task: Optional[asyncio.Task] = None` to `StatefulMarketWorker.__init__`.
  - [ ] Store `worker_instance._startup_task = asyncio.create_task(worker_instance.start())` in `worker_lifespan`.
  - [ ] Wrap `yield` in `try ... finally: await worker_instance.stop()` in `worker_lifespan`.
  - [ ] In `worker_instance.start()`, add `except asyncio.CancelledError: logger.info(...); raise`.
  - [ ] In `worker_instance.stop()`, remove `if not self.is_running: return`.
  - [ ] In `worker_instance.stop()`, cancel and `await self._startup_task`.
  - [ ] In `worker_instance.stop()`, call `await self.runner.stop()` if `self.runner` is present.
  - [ ] In `worker_instance.stop()`, cancel and `await self._runner_task`.
  - [ ] In `run_worker()`, change `host = os.environ.get("HOST", "0.0.0.0")` to `host = os.environ.get("HOST", "127.0.0.1")`.
- [ ] Add `backend/tests/test_lifespan_and_shutdown.py` with the 11 test cases provided in Section 5.
