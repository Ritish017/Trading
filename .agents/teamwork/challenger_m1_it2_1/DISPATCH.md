## 2026-10-06T18:54:14Z
You are teamwork_preview_challenger (Lifespan & Expiry Challenger) for Milestone 1 Iteration 2.
Your dedicated working directory is: C:\Tradinf2\.agents\teamwork\challenger_m1_it2_1\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to inspect:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\.agents\teamwork\worker_m1_it2\handoff.md and changes.md

Mission:
Empirically stress-test lifespan teardown and signal expiry fail-closed logic:
1. Lifespan teardown: Verify that MarketDataService.disconnect() and provider.disconnect() execute without errors or unhandled task leaks.
2. Signal expiry fail-closed: Test submitting paper orders via /api/signals/{id}/paper-trade with:
   - Expired ISO timestamp (e.g. 2020-01-01T00:00:00Z) -> must reject with 400.
   - Naive past datetime string -> must reject with 400.
   - Corrupt timestamp string -> must reject with 400.
   - Valid future timestamp -> must accept and process trade.
3. Formulate your verdict: APPROVE or REQUEST_CHANGES.
4. Write your report to C:\Tradinf2\.agents\teamwork\challenger_m1_it2_1\handoff.md.
5. Send a message to parent reporting your verdict.
