## 2026-10-06T17:11:51Z

You are a teamwork_preview_explorer (Backend Codebase Explorer).
Your working directory is: C:\Tradinf2\.agents\teamwork\explorer_survey_backend\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Your mission is to explore and analyze the backend codebase of the APEX workstation in C:\Tradinf2.
Input files to read first:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\docs\APEX_PROJECT_CONTEXT.md

Areas to investigate in the backend:
1. backend/app/main.py and worker.py: Check lifespan management, shutdown handlers, task cancellations, and provider disconnection.
2. Authentication & security: Check paper order and close endpoints, auth dependencies, token verification, localhost binding, and credential handling.
3. Decision engine & ingestion: Check how Indian equities and F&O instruments are handled, contract parameters (expiry, lot size, tick size, OI, volume, spread, margin), handling of missing data (fail-closed UNAVAILABLE vs synthetic data), scan coverage ledger, and LONG/SHORT geometry validation (stop < entry < targets vs targets < entry < stop).
4. Paper trading & ledger: Check paper broker execution, mark-to-market calculations, server ledger, order submission validation, durable idempotency keys, exit lifecycle (TP, SL, strategy invalidation, time/expiry exits, gap handling), immutable journal, and crash recovery logic.
5. AI explanation service: Check how AI explanations are generated, how deterministic calculation evidence is formatted/cited, and how timeouts/offline states are handled.
6. Backend tests: Locate all test files, test runner configuration (pytest), and run a test dry run to assess baseline test pass/fail status.
7. Write your full report to C:\Tradinf2\.agents\teamwork\explorer_survey_backend\report.md and structured handoff to C:\Tradinf2\.agents\teamwork\explorer_survey_backend\handoff.md.
8. When finished, send a message to parent (orchestrator) reporting completion and key findings.
