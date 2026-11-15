# Milestone 3 Exploration Report: Paper Engine Unification (F15) & Order Pre-Submission Validation (F16)

**Agent**: `explorer_m3_1`  
**Date**: 2026-10-07  
**Milestone**: Milestone 3 (Requirement R3: Authoritative Paper Execution, Exit Lifecycle, and Journaling)  
**Authoritative References**: `ORIGINAL_REQUEST.md`, `PROJECT.md`, `COMPLETE_AUDIT.md`, `backend/tests/e2e/test_tier1_features.py`

---

## 1. Executive Summary

This report delivers a comprehensive technical investigation of **Feature 15 (Paper Engine Unification)** and **Feature 16 (Order Pre-Submission Validation)** for Milestone 3.

### Core Discoveries
1. **Dual Disconnected Engines (V06 / F15)**:
   - `backend/app/paper_trading/engine.py` (`PaperTradingEngine`) acts as the server's transactional ledger for manual UI orders and worker background execution, connected to PostgreSQL/SQLite via `PaperRepository`.
   - `backend/app/paper_engine/bridge.py` (`PaperTradingBridge`) acts as an in-memory strategy evaluation bridge storing its own `positions: Dict[str, PaperPosition]`, `available_cash`, and `trade_audits: List[PaperTradeAudit]`, with zero database persistence.
   - **Severe divergence**: Orders placed via UI (`POST /api/paper/order`) never enter `PaperTradingBridge`, meaning `/api/paper/performance` and `/api/paper/audits` report zero or disconnected data. Strategy trades in `bridge` never appear in `paper_engine.positions` or the UI (`/api/paper/positions`).
2. **Order Pre-Submission Validation Gaps (F16)**:
   - `PaperTradingEngine.execute_order()` currently performs only rudimentary checks (`quantity <= 0`, `price <= 0`, and `margin_required > capital`).
   - It **does not revalidate**:
     - Signal `QUALIFIED` lifecycle state (accepts `CANDIDATE`, `REJECTED`, or `INVALIDATED` signals if passed).
     - Signal freshness and expiration timestamp (accepts expired signals).
     - Directional trade geometry bounds (accepts BUY orders where `stopLoss >= price` or `targetPrice <= price`).
     - Portfolio risk limits (max open positions, daily loss limit, concentration limits).
   - Although `/api/signals/{signal_id}/paper-trade` in `main.py:2476` implements partial signal checks, direct submissions via `POST /api/paper/order`, background worker executions, or programmatic orders completely bypass these critical checks.

---

## 2. Feature 15: Paper Engine Unification Deep Dive

### 2.1 Side-by-Side System Comparison

| Dimension | Engine A: `PaperTradingEngine` (`paper_trading/engine.py`) | Engine B: `PaperTradingBridge` (`paper_engine/bridge.py`) | Unification Target (Authoritative Single Engine) |
| :--- | :--- | :--- | :--- |
| **Primary Location** | `backend/app/paper_trading/engine.py` | `backend/app/paper_engine/bridge.py` | `backend/app/paper_trading/engine.py` |
| **Class Name** | `PaperTradingEngine` | `PaperTradingBridge` | `PaperTradingEngine` as core ledger; `PaperTradingBridge` as strategy adapter delegating to `PaperTradingEngine` |
| **State Storage** | `positions: Dict[str, Dict[str, Any]]` | `positions: Dict[str, PaperPosition]` | Authoritative dictionary in `PaperTradingEngine` backed by DB |
| **Capital Pool** | `self.capital: float` (default ₹1,000,000) | `self.available_cash: float` (default ₹1,000,000) | Unified `self.capital` in `PaperTradingEngine`; `bridge.available_cash` is a property aliasing `engine.capital` |
| **Statutory Frictions** | Full Indian Frictions (`calculate_indian_equity_frictions`) | Full Indian Frictions (`calculate_indian_equity_frictions`) | Shared model from `bridge.py:calculate_indian_equity_frictions` |
| **Order/Fill Models** | `CanonicalOrder`, `CanonicalFill` | Dataclasses (`PaperPosition`, `PaperSignal`) | `CanonicalOrder` / `CanonicalFill` + `PaperPosition` metadata bridge |
| **Audits / Journal** | `closed_trades: List[Dict]` (basic fields) | `trade_audits: List[PaperTradeAudit]` (rich evidence) | Unified `trade_audits: List[PaperTradeAudit]` & `closed_trades: List[Dict]` in `PaperTradingEngine` |
| **Database Sync** | Persistent via `PaperRepository` (`load_from_db`, `sync_order_to_db`, `sync_close_to_db`) | None (ephemeral in-memory only) | All state (manual + automated) persisted atomically to DB via `PaperRepository` |
| **API Endpoints** | `POST /api/paper/order`<br>`GET /api/paper/positions`<br>`POST /api/paper/close/{id}`<br>`POST /api/paper/reset` | `GET /api/paper/performance`<br>`GET /api/paper/audits`<br>`GET /api/paper/drift/{id}` | All endpoints read/write to the authoritative `PaperTradingEngine` |

