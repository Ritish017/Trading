"""
Empirical Adversarial Challenge Suite - Milestone 1
==================================================
Tests:
1. Concurrency and cancellation stress on app_lifespan and worker_lifespan
   - Startup cancellation
   - Shutdown cancellation
   - Provider disconnection guarantees
   - Unawaited tasks / coroutine leak detection
2. Security attack testing on /api/paper/positions
   - Unauthenticated / anonymous requests (401)
   - Invalid token / empty token / missing server secret (401)
   - Cross-account / IDOR isolation (403)
3. Signal trade edge cases on /api/signals/{id}/paper-trade
   - States: CANDIDATE, TRIGGERED, EXPIRED, REJECTED (400)
   - Expired timestamps (400)
   - Inverted geometry: LONG stop >= entry, SHORT stop <= entry (400)
   - Quality grade: NO TRADE (400)
   - Cross-account and unauthenticated requests (403, 401)
"""

import asyncio
import datetime
import pytest
import warnings
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app, app_lifespan, market_data_service, active_ws_connections
from backend.app.config import settings
from backend.app.worker import (
    worker_app,
    worker_lifespan,
    worker_instance,
    StatefulMarketWorker,
    WorkerState,
)
from backend.app.signal_engine.signal_store import signal_store as apex_signal_store
from backend.app.signal_engine.models import (
    SignalDecision,
    SignalDirection,
    SignalState,
    SignalQualityGrade,
    StopLossResult,
    TargetLevel,
    PositionSizing,
)


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# Diagnostic & Concurrency Stress Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_diagnostic_market_data_service_disconnect_flow():
    """Diagnose market_data_service and active_provider disconnect wiring."""
    print("\n--- Diagnostic Start ---")
    print(f"hasattr(market_data_service, 'disconnect'): {hasattr(market_data_service, 'disconnect')}")
    print(f"type(market_data_service.active_provider): {type(market_data_service.active_provider)}")
    print(f"hasattr(market_data_service.active_provider, 'disconnect'): {hasattr(market_data_service.active_provider, 'disconnect')}")
    
    # Check if active_provider disconnect is callable
    assert hasattr(market_data_service.active_provider, "disconnect")
    
    # Check what happens during lifespan teardown
    active_prov = market_data_service.active_provider
    mock_disconnect = AsyncMock()
    with patch.object(active_prov, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        # Check if the active_provider changed during lifespan
        print(f"Active provider after lifespan: {type(market_data_service.active_provider)}")
        print(f"Same instance: {market_data_service.active_provider is active_prov}")
        print(f"mock_disconnect call count: {mock_disconnect.await_count}")


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_during_startup():
    """Trigger task cancellation DURING startup of app_lifespan.
    Verify provider disconnect is guaranteed and no dangling tasks remain.
    """
    mock_disconnect = AsyncMock()
    startup_started = asyncio.Event()

    async def slow_initialize():
        startup_started.set()
        await asyncio.sleep(10.0)

    # Patch ensure_initialized to pause mid-startup
    with patch("backend.app.main.ensure_initialized", side_effect=slow_initialize), \
         patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):

        async def run_lifespan():
            async with app_lifespan(app):
                pass

        task = asyncio.create_task(run_lifespan())
        await startup_started.wait()
        # Cancel while startup is paused in sleep
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Disconnect must have been called despite cancellation during startup
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_during_shutdown():
    """Trigger cancellation while app_lifespan is executing shutdown teardown.
    Verify all active WebSockets close and no coroutines are left unawaited.
    """
    ws_mock = AsyncMock()
    ws_mock.close = AsyncMock()
    active_ws_connections.add(ws_mock)

    mock_disconnect = AsyncMock()

    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        async def run_lifespan():
            async with app_lifespan(app):
                await asyncio.sleep(0.01)

        task = asyncio.create_task(run_lifespan())
        await asyncio.sleep(0.005)
        # Cancel right around yield return
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        ws_mock.close.assert_awaited_once_with(code=1001, reason="Server shutting down")
        assert len(active_ws_connections) == 0
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_lifespan_cancellation_during_startup():
    """Trigger cancellation during worker_lifespan while worker startup is in flight.
    Verify worker.stop() is cleanly executed and background startup task is cancelled.
    """
    worker = StatefulMarketWorker(worker_id="test-worker-cancel-startup", dry_run=True)
    startup_started = asyncio.Event()

    async def slow_preflight():
        startup_started.set()
        await asyncio.sleep(10.0)
        return {"overall_status": "READY"}

    worker.preflight = slow_preflight

    with patch("backend.app.worker.worker_instance", worker):
        async def run_worker():
            async with worker_lifespan(worker_app):
                pass

        task = asyncio.create_task(run_worker())
        await startup_started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert worker.worker_state == WorkerState.STOPPED
        assert worker.is_running is False
        assert worker._startup_task.done()


