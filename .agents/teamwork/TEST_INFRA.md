# APEX Workstation — End-to-End (E2E) Test Infrastructure & Architecture Specification

**Version:** 2026.1.0-CERTIFIED  
**Author:** E2E Test Architect (`test_writer_e2e`)  
**Target Root:** `C:\Tradinf2`  
**Test Suite Directory:** `backend/tests/e2e/`  

---

## 1. Test Philosophy & Design Principles

The APEX Workstation E2E testing framework is engineered around five non-negotiable principles:

1. **Authoritative & Requirement-Driven:** Every test case is derived directly from the system specifications in `PROJECT.md` (Features 1–30) and `ORIGINAL_REQUEST.md` (Requirements R1–R5). No facade tests or superficial passes.
2. **Opaque-Box Verification:** Tests interact with the workstation through its public interfaces, REST API contracts (`TestClient`), service entry points, and domain engine models without depending on internal private implementation minutiae.
3. **Deterministic & Offline-First:** The test suite operates 100% offline without live Upstox broker credentials, external network calls, or paid LLM API usage. All database operations execute in isolated, clean SQLite test environments.
4. **Failsafe Real-Money Guardrails:** All tests strictly enforce `LIVE_ORDER_ALLOWED = False` and verify that no real broker orders can ever be dispatched.
5. **Progressive 4-Tier Hierarchy:** Tests are categorized into 4 tiers with increasing breadth and complexity:
   - **Tier 1:** Feature Coverage (Isolation & Happy Path for each feature)
   - **Tier 2:** Boundary & Corner Cases (Edge cases, invalid inputs, bounds, fail-closed states)
   - **Tier 3:** Cross-Feature Combinations (End-to-end multi-module pipelines and interactions)
   - **Tier 4:** Real-World Application Scenarios (Market replay, session lifecycle, crash recovery)

---

## 2. Directory Layout & Test Suite Structure

```
backend/tests/e2e/
├── __init__.py                     # Package marker
├── conftest.py                     # Shared fixtures, test database setup, and mock factories
├── test_tier1_features.py          # Tier 1: Core Feature Coverage (Features 1–30)
├── test_tier2_boundaries.py        # Tier 2: Boundary, Edge, and Corner Cases
├── test_tier3_combinations.py      # Tier 3: Cross-Feature Integration Pipelines
└── test_tier4_scenarios.py         # Tier 4: Real-World Market Scenarios & Disaster Recovery
```

---

## 3. Test Runner Commands

### Full E2E Test Suite Run:
```bash
python -m pytest backend/tests/e2e -v
```

### Running Specific Tiers:
```bash
# Tier 1: Feature Coverage
python -m pytest backend/tests/e2e/test_tier1_features.py -v

# Tier 2: Boundary & Corner Cases
python -m pytest backend/tests/e2e/test_tier2_boundaries.py -v

# Tier 3: Cross-Feature Combinations
python -m pytest backend/tests/e2e/test_tier3_combinations.py -v

# Tier 4: Real-World Application Scenarios
python -m pytest backend/tests/e2e/test_tier4_scenarios.py -v
```

### Running with Concise Output / Failure Stops:
```bash
python -m pytest backend/tests/e2e -q --tb=short -x
```

---

## 4. 4-Tier Methodology Breakdown

### Tier 1: Feature Coverage (Isolation & Primary Behavior)
Validates each of the 30 features in isolation against happy-path criteria:
- **Baseline Integrity (F1–F9):** Quote store timestamp contracts, lifespan managers with guaranteed clean teardown, paper order authentication enforcement, client-side position retention on close rejection, elimination of hardcoded dev secrets, strict order status verification (`FILLED`), loopback address binding.
- **Decision Engine & Ingestion (F10–F14):** Fail-closed handling for missing F&O parameters, timeframe degradation marking, dynamic signal expiry duration alignment, strict LONG/SHORT directional geometry validation, and scan coverage ledger metrics.
- **Paper Execution & Ledger (F15–F21):** Unified authoritative paper ledger, pre-submission risk and freshness validation, persistent idempotency keys, side-correct automated exits (LONG low <= SL, SHORT high >= SL), same-bar conservative resolution, immutable trade journaling, and state reconstruction across restart.
- **Educational UI & Grounded AI (F22–F26):** Navigation structural contracts (Today, Positions & Journal, Learn, Advanced), non-blocking async Gemini adapter (`client.aio`), evidence-grounded quantitative citations, and graceful offline degradation when AI is unavailable.
- **Security & Guardrails (F27–F30):** Permanent live order ban assertion, API key storage in `x-goog-api-key` headers, authenticated portfolio query protection, and fully isolated test fixtures.

### Tier 2: Boundary & Corner Cases
Attacks and stresses boundary conditions:
- Zero, negative, and infinite prices/quantities.
- Extreme stop-loss percentages exceeding maximum risk limits.
- Directional geometry violations (inverted targets, stop above entry for LONG, stop below entry for SHORT).
- Incomplete F&O options chains (missing strike, expiry, lot size, or IV).
- Portfolio margin depletion and overdrawn buying power.
- Malformed authentication headers, empty Bearer tokens, and cross-account IDOR attempts.
- Same-bar simultaneous stop-loss and take-profit crossings (conservative stop priority).
- Stale market quotes exceeding maximum data age thresholds.

