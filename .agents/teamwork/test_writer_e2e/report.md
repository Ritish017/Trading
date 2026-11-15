# APEX Workstation — E2E Testing Track Architect Report

**Agent:** `teamwork_preview_test_writer` (`test_writer_e2e`)  
**Timestamp:** 2026-10-06T17:45:00Z  
**Target Suite:** `backend/tests/e2e/`  

---

## 1. Executive Summary

The E2E Test Architecture for APEX Workstation is fully designed, implemented, and certified. The test harness provides authoritative, requirement-driven, opaque-box test coverage spanning Requirements R1 through R5 and all 30 features from `PROJECT.md` § Feature Inventory across a progressive 4-tier hierarchy.

All test suites operate 100% offline and deterministically without live broker credentials or external LLM API dependencies, utilizing isolated in-memory test structures.

---

## 2. Test Files Created

1. **Test Infrastructure & Specifications:**
   - `C:\Tradinf2\TEST_INFRA.md` (and `.agents/teamwork/TEST_INFRA.md`): Test philosophy, architecture, runner commands, coverage matrix, and mock boundaries.
   - `C:\Tradinf2\TEST_READY.md` (and `.agents/teamwork/TEST_READY.md`): Test runner verification, tier breakdown, and feature readiness certification.

2. **Pytest E2E Suite (`backend/tests/e2e/`):**
   - `backend/tests/e2e/__init__.py`: Package initialization.
   - `backend/tests/e2e/conftest.py`: Deterministic test fixtures, isolated test authentication mapping (`TEST_CONFIG_AUTH`), clean paper engine instantiation, and realistic mock market/options data.
   - `backend/tests/e2e/test_tier1_features.py`: **Tier 1 (Feature Coverage):** 30 test suites covering happy paths, isolation, and contracts for Features 1–30.
   - `backend/tests/e2e/test_tier2_boundaries.py`: **Tier 2 (Boundary & Corner Cases):** 11 suites covering negative prices/quantities, capital overdraw, partial closes, geometry violations (LONG & SHORT), quantitative gate bounds (R:R, stop percentage, portfolio capacity), F&O data failure, authentication attacks, and IDOR prevention.
   - `backend/tests/e2e/test_tier3_combinations.py`: **Tier 3 (Cross-Feature Combinations):** 5 integration pipelines covering full signal-to-journal lifecycle, durable idempotency surviving restarts, options spread structuring & execution, multi-tenant ledger isolation, and offline AI degradation during active trading.
   - `backend/tests/e2e/test_tier4_scenarios.py`: **Tier 4 (Real-World Application Scenarios):** 4 comprehensive production scenarios covering a complete 09:15–15:30 IST intraday session replay (long and short trades, MTM progression, profit/stop exits, daily summary), gap-down market stress with conservative fill policy, crash and disaster recovery, and portfolio exposure saturation.

---

## 3. How to Run the Tests

```bash
# Full E2E Test Suite Run:
python -m pytest backend/tests/e2e -v

# Individual Tier Runs:
python -m pytest backend/tests/e2e/test_tier1_features.py -v
python -m pytest backend/tests/e2e/test_tier2_boundaries.py -v
python -m pytest backend/tests/e2e/test_tier3_combinations.py -v
python -m pytest backend/tests/e2e/test_tier4_scenarios.py -v
```

---

## 4. Discovered Implementation Defects & Observations (For Escalation)

In accordance with the test writer role (test code only, never implementation code; escalate defects to implementing agents):

1. **Frontend Type Check Defect (Feature 1 Target):**
   - **Location:** `frontend/src/stores/canonicalQuoteStore.ts:152, 163`
   - **Defect:** `incomingTs` is referenced in `updateFromWS()` without being declared/extracted from `tick` (unlike `updateFromREST()`). This causes `TS2304: Cannot find name 'incomingTs'`.
   - **Escalation:** Assigned to UI / Frontend implementing agent for Milestone M1.

2. **AI Header Secret Storage (Feature 28 Target):**
   - **Location:** `backend/app/ai_engine/gemini_client.py:37, 81`
   - **Defect:** Google Gemini REST URL includes API key in the query string (`?key={self.api_key}`) rather than using the `x-goog-api-key` header.
   - **Escalation:** Assigned to AI / Security implementing agent for Milestone M5.
