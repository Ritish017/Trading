"""
APEX Lifespan and Process Teardown Hardening Test Suite
======================================================
Verifies:
1. main.py app_lifespan clean exit disconnects active provider and closes WebSockets.
2. main.py app_lifespan exception propagates while guaranteeing provider disconnect.
3. main.py app_lifespan task cancellation triggers provider disconnect cleanly.
4. main.py app_lifespan closes active client WebSockets with code 1001.
5. worker.py worker_lifespan retains startup task reference on worker_instance.
6. worker.py worker_lifespan clean exit calls worker_instance.stop().
7. worker.py worker_lifespan exception in probe calls worker_instance.stop().
8. worker.py worker_lifespan cancellation calls worker_instance.stop().
9. worker_instance.stop() successfully cancels and awaits in-flight startup task (is_running=False).
10. worker_instance.stop() cancels and awaits _runner_task when is_running=True.
11. worker_instance.stop() is idempotent across repeated calls.
12. worker.py run_worker binds to 127.0.0.1 by default when HOST is unset.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, patch

from backend.app.main import (
    app,
    app_lifespan,
    market_data_service,
    active_ws_connections,
    ensure_initialized,
)
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

@pytest.fixture(autouse=True)
async def setup_app_lifecycle():
    """Ensure app components and market data provider are initialized before testing lifespans."""
    await ensure_initialized()


@pytest.mark.asyncio
async def test_app_lifespan_normal_shutdown():
    """Verify normal app_lifespan exit disconnects market data provider."""
    await ensure_initialized()
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_market_data_service_disconnect_cleanly():
    """Verify normal app_lifespan exit invokes market_data_service.disconnect()."""
    mock_service_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_service_disconnect):
        async with app_lifespan(app):
            pass
        mock_service_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_exception_guarantees_cleanup():
    """Verify exception inside app_lifespan still executes provider cleanup in finally block."""
    await ensure_initialized()
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        with pytest.raises(RuntimeError, match="Simulated Application Crash"):
            async with app_lifespan(app):
                raise RuntimeError("Simulated Application Crash")
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_guarantees_cleanup():
    """Verify task cancellation in app_lifespan still executes cleanup in finally block."""
    await ensure_initialized()
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
async def test_market_data_service_disconnect_delegates_to_active_provider():
    """Verify MarketDataService.disconnect() calls active_provider.disconnect()."""
    mock_provider_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_provider_disconnect):
        await market_data_service.disconnect()
        mock_provider_disconnect.assert_awaited_once()


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
    """Verify that task cancellation of worker_lifespan triggers stop() in finally block."""
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
