# Milestone 3 Exploration Report: Features 17, 20, and 21

**Author:** `explorer_m3_3`  
**Working Directory:** `C:\Tradinf2\.agents\teamwork\explorer_m3_3\`  
**Target Milestone:** Milestone 3 (Requirement R3) — Paper Execution, Exit Lifecycle, and Journaling  
**Target Features:**  
- **Feature 17**: Durable Idempotency Keys  
- **Feature 20**: Immutable Paper Journal  
- **Feature 21**: Crash Recovery  
**Target Codebase Paths:**  
- `backend/app/database/models.py`  
- `backend/app/database/repositories/paper_repository.py`  
- `backend/app/database/repositories/audit_repository.py`  
- `backend/app/database/connection.py`  
- `backend/app/paper_trading/engine.py`  
- `backend/app/paper_engine/forward_models.py`  
- `backend/app/journal/analytics.py`  
- `backend/app/live_paper/session_runner.py`  
- `backend/app/live_paper/master_evidence_logger.py`  
- `backend/tests/e2e/test_tier1_features.py` (`test_f17_*`, `test_f20_*`, `test_f21_*`)  
- `backend/tests/e2e/test_tier3_combinations.py` (`test_t3_full_signal_to_journal_lifecycle`, `test_t3_durable_idempotency_across_server_restart`)  
- `backend/tests/e2e/test_tier4_scenarios.py` (`test_s1_*`, `test_s2_*`, `test_s3_*`, `test_s4_*`)  
- `backend/tests/acceptance/test_paper_acceptance.py`  
- `backend/tests/test_database_persistence.py`  

---

## 1. Executive Summary

Milestone 3 establishes the authoritative paper execution ledger, exit lifecycle, and post-trade accounting for the APEX trading workstation. An exhaustive audit of the existing implementation across the database layer, paper trading engine, session runner, and test suites reveals a critical architectural situation:

1. **Feature 17 (Durable Idempotency Keys)**: Idempotency is currently **partially implemented purely in-memory** (`engine.idempotency_cache`). There is **zero database persistence** for idempotency keys. Neither `backend/app/database/models.py` nor `PaperRepository` tracks idempotency keys. On server or worker restart, the in-memory cache is wiped out, leaving the engine vulnerable to duplicate order execution and double cash debiting if a client or automated trigger retries an order across a restart.
2. **Feature 20 (Immutable Paper Journal)**: Trade execution and closure are tracked, but **critical forensic linkage is severed at the entry step**. Although `PaperOrderRequest` accepts `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, and `decision_reason`, the engine drops these attributes when constructing the position dictionary. When positions close, `PaperClosedTradeModel` persists gross and net P&L with basic statutory frictions, but has **no linkage to the originating signal fingerprint, candidate evaluation, or calculation evidence**. Moreover, the closed trades are not tied to the append-only cryptographic audit trail (`AuditEventModel` / SHA-256 seal) when invoked via FastAPI REST endpoints.
3. **Feature 21 (Crash Recovery)**: State reconstruction is **asymmetric and incomplete**:
   - `PaperTradingEngine.load_from_db()` restores `capital`, `positions`, and `closed_trades`.
   - However, `load_from_db()` **fails to restore `idempotency_cache`**, active/pending orders from `PaperOrderModel`, order history, or fill history.
   - Monotonic audit sequence numbers are recovered in `master_evidence_logger.py` / `session_runner.py` via `AuditRepository.get_last_sequence_numbers()`, but `PaperTradingEngine` itself and the REST API endpoints in `main.py` do not track or participate in this monotonic sequence.
   - Most dangerously, current E2E test suites (`test_f21_crash_recovery_state_preservation`, `test_t3_durable_idempotency_across_server_restart`, `test_s3_disaster_recovery_and_state_reconstruction`) **mask this gap** by manually copying Python dictionary variables in-memory (`server2.idempotency_cache[k] = cached_payload`) rather than verifying actual recovery from SQLite/PostgreSQL.

Below is the complete forensic audit and concrete implementation blueprint for the worker agent.

---

## 2. Feature 17: Durable Idempotency Keys

