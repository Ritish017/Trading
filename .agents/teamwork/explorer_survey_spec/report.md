# APEX Quantitative Workstation: Specification Mining & Requirements Inventory

**Document Version**: 1.0.0  
**Date**: 2026-10-06  
**Author**: teamwork_preview_spec_miner (Specification Investigator)  
**Workspace**: `C:\Tradinf2`  
**Repository**: `https://github.com/Ritish017/Trading` (Commit: `34849a90596eb8af218268cdebabb561ca627ede`)  

---

## 1. Executive Summary & Specification Scope

The APEX workstation is a personal, agentic quantitative research and trading system designed specifically for Indian equities (NSE/BSE) and derivatives (Futures & Options). It is strictly architected for single-user personal operation, explicitly excluding SaaS multitenancy, subscription billing, copy trading, social feeds, and public cloud infrastructure complexity.

The objective of this specification mining investigation is to synthesize the complete, authoritative system specification across user mandates and engineering briefs:
1. `C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md` (Core mandate & acceptance criteria)
2. `C:\Tradinf2\docs\APEX_ANTIGRAVITY_MASTER_PROMPT.md` (Master engineering brief, roles, milestone gates, invariants)
3. `C:\Tradinf2\docs\APEX_PROJECT_CONTEXT.md` (Consolidated architectural history, decisions, certified baselines)
4. `C:\Tradinf2\docs\APEX_ANTIGRAVITY_RESEARCH.md` (Diagnostic evidence, gap audits, model capabilities)

The system enforces a non-negotiable divide: **Automated Analysis, Real Market Ingestion, and Full Paper Execution Lifecycle are fully enabled**, while **Live Broker Order Execution is strictly and permanently disabled**.

---

## 2. Authoritative Specification Sources & Document Hierarchy

When architectural ambiguity arises, the following precedence order applies:
1. **User Request & Master Prompt** (`ORIGINAL_REQUEST.md`, `APEX_ANTIGRAVITY_MASTER_PROMPT.md`): Primary functional contract, acceptance criteria, safety invariants.
2. **Current Repository Audit & Research Findings** (`APEX_ANTIGRAVITY_RESEARCH.md`): Verified code anomalies, line-level diagnostics, benchmark evidence.
3. **Consolidated Project Context** (`APEX_PROJECT_CONTEXT.md`): Architectural history, past passes, design decisions.
4. **Existing Codebase & Certified Invariant Tests** (`backend/tests/`): Mathematical and geometrical test oracles.

---

## 3. Detailed Specification by Requirement Pillar (R1 – R5)

### R1. Baseline Integrity & First-Wave Defect Repairs
* **R1.1 Canonical Quote Store TypeScript Fix**:
  * *File*: `frontend/src/stores/canonicalQuoteStore.ts` (lines 152, 163).
  * *Defect*: `updateFromWs` references undeclared variable `incomingTs`, causing TS2304 compile failures during `npm run lint` (`tsc --noEmit`), even though Vite bundler tolerates it.
  * *Requirement*: Extract incoming timestamp from incoming tick payload (`tick.timestamp ?? tick.time ?? Math.floor(Date.now() / 1000)`), normalize to epoch seconds, and eliminate all TS diagnostics.
* **R1.2 FastAPI Lifespan Exception/Cancellation Guard**:
  * *File*: `backend/app/main.py` (lines 114–134).
  * *Defect*: Bare `yield` inside `@asynccontextmanager async def app_lifespan(app: FastAPI)` without `try ... finally`. If an exception or cancellation occurs during app operation, subsequent shutdown code (provider disconnect, resource cleanup) is bypassed.
  * *Requirement*: Wrap the `yield` in a `try ... finally` block, ensuring `market_data_service.active_provider.disconnect()` is guaranteed to execute upon cancellation or error.
* **R1.3 Stateful Market Worker Lifespan & Startup Task Retention**:
  * *File*: `backend/app/worker.py` (lines 220–235).
  * *Defect*: Bare `yield` inside `worker_lifespan`. Background startup task created via `asyncio.create_task(worker_instance.start())` is fire-and-forget; its reference is not retained, risking unhandled garbage collection or orphaned execution, and shutdown fails to cancel/await the task cleanly.
  * *Requirement*: Retain worker task handle (`self._worker_task`), guard `yield` with `try ... finally`, cleanly signal shutdown, cancel the worker task, and await its termination.
* **R1.4 Paper Order and Close Authentication Enforced in UI**:
  * *File*: `frontend/src/App.tsx` (lines 669–695, 701–714).
  * *Defect*: `handlePaperOrder` and `handleClosePaperPosition` issue `fetch` calls to `/api/paper/order` and `/api/paper/close/{id}` without `Authorization` or `X-API-Key` headers. When auth is enabled on the backend, mutations fail with 401.
  * *Requirement*: Provide authenticated request headers sourced from user session state.
* **R1.5 Non-Destructive Position Close Failure Handling**:
  * *File*: `frontend/src/App.tsx` (line 713).
  * *Defect*: `setPaperPositions((prev) => prev.filter((p) => p.id !== id))` is placed unconditionally outside the `if (res.ok)` check. A failed or rejected close request still purges the position from the UI state, causing position disappearance.
  * *Requirement*: Only remove the position from local UI state if the backend confirms successful closure (`res.ok && data.status === 'CLOSED'`). On failure or network error, retain the position and surface an explicit error toast.
* **R1.6 Hardcoded Development Credential Elimination**:
  * *File*: `frontend/src/components/pages/SignalCenterPage.tsx` (line 846).
  * *Defect*: Hardcoded `'X-API-Key': 'apex_default_dev_key'` is bundled into the client build.
  * *Requirement*: Remove hardcoded credentials from frontend source code; inject session token via secure app state or environment-configured client headers.
* **R1.7 Authoritative Backend Order State Fill Confirmation**:
  * *File*: `frontend/src/components/pages/SignalCenterPage.tsx` (lines 850–856) and `backend/app/main.py` (lines 2501–2511).
  * *Defect*: Client checks `if (res.ok)` (HTTP 200) to confirm paper order fill. However, `/api/signals/{id}/paper-trade` returns HTTP 200 with `order_result: {"status": "REJECTED", "reason": "..."}`, resulting in false "Order Placed" notifications for rejected orders.
  * *Requirement*: UI must inspect `data.order_result.status === 'FILLED'` before confirming order placement; rejected orders must display the specific rejection reason.

---