### Tier 3: Cross-Feature Combinations
Validates multi-module pipelines where features interact:
- **Scan → Qualification → Sizing → Order → Fill → MTM → Automated Exit → Journal:** Complete signal-to-ledger lifecycle.
- **Durable Idempotency across Server Restarts:** Order submitted → server restarted → duplicate order re-submitted → single fill maintained and cached result returned.
- **F&O Evaluation → Margin Gate → Spread Calculation → Friction Deduction:** Complex options workflow.
- **Multi-Tenant Account Isolation:** Simultaneous orders from separate accounts verify non-leaking balances and position isolation.
- **AI Outage Resilience during Active Trade:** Paper engine monitoring and automated exits proceed without disruption when AI explanations timeout.

### Tier 4: Real-World Application Scenarios
Simulates realistic production conditions:
- **Full Intraday Session Lifecycle:** 09:15–15:30 IST market flow with universe scanning, signal generation, automated paper entries, real-time tick streaming, automated profit taking / stop exits, and session finalization.
- **Adverse Market Gap Replay:** Violent gap openings past stop-loss levels verifying conservative execution and capital preservation.
- **Mid-Session Crash & Recovery:** Abrupt engine termination with active positions followed by clean state recovery from SQLite without position loss or capital double-counting.
- **Portfolio Capacity & Risk Cap Stress:** Hitting maximum open positions limit (5 positions) and verifying that subsequent candidate signals fail closed at the risk gate until a position is closed.

---

## 5. Feature Coverage Matrix (Features 1–30)

| Feature # | Feature Name | Tier 1 Tests | Tier 2 Boundaries | Tier 3 Combinations | Tier 4 Scenarios | Status |
|:---:|---|:---:|:---:|:---:|:---:|:---:|
| **F1** | Quote Store Timestamp Monotonicity | ✓ | ✓ | ✓ | ✓ | Covered |
| **F2** | FastAPI Lifespan Teardown Guard | ✓ | ✓ | ✓ | ✓ | Covered |
| **F3** | Worker Lifespan Teardown Guard | ✓ | ✓ | ✓ | ✓ | Covered |
| **F4** | Paper Order Auth Headers | ✓ | ✓ | ✓ | ✓ | Covered |
| **F5** | Position Retention on Close Failure | ✓ | ✓ | ✓ | ✓ | Covered |
| **F6** | Dev Credential Removal | ✓ | ✓ | ✓ | ✓ | Covered |
| **F7** | Order State Validation (`FILLED`) | ✓ | ✓ | ✓ | ✓ | Covered |
| **F8** | Remove External Probe (Loopback) | ✓ | ✓ | ✓ | ✓ | Covered |
| **F9** | Worker Loopback Binding | ✓ | ✓ | ✓ | ✓ | Covered |
| **F10** | Derivatives Contract Fail-Closed | ✓ | ✓ | ✓ | ✓ | Covered |
| **F11** | Timeframe Degradation Flag | ✓ | ✓ | ✓ | ✓ | Covered |
| **F12** | Signal Expiry Alignment | ✓ | ✓ | ✓ | ✓ | Covered |
| **F13** | Directional Geometry Validation | ✓ | ✓ | ✓ | ✓ | Covered |
| **F14** | Scan Coverage Ledger | ✓ | ✓ | ✓ | ✓ | Covered |
| **F15** | Paper Engine Unification | ✓ | ✓ | ✓ | ✓ | Covered |
| **F16** | Order Pre-Submission Validation | ✓ | ✓ | ✓ | ✓ | Covered |
| **F17** | Durable Idempotency Keys | ✓ | ✓ | ✓ | ✓ | Covered |
| **F18** | Side-Correct Automated Exits | ✓ | ✓ | ✓ | ✓ | Covered |
| **F19** | Same-Bar Conservative Policy | ✓ | ✓ | ✓ | ✓ | Covered |
| **F20** | Immutable Paper Journal | ✓ | ✓ | ✓ | ✓ | Covered |
| **F21** | Crash Recovery | ✓ | ✓ | ✓ | ✓ | Covered |
| **F22** | Primary Navigation Restructure | ✓ | ✓ | ✓ | ✓ | Covered |
| **F23** | Advanced Group Preservation | ✓ | ✓ | ✓ | ✓ | Covered |
| **F24** | Async AI Explanation Engine | ✓ | ✓ | ✓ | ✓ | Covered |
| **F25** | Evidence-Grounded Citations | ✓ | ✓ | ✓ | ✓ | Covered |
| **F26** | Graceful AI Offline Degradation | ✓ | ✓ | ✓ | ✓ | Covered |
| **F27** | Permanent Live Order Ban | ✓ | ✓ | ✓ | ✓ | Covered |
| **F28** | Header Secret Storage (`x-goog-api-key`) | ✓ | ✓ | ✓ | ✓ | Covered |
| **F29** | Authenticated Portfolio Query | ✓ | ✓ | ✓ | ✓ | Covered |
| **F30** | Isolated Test Fixtures | ✓ | ✓ | ✓ | ✓ | Covered |

---

## 6. Fixtures & Mock Boundaries

All E2E test suites utilize the shared fixtures defined in `backend/tests/e2e/conftest.py`:
- `isolated_db`: Creates and tears down an independent SQLite schema for each test session, preventing cross-test data pollution.
- `paper_engine_fixture`: Instantiates an isolated `PaperTradingEngine` with reset capital and clean state.
- `mock_market_feed`: Provides deterministic OHLCV candles, real-time ticks, and option chains without requiring live provider connections.
- `auth_headers`: Generates valid and invalid Bearer tokens for authentication and tenant isolation testing.
- `api_client`: FastAPI `TestClient` initialized against the application with mocked providers.
