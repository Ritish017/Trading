## 2026-10-06T17:43:16Z
You are teamwork_preview_worker (Baseline Integrity Implementer) for Milestone 1 (R1).
Your dedicated working directory is: C:\Tradinf2\.agents\teamwork\worker_m1\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to read thoroughly:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\.agents\teamwork\explorer_m1_1\handoff.md and report.md
- C:\Tradinf2\.agents\teamwork\explorer_m1_2\handoff.md and report.md
- C:\Tradinf2\.agents\teamwork\explorer_m1_3\handoff.md and report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You own exclusively:
- frontend/src/stores/canonicalQuoteStore.ts
- frontend/src/utils/auth.ts (or apiAuth.ts)
- frontend/src/App.tsx
- frontend/src/components/pages/SignalCenterPage.tsx
- frontend/src/components/IndexTickerBar.tsx
- backend/app/main.py
- backend/app/worker.py
- backend/tests/test_lifespans_hardening.py
- backend/tests/test_security_hardening.py

Scope of Implementation:
1. Frontend Quote Store: In `frontend/src/stores/canonicalQuoteStore.ts`, fix the undeclared `incomingTs` variables in `updateFromWS`. Implement timestamp monotonicity check to reject outdated ticks.
2. Frontend Auth & Mutation Guards:
   - Create auth helper (`frontend/src/utils/auth.ts`) providing standard auth headers.
   - In `frontend/src/App.tsx`, attach auth headers to `/api/paper/order` and `/api/paper/close/{id}`.
   - In `frontend/src/App.tsx`, fix `handleClosePaperPosition` so that if the API call fails or is not ok, the position is NOT removed from client state (`paperPositions`), and an error notification is shown.
3. Frontend Credential Sanitization & Order Status:
   - In `frontend/src/components/pages/SignalCenterPage.tsx`, remove hardcoded dev key `'apex_default_dev_key'` and use the auth helper.
   - Only confirm order placement if `data.order_result?.status === 'FILLED'`. If status is `REJECTED` or failed, display an error message.
4. Remove External Probe:
   - In `frontend/src/components/IndexTickerBar.tsx`, remove external Render probe URL `https://apex-market-worker-probe.onrender.com/api/worker/status` to maintain local loopback isolation.
5. Backend Lifespans & Shutdown Teardown:
   - In `backend/app/main.py`, wrap `yield` in `app_lifespan` inside `try ... finally` to guarantee `active_provider.disconnect()` runs on shutdown, exception, or cancellation.
   - In `backend/app/worker.py`, wrap `yield` in `worker_lifespan` inside `try ... finally`. Retain an explicit reference to the startup task created by `create_task(worker_instance.start())`.
   - In `backend/app/worker.py`, improve `worker_instance.stop()` to cleanly cancel and await any running or starting tasks even if `self.is_running` is False.
   - Change default host binding to `127.0.0.1`.
6. Backend Endpoint Auth Hardening:
   - In `backend/app/main.py`, enforce `auth: AccountContext = Depends(verify_api_key)` on `/api/paper/positions` to prevent unauthenticated portfolio dumping.
   - In `/api/signals/{id}/paper-trade`, enforce authentication and revalidate that the signal is in `QUALIFIED` state and not expired.

Verification:
You MUST run the builds and tests and document the exact outputs in your handoff report:
1. In `frontend`: Run `npm.cmd run lint` (`tsc --noEmit`). Must exit 0 with zero errors.
2. In `frontend`: Run `npm.cmd run build`. Must compile successfully.
3. In `backend`: Run `python -m pytest backend/tests/test_security_hardening.py backend/tests/acceptance/test_security_acceptance.py -v`.
4. Run/add lifespan tests verifying clean shutdown without leaked tasks or unhandled exceptions.

Document your full work in `C:\Tradinf2\.agents\teamwork\worker_m1\changes.md` and write a complete 5-component handoff report to `C:\Tradinf2\.agents\teamwork\worker_m1\handoff.md`.
Send a message to parent upon completion.