### 2.1 Current Implementation Analysis
- **Request Ingestion**: `PaperOrderRequest` (`backend/app/paper_trading/engine.py:32`) defines `idempotency_key: Optional[str] = None`.
- **In-Memory Cache**: `PaperTradingEngine.__init__` (`engine.py:74`) initializes `self.idempotency_cache: Dict[str, Dict[str, Any]] = {}`.
- **Execution Fast-Path**: In `PaperTradingEngine.execute_order` (`engine.py:81-85`):
  ```python
  if order_req.idempotency_key and order_req.idempotency_key in self.idempotency_cache:
      cached = dict(self.idempotency_cache[order_req.idempotency_key])
      cached["is_idempotent_replay"] = True
      return cached
  ```
- **Post-Fill Storage**: If an order fills, line 212-213 stores the response:
  ```python
  if order_req.idempotency_key:
      self.idempotency_cache[order_req.idempotency_key] = res
  ```
- **Acceptance & Tier 1 Tests**:
  - `backend/tests/e2e/test_tier1_features.py:473` (`test_f17_durable_idempotency_keys`) validates that a second execution on the same in-memory engine returns `is_idempotent_replay: True` and does not deduct capital.
  - `backend/tests/acceptance/test_paper_acceptance.py:97` (`test_order_idempotency_prevents_duplicate_execution`) validates duplicate submission against a running engine instance.

### 2.2 Forensic Gaps Identified
1. **Absence of Database Model**:
   - In `backend/app/database/models.py`, `PaperOrderModel` (lines 98–125) does **not** contain an `idempotency_key` column.
   - There is no `PaperIdempotencyModel` table anywhere in the schema.
2. **Absence of Repository Persistence**:
   - `PaperRepository` (`backend/app/database/repositories/paper_repository.py`) has no queries, inserts, or index lookups for idempotency keys.
   - `record_trade_execution_atomic` (lines 176–316) does not accept or store `idempotency_key`.
3. **No Database Hydration on Startup**:
   - `PaperTradingEngine.load_from_db` (`engine.py:407–428`) calls `repo.load_portfolio_state(...)`. It only extracts capital, positions, and closed trades. It never touches `self.idempotency_cache`.
4. **Vulnerability Across Restarts**:
   - In `backend/tests/e2e/test_tier3_combinations.py:118` (`test_t3_durable_idempotency_across_server_restart`), the test author wrote:
     ```python
     server2 = PaperTradingEngine(initial_capital=500000.0)
     server2.capital = cap_after_first
     server2.positions = dict(server1.positions)
     server2.idempotency_cache[idempotency_key] = cached_payload  # MANUALLY COPIED IN TEST!
     ```
     This proves that durability across restarts is **unimplemented**; the test only passes because of manual in-memory test plumbing. If `server2` had called `await server2.load_from_db()`, `idempotency_cache` would be empty, and resubmission would result in a second fill and double debit!

### 2.3 Proposed Worker Implementation Strategy
1. **Add Database Model in `backend/app/database/models.py`**:
   Create a dedicated table `PaperIdempotencyModel`:
   ```python
   class PaperIdempotencyModel(Base):
       __tablename__ = "paper_idempotency_keys"

       id = Column(Integer, primary_key=True, autoincrement=True)
       idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
       account_id = Column(String(100), nullable=False, index=True)
       order_id = Column(String(100), nullable=False, index=True)
       status = Column(String(30), nullable=False, default="FILLED")
       response_json = Column(JSON, nullable=False)
       created_at = Column(DateTime(timezone=True), server_default=func.now())

   Index("idx_paper_idem_acc_key", PaperIdempotencyModel.account_id, PaperIdempotencyModel.idempotency_key)
   ```
   *Rationale:* Storing the complete `response_json` ensures exact idempotent replay parity (same `order_id`, `fill_id`, `position`, `available_capital`, timestamps).
2. **Auto-Migration in `backend/app/database/connection.py`**:
   Add table creation and column check inside `init_db()`.