### R2. Server-Authoritative Decision Contract & Market Ingestion
* **R2.1 Unified Versioned Decision Contract**:
  * *Files*: `backend/app/signal_engine/models.py`, `version_freeze.py`.
  * *Specification*: All decision pipelines (scanner, observatory, API, UI, AI explanations, replay) must bind to one unified `SignalDecision` schema.
  * *Fields Required*:
    - Stable instrument ID, exchange (`NSE`/`BSE`), asset class (`EQUITY`, `FUTURES`, `OPTIONS`).
    - Source timestamp, receipt timestamp, input provenance (`RAW_AUTHENTIC_DATA`, `HISTORICAL_RESEARCH_RESULT`, `SIMULATED`, `UNAVAILABLE`, `DEGRADED`), freshness (`LIVE`, `HISTORICAL`).
    - Cryptographic strategy/configuration hash (`d3e94bea...`), strategy version (`2026.1.0-FROZEN`), git commit.
    - Market regime, applicability status, and vote outcome for all 20 strategies (`passed`, `failed`, `not_applicable`, `unavailable`).
    - Hard eligibility/risk gates separated from soft confluence scores.
    - Entry trigger, valid price zone, stop-loss, ordered targets, invalidation level, expiry timestamp, quantity, capital/margin requirements, estimated statutory transaction costs.
    - Explicit `reasons_why` citing deterministic calculation evidence.
* **R2.2 Genuine Derivative Contract Parameter Requirement**:
  * *Files*: `backend/app/signal_engine/signal_pipeline.py` (lines 608–617), `futures_engine.py`, `options_engine.py`.
  * *Defect*: `signal_pipeline.py` substitutes hardcoded default numbers (`dte=15`, `volume=50000`, `oi=500000`, `lot_size=250`, `margin_per_lot=150000.0`).
  * *Requirement*: Ban synthetic number injection. Require authentic contract parameters (expiry, lot size, tick size, open interest, volume, bid/ask spread, applicable margin).
* **R2.3 Fail-Closed Derivatives Unavailable Handling**:
  * *Requirement*: If genuine F&O chain, lot size, or margin inputs are missing or incomplete, the engine must fail closed with an explicit `UNAVAILABLE` or `OPTIONS_DATA_INSUFFICIENT` / `FUTURES_DATA_INSUFFICIENT` decision, rather than fabricating plausible numbers.
* **R2.4 Instrument Master & Scan Coverage Ledger**:
  * *Files*: `backend/app/signal_engine/scanner.py`, `models.py`.
  * *Specification*: The scanner must maintain an authoritative instrument master and emit a `ScanCoverageLedger` for every scan run.
  * *Required Metrics*: Total requested universe, eligible instruments, evaluated instruments, unavailable instruments (with missing data reason), skipped instruments (with gate reason), rejected instruments, and qualified signals, accompanied by evaluation timestamps.
  * *Rule*: No silent truncation of universe; do not claim full scan coverage if only a subset was processed.
* **R2.5 Deterministic Feature Caching**:
  * *Specification*: Compute features once per completed bar / timeframe / instrument / input version (`compute_market_features`). Avoid recomputing indicators on every tick or during repeated UI fetches.
* **R2.6 Strict Directional Geometry Invariants**:
  * *Rule for LONG*: `stop_loss < entry_price < target_1 < target_2 < target_3`.
  * *Rule for SHORT*: `target_3 < target_2 < target_1 < entry_price < stop_loss`.
  * *Validation*: Invariants must strictly reject zero, negative, infinite values, inverted stops, or targets on the wrong side of entry. Risk distance (`|entry - stop|`) must be > 0.
* **R2.7 Primary Timeframe Integrity**:
  * *Files*: `backend/app/signal_engine/signal_pipeline.py` (lines 352–357).
  * *Defect*: Silently falls back to another timeframe from `mtf_timeframes` if primary timeframe candles are missing.
  * *Requirement*: If the configured primary timeframe (e.g. 5m) lacks candles, do NOT substitute 15m/1h without marking the decision as `DEGRADED` or rejecting with `TIMEFRAME_UNAVAILABLE`.
* **R2.8 Signal Expiry Synchronization**:
  * *Files*: `backend/app/signal_engine/signal_pipeline.py` (lines 585, 717).
  * *Defect*: Expiry timestamp is hardcoded to `3 * 900` (45 min) while description says `Valid for {signal_expiry_candles} candles on {primary_timeframe}`.
  * *Requirement*: Synchronize timestamp computation with configuration: `now + (signal_expiry_candles * timeframe_duration_seconds)`.
* **R2.9 Authentic Data Provenance & Gap Preservation**:
  * *Files*: `backend/app/broker_providers/upstox_client.py` (line 492).
  * *Defect*: Yahoo fallback fills missing high/low with max(open, close) and missing volume with 0, while stamping data as `RAW_EXCHANGE_PRICE`.
  * *Requirement*: Preserve genuine missingness in OHLCV; never fabricate substitute prices or zero volumes. Non-live or fallback data must never be stamped `RAW_AUTHENTIC_DATA`.

---

### R3. Authoritative Paper Execution, Exit Lifecycle, and Journaling
* **R3.1 Unified Server Ledger & Mark-to-Market**:
  * *Files*: `backend/app/paper_trading/engine.py`, `backend/app/paper_engine/bridge.py`.
  * *Defect*: Dual un-unified paper engines: `paper_trading/engine.py` updates mark-to-market prices without executing automated exits; `paper_engine/bridge.py` contains long-biased automated exit logic.
  * *Requirement*: Consolidate into a single authoritative server ledger. Client localStorage is strictly a read cache. MTM updates must evaluate stop-loss, target, and invalidation triggers automatically.
* **R3.2 Pre-Submission Revalidation**:
  * *Files*: `backend/app/main.py` (lines 2464–2500).
  * *Defect*: `/api/signals/{id}/paper-trade` fails to check whether signal state is `QUALIFIED` or whether signal has expired.
  * *Requirement*: Server must revalidate:
    1. Signal state == `QUALIFIED` (reject `TRIGGERED`, `EXPIRED`, `INVALIDATED`, `CANCELLED`).
    2. Current timestamp < `signal.expiry`.
    3. Price within valid entry zone (`entry_zone_low <= ltp <= entry_zone_high`).
    4. Account ownership and risk limits.
* **R3.3 Durable Idempotency Enforcement**:
  * *Requirement*: Generate and persist durable idempotency keys for signal submissions (`signal_{signal_id}`). Prevent concurrent submissions or rapid double-clicks from creating duplicate fills or overdrawing cash balance.
* **R3.4 Side-Correct Automated Exits**:
  * *Defect*: `bridge.py` lines 219–235 calculate gross unrealized P&L as `(current - entry) * qty` and checks `low <= stop` for all positions, failing for SHORT positions.
  * *Requirement*:
    * *LONG Exits*:
      * Stop Loss: `current_low <= stop_loss` -> Exit at `stop_loss` (or open if gap down). Realized PnL = `(exit - entry) * qty - frictions`.
      * Take Profit: `current_high >= take_profit` -> Exit at `take_profit`. Realized PnL = `(exit - entry) * qty - frictions`.
    * *SHORT Exits*:
      * Stop Loss: `current_high >= stop_loss` -> Exit at `stop_loss` (or open if gap up). Realized PnL = `(entry - exit) * qty - frictions`.
      * Take Profit: `current_low <= take_profit` -> Exit at `take_profit`. Realized PnL = `(entry - exit) * qty - frictions`.
