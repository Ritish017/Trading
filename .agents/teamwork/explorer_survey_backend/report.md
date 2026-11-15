# APEX Backend Codebase Investigation Report

**Date**: 2026-10-06  
**Investigator**: teamwork_preview_explorer (Backend Codebase Explorer)  
**Target Repository**: `C:\Tradinf2` (commit `34849a90596eb8af218268cdebabb561ca627ede`)  
**Scope**: Read-only codebase exploration across 6 core backend architectural areas.

---

## Executive Summary

A comprehensive investigation of the APEX trading workstation backend (`backend/app/`, `backend/tests/`) was performed. The backend architecture exhibits strong foundations:
- A frozen quantitative signal pipeline with 20 systematic strategies and deterministic feature generation.
- A functional fail-closed API security module (`verify_api_key`) using constant-time comparison.
- Dual database persistence layers (PostgreSQL in production, SQLite in local development) with dialect-agnostic column inspection.
- 357 collected backend test cases across 50+ test suites, with a baseline run of 30 core safety, security, paper accounting, and financial invariant tests passing cleanly (100% pass rate).

However, critical architectural, security, lifecycle, and data-integrity defects were uncovered that prevent production reliability:
1. **Lifespan & Shutdown Vulnerability**: Unguarded `yield` generators in both `main.py` and `worker.py` bypass provider disconnection and resource cleanup upon cancellation or exceptions. Unreferenced background tasks in `worker.py` can be silently garbage-collected or bypassed during shutdown.
2. **Authentication Gaps & Credential Exposure**: `/api/paper/positions` allows unauthenticated access to portfolio positions when `account_id` is omitted. Signal-to-paper submissions lack state and expiry revalidation. Frontend components (`SignalCenterPage.tsx` and `App.tsx`) leak hardcoded dev keys, omit auth headers, and delete open positions on failed close requests.
3. **Derivatives Fabrication & Missing Geometry Invariants**: The opportunity scanner constructs only EQUITY candidates. Derivatives analysis fabricates synthetic DTE, OI, volume, lot size, and margin when missing rather than failing closed. Signal expiry and primary timeframe silently degrade without provenance propagation. Stop/target validation lacks strict LONG/SHORT geometry checks.
4. **Dual Paper Engine Discrepancy & Incomplete Lifecycle**: Two competing paper engines exist (`PaperTradingEngine` vs `PaperTradingBridge`). `PaperTradingEngine` does not automatically trigger SL/TP exits, while `PaperTradingBridge` contains hardcoded LONG-biased exit arithmetic that inverts SHORT exits. Idempotency keys are cached only in volatile memory.
5. **AI Service Event-Loop Blocking & Query-Param Key Leakage**: Async AI methods call synchronous SDK functions directly on the FastAPI event loop. Secret API keys are passed in URL query strings. No dedicated AI explanation service exists for signals, no-trade states, or trade journal entries.

---

## Detailed Findings by Focus Area

### 1. Lifespan Management, Shutdown Handlers & Worker Lifecycle

#### Observations:
- **`backend/app/main.py:114-134` (`app_lifespan`)**:
  ```python
  @asynccontextmanager
  async def app_lifespan(app: FastAPI):
      logger.info(f"Starting APEX Quant Lab Backend in {settings.environment} mode.")
      await ensure_initialized()
      try:
          default_symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", ...]
          await market_data_service.subscribe(default_symbols)
          if not os.environ.get("VERCEL"):
              await market_data_service.connect_websocket(on_normalized_tick_received)
      except Exception as e:
          logger.warning(f"WebSocket background feed non-fatal warning: {e}")
      yield
      logger.info("Shutting down APEX Quant Lab Backend...")
      if hasattr(market_data_service.active_provider, "disconnect"):
          try:
              await market_data_service.active_provider.disconnect()
          except Exception:
              pass
  ```
  - `yield` (line 126) is **not** wrapped inside a `try...finally` block. When FastAPI terminates due to an unhandled exception or receives `asyncio.CancelledError`, generator execution aborts, and lines 127–132 are never reached.
  - `market_data_service` does not have a formal `disconnect()` method; `main.py` directly queries `hasattr(market_data_service.active_provider, "disconnect")`.
  - Background WebSocket connections spawned by `market_data_service.connect_websocket` are not retained in a task reference and cannot be cancelled cleanly.

