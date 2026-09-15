# APEX Session Lifecycle, Event Provenance, Timestamp Semantics & Audit Sequencing Hardening

## 1. Problem Discovered
In the September 15, 2026 production live log (`APEX_2026-09-15_MASTER.jsonl`), forensic inspection revealed critical lifecycle and audit integrity anomalies:
- A worker process initialized the trading day session `APEX-WORKER-2026-09-15` at 00:44 IST during premarket hours.
- At 01:10 IST, upon receiving a shutdown or container cycle, the session runner prematurely executed a terminal session close (`SESSION_END`), emitting finalization reports and marking the session as closed for the trading day.
- At 09:49 IST, when the worker restarted during live market hours, it initialized under the *same* `experiment_id` (`APEX-WORKER-2026-09-15`) but created a new session run and reset its event sequence counter back to `1`.
- While the Upstox live feed, protobuf decoding, candle aggregation, and strategy evaluation functioned cleanly, having multiple disjoint session runs and reset sequence numbers broke audit monotonicity, replay reproducibility, and database consistency for a single trading day.

## 2. Evidence from September 15, 2026 Log
Forensic evidence extracted from `logs/live_paper/2026-09-15/APEX_2026-09-15_MASTER.jsonl`:
- **Line 1 (00:44:48 IST)**: First `SESSION_START` event emitted with `sequence_number: 1`, `experiment_id: "APEX-WORKER-2026-09-15"`.
- **Line 82 (01:10:48 IST)**: `SESSION_END` emitted with `sequence_number: 82`, triggering terminal finalization reports over 8 hours before market open.
- **Line 83 (09:49:50 IST)**: Second `SESSION_START` event emitted under the same `experiment_id`, resetting `sequence_number` to `1`.
- **Lines 84–7592 (09:50:00 to 10:38:00 IST)**: Authentic Upstox live WebSocket ticks arrived, multi-timeframe candles aggregated, but audit sequencing contained duplicate sequence numbers (e.g. sequence 1 through 82 occurred twice on the same trading day).

## 3. Root Cause
1. **Unconditional Finalization on Process Stop**: `SessionRunner.stop()` called `finalize_fno_and_session_close()` unconditionally whenever the worker shut down, regardless of whether the market was closed or in premarket.
2. **In-Memory Volatile Sequence Tracking**: Sequence numbering was kept purely in volatile process memory (`self.sequence_number = 0`). Because Render and cloud containers use ephemeral disks, restarts lost local history and restarted numbering from 1.
3. **Absence of Persistent DB Sequence Recovery**: The session runner did not query the PostgreSQL audit repository at startup to discover the maximum global sequence number already recorded for the trading day.
4. **Missing Distinction Between Process and Session Lifecycle**: The system conflated the **Worker Process Lifecycle** (which can restart or cycle at any time) with the **Trading Session Lifecycle** (which spans the entire canonical trading day 00:00–23:59 IST).
5. **Lack of Provenance Distinction**: Data events did not strictly declare whether candles and ticks came from authentic live WebSocket streaming, historical REST seeding, or indicator bootstrap warmup.

## 4. Architecture Before
- **Experiment Model**: 1 experiment = 1 worker run. When the worker stopped, the session was marked finalized in PostgreSQL.
- **Sequencing**: A single integer `sequence_number` starting at 1 on every worker boot.
- **State Machine**: Rudimentary boolean flags (`running`, `session_active`).
- **Timestamps**: Events carried generic `timestamp` fields, occasionally substituting local server reception time for market time.
- **Provenance**: Informal strings or inferred provider flags. Historical warmup candles could be misattributed to live session activity counters.

## 5. Architecture After
- **Four-Tier Conceptual Hierarchy**:
  1. `experiment_id`: Canonical identifier for the trading day (`APEX-WORKER-YYYY-MM-DD`).
  2. `trading_day`: Date string (`YYYY-MM-DD`).
  3. `session_instance_id`: Globally unique session instance identifier (`SESS-{trading_day}-{uuid[:8]}`).
  4. `worker_instance_id`: Unique process identifier (`WRK-{pid}-{boot_timestamp}`).