* **R3.5 Conservative Gap & Same-Bar Ambiguity Policy**:
  * *Specification*: When replaying bar data where both stop-loss and take-profit levels are breached within the same bar (`high >= target` and `low <= stop`), apply a strict conservative policy: **assume STOP LOSS was hit first**, unless intra-bar tick sequence proves otherwise. Never assume optimistic fills.
* **R3.6 Immutable Journal & Evidence Fingerprinting**:
  * *Specification*: Persist a durable, immutable journal (`PaperTradeAudit` / SQLite / PostgreSQL). Link every trade entry and exit to:
    - Original `signal_id`.
    - Cryptographic `configuration_hash`.
    - Strategy consensus votes and evidence snapshot.
    - Fill price, exit price, duration, slippage, statutory taxes (STT, stamp duty, exchange turnover fee, GST, SEBI turnover fee), and net P&L.
* **R3.7 Crash Recovery & State Reconstruction**:
  * *Specification*: On server or worker startup, restore:
    - Active open positions.
    - Cash balance and allocated margin.
    - Pending orders.
    - Monotonic audit sequence progression.
  * *Rule*: A simulated restart with open positions must leave positions and cash intact without duplicate session starts or sequence resets.
* **R3.8 Session Ownership & Finalization Boundaries**:
  * *Specification*: Standard NSE session boundaries: 09:15 market open, 15:30 equity close, 15:40 F&O finalization. Mid-session worker stoppage (e.g. 11:30 IST) must be logged as `WORKER_SHUTDOWN`, **not** `SESSION_FINALIZED`. A subsequent restart on the same trading day must resume the active session with `WORKER_RECOVERY` without resetting audit sequences.

---

### R4. Grounded AI Explanations and Educational UI
* **R4.1 Three-View Primary Navigation**:
  * *Files*: `frontend/src/App.tsx`, `frontend/src/components/NavigationTabs.tsx`.
  * *Specification*: Redesign the flat 12-tab navigation into three primary daily workflow views:
    1. **Today**: System health, scan coverage, actionable qualified signals, waiting conditions, explicit no-trade reasons.
    2. **Positions & Journal**: Canonical paper portfolio, real-time MTM, net P&L after statutory frictions, historical journal, exit logs.
    3. **Learn**: Plain-language explanations of active setups, mathematical indicator definitions, risk/reward principles, uncertainty explanations.
* **R4.2 Preservation of Advanced Views Group**:
  * *Specification*: Retain all existing specialized desks under a dedicated, collapsible **Advanced** navigation group:
    - Trading Terminal
    - AI Market Intelligence Desk
    - Derivatives Lab
    - Institutional Desk (FII/DII flow & market breadth)
    - Backtest Lab
    - Strategy Lab
    - Fundamental Analysis
    - Quantitative Research Factory
    - Command Center
* **R4.3 Asynchronous Non-Blocking Runtime AI Adapter**:
  * *Files*: `backend/app/ai_engine/agents.py` (lines 11–17), `chief_analyst.py` (lines 270–273), `gemini_client.py`.
  * *Defect*: `_call_gemini_async` attempts `client.models.generate_content_async` (which does not exist in standard SDK) and falls back to synchronous `client.models.generate_content`, blocking FastAPI's event loop. `chief_analyst.py` also calls synchronous SDK methods inside async functions.
  * *Requirement*: Use proper async SDK interface (`client.aio.models.generate_content`) or non-blocking HTTP (`httpx.AsyncClient`). Never run blocking network calls inside FastAPI coroutines.
* **R4.4 Deterministic Evidence Citations & Anti-Hallucination**:
  * *Files*: `frontend/src/App.tsx` (lines 637–644), `frontend/src/utils/indianTechnicalAnalysis.ts` (lines 101–117).
  * *Defect*: UI fabricates tactical trade setups (entry, stop, target, 1:2.0 RR) from narrative AI commentary and stock high/low.
  * *Requirement*: Prohibit AI from generating authoritative tactical price levels. All prices, stops, targets, and sizing must come from the quantitative signal engine. Runtime AI is restricted to explaining verified evidence, citing specific indicator values, and summarizing risks.
* **R4.5 Graceful Degradation & Quota Handling**:
  * *Specification*: When AI services experience timeouts (>15s), rate limits (HTTP 429), or outages, the system must degrade gracefully:
    - Display honest "AI Analysis Temporarily Unavailable" badge.
    - Zero disruption to quantitative signal generation, market data feeds, paper execution, or automated exits.
    - No fabricated synthetic text or fake confidence percentages.
* **R4.6 Security of AI Prompts & Least Privilege**:
  * *Specification*: Treat market news and external commentary as untrusted input data, never executable instructions. Never provide broker execution, system shell, or secret retrieval tools to the runtime explanation model. Redact API keys, account identifiers, and private holdings from prompt context.

---

### R5. Security, Local Operation, and Real-Money Guardrails
* **R5.1 Absolute Real-Money Execution Prohibition**:
  * *Files*: `backend/app/live_paper/safety.py`, `backend/app/config.py`.
  * *Invariants*: `LIVE_ORDER_ALLOWED = False`, `LIVE_TRADING_ENABLED = False`. Any call attempting to route live orders must immediately raise `LiveOrderForbiddenSecurityError`.
  * *Requirement*: Broker API integration remains strictly read-only for market data ingestion.
* **R5.2 Local Loopback Service Binding**:
  * *Specification*: Default backend host binds to `127.0.0.1` / `localhost`. CORS allowed origins restricted to local development addresses (`localhost:5173`, `127.0.0.1:5173`, `localhost:3000`). Public self-registration is permanently disabled.
* **R5.3 Server-Side Secrets & Query URL Key Redaction**:
  * *Files*: `backend/app/ai_engine/gemini_client.py` (lines 37, 81).
  * *Defect*: API key is passed as query parameter `?key={api_key}`, leaking secrets into HTTP proxy logs and error traces.
  * *Requirement*: Pass `x-goog-api-key` header in HTTPS requests. Eliminate all API keys from frontend bundles, query strings, and log messages.
* **R5.4 Fail-Closed Authentication & IDOR Defense**:
  * *Files*: `backend/app/main.py` (lines 965–1000).
  * *Specification*: All state mutation endpoints (`/api/paper/order`, `/api/paper/close/{id}`, `/api/signals/{id}/paper-trade`) require authentication via `verify_api_key`. Enforce tenant/account verification: an authenticated user cannot view or mutate positions belonging to another account.
