## 2026-10-06T17:30:18Z
You are a teamwork_preview_test_writer (E2E Test Architect) leading the E2E Testing Track for APEX Workstation.
Your working directory is: C:\Tradinf2\.agents\teamwork\test_writer_e2e\
Create your directory and maintain your progress.md and BRIEFING.md inside it.

Inputs to read:
- C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- C:\Tradinf2\.agents\teamwork\PROJECT.md
- C:\Tradinf2\docs\APEX_ANTIGRAVITY_MASTER_PROMPT.md
- C:\Tradinf2\docs\APEX_PROJECT_CONTEXT.md

Mission:
Build an authoritative, opaque-box, requirement-driven E2E test suite in backend/tests/e2e/ (or pytest-discoverable suite) covering all requirements (R1–R5) and the 30 features in PROJECT.md § Feature Inventory.
Follow the 4-tier methodology:
- Tier 1: Feature Coverage (>=5 test cases per feature for core features, verifying isolation and happy path).
- Tier 2: Boundary & Corner Cases (>=5 test cases per feature covering edge cases, empty data, invalid F&O inputs, missing params, bounds).
- Tier 3: Cross-Feature Combinations (pairwise interactions, e.g., scanning -> qualification -> paper order -> MTM tick -> automated exit -> journal entry).
- Tier 4: Real-World Application Scenarios (end-to-end user workflows, market replay, crash recovery).

Requirements:
1. Create C:\Tradinf2\TEST_INFRA.md (and copy to C:\Tradinf2\.agents\teamwork\TEST_INFRA.md) detailing the test philosophy, architecture, runner command, and coverage checklist.
2. Implement the test files with clear assertions. Ensure tests use mock/fixture market feeds or isolated SQLite environments so they can run offline deterministically without real Upstox credentials.
3. Test runner: Ensure all tests run with pytest backend/tests/e2e -v (or specified command). Run the tests to verify the test harness executes properly.
4. When complete, create C:\Tradinf2\TEST_READY.md (and copy to C:\Tradinf2\.agents\teamwork\TEST_READY.md) with the test runner command, tier breakdown, and feature coverage checklist.
5. Write your report to C:\Tradinf2\.agents\teamwork\test_writer_e2e\report.md and handoff to handoff.md.
6. Send a message to parent reporting completion and status.
