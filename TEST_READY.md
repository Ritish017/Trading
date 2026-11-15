# APEX Workstation — End-to-End Test Suite Ready Certification

**Status:** CERTIFIED & READY  
**Version:** 2026.1.0-CERTIFIED  
**Lead Architect:** E2E Test Architect (`test_writer_e2e`)  
**Suite Location:** `backend/tests/e2e/`  

---

## 1. Test Runner Command

To execute the authoritative, opaque-box, requirement-driven E2E test suite:

```bash
python -m pytest backend/tests/e2e -v
```

### Targeted Execution by Tier:
```bash
# Tier 1: Core Feature Coverage (Features 1–30)
python -m pytest backend/tests/e2e/test_tier1_features.py -v

# Tier 2: Boundary & Corner Cases (F&O data, negative bounds, IDOR)
python -m pytest backend/tests/e2e/test_tier2_boundaries.py -v

# Tier 3: Cross-Feature Integration Pipelines (Scan -> Order -> MTM -> Exit -> Journal)
python -m pytest backend/tests/e2e/test_tier3_combinations.py -v

# Tier 4: Real-World Production Scenarios (09:15-15:30 IST Replay, Gap-down, Crash Recovery)
python -m pytest backend/tests/e2e/test_tier4_scenarios.py -v
```

---

## 2. 4-Tier Test Breakdown

| Tier | Test File | Test Count | Scope & Focus |
|:---:|---|:---:|---|
| **Tier 1** | `backend/tests/e2e/test_tier1_features.py` | 30 test suites | **Feature Coverage:** Happy paths, individual isolation, contract invariants for Features 1–30 |
| **Tier 2** | `backend/tests/e2e/test_tier2_boundaries.py` | 11 comprehensive suites | **Boundary & Corner Cases:** Zero/negative params, capital depletion, geometry bounds, F&O missing data, security attacks, IDOR |
| **Tier 3** | `backend/tests/e2e/test_tier3_combinations.py` | 5 integration pipelines | **Cross-Feature Combinations:** Full signal-to-journal pipeline, restart idempotency, options spread execution, multi-tenant isolation, AI degradation |
| **Tier 4** | `backend/tests/e2e/test_tier4_scenarios.py` | 4 production scenarios | **Real-World Scenarios:** Full 09:15–15:30 IST session replay, gap-down market stress, crash and disaster recovery, portfolio capacity saturation |

---

## 3. Requirements (R1–R5) & Feature Coverage Matrix

### Requirement Mapping:
- **R1: Baseline Integrity & First-Wave Defect Repairs** -> Covered across F1–F9 (Quote store timestamps, lifespans, auth headers, position retention on close failure, dev credential removal, order state validation, loopback binding).
- **R2: Server-Authoritative Decision Contract & Market Ingestion** -> Covered across F10–F14 (F&O fail-closed, timeframe degradation, dynamic signal expiry, directional geometry LONG/SHORT, scan coverage ledger).
- **R3: Authoritative Paper Execution, Exit Lifecycle, and Journaling** -> Covered across F15–F21 (Single paper engine, pre-validation, durable idempotency, side-correct automated exits, same-bar conservative resolution, immutable journal, crash recovery).
- **R4: Grounded AI Explanations and Educational UI** -> Covered across F22–F26 (Primary navigation structure, Advanced container, async Gemini adapter, evidence-grounded citations, graceful offline degradation).
- **R5: Security, Local Operation, and Real-Money Guardrails** -> Covered across F27–F30 (`LIVE_ORDER_ALLOWED = False` permanent ban, header secret auth, portfolio query protection, isolated test fixtures).

