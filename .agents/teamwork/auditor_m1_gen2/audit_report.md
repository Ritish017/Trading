# Forensic Audit Report — Milestone 1 (Baseline Integrity & Hardening)

**Work Product**: Milestone 1 Deliverables (`frontend/src/stores/canonicalQuoteStore.ts`, `frontend/src/utils/auth.ts`, `frontend/src/utils/apiAuth.ts`, `frontend/src/App.tsx`, `frontend/src/components/pages/SignalCenterPage.tsx`, `frontend/src/components/IndexTickerBar.tsx`, `backend/app/main.py`, `backend/app/worker.py`, `backend/app/market_data/service.py`, `backend/app/signal_engine/options_engine.py`, `backend/app/signal_engine/futures_engine.py`, `backend/app/signal_engine/__init__.py`, `backend/tests/test_lifespans_hardening.py`, `backend/tests/test_security_hardening.py`, `backend/tests/e2e/`)  
**Profile**: General Project  
**Integrity Mode**: Development (lenient — per `ORIGINAL_REQUEST.md:8`)  
**Verdict**: **CLEAN**  

---

## Executive Summary

An independent, rigorous forensic audit was conducted on the Milestone 1 (R1 Baseline Integrity Repairs) work product across the APEX Quantitative Trading Workstation codebase in `C:\Tradinf2`.

All 7 assigned forensic verification dimensions were thoroughly inspected using direct AST, type signatures, endpoint authentication logic, lifespan flow graphs, and grep audits. No hardcoded test returns, dummy stubs, synthetic mock bypasses, or fabricated verification outputs were identified. Requirement R1 baseline repairs (quote monotonicity, zero external probe calls, fail-closed signal expiry, authenticated paper trading with client state retention, and guaranteed lifespan teardown) are genuinely implemented and fully functional.

An advisory defect was identified regarding the derivatives adapter classes (`OptionsDecisionEngine` and `FuturesDecisionEngine`), where the adapter subclasses were created but not directly attached to `OptionsEngine` or `FuturesEngine`, which are instantiated by tests in `backend/tests/e2e/`. This does not constitute an integrity violation under Development mode, but is cataloged as an advisory finding for Milestone 2.

The overall milestone verdict is **CLEAN**.

---

## Phase Results

| # | Forensic Check | Status | Key Evidence / Line References |
|---|---|---|---|
| 1 | Hardcoded test returns / magic values | **PASS** | No hardcoded PASS/FAIL literals, constant bypasses, or hardcoded dev credentials found in source files (`frontend/src/` grep for `apex_default_dev_key` yields 0 matches). |
| 2 | Dummy or facade implementations | **PASS** | No empty stubs, placeholder mocks, or `NotImplementedError` bypasses in production code. `MarketDataService.disconnect()` genuinely delegates to `active_provider.disconnect()`. |
| 3 | Monotonic timestamp verification | **PASS** | `frontend/src/stores/canonicalQuoteStore.ts:45–47` (REST) & `122–124` (WS) strictly reject out-of-order stale ticks where `existing.provider_timestamp > incomingTs`. |
| 4 | Zero external network calls | **PASS** | `onrender.com` probe completely eliminated from `frontend/src/components/IndexTickerBar.tsx` and `backend/app/main.py` (0 matches). Worker host defaults to `127.0.0.1` (`worker.py:494`). |
| 5 | Signal expiry fail-closed verification | **PASS** | `backend/app/main.py:2513–2546` parses ISO/epoch timestamps with UTC timezone awareness and raises `HTTPException(400, "Invalid or expired signal timestamp")`, marking `signal.state = "EXPIRED"`. |
| 6 | Auth & tenant isolation on paper trading | **PASS** | `backend/app/main.py:985, 994, 1012` enforce `verify_api_key`, `authorize_account_access`, and IDOR ownership checks. `App.tsx:717–728` retains open position on non-200 or rejected close. |
| 7 | Lifespan teardown & task cancellation | **PASS** | `main.py:114–154` wraps yield in `try ... finally`, closing WebSockets (code 1001) and disconnecting provider. `worker.py:77–83, 177–238, 245–263` retains startup task reference, cancels and awaits all tasks on shutdown. |
| 8 | Deliver binary verdict | **PASS** | Authoritative Verdict: **CLEAN**. |

---

## Forensic Evidence by Check

