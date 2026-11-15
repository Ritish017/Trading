## 2026-10-06T17:30:18Z
You are a teamwork_preview_explorer (Backend Lifespan Explorer) for Milestone 1 (R1).
Your working directory is: C:\Tradinf2\.agents\teamwork\explorer_m1_2\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to read:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\.agents\teamwork\explorer_survey_backend\report.md

Scope: Backend Lifespans & Process Teardown Guards:
1. backend/app/main.py:
   - In app_lifespan, wrap yield in try ... finally so provider disconnect and resource cleanup always run on shutdown, exception, or task cancellation.
2. backend/app/worker.py:
   - In worker_lifespan, wrap yield in try ... finally.
   - Store the background startup task created by asyncio.create_task(worker_instance.start()) in an explicit reference (e.g. worker_instance._startup_task or module-level variable) so it cannot be garbage-collected.
   - In worker_instance.stop(), ensure that even if self.is_running is False (startup in progress), any ongoing startup tasks or runner tasks are cleanly cancelled and awaited.
3. backend/app/worker.py:
   - Change default host binding from 0.0.0.0 to 127.0.0.1 (HOST = os.environ.get("HOST", "127.0.0.1")).

Tasks:
- Inspect the exact code in main.py and worker.py.
- Formulate exact replacement code and teardown logic for the Worker.
- Recommend unit/integration tests to verify graceful shutdown and cancellation handling.
- Write your analysis to C:\Tradinf2\.agents\teamwork\explorer_m1_2\report.md and handoff to handoff.md.
- Send a message to parent reporting completion.