### 2.2 Forensic Cache vs Backend Ledger Discrepancies
1. **Disconnected Execution & Performance**:
   - `main.py:1008`: In `GET /api/paper/positions`, `summary["performance"]` falls back to `paper_bridge.get_performance_summary()` only when `total_trades == 0`.
   - `main.py:1882`: `GET /api/paper/performance` directly calls `paper_bridge.get_performance_summary()`. As a result, closed trades from manual UI trading never register in performance analytics.
   - `main.py:1888`: `GET /api/paper/audits` returns `paper_bridge.trade_audits`, which remains empty when trades occur through `paper_engine`.
2. **Dual Capital Pools & Accounting Drift**:
   - `paper_engine.capital` and `paper_bridge.available_cash` are independent numbers. An order placed via `/api/paper/order` deducts capital from `paper_engine`, but `paper_bridge.available_cash` remains unaffected.
3. **Mark-to-Market & Automated Exits Asymmetry**:
   - In `main.py:78`, ticks update `paper_engine.update_market_price(tick.symbol, tick.ltp)`. However, `paper_engine.update_market_price` only computes unrealized PnL and **never evaluates stop-loss or take-profit triggers**.
   - `PaperTradingBridge.update_positions_mark_to_market` has exit evaluation logic, but it is **never connected to live websocket or worker ticks**.
4. **Worker vs Main Application Instance Fragmentation**:
   - `main.py` instantiates global `paper_engine = PaperTradingEngine()`.
   - `backend/app/worker.py` creates `MarketWorker`, which instantiates `LivePaperSessionRunner`, which creates its own `self.paper_engine = PaperTradingEngine()`.
   - Both sync to DB, but their in-memory caches diverge during live runtime.

---

## 3. Feature 16: Order Pre-Submission Validation Deep Dive

### 3.1 Existing Validation State
In `backend/app/paper_trading/engine.py:113-144`:
```python
# Current Engine Validation (Lines 113-120):
if canonical_order.quantity <= 0 or canonical_order.requested_price <= 0 or not canonical_order.symbol:
    canonical_order.transition_to(OrderState.REJECTED, reason="Invalid quantity, price, or symbol.")
    return {"status": "REJECTED", "order_id": order_id, "reason": canonical_order.rejection_reason}

# Current Margin Check (Lines 131-143):
margin_required = total_val * 0.20 if "MIS" in canonical_order.product_type else total_val
total_cash_needed = margin_required + frictions["total_fees"]
if is_buy and total_cash_needed > self.capital:
    canonical_order.transition_to(OrderState.REJECTED, reason=f"Insufficient margin...")
    return {"status": "REJECTED", "order_id": order_id, "reason": canonical_order.rejection_reason}
```

### 3.2 Five Critical Pre-Submission Validation Gaps

#### Gap 1: Signal Qualification Revalidation
- **Requirement**: If an order references a `signal_id`, it must verify that the signal is in `QUALIFIED` status. Submitting an expired, candidate, or invalidated signal must fail closed with an explicit rejection.
- **Current Defect**: `PaperTradingEngine.execute_order()` accepts `signal_id` in `PaperOrderRequest` without querying `apex_signal_store` or `SignalRepository` to verify qualification.