* **R5.5 Unauthenticated Portfolio Read Information Leak Fix**:
  * *Files*: `backend/app/main.py` (lines 975–984).
  * *Defect*: Querying `/api/paper/positions` without `account_id` bypasses authentication checks and returns global aggregate portfolio positions.
  * *Requirement*: Require authentication or isolate to caller's verified personal account session; never expose cross-account aggregates to unauthenticated callers.

---

## 4. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R1: Baseline Integrity | Canonical Quote Store TS Fix | Resolve undeclared `incomingTs` references in `canonicalQuoteStore.ts` | Normalized tick payload (`tick.timestamp`, `tick.time`) | `CanonicalQuote` record with valid epoch seconds | Defaults to `Math.floor(Date.now() / 1000)` if timestamp missing | `canonicalQuoteStore.ts:152, 163`, `APEX_ANTIGRAVITY_RESEARCH.md:46` |
| 2 | R1: Baseline Integrity | FastAPI Lifespan Cancellation Guard | Ensure provider disconnect and resource cleanup execute on error or cancellation | ASGI lifespan context | Safe shutdown of active broker connections | `try ... finally` guarantees `disconnect()` runs despite cancellation | `backend/app/main.py:114`, `APEX_PROJECT_CONTEXT.md:130` |
| 3 | R1: Baseline Integrity | Worker Lifespan & Task Retention | Guard worker lifespan and retain background task handle to prevent task orphaning | Worker FastAPI lifespan | Clean task cancellation and state flush | Cleanly cancels and awaits `_worker_task` on SIGINT/SIGTERM | `backend/app/worker.py:220`, `APEX_ANTIGRAVITY_RESEARCH.md:41` |
| 4 | R1: Baseline Integrity | Authenticated Paper Order Submissions | Propagate auth credentials from UI session to `/api/paper/order` and `/api/paper/close/{id}` | User session token, order payload | Authenticated HTTP request with auth header | Rejects unauthenticated requests with HTTP 401 | `frontend/src/App.tsx:669, 701`, `ORIGINAL_REQUEST.md:15` |
| 5 | R1: Baseline Integrity | Non-Destructive Position Close | Retain position in UI local state if backend close request fails or errors | Close response status | Position preserved in UI list on error; removed only on confirmed close | Displays error notification toast, leaves position intact | `frontend/src/App.tsx:713`, `APEX_ANTIGRAVITY_RESEARCH.md:36` |
| 6 | R1: Baseline Integrity | Development Key Elimination | Remove hardcoded `apex_default_dev_key` from frontend client code | Client session context | Requests use dynamic session auth headers | Rejects hardcoded dev keys in production | `SignalCenterPage.tsx:846`, `ORIGINAL_REQUEST.md:16` |
| 7 | R1: Baseline Integrity | Authoritative Fill Confirmation | Treat only `status === 'FILLED'` from backend as fill confirmation, not generic HTTP 200 | Order response payload | Success banner only on `FILLED`; error toast on `REJECTED` | Displays specific rejection reason if status is REJECTED | `SignalCenterPage.tsx:850`, `backend/app/main.py:2501` |
| 8 | R2: Decision Contract | Unified Decision Contract | Canonical `SignalDecision` schema binding all signal generation, UI, and AI | Candidate instrument, multi-TF candles, live quote | Typed `SignalDecision` with cryptographic config hash | Produces `NO_TRADE` with explicit `RejectionRecord` on failure | `backend/app/signal_engine/models.py:300`, `APEX_ANTIGRAVITY_MASTER_PROMPT.md:75` |
| 9 | R2: Decision Contract | Authentic Derivatives Ingestion | Ingest genuine contract parameters (expiry, lot size, tick size, OI, volume, spread, margin) | Exchange derivative contracts / Upstox option chain | Authentic contract parameters bound to decision | Fails closed with `DATA_UNAVAILABLE` if data missing; no synthetic defaults | `backend/app/signal_engine/signal_pipeline.py:608`, `ORIGINAL_REQUEST.md:20` |
| 10 | R2: Decision Contract | Instrument Master & Scan Coverage Ledger | Complete scan coverage accounting across configured universe | Universe list, market data service | `ScannerResult` containing `ScanCoverageLedger` with coverage counts | Records unavailable/skipped members with explicit reason | `backend/app/signal_engine/scanner.py:92`, `APEX_ANTIGRAVITY_MASTER_PROMPT.md:96` |
| 11 | R2: Decision Contract | Deterministic Feature Cache | Compute and cache technical features once per instrument / bar / timeframe | Completed OHLCV bar series | `MarketFeatures` dictionary keyed by bar timestamp | Returns empty vector on insufficient candles | `backend/app/quant_engine/features.py:28`, `APEX_ANTIGRAVITY_MASTER_PROMPT.md:100` |
| 12 | R2: Decision Contract | Directional Geometry Enforcement | Mathematically enforce LONG (`stop < entry < targets`) and SHORT (`targets < entry < stop`) | Computed stop loss, entry price, target levels | Validated geometric price levels | Hard gate fails with `GEOMETRY_INVALID` if levels are inverted | `backend/app/signal_engine/stop_target_engine.py:20`, `test_financial_invariants.py:8` |
| 13 | R2: Decision Contract | Primary Timeframe Integrity | Ensure signals are evaluated on genuine primary timeframe candles | Timeframe candle dictionary | Evaluated signal on primary timeframe | Fails closed with `TIMEFRAME_UNAVAILABLE` or `DEGRADED`; no silent substitution | `signal_pipeline.py:352`, `APEX_ANTIGRAVITY_RESEARCH.md:32` |
| 14 | R2: Decision Contract | Synchronized Signal Expiry | Align signal expiry timestamp with configured candle duration | Config expiry candles, primary timeframe | ISO 8601 UTC expiry timestamp matching candle duration | Sets expired state if evaluated past expiry | `signal_pipeline.py:585, 717`, `APEX_ANTIGRAVITY_RESEARCH.md:32` |
| 15 | R2: Decision Contract | Authentic Data Provenance & Gap Preservation | Preserve genuine gaps in OHLCV; stamp provenance truthfully | Historical candles, live ticks | Verifiable `DataProvenance` tag (`RAW_AUTHENTIC_DATA` vs `SIMULATED`) | Preserves `None` on missing highs/lows rather than substituting | `broker_providers/upstox_client.py:492`, `test_financial_invariants.py:16` |
| 16 | R3: Paper Execution | Unified Server-Authoritative Ledger | Single server ledger managing paper positions, cash balance, and MTM | Live ticks / candle updates | Updated open positions, unrealized P&L, trigger evaluations | Eliminates discrepancies between UI cache and backend state | `backend/app/paper_trading/engine.py:217`, `paper_engine/bridge.py:201` |
| 17 | R3: Paper Execution | Signal Submission Pre-Validation | Revalidate signal qualification, expiry, price range, and risk gates before order creation | Signal ID, caller auth, market price | Order execution or HTTP 400 error | Rejects expired, triggered, or invalidated signals with explicit error | `backend/app/main.py:2464`, `ORIGINAL_REQUEST.md:26` |
| 18 | R3: Paper Execution | Durable Idempotency Keys | Idempotency key tracking to eliminate duplicate order fills or overdrawing cash | `idempotency_key` string | Cached order result returned for duplicate requests | Rejects concurrent duplicate orders without double debit | `backend/app/paper_trading/engine.py:212`, `ORIGINAL_REQUEST.md:26` |
| 19 | R3: Paper Execution | Side-Correct Automated Exits | Automated stop-loss and take-profit exits with correct mathematical logic for LONG and SHORT | Tick / candle high, low, close | Auto-closed position, realized P&L, audit log | Side-correct trigger: SHORT stops on high >= stop; targets on low <= target | `paper_engine/bridge.py:219`, `ORIGINAL_REQUEST.md:27` |
| 20 | R3: Paper Execution | Conservative Gap & Same-Bar Exit Policy | Conservative execution policy when bar triggers both stop-loss and take-profit | Bar high, low, open, close | Stop-loss triggered first to protect against optimistic bias | Logs warning on ambiguous same-bar trigger | `APEX_ANTIGRAVITY_MASTER_PROMPT.md:114` |
| 21 | R3: Paper Execution | Immutable Audit Journal Linkage | Persist immutable trade audits linking entries/exits to original signal fingerprint | Order fill event, exit audit event | `PaperTradeAudit` record in SQLite/PostgreSQL | Immutable sequence numbering guaranteed | `paper_engine/bridge.py:245`, `live_paper/master_evidence_logger.py` |
| 22 | R3: Paper Execution | Crash Recovery & State Reconstruction | Restore active positions, cash balance, and audit sequence progression on startup | Database tables (`positions`, `audit_events`) | Reconstructed runtime memory state | Freezes on reconciliation ambiguity; maintains monotonic audit sequence | `paper_trading/engine.py:103`, `live_paper/session_runner.py` |
| 23 | R3: Paper Execution | Forensic Session Ownership & Shutdown Rules | Enforce session continuity: mid-session worker stop is NOT session finalization | Process lifecycle signals, exchange clock | Session status (`WORKER_SHUTDOWN` vs `FINALIZED`) | Recovers session on restart without duplicate start event | `backend/app/worker.py:211`, `test_sept15_replay.py:10` |
| 24 | R4: UI & AI | Three-View Primary Navigation | Streamlined daily UI navigation: Today, Positions & Journal, Learn | User navigation selection | Focused single-responsibility workspace views | Preserves responsive layout and keyboard accessibility | `frontend/src/App.tsx:828`, `NavigationTabs.tsx:48` |
| 25 | R4: UI & AI | Preserved Advanced Views Group | Retain all 9 analytical, backtest, and command-center pages under Advanced group | User navigation menu | Full advanced workstations accessible on demand | Defaults collapsed to avoid overwhelming interface | `frontend/src/App.tsx:836`, `NavigationTabs.tsx:19` |
| 26 | R4: UI & AI | Today Operational Dashboard | Single-screen view of data health, scan coverage, qualified signals, and no-trade rationales | Scanner results, feed status, rejection records | High-clarity operational dashboard | Honest empty states when no trade is qualified | `SignalCenterPage.tsx`, `ORIGINAL_REQUEST.md:32` |
| 27 | R4: UI & AI | Positions & Journal Workspace | Real-time canonical portfolio view with P&L net of statutory costs and trade audit history | Paper engine portfolio summary, journal repository | Net P&L display, trade exit logs, cost breakdowns | Shows visible error banners on close failures | `frontend/src/components/pages/PortfolioPage.tsx` |
| 28 | R4: UI & AI | Contextual Educational Learn View | Educational breakdown explaining setup mechanics, indicator roles, and wait conditions | Active signal setup, quantitative evidence | Plain-language conceptual explanations | Explains why system waits without overwhelming indicator tables | `frontend/src/components/pages/LearnPage.tsx` |
| 29 | R4: UI & AI | Async Runtime AI Adapter | Non-blocking async adapter for Gemini model calls in background tasks | Evidence payload, prompt template | Typed JSON commentary or research notes | Never blocks FastAPI event loop; uses `client.aio` | `backend/app/ai_engine/agents.py:11`, `gemini_client.py:22` |
| 30 | R4: UI & AI | Deterministic AI Evidence Citations | Ground all narrative explanations strictly in deterministic quantitative calculation data | Factual feature vector, strategy votes, gates | Grounded narrative strictly citing provided metrics | Banned from inventing tactical price levels or stops | `chief_analyst.py:246`, `ORIGINAL_REQUEST.md:34` |
| 31 | R4: UI & AI | Graceful AI Degradation | Uninterrupted trading operation when AI service times out, rate-limits, or is offline | Timeout / 429 response | Visible "AI Unavailable" notice; signals & exits 100% operational | No synthetic text or fake confidence scores displayed | `gemini_client.py:68`, `ORIGINAL_REQUEST.md:35` |
| 32 | R4: UI & AI | Prompt Boundary Defense | Sanitize and isolate untrusted external market news from LLM instruction context | External news feeds, SEBI filings | Sanitized data context parts | Models denied access to broker orders, shell, or secrets | `chief_analyst.py:250`, `APEX_ANTIGRAVITY_MASTER_PROMPT.md:130` |
| 33 | R5: Security | Real-Money Order Hard Block | Permanent absolute code-level prohibition against real-money broker order placement | Order execution invocation | Execution blocked immediately | Raises `LiveOrderForbiddenSecurityError` | `backend/app/live_paper/safety.py:25`, `ORIGINAL_REQUEST.md:38` |
| 34 | R5: Security | Local Loopback Binding & Strict CORS | Bind backend server to 127.0.0.1; restrict CORS to authorized local origins | Incoming HTTP requests | Allowed or rejected based on Origin header | Rejects unauthorized origins; prevents public network binding | `backend/app/config.py:48`, `backend/app/main.py:48` |
| 35 | R5: Security | Server-Side Secrets & Query Redaction | Pass API keys in HTTPS headers; eliminate keys from URLs, client bundles, and logs | API credentials | Secure `x-goog-api-key` header injection | Sanitizes error messages to prevent credential leakage | `gemini_client.py:37`, `ORIGINAL_REQUEST.md:39` |
| 36 | R5: Security | Fail-Closed Endpoint Authentication | Enforce authentication on all private portfolio, journal, and mutation endpoints | API auth token / Bearer token | Validated `AccountContext` | Returns HTTP 401 Unauthorized for missing/invalid keys | `backend/app/security/auth.py`, `backend/app/main.py:965` |
| 37 | R5: Security | IDOR Cross-Account Isolation | Prevent tenant Account A from viewing or closing positions belonging to Account B | User account context, position account ID | Scoped access verification | Returns HTTP 403 Forbidden on ownership mismatch | `backend/app/security/auth.py:65`, `backend/app/main.py:995` |
| 38 | R5: Security | Portfolio Aggregation Leak Repair | Fix `/api/paper/positions` to require auth or default strictly to caller's account | Query params, auth context | Account-isolated portfolio summary | Rejects unauthenticated attempts to view cross-account data | `backend/app/main.py:975`, `APEX_ANTIGRAVITY_RESEARCH.md:40` |
| 39 | Financial / Tax | Statutory Indian Transaction Cost Calculator | Precise calculation of brokerage, STT, exchange turnover fees, stamp duty, SEBI fees, GST | Trade leg (CNC, MIS, Futures, Options), turnover | Itemized `CostBreakdown` and net realized P&L | Accurately models sell-leg STT for intraday and both legs for delivery | `backend/app/signal_engine/transaction_cost.py:28` |
| 40 | Quant Engine | Twenty-Strategy Conformance Registry | Register and evaluate 20 distinct quantitative strategies across regimes | OHLCV candles, market features | Array of `StrategyVote` items with rule counts and reasons | Marks incompatible strategies as `NOT_APPLICABLE` | `backend/app/strategy_engine/registry.py:54` |
| 41 | Quant Engine | Independent Evidence Confluence | Adjust confluence votes by grouping correlated strategies into evidence families | Array of strategy votes | `StrategyConsensus` with independent vote counts | Warns when consensus is driven by correlated votes | `backend/app/signal_engine/confluence_engine.py` |
| 42 | Quant Engine | Dynamic Market Regime Detector | Classify regime into TRENDING (BULL/BEAR), RANGING, BREAKOUT, or HIGH_VOLATILITY | ADX, ATR, EMA slope, volume | Classified regime string and confidence score | Falls back to `UNKNOWN` on insufficient data | `backend/app/quant_engine/regime.py:20` |
| 43 | Quant Engine | Black-Scholes Greeks Calculator | Compute theoretical pricing and Delta, Gamma, Theta, Vega Greeks for option chains | Strike, spot, DTE, risk-free rate, volatility | Typed `OptionGreeks` struct | Rejects non-finite values; flags deep OTM / near-expiry anomalies | `backend/app/signal_engine/options_engine.py:20` |
| 44 | Quant Engine | Multi-Timeframe Trend & Alignment Engine | Analyze momentum, trend, and alignment across 5m, 15m, 1h, and Daily timeframes | Multi-timeframe candle dictionary | `MultiTimeframeResult` with alignment score | Flags conflicting signals when primary TF disagrees with higher TF | `backend/app/signal_engine/multi_timeframe_engine.py` |
| 45 | Quant Engine | Mathematical Position Sizing Engine | Calculate share quantity based on capital, risk percentage, and stop distance | Available capital, max risk pct, entry, stop | Calculated quantity and required capital | Quantity constrained by lot size for derivatives; fails on 0 risk | `backend/app/signal_engine/position_sizing_engine.py` |
| 46 | Runtime / Worker | Master Evidence Logger & Audit Sequencer | Append-only event journaling with strictly monotonic global sequence numbers | Timestamped system events | JSONL master log and database audit record | Sequence numbers never decrease; duplicate event IDs rejected | `backend/app/live_paper/master_evidence_logger.py:50` |
| 47 | Runtime / Worker | SQLite / PostgreSQL Dual Persistence | Asynchronous persistence with non-pooling SQLite for dev and connection pool for Postgres | SQLAlchemy async engine | Persisted tables (`orders`, `positions`, `audit`) | NullPool on SQLite prevents retained threads in short processes | `backend/app/database/connection.py:47` |
| 48 | Runtime / Worker | Forensic Log Replay Engine | Replay historical session JSONL logs to verify lifecycle invariants and state transitions | Raw master event logs | Deterministic session replay verification | Proves absence of premature closing or duplicate session starts | `backend/tests/live_paper/test_sept15_replay.py` |