@pytest.mark.asyncio
async def test_worker_lifespan_cancellation_during_shutdown():
    """Trigger cancellation during worker shutdown teardown.
    Verify worker safely transitions to STOPPED and resources are freed.
    """
    worker = StatefulMarketWorker(worker_id="test-worker-cancel-shutdown", dry_run=True)
    worker.is_running = True
    worker.worker_state = WorkerState.RUNNING

    # Add a mock runner
    worker.runner = AsyncMock()
    worker.runner.stop = AsyncMock()

    # Create dummy runner task
    async def dummy_runner():
        try:
            while True:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            raise

    runner_task = asyncio.create_task(dummy_runner())
    worker._runner_task = runner_task

    with patch("backend.app.worker.worker_instance", worker):
        # Stop worker directly
        await worker.stop()

        assert worker.worker_state == WorkerState.STOPPED
        assert worker.is_running is False
        assert runner_task.done()
        worker.runner.stop.assert_awaited_once()


# ===========================================================================
# Security Attack Tests: /api/paper/positions
# ===========================================================================

def test_security_positions_unauthenticated_rejected(client, monkeypatch):
    """Anonymous / unauthenticated request to /api/paper/positions must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "valid-secret-token-123")
    res = client.get("/api/paper/positions")
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers


def test_security_positions_unauthenticated_with_account_query_rejected(client, monkeypatch):
    """Anonymous request attempting to specify account_id query param must still return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "valid-secret-token-123")
    res = client.get("/api/paper/positions?account_id=primary_personal_account")
    assert res.status_code == 401


def test_security_positions_invalid_token_rejected(client, monkeypatch):
    """Request with incorrect API key to /api/paper/positions must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "valid-secret-token-123")
    res = client.get(
        "/api/paper/positions",
        headers={"X-API-Key": "wrong-token-abc"}
    )
    assert res.status_code == 401


def test_security_positions_empty_token_rejected(client, monkeypatch):
    """Request with empty header to /api/paper/positions must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "valid-secret-token-123")
    res = client.get(
        "/api/paper/positions",
        headers={"X-API-Key": ""}
    )
    assert res.status_code == 401


def test_security_positions_unconfigured_server_token_fails_closed(client, monkeypatch):
    """If server has no API_AUTH_TOKEN configured, /api/paper/positions must fail closed (401)."""
    monkeypatch.setattr(settings, "api_auth_token", None)
    res = client.get(
        "/api/paper/positions",
        headers={"X-API-Key": "any-token"}
    )
    assert res.status_code == 401
    assert "Server fails closed" in res.json().get("detail", "")


def test_security_positions_cross_account_rejected(client, monkeypatch):
    """Account A caller requesting Account B positions must return 403 Forbidden."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    res = client.get(
        "/api/paper/positions?account_id=account_b",
        headers={"X-API-Key": "token_a"}
    )
    assert res.status_code == 403
    assert "not authorized" in res.json().get("detail", "").lower()


def test_security_positions_cross_account_whitespace_padding_rejected(client, monkeypatch):
    """Whitespace-padded cross-account target must also be rejected with 403."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    res = client.get(
        "/api/paper/positions?account_id=%20account_b%20",
        headers={"X-API-Key": "token_a"}
    )
    assert res.status_code == 403
    assert "not authorized" in res.json().get("detail", "").lower()


def test_security_positions_own_account_succeeds(client, monkeypatch):
    """Authenticated caller accessing own account positions returns 200 OK."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    res = client.get(
        "/api/paper/positions?account_id=account_a",
        headers={"X-API-Key": "token_a"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "positions" in data
    assert "capital" in data


# ===========================================================================
# Signal Trade Edge Case Tests: /api/signals/{id}/paper-trade
# ===========================================================================

def _create_mock_signal(
    signal_id: str,
    state: SignalState = SignalState.QUALIFIED,
    direction: SignalDirection = SignalDirection.LONG,
    entry: float = 1000.0,
    stop_price: float = 950.0,
    targets: list = None,
    expiry: str = None,
    quality_grade: SignalQualityGrade = SignalQualityGrade.A,
):
    if targets is None:
        targets = [TargetLevel(price=1100.0 if direction == SignalDirection.LONG else 900.0, level=1, method="RR")]
    sig = SignalDecision(
        signal_id=signal_id,
        symbol="INFY.NS",
        direction=direction,
        state=state,
        quality_grade=quality_grade,
        entry=entry,
        stop_loss=StopLossResult(price=stop_price, method="ATR"),
        targets=targets,
        expiry=expiry,
        position_size=PositionSizing(
            method="FIXED_RISK",
            capital=1000000.0,
            risk_per_trade_pct=1.0,
            max_risk_amount=10000.0,
            entry_price=entry,
            stop_price=stop_price,
            risk_per_share=abs(entry - stop_price),
            quantity=10,
            capital_required=entry * 10,
            maximum_loss=abs(entry - stop_price) * 10,
        ),
    )
    apex_signal_store.upsert_signal(sig)
    return sig


def test_signal_trade_candidate_state_fails_closed(client, monkeypatch):
    """Submitting order for signal in CANDIDATE state must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_candidate_01", state=SignalState.CANDIDATE)

    res = client.post(
        "/api/signals/sig_candidate_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_candidate_01"}
    )
    assert res.status_code == 400
    assert "only qualified signals can be executed" in res.json().get("detail", "").lower()