#### Gap 2: Signal Freshness and Expiration Timestamp
- **Requirement**: Expired signals must be rejected. The engine must check `signal.expiry` (handling ISO-8601 strings, UTC offsets, and epoch timestamps) against `datetime.now(timezone.utc)`.
- **Current Defect**: Bypassed unless submitted via `/api/signals/{id}/paper-trade`. Submitting via `/api/paper/order` executes regardless of age.

#### Gap 3: Directional Price Geometry Bounds
- **Requirement (Feature 13 / R2 Contract)**:
  - For `BUY` (LONG): `stopLoss < price < targetPrice` (stop below entry, targets above entry).
  - For `SELL` (SHORT): `targetPrice < price < stopLoss` (stop above entry, targets below entry).
- **Current Defect**: `PaperTradingEngine.execute_order()` allows any stopLoss or targetPrice without geometry verification.

#### Gap 4: Portfolio Risk Limits & Capacity Saturation
- **Requirement**: Hard portfolio risk checks before order acceptance:
  - Maximum open positions limit (e.g. 5 or 10 positions).
  - Capital allocation / concentration limit per symbol (e.g. max 25% of equity).
  - Daily loss limit (e.g. portfolio halt if daily loss exceeds -3%).
- **Current Defect**: Tested in `test_tier4_scenarios.py:test_s4_portfolio_capacity_saturation_stress` via `gate_portfolio_risk(portfolio_state, config)`, but **not integrated into `execute_order()`**.

#### Gap 5: Margin Requirements & Statutory Frictions
- **Requirement**: Genuine margin calculation with Indian statutory frictions buffer (`turnover * 0.20` for MIS, `turnover * 1.0` for CNC, F&O contract margin).
- **Current State**: Partially implemented for CNC/MIS, but missing F&O contract validation and preflight validation interface.

---

## 4. Recommended Architecture & Implementation Strategy

### 4.1 Feature 15 Unification Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      AUTHORITATIVE SERVER LEDGER                       │
│                     PaperTradingEngine (engine.py)                     │
│                                                                        │
│  - Unified Capital (self.capital)                                      │
│  - Unified Positions (self.positions: Dict[str, Dict])                 │
│  - Unified Closed Trades & Audits (self.closed_trades, trade_audits)   │
│  - Pre-Submission Validation Engine (validate_order_pre_submission)    │
│  - Mark-to-Market & Automated Exits (process_market_tick)              │
│  - Persistent Idempotency Cache (self.idempotency_cache)               │
│  - Database Persistence (PaperRepository load/sync)                    │
└──────────────────────────────────▲─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴────────────────────────┐
         │                                                  │
