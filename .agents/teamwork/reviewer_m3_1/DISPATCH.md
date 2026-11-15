# Task Assignment: reviewer_m3_1

## Objective
Independent Review of Milestone 3 (Requirement R3): Authoritative Paper Execution, Exit Lifecycle, and Journaling (Features 15 through 21).

## Authoritative Inputs
- Original Request: C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md (MANDATORY: Read first!)
- Project Plan: C:\Tradinf2\.agents\teamwork\PROJECT.md
- Worker Handoff: C:\Tradinf2\.agents\teamwork\worker_m3\handoff.md
- Code Under Review:
  - `backend/app/paper_trading/engine.py`
  - `backend/app/paper_engine/bridge.py`
  - `backend/app/database/models.py`
  - `backend/app/database/connection.py`
  - `backend/app/database/repositories/paper_repository.py`
  - `backend/app/main.py`
  - `backend/tests/e2e/test_tier1_features.py` (F15–F21)
  - `backend/tests/e2e/test_tier3_combinations.py`

## Review Criteria
1. **Feature 15 (Paper Engine Unification)**: Is `PaperTradingEngine` truly the single server-authoritative ledger? Does `PaperTradingBridge` cleanly delegate state, cash, positions, and audits without diverging?
2. **Feature 16 (Order Pre-Submission Validation)**: Does `validate_order_pre_submission` validate geometry for BUY and SELL, check signal qualification & expiry, enforce portfolio saturation limits, and validate cash/margin requirements? Is the SHORT margin bug resolved?
3. **Feature 17 (Durable Idempotency Keys)**: Are idempotency keys stored in the database (`PaperIdempotencyModel`) and restored? Does duplicate submission return cached response without double debit or execution?
4. **Feature 18 (Side-Correct Automated Exits)**: Does `process_market_tick` and `evaluate_exits` evaluate LONG (low <= SL, high >= TP) and SHORT (high >= SL, low <= TP) correctly with conservative gap defense?
5. **Feature 19 (Same-Bar Conservative Resolution Policy)**: Does stop-loss take precedence when both stop and target are breached within the same bar, with `same_bar_conflict=True`?
6. **Feature 20 (Immutable Paper Journal)**: Are signal fingerprints retained in positions and closed trades? Are statutory frictions and calculation evidence stored?
7. **Feature 21 (Crash Recovery)**: Does `load_from_db` restore complete portfolio state including idempotency cache?
8. **Test Execution**: Run the test suites yourself to verify test passes:
   - `python -m pytest backend/tests/e2e/test_tier1_features.py -k "f15 or f16 or f17 or f18 or f19 or f20 or f21" -v`
   - `python -m pytest backend/tests/test_database_persistence.py -v`
   - `python -m pytest backend/tests/test_paper_bridge.py backend/tests/test_unified_paper_order.py -v`
   - `python -m pytest backend/tests/acceptance/test_paper_acceptance.py -v`
   - `python -m pytest backend/tests/e2e/test_tier3_combinations.py -v`

## Output Requirements
State your explicit verdict: `APPROVE` or `REQUEST_CHANGES`.
Write your full review report to `C:\Tradinf2\.agents\teamwork\reviewer_m3_1\handoff.md` and send a completion message.


## 2026-10-07T17:58:03Z
[Message] timestamp=2026-10-07T17:58:03Z sender=db928666-a41e-4bc1-8308-20a2c4588dfa priority=MESSAGE_PRIORITY_HIGH content=You are reviewer_m3_1. Your working directory is C:\Tradinf2\.agents\teamwork\reviewer_m3_1\.
Read your instructions in C:\Tradinf2\.agents\teamwork\reviewer_m3_1\DISPATCH.md.
MANDATORY: Read C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md before starting work.
Review the Milestone 3 implementation by worker_m3 across Features 15–21.
Examine code correctness, completeness, and interface contracts.
Execute test commands to verify all tests pass.
State your explicit verdict: APPROVE or REQUEST_CHANGES.
Write your review report to C:\Tradinf2\.agents\teamwork\reviewer_m3_1\handoff.md and send a completion message back to the caller.