3. **Atomic Repository Transactions in `PaperRepository`**:
   - Update `record_trade_execution_atomic` to take `idempotency_key: Optional[str] = None` and `order_result: Optional[Dict[str, Any]] = None`.
   - Within the existing atomic transaction block (before `session.commit()`), if `idempotency_key` is present:
     ```python
     if idempotency_key and order_result:
         idem_rec = PaperIdempotencyModel(
             idempotency_key=idempotency_key,
             account_id=account_id,
             order_id=order_result.get("order_id", ""),
             status=order_result.get("status", "FILLED"),
             response_json=order_result,
         )
         self.session.add(idem_rec)
     ```
   - Add `load_idempotency_cache(account_id: str) -> Dict[str, Dict[str, Any]]`:
     ```python
     async def load_idempotency_cache(self, account_id: str) -> Dict[str, Dict[str, Any]]:
         stmt = select(PaperIdempotencyModel).where(PaperIdempotencyModel.account_id == account_id)
         res = await self.session.execute(stmt)
         records = res.scalars().all()
         return {r.idempotency_key: r.response_json for r in records}
     ```
   - In `reset_portfolio_state(account_id)`: delete from `PaperIdempotencyModel`.
4. **Engine Integration (`PaperTradingEngine`)**:
   - In `load_from_db()`:
     ```python
     idem_cache = await repo.load_idempotency_cache(account_id)
     self.idempotency_cache.update(idem_cache)
     ```
   - In `sync_order_to_db()`:
     Pass `order_req.get("idempotency_key")` and the order result to `record_trade_execution_atomic`.

---

## 3. Feature 20: Immutable Paper Journal

### 3.1 Current Implementation Analysis
- **Order Execution**: In `PaperTradingEngine.execute_order` (`engine.py:80–215`), an incoming order is validated, friction calculated, and filled.
- **Position Struct**: Lines 179–199 build the position dictionary:
  `pos = {"id": pos_id, "account_id": account_id, "symbol": ..., "quantity": ..., "entryPrice": ..., "marginLocked": ..., "targetPrice": ..., "stopLoss": ...}`.
- **Position Close**: In `PaperTradingEngine.close_position` (`engine.py:237–328`), effective exit price with friction is determined, gross/net P&L calculated, capital refunded, and a trade record appended to `self.closed_trades`:
  ```python
  closed_record = {
      "id": f"TRD_{pos['symbol']}_{int(time.time() * 1000)}",
      "account_id": pos.get("account_id", "primary_personal_account"),
      "pos_id": pos_id,
      "symbol": pos["symbol"],
      "companyName": pos.get("companyName"),
      "productType": pos.get("productType"),
      "side": pos.get("side"),
      "quantity": qty_to_close,
      "entryPrice": pos["entryPrice"],
      "exitPrice": effective_exit_price,
      "grossPnL": round(gross_pnl, 2),
      "realizedPnL": round(realized_pnl, 2),
      "brokerage": exit_frictions["brokerage"],
      "taxes": total_exit_fees - exit_frictions["brokerage"],
      "exit_frictions": exit_frictions,
      "timestamp": pos.get("timestamp", time.time()),
      "closedAt": time.time(),
  }
  ```
- **Database Model**: `PaperClosedTradeModel` (`models.py:168–186`) stores `trade_id`, `account_id`, `symbol`, `side`, `product_type`, `quantity`, `entry_price`, `exit_price`, `gross_pnl`, `brokerage`, `taxes`, `realized_pnl`, `entry_time`, `closed_at`.
- **E2E Tests**:
  - `backend/tests/e2e/test_tier1_features.py:554` (`test_f20_immutable_paper_journal`) verifies that closed trades contain `symbol`, `realizedPnL > 0`, `brokerage`, `taxes`, `exit_frictions`, and timestamps.
  - `backend/tests/e2e/test_tier3_combinations.py:45` (`test_t3_full_signal_to_journal_lifecycle`) verifies the signal-to-journal progression.

### 3.2 Forensic Gaps Identified
1. **Critical Severing of Signal Fingerprint at Entry**:
   - `PaperOrderRequest` accepts:
     - `signal_id`: Unique identifier of the generated signal.
     - `candidate_id`: ID from the scanner observatory.
     - `strategy_version`: Systematic quantitative strategy version.
     - `signal_engine_version`: Engine version.
     - `configuration_hash`: SHA-256 / hash of frozen risk & indicator config.
     - `decision_reason`: Explicit quantitative reasoning for entering the trade.
   - However, in `engine.py` line 179, when `pos` is assembled, **none of these fields are retained in the position dictionary**!
   - Consequently, when `close_position` runs, `pos` has completely forgotten its originating signal. The closed trade record has **no signal fingerprint, no candidate ID, and no strategy version**.