- **Authoritative PostgreSQL Audit Recovery**:
  - Worker boot queries `get_last_sequence_numbers(experiment_id)` from PostgreSQL.
  - If a session already started today, `initialize_session()` enters **Session Recovery Mode**, resuming `global_sequence_number` monotonically without emitting a duplicate `SESSION_START`. Instead, it records a structured `WORKER_RECOVERY` audit event.
- **Conditional Shutdown & Safe Finalization**:
  - `SessionRunner.stop()` inspects `SessionLifecycleManager.can_finalize()`.
  - If stopped prior to 15:40 IST (e.g. midnight maintenance, premarket deployment), it logs a `WORKER_SHUTDOWN` event and leaves `session_finalized = False`.
  - Only after 15:40 IST and once regular market and F&O closing procedures are executed does it transition to `FINALIZED`.

## 6. Session State Machine
Managed by `SessionLifecycleManager` in `backend/app/live_paper/session_lifecycle.py`:

```
   [PREMARKET] (before 09:15 IST)
        │
        ▼ (09:15 IST trigger)
   [MARKET_OPEN] (09:15:00 - 09:15:59 IST)
        │
        ▼ (09:16:00 IST trigger)
   [REGULAR_MARKET] (09:16 - 15:30 IST) ──► Paper trades & signal evaluation active
        │
        ▼ (15:30 IST trigger)
   [EQUITY_CLOSE] (15:30 - 15:40 IST) ────► Intraday order entry blocked; squaring off
        │
        ▼ (15:40 IST trigger)
   [FNO_FINALIZATION] (15:40 IST) ────────► Settle F&O contracts, record close metrics
        │
        ▼
   [FINALIZED] (Terminal / Idempotent) ───► Terminal state; further ticks will not reopen
```

- **Forward-Only Transitions**: Cannot transition backwards (e.g. `REGULAR_MARKET` cannot return to `PREMARKET`).
- **Terminal Lock**: Once `FINALIZED`, the session remains locked. A worker remaining online after 15:40 IST cannot reopen the session.
- **Trading Day Guards**: `can_execute_paper_trades()` evaluates strictly to `True` only in `REGULAR_MARKET` (and conditionally in `MARKET_OPEN` if warmup is satisfied).

## 7. Event Sequencing Model
Events now maintain dual sequencing:
1. `sequence_number`: Local monotonically increasing counter within the current process instance.
2. `global_sequence_number`: Monotonically increasing sequence across the entire trading day (`experiment_id`), backed by PostgreSQL.
- Composite index `idx_audit_session_gseq` on `(experiment_id, global_sequence_number)`.
- Restarts fetch `MAX(global_sequence_number)` from DB and increment monotonically.
- Sequence resets are flagged as critical `SEQUENCE_RESET` anomalies.

## 8. Timestamp Model
Every market and analytical event distinguishes:
1. `market_timestamp`: Authentic timestamp extracted directly from the broker/exchange payload (Upstox feed).
2. `event_timestamp_utc`: ISO-8601 UTC timestamp when APEX recorded the event.
3. `event_timestamp_ist`: Human-readable Indian Standard Time (`UTC+05:30`) presentation timestamp.
4. `processing_timestamp_utc`: Processing epoch when the internal pipeline handled the event.
5. `processing_latency_ms`: Measured difference: `(processing_timestamp - market_timestamp) * 1000`.

*Invariants*:
- Market timestamps are NEVER fabricated or overwritten with system clock.
- Processing clock is never used as a proxy for market event time.

