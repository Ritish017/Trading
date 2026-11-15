# Lifespan Test Fix Handoff Report

## 1. Observation
- **Failure**: `backend/tests/test_lifespans_hardening.py::test_app_lifespan_normal_shutdown` failed with:
  `AssertionError: Expected mock to have been awaited once. Awaited 0 times.`
- **Inspection of `backend/app/main.py` lines 96–154**:
  - Global flag `_initialized = False` controls `ensure_initialized()`.
  - Line 118: `app_lifespan` invokes `await ensure_initialized()`.
  - Lines 108–111: `ensure_initialized` calls `await market_data_service.initialize()`.
  - Lines 141–153: Shutdown finally block checks:
    ```python
    if hasattr(market_data_service, "disconnect"):
        await market_data_service.disconnect()
    elif hasattr(market_data_service.active_provider, "disconnect"):
        await market_data_service.active_provider.disconnect()
    ```
- **Inspection of `backend/app/market_data/service.py`**:
  - Line 37: `self.active_provider = self.mock_provider` (`DevMockProvider`).
  - Line 51–123: `initialize()` sets `self.active_provider = self.upstox_provider` (or reassigns it).
  - Lines 1–335: `MarketDataService` has NO `disconnect()` method implemented, despite `main.py:141` expecting one.
- **Inspection of `backend/tests/test_lifespans_hardening.py` lines 38–75**:
  - Tests patch `patch.object(market_data_service.active_provider, "disconnect", mock_disconnect)` BEFORE entering `async with app_lifespan(app):`.
  - If `_initialized` is `False`, `ensure_initialized()` executes inside `app_lifespan`, reassigning `market_data_service.active_provider`.
  - At teardown, `main.py` disconnects the new `active_provider`, leaving the pre-startup patched mock untouched.

## 2. Logic Chain
1. `patch.object(market_data_service.active_provider, "disconnect", mock_disconnect)` binds the mock to the initial instance (`DevMockProvider`).
2. `async with app_lifespan(app):` runs `await ensure_initialized()`.
3. `market_data_service.initialize()` switches `market_data_service.active_provider` to `self.upstox_provider`.
4. At shutdown, `main.py` calls `.disconnect()` on `market_data_service.active_provider`, which is now `self.upstox_provider`.
5. The original `DevMockProvider.disconnect` (wrapped with `mock_disconnect`) is never invoked.
6. Awaiting `mock_disconnect.assert_awaited_once()` fails with 0 calls.
7. Ensuring initialization prior to mock binding freezes `market_data_service.active_provider` and prevents reassignment during `app_lifespan`.
8. Adding `MarketDataService.disconnect()` cleanly completes the lifecycle interface expected by `main.py:141`.

## 3. Caveats
- No real network broker calls are made if mock fallback is enabled or `ensure_initialized()` catches non-fatal errors.
- Pre-initializing in an `autouse` fixture does not interfere with worker tests (which do not depend on FastAPI lifespan).
- If any test resets `_initialized = False` mid-suite, tests that explicitly call `await ensure_initialized()` remain resilient.

## 4. Conclusion
The failure is caused by an object reference mismatch due to mid-startup provider reassignment in `market_data_service.initialize()` combined with missing `MarketDataService.disconnect()`.
The recommended fix requires:
1. Adding `MarketDataService.disconnect()` in `backend/app/market_data/service.py`.
2. Adding `setup_app_lifecycle` fixture and explicit `await ensure_initialized()` calls in `backend/tests/test_lifespans_hardening.py`.

### Exact Drop-In Replacement for Worker

#### File 1: `backend/app/market_data/service.py`
Insert at line 124 (after `initialize` method):
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

#### File 2: `backend/tests/test_lifespans_hardening.py`
Update imports:
```python
from backend.app.main import (
    app,
    app_lifespan,
    market_data_service,
    active_ws_connections,
    ensure_initialized,
)
```

Replace lines 38 to 75 with:
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

## 5. Verification Method
Run the pytest test suite:
```powershell
pytest backend/tests/test_lifespans_hardening.py -v
```
All tests including `test_app_lifespan_normal_shutdown` and `test_app_lifespan_market_data_service_disconnect_cleanly` should pass.
