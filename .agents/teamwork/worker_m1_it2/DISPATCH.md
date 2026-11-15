## 2026-10-06T18:42:33Z
You are teamwork_preview_worker (Baseline Integrity Remediation Worker) for Milestone 1 Iteration 2.
Your dedicated working directory is: C:\Tradinf2\.agents\teamwork\worker_m1_it2\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to read:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\.agents\teamwork\reviewer_m1_1\handoff.md and review.md
- C:\Tradinf2\.agents\teamwork\reviewer_m1_2\handoff.md and review.md
- C:\Tradinf2\.agents\teamwork\explorer_m1_it2_1\handoff.md
- C:\Tradinf2\.agents\teamwork\explorer_m1_it2_3\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You own exclusively:
- backend/app/market_data/service.py
- backend/tests/test_lifespans_hardening.py
- backend/app/main.py
- backend/tests/e2e/test_tier1_features.py
- backend/tests/e2e/test_tier2_boundaries.py
- backend/tests/e2e/test_tier3_combinations.py
- backend/tests/e2e/test_tier4_scenarios.py

Scope of Remediation:
1. Lifespan Mock & Disconnect:
   - In backend/app/market_data/service.py: add a disconnect() method to MarketDataService delegating cleanly to active_provider.disconnect() if present.
   - In backend/tests/test_lifespans_hardening.py: apply the fixture/mocking fix from explorer_m1_it2_1\handoff.md ensuring ensure_initialized() runs prior to attaching the disconnect spy, or attach to the post-initialized provider. Ensure test_app_lifespan_normal_shutdown passes!
2. Residual onrender.com URLs:
   - In backend/app/main.py (lines 195, 234, 264, 333, 382, 406): purge all 6 occurrences of https://apex-market-worker-probe.onrender.com. Substitute with local loopback http://127.0.0.1:8001/api/worker/status or local health fallback.
3. Signal Expiry Parsing in /api/signals/{signal_id}/paper-trade:
   - In backend/app/main.py: robustly parse sig_expiry with UTC timezone awareness (e.g. replacing 'Z' with '+00:00', making naive datetimes UTC-aware). If current time > expiry or invalid format, fail closed with HTTPException(status_code=400).
4. E2E Test Suite Imports:
   - In backend/tests/e2e/test_tier1_features.py, test_tier2_boundaries.py, test_tier3_combinations.py: replace OptionsDecisionEngine with OptionsEngine, and FuturesDecisionEngine with FuturesEngine.
   - In backend/tests/e2e/test_tier4_scenarios.py: import ValidationGateResult from backend.app.signal_engine.validation_gates.

Verification Requirements:
1. python -m pytest backend/tests/test_lifespans_hardening.py -v (all tests pass).
2. python -m pytest backend/tests/test_security_hardening.py backend/tests/acceptance/test_security_acceptance.py -v (all pass).
3. python -m pytest backend/tests/e2e --collect-only (clean collection, 0 import errors).
4. Verify 0 occurrences of onrender.com across backend/app/main.py.

Document your changes in C:\Tradinf2\.agents\teamwork\worker_m1_it2\changes.md and write a complete 5-component handoff report to C:\Tradinf2\.agents\teamwork\worker_m1_it2\handoff.md.
Send message to parent upon completion.