## 9. Provenance Model
Standardized enum `DataProvenance`:
- `AUTHENTIC_LIVE`: Live WebSocket tick received during active market hours.
- `AUTHENTIC_HISTORICAL`: Real historical bar fetched via broker REST API.
- `BOOTSTRAP_HISTORICAL`: Historical bar used solely to warm up technical indicators prior to trading.
- `REPLAY`: Deterministic simulation playback data.
- `PAPER_SIMULATED`: Generated internally by the paper-trading execution model.
- `DERIVED`: Computed analytical metrics (e.g. candle updates, regime classifiers).
- `UNKNOWN` / `NOT_VERIFIABLE`: Fallback for untraced payloads.

*Rules*:
- Bootstrap historical data is NEVER counted toward live tick counters or latency averages.
- Metrics expose separate `ticks_live` vs `ticks_historical` and `candles_live` vs `candles_historical`.

## 10. Restart & Recovery Behavior
1. Worker starts and calls `session_runner.initialize_session()`.
2. Queries `audit_repo.has_session_started(experiment_id)` and `get_last_sequence_numbers(experiment_id)`.
3. If past session exists:
   - Sets `self.global_sequence_number = max_db_sequence`.
   - Bypasses duplicate `SESSION_START`.
   - Records `WORKER_RECOVERY` audit event detailing `recovered_from_global_seq`, `session_instance_id`, and `worker_instance_id`.
   - Re-emits `UNIVERSE_SNAPSHOT` and continues market data aggregation seamlessly.

## 11. PostgreSQL Changes
- **Updated Models (`backend/app/database/models.py`)**:
  - `AuditEventModel`: Added `trading_day`, `session_instance_id`, `worker_instance_id`, `global_sequence_number`, `market_timestamp`, `processing_timestamp_utc`, `processing_latency_ms`, `provider`, `instrument_key`, `market_phase`. Added composite index `idx_audit_session_gseq`.
  - `SessionReportModel`: Added `session_instance_id`, `worker_instance_id`, `final_global_sequence`, `recovery_count`.
- **Database Connection & Migration (`backend/app/database/connection.py`)**:
  - Implemented dialect-agnostic idempotent column reflection and migration in `init_db()` for both SQLite and PostgreSQL engines, guaranteeing non-destructive upgrades.
- **Audit Repository (`backend/app/database/repositories/audit_repository.py`)**:
  - Added `get_last_sequence_numbers(experiment_id)`.
  - Added `has_session_started(experiment_id)`.
  - Added `get_session_recovery_state(experiment_id)`.
  - Persists all 10 new audit dimensions across single and batch inserts.

## 12. API Changes
- Endpoint `GET /api/session/status` updated to Phase 13 contract in both `backend/app/worker.py` and `backend/app/main.py`:
  ```json
  {
    "experiment_id": "APEX-WORKER-2026-09-15",
    "trading_day": "2026-09-15",
    "worker_instance_id": "WRK-1234-1773738000",
    "session_instance_id": "SESS-2026-09-15-a1b2c3d4",
    "worker_state": "RUNNING",
    "market_phase": "REGULAR_MARKET",
    "session_status": "ACTIVE",
    "is_market_open": true,
    "cloud_autonomous": true,
    "last_market_timestamp": "2026-09-15T10:30:00+05:30",
    "last_event_timestamp": "2026-09-15T05:00:00.123456Z",
    "last_global_sequence": 1420,
    "ticks_live": 1350,
    "ticks_historical": 0,
    "candles_live": 70,
    "candles_historical": 250,
    "evaluations": 12,
    "candidates": 4,
    "signals": 2,
    "paper_orders": 2,
    "recovery_count": 0
  }
  ```

## 13. Frontend Changes
- Verified `frontend/src/components/IndexTickerBar.tsx`:
  - Worker state indicator displays authentic backend status (`ONLINE` / `DEGRADED` / `OFFLINE`).
  - Market phase badge clearly distinguishes `PREMARKET`, `MARKET OPEN`, and `CLOSED`.
  - Data telemetry modal correctly presents live ticks and historical candle counts without fabricating live tags.
- Verified TypeScript compilation and bundle production (`npm run build` completed cleanly).

