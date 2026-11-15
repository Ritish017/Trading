# Investigation Report: Lifespan Teardown Provider Disconnect Test Failure

**Author**: `teamwork_preview_explorer` (Lifespan Test Fix Explorer)  
**Parent Agent ID**: `89f607f3-2421-4e10-b882-c14724281ad4`  
**Milestone**: Milestone 1 Iteration 2 (R1 Baseline Integrity Repairs)  
**Date**: 2026-10-06 / 2026-10-07  
**Status**: Investigation Complete — Root Cause Verified & Exact Drop-in Solution Formulated  

---

## 1. Executive Summary

In `backend/tests/test_lifespans_hardening.py`, `test_app_lifespan_normal_shutdown` failed with:
```
AssertionError: Expected mock to have been awaited once. Awaited 0 times.
```

### Root Cause Summary
Before `app_lifespan(app)` runs, the test executes:
```python
with patch.object(market_data_service.active_provider, "disconnect", mock_disconnect):
```
At that point in time, `market_data_service.active_provider` evaluates to `market_data_service.mock_provider` (instance of `DevMockProvider`), assigned in `MarketDataService.__init__`. The mock is bound to that specific instance.

When `app_lifespan(app)` enters, line 118 calls `await ensure_initialized()`. Because `_initialized` is initially `False`, it runs `await market_data_service.initialize()`. In `initialize()`, because `settings.active_broker_provider` defaults to `"UPSTOX"`, `market_data_service.active_provider` is reassigned to `self.upstox_provider` (instance of `UpstoxProvider`).

When `app_lifespan` exits and executes its `finally:` block in `backend/app/main.py`:
```python
elif hasattr(market_data_service.active_provider, "disconnect"):
    await market_data_service.active_provider.disconnect()
```
It evaluates `market_data_service.active_provider` dynamically. That reference now points to `self.upstox_provider`. Consequently, `self.upstox_provider.disconnect()` is called, while `self.mock_provider.disconnect` (where `mock_disconnect` was attached) is **never awaited**.

Furthermore, `backend/app/main.py` lines 141–146 already include:
```python
if hasattr(market_data_service, "disconnect"):
    await market_data_service.disconnect()
```
However, `MarketDataService` in `backend/app/market_data/service.py` **lacks** a `disconnect()` method.

---

## 2. Codebase Inspection & Evidence Chain

### 2.1. Lifespan Teardown in `backend/app/main.py`
File: `backend/app/main.py`, Lines 114–154:
```python
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(f"Starting APEX Quant Lab Backend in {settings.environment} mode.")
    try:
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
```

**Observation**:
1. Lines 141–146 deliberately check `if hasattr(market_data_service, "disconnect"):` first!
2. Lines 147–152 only execute as a fallback `elif hasattr(market_data_service.active_provider, "disconnect"):`.

### 2.2. Provider Initialization in `backend/app/market_data/service.py`
File: `backend/app/market_data/service.py`, Lines 23–88:
```python
class MarketDataService:
    def __init__(self):
        self.primary_provider_name = settings.active_broker_provider.upper()
        self.allow_mock_fallback = settings.allow_mock_fallback
        
        self.mock_provider = DevMockProvider()
        self.upstox_provider = UpstoxProvider(
            token=settings.get_upstox_token or "",
            base_url=settings.upstox_base_url
        )
        self.dhan_provider = DhanProvider(
            client_id=settings.dhan_client_id or "",
            access_token=settings.dhan_access_token or ""
        )

        self.active_provider: MarketDataProvider = self.mock_provider
```
And in `initialize()`:
```python
    async def initialize(self) -> bool:
        if self.primary_provider_name == "UPSTOX":
            if not settings.get_upstox_token:
                if self.allow_mock_fallback:
                    self.active_provider = self.mock_provider
                    ...
                else:
                    self.active_provider = self.upstox_provider
                    ...
            connected = await self.upstox_provider.connect()
            if connected:
                self.active_provider = self.upstox_provider
                ...
            else:
                if self.allow_mock_fallback:
                    self.active_provider = self.mock_provider
                    ...
                else:
                    self.active_provider = self.upstox_provider
                    ...
```
And searching `backend/app/market_data/service.py` for `disconnect`:
**Observation**: No `disconnect()` method exists on `MarketDataService`.

### 2.3. The Failing Test in `backend/tests/test_lifespans_hardening.py`
File: `backend/tests/test_lifespans_hardening.py`, Lines 38–75:
```python
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
    """Verify task cancellation in app_lifespan still executes cleanup in finally block."""
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

**Observation**:
All three tests evaluate `market_data_service.active_provider` **before** entering `app_lifespan`. When `ensure_initialized()` executes during startup, `active_provider` is reassigned to another instance. At shutdown, `main.py` calls `disconnect` on the new instance, leaving the old instance's patched mock unawaited.

---

## 3. Recommended Clean Solution

The complete, architectural solution consists of two targeted changes:

### 1. Add `disconnect()` to `MarketDataService` (`backend/app/market_data/service.py`)
Add `disconnect()` to `MarketDataService` to satisfy lifecycle symmetry:
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

Why this is required:
- `main.py` lines 141–146 was intentionally designed to call `market_data_service.disconnect()`.
- It properly encapsulates provider lifecycle within the `MarketDataService` domain orchestrator.
- When `main.py` calls `await market_data_service.disconnect()`, `market_data_service` delegates to whatever provider is active at shutdown time.

### 2. Update `backend/tests/test_lifespans_hardening.py`
Update the three `app_lifespan` tests to patch `market_data_service.disconnect` directly, and add an isolated test for `MarketDataService.disconnect()` delegation:

```python
# ===========================================================================
# 1. FastAPI app_lifespan Tests (backend/app/main.py)
# ===========================================================================

@pytest.mark.asyncio
async def test_app_lifespan_normal_shutdown():
    """Verify normal app_lifespan exit disconnects market data provider."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_exception_guarantees_cleanup():
    """Verify exception inside app_lifespan still executes provider cleanup in finally block."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
        with pytest.raises(RuntimeError, match="Simulated Application Crash"):
            async with app_lifespan(app):
                raise RuntimeError("Simulated Application Crash")
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_guarantees_cleanup():
    """Verify task cancellation in app_lifespan still executes cleanup in finally block."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
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
```

---

## 4. Exact Implementation Snippets for Implementer (Worker)

### Snippet 1: `backend/app/market_data/service.py`
Insert right after `unsubscribe(self, symbols: List[str])`:
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

### Snippet 2: `backend/tests/test_lifespans_hardening.py`
Replace lines 38–75 with:
```python
@pytest.mark.asyncio
async def test_app_lifespan_normal_shutdown():
    """Verify normal app_lifespan exit disconnects market data provider."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
        async with app_lifespan(app):
            pass
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_exception_guarantees_cleanup():
    """Verify exception inside app_lifespan still executes provider cleanup in finally block."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
        with pytest.raises(RuntimeError, match="Simulated Application Crash"):
            async with app_lifespan(app):
                raise RuntimeError("Simulated Application Crash")
        mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_app_lifespan_cancellation_guarantees_cleanup():
    """Verify task cancellation in app_lifespan still executes cleanup in finally block."""
    mock_disconnect = AsyncMock()
    with patch.object(market_data_service, "disconnect", mock_disconnect):
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
```
