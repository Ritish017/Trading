## 2026-10-06T18:00:31Z
You are teamwork_preview_reviewer (Backend Security Reviewer) for Milestone 1.
Your dedicated working directory is: C:\Tradinf2\.agents\teamwork\reviewer_m1_2\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to inspect:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\.agents\teamwork\worker_m1\handoff.md and changes.md
- Backend files:
  - backend/app/main.py
  - backend/app/worker.py
  - backend/tests/test_lifespans_hardening.py
  - backend/tests/test_security_hardening.py

Tasks:
1. Examine backend lifespan changes and endpoint authentication for correctness, completeness, and robustness.
2. Verify that app_lifespan and worker_lifespan cleanly handle shutdown, exceptions, and task cancellations without leaking tasks or unhandled exceptions.
3. Verify that /api/paper/positions strictly requires authentication and isolates accounts.
4. Verify that /api/signals/{id}/paper-trade enforces QUALIFIED state, non-expired timestamps, and directional geometry.
5. Run the test suite: python -m pytest backend/tests/test_lifespans_hardening.py backend/tests/test_security_hardening.py backend/tests/acceptance/test_security_acceptance.py -v
6. Formulate your verdict: APPROVE or REQUEST_CHANGES.
7. Write your review report to C:\Tradinf2\.agents\teamwork\reviewer_m1_2\review.md and handoff to handoff.md with your explicit VERDICT.
8. Send a message to parent reporting your verdict and summary.