- **`backend/app/worker.py:220-234` (`worker_lifespan`)**:
  ```python
  @asynccontextmanager
  async def worker_lifespan(app: FastAPI):
      ...
      auto_start = os.environ.get("WORKER_AUTO_START", "true").lower() in ("true", "1", "yes")
      if auto_start:
          asyncio.create_task(worker_instance.start())
      yield
      await worker_instance.stop()
  ```
  - Unguarded `yield`: Missing `try...finally`. If shutdown encounters an exception or cancellation, `await worker_instance.stop()` is bypassed.
  - Unretained task: `asyncio.create_task(worker_instance.start())` creates an anonymous task with no variable reference. In Python 3.14, unreferenced tasks are subject to garbage collection while running.
  - Startup race on shutdown (`worker.py:174-175`):
    ```python
    async def stop(self) -> None:
        if not self.is_running:
            return
    ```
    `self.is_running` is set to `True` only after preflight, database init, and heartbeat registration complete (line 152). If a shutdown signal arrives while `start()` is in progress, `stop()` returns immediately, abandoning in-flight tasks and failing to close the session or update the database heartbeat to `STOPPED`.
  - Dangling runner task (`worker.py:183-185`):
    ```python
    if self._runner_task and not self._runner_task.done():
        self._runner_task.cancel()
    ```
    The task is cancelled but never awaited (`await self._runner_task`), risking unhandled `CancelledError` warnings and unawaited network teardowns.

- **`backend/app/live_paper/session_runner.py:374-432` (`LivePaperSessionRunner.stop`)**:
  - In contrast to `worker.py`, `session_runner.py` correctly cancels and awaits its owned background tasks:
    `tasks = [t for t in (self._heartbeat_task, self._mtm_task, self._scan_task, self._clock_task) if t]`
    `await asyncio.gather(*tasks, return_exceptions=True)`
  - Distinguishes mid-session shutdown from session close: if stopped before 15:40 IST (`FNO_CLOSE_TIME`), emits `WORKER_SHUTDOWN` without premature session finalization.

---

### 2. Authentication, Security, and Credential Handling

#### Observations:
- **Server Auth Implementation (`backend/app/security/auth.py`)**:
  - `verify_api_key` (lines 57–109): Inspects `X-API-Key` or `Authorization: Bearer <token>`. Compares against `settings.api_auth_token` using `secrets.compare_digest`. Fails closed with HTTP 401 if `api_auth_token` is unconfigured.
  - `authorize_account_access` (lines 39–55): Enforces strict tenant/account boundary checking, raising HTTP 403 on mismatched `target_account_id`.

- **Unauthenticated Portfolio Disclosure (`backend/app/main.py:974-984`)**:
  ```python
  @app.get("/api/paper/positions")
  async def get_paper_positions(account_id: Optional[str] = None, auth: Optional[AccountContext] = Depends(verify_api_key_optional)):
      if account_id:
          if not auth:
              raise HTTPException(status_code=401, detail="Authentication required...")
          authorize_account_access(auth, account_id)
      summary = paper_engine.get_portfolio_summary(account_id=account_id or (auth.account_id if auth else None))
      return summary
  ```
  - When `account_id` is omitted and `auth` is `None`, no authentication is required! `paper_engine.get_portfolio_summary(account_id=None)` executes and returns all open positions across the system.

- **Missing State & Expiry Revalidation (`backend/app/main.py:2451-2510`)**:
  - `POST /api/signals/{signal_id}/paper-trade`: Requires authentication, but only checks:
    ```python
    q_grade = getattr(signal.quality_grade, "value", signal.quality_grade)
    if q_grade in ("NO TRADE", "NO_TRADE"):
        raise HTTPException(status_code=400, detail="Cannot paper trade a NO TRADE signal")
    if not signal.entry or not signal.stop_loss:
        raise HTTPException(status_code=400, detail="Signal missing entry price or stop loss")
    ```
  - Does **not** verify whether `signal.state == "QUALIFIED"`. Expired (`signal.expiry < now`), invalidated, or already-triggered signals are accepted without revalidating price freshness or risk limits at action time.

- **Frontend Security Violations**:
  - `frontend/src/App.tsx:669-672`: `handlePaperOrder` sends a raw `fetch('/api/paper/order')` with **no** auth headers.
  - `frontend/src/App.tsx:701-703`: `handleClosePaperPosition` sends `fetch('/api/paper/close/${id}')` with **no** auth headers.
  - `frontend/src/App.tsx:713`:
    ```typescript
    setPaperPositions((prev) => prev.filter((p) => p.id !== id));
    ```
    Executed unconditionally outside `if (res.ok)`. When a close request fails (HTTP 401, 500, network error), the position is purged from local client state while remaining open on the server ledger!
  - `frontend/src/components/pages/SignalCenterPage.tsx:846`: Hardcoded dev key:
    `headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' }`
  - `frontend/src/components/pages/SignalCenterPage.tsx:850`: Treats HTTP 200 `res.ok` as fill confirmation, ignoring whether backend returned `{ "order_result": { "status": "REJECTED" } }`.

