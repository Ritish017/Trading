# Specification Mining Handoff Report

**Agent**: `teamwork_preview_spec_miner` (Specification Investigator)  
**Task**: Deep Specification Investigation across Authoritative Project Documentation and User Requirements  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\explorer_survey_spec\`  
**Target Path**: `C:\Tradinf2\.agents\teamwork\explorer_survey_spec\handoff.md`  
**Date**: 2026-10-06  

---

## 1. Observation

Direct line-level and document-level observations gathered across the authoritative sources:

1. **`ORIGINAL_REQUEST.md` (lines 12–40)**:
   Explicitly defines requirements R1 through R5 and specifies the development integrity mode as `development` in `C:\Tradinf2`. It lists 12 discrete acceptance criteria across baseline quality, decision pipeline, paper execution, and UI/security guardrails.

2. **`APEX_ANTIGRAVITY_MASTER_PROMPT.md` (lines 60–70, 75–122, 136–145)**:
   Specifies the execution model, 8 scoped parallel roles, milestone wave sequencing (M0 to M6), quantitative decision contract invariants (`stop < entry < targets` for LONG, `targets < entry < stop` for SHORT), full scan coverage accounting, one authoritative server paper ledger, side-correct exit execution, 3-view default navigation (**Today**, **Positions & Journal**, **Learn**) with an **Advanced** group, and strict local loopback operation with permanent live-broker order bans (`LIVE_ORDER_ALLOWED = False`).

3. **`APEX_ANTIGRAVITY_RESEARCH.md` (lines 28–49)**:
   Documents verified gaps and diagnostic results:
   - `frontend/src/stores/canonicalQuoteStore.ts:152, 163`: Three TS2304 compilation errors (`Cannot find name 'incomingTs'`) failing `npm run lint`.
   - `frontend/src/App.tsx:669, 701`: Paper order and close fetch requests lack authentication headers.
   - `frontend/src/App.tsx:713`: Failed close requests remove positions locally because the state filter runs outside the response check.
   - `frontend/src/components/pages/SignalCenterPage.tsx:846`: Hardcoded dev key `'X-API-Key': 'apex_default_dev_key'`.
   - `frontend/src/components/pages/SignalCenterPage.tsx:850`: Treats HTTP 200 as order fill without checking `data.order_result.status === 'FILLED'`.
   - `backend/app/signal_engine/signal_pipeline.py:352`: Primary timeframe silently substituted without degradation.
   - `backend/app/signal_engine/signal_pipeline.py:585, 717`: Signal expiry hardcoded to `3 * 900` while description claims duration based on configured primary timeframe.
   - `backend/app/signal_engine/signal_pipeline.py:608–614`: Synthetic default values for derivatives (`dte=15`, `volume=50000`, `oi=500000`, `lot_size=250`, `margin_per_lot=150000.0`).
   - `backend/app/paper_trading/engine.py:217` vs `paper_engine/bridge.py:219`: MTM updates only unrealized P&L without triggering automated exits; separate bridge contains LONG-biased exit math (`gross_unrealized = (pos.current_price - pos.entry_price) * pos.quantity` and `current_candle_low <= pos.stop_loss`).
   - `backend/app/ai_engine/agents.py:11` & `chief_analyst.py:270`: Asynchronous methods call synchronous, blocking SDK methods inside the FastAPI event loop.
   - `backend/app/ai_engine/gemini_client.py:37, 81`: REST calls pass API key in query string `?key={api_key}` rather than `x-goog-api-key` header.
   - `backend/app/main.py:126` & `worker.py:232`: FastAPI and worker lifespans have bare `yield` lacking `try ... finally` protection, and worker background startup task is unhandled.
   - `backend/app/main.py:975`: Unauthenticated GET to `/api/paper/positions` without `account_id` returns aggregate positions across accounts.
   - `backend/app/main.py:2464`: `/api/signals/{id}/paper-trade` fails to revalidate that signal is in `QUALIFIED` state or verify expiry timestamp.

4. **Codebase Inspection in `backend/` and `frontend/`**:
   - `frontend/src/components/NavigationTabs.tsx`: Contains 12 flat tabs (`terminal`, `intelligence`, `derivatives`, `institutional`, `portfolio`, `backtest`, `learn`, `strategylab`, `fundamentals`, `researchfactory`, `commandcenter`, `signalcenter`).
   - `backend/tests/`: Contains 68 test files covering invariants, acceptance, security hardening, F&O costs, session lifecycle, and log forensics (`test_sept15_replay.py`).

---

## 2. Logic Chain

1. **Defect Scope & Repair Hierarchy (R1)**:
   - Observations 3.a–3.d show that the first-wave defects prevent clean baseline compilation (`tsc --noEmit`), cause memory or task leaks during unexpected process shutdown, break paper accounting in the frontend by deleting positions upon failed closes, and leak dev credentials.
   - Therefore, resolving `incomingTs`, adding `try ... finally` to lifespans, retaining `_worker_task`, adding authentication headers, and verifying `order_result.status === 'FILLED'` form the mandatory foundation (M1) before higher-level pipeline changes can be validated.

2. **Decision Contract & Ingestion Authenticity (R2)**:
   - Observation 3.e shows synthetic fallback data in futures evaluation and silent timeframe replacement in signal generation, violating the user requirement for authentic quantitative calculations.
   - Invariants in Observation 2 require geometric consistency (`stop < entry < targets` for LONG; `targets < entry < stop` for SHORT) and complete universe accounting (`ScanCoverageLedger`).
   - Therefore, derivatives without authentic contract parameters must fail closed (`DATA_UNAVAILABLE`), timeframe discrepancies must be flagged as `DEGRADED`, and the scanner must log an explicit coverage ledger across all universe members.

3. **Authoritative Paper Lifecycle & Crash Recovery (R3)**:
   - Observation 3.f shows two uncoordinated paper engines: one that tracks MTM without exits, and another with LONG-biased exit logic that miscalculates SHORT trade P&L and triggers exits incorrectly on price moves.
   - Observation 3.h shows that signal order placement does not verify whether signals are in `QUALIFIED` status or expired.
   - Therefore, unifying into a single authoritative server ledger with side-correct automated exit execution (SHORT stops trigger on price rise; SHORT targets trigger on price fall) and pre-submission revalidation is necessary to ensure truthful accounting and crash recovery.

4. **Educational UI & Async AI Grounding (R4)**:
   - Observation 4 shows 12 flat tabs in `NavigationTabs.tsx`, conflicting with the user's requirement for a streamlined daily workflow.
   - Observation 3.g shows that current AI adapters call synchronous SDK functions that block the FastAPI event loop, and UI logic in `App.tsx:637` derives tactical setups from text commentary rather than quantitative models.
   - Therefore, reorganizing navigation into **Today**, **Positions & Journal**, and **Learn** (while preserving the 9 advanced pages under an **Advanced** group), migrating AI calls to non-blocking async (`client.aio`), and strictly grounding narrative in quantitative calculation evidence satisfies R4 without risking event loop stalls.

5. **Security, Local Loopback & Safety Guardrails (R5)**:
   - Observation 3.g shows API keys passed in query strings, and Observation 3.h shows unauthenticated global portfolio queries leaking aggregate positions.
   - Invariants in Observation 2 mandate local loopback binding and permanent prohibition of real-money orders.
   - Therefore, moving API keys to headers, enforcing authentication on portfolio reads, and asserting `LIVE_ORDER_ALLOWED = False` secures personal local operation.

---

## 3. Caveats

1. **Live Broker Connectivity**: No real Upstox broker credentials were used or tested during this survey. Market data feeds were evaluated from codebase structures and recorded fixtures.
2. **PostgreSQL vs SQLite Runtime**: Local development and existing tests use SQLite (`sqlite+aiosqlite:///`). While PostgreSQL connection strings and pool options exist in `connection.py`, production PostgreSQL behavior was not directly executed in this turn.
3. **External Upstox API Limits**: Historical candle rate limits (Upstox REST quotas) are subject to official broker terms and must be respected during live universe scanning.