2. **Missing Calculation Evidence & Exit Attribution**:
   - `PaperClosedTradeModel` does not have columns for:
     - `signal_id` / `decision_fingerprint`
     - `candidate_id`
     - `exit_reason` (e.g., `TAKE_PROFIT`, `STOP_LOSS`, `STRATEGY_INVALIDATION`, `TIME_EXPIRY`, `MANUAL`)
     - `calculation_evidence_json` (entry targets, stop loss, R-multiple, indicator values at entry, holding period bars/seconds)
     - Full statutory friction breakdown (`stt`, `exchange_charges`, `sebi_charges`, `gst`, `stamp_duty`, `slippage`)
   - Contrast this with `PaperJournalEntry` in `backend/app/paper_engine/forward_models.py:138`, which defines these exact forensic fields (`hypothesis_id`, `exit_reason`, `mae`, `mfe`, `technical_evidence`, `execution_drift`). The forward models have the right structure, but the authoritative `PaperTradingEngine` and `PaperClosedTradeModel` do not use them.
3. **Absence of Immutable Audit Chaining**:
   - In `backend/app/main.py:984` (`place_paper_order`) and `main.py:1011` (`close_paper_position`), neither endpoint calls `AuditEventModel` or `MasterEvidenceLogger`.
   - The journal entries are mutable SQL records without a cryptographic SHA-256 seal or audit sequence number linking them to the master event log.