---

## 5. Comprehensive Edge Cases

| # | Feature | Input | Observed / Required Behavior |
|---|---------|-------|------------------------------|
| 1 | Canonical Quote Store | Tick received with missing or undefined `timestamp` | Store falls back safely to current epoch seconds (`Math.floor(Date.now() / 1000)`); never assigns `undefined` or throws TS2304 error. |
| 2 | Canonical Quote Store | Tick received with negative or zero LTP | Store rejects tick update immediately, returns `null`, and leaves existing valid quote intact. |
| 3 | FastAPI Lifespan | Process receives SIGINT/SIGTERM during startup | Lifespan `yield` is enclosed in `try ... finally`; `market_data_service.active_provider.disconnect()` runs reliably. |
| 4 | Stateful Market Worker | Worker auto-started in background and cancelled before completion | Worker retains task reference `_worker_task`; shutdown cancels and awaits the task without leaving orphan background loops. |
| 5 | Paper Order Submission | Unauthenticated POST to `/api/paper/order` | Request is rejected immediately with HTTP 401 Unauthorized; no order record or state mutation created. |
| 6 | Position Close | Network disconnection or HTTP 500 error during close request | UI displays error notification toast, leaves position intact in UI state (`paperPositions`), preventing false removal. |
| 7 | Signal Center Trade Button | Backend returns HTTP 200 with `order_result: {"status": "REJECTED"}` | UI inspects `order_result.status`, identifies rejection, displays error notification with reason, and does not show fill toast. |
| 8 | Signal-to-Paper Submission | Signal submitted when `signal.state == "TRIGGERED"` or `"EXPIRED"` | Backend rejects order with HTTP 400 ("Signal must be in QUALIFIED state"); no duplicate order created. |
| 9 | Signal-to-Paper Submission | Signal submitted when `ltp` has drifted outside `entry_zone` | Revalidation checks price bounds against `entry_zone_low` and `entry_zone_high`; rejects order if drifted too far. |
| 10 | Signal-to-Paper Submission | Signal submitted past its `expiry` timestamp | Backend compares submission time with `signal.expiry`; rejects expired signal with HTTP 400. |
| 11 | Paper Order Idempotency | Identical order submitted twice concurrently (double click) | Second request matches existing `idempotency_key` in cache/DB; returns original filled order result without double-charging cash. |
| 12 | Paper Position Sizing | Stop loss identical to entry price (`stop == entry`) | Engine detects zero risk distance; returns `GEOMETRY_INVALID`, prevents division by zero in position sizing. |
| 13 | Directional Geometry | LONG signal proposed with `stop >= entry` or `target <= entry` | Hard validation gate fails immediately; returns `NO_TRADE` with gate failure `GEOMETRY_INVALID`. |
| 14 | Directional Geometry | SHORT signal proposed with `stop <= entry` or `target >= entry` | Hard validation gate fails immediately; returns `NO_TRADE` with gate failure `GEOMETRY_INVALID`. |
| 15 | Target Ordering | Targets computed out of order (e.g. T2 < T1 for LONG) | Target engine enforces progressive ordering: T1 < T2 < T3 for LONG, and T1 > T2 > T3 for SHORT. |
| 16 | Automated Exits (LONG) | Market tick with `low <= stop_loss` | Engine closes LONG position at `stop_loss` (or tick price if gap); realized P&L is negative net of costs. |
| 17 | Automated Exits (SHORT) | Market tick with `high >= stop_loss` | Engine closes SHORT position at `stop_loss` (or tick price if gap); realized P&L is negative net of costs. |
| 18 | Automated Exits (SHORT) | Market tick with `low <= take_profit` | Engine closes SHORT position at `take_profit`; realized P&L is positive: `(entry - exit) * qty - frictions`. |
| 19 | Same-Bar Exit Ambiguity | Single bar replay where `high >= target` AND `low <= stop` | Engine applies conservative policy: triggers STOP LOSS first, preventing inflated backtest returns. |
| 20 | Market Data Fallback | Upstox native candle fetch fails; Yahoo fallback queried | Yahoo response missing high/low; engine preserves `None` rather than substituting `max(open, close)` and zero volume. |
| 21 | Data Provenance | Market data feed running in development simulation mode | Data is tagged `DataProvenance.SIMULATED`; never stamped `RAW_AUTHENTIC_DATA`. |
| 22 | Scan Coverage | F&O option chain API returns empty strikes list | Scanner marks symbol `DATA_UNAVAILABLE` in `ScanCoverageLedger`; records missing strikes reason, does not crash. |
| 23 | Scan Coverage | Underlying equity candidate missing primary 5m candles | Engine records `TIMEFRAME_UNAVAILABLE`; does not substitute 15m/1h without explicit degraded flag. |
| 24 | Derivatives Evaluation | Futures data lacks real lot size or margin requirements | Pipeline fails closed with `FUTURES_DATA_INSUFFICIENT`; bans synthetic defaults (`dte=15`, `lot=250`). |
| 25 | Session Lifecycle | Worker process crashes at 11:30 IST and restarts at 11:35 IST | Session marked `WORKER_SHUTDOWN` without finalizing; restarts as `WORKER_RECOVERY`, preserves global sequence. |
| 26 | Session Lifecycle | Worker process reaches 15:30 IST | System records `EQUITY_MARKET_CLOSE`; moves to post-market, awaiting 15:40 IST F&O session finalization. |
| 27 | Session Lifecycle | Worker process starts at 00:30 IST (midnight) | Worker initializes in `TRADING_DAY_PREMARKET`; session not finalized; awaits 09:15 IST market open. |
| 28 | Database Recovery | Simulated server crash while holding open paper positions | On reboot, `paper_engine.load_from_db()` restores all active positions, cash balance, and monotonic audit sequence. |
| 29 | Runtime AI Adapter | Gemini API times out after 15 seconds | `httpx.AsyncClient` timeout triggers; adapter returns `UNAVAILABLE`; UI shows fallback notice; trading continues. |
| 30 | Runtime AI Adapter | Gemini API responds with HTTP 429 Too Many Requests | Adapter attempts exponential backoff with jitter up to max retries; on exhaustion, degrades gracefully to notice. |
| 31 | Runtime AI Adapter | Gemini API returns malformed JSON or markdown fences | Parser strips ````json` fences; on JSONDecodeError, falls back to structured fallback commentary without raising exception. |
| 32 | Tactical Trade Setup | AI commentary suggests price targets or stops | UI ignores AI-suggested levels for execution; only quantitative signal engine outputs are valid for paper trading. |
| 33 | Prompt Injection Attack | Ingested market headline contains prompt injection instructions | News text is bound strictly to content parameter; model is provided no tools for orders, shell, or file writing. |
| 34 | Tenant Isolation (IDOR) | Account A attempts to close a position owned by Account B | Endpoint verifies `pos.account_id == auth.account_id`; rejects request with HTTP 403 Forbidden. |
| 35 | Unauthenticated Read | Unauthenticated GET to `/api/paper/positions` | Endpoint rejects unauthenticated cross-account queries with 401; isolates default account data safely. |
| 36 | Real Money Order Attempt | Execution engine called with `LIVE_ORDER_ALLOWED = True` | `LivePaperSafetyGuard` asserts invariant, raises `LiveOrderForbiddenSecurityError`, and aborts execution immediately. |

---

## 6. Cross-Cutting Invariants and Mathematical Rules

### 6.1 Mathematical & Geometrical Rules
1. **Long Price Geometry**:  
   $$0 < \text{stop\_loss} < \text{entry\_price} < \text{target\_1} < \text{target\_2} < \text{target\_3}$$
2. **Short Price Geometry**:  
   $$0 < \text{target\_3} < \text{target\_2} < \text{target\_1} < \text{entry\_price} < \text{stop\_loss}$$
3. **Risk Distance**:  
   $$\text{risk\_distance} = |\text{entry\_price} - \text{stop\_loss}| > 0$$
4. **Risk-to-Reward Ratio**:  
   $$\text{RR}_1 = \frac{|\text{target\_1} - \text{entry\_price}|}{\text{risk\_distance}} \ge \text{min\_risk\_reward} \quad (\text{default: } 1.5)$$
5. **Position Sizing Conservation**:  
   $$\text{quantity} \times \text{risk\_distance} \le \text{capital} \times \text{risk\_per\_trade\_pct} \quad (\text{default: } 1.0\%)$$
6. **Derivative Lot Constraint**:  
   $$\text{quantity} = \max\left(1, \left\lfloor \frac{\text{raw\_quantity}}{\text{lot\_size}} \right\rfloor\right) \times \text{lot\_size}$$

### 6.2 Statutory Transaction Costs (NSE India 2026 Model)
* **Equity Delivery (CNC)**:
  - Brokerage: $\min(20, 0.05\% \times \text{turnover})$ per order.
  - STT: $0.1\%$ on Buy Turnover + $0.1\%$ on Sell Turnover.
  - Stamp Duty: $0.015\%$ on Buy Turnover only.
  - Exchange Turnover Fee: $0.00297\% \times \text{turnover}$.
  - SEBI Turnover Fee: ₹10 per crore ($0.0001\% \times \text{turnover}$).
  - GST: $18\% \times (\text{brokerage} + \text{exchange\_fee} + \text{sebi\_fee})$.
* **Equity Intraday (MIS)**:
  - Brokerage: $\min(20, 0.05\% \times \text{turnover})$ per order.
  - STT: $0.025\%$ on Sell Turnover only.
  - Stamp Duty: $0.003\%$ on Buy Turnover only.
  - Exchange Turnover Fee: $0.00297\% \times \text{turnover}$.
  - GST: $18\% \times (\text{brokerage} + \text{exchange\_fee} + \text{sebi\_fee})$.
* **Futures**:
  - Brokerage: Flat ₹20 per order.
  - STT: $0.02\%$ on Sell Turnover only.
  - Stamp Duty: $0.002\%$ on Buy Turnover only.
* **Accounting Conservation Invariant**:
  $$\text{Net Realized P\&L} = \text{Gross P\&L} - \text{Total Frictions} - \text{Slippage}$$

---

## 7. Architectural State Machines and Lifecycles

### 7.1 Signal Lifecycle State Machine
```
[ CANDIDATE ]
      │
      ▼ (Screening & Eligibility)
