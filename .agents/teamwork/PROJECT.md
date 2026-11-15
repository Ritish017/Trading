# Project: APEX Quantitative Trading Workstation

## Architecture
- **Backend**: FastAPI (`backend/app/main.py`), Background Worker (`backend/app/worker.py`), SQLAlchemy Async Engine (`backend/app/database/connection.py`).
  - **Data Ingestion & Master**: `backend/app/broker_providers/` (Upstox client, mock fallbacks), `backend/app/signal_engine/scanner.py`, `backend/app/signal_engine/market_data_service.py`.
  - **Decision Engine**: `backend/app/signal_engine/signal_pipeline.py`, `validation_gates.py`, `regime_detector.py`.
  - **Paper Execution & Ledger**: `backend/app/paper_trading/engine.py` (authoritative server engine, MTM, automated exits, crash recovery, persistent idempotency cache, journal repository).
  - **AI Explanations**: `backend/app/ai_engine/gemini_client.py` (async non-blocking, header-based auth), `backend/app/ai_engine/explanation_service.py` (grounded citations).
  - **Security & Auth**: `backend/app/api/auth.py` (`verify_api_key`, `verify_api_key_optional`, loopback enforcement).
- **Frontend**: React + TypeScript + Vite + Tailwind (`frontend/src/`).
  - **Stores**: `canonicalQuoteStore.ts` (real-time tick ingestion, monotonicity guard, timestamp validation).
  - **Navigation**: `NavigationTabs.tsx` (Primary: **Today**, **Positions & Journal**, **Learn**; Preserved Container: **Advanced** housing Terminal, Intelligence, Derivatives, Institutional, Portfolio, Backtest, StrategyLab, Fundamentals, ResearchFactory).
  - **UI Views**: `TodayView.tsx` (Data health, scan coverage, actionable signals, no-trade reasons), `PositionsJournalView.tsx` (Live positions, P&L net of costs, immutable exit journal, close confirmation), `LearnView.tsx` (Educational breakdowns, setup mechanics).
  - **App State**: `App.tsx` (Authenticated paper mutation calls, local position retention on failed close, order state verification).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Quote Store Timestamp Fix | Fix TS2304 `incomingTs` undeclared in `canonicalQuoteStore.ts` with monotonicity protection | M1 | Survey R1 |
| 2 | FastAPI Lifespan Guard | Wrap `app_lifespan` yield in `try ... finally` to guarantee provider disconnection on exception/cancel | M1 | Survey R1 |
| 3 | Worker Lifespan Guard | Wrap `worker_lifespan` in `try ... finally`, retain background startup task, await runner cancellation | M1 | Survey R1 |
| 4 | Paper Order Auth Headers | Send auth headers on `/api/paper/order` and `/api/paper/close/{id}` in `App.tsx` | M1 | Survey R1 |
| 5 | Position Retention on Close Failure | Keep position in local state and alert user when paper close request fails | M1 | Survey R1 |
| 6 | Dev Credential Removal | Remove hardcoded `apex_default_dev_key` from frontend source code | M1 | Survey R1 |
| 7 | Order State Validation | Require `order_result.status === 'FILLED'` instead of HTTP 200 before showing fill confirmation | M1 | Survey R1 |
| 8 | Remove External Probe | Eliminate external Render network call in `IndexTickerBar.tsx` for local-loopback compliance | M1 | Survey R1 / R5 |
| 9 | Worker Loopback Binding | Bind worker and backend host to `127.0.0.1` by default rather than `0.0.0.0` | M1 | Survey R1 / R5 |
| 10 | Derivatives Contract Fail-Closed | Reject incomplete F&O parameters with `DATA_UNAVAILABLE` instead of synthetic defaults | M2 | Survey R2 |
| 11 | Timeframe Degradation Flag | Flag non-primary timeframe fallbacks as `DEGRADED` rather than silent substitution | M2 | Survey R2 |
| 12 | Signal Expiry Alignment | Calculate signal expiry duration dynamically based on primary timeframe duration | M2 | Survey R2 |
| 13 | Directional Geometry Validation | Enforce LONG (`stop < entry < targets`) and SHORT (`targets < entry < stop`) strictly | M2 | Survey R2 |
| 14 | Scan Coverage Ledger | Record requested, eligible, evaluated, unavailable, skipped, rejected counts with timestamps | M2 | Survey R2 |
| 15 | Paper Engine Unification | Consolidate `PaperTradingEngine` and `PaperTradingBridge` into single authoritative server engine | M3 | Survey R3 |
| 16 | Order Pre-Submission Validation | Revalidate `QUALIFIED` status, expiry timestamp, price bounds, and portfolio risk limits at submission | M3 | Survey R3 |
| 17 | Durable Idempotency Keys | Persist paper order idempotency keys in database to prevent double execution across restarts | M3 | Survey R3 |
| 18 | Side-Correct Automated Exits | Automate TP/SL for LONG (stop on low <= stop) and SHORT (stop on high >= stop; target on low <= target) | M3 | Survey R3 |
| 19 | Same-Bar Conservative Policy | Assume stop loss executed first if both stop and target crossed within same bar | M3 | Survey R3 |
| 20 | Immutable Paper Journal | Persist executed entry and exit trades linked to original signal fingerprint and calculation evidence | M3 | Survey R3 |
| 21 | Crash Recovery | Restore active orders, open positions, cash balance, and monotonic audit sequence on server restart | M3 | Survey R3 |
| 22 | Primary Navigation Restructure | Restructure UI navigation into **Today**, **Positions & Journal**, and **Learn** | M4 | Survey R4 |
| 23 | Advanced Group Preservation | House existing 9 analytical/backtest pages under an **Advanced** container menu | M4 | Survey R4 |
| 24 | Async AI Explanation Engine | Migrate AI engine to non-blocking `client.aio` avoiding FastAPI event loop blocks | M4 | Survey R4 |
| 25 | Evidence-Grounded Citations | Ground signal and no-trade explanations strictly in deterministic quantitative calculation metrics | M4 | Survey R4 |
| 26 | Graceful AI Offline Degradation | Fall back to visible status badges and local deterministic templates on AI timeout/failure | M4 | Survey R4 |
| 27 | Permanent Live Order Ban | Assert `LIVE_ORDER_ALLOWED = False` and block live broker order routing permanently | M5 | Survey R5 |
| 28 | Header Secret Storage | Send API keys via `x-goog-api-key` header instead of URL query string parameter | M5 | Survey R5 |
| 29 | Authenticated Portfolio Query | Require authentication on `/api/paper/positions` to prevent global aggregate leakage | M5 | Survey R5 |
| 30 | Isolated Test Fixtures | Ensure test fixtures use isolated database and storage paths without touching personal sessions | M5 | Survey R5 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Survey & Scope Mapping | Specification mining, backend and frontend code investigation | none | DONE |
| M1 | Baseline Integrity Repairs | R1: `canonicalQuoteStore.ts`, lifespans, auth headers, close state retention, dev credentials, loopback | M0 | DONE |
| M2 | Decision Contract & Ingestion | R2: F&O fail-closed, timeframe degradation, directional geometry, scan coverage ledger | M1 | DONE |
| M3 | Paper Execution & Exit Lifecycle | R3: Single engine, pre-validation, durable idempotency, side-correct exits, immutable journal, recovery | M2 | PLANNED |
| M4 | Grounded AI & Educational UI | R4: 3 primary views (**Today**, **Positions & Journal**, **Learn**), **Advanced** container, async AI, grounded citations | M3 | PLANNED |
| M5 | Security & Guardrails | R5: Live order ban assertion, secret headers, portfolio auth, isolated fixtures | M1, M3 | PLANNED |
| M-E2E | E2E Testing Suite | Dual Track: Opaque-box test harness and Tiers 1-4 test suite generation | M0 | DONE |
| M-Final | Final Verification & Hardening | Phase 1: 100% E2E test pass (Tiers 1-4); Phase 2: Tier 5 Adversarial Hardening; Phase 3: Forensic Audit | M1, M2, M3, M4, M5, M-E2E | PLANNED |

