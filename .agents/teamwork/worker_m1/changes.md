# Milestone 1 (R1) Implementation Changes: Baseline Integrity & Hardening

**Implementer**: `teamwork_preview_worker` (Milestone 1 Baseline Integrity Implementer)  
**Date**: 2026-10-06  
**Status**: COMPLETE  

---

## Summary of Changes

### 1. `frontend/src/stores/canonicalQuoteStore.ts`
- **Issue**: Undeclared `incomingTs` variables at lines 152 and 163 broke TypeScript compilation (`TS2304: Cannot find name 'incomingTs'`), preventing `npm run lint` (`tsc --noEmit`) and `npm run build` from succeeding. Furthermore, WebSocket ticks lacked monotonicity protection, allowing out-of-order stale ticks to overwrite newer quotes.
- **Resolution**:
  - Look up existing quote using `this.getQuote(symbol) || this.quotes.get(symbol)`.
  - Declared `incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0)`.
  - Normalized milliseconds to epoch seconds if `incomingTs > 1e11`.
  - Added timestamp monotonicity guard: `if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) return existing;`.
  - Referenced `incomingTs` properly in `provider_timestamp` and `last_ws_ts`.
  - Added stripped ticker alias updates (`symbol.replace('.NS', '').replace('.BO', '')`) mirroring REST quote ingestion.

### 2. `frontend/src/utils/auth.ts` and `frontend/src/utils/apiAuth.ts`
- **Issue**: Frontend components were sending unauthenticated requests or leaking hardcoded dev keys (`apex_default_dev_key`).
- **Resolution**:
  - Implemented centralized token resolution utility:
    - Checks browser `localStorage` (`apex_api_key`, `apex_auth_token`, `apexnse_api_key`).
    - Checks runtime window global `window.__APEX_API_KEY__`.
    - Checks Vite environment variables (`VITE_APEX_API_KEY`, `VITE_API_KEY`, `VITE_API_AUTH_TOKEN`).
  - Implemented `getAuthHeaders(extraHeaders)` providing both `X-API-Key` and `Authorization: Bearer <token>` matching FastAPI `verify_api_key` dependency.
  - Exported `setApiAuthToken(token)` for user key persistence.
  - Created `frontend/src/utils/apiAuth.ts` re-exporting `./auth` for complete import compatibility.

### 3. `frontend/src/App.tsx`
- **Issue**:
  - `/api/paper/order` and `/api/paper/close/{id}` omitted authentication headers, failing with 401 against the fail-closed backend.
  - `/api/paper/positions` initial fetch omitted authentication headers.
  - In `handleClosePaperPosition`, line 713 unconditionally purged the position from client state `paperPositions` even when the backend API call failed (401, 404, 500, or network drop), creating critical client-server desynchronization.
- **Resolution**:
  - Imported `getAuthHeaders` from `./utils/auth`.
  - Injected `headers: getAuthHeaders()` into `/api/paper/positions`.
  - Injected `headers: getAuthHeaders({ 'Content-Type': 'application/json' })` into `/api/paper/order` and `/api/paper/close/{id}`.
  - Refactored `handleClosePaperPosition` so that `setPaperPositions((prev) => prev.filter((p) => p.id !== id))` strictly executes when `res.ok && (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED' || data.success !== false)`.
  - Added explicit user alerts on non-ok HTTP responses, execution rejections, and network errors, guaranteeing that positions are retained in UI on failure.

### 4. `frontend/src/components/pages/SignalCenterPage.tsx`
- **Issue**:
  - Hardcoded dev key `'X-API-Key': 'apex_default_dev_key'` at line 846 violated R1/R5 security requirements.
  - Line 850 checked only `res.ok` (HTTP 200), falsely announcing order fill success when the backend paper engine rejected the order (`order_result.status === 'REJECTED'`).
- **Resolution**:
  - Replaced hardcoded dev key with `getAuthHeaders({ 'Content-Type': 'application/json' })`.
  - Verified `data.order_result?.status === 'FILLED'` before announcing trade execution (`✓ LONG RELIANCE — Filled at ₹2800.00`).
  - Displayed explicit rejection notices when `data.order_result?.status === 'REJECTED'` (`✗ Order Rejected: ${reason}`).
  - Added descriptive error notifications for HTTP errors and network failures.

### 5. `frontend/src/components/IndexTickerBar.tsx`
- **Issue**: Probed external Render URL `https://apex-market-worker-probe.onrender.com/api/worker/status`, violating local loopback isolation (R5 / Item 8 in `PROJECT.md`).
- **Resolution**: Removed lines 82–91 containing the external Render probe, restricting telemetry to local `/api/worker/status`.

