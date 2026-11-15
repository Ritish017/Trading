"""
Empirical Verification Script for Lifespan Teardown & Signal Expiry
Run with: python backend/tests/verify_challenger_lifespan_and_expiry.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import (
    app,
    market_data_service,
    ensure_initialized,
    app_lifespan,
    paper_engine,
)
from backend.app.signal_engine.signal_store import signal_store
from backend.app.signal_engine.models import (
    SignalDecision,
    SignalDirection,
    SignalType,
    SignalState,
    SignalQualityGrade,
    StopLossResult,
    TargetLevel,
    PositionSizing,
)


def run_all_checks():
    results = {}

    print("=================================================================")
    print("STEP 1: EMPIRICAL LIFESPAN TEARDOWN & PROVIDER DISCONNECT CHECKS")
    print("=================================================================")

    async def check_lifespan():
        # Ensure initialized
        await ensure_initialized()

        # 1.1 Direct disconnect test
        print("[1.1] Testing MarketDataService.disconnect() directly...")
        provider_disconnect_called = False
        original_provider = market_data_service.active_provider

        mock_provider = AsyncMock()
        async def mock_disc():
            nonlocal provider_disconnect_called
            provider_disconnect_called = True
        mock_provider.disconnect = mock_disc
        mock_provider.provider_name = "MOCK_PROVIDER"

        market_data_service.active_provider = mock_provider
        market_data_service.is_live = True
        market_data_service.status_code = "CONNECTED"

        # Check tasks before
        tasks_before = [t for t in asyncio.all_tasks() if not t.done()]

        await market_data_service.disconnect()

        tasks_after = [t for t in asyncio.all_tasks() if not t.done()]
        leaked_tasks = set(tasks_after) - set(tasks_before)

        assert provider_disconnect_called, "active_provider.disconnect() was NOT called!"
        assert market_data_service.is_live is False, "market_data_service.is_live is not False!"
        assert market_data_service.status_code == "DISCONNECTED", f"status_code is {market_data_service.status_code}, expected DISCONNECTED"
        assert market_data_service.provider_mode == "UNAVAILABLE", f"provider_mode is {market_data_service.provider_mode}, expected UNAVAILABLE"
        assert len(leaked_tasks) == 0, f"Leaked tasks detected: {leaked_tasks}"
        print("  -> PASS: MarketDataService.disconnect() executed cleanly, delegate called, no leaked tasks.")

        # 1.2 Provider disconnect exception handling
        print("[1.2] Testing MarketDataService.disconnect() provider exception resilience...")
        failing_provider = AsyncMock()
        failing_provider.disconnect.side_effect = RuntimeError("Provider disconnect network error")
        failing_provider.provider_name = "FAILING_PROVIDER"
        market_data_service.active_provider = failing_provider
        market_data_service.is_live = True
        market_data_service.status_code = "CONNECTED"

        # Must not raise
        await market_data_service.disconnect()
        assert market_data_service.is_live is False
        assert market_data_service.status_code == "DISCONNECTED"
        assert market_data_service.provider_mode == "UNAVAILABLE"
        print("  -> PASS: MarketDataService.disconnect() gracefully caught provider exception and transitioned state.")

        # Restore original provider
        market_data_service.active_provider = original_provider

        # 1.3 Full app_lifespan context manager execution
        print("[1.3] Testing full app_lifespan context manager teardown...")
        lifespan_provider_called = False
        async def mock_life_disc():
            nonlocal lifespan_provider_called
            lifespan_provider_called = True

        with patch.object(market_data_service, "disconnect", new_callable=AsyncMock) as mock_svc_disc:
            async with app_lifespan(app):
                pass
            mock_svc_disc.assert_awaited_once()
        print("  -> PASS: app_lifespan triggers market_data_service.disconnect() in finally block.")

    asyncio.run(check_lifespan())
    results["lifespan_teardown"] = "PASS"

    print("\n=================================================================")
    print("STEP 2: EMPIRICAL SIGNAL EXPIRY FAIL-CLOSED CHECKS")
    print("=================================================================")

    # Configure client and auth
    settings.api_auth_token = "challenger-secret-token-2026"
    client = TestClient(app)
    headers = {"X-API-Key": "challenger-secret-token-2026"}

    def make_test_signal(signal_id: str, expiry_value: str) -> SignalDecision:
        return SignalDecision(
            signal_id=signal_id,
            symbol="RELIANCE.NS",
            direction=SignalDirection.LONG,
            signal_type=SignalType.EQUITY_LONG,
            state=SignalState.QUALIFIED,
            quality_grade=SignalQualityGrade.A,
            entry=2500.0,
            stop_loss=StopLossResult(
                price=2450.0,
                method="STRUCTURAL",
                method_description="Stop below 2450",
                risk_per_share=50.0,
            ),
            targets=[
                TargetLevel(
                    level=1,
                    price=2600.0,
                    method="RISK_REWARD",
                    method_description="2:1 target",
                    expected_rr=2.0,
                )
            ],
            position_size=PositionSizing(
                method="FIXED_RISK",
                capital=1000000.0,
                risk_per_trade_pct=1.0,
                max_risk_amount=10000.0,
                entry_price=2500.0,
                stop_price=2450.0,
                risk_per_share=50.0,
                quantity=10,
                capital_required=25000.0,
                maximum_loss=500.0,
            ),
            expiry=expiry_value,
        )

    # 2.1 Expired ISO timestamp (2020-01-01T00:00:00Z)
    print("[2.1] Testing expired ISO timestamp ('2020-01-01T00:00:00Z')...")
    sig_iso_id = f"test-sig-iso-{uuid.uuid4().hex[:6]}"
    sig_iso = make_test_signal(sig_iso_id, "2020-01-01T00:00:00Z")
    signal_store.upsert_signal(sig_iso)

    res_iso = client.post(
        f"/api/signals/{sig_iso_id}/paper-trade",
        json={"signal_id": sig_iso_id},
        headers=headers,
    )
    print(f"  Status code: {res_iso.status_code}, Response: {res_iso.text}")
    assert res_iso.status_code == 400, f"Expected 400 but got {res_iso.status_code}"
    assert "Invalid or expired signal timestamp" in res_iso.json()["detail"]
    assert sig_iso.state == "EXPIRED", f"Expected signal.state == 'EXPIRED' but got {sig_iso.state}"
    print("  -> PASS: Rejected with 400, detail matched, signal transitioned to EXPIRED.")
    results["expired_iso"] = "PASS"

    # 2.2 Naive past datetime string (2020-01-01 12:00:00)
    print("[2.2] Testing naive past datetime string ('2020-01-01 12:00:00')...")
    sig_naive_id = f"test-sig-naive-{uuid.uuid4().hex[:6]}"
    sig_naive = make_test_signal(sig_naive_id, "2020-01-01 12:00:00")
    signal_store.upsert_signal(sig_naive)

    res_naive = client.post(
        f"/api/signals/{sig_naive_id}/paper-trade",
        json={"signal_id": sig_naive_id},
        headers=headers,
    )
    print(f"  Status code: {res_naive.status_code}, Response: {res_naive.text}")
    assert res_naive.status_code == 400, f"Expected 400 but got {res_naive.status_code}"
    assert "Invalid or expired signal timestamp" in res_naive.json()["detail"]
    assert sig_naive.state == "EXPIRED", f"Expected signal.state == 'EXPIRED' but got {sig_naive.state}"
    print("  -> PASS: Rejected with 400, detail matched, signal transitioned to EXPIRED.")
    results["naive_past"] = "PASS"

    # 2.3 Corrupt timestamp string ("corrupt-invalid-timestamp-xyz")
    print("[2.3] Testing corrupt timestamp string ('corrupt-invalid-timestamp-xyz')...")
    sig_corrupt_id = f"test-sig-corrupt-{uuid.uuid4().hex[:6]}"
    sig_corrupt = make_test_signal(sig_corrupt_id, "corrupt-invalid-timestamp-xyz")
    signal_store.upsert_signal(sig_corrupt)

    res_corrupt = client.post(
        f"/api/signals/{sig_corrupt_id}/paper-trade",
        json={"signal_id": sig_corrupt_id},
        headers=headers,
    )
    print(f"  Status code: {res_corrupt.status_code}, Response: {res_corrupt.text}")
    assert res_corrupt.status_code == 400, f"Expected 400 but got {res_corrupt.status_code}"
    assert "Invalid or expired signal timestamp" in res_corrupt.json()["detail"]
    print("  -> PASS: Rejected with 400, detail matched fail-closed.")
    results["corrupt_timestamp"] = "PASS"

    # 2.4 Valid future timestamp (UTC now + 2 hours)
    future_time_iso = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    print(f"[2.4] Testing valid future timestamp ('{future_time_iso}')...")
    sig_future_id = f"test-sig-future-{uuid.uuid4().hex[:6]}"
    sig_future = make_test_signal(sig_future_id, future_time_iso)
    signal_store.upsert_signal(sig_future)

    res_future = client.post(
        f"/api/signals/{sig_future_id}/paper-trade",
        json={"signal_id": sig_future_id},
        headers=headers,
    )
    print(f"  Status code: {res_future.status_code}, Response: {res_future.text}")
    assert res_future.status_code == 200, f"Expected 200 but got {res_future.status_code}: {res_future.text}"
    body = res_future.json()
    assert body["order_result"]["status"] == "FILLED", f"Expected FILLED but got {body['order_result']['status']}"
    assert sig_future.state == "TRIGGERED", f"Expected TRIGGERED but got {sig_future.state}"
    print("  -> PASS: Accepted with 200, order status FILLED, signal transitioned to TRIGGERED.")
    results["valid_future"] = "PASS"

    print("\n=================================================================")
    print("ALL EMPIRICAL CHECKS PASSED PERFECTLY!")
    print(f"Summary: {results}")
    print("=================================================================")
    return results


if __name__ == "__main__":
    run_all_checks()