## Interface Contracts
### `frontend/src/stores/canonicalQuoteStore.ts`
- Method: `updateFromWS(tick: any): void`
- Invariant: `incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0)`
- Invariant: Drop tick if `incomingTs < currentQuote.last_trade_time` to enforce monotonicity.

### `backend/app/main.py` & `worker.py` Lifespans
- Signature: `@asynccontextmanager async def app_lifespan(app: FastAPI)`
- Contract: Teardown logic MUST execute in `finally:` block; background tasks MUST be tracked and cleanly awaited on cancellation.

### `backend/app/signal_engine/validation_gates.py` & `signal_pipeline.py`
- Contract:
  - If `direction == "LONG"`: require `stop_loss < entry_price < target_1 < target_2`
  - If `direction == "SHORT"`: require `target_2 < target_1 < entry_price < stop_loss`
  - Incomplete F&O fields: `raise MissingDataError("DATA_UNAVAILABLE: Incomplete contract parameters")`

### `backend/app/paper_trading/engine.py` (Authoritative Server Ledger)
- Method: `submit_order(req: PaperOrderRequest, auth: AccountContext, idempotency_key: str) -> PaperOrderResult`
- Method: `process_market_tick(symbol: str, ltp: float, high: float, low: float) -> List[PaperExitEvent]`
- Exit Logic:
  - LONG: if `low <= pos.stop_loss` -> EXIT_STOP; elif `high >= pos.take_profit` -> EXIT_TARGET
  - SHORT: if `high >= pos.stop_loss` -> EXIT_STOP; elif `low <= pos.take_profit` -> EXIT_TARGET
  - Same-bar conflict (`low <= stop` AND `high >= target`): Stop takes precedence.

## Code Layout
- `backend/app/main.py`: FastAPI app, router mounting, lifespan management.
- `backend/app/worker.py`: Background scanning and tick processing daemon.
- `backend/app/signal_engine/`: Scanner, pipeline, validation gates, coverage ledger.
- `backend/app/paper_trading/`: Authoritative server ledger, position manager, exit evaluator, journal repository.
- `backend/app/ai_engine/`: Async Gemini client, explanation service, prompt templates.
- `backend/app/database/models.py`: Database models (positions, orders, idempotency_keys, journal_entries).
- `frontend/src/stores/canonicalQuoteStore.ts`: Client tick store.
- `frontend/src/components/NavigationTabs.tsx`: Navigation header.
- `frontend/src/components/pages/`: Page components (**Today**, **Positions & Journal**, **Learn**, **Advanced** group).
- `frontend/src/App.tsx`: Root client application and mutation coordinators.
- `backend/tests/`: Pytest regression, invariant, security, and acceptance test suites.
