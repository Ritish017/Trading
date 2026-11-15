# Handoff Report: explorer_m3_3

## 1. Observation
1. **Feature 17 (Durable Idempotency Keys)**:
   - `backend/app/paper_trading/engine.py:74`: `self.idempotency_cache: Dict[str, Dict[str, Any]] = {}` is an in-memory dictionary.
   - `backend/app/paper_trading/engine.py:82-85`:
     ```python
     if order_req.idempotency_key and order_req.idempotency_key in self.idempotency_cache:
         cached = dict(self.idempotency_cache[order_req.idempotency_key])
         cached["is_idempotent_replay"] = True
         return cached
     ```
   - `backend/app/database/models.py:98-125`: `PaperOrderModel` lacks an `idempotency_key` column, and no `PaperIdempotencyModel` table exists in the schema.
   - `backend/app/database/repositories/paper_repository.py:176-316`: `record_trade_execution_atomic` does not store `idempotency_key`.
   - `backend/tests/e2e/test_tier3_combinations.py:143`: Test manually assigns `server2.idempotency_cache[idempotency_key] = cached_payload` across instances rather than restoring it from the database.
2. **Feature 20 (Immutable Paper Journal)**:
   - `backend/app/paper_trading/engine.py:179-199`: `pos` dictionary drops `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, and `decision_reason` passed in `order_req`.
   - `backend/app/paper_trading/engine.py:284-302`: `closed_record` constructed in `close_position` only carries `id`, `account_id`, `pos_id`, `symbol`, `companyName`, `productType`, `side`, `quantity`, `entryPrice`, `exitPrice`, `grossPnL`, `realizedPnL`, `brokerage`, `taxes`, `exit_frictions`, `timestamp`, `closedAt`. Origination fingerprint is lost.
   - `backend/app/database/models.py:168-186`: `PaperClosedTradeModel` lacks `signal_id`, `candidate_id`, `exit_reason`, and `calculation_evidence_json`.
   - `backend/app/main.py:984, 1011`: API endpoints `/api/paper/order` and `/api/paper/close/{pos_id}` do not invoke `AuditEventModel` or `MasterEvidenceLogger`.
3. **Feature 21 (Crash Recovery)**:
   - `backend/app/paper_trading/engine.py:407-428`: `load_from_db` calls `repo.load_portfolio_state(...)`, which only restores capital, positions, and closed trades; `self.idempotency_cache`, `order_history`, and `fill_history` are not restored.
   - `backend/tests/e2e/test_tier1_features.py:586-588`: `test_f21_crash_recovery_state_preservation` simulates crash recovery using in-memory variable assignment (`engine2.capital = saved_capital`, `engine2.positions = saved_positions`).
   - `backend/tests/e2e/test_tier4_scenarios.py:170-172`: `test_s3_disaster_recovery_and_state_reconstruction` also uses in-memory dictionary assignment.
   - `backend/app/live_paper/master_evidence_logger.py:529`: Recovers `max_gseq` from `AuditRepository`, but `PaperTradingEngine` and `main.py` are disconnected from monotonic sequence management.

## 2. Logic Chain
1. From Observation 1: Because `idempotency_cache` is kept solely in memory and neither `PaperOrderModel` nor any idempotency table stores keys in SQLite/PostgreSQL, a server reboot clears all cached keys.
2. Therefore, if a client or automated trigger retries an order after a crash/restart, `execute_order` treats it as a fresh order, executing a duplicate fill and double-debiting capital/margin.
3. From Observation 2: Because `execute_order` omits signal metadata when creating `pos`, `close_position` cannot retrieve originating signal context when building `closed_record`.
4. Therefore, `PaperClosedTradeModel` persists trades disconnected from decision fingerprints and calculation evidence, violating Requirement R3 and Feature 20.
5. From Observation 3: `load_from_db` leaves `idempotency_cache` empty upon restart, and existing crash recovery tests mask this failure by manually copying dictionaries in memory.
6. Therefore, true crash recovery is only partial (restoring positions and capital, but losing idempotency and audit continuity).

## 3. Caveats
1. Real-money broker routing remains strictly prohibited (`LIVE_ORDER_ALLOWED = False`); all execution is confined to the authoritative paper engine.
2. In-process test execution with `run_command` timed out waiting for user approval; however, all codebase logic, repository models, and test assertions were directly inspected and verified via file system reads.
3. Other M3 features (F15, F16, F18, F19) interact with the paper engine but are focused on validation gates, order sizing, automated exit thresholds, and same-bar conservative policies.

## 4. Conclusion
1. **Feature 17**: Implement `PaperIdempotencyModel` in `backend/app/database/models.py`, persist keys and cached responses atomically in `PaperRepository.record_trade_execution_atomic`, and hydrate `self.idempotency_cache` in `PaperTradingEngine.load_from_db`.
2. **Feature 20**: Retain signal metadata in `pos` during `execute_order`, enrich `PaperClosedTradeModel` with `signal_id`, `candidate_id`, `exit_reason`, and `calculation_evidence_json`, and attach statutory friction breakdowns.
3. **Feature 21**: Update `load_portfolio_state` to restore the full ledger (positions, capital, closed trades, and idempotency cache), coordinate monotonic sequence progression via `AuditRepository`, and update E2E tests to verify genuine cold-boot database restoration.

## 5. Verification Method
1. Inspect `backend/app/database/models.py` for `PaperIdempotencyModel` and updated `PaperClosedTradeModel`.
2. Inspect `backend/app/paper_trading/engine.py` for signal retention in `pos` and `idempotency_cache` hydration in `load_from_db`.
3. Run test suites:
   ```bash
   pytest backend/tests/test_database_persistence.py backend/tests/acceptance/test_database_acceptance.py -v
   pytest backend/tests/e2e/test_tier1_features.py -k "f17 or f20 or f21" -v
   pytest backend/tests/e2e/test_tier3_combinations.py -k "t3_durable_idempotency" -v
   ```
4. Invalidation condition: If an order resubmission with the same `idempotency_key` against a restarted engine instance after `load_from_db()` executes as a new fill rather than returning `is_idempotent_replay: True`, the fix is invalid.
