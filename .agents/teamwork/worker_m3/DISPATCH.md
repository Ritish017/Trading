# Task Assignment: worker_m3

## Objective
Implement Milestone 3 (Requirement R3): Authoritative Paper Execution, Exit Lifecycle, and Journaling (Features 15 through 21).

## Mandatory Inputs & References
- ORIGINAL REQUEST (MANDATORY: Read first!): C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
- Project Scope: C:\Tradinf2\.agents\teamwork\PROJECT.md
- Explorer 1 Report (F15 Unification & F16 Pre-submission): C:\Tradinf2\.agents\teamwork\explorer_m3_1\report.md
- Explorer 2 Report (F18 Side-Correct Exits & F19 Same-Bar Policy): C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md
- Explorer 3 Report (F17 Idempotency, F20 Journal, F21 Recovery): C:\Tradinf2\.agents\teamwork\explorer_m3_3\report.md

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Write Ownership & Target Files
You exclusively own and may edit the following files:
1. `backend/app/database/models.py` (Add `PaperIdempotencyModel`, enrich `PaperPositionModel` and `PaperClosedTradeModel`)
2. `backend/app/database/connection.py` (Ensure schema migrations/table creation for new columns/tables in `init_db()`)
3. `backend/app/database/repositories/paper_repository.py` (Atomic persistence of idempotency keys, signal metadata, friction breakdown, full state loading)
4. `backend/app/paper_trading/engine.py` (Unified authoritative engine: `validate_order_pre_submission`, `process_market_tick`, `evaluate_exits`, `same_bar_conflict`, `load_from_db`, signal metadata retention in `pos`, enriched `close_position`)
5. `backend/app/paper_engine/bridge.py` (Refactor `PaperTradingBridge` to delegate state, cash, positions, and trades to authoritative `PaperTradingEngine`)
6. `backend/app/main.py` (Route `/api/paper/performance` and `/api/paper/audits` to `paper_engine`, wire `process_market_tick` into `on_normalized_tick_received`)
7. `backend/tests/e2e/test_tier1_features.py` (Upgrade tests for F15–F21 to verify real engine and database functionality)
8. `backend/tests/e2e/test_tier3_combinations.py` (Upgrade restart idempotency test to use authentic `load_from_db`)

## Implementation Details

### 1. Feature 15: Paper Engine Unification
- Consolidate `PaperTradingBridge` and `PaperTradingEngine` so that `PaperTradingEngine` is the single server-authoritative ledger.
- `PaperTradingBridge` delegates all cash, positions, order execution, and performance calculation to `PaperTradingEngine`.
- Maintain `trade_audits: List[PaperTradeAudit]` in `PaperTradingEngine`.
- Ensure `/api/paper/performance`, `/api/paper/audits`, `/api/paper/positions` all query `PaperTradingEngine`.

### 2. Feature 16: Order Pre-Submission Validation
- In `PaperTradingEngine`, implement `validate_order_pre_submission`:
  - Check quantity > 0, price > 0, symbol present.
  - Check directional geometry: BUY requires `stopLoss < price < targetPrice` (when set); SELL requires `targetPrice < price < stopLoss` (when set).
  - Check signal qualification & freshness/expiry: if `signal_id` provided, verify signal status is `QUALIFIED` (not `CANDIDATE`, `REJECTED`, or `EXPIRED`) and not expired.
  - Check margin & cash requirements: calculate margin + Indian statutory friction fees; ensure sufficient capital for both BUY and SELL (SHORT). Fix the SELL margin bypass bug.
  - Check portfolio capacity (max open positions limit).
- Integrate this validation into `execute_order()`, rejecting invalid orders with explicit reason.

### 3. Feature 17: Durable Idempotency Keys
- Add `PaperIdempotencyModel` in `backend/app/database/models.py`.
- In `PaperRepository`, save idempotency key with `response_json` in `record_trade_execution_atomic`.
- Add `load_idempotency_cache` to `PaperRepository`.
- In `PaperTradingEngine.load_from_db`, hydrate `self.idempotency_cache`.
- In `PaperTradingEngine.sync_order_to_db`, persist `idempotency_key`.

### 4. Feature 18: Side-Correct Automated Exits
- Add `process_market_tick(symbol, ltp, high, low, open_price, timestamp)` and `evaluate_exits` to `PaperTradingEngine`.
- LONG: `low <= stop_loss` -> `EXIT_STOP` (with gap defense if `open <= stop_loss`); `high >= take_profit` -> `EXIT_TARGET`.
- SHORT: `high >= stop_loss` -> `EXIT_STOP` (with gap defense if `open >= stop_loss`); `low <= take_profit` -> `EXIT_TARGET`.
- In `close_position`, record `exit_reason` (`STOP_LOSS`, `TAKE_PROFIT`, `MANUAL`) and `exit_type`.
- Wire `process_market_tick` into `main.py` tick ingestion.

### 5. Feature 19: Same-Bar Conservative Resolution Policy
- If both stop loss and target are crossed within the same bar (`low <= stop` AND `high >= target` for LONG; `high >= stop` AND `low <= target` for SHORT), Stop-Loss takes absolute conservative precedence.
- Set `same_bar_conflict = True` and trigger `EXIT_STOP`.

### 6. Feature 20: Immutable Paper Journal
- In `execute_order()`, retain `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, `decision_reason`, `targetPrice`, `stopLoss` in `pos`.
- In `PaperClosedTradeModel`, add columns for `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, `exit_reason`, friction breakdowns, and `calculation_evidence_json`.
- In `close_position()`, populate calculation evidence (including `r_multiple_realized` and friction breakdown) and pass to DB.

### 7. Feature 21: Crash Recovery
- In `PaperRepository.load_portfolio_state`, load `capital`, `positions`, `closed_trades`, `idempotency_cache`, and active orders.
- In `PaperTradingEngine.load_from_db`, restore full state so a cold-started engine has complete parity with the database.

## Verification Requirements
You MUST run the build/test commands and include the output in your handoff report:
1. `python -m pytest backend/tests/e2e/test_tier1_features.py -k "f15 or f16 or f17 or f18 or f19 or f20 or f21" -v`
2. `python -m pytest backend/tests/test_database_persistence.py backend/tests/acceptance/test_database_acceptance.py -v`
3. `python -m pytest backend/tests/test_paper_bridge.py backend/tests/test_unified_paper_order.py -v`
4. `python -m pytest backend/tests/acceptance/test_paper_acceptance.py -v`
5. `python -m pytest backend/tests/e2e/test_tier3_combinations.py -v`

Write your completion report to `C:\Tradinf2\.agents\teamwork\worker_m3\handoff.md` and send a completion message.


## 2026-10-07T17:32:21Z
You are worker_m3. Your working directory is C:\Tradinf2\.agents\teamwork\worker_m3\.
Read your instructions in C:\Tradinf2\.agents\teamwork\worker_m3\DISPATCH.md.
MANDATORY: Read C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md before starting work.
Read the explorer reports:
- C:\Tradinf2\.agents\teamwork\explorer_m3_1\report.md
- C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md
- C:\Tradinf2\.agents\teamwork\explorer_m3_3\report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Implement Features 15 through 21 (Milestone 3 / Requirement R3).
Execute builds and tests to verify your implementation.
Write your completion report to C:\Tradinf2\.agents\teamwork\worker_m3\handoff.md and send a completion message back to the caller.