## 14. Tests Added
Located in:
1. `backend/tests/live_paper/test_session_lifecycle_hardening.py` (24 deterministic unit and integration tests):
   - `test_01_worker_starts_at_midnight`: Premarket state, no false finalization.
   - `test_02_worker_starts_at_0800_same_trading_day`: Identical experiment and trading day.
   - `test_03_worker_transition_premarket_to_market_open`: Clean clock-driven transition at 09:15.
   - `test_04_worker_starts_at_0916_regular_market`: Active trading phase initialized correctly.
   - `test_05_worker_restart_recovers_same_session`: Restarts recover sequence without duplicate session start.
   - `test_06_websocket_reconnect_preserves_session`: Socket disconnect does not terminate trading session.
   - `test_07_historical_rest_seed_provenance`: Bootstrap candles marked `BOOTSTRAP_HISTORICAL`.
   - `test_08_live_tick_marked_authentic_live`: Upstox ticks marked `AUTHENTIC_LIVE`.
   - `test_09_historical_timestamp_not_mislabeled_live`: Historical timestamps not conflated with live.
   - `test_10_global_sequence_survives_restart`: Global sequence monotonically continues across restarts.
   - `test_11_global_sequence_never_decreases`: Invariant verified against multi-batch writes.
   - `test_12_duplicate_event_insertion_idempotent`: Audit repo handles duplicate event IDs safely.
   - `test_13_duplicate_finalization_idempotent`: Multiple finalization calls are idempotent.
   - `test_14_equity_close_transition`: 15:30 IST halts new entries and transitions to `EQUITY_CLOSE`.
   - `test_15_fno_finalization`: 15:40 IST finalizes F&O and generates final reports.
   - `test_16_worker_alive_after_finalized_remains_finalized`: Terminal phase locked.
   - `test_17_timestamp_conversion_utc_ist`: Precise ISO UTC to IST offset calculation.
   - `test_18_market_timestamp_preserved`: Broker tick timestamp preserved verbatim.
   - `test_19_processing_latency_calculation`: Measured latency accurately calculated.
   - `test_20_session_status_endpoint`: Schema compliance for `/api/session/status`.
   - `test_21_postgres_transaction_rollback`: Sequence and DB consistency on transaction rollback.
   - `test_22_postgres_reconnect_recovery`: DB reconnect logic restores state safely.
   - `test_23_session_report_checksum_consistency`: SHA-256 payload checksums remain reproducible.
   - `test_24_live_order_allowed_remains_false`: Absolute safety verification (`LIVE_ORDER_ALLOWED == False`).
2. `backend/tests/live_paper/test_sept15_replay.py`:
   - Full forensic replay of the September 15 timeline proving the corrected lifecycle.

## 15. Test Results
- **Session Lifecycle & Replay Suite**: 25 passed, 0 failed in 3.36s.
- **Full Live Paper Suite**: 45 passed, 0 failed.
- **Full Quantitative Regression Suite**: 76 passed, 0 failed across signals, strategies, risk rules, and paper orders.
- **Frontend Build**: 0 errors, 0 warnings.

## 16. Production Verification
- Upstox WebSocket feed actively receiving and processing live market ticks.
- Cloud worker running autonomously on Render with continuous PostgreSQL audit persistence.
- Session status reporting authoritative `REGULAR_MARKET` / `RUNNING` status with monotonic event sequencing.

## 17. Remaining Limitations
- In the event of prolonged cloud host termination during active market hours, candles for the downtime period must be filled via historical REST backfill (already supported in `HistoricalDataService`).
- Special exchange trading sessions (e.g. Diwali Muhurat trading) require passing custom market-phase timetable overrides.

## 18. Explicit Safety Statement
> **"Live capital remains prohibited; this change improves research/audit correctness only."**
- `LIVE_ORDER_ALLOWED = False` remains strictly and permanently enforced in code and configuration.
- No live broker orders are transmitted under any circumstances.
