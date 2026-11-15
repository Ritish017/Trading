## 2026-10-06T18:35:09Z
You are a teamwork_preview_worker (Milestone 1 Baseline Hardening Worker).
Your dedicated working directory is:
C:\Tradinf2\.agents\teamwork\worker_m1_it2_gen2\

MANDATORY FIRST STEP: Read C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md before starting work. Do not summarize or filter it.
Also read C:\Tradinf2\.agents\teamwork\PROJECT.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Context and Explorer Reports to review:
1. Lifespan teardown fix: C:\Tradinf2\.agents\teamwork\explorer_m1_it2_1_gen2\handoff.md and report.md
2. Probe removal and expiry fix: C:\Tradinf2\.agents\teamwork\explorer_m1_it2_2_gen2\handoff.md and report.md
3. E2E test collection fix: C:\Tradinf2\.agents\teamwork\explorer_m1_it2_3_gen2\handoff.md and report.md

Files you own exclusively:
- backend/app/market_data/service.py
- backend/tests/test_lifespans_hardening.py
- backend/app/main.py
- backend/app/signal_engine/options_engine.py
- backend/app/signal_engine/futures_engine.py
- backend/app/signal_engine/__init__.py
- backend/tests/e2e/test_tier1_features.py
- backend/tests/e2e/test_tier2_boundaries.py
- backend/tests/e2e/test_tier3_combinations.py
- backend/tests/e2e/test_tier4_scenarios.py

Implementation Tasks:
1. In backend/app/market_data/service.py: Implement the async disconnect() method on MarketDataService that cleanly delegates to self.active_provider.disconnect().
2. In backend/tests/test_lifespans_hardening.py: Patch market_data_service.disconnect directly in test_app_lifespan_normal_shutdown, test_app_lifespan_exception_guarantees_cleanup, and test_app_lifespan_cancellation_guarantees_cleanup; add test verifying MarketDataService.disconnect() delegates to active_provider.disconnect().
3. In backend/app/main.py:
   - Eliminate all 6 fallback occurrences of https://apex-market-worker-probe.onrender.com / RENDER_WORKER_URL (lines 195, 234, 264, 333, 382, 406). Replace with local loopback LOCAL_WORKER_URL (only if 127.0.0.1 or localhost) or local state evaluation.
   - In /api/signals/{signal_id}/paper-trade (lines 2512–2528): Parse expiry timestamps with timezone awareness (coercing naive to UTC), and fail closed with HTTPException(status_code=400, detail="Invalid or expired signal timestamp") on expiration, invalid format, or error.
4. In backend/app/signal_engine/options_engine.py, futures_engine.py, __init__.py, and backend/tests/e2e/:
   - Provide OptionsDecisionEngine and FuturesDecisionEngine compatibility classes / adapters handling evaluate()/analyze() and parameter mapping (chain -> option_chain, etc.).
   - In backend/tests/e2e/test_tier4_scenarios.py, import ValidationGateResult.
   - Ensure all 4 tiers in backend/tests/e2e collect cleanly.

Verification Requirements:
- Run: python -m pytest backend/tests/test_lifespans_hardening.py
- Run: python -m pytest backend/tests/test_security_hardening.py
- Run: python -m pytest backend/tests/e2e --collect-only
- Verify 0 collection errors and passing unit tests.

Deliverables:
- Record all changes in changes.md in your working directory.
- Write a complete handoff report in handoff.md in your working directory.
- Send a message to parent with your handoff path when complete.
