## 2026-10-06T18:23:59Z
You are a teamwork_preview_explorer (Lifespan Test Fix Explorer) for Milestone 1 Iteration 2.
Your dedicated working directory is:
C:\Tradinf2\.agents\teamwork\explorer_m1_it2_1_gen2\

MANDATORY FIRST STEP: Read C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md before starting work. Do not summarize or filter it.
Also read C:\Tradinf2\.agents\teamwork\PROJECT.md.

Issue to investigate:
In backend/tests/test_lifespans_hardening.py, test_app_lifespan_normal_shutdown failed with:
AssertionError: Expected mock to have been awaited once. Awaited 0 times.

Root Cause:
In backend/app/main.py:app_lifespan, pre-startup assigns or mocks market_data_service.active_provider. However, during startup, market_data_service.ensure_initialized() or similar code reassigns market_data_service.active_provider to a new instance, so when app_lifespan runs `finally: await market_data_service.active_provider.disconnect()`, it disconnects the newly assigned provider rather than the pre-startup patched mock.

Your task:
1. Maintain your BRIEFING.md, DISPATCH.md, and progress.md in your working directory.
2. Inspect backend/app/main.py lines 110–160 and backend/tests/test_lifespans_hardening.py.
3. Inspect market_data_service structure and methods in backend/app/signal_engine/market_data_service.py.
4. Formulate the clean fix for test_lifespans_hardening.py (and main.py if needed, e.g. adding market_data_service.disconnect() or ensuring the test fixture patches the active provider properly).
5. Document your findings in report.md and handoff.md in your working directory.
6. Send a message to parent when complete with your report path.