### 3.3 Proposed Worker Implementation Strategy
1. **Preserve Signal Metadata in `PaperPositionModel` and `pos` dict**:
   - In `PaperPositionModel` (`models.py:127`): Add columns `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, `decision_reason`, `target_price`, `stop_loss`.
   - In `PaperTradingEngine.execute_order` (`engine.py:179`): Include all signal metadata fields into `pos`:
     ```python
     pos = {
         ...
         "signal_id": canonical_order.signal_id,
         "candidate_id": canonical_order.candidate_id,
         "strategy_version": canonical_order.strategy_version,
         "configuration_hash": canonical_order.configuration_hash,
         "decision_reason": canonical_order.decision_reason,
     }
     ```
2. **Enrich `PaperClosedTradeModel` (`backend/app/database/models.py:168`)**:
   Add the following columns:
   ```python
   signal_id = Column(String(100), nullable=True, index=True)
   candidate_id = Column(String(100), nullable=True, index=True)
   strategy_version = Column(String(50), nullable=True)
   configuration_hash = Column(String(100), nullable=True)
   exit_reason = Column(String(50), nullable=False, default="MANUAL")
   stt = Column(Float, default=0.0)
   exchange_charges = Column(Float, default=0.0)
   sebi_charges = Column(Float, default=0.0)
   gst = Column(Float, default=0.0)
   stamp_duty = Column(Float, default=0.0)
   slippage = Column(Float, default=0.0)
   total_frictions = Column(Float, default=0.0)
   calculation_evidence_json = Column(JSON, nullable=True)
   ```
3. **Propagate Evidence in `close_position` (`engine.py:237`)**:
   - Add parameter `exit_reason: str = "MANUAL"` to `close_position`.
   - Construct `calculation_evidence_json`:
     ```python
     r_multiple = round(gross_pnl / (abs(pos["entryPrice"] - pos["stopLoss"]) * qty_to_close), 2) if pos.get("stopLoss") and pos["stopLoss"] != pos["entryPrice"] else None
     evidence = {
         "entry_price": pos["entryPrice"],
         "exit_price": effective_exit_price,
         "stop_loss": pos.get("stopLoss"),
         "target_price": pos.get("targetPrice"),
         "r_multiple_realized": r_multiple,
         "decision_reason": pos.get("decision_reason"),
         "frictions": exit_frictions,
     }
     ```
   - Transfer `signal_id`, `candidate_id`, `strategy_version`, `configuration_hash`, `exit_reason`, and `evidence` to `closed_record`.
4. **Link to Append-Only `AuditEventModel`**:
   - In `PaperRepository.record_trade_closure_atomic`:
     Insert an audit event with `event_type="PAPER_TRADE_CLOSED"`, linking the trade ID, signal ID, realized P&L, and monotonic sequence.

---

## 4. Feature 21: Crash Recovery

### 4.1 Current Implementation Analysis
- **Database Restoration**: `PaperTradingEngine.load_from_db` (`engine.py:407–428`) calls `PaperRepository.load_portfolio_state(...)`.
- **State Loaded**:
  - `capital`: restored from `account.available_capital`.
  - `positions`: restored from `PaperPositionModel` (id, symbol, side, quantity, entryPrice, currentPrice, targetPrice, stopLoss, marginLocked, unrealizedPnL, realizedPnL).
  - `closed_trades`: restored from `PaperClosedTradeModel`.
- **Lifespan Startup**: `backend/app/main.py:103` in `ensure_initialized()` executes `await paper_engine.load_from_db()`.
- **Worker Session Runner**: `backend/app/live_paper/session_runner.py:210` executes `await self.paper_engine.load_from_db()` and logs restored position count.
- **Monotonic Sequence Recovery**:
  - In `backend/app/live_paper/master_evidence_logger.py:521` (`recover_sequence_from_db`):
    ```python
    max_gseq, max_lseq = await repo.get_last_sequence_numbers(self.session_date)
    if max_gseq > self._global_sequence_number:
        self._global_sequence_number = max_gseq
    if max_lseq > self._sequence_number:
        self._sequence_number = max_lseq
    ```
  - In `backend/app/live_paper/session_runner.py:180` (`initialize_session`):
    Queries `AuditRepository.get_session_recovery_state(self.session_date)` and increments `self.recovery_count`.

### 4.2 Forensic Gaps Identified
1. **Idempotency Cache Lost on Crash**:
   - Because `load_from_db()` does not touch `idempotency_cache`, any in-flight order retry arriving after a restart will re-execute.
2. **Order History and Fill History Lost**:
   - `self.order_history` and `self.fill_history` are in-memory lists in `PaperTradingEngine`. They are never populated during `load_from_db()`, meaning audit queries on order lifecycle after restart return empty.
3. **Pending / Active Order State Not Restored**:
   - If an order is accepted but awaiting tick fill (e.g. limit order or queued order), `load_from_db()` only queries `PaperPositionModel`. It ignores `PaperOrderModel`.
4. **Audit Sequence Disconnect in REST Server**:
   - While `session_runner.py` in the worker process recovers `max_gseq` from `AuditRepository`, `PaperTradingEngine` in `main.py` has no reference to `AuditRepository` or monotonic sequences.
5. **Testing Illusion**:
   - `test_f21_crash_recovery_state_preservation` (`test_tier1_features.py:576`):
     ```python
     engine2 = PaperTradingEngine(initial_capital=500000.0)
     engine2.capital = saved_capital
     engine2.positions = saved_positions
     ```
   - `test_s3_disaster_recovery_and_state_reconstruction` (`test_tier4_scenarios.py:155`):
     ```python
     session2 = PaperTradingEngine(initial_capital=1000000.0)
     session2.capital = cap_before_crash
     session2.positions = positions_snapshot
     ```
   - Both tests merely test Python variable assignment. They completely bypass SQLite/PostgreSQL persistence and provide zero verification of genuine database recovery!

### 4.3 Proposed Worker Implementation Strategy
1. **Exhaustive `load_portfolio_state` in `PaperRepository`**:
   Update `PaperRepository.load_portfolio_state` to return a 5-tuple:
   `Tuple[float, Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]`
   consisting of:
   - `capital`: Available cash balance.
   - `positions`: All active open positions with signal fingerprint intact.
   - `closed_trades`: Historical closed trades with calculation evidence.
   - `idempotency_cache`: Persisted idempotency keys with replay payloads.
   - `active_orders`: Orders with status `ACCEPTED` / `SUBMITTED`.
2. **Hydrate All Engine Caches in `PaperTradingEngine.load_from_db`**:
   ```python
   async def load_from_db(self, session: Optional[AsyncSession] = None, account_id: str = "primary_personal_account"):
       ...
       cap, pos, trades, idem, active_orders = await repo.load_full_state(account_id, self.initial_capital)
       self.capital = cap
       self.positions = pos
       self.closed_trades = trades
       self.idempotency_cache = idem
       self.order_history = active_orders
   ```
3. **Monotonic Audit Sequence Coordinator**:
   Expose an authoritative monotonic sequence provider via `AuditRepository.get_next_sequence_number(session_date)` so both the background worker and FastAPI engine advance the same monotonic counter.
4. **Authentic Database E2E Tests**:
   Update `test_f21_crash_recovery_state_preservation` and `test_t3_durable_idempotency_across_server_restart`:
   - Engine 1 executes order and syncs to DB via `await engine1.sync_order_to_db(...)`.
   - Engine 2 initializes with zero state, calls `await engine2.load_from_db(session=s, account_id=...)`.
   - Assert `engine2.capital == engine1.capital`.
   - Assert `engine2.positions == engine1.positions`.
   - Assert `engine2.idempotency_cache` has the key.
   - Resubmit with same `idempotency_key` -> returns cached fill with `is_idempotent_replay: True` and zero capital debit!

---

## 5. Summary of Recommended Code Changes

| File | Proposed Change | Purpose |
|------|-----------------|---------|
| `backend/app/database/models.py` | 1. Add `PaperIdempotencyModel`<br>2. Add `signal_id`, `candidate_id`, `strategy_version` to `PaperPositionModel`<br>3. Add `signal_id`, `candidate_id`, `exit_reason`, `frictions_detail`, `calculation_evidence_json` to `PaperClosedTradeModel` | Durable storage for F17 idempotency, F20 journal evidence, and F21 recovery |
| `backend/app/database/connection.py` | Add auto-migration checks in `init_db()` for new columns in `paper_positions`, `paper_closed_trades`, and `paper_idempotency_keys` | Dialect-agnostic zero-downtime schema upgrades for SQLite & PostgreSQL |
| `backend/app/database/repositories/paper_repository.py` | 1. Accept `idempotency_key` & `order_result` in `record_trade_execution_atomic`<br>2. Add `load_idempotency_cache`<br>3. Enrich `record_trade_closure_atomic` with signal fingerprint and friction breakdown<br>4. Update `load_portfolio_state` to load idempotency cache and signal metadata | Atomic transactional persistence & complete recovery |
| `backend/app/paper_trading/engine.py` | 1. Preserve signal metadata in `pos` dictionary during `execute_order`<br>2. Accept `exit_reason` and attach evidence in `close_position`<br>3. Hydrate `self.idempotency_cache` in `load_from_db`<br>4. Pass `idempotency_key` in `sync_order_to_db` | Enforce authoritative memory-DB parity for F17, F20, and F21 |
| `backend/tests/e2e/test_tier1_features.py` | Update `test_f17_*`, `test_f20_*`, `test_f21_*` to verify database durability, signal fingerprint linkage, and cold-engine reboot | Replace in-memory mocks with authoritative persistence checks |
| `backend/tests/e2e/test_tier3_combinations.py` | In `test_t3_durable_idempotency_across_server_restart`, remove manual dictionary assignment `server2.idempotency_cache[k] = v` and use `await server2.load_from_db()` | Authentic verification of durable idempotency across restarts |

---

## 6. Verification Method

To verify the implementation once the Worker finishes code modifications:
1. **Unit & Isolation Verification**:
   ```bash
   pytest backend/tests/test_database_persistence.py backend/tests/acceptance/test_database_acceptance.py -v
   ```
2. **Tier 1 Feature Coverage (F17, F20, F21)**:
   ```bash
   pytest backend/tests/e2e/test_tier1_features.py -k "f17 or f20 or f21" -v
   ```
3. **Tier 3 Combinations (Combinations 1 & 2)**:
   ```bash
   pytest backend/tests/e2e/test_tier3_combinations.py -k "t3_full_signal_to_journal or t3_durable_idempotency" -v
   ```
4. **Tier 4 Real-World Scenarios (Scenarios 1, 2, 3)**:
   ```bash
   pytest backend/tests/e2e/test_tier4_scenarios.py -k "s1 or s2 or s3" -v
   ```
5. **Complete Test Suite Regression Check**:
   ```bash
   pytest backend/tests/acceptance/test_paper_acceptance.py -v
   ```