### Feature Inventory Verification:
| # | Feature | Target File | Verification Method | Status |
|:---:|---|---|---|:---:|
| 1 | Quote Store Timestamp Fix | `canonicalQuoteStore.ts` | Monotonicity progression & tick ordering assertions | READY |
| 2 | FastAPI Lifespan Guard | `backend/app/main.py` | `app_lifespan` context manager validation | READY |
| 3 | Worker Lifespan Guard | `backend/app/worker.py` | `worker_lifespan` context manager validation | READY |
| 4 | Paper Order Auth Headers | `backend/app/main.py` | 401 unauthenticated mutation rejection | READY |
| 5 | Position Retention on Close Failure | `backend/app/paper_trading/engine.py` | Failed close preserves position in state | READY |
| 6 | Dev Credential Removal | Frontend & Config | Absence of hardcoded default dev secrets | READY |
| 7 | Order State Validation | `backend/app/paper_trading/engine.py` | `FILLED` state verification | READY |
| 8 | Remove External Probe | Network / Loopback | Local loopback compliance assertion | READY |
| 9 | Worker Loopback Binding | `backend/app/worker.py` | Worker loopback host binding | READY |
| 10 | Derivatives Contract Fail-Closed | `options_engine.py`, `futures_engine.py` | Missing data fails closed to `OPTIONS_DATA_INSUFFICIENT` | READY |
| 11 | Timeframe Degradation Flag | `signal_pipeline.py` | Secondary timeframe degradation flag | READY |
| 12 | Signal Expiry Alignment | `models.py` | Dynamic candle duration multiplier | READY |
| 13 | Directional Geometry Validation | `validation_gates.py`, `stop_target_engine.py` | LONG `stop < entry < targets`, SHORT `targets < entry < stop` | READY |
| 14 | Scan Coverage Ledger | `scanner.py`, `models.py` | `ScannerPipelineStats` metrics verification | READY |
| 15 | Paper Engine Unification | `backend/app/paper_trading/engine.py` | Single authoritative ledger & portfolio state | READY |
| 16 | Order Pre-Submission Validation | `backend/app/paper_trading/engine.py` | Quantity, price, margin bounds revalidation | READY |
| 17 | Durable Idempotency Keys | `backend/app/paper_trading/engine.py` | Duplicate keys return cached fill without double debit | READY |
| 18 | Side-Correct Automated Exits | `backend/app/paper_trading/engine.py` | LONG (low <= SL), SHORT (high >= SL) triggers | READY |
| 19 | Same-Bar Conservative Policy | `backend/app/paper_trading/engine.py` | Stop-loss takes precedence over target in same bar | READY |
| 20 | Immutable Paper Journal | `backend/app/paper_trading/engine.py` | Closed trade persistency with full friction breakdown | READY |
| 21 | Crash Recovery | `backend/app/paper_trading/engine.py` | State restoration from database/snapshot | READY |
| 22 | Primary Navigation Restructure | Frontend Navigation | 3 Primary tabs: Today, Positions & Journal, Learn | READY |
| 23 | Advanced Group Preservation | Frontend Navigation | 9 Advanced analytical modules preserved | READY |
| 24 | Async AI Explanation Engine | `backend/app/ai_engine/gemini_client.py` | Non-blocking `client.aio` execution | READY |
| 25 | Evidence-Grounded Citations | `backend/app/ai_engine/` | Strict factual parameter citation checks | READY |
| 26 | Graceful AI Offline Degradation | `backend/app/ai_engine/` | Visible status badges and local deterministic templates | READY |
| 27 | Permanent Live Order Ban | `backend/app/live_paper/safety.py` | Hard assertion `LIVE_ORDER_ALLOWED == False` | READY |
| 28 | Header Secret Storage | `backend/app/security/auth.py` | Authorization headers verified | READY |
| 29 | Authenticated Portfolio Query | `backend/app/main.py` | Account-scoped positions require auth | READY |
| 30 | Isolated Test Fixtures | `backend/tests/e2e/conftest.py` | Dedicated test environment without session data | READY |

---

## 4. Test Harness Environment Guarantee

- **Zero External Network Dependencies:** No live network requests are made to Upstox, Google Gemini, or external cloud endpoints during testing.
- **Pure Local Execution:** Operates seamlessly under pytest in Windows PowerShell or Linux/macOS environments.
- **Deterministic Oracles:** All expected values are mathematically derived or computed against authoritative quantitative specifications.