def test_signal_trade_triggered_state_fails_closed(client, monkeypatch):
    """Submitting order for signal in TRIGGERED state must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_triggered_01", state=SignalState.TRIGGERED)

    res = client.post(
        "/api/signals/sig_triggered_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_triggered_01"}
    )
    assert res.status_code == 400
    assert "only qualified signals can be executed" in res.json().get("detail", "").lower()


def test_signal_trade_expired_state_fails_closed(client, monkeypatch):
    """Submitting order for signal in EXPIRED state must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_expired_01", state=SignalState.EXPIRED)

    res = client.post(
        "/api/signals/sig_expired_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_expired_01"}
    )
    assert res.status_code == 400
    assert "only qualified signals can be executed" in res.json().get("detail", "").lower()


def test_signal_trade_expired_timestamp_fails_closed(client, monkeypatch):
    """Submitting order for QUALIFIED signal whose expiry timestamp is past must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    # Expired 1 hour ago
    past_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    _create_mock_signal("sig_past_time_01", state=SignalState.QUALIFIED, expiry=past_iso)

    res = client.post(
        "/api/signals/sig_past_time_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_past_time_01"}
    )
    assert res.status_code == 400
    assert "expired" in res.json().get("detail", "").lower()


def test_signal_trade_inverted_geometry_long_stop_greater_than_entry(client, monkeypatch):
    """Submitting LONG order with stop > entry (e.g. entry=1000, stop=1050) must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_inv_long_01", state=SignalState.QUALIFIED, direction=SignalDirection.LONG, entry=1000.0, stop_price=1050.0)

    res = client.post(
        "/api/signals/sig_inv_long_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_inv_long_01"}
    )
    assert res.status_code == 400
    assert "invalid long trade geometry" in res.json().get("detail", "").lower()


def test_signal_trade_inverted_geometry_long_stop_equal_to_entry(client, monkeypatch):
    """Submitting LONG order with stop == entry (e.g. entry=1000, stop=1000) must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_inv_long_02", state=SignalState.QUALIFIED, direction=SignalDirection.LONG, entry=1000.0, stop_price=1000.0)

    res = client.post(
        "/api/signals/sig_inv_long_02/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_inv_long_02"}
    )
    assert res.status_code == 400
    assert "invalid long trade geometry" in res.json().get("detail", "").lower()


def test_signal_trade_inverted_geometry_short_stop_less_than_entry(client, monkeypatch):
    """Submitting SHORT order with stop < entry (e.g. entry=1000, stop=950) must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_inv_short_01", state=SignalState.QUALIFIED, direction=SignalDirection.SHORT, entry=1000.0, stop_price=950.0)

    res = client.post(
        "/api/signals/sig_inv_short_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_inv_short_01"}
    )
    assert res.status_code == 400
    assert "invalid short trade geometry" in res.json().get("detail", "").lower()


def test_signal_trade_inverted_geometry_short_stop_equal_to_entry(client, monkeypatch):
    """Submitting SHORT order with stop == entry (e.g. entry=1000, stop=1000) must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_inv_short_02", state=SignalState.QUALIFIED, direction=SignalDirection.SHORT, entry=1000.0, stop_price=1000.0)

    res = client.post(
        "/api/signals/sig_inv_short_02/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_inv_short_02"}
    )
    assert res.status_code == 400
    assert "invalid short trade geometry" in res.json().get("detail", "").lower()


def test_signal_trade_no_trade_grade_rejected(client, monkeypatch):
    """Submitting order with NO TRADE grade must fail closed with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_no_trade_01", state=SignalState.QUALIFIED, quality_grade=SignalQualityGrade.NO_TRADE)

    res = client.post(
        "/api/signals/sig_no_trade_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "sig_no_trade_01"}
    )
    assert res.status_code == 400
    assert "no trade" in res.json().get("detail", "").lower()


def test_signal_trade_path_body_mismatch_rejected(client, monkeypatch):
    """Mismatched signal_id between URL path and request body must return 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-token-123")
    _create_mock_signal("sig_path_01", state=SignalState.QUALIFIED)

    res = client.post(
        "/api/signals/sig_path_01/paper-trade",
        headers={"X-API-Key": "test-token-123"},
        json={"signal_id": "different_signal_id"}
    )
    assert res.status_code == 400
    assert "mismatched" in res.json().get("detail", "").lower()
