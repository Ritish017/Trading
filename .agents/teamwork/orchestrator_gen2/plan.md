# Project Orchestrator Plan — Generation 2

## Objective
Deliver a production-ready, fully verified APEX trading and quantitative analysis workstation in `C:\Tradinf2` adhering strictly to R1 through R5 in `ORIGINAL_REQUEST.md` and the 30-feature inventory in `PROJECT.md`, passing 100% of the 4-tier E2E tests in `TEST_INFRA.md` with zero integrity violations.

---

## Milestone Breakdown & Execution Flow

### Milestone 1 (M1 - R1): Finalize Baseline Defects & Compilation
- **Items**:
  1. Fix `test_lifespans_hardening.py` mock disconnect expectation so that `market_data_service.disconnect()` properly awaits the provider or fixture correctly sets up the mock provider post-initialization.
  2. In `backend/app/main.py`: replace the 6 fallback URLs pointing to `https://apex-market-worker-probe.onrender.com` with local loopback / state checks, and ensure signal expiry parsing is timezone-aware UTC and fails closed (HTTP 400).
  3. In `backend/tests/e2e/test_tier1_features.py`: fix the import of `OptionsDecisionEngine` (import `OptionsEngine` or define compatibility alias).
- **Verification**: Worker runs `pytest backend/tests/test_lifespans_hardening.py`, `pytest backend/tests/test_security_hardening.py`, and `pytest backend/tests/e2e --collect-only`. Reviewer and Challenger confirmation.

### Milestone 2 (M2 - R2): Server-Authoritative Decision Contract & Market Ingestion
- **Scope**: Features 10, 11, 12, 13, 14.
- **Key Modules**: `backend/app/signal_engine/options_engine.py`, `backend/app/signal_engine/validation_gates.py`, `backend/app/signal_engine/scanner.py`, `backend/app/signal_engine/market_data_service.py`.
- **Requirements**:
  - Derivatives Contract Fail-Closed: Missing or zero Greek/IV/open interest/expiry contracts fail closed with `DATA_UNAVAILABLE` rather than synthetic fallbacks.
  - Directional Geometry: Strictly enforce LONG (`stop < entry < targets`) and SHORT (`targets < entry < stop`).
  - Scan Coverage Ledger: Record every scan cycle with requested, eligible, evaluated, unavailable, skipped, rejected counts.
  - Timeframe Degradation: Flag fallback timeframes explicitly as `DEGRADED`.
  - Signal Expiry Alignment: Dynamic calculation based on primary timeframe duration.
- **Iteration**: Explorers -> Worker -> Reviewers (2) + Challengers (2) + Forensic Auditor (1) -> Gate.

### Milestone 3 (M3 - R3): Paper Execution, Ledger & Automated Exits
- **Scope**: Features 15, 16, 17, 18, 19, 20, 21.
- **Key Modules**: `backend/app/paper_trading/engine.py`, `backend/app/database/models.py`.
- **Requirements**:
  - Single authoritative server paper engine (unify bridge and engine).
  - Pre-submission order validation (re-verify QUALIFIED status, unexpired timestamp, price bounds, portfolio risk limits).
  - Durable database idempotency keys to prevent duplicate execution across restarts.
  - Side-correct automated exits (LONG: stop if low <= stop, TP if high >= TP; SHORT: stop if high >= stop, TP if low <= TP; same-bar conservative stop-first priority).
  - Immutable paper journal linked to signal fingerprint and evidence.
  - Crash recovery restoring active orders, positions, and balance on server restart.
- **Iteration**: Explorers -> Worker -> Reviewers + Challengers + Forensic Auditor -> Gate.

### Milestone 4 (M4 - R4): UI Navigation Redesign & Grounded AI Explanations
- **Scope**: Features 22, 23, 24, 25, 26.
- **Key Modules**: `frontend/src/components/NavigationTabs.tsx`, `frontend/src/components/pages/`, `backend/app/ai_engine/`.
- **Requirements**:
  - UI Navigation: 3 primary views (**Today**, **Positions & Journal**, **Learn**) + **Advanced** container preserving the 9 existing analytical/backtesting screens.
  - Async non-blocking Gemini client (`client.aio`) without blocking FastAPI event loop.
  - Grounded quantitative explanations with verifiable metrics citations.
  - Graceful degradation with UI status indicators when AI engine is offline.
- **Iteration**: Explorers -> Worker -> Reviewers + Challengers + Forensic Auditor -> Gate.

### Milestone 5 (M5 - R5): Security Guardrails & Verification
- **Scope**: Features 27, 28, 29, 30.
- **Key Modules**: `backend/app/broker_providers/`, `backend/app/api/auth.py`, test fixtures.
- **Requirements**:
  - Assert `LIVE_ORDER_ALLOWED = False` permanently, blocking live broker order routing.
  - Header-based API key transport (`x-goog-api-key`).
  - Strict portfolio authentication on `/api/paper/positions`.
  - Isolated test fixtures preventing interference with personal sessions.
- **Iteration**: Explorers -> Worker -> Reviewers + Challengers + Forensic Auditor -> Gate.

### Milestone Final: 4-Tier E2E Test Suite Run & Hardening
- **Scope**:
  - Execute full E2E test suite in `backend/tests/e2e/`:
    - Tier 1: Feature Coverage (≥5 per feature)
    - Tier 2: Boundary & Corner Cases (≥5 per feature)
    - Tier 3: Cross-Feature Combinations
    - Tier 4: Real-World Application Scenarios
  - Phase 2: Tier 5 Adversarial Coverage Hardening with Challenger.
  - Forensic Audit: Verification of 100% authentic implementation without mocks or hardcoded bypasses.
- **Completion**: Signal Sentinel parent agent when all criteria are satisfied.