### 6. `backend/app/main.py`
- **Issue**:
  - In `app_lifespan`, generator `yield` was unguarded by `try ... finally`. If cancellation or exception occurred during lifespan, `active_provider.disconnect()` was skipped, leaving connections hanging.
  - Active frontend WebSocket connections in `active_ws_connections` were abandoned without close frames on shutdown.
  - `/api/paper/positions` used `verify_api_key_optional` and skipped checks when `account_id` was omitted, leaking global portfolio positions across all users to anonymous callers.
  - `/api/signals/{signal_id}/paper-trade` did not validate `signal.state == "QUALIFIED"`, did not validate signal expiration timestamps, and did not enforce directional stop geometry (`stop < entry` for LONG; `stop > entry` for SHORT).
- **Resolution**:
  - Wrapped `yield` in `app_lifespan` in `try ... finally`.
  - In `finally:`: closed all active WebSockets in `active_ws_connections` with code 1001 ("Server shutting down") and cleared the set; invoked `market_data_service.disconnect()` / `active_provider.disconnect()`.
  - In `/api/paper/positions`: enforced `auth: AccountContext = Depends(verify_api_key)`, scoped target account to `account_id or auth.account_id`, and called `authorize_account_access(auth, target_account)`.
  - In `/api/signals/{signal_id}/paper-trade`:
    - Enforced path and body `signal_id` consistency.
    - Verified `signal.state == "QUALIFIED"`, rejecting unqualified setups with HTTP 400.
    - Validated signal expiry ISO timestamp against `datetime.now(timezone.utc)`, marking expired signals as `EXPIRED` and rejecting with HTTP 400.
    - Validated directional trade geometry (`stop < entry` for LONG, `stop > entry` for SHORT), rejecting inverted stops with HTTP 400.
    - Verified caller account access and constructed authoritative `PaperOrderRequest`.

### 7. `backend/app/worker.py`
- **Issue**:
  - In `worker_lifespan`, `asyncio.create_task(worker_instance.start())` created an unreferenced background task subject to premature garbage collection in Python 3.14 / 3.12+.
  - In `worker_lifespan`, `yield` was unguarded by `try ... finally`, skipping `worker_instance.stop()` on probe errors or task cancellations.
  - In `worker_instance.stop()`, the check `if not self.is_running: return` caused early exit if shutdown was triggered while startup preflight/database migration was in progress, leaving background startup tasks running and heartbeat stuck in `STARTING`.
  - `_runner_task.cancel()` was called without `await`, risking unawaited task warnings.
  - `run_worker` defaulted to `host = os.environ.get("HOST", "0.0.0.0")`, exposing the probe to external interfaces.
- **Resolution**:
  - Added `self._startup_task: Optional[asyncio.Task] = None` attribute to `StatefulMarketWorker.__init__`.
  - Wrapped `worker_instance.start()` in `try ... except asyncio.CancelledError: raise`.
  - Stored `worker_instance._startup_task = asyncio.create_task(worker_instance.start())` in `worker_lifespan`.
  - Wrapped `yield` in `worker_lifespan` in `try ... finally: await worker_instance.stop()`.
  - In `worker_instance.stop()`:
    - Guarded against redundant calls (`if self.worker_state == WorkerState.STOPPED: return`).
    - Cancelled and explicitly awaited `self._startup_task`.
    - Awaited `self.runner.stop()`.
    - Cancelled and explicitly awaited `self._runner_task`.
    - Recorded `STOPPED` heartbeat to database with retries.
    - Set `self.worker_state = WorkerState.STOPPED` and signaled `self._shutdown_event`.
  - In `run_worker()`: changed default host from `"0.0.0.0"` to `"127.0.0.1"`.

### 8. `backend/tests/test_lifespans_hardening.py`
- **Created**: 12 comprehensive unit and integration tests covering:
  - Normal `app_lifespan` provider disconnect
  - Exception inside `app_lifespan` executing `finally` cleanup
  - Task cancellation in `app_lifespan` executing cleanup
  - Client WebSocket closure with code 1001
  - Startup task reference retention on `worker_instance._startup_task`
  - Probe exception triggering `worker_instance.stop()`
  - Task cancellation triggering `worker_instance.stop()`
  - `worker_instance.stop()` cancelling and awaiting in-flight startup task (`is_running=False`)
  - `worker_instance.stop()` cancelling and awaiting `_runner_task` (`is_running=True`)
  - Idempotent `stop()` calls
  - Loopback default binding (`127.0.0.1`) when `HOST` is unset

### 9. `backend/tests/test_security_hardening.py`
- **Appended**: 8 comprehensive security and endpoint authorization tests covering:
  - Fail-closed rejection of unauthenticated `GET /api/paper/positions` (401)
  - Success of authenticated `GET /api/paper/positions` (200)
  - Cross-account rejection of `GET /api/paper/positions?account_id=...` (403)
  - Anonymous rejection of `POST /api/signals/{id}/paper-trade` (401)
  - Cross-account rejection of `POST /api/signals/{id}/paper-trade` (403)
  - Rejection of unqualified signals (`state != QUALIFIED`) with HTTP 400
  - Rejection of expired signals (`datetime.now() > expiry`) with HTTP 400
  - Successful order fill and state transition to `TRIGGERED` for authenticated, valid `QUALIFIED` signals (200)
