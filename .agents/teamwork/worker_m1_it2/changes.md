# Baseline Integrity Remediation Changes (Milestone 1 Iteration 2)

**Agent**: `teamwork_preview_worker`  
**Date**: 2026-10-06  
**Milestone**: Milestone 1 Iteration 2  

---

## 1. `backend/app/market_data/service.py`
- **Change**: Added native `disconnect()` asynchronous method to `MarketDataService`.
- **Details**:
  ```python
  async def disconnect(self) -> None:
      """Gracefully disconnect active provider and mark service as disconnected."""
      if self.active_provider and hasattr(self.active_provider, "disconnect"):
          try:
              await self.active_provider.disconnect()
              logger.info(f"[MARKET DATA HUB] Active provider ({getattr(self.active_provider, 'provider_name', 'UNKNOWN')}) disconnected cleanly.")
          except Exception as e:
              logger.warning(f"[MARKET DATA HUB] Error disconnecting active provider: {e}")
      self.is_live = False
      self.status_code = "DISCONNECTED"
      self.provider_mode = "UNAVAILABLE"
  ```
- **Rationale**: Completes the lifecycle contract expected by `backend/app/main.py:141` (`if hasattr(market_data_service, "disconnect"): await market_data_service.disconnect()`). Gracefully delegates to `self.active_provider.disconnect()` and updates internal health states.

---

## 2. `backend/tests/test_lifespans_hardening.py`
- **Change**: Added `ensure_initialized` import and `setup_app_lifecycle` autouse fixture; updated lifespan teardown tests.
- **Details**:
  - Imported `ensure_initialized` from `backend.app.main`.
  - Added `@pytest.fixture(autouse=True) async def setup_app_lifecycle(): await ensure_initialized()`.
  - In `test_app_lifespan_normal_shutdown`, ensures provider is initialized before attaching `patch.object(market_data_service.active_provider, "disconnect", mock_disconnect)`, preventing provider reassignment during startup from unlinking the mock.
  - Added `test_app_lifespan_market_data_service_disconnect_cleanly` to verify top-level `market_data_service.disconnect()` invocation.
  - Hardened `test_app_lifespan_exception_guarantees_cleanup` and `test_app_lifespan_cancellation_guarantees_cleanup` with pre-initialization.

---

## 3. `backend/app/main.py`
- **Changes**:
  1. **Purged External Probe URLs**: Verified 0 occurrences of `https://apex-market-worker-probe.onrender.com`. All worker health and status probes strictly use `LOCAL_WORKER_URL` with local loopback validation (`127.0.0.1` or `localhost`).
  2. **Signal Expiry Validation**: Hardened timestamp parsing in `/api/signals/{signal_id}/paper-trade`:
     - Accepts `datetime` objects, ISO-8601 strings (handling trailing `'Z'` into `'+00:00'`), and numeric unix epoch timestamps.
     - Normalizes naive datetimes to UTC timezone awareness via `.replace(tzinfo=timezone.utc)` and converts aware datetimes to UTC via `.astimezone(timezone.utc)`.
     - Validates current time `datetime.now(timezone.utc) > expiry_dt`, sets `signal.state = "EXPIRED"`, and fails closed with `HTTPException(status_code=400, detail="Invalid or expired signal timestamp")`.
     - Catches any parse/comparison errors, logs warning, and fails closed with `HTTPException(status_code=400, detail="Invalid or expired signal timestamp")`.

---

## 4. E2E Test Suite Imports & Identifiers
- **`backend/tests/e2e/test_tier1_features.py`**:
  - Replaced `OptionsDecisionEngine` with `OptionsEngine` in imports (line 40) and test instantiations (line 242).
  - Replaced `FuturesDecisionEngine` with `FuturesEngine` in imports (line 46) and test instantiations (line 277).
- **`backend/tests/e2e/test_tier2_boundaries.py`**:
  - Replaced `OptionsDecisionEngine` with `OptionsEngine` in imports (line 41) and test instantiations (line 254).
  - Replaced `FuturesDecisionEngine` with `FuturesEngine` in imports (line 47).
- **`backend/tests/e2e/test_tier3_combinations.py`**:
  - Replaced `OptionsDecisionEngine` with `OptionsEngine` in imports (line 33) and test instantiations (line 164).
- **`backend/tests/e2e/test_tier4_scenarios.py`**:
  - Removed `ValidationGateResult` from `backend.app.signal_engine.models` import and imported `ValidationGateResult` from `backend.app.signal_engine.validation_gates` (lines 25, 30).