- **Localhost Binding (`backend/app/worker.py:465`)**:
  - Defaults to `host = os.environ.get("HOST", "0.0.0.0")`, binding to all network interfaces by default rather than local loopback (`127.0.0.1`).

---

### 3. Decision Engine & Ingestion Architecture

#### Observations:
- **Derivatives Omission in Scanner (`backend/app/signal_engine/scanner.py:278-285`)**:
  - The market opportunity scanner builds candidate records exclusively with `asset_class=AssetClass.EQUITY`:
    ```python
    candidate = CandidateRecord(
        symbol=symbol,
        exchange="NSE",
        asset_class=AssetClass.EQUITY,
        last_price=float(quote.get("ltp", 0)),
        ...
    )
    ```
  - Indian futures and options are completely absent from market-wide scanning.

- **Synthetic Derivatives Data Substitution (`backend/app/signal_engine/signal_pipeline.py:608-614`)**:
  ```python
  f_res = FuturesEngine.analyze(
      underlying_symbol=symbol,
      underlying_direction=direction,
      underlying_price=ltp,
      futures_price=float(futures_data.get("futures_price", ltp)),
      dte=int(futures_data.get("dte", 15)),
      volume=int(futures_data.get("volume", 50000)),
      oi=int(futures_data.get("oi", 500000)),
      oi_change_pct=float(futures_data.get("oi_change_pct", 0.0)),
      lot_size=int(futures_data.get("lot_size", 250)),
      margin_per_lot=float(futures_data.get("margin_per_lot", 150000.0)),
      ...
  )
  ```
  - When real contract data is missing, the engine invents DTE (15), volume (50,000), OI (500,000), lot size (250), and margin (₹150,000). Violates R2 requirement to fail closed with UNAVAILABLE / missing data.

- **Configuration Mismatches & Silent Degradation**:
  - Expiry mismatch (`signal_pipeline.py:585` vs `:717`):
    Line 585: `expiry_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3 * 900))` (hardcoded 3x 15m).
    Line 717: `expiry_condition=f"Valid for {config.signal_expiry_candles} candles on {config.primary_timeframe} timeframe"`.
  - Silent primary timeframe substitution (`signal_pipeline.py:352-357`):
    ```python
    if not all_candles:
        for tf in config.mtf_timeframes:
            if candles_by_timeframe.get(tf):
                all_candles = candles_by_timeframe[tf]
                break
    ```
    Silently uses whatever candle timeframe is found without flagging degraded data.
  - Provenance inference (`signal_pipeline.py:572-577`): Inferred solely from `quote.get("is_live")`, ignoring candle provenance.
  - Yahoo Finance candle gap filling (`backend/app/broker_providers/upstox_client.py:492-494`): Missing high/low are filled with `max(open, close)` and `min(open, close)`, and missing volume is set to 0.

- **Scan Coverage Ledger Gaps (`backend/app/signal_engine/models.py:403-417`)**:
  - `ScannerPipelineStats` records attrition stages (`universe_size`, `data_valid`, `initial_screened`, `qualified`, etc.), but does not track:
    - Requested count
    - Eligible count
    - Evaluated count
    - Unavailable count
    - Skipped count with explicit reasons
    - Rejected count with gate breakdown
    - Evaluation timestamps per instrument

- **Directional Geometry Validation**:
  - `backend/app/signal_engine/validation_gates.py:310-355` (`gate_stop_determinable`):
    ```python
    stop_pct = abs(entry_price - stop_price) / entry_price * 100
    ```
    Uses `abs(...)`. Does not verify `stop < entry` for LONG or `stop > entry` for SHORT!
  - `backend/app/signal_engine/stop_target_engine.py`: Snaps `t1_price` to nearby resistance without ensuring `t1_price > entry` for LONG, or `t1_price < entry` for SHORT.
  - Missing server-side hard validation for:
    - LONG: `stop < entry < target_1 < target_2 < target_3`
    - SHORT: `target_3 < target_2 < target_1 < entry < stop`.

