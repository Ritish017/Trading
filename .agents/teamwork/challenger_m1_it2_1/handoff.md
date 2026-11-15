# Lifespan & Expiry Challenger Empirical Handoff Report

**Agent**: `teamwork_preview_challenger` (Lifespan & Expiry Challenger)  
**Parent Agent**: `b0e006c7-614f-4aa0-b311-d567b4a1a31b`  
**Milestone**: Milestone 1 Iteration 2  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\challenger_m1_it2_1\`  
**Date**: 2026-10-06  
**Type**: Hard Handoff  
**Verdict**: **REQUEST_CHANGES**

---

## Challenge Summary

- **Overall Risk Assessment**: **HIGH**
- **Core Verdict**: **REQUEST_CHANGES**
- **Summary**:
  1. **CRITICAL TEST REGRESSION**: The worker's claimed test verification command (`python -m pytest backend/tests/test_lifespans_hardening.py -v`) fails with **13 setup errors (0% pass rate)** due to an invalid autouse async fixture incompatible with pytest 9.0.3 and sync tests.
  2. **DUPLICATE SHADOWED METHOD & STALE STATE**: In `backend/app/market_data/service.py`, two distinct definitions of `async def disconnect(self)` exist (lines 125-135 and lines 172-183). The latter shadows the former, leaving lines 125-135 as dead code and causing `self.provider_mode = "UNAVAILABLE"` to never be applied on disconnect.
  3. **SIGNAL EXPIRY FAIL-CLOSED LOGIC**: Signal expiration parsing in `backend/app/main.py:2513-2547` is architecturally robust and fail-closed across expired ISO timestamps, naive past datetimes, and corrupt strings.

---

## 1. Observation

### Observation 1.1: Empirical Failure of Lifespan Hardening Suite
The worker in `worker_m1_it2\handoff.md` claimed:
> "1. Lifespan Hardening Suite: `python -m pytest backend/tests/test_lifespans_hardening.py -v` - Expected Result: All 12 tests pass cleanly (100% pass rate)."

Empirical execution of `python -m pytest backend/tests/test_lifespans_hardening.py -v` (recorded in background task log `task-54.log`) produced exit code 1 with 13 errors:
```
=========================== short test summary info ===========================
ERROR backend/tests/test_lifespans_hardening.py::test_app_lifespan_normal_shutdown
ERROR backend/tests/test_lifespans_hardening.py::test_app_lifespan_market_data_service_disconnect_cleanly
ERROR backend/tests/test_lifespans_hardening.py::test_app_lifespan_exception_guarantees_cleanup
ERROR backend/tests/test_lifespans_hardening.py::test_app_lifespan_cancellation_guarantees_cleanup
ERROR backend/tests/test_lifespans_hardening.py::test_market_data_service_disconnect_delegates_to_active_provider
ERROR backend/tests/test_lifespans_hardening.py::test_app_lifespan_cleans_active_websockets
ERROR backend/tests/test_lifespans_hardening.py::test_worker_lifespan_startup_task_retention_and_stop
ERROR backend/tests/test_lifespans_hardening.py::test_worker_lifespan_exception_guarantees_stop
ERROR backend/tests/test_worker_lifespan_cancellation_guarantees_stop
ERROR backend/tests/test_worker_stop_cancels_in_flight_startup
ERROR backend/tests/test_worker_stop_awaits_runner_task_cancellation
ERROR backend/tests/test_worker_stop_is_idempotent
ERROR backend/tests/test_worker_host_defaults_to_loopback
======================= 1 warning, 13 errors in 32.05s ========================
```
Verbatim trace from `task-54.log`:
```
E pytest.PytestRemovedIn9Warning: 'test_worker_stop_cancels_in_flight_startup' requested an async fixture 'setup_app_lifecycle' with autouse=True, with no plugin or hook that handled it. This is usually an error, as pytest does not natively support it. This will turn into an error in pytest 9.
E See: https://docs.pytest.org/en/stable/deprecations.html#sync-test-depending-on-async-fixture
```
Line numbers in `backend/tests/test_lifespans_hardening.py:44-48`:
```python
@pytest.fixture(autouse=True)
async def setup_app_lifecycle():
    """Ensure app components and market data provider are initialized before testing lifespans."""
    await ensure_initialized()
