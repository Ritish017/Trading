## 2026-10-06T19:06:57Z
You are teamwork_preview_worker (Surgical Fix Worker) for Milestone 1 Iteration 3.
Working directory: C:\Tradinf2\.agents\teamwork\worker_m1_it3\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
- backend/app/market_data/service.py
- backend/tests/test_lifespans_hardening.py

Scope:
1. In backend/app/market_data/service.py:
   - Inspect lines 120–190. Remove the duplicate definition of async def disconnect(self) (lines 172–183).
   - Ensure the single canonical async def disconnect(self) -> None: sets self.status_code = "DISCONNECTED", self.provider_mode = "UNAVAILABLE", and awaits self.active_provider.disconnect() if present.
2. In backend/tests/test_lifespans_hardening.py:
   - Fix the fixture setup: remove the autouse=True async fixture that broke sync tests in pytest 9.0.3.
   - In the specific async tests that test app_lifespan (e.g. test_app_lifespan_normal_shutdown, test_app_lifespan_market_data_service_disconnect_cleanly), call await ensure_initialized() at the beginning of the test before patching or mocking active_provider.disconnect().
3. Verification:
   - Run python -m pytest backend/tests/test_lifespans_hardening.py -v.
   - Run python -m pytest backend/tests/test_security_hardening.py -v.
   - Document commands and outputs in handoff.md.
4. Send message to parent upon completion.
