# Handoff Report: Milestone 3 Exploration (F15 & F16)

**Agent**: `explorer_m3_1`  
**Milestone**: Milestone 3 (Requirement R3)  
**Topic**: Feature 15 (Paper Engine Unification) & Feature 16 (Order Pre-Submission Validation)  
**Date**: 2026-10-07  

---

## 1. Observation

1. **Dual Independent Paper Engines Identified**:
   - `backend/app/paper_trading/engine.py:57-75`:
     ```python
     class PaperTradingEngine:
         def __init__(self, initial_capital: float = 1000000.0, brokerage: float = 20.0, slippage_pct: float = 0.05):
             self.initial_capital = initial_capital
             self.capital = initial_capital
             self.positions: Dict[str, Dict[str, Any]] = {}
             self.closed_trades: List[Dict[str, Any]] = []
             self.idempotency_cache: Dict[str, Dict[str, Any]] = {}
     ```
   - `backend/app/paper_engine/bridge.py:73-84`:
     ```python
     class PaperTradingBridge:
         def __init__(self, initial_capital: float = 1000000.0):
             self.initial_capital = initial_capital
             self.available_cash = initial_capital
             self.positions: Dict[str, PaperPosition] = {}
             self.trade_audits: List[PaperTradeAudit] = []
             self.signals_history: List[PaperSignal] = []
     ```
   - `backend/app/main.py:64` and `main.py:1870`:
     - Line 64: `paper_engine = PaperTradingEngine(initial_capital=settings.default_paper_capital)`
     - Line 1870: `from backend.app.paper_engine.bridge import paper_bridge`

2. **Route Fragmentation and Shadowing in `backend/app/main.py`**:
   - Line 984: `POST /api/paper/order` executes solely on `paper_engine.execute_order(order, ...)`.
   - Line 994: `GET /api/paper/positions` queries `paper_engine.get_portfolio_summary()`, with fallback `summary["performance"] = paper_bridge.get_performance_summary()` only if `total_trades == 0`.
   - Line 1879: `GET /api/paper/performance` queries `paper_bridge.get_performance_summary()`.
   - Line 1885: `GET /api/paper/audits` queries `paper_bridge.trade_audits`.
   - Line 1917: `GET /api/paper/drift/{strategy_id}` filters `paper_bridge.trade_audits`.

3. **Current Pre-Submission Validation Deficits in `PaperTradingEngine.execute_order`**:
   - `backend/app/paper_trading/engine.py:113-144`:
     - Only checks `canonical_order.quantity <= 0 or canonical_order.requested_price <= 0 or not canonical_order.symbol`.
     - Only checks `is_buy and total_cash_needed > self.capital`.
     - Zero validation of `order_req.signal_id` qualification or expiration.
     - Zero validation of trade geometry (`stopLoss` vs `price` vs `targetPrice`).
     - Zero validation of portfolio capacity (`max_positions` or daily loss limit).

4. **Existing Pre-Submission Reference Pattern in `main.py:2476-2570`**:
   - `/api/signals/{signal_id}/paper-trade` demonstrates required checks:
     - State: `sig_state != "QUALIFIED"` raises 400.
     - Grade: `q_grade in ("NO TRADE", "NO_TRADE")` raises 400.
     - Expiry: `datetime.now(timezone.utc) > expiry_dt` marks `signal.state = "EXPIRED"` and raises 400.
     - Directional geometry: `LONG and stop_price >= signal.entry` or `SHORT and stop_price <= signal.entry` raises 400.
   - However, this logic lives exclusively in the signal endpoint and is completely absent from `PaperTradingEngine.execute_order()` and `/api/paper/order`.

5. **Test Assertions in `backend/tests/e2e/test_tier1_features.py`**:
   - `test_f15_paper_engine_unification:431-450`:
     - Requires single authoritative engine tracking orders, positions, MTM, and cash balance.
   - `test_f16_order_pre_submission_validation:454-469`:
     - Requires zero quantity rejection, negative price rejection, and exceeding capital rejection at engine level.

---

## 2. Logic Chain