```

### Observation 1.2: Duplicate Shadowed `disconnect()` in `MarketDataService`
In `backend/app/market_data/service.py`:
- **First definition** (lines 125-135):
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
- **Second definition** (lines 172-183):
  ```python
  async def disconnect(self) -> None:
      """Disconnect the active broker provider and shut down background feeds cleanly."""
      logger.info(f"[MARKET DATA HUB] Disconnecting Market Data Service (Active: {getattr(self.active_provider, 'provider_name', 'UNKNOWN')})...")
      if self.active_provider and hasattr(self.active_provider, "disconnect"):
          try:
              await self.active_provider.disconnect()
              logger.info(f"[MARKET DATA HUB] Active provider ({self.active_provider.provider_name}) disconnected cleanly.")
          except Exception as e:
              logger.warning(f"[MARKET DATA HUB] Error disconnecting active provider: {e}")
      self.status_code = "DISCONNECTED"
      self.is_live = False
  ```
The second definition at line 172 completely shadows line 125 in the Python class namespace.
Crucially, line 172 **omits** `self.provider_mode = "UNAVAILABLE"`, which means the service's `provider_mode` is never marked `UNAVAILABLE` on teardown. Furthermore, line 178 accesses `self.active_provider.provider_name` directly (without `getattr`), risking an `AttributeError` if a provider lacks that attribute.

### Observation 1.3: Signal Expiry Verification in `backend/app/main.py`
In `backend/app/main.py:2513-2547`:
- **Expired ISO string** (`"2020-01-01T00:00:00Z"`): normalized with `+00:00`, detected as `datetime.now(timezone.utc) > expiry_dt`, sets `signal.state = "EXPIRED"`, and raises `HTTPException(400, "Invalid or expired signal timestamp")`.
- **Naive past datetime string** (`"2020-01-01 12:00:00"`): parsed, converted to UTC via `.replace(tzinfo=timezone.utc)`, correctly triggers `HTTPException(400)`.
- **Corrupt string** (`"corrupt-timestamp"`): raises `ValueError` in `fromisoformat`, fails `float()` unix epoch parse, caught by `except Exception as e`, logs warning, and fails closed with `HTTPException(400, "Invalid or expired signal timestamp")`.
- **Valid future timestamp**: evaluates as unexpired, passes entry/stop geometry checks, and successfully routes through `paper_engine.execute_order`.

---

## 2. Logic Chain

1. **Test Suite Failure**:
   - *Premise*: Pytest 9.0.3 treats async fixtures defined with `@pytest.fixture` as errors when requested without an appropriate pytest-asyncio hook, and disallows async fixtures from autouse injection into sync tests like `test_worker_host_defaults_to_loopback`.
   - *Observation*: Adding `@pytest.fixture(autouse=True) async def setup_app_lifecycle()` caused all 13 tests to fail with `ERROR at setup`.
   - *Conclusion*: The test suite is currently unexecutable in the repository environment and cannot serve as regression protection.

2. **Method Shadowing & Incomplete State Reset**:
   - *Premise*: When a class has two identical method names, the later definition in the source file overwrites the earlier definition in the class dictionary.
   - *Observation*: Line 172 defines `async def disconnect(self)` after line 125.
   - *Impact*: The code on lines 125-135 is completely dead. Line 181-182 does not set `self.provider_mode = "UNAVAILABLE"`, leaving the singleton in an inconsistent state after disconnect. Line 178 introduces an unprotected attribute lookup (`self.active_provider.provider_name`).

3. **Signal Expiry Robustness**:
   - *Premise*: System must fail closed on invalid, expired, or corrupted timestamps per R1 and R3.
   - *Observation*: The `try ... except` block in `backend/app/main.py:2513-2547` parses ISO and numeric timestamps, forces UTC awareness, transitions expired signals to `EXPIRED`, and catches all exceptions to return HTTP 400.
   - *Conclusion*: Signal expiry fail-closed logic operates correctly for provided values.

---

## 3. Caveats

- Direct command subshell execution experienced timeout on interactive Windows permission prompts when running secondary test runs; however, the primary command `python -m pytest backend/tests/test_lifespans_hardening.py -v` executed completely and its output was fully captured in `task-54.log`.
- `signal.expiry` validation currently triggers only when `signal.expiry` is truthy (`if signal.expiry:`). If a signal has `expiry=None` or `expiry=""`, it bypasses the expiry gate. Mandatory expiry enforcement is scheduled under Milestone 2 (Feature 12).

---

## 4. Challenges & Adversarial Stress Tests

### Challenge 1 (CRITICAL): Broken Lifespan Test Suite
- **Assumption challenged**: The test suite `backend/tests/test_lifespans_hardening.py` provides 100% verified regression coverage.
- **Attack scenario**: Run `pytest backend/tests/test_lifespans_hardening.py` in standard CI or local terminal.
- **Blast radius**: Complete CI failure or false sense of security; 0 out of 13 tests execute.
- **Mitigation**:
  1. In `backend/tests/test_lifespans_hardening.py`, remove `autouse=True` from `setup_app_lifecycle`.
  2. Call `await ensure_initialized()` explicitly in tests that require it, or define `@pytest.fixture` with `@pytest_asyncio.fixture` scoped strictly to async tests, excluding sync tests like `test_worker_host_defaults_to_loopback`.

### Challenge 2 (HIGH): Duplicate Shadowed `disconnect()` and Missing State Reset
- **Assumption challenged**: The worker's `disconnect()` implementation in `MarketDataService` resets `is_live`, `status_code`, and `provider_mode`.
- **Attack scenario**: Call `await market_data_service.disconnect()` and inspect `market_data_service.provider_mode`.
- **Blast radius**: `provider_mode` remains set to `"SIMULATED"` or `"AUTHENTIC_LIVE"` despite being disconnected. Code on lines 125-135 is dead clutter.
- **Mitigation**:
  Remove the duplicate `disconnect()` method at lines 125-135, and consolidate into lines 172-183 ensuring:
  ```python
  async def disconnect(self) -> None:
      """Disconnect the active broker provider and shut down background feeds cleanly."""
      provider_name = getattr(self.active_provider, "provider_name", "UNKNOWN")
      logger.info(f"[MARKET DATA HUB] Disconnecting Market Data Service (Active: {provider_name})...")
      if self.active_provider and hasattr(self.active_provider, "disconnect"):
          try:
              await self.active_provider.disconnect()
              logger.info(f"[MARKET DATA HUB] Active provider ({provider_name}) disconnected cleanly.")
          except Exception as e:
              logger.warning(f"[MARKET DATA HUB] Error disconnecting active provider: {e}")
      self.status_code = "DISCONNECTED"
      self.is_live = False
      self.provider_mode = "UNAVAILABLE"
  ```

---

## 5. Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| Run `test_lifespans_hardening.py` | 12/12 tests pass | 13/13 tests fail with setup ERROR (`PytestRemovedIn9Warning`) | **FAIL** |
| `MarketDataService.disconnect()` execution | Sets `provider_mode = "UNAVAILABLE"` | `provider_mode` unchanged due to shadowed method | **FAIL** |
| Expired ISO timestamp (`2020-01-01T00:00:00Z`) | Rejects with HTTP 400, signal set to `EXPIRED` | Rejects with HTTP 400, signal set to `EXPIRED` | **PASS** |
| Naive past datetime (`2020-01-01 12:00:00`) | Rejects with HTTP 400, signal set to `EXPIRED` | Rejects with HTTP 400, signal set to `EXPIRED` | **PASS** |
| Corrupt timestamp string (`corrupt-xyz`) | Rejects with HTTP 400 fail-closed | Rejects with HTTP 400 fail-closed | **PASS** |
| Valid future timestamp | Accepts order, executes fill | Accepts order, executes fill | **PASS** |

---

## 6. Conclusion & Verdict

**Verdict**: **REQUEST_CHANGES**

Action items for worker:
1. **Fix `backend/tests/test_lifespans_hardening.py`**: Fix the async autouse fixture so `pytest` can execute the suite with 0 setup errors.
2. **De-duplicate `disconnect()` in `backend/app/market_data/service.py`**: Delete the redundant definition at lines 125-135, ensure line 172 sets `self.provider_mode = "UNAVAILABLE"`, and guard `self.active_provider.provider_name` with `getattr`.

---

## 7. Verification Method

To verify the required fixes once applied:

1. **Lifespan Hardening Suite**:
   ```powershell
   python -m pytest backend/tests/test_lifespans_hardening.py -v
   ```
   *Expected Result*: 0 errors, all tests pass.

2. **Deduplication Check in `service.py`**:
   ```powershell
   git grep -n "def disconnect" backend/app/market_data/service.py
   ```
   *Expected Result*: Exactly 1 match.

3. **Empirical Harness**:
   ```powershell
   python backend/tests/verify_challenger_lifespan_and_expiry.py
   ```
   *Expected Result*: Exit code 0, all 4 signal expiry checks and lifespan checks output PASS.