[ ANALYZING ]
      │
      ▼ (Multi-TF, Features, Strategies, Risk Gates)
[ VALIDATING ]
      ├── (Hard Gate Fail / Score Low) ──► [ REJECTED / NO_TRADE ]
      │
      ▼ (All Gates Pass & Score Qualified)
[ QUALIFIED ] ──► (TTL / Expiry elapsed) ──► [ EXPIRED ]
      │                                       ▲
      ▼ (Pre-Submission Check & Paper Fill)   │
[ TRIGGERED ]                                 │
      │                                       │
      ▼ (Order Filled in Server Ledger)       │
[ ACTIVE ] ───────────────────────────────────┤
      ├── (Price hits Stop) ────────► [ STOPPED ]
      ├── (Price hits T1) ──────────► [ TARGET_1 ]
      ├── (Price hits T2) ──────────► [ TARGET_2 ]
      ├── (Price hits T3) ──────────► [ TARGET_REACHED ]
      └── (Structure Breaks) ───────► [ INVALIDATED ]
```

### 7.2 Session & Worker Recovery State Machine
```
[ 00:00 - 09:14 IST ] ──► WORKER_ONLINE in TRADING_DAY_PREMARKET
                                │
[ 09:15 IST ] ──────────► MARKET_OPEN (Active Session)
                                │