1. From **Observation 1 & 2**, `PaperTradingEngine` and `PaperTradingBridge` are completely decoupled with independent in-memory state dicts (`positions`), independent capital counters (`capital` vs `available_cash`), and partitioned endpoints. Trades placed via `/api/paper/order` never update `paper_bridge.trade_audits`, causing `/api/paper/performance` and `/api/paper/audits` to report disconnected metrics.
2. From **Observation 3**, `PaperTradingEngine.execute_order()` only validates price > 0, quantity > 0, and available capital. It permits execution of unvalidated trade geometries (e.g., BUY orders with stop-loss higher than entry price), ignores signal lifecycle states (`CANDIDATE`, `REJECTED`, `EXPIRED`), and does not enforce portfolio saturation gates.
3. From **Observation 4**, the validation rules already exist in `/api/signals/{signal_id}/paper-trade` in `main.py`, but are not accessible when executing orders through `PaperTradingEngine.execute_order()`, creating a security and integrity vulnerability.
4. Unifying `PaperTradingBridge` to act as an adapter that delegates directly to `PaperTradingEngine` resolves the state bifurcation while preserving compatibility with `test_paper_bridge.py`.
5. Moving the pre-submission validation logic into a dedicated method `validate_order_pre_submission()` on `PaperTradingEngine` guarantees that all order submission pathways (API routes, session runners, and test harnesses) uniformly enforce signal qualification, expiry, directional geometry, and portfolio risk gates.

---

## 3. Caveats

1. **Derivative F&O Contract Parameters**: Contract lot sizing and margin models for Indian F&O (Feature 10) must be respected when orders originate from options/futures engines. The pre-submission validator should fail closed if required margin cannot be deterministically computed.
2. **Idempotency Durability (Feature 17)**: While in-memory idempotency caching exists (`self.idempotency_cache`), database persistence of idempotency keys (`IdempotencyKeyModel`) belongs to Feature 17 and will complement the pre-submission validation engine.
3. **Automated Exits on Tick Stream (Feature 18)**: `update_market_price()` currently only updates P&L. Integrating automated exit evaluation (Feature 18) will build directly on the unified positions ledger established in Feature 15.

---

## 4. Conclusion

- **Feature 15**: Consolidate `PaperTradingEngine` as the single authoritative server ledger. Refactor `PaperTradingBridge` to wrap and delegate all operations (`available_cash`, `positions`, `trade_audits`, `execute_next_bar_entry`, `close_position`) to `PaperTradingEngine`. Point all FastAPI endpoints (`/api/paper/performance`, `/api/paper/audits`) to `paper_engine`.
- **Feature 16**: Implement `validate_order_pre_submission()` inside `PaperTradingEngine` to enforce a 5-tier check sequence: (1) Basic parameter validity, (2) Directional geometry bounds (LONG/SHORT), (3) Signal qualification & freshness/expiry timestamp, (4) Portfolio capacity (max positions), and (5) Statutory margin + fees. Integrate this check directly into `PaperTradingEngine.execute_order()`.

---

## 5. Verification Method

Once Worker implements these features, execute the following test commands to independently verify:

1. **Feature 15 & 16 Coverage**:
   ```powershell
   pytest backend/tests/e2e/test_tier1_features.py -k "test_f15 or test_f16" -v
   ```
2. **Boundary & Saturation Tests**:
   ```powershell
   pytest backend/tests/e2e/test_tier2_boundaries.py -k "test_t2_zero_and_negative or test_t2_capital_exhaustion" -v
   pytest backend/tests/e2e/test_tier4_scenarios.py -k "test_s4_portfolio_capacity_saturation_stress" -v
   ```
3. **Paper Bridge Unit Test Suite**:
   ```powershell
   pytest backend/tests/test_paper_bridge.py -v
   ```
4. **Security Hardening Signal Pre-Validation**:
   ```powershell
   pytest backend/tests/test_security_hardening.py -k "test_signal_paper_trade" -v
   ```
5. **Inspection Files**:
   - `backend/app/paper_trading/engine.py`
   - `backend/app/paper_engine/bridge.py`
   - `backend/app/main.py`