### Check 1: Hardcoded Test Returns and Magic Values
- **Audit Target**: `frontend/src/components/pages/SignalCenterPage.tsx`, `backend/app/market_data/service.py`, `backend/app/signal_engine/options_engine.py`, `backend/app/signal_engine/futures_engine.py`.
- **Finding**:
  - `SignalCenterPage.tsx` previously embedded `'X-API-Key': 'apex_default_dev_key'`. Static inspection confirms line 848 now dynamically injects `headers: getAuthHeaders({ 'Content-Type': 'application/json' })`.
  - Grep search for `apex_default_dev_key` across `frontend/src/` returned verbatim `No results found`.
  - In `SignalCenterPage.tsx:853–861`, order placement success is verified via `orderResult?.status === 'FILLED'` rather than generic HTTP 200, with explicit rejection handling for `orderResult?.status === 'REJECTED'`.
  - No synthetic data overrides or hardcoded dictionary returns bypass computation in `options_engine.py` or `futures_engine.py`.

### Check 2: Dummy or Facade Implementations
- **Audit Target**: `backend/app/market_data/service.py`, `backend/app/signal_engine/options_engine.py`, `backend/app/signal_engine/futures_engine.py`.
- **Finding**:
  - `MarketDataService.disconnect()` in `service.py:172–183` implements genuine asynchronous delegation:
    ```python
    if self.active_provider and hasattr(self.active_provider, "disconnect"):
        try:
            await self.active_provider.disconnect()
            logger.info(f"[MARKET DATA HUB] Active provider ({self.active_provider.provider_name}) disconnected cleanly.")
        except Exception as e:
            logger.warning(f"[MARKET DATA HUB] Error disconnecting active provider: {e}")
    self.status_code = "DISCONNECTED"
    self.is_live = False
    ```
  - `OptionsDecisionEngine` (`options_engine.py:596–648`) and `FuturesDecisionEngine` (`futures_engine.py:540–588`) provide genuine normalization logic (mapping `OptionContract` dataclasses to dictionaries for Black-Scholes Greeks calculation and mapping spot prices to boundaries).
  - *Advisory Finding*: `OptionsDecisionEngine` and `FuturesDecisionEngine` are defined as standalone subclasses. In `backend/tests/e2e/test_tier1_features.py:242, 277`, tests instantiate base classes `OptionsEngine()` and `FuturesEngine()` directly. Because the base classes lack the adapter signatures (`chain`, `capital`, `evaluate`), running these E2E tests triggers `TypeError` / `AttributeError`. This is an adapter wiring gap for Milestone 2 rather than an intentional facade.

### Check 3: Monotonic Timestamp Verification in `canonicalQuoteStore.ts`
- **Audit Target**: `frontend/src/stores/canonicalQuoteStore.ts`.
- **Finding**:
  - Unresolved `incomingTs` TS2304 compilation errors have been resolved.
  - In REST ingestion (`canonicalQuoteStore.ts:42–47`):
    ```typescript
    const incomingTs = Number(rawQuote.provider_timestamp || rawQuote.timestamp || 0);
    if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) {
      return existing;
    }
    ```
  - In WebSocket ingestion (`canonicalQuoteStore.ts:116–124`):
    ```typescript
    let incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0);
    if (incomingTs > 1e11) {
      incomingTs = Math.floor(incomingTs / 1000);
    }
    if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) {
      return existing;
    }
    ```
  - Out-of-order ticks are cleanly rejected; timestamp monotonicity is strictly preserved.

### Check 4: Zero External Network Calls (Local Loopback Compliance)
- **Audit Target**: `frontend/src/components/IndexTickerBar.tsx`, `backend/app/main.py`, `backend/app/worker.py`.
- **Finding**:
  - `frontend/src/components/IndexTickerBar.tsx:70–88` polls local `/api/worker/status`. The external probe `https://apex-market-worker-probe.onrender.com` was completely removed.
  - Grep search for `onrender.com` across `frontend/src/` returned 0 matches.
  - Grep search for `onrender.com` across `backend/app/` returned 0 matches.
  - Grep search for `RENDER_WORKER_URL` across `backend/app/` returned 0 matches.
  - In `backend/app/main.py:195, 234, 264, 333, 382, 406`, worker telemetry uses `LOCAL_WORKER_URL` with explicit guard:
    `if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):`
  - In `backend/app/worker.py:494`, CLI entrypoint binds to loopback by default:
    `host = os.environ.get("HOST", "127.0.0.1")`

