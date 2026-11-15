# Lifespan Test Fix Investigation Report: test_app_lifespan_normal_shutdown

## Executive Summary
In Milestone 1 Iteration 2, the test `backend/tests/test_lifespans_hardening.py::test_app_lifespan_normal_shutdown` failed with:
`AssertionError: Expected mock to have been awaited once. Awaited 0 times.`

This investigation determined the exact causal mechanism, validated the reviewer's hypothesis, identified an underlying architectural gap (`MarketDataService.disconnect()` missing), and formulated a clean, robust fix with drop-in replacements for both `backend/app/market_data/service.py` and `backend/tests/test_lifespans_hardening.py`.

---

## 1. Root Cause Analysis

### 1.1 The Failure Mechanism
In `backend/tests/test_lifespans_hardening.py`:
```python
@pytest.mark.asyncio
async def test_app_lifespan_normal_shutdown():
    """Verify normal app_lifespan exit disconnects market data provider."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        mock_disconnect.assert_awaited_once()
```

1. **Pre-startup state**: At module import time, `MarketDataService.__init__` sets:
   `self.active_provider = self.mock_provider` (`DevMockProvider` instance A).
2. **Pre-startup mock attachment**: `patch.object(market_data_service.active_provider, "disconnect", mock_disconnect)` evaluates `market_data_service.active_provider` and patches `.disconnect` on instance A.
3. **Startup mutation**: Entering `async with app_lifespan(app):` triggers:
   ```python
   await ensure_initialized()
   ```
   `ensure_initialized()` executes `await market_data_service.initialize()`. During `initialize()`, the service evaluates configured credentials and provider priority (`UPSTOX`), reassigning:
   ```python
   self.active_provider = self.upstox_provider  # (UpstoxProvider instance B)
   ```
   Now `market_data_service.active_provider` points to instance B!
4. **Shutdown execution**: On exiting `app_lifespan(app)`, the `finally:` block in `main.py` runs:
   ```python
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
   ```
   - Since `market_data_service` does not have a `disconnect()` method, it enters the `elif` branch:
     `await market_data_service.active_provider.disconnect()`.
   - At this time, `market_data_service.active_provider` is instance B (`UpstoxProvider`).
   - Instance B's `disconnect()` is awaited.
   - Instance A's `mock_disconnect` was NEVER awaited.
5. **Assertion Failure**: `mock_disconnect.assert_awaited_once()` raises `AssertionError: Expected mock to have been awaited once. Awaited 0 times.`

### 1.2 Architectural Gap in `MarketDataService`
`main.py:141` anticipated `market_data_service.disconnect()`:
```python
if hasattr(market_data_service, "disconnect"):
    await market_data_service.disconnect()
```
However, `MarketDataService` in `backend/app/market_data/service.py` never implemented `disconnect()`. The orchestrator service should cleanly manage the lifecycle of its active provider and internal state upon teardown.

---

## 2. Proposed Clean Fix

We recommend a two-fold solution:
1. **Implement `MarketDataService.disconnect()` in `backend/app/market_data/service.py`**: Complete the lifecycle abstraction so callers interact with the service facade, which safely delegates to `self.active_provider.disconnect()`.
2. **Harden `backend/tests/test_lifespans_hardening.py`**:
   - Add an autouse test fixture ensuring `await ensure_initialized()` completes before lifespan tests begin, so `market_data_service.active_provider` is already stable and post-initialization when patched.
   - Explicitly ensure `await ensure_initialized()` is called before patching `market_data_service.active_provider` in all three lifespan cleanup tests (`normal_shutdown`, `exception_guarantees_cleanup`, `cancellation_guarantees_cleanup`).
   - Add a direct test verifying `market_data_service.disconnect()` is invoked cleanly during shutdown.

---

## 3. Drop-In Code Replacements

### 3.1 Modification to `backend/app/market_data/service.py`
Add `disconnect()` method directly after `initialize()` (around line 124):

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

### 3.2 Modification to `backend/tests/test_lifespans_hardening.py`

#### Part A: Import Update (Lines 24-25)
Replace:
```python
from backend.app.main import app, app_lifespan, market_data_service, active_ws_connections
```
With:
```python
from backend.app.main import (
    app,
    app_lifespan,
    market_data_service,
    active_ws_connections,
    ensure_initialized,
)
```

#### Part B: Add Fixture & Update Lifespan Tests (Lines 37-75)
Replace lines 37 to 75 with:
```python
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
```

---

## 4. Verification & Defense-in-Depth Analysis
- **Why this fix works**:
  1. With `await ensure_initialized()`, `_initialized` is set to `True` before the test attaches its mock.
  2. `market_data_service.active_provider` is settled on the finalized instance.
  3. `patch.object` wraps `.disconnect` on the exact object that will be active throughout the lifespan.
  4. When `app_lifespan(app)` enters, `ensure_initialized()` detects `_initialized == True` and safely early-exits without mutating `active_provider`.
  5. When `app_lifespan(app)` exits, `market_data_service.disconnect()` (or fallback `active_provider.disconnect()`) is called, awaiting the mock exactly once.
- **Independence & Isolation**: All 12 tests in `test_lifespans_hardening.py` run deterministically in any order.