---

## 4. Conclusion

The specification mining investigation is complete. The system requirements and architectural constraints have been exhaustively cataloged across R1 through R5:
- All 48 discrete functional and structural features have been inventoried with input/output contracts, error behaviors, and discovery references.
- All 36 edge cases spanning quote handling, lifespans, geometric rules, side-correct exits, race conditions, and security attacks have been documented.
- The milestone sequence (M0 through M6) and acceptance criteria verification matrix provide a concrete, reproducible blueprint for the implementation team.
- The full specification report has been written to `C:\Tradinf2\.agents\teamwork\explorer_survey_spec\report.md`.

---

## 5. Verification Method

To independently verify the findings in this report:

1. **Verify TypeScript Defect (R1)**:
   ```powershell
   npm.cmd run lint
   ```
   *Expected diagnostic*: TS2304 `Cannot find name 'incomingTs'` at `frontend/src/stores/canonicalQuoteStore.ts:152, 163`.

2. **Verify Lifespan Vulnerability (R1)**:
   Inspect `backend/app/main.py` lines 114–134 and `backend/app/worker.py` lines 220–235 using `view_file` to confirm bare `yield` and absence of `try ... finally`.

3. **Verify Existing Invariant and Security Test Suites (R2, R3, R5)**:
   ```powershell
   pytest backend/tests/acceptance/test_security_acceptance.py
   pytest backend/tests/acceptance/test_paper_acceptance.py
   pytest backend/tests/signal_engine/test_financial_invariants.py
   pytest backend/tests/live_paper/test_sept15_replay.py
   ```
   *Expected output*: Tests run and pass against current isolated SQLite fixtures.

4. **Verify Paper Exit Directional Bias (R3)**:
   Inspect `backend/app/paper_engine/bridge.py` lines 219–235 using `view_file` to confirm `gross_unrealized` formula and `low <= stop_loss` trigger condition lack SHORT direction branching.

5. **Verify AI Query URL Key Leakage (R4, R5)**:
   Inspect `backend/app/ai_engine/gemini_client.py` lines 37 and 81 using `view_file` to confirm query string `?key={self.api_key}`.