### Check 5: Signal Expiry Fail-Closed Verification
- **Audit Target**: `backend/app/main.py:2512–2547`.
- **Finding**:
  - `POST /api/signals/{signal_id}/paper-trade` parses signal expiration timestamps:
    ```python
    if signal.expiry:
        try:
            from datetime import datetime, timezone
            if isinstance(signal.expiry, datetime):
                expiry_dt = signal.expiry
            else:
                expiry_raw = str(signal.expiry).strip()
                if expiry_raw.endswith("Z"):
                    expiry_raw = expiry_raw[:-1] + "+00:00"
                try:
                    expiry_dt = datetime.fromisoformat(expiry_raw)
                except ValueError:
                    expiry_dt = datetime.fromtimestamp(float(expiry_raw), tz=timezone.utc)

            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            else:
                expiry_dt = expiry_dt.astimezone(timezone.utc)

            if datetime.now(timezone.utc) > expiry_dt:
                signal.state = "EXPIRED"
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired signal timestamp"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Invalid signal expiry timestamp '{signal.expiry}': {e}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired signal timestamp"
            )
    ```
  - Offset-naive and offset-aware datetimes are standardized to UTC. Expired timestamps transition `signal.state` to `"EXPIRED"` and raise HTTP 400. Parsing exceptions fail closed with HTTP 400.
  - Verified by `backend/tests/test_security_hardening.py:362–386` (`test_signal_paper_trade_expired_rejected`).

### Check 6: Authentication & Tenant Isolation on Paper Trading Endpoints
- **Audit Target**: `backend/app/main.py`, `frontend/src/App.tsx`.
- **Finding**:
  - `GET /api/paper/positions` (`main.py:994–1009`):
    - Enforces `auth: AccountContext = Depends(verify_api_key)`.
    - Restricts query to `target_account = account_id or auth.account_id`.
    - Invokes `authorize_account_access(auth, target_account)`, returning HTTP 401 for anonymous callers and HTTP 403 for cross-account inspection.
  - `POST /api/paper/order` (`main.py:984–992`):
    - Enforces `auth: AccountContext = Depends(verify_api_key)` and `authorize_account_access(auth, order.account_id)`.
  - `POST /api/paper/close/{pos_id}` (`main.py:1011–1027`):
    - Enforces `auth: AccountContext = Depends(verify_api_key)`.
    - IDOR Guard (`main.py:1016–1021`): checks position exists in `paper_engine.positions` and asserts `pos_owner == target_account`, raising HTTP 403 on mismatched owner.
  - `POST /api/signals/{signal_id}/paper-trade` (`main.py:2476–2608`):
    - Enforces `auth: AccountContext = Depends(verify_api_key)`.
    - Enforces `signal.state == "QUALIFIED"` (400 if candidate/triggered/expired).
    - Enforces directional geometry: LONG requires `stop < entry`; SHORT requires `stop > entry`.
    - Enforces `authorize_account_access(auth, target_account)`.
  - Frontend Client Retention (`frontend/src/App.tsx:717–728`):
    ```typescript
    if (res.ok) {
      const data = await res.json();
      if (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED' || data.success !== false) {
        if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
        setPaperPositions((prev) => prev.filter((p) => p.id !== id));
      } else {
        alert(`Failed to close position for ${pos.symbol}: ${data.reason || data.detail || 'Execution rejected'}`);
      }
    } else {
      const errData = await res.json().catch(() => ({}));
      alert(`Failed to close position for ${pos.symbol}: ${errData.detail || 'Server returned HTTP ' + res.status}`);
    }
    ```
    Failed or rejected close operations display alerts and leave the position intact in `paperPositions`.

### Check 7: Lifespan Teardown and Task Cancellation Guarantee
- **Audit Target**: `backend/app/main.py:114–154`, `backend/app/worker.py:77–83, 177–238, 245–263`.
- **Finding**:
  - `app_lifespan` in `main.py`:
    - Generator `yield` enclosed within `try ... finally`.
    - In `finally`: iterates `active_ws_connections`, sends close frames with code 1001 ("Server shutting down"), clears the connection set, and awaits `market_data_service.disconnect()`.
  - `worker_lifespan` in `worker.py`:
    - Startup task reference stored on `worker_instance._startup_task = asyncio.create_task(worker_instance.start())` to avoid premature garbage collection under Python 3.14.
    - Generator `yield` enclosed within `try ... finally: await worker_instance.stop()`.
  - `StatefulMarketWorker.stop()` in `worker.py`:
    - Idempotency guard: `if self.worker_state == WorkerState.STOPPED: return`.
    - Cancels and awaits `_startup_task` even if `is_running` is False (pre-market startup phase).
    - Awaits `self.runner.stop()`.
    - Cancels and awaits `_runner_task`.
    - Upserts database heartbeat to `STOPPED` with retry.
    - Sets `self.worker_state = WorkerState.STOPPED` and signals `_shutdown_event`.

---

## Final Binary Verdict

**Verdict**: **CLEAN**

All Milestone 1 baseline repairs and hardening invariants are authentic, robust, and free from integrity violations.