---

### 4. Paper Trading & Server Ledger Architecture

#### Observations:
- **Competing Dual Paper Engines**:
  - **Engine A**: `backend/app/paper_trading/engine.py` (`PaperTradingEngine`).
    - Authoritative engine wired to `POST /api/paper/order`, `POST /api/paper/close/{pos_id}`, and database sync via `PaperRepository`.
    - Mark-to-market method (`update_market_price`, lines 217–227) **only** updates `currentPrice`, `unrealizedPnL`, and `unrealizedPnLPercent`. It has **no** automated exit evaluation for stop-loss, target, or timeout!
  - **Engine B**: `backend/app/paper_engine/bridge.py` (`PaperTradingBridge`).
    - Separate in-memory bridge. Contains `update_positions_mark_to_market` with SL/TP triggers.
    - Long-biased exit arithmetic bug (`bridge.py:219, 224, 231`):
      `gross_unrealized = (pos.current_price - pos.entry_price) * pos.quantity` (LONG only).
      `if current_candle_low <= pos.stop_loss: close_position(pos.stop_loss, ..., ExitReason.STOP_LOSS)` (LONG only).
      For a SHORT trade, stop loss is hit on a price RISE (`current_candle_high >= pos.stop_loss`), not low!
  - Disconnected aggregation in `main.py:983`:
    ```python
    if not summary.get("performance", {}).get("total_trades"):
        summary["performance"] = paper_bridge.get_performance_summary()
    ```

- **Volatile Idempotency Cache (`backend/app/paper_trading/engine.py:74, 213`)**:
  - `self.idempotency_cache: Dict[str, Dict[str, Any]] = {}` is an in-memory dictionary.
  - Not persisted in PostgreSQL or SQLite. Process restart wipes idempotency, risking duplicate order fills on client retries.

- **Absence of Server-Side Trade Journal Table (`backend/app/database/models.py`)**:
  - `PaperClosedTradeModel` (lines 168–186) stores only basic financial fields (`trade_id`, `entry_price`, `exit_price`, `realized_pnl`, `brokerage`, `taxes`).
  - Lacks:
    - `signal_id` / `decision_fingerprint`
    - `strategy_id` / `strategy_version` / `configuration_hash`
    - Deterministic calculation evidence snapshot
    - `exit_reason` (TP, SL, INVALIDATION, TIME_EXIT, MANUAL)
    - Monotonic audit sequence number
  - `POST /api/journal/analytics` in `main.py:1039-1041` operates directly on user-supplied request body lists rather than querying the persistent server ledger.

- **Crash Recovery State**:
  - `PaperTradingEngine.load_from_db()` (lines 407–428) successfully recovers capital, positions, and closed trades from `PaperRepository`.
  - However, in-flight orders, pending exit triggers, and idempotency state are not restored.

---

### 5. AI Explanation Service & Evidence Grounding

#### Observations:
- **Security & Secret Leakage in REST Client (`backend/app/ai_engine/gemini_client.py:37, 81`)**:
  ```python
  url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
  ```
  - The API key is passed in the URL query string, exposing credentials in proxy logs, web server access logs, and HTTP traces. It must be moved to the `x-goog-api-key` header.
  - Model defaults to `"gemini-2.5-flash"` rather than verified current models.

- **FastAPI Event-Loop Blocking**:
  - `backend/app/ai_engine/agents.py:16`:
    ```python
    async def _call_gemini_async(client: Any, model: str, contents: str) -> Any:
        if client and hasattr(client, "models"):
            if hasattr(client.models, "generate_content_async"):
                return await client.models.generate_content_async(model=model, contents=contents)
            return client.models.generate_content(model=model, contents=contents) # BLOCKS!
    ```
  - `backend/app/ai_engine/chief_analyst.py:270-273`:
    ```python
    async def _synthesize_with_llm(self, ...):
        response = self.client.models.generate_content( # BLOCKS!
            model="gemini-2.5-flash",
            contents=prompt
        )
    ```
    Synchronous HTTP execution inside `async def` blocks the FastAPI event loop for up to 15 seconds.

- **Missing Evidence-Grounded AI Explanation Service**:
  - No endpoints or backend services exist to generate explanations for:
    1. Actionable signals (explaining why the trade was qualified, citing entry, stop, target, R:R, and strategy votes).
    2. No-trade states (explaining why a symbol was rejected, citing specific failed hard gates or regime incompatibilities).
    3. Trade journal reviews (reviewing executed paper trades against planned stops and targets).
  - `PersonalTradingCoach.analyze_trader_journal` (agents.py:180–209) is a static heuristic stub calculating average win/loss and returning canned strings without calling an LLM or citing calculation evidence.