┌────────┴──────────────┐                         ┌────────┴─────────────┐
│  PaperTradingBridge   │                         │     FastAPI Routes   │
│     (bridge.py)       │                         │       (main.py)      │
│                       │                         │                      │
│ - Adapter layer       │                         │ - /api/paper/order   │
│ - Delegates next-bar  │                         │ - /api/paper/close   │
│   execution to Engine │                         │ - /api/paper/positions
│ - Wraps Engine state  │                         │ - /api/paper/audits  │
│ - Preserves Phase 8   │                         │ - /api/paper/perf    │
│   test signatures     │                         │ - /api/paper/drift   │
└───────────────────────┘                         └──────────────────────┘
```

#### Detailed Worker Implementation Steps for F15:
1. **Enhance `PaperTradingEngine` (`backend/app/paper_trading/engine.py`)**:
   - Add `self.trade_audits: List[PaperTradeAudit] = []` to `PaperTradingEngine.__init__`.
   - In `close_position(...)`: when creating `closed_record`, also construct a `PaperTradeAudit` instance (importing from `backend.app.paper_engine.models`) and append to `self.trade_audits`.
   - Add `get_trade_audits(self, strategy_id: Optional[str] = None) -> List[PaperTradeAudit]` to retrieve forensic audit records.
   - Export an authoritative singleton or factory getter: `get_paper_engine() -> PaperTradingEngine` or instantiate `paper_engine = PaperTradingEngine()`.
2. **Refactor `PaperTradingBridge` (`backend/app/paper_engine/bridge.py`)**:
   - Refactor `PaperTradingBridge` to accept an optional `engine: Optional[PaperTradingEngine] = None`. If omitted, default to the singleton `paper_engine`.
   - Implement `available_cash` as a property returning `self.engine.capital`.
   - Implement `positions` property delegating to `self.engine.positions` (or returning mapped `PaperPosition` instances).
   - In `execute_next_bar_entry(signal, next_bar_open, next_bar_timestamp, quantity, allocation_amount)`:
     - Convert `signal` into a `PaperOrderRequest` (using `signal.symbol`, `side=signal.side.value`, `price=next_bar_open`, `stopLoss=signal.stop_loss`, `targetPrice=signal.take_profit`, `signal_id=signal.signal_id`, `strategy_version=signal.strategy_version`).
     - Call `self.engine.execute_order(order_req)`.
     - Return the resulting position mapped to `PaperPosition`.
   - In `close_position(position_id, exit_price, exit_timestamp, exit_reason)`:
     - Delegate to `self.engine.close_position(...)` and return the created `PaperTradeAudit`.
   - In `get_performance_summary()`:
     - Delegate to `self.engine.get_performance_summary()`.
   - In `trade_audits`:
     - Return `self.engine.trade_audits`.
3. **Consolidate Endpoints in `backend/app/main.py`**:
   - Update `GET /api/paper/performance` to return `paper_engine.get_performance_summary()`.
   - Update `GET /api/paper/audits` to return `[asdict(a) for a in paper_engine.trade_audits]`.
   - In `GET /api/paper/positions`, remove the fallback check on `paper_bridge`; `paper_engine` provides the unified performance metrics directly.
   - Update `GET /api/paper/drift/{strategy_id}` to inspect `paper_engine.trade_audits`.

---

### 4.2 Feature 16 Pre-Submission Validation Architecture

#### Detailed Worker Implementation Steps for F16:
1. **Create Pre-Submission Validation Helper in `backend/app/paper_trading/engine.py`**:
   - Implement `validate_order_pre_submission`:
     ```python
     def validate_order_pre_submission(
         self,
         order_req: PaperOrderRequest,
         account_id: str = "primary_personal_account",
         max_positions: int = 10,
     ) -> Tuple[bool, Optional[str]]:
         """
         Validates order pre-submission invariants:
         1. Basic quantity, price, and symbol validity.
         2. Directional geometry (BUY: stopLoss < price < targetPrice; SELL: targetPrice < price < stopLoss).
         3. Signal qualification and freshness/expiry (if signal_id is present).
         4. Portfolio capacity limits (max open positions).
         5. Margin and available capital requirements.
         """
     ```
2. **Implement Step-by-Step Validation Checks**:
   - **Step 1: Basic Checks**:
     - Reject if `order_req.quantity <= 0`, `order_req.price <= 0`, or not `order_req.symbol`.
   - **Step 2: Directional Geometry Validation (Feature 13 / R2 Contract)**:
     - For `order_req.side.upper() == "BUY"`:
       - If `order_req.stopLoss` is set and `order_req.stopLoss >= order_req.price`:
         return `False, f"Invalid LONG trade geometry: stopLoss (₹{order_req.stopLoss}) must be below price (₹{order_req.price})"`
       - If `order_req.targetPrice` is set and `order_req.targetPrice <= order_req.price`:
         return `False, f"Invalid LONG trade geometry: targetPrice (₹{order_req.targetPrice}) must be above price (₹{order_req.price})"`
     - For `order_req.side.upper() == "SELL"`:
       - If `order_req.stopLoss` is set and `order_req.stopLoss <= order_req.price`:
         return `False, f"Invalid SHORT trade geometry: stopLoss (₹{order_req.stopLoss}) must be above price (₹{order_req.price})"`
       - If `order_req.targetPrice` is set and `order_req.targetPrice >= order_req.price`:
         return `False, f"Invalid SHORT trade geometry: targetPrice (₹{order_req.targetPrice}) must be below price (₹{order_req.price})"`
   - **Step 3: Signal Qualification & Freshness/Expiry Revalidation**:
     - If `order_req.signal_id`:
       - Lookup signal:
         ```python
         from backend.app.signal_engine.signal_store import apex_signal_store
         signal = apex_signal_store.get_signal_by_id(order_req.signal_id)
         ```
       - If signal found:
         - Verify state: `sig_state = getattr(signal.state, "value", signal.state)`. If `sig_state != "QUALIFIED"`:
           return `False, f"Cannot execute signal '{order_req.signal_id}': status is '{sig_state}', expected 'QUALIFIED'"`
         - Verify quality grade: if grade is `NO_TRADE` or `NO TRADE`:
           return `False, "Cannot execute signal with quality grade NO_TRADE"`
         - Verify expiry: parse `signal.expiry`. If `datetime.now(timezone.utc) > expiry_dt`:
           signal.state = "EXPIRED"
           return `False, "Invalid or expired signal timestamp"`
   - **Step 4: Portfolio Risk Limits**:
     - Check open positions count: if `len(self.positions) >= max_positions` and `order_req.symbol not in [p['symbol'] for p in self.positions.values()]`:
       return `False, f"Maximum open positions ({len(self.positions)}) reached (limit {max_positions})"`
   - **Step 5: Margin & Cash Check**:
     - Compute total cash needed including statutory friction fees.
     - If `total_cash_needed > self.capital`:
       return `False, f"Insufficient margin. Required ₹{total_cash_needed:,.2f}, Available ₹{self.capital:,.2f}"`
3. **Integrate into `execute_order`**:
   - Run `valid, reason = self.validate_order_pre_submission(order_req, account_id)` immediately after order creation.
   - If `not valid`:
     - Transition order to `OrderState.REJECTED` with reason.
     - Return `{"status": "REJECTED", "order_id": order_id, "reason": reason}`.
4. **Expose Dedicated Pre-submission Endpoint in `main.py`**:
   - Add `POST /api/paper/validate-order` allowing frontend pre-flight validation before submission.

---

## 5. Interface Contracts & Code Locations for Worker Implementation

### 5.1 Files to Modify

| Target File | Changes Required | Rationale |
| :--- | :--- | :--- |
| `backend/app/paper_trading/engine.py` | 1. Add `trade_audits: List[PaperTradeAudit]` to `PaperTradingEngine`<br>2. Add `validate_order_pre_submission(...)`<br>3. Integrate pre-submission validation in `execute_order`<br>4. Generate `PaperTradeAudit` in `close_position`<br>5. Add `get_trade_audits()` method | Unifies authoritative ledger and implements pre-submission validation |
| `backend/app/paper_engine/bridge.py` | 1. Update `PaperTradingBridge` to accept optional `engine: Optional[PaperTradingEngine]`<br>2. Delegate `available_cash`, `positions`, `trade_audits`, `get_performance_summary()` to `engine`<br>3. Delegate `execute_next_bar_entry` and `close_position` to `engine` | Consolidates bridge with engine while maintaining 100% Phase 8 test compatibility |
| `backend/app/main.py` | 1. Route `/api/paper/performance` and `/api/paper/audits` to unified `paper_engine`<br>2. In `POST /api/paper/order`, return explicit HTTP 400 when rejected if requested, or return `{"status": "REJECTED", ...}` as expected by contract<br>3. Add `POST /api/paper/validate-order` endpoint | Eliminates route shadowing and exposes pre-submission validation |
| `backend/app/paper_trading/canonical_order.py` | Verify `VALID_ORDER_TRANSITIONS` supports `CREATED -> VALIDATED -> REJECTED` | Ensures clean state machine handling for invalid orders |

---

## 6. Verification Method

To verify the implementation independently once Worker finishes:
1. **Tier 1 Feature Tests (F15 & F16)**:
   ```powershell
   pytest backend/tests/e2e/test_tier1_features.py -k "test_f15 or test_f16" -v
   ```
2. **Tier 2 Boundary Tests (Order & Margin Limits)**:
   ```powershell
   pytest backend/tests/e2e/test_tier2_boundaries.py -k "quantity or price or capital or saturation" -v
   ```
3. **Paper Bridge Unit Tests (Phase 8 Compatibility)**:
   ```powershell
   pytest backend/tests/test_paper_bridge.py -v
   ```
4. **Security Hardening Signal Execution Tests**:
   ```powershell
   pytest backend/tests/test_security_hardening.py -k "signal_paper_trade" -v
   ```
5. **Unified Paper Order Lifecycle Tests**:
   ```powershell
   pytest backend/tests/test_unified_paper_order.py -v
   ```