[ Unexpected Worker Stop ] ──► WORKER_SHUTDOWN (Session NOT finalized)
                                │
[ Worker Restart Same Day ] ──► WORKER_RECOVERY (Resumes sequence monotonically)
                                │
[ 15:30 IST ] ──────────► EQUITY_MARKET_CLOSE
                                │
[ 15:40 IST ] ──────────► FNO_FINALIZATION ──► SESSION_FINALIZED
```

---

## 8. Milestone Dependencies & Engineering Wave Alignment

| Milestone | Scope & Deliverables | Blocking Pre-requisites | Success Gate Criteria |
|-----------|----------------------|-------------------------|-----------------------|
| **M0** | Baseline contracts, test harness, specification freeze | None | Reproduce baseline diagnostics; freeze schemas |
| **M1** | R1 Repairs: Quote store TS fix, lifespans, auth, credentials | M0 | `npm run lint` & `build` clean; lifespans guarded |
| **M2** | R2 Equity Pipeline: Scanner coverage, long/short geometry, replay | M1 | Scanner coverage ledger; replay signal-to-order passes |
| **M3** | R2/R3 Derivatives & Exits: Genuine F&O contracts, side-correct exits | M2 | Derivatives fail closed without synthetic data; short exits correct |
| **M4** | R3 Durable Runtime: Crash recovery, session boundaries, audit sequence | M3 | Simulated reboot recovers positions & cash balance |
| **M5** | R4 UI & AI: Today/Positions/Learn, Advanced group, async AI adapter | M4 | 3-view navigation functional; AI offline mode verified |
| **M6** | Final Validation: End-to-end regression pass, runbook delivery | M5 | All test suites green; security & safety invariants intact |

---

## 9. Acceptance Criteria Verification Matrix

| Area | Criterion | Target Output / Assertion | Verification Command / Method |
|------|-----------|---------------------------|-------------------------------|
| **Baseline** | TypeScript compiles cleanly with zero diagnostics | Zero TS errors in `canonicalQuoteStore.ts` | `npm.cmd run lint` (`tsc --noEmit`) |
| **Baseline** | Production bundle builds successfully | Vite build completes cleanly | `npm.cmd run build` |
| **Baseline** | Safety & paper accounting test suites pass | 16+ tests pass with zero regressions | `pytest backend/tests/acceptance/` |
| **Signal Engine** | Replay evaluation produces valid geometry | `stop < entry < targets` (LONG), `targets < entry < stop` (SHORT) | `pytest backend/tests/signal_engine/test_financial_invariants.py` |
| **Signal Engine** | Incomplete derivatives inputs fail closed | Explicit `UNAVAILABLE` or `OPTIONS_DATA_INSUFFICIENT` | `pytest backend/tests/signal_engine/test_fno_and_costs.py` |
| **Signal Engine** | Universe scan reports full coverage metrics | Ledger contains requested, eligible, evaluated, rejected counts | `OpportunityScanner.run_scan()` inspection |
| **Paper Execution** | Submitting expired/invalidated signal is rejected | HTTP 400 with explicit rejection detail | `/api/signals/{id}/paper-trade` negative test |
| **Paper Execution** | Concurrent duplicate submissions do not duplicate fills | Single filled order; identical cached response returned | `test_unified_paper_order.py` idempotency check |
| **Paper Execution** | Automated stop/target exits execute side-correctly | SHORT exits trigger on price rise for stop, price drop for target | `test_paper_bridge.py` & MTM unit tests |
| **Paper Execution** | Crash recovery preserves state across restart | Restored positions match open positions prior to restart | Reboot simulation test in `test_session_lifecycle_hardening.py` |
| **UI & Security** | Failed paper-close leaves position intact in UI | Position remains in `paperPositions` state on error | UI unit/component test for `handleClosePaperPosition` |
| **UI & Security** | All mutations require valid authentication | Requests without valid token return HTTP 401 | `test_unauthenticated_mutation_fails_closed` |
| **UI & Security** | Offline AI does not degrade trading or exits | Signals and automated paper exits remain 100% operational | Gemini client mock timeout test |
| **Safety Guardrail** | Live broker orders remain strictly prohibited | `LIVE_ORDER_ALLOWED == False` asserted at runtime | `LivePaperSafetyGuard.assert_paper_mode_enforced()` |