---

### 6. Backend Test Suite Baseline & Pass/Fail Status

#### Observations:
- **Test Inventory**:
  - Ripgrep search and pytest collection discovered **357 tests** across 50+ test files.
  - Directory structure:
    - `backend/tests/acceptance/`: End-to-end acceptance tests for database, security, market data, paper trading, websocket, and quant engine.
    - `backend/tests/live_paper/`: Autonomous session runner, preflight, safety invariants, master evidence logger, worker lifecycle, and replay.
    - `backend/tests/signal_engine/`: Financial invariants, F&O and costs, lifecycle and persistence, lookahead certification, and walk-forward validation.
    - `backend/tests/strategy_engine/`: Conformance matrices across all 20 systematic strategies.
    - `backend/tests/`: Root-level unit and integration suites.

- **Test Runner Configuration**:
  - Runner: `python -m pytest backend/tests`.
  - Python runtime: Python 3.14.0 (Windows).
  - Pytest collection duration: 19.62s (357 tests collected).

- **Dry-Run Baseline Execution**:
  - Targeted verification command:
    ```powershell
    python -m pytest backend/tests/test_security_hardening.py backend/tests/test_unified_paper_order.py backend/tests/signal_engine/test_financial_invariants.py backend/tests/live_paper/test_safety_invariants.py backend/tests/acceptance/test_paper_acceptance.py -q
    ```
  - Output summary:
    ```
    .............................. [100%]
    30 passed, 1 warning in 71.94s
    ```
  - Result: **30 passed, 0 failed** (100% pass rate).
  - Deprecation warning noted: `google.genai.types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17`.

---

## Actionable Recommendations for Implementation

| Priority | Component | Recommendation | Target Files |
|:---:|---|---|---|
| **P0** | Lifespan & Shutdown | Wrap `yield` in `try...finally` in both `main.py` and `worker.py`. Retain worker background task. Await task cancellation in `worker.stop()`. Add explicit `disconnect()` to `MarketDataService`. | `backend/app/main.py`<br>`backend/app/worker.py`<br>`backend/app/market_data/service.py` |
| **P0** | Security & Auth | Enforce mandatory auth on `/api/paper/positions`. Add auth headers to frontend `App.tsx`. Remove dev key from `SignalCenterPage.tsx`. Require valid backend order state. Bind worker to `127.0.0.1`. | `backend/app/main.py`<br>`backend/app/worker.py`<br>`frontend/src/App.tsx`<br>`frontend/src/components/pages/SignalCenterPage.tsx` |
| **P0** | Paper Exit Lifecycle | Unify into one authoritative server engine (`PaperTradingEngine`). Add side-correct automated exit triggers (TP, SL, timeout) to tick/candle processing. Persist idempotency keys in DB. | `backend/app/paper_trading/engine.py`<br>`backend/app/paper_engine/bridge.py`<br>`backend/app/database/repositories/paper_repository.py` |
| **P1** | Decision Engine | Fail closed on missing derivatives parameters (no synthetic DTE/OI/volume). Enforce LONG (`stop < entry < targets`) and SHORT (`targets < entry < stop`) geometry in `validation_gates.py`. | `backend/app/signal_engine/signal_pipeline.py`<br>`backend/app/signal_engine/validation_gates.py`<br>`backend/app/signal_engine/stop_target_engine.py` |
| **P1** | Scan Coverage Ledger | Expand `ScannerPipelineStats` to record requested, eligible, evaluated, unavailable, skipped (with reasons), and rejected counts with timestamps. | `backend/app/signal_engine/models.py`<br>`backend/app/signal_engine/scanner.py` |
| **P1** | Immutable Journal | Add `paper_journal` table with links to `signal_id`, `configuration_hash`, evidence snapshot, `exit_reason`, and monotonic sequence numbers. | `backend/app/database/models.py`<br>`backend/app/database/repositories/journal_repository.py` |
| **P2** | AI Explanations | Replace query-param key with header in `gemini_client.py`. Use non-blocking async calls. Build typed explanation service citing deterministic signal and rejection evidence with graceful offline fallback. | `backend/app/ai_engine/gemini_client.py`<br>`backend/app/ai_engine/agents.py`<br>`backend/app/ai_engine/chief_analyst.py` |
