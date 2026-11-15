# Handoff Report: Milestone 3 (Feature 18 & Feature 19)

**Agent**: `explorer_m3_2`  
**Handoff Type**: Hard (Task Complete)  
**Target Milestone**: M3 — Requirement R3 (Side-Correct Automated Exits & Same-Bar Conservative Policy)  
**Detailed Report**: `C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md`

---

## 1. Observation

1. **Missing Methods in `PaperTradingEngine`**:
   - In `backend/app/paper_trading/engine.py` (lines 57–501), the class `PaperTradingEngine` defines `execute_order` (line 80), `update_market_price` (line 217), `close_position` (line 237), `get_portfolio_summary` (line 368), and DB persistence helpers.
   - Searching for `process_market_tick` and `evaluate_exits` across the entire backend (`grep_search` on `backend/app`) yielded **0 results**.
   - `update_market_price` (lines 217–227) only updates `pos["currentPrice"]` and unrealized P&L:
     ```python
     def update_market_price(self, symbol: str, current_price: float):
         if current_price <= 0:
             return
         for pos_id, pos in self.positions.items():
             if pos["symbol"] == symbol:
                 pos["currentPrice"] = current_price
                 diff = current_price - pos["entryPrice"] if pos["side"] == "BUY" else pos["entryPrice"] - current_price
                 pos["unrealizedPnL"] = round(diff * pos["quantity"], 2)
                 pos["unrealizedPnLPercent"] = round((diff / pos["entryPrice"]) * 100.0, 2) if pos["entryPrice"] > 0 else 0.0
     ```
     It does not evaluate `stopLoss` or `targetPrice`.

2. **Divergent Ad-Hoc Implementation in `session_runner.py`**:
   - In `backend/app/live_paper/session_runner.py` (lines 1183–1220), `_check_position_stops_and_targets` was implemented ad-hoc:
     ```python
     open_pos = self.paper_engine.get_position(symbol)
     ...
     if is_long:
         if stop_loss and current_price <= stop_loss:
             stop_hit = True
             exit_reason = "STOP_LOSS"
         elif target_price and current_price >= target_price:
             target_hit = True
             exit_reason = "TARGET_1"
     else:
         if stop_loss and current_price >= stop_loss:
             stop_hit = True
             exit_reason = "STOP_LOSS"
         elif target_price and current_price <= target_price:
             target_hit = True
             exit_reason = "TARGET_1"
     ```
   - This checks only single scalar `current_price`, queries only the first position for the symbol (`get_position(symbol)`), ignores high/low candle ranges, does not handle same-bar conflicts, and is bypassed by `main.py`.

3. **Margin Validation Gate Vulnerability in `execute_order`**:
   - In `backend/app/paper_trading/engine.py` line 134:
     ```python
     if is_buy and total_cash_needed > self.capital:
         canonical_order.transition_to(
             OrderState.REJECTED,
             reason=f"Insufficient margin. Required ₹{total_cash_needed:,.2f}, Available ₹{self.capital:,.2f}"
         )
     ```
     If `side == "SELL"` (SHORT order), `is_buy` is `False`, allowing un-margined short positions to execute regardless of capital.

4. **Missing Exit Reason in `close_position`**:
   - In `backend/app/paper_trading/engine.py` line 237:
     ```python
     def close_position(
         self,
         pos_id: str,
         close_price: Optional[float] = None,
         account_id: Optional[str] = None,
         close_quantity: Optional[int] = None,
     ) -> Dict[str, Any]:
     ```
     No `exit_reason` or `exit_type` parameter is supported, and `closed_record` (lines 284–302) does not store why the position closed.

5. **Placeholder E2E Tests in `backend/tests/e2e/test_tier1_features.py`**:
   - `test_f18_side_correct_automated_exits` (lines 502–518):
     Calls `clean_paper_engine.close_position(pos_id, close_price=1545.0)` manually. Does not test automated triggers or SHORT positions.
   - `test_f19_same_bar_conservative_policy` (lines 523–549):
     Defines an inline local function `def resolve_same_bar(...)` and does not call `clean_paper_engine` or `PaperTradingEngine`.

---

## 2. Logic Chain

1. **From Observation 1**: Because `PaperTradingEngine` lacks `process_market_tick` and `evaluate_exits`, the engine is unable to trigger automated exits when incoming market data breaches stop-loss or take-profit thresholds.
2. **From Observation 2**: Because `session_runner.py` implemented its own exit evaluation using only scalar `current_price`, it creates architectural divergence, fails to process high/low ranges from candles, and does not resolve same-bar conflicts.
3. **From Observation 3**: Because line 134 of `engine.py` filters on `is_buy and total_cash_needed > self.capital`, short selling is not margin-checked, exposing the ledger to unbounded short positions.
4. **From Observation 4**: Because `close_position` does not take or log `exit_reason`, audit records and journal entries cannot distinguish between manual close, stop-loss, and take-profit.
5. **From Observation 5**: Because the E2E tests for F18 and F19 use manual closes and inline functions, they currently pass trivially without verifying that the engine enforces side-correct automated exits or conservative same-bar resolution.
6. **Conclusion**: To fulfill Milestone 3 (Requirement R3), the Worker must implement `PaperExitEvent`, `evaluate_exits`, and `process_market_tick` on `PaperTradingEngine`, update `close_position` with `exit_reason`/`exit_type`, fix the short margin gate, integrate with `main.py`, and upgrade the test assertions in `test_tier1_features.py`.

---

## 3. Caveats

1. **Broker Live Routing**: Per R5, live broker routing remains permanently disabled (`LIVE_ORDER_ALLOWED = False`). All exits remain strictly in the paper ledger.
2. **Tick vs Bar Resolution**: When only `ltp` is provided (e.g. tick stream), `high = low = ltp`. Same-bar conflict can only occur when `high` and `low` span both thresholds, which occurs during candle updates or aggregated bars.
3. **Multi-Leg / Bracket Orders**: The current engine treats stop loss and take profit as attributes on the position (`pos["stopLoss"]`, `pos["targetPrice"]`), rather than standalone secondary orders in the order book. This is consistent with the current schema.

---

## 4. Conclusion

Features 18 and 19 require adding `process_market_tick` and `evaluate_exits` directly to `PaperTradingEngine` (`backend/app/paper_trading/engine.py`).
- For LONG: `low <= stop_loss` -> `EXIT_STOP`; `high >= target_price` -> `EXIT_TARGET`.
- For SHORT: `high >= stop_loss` -> `EXIT_STOP`; `low <= target_price` -> `EXIT_TARGET`.
- On Conflict (`stop` and `target` both hit in same bar): **STOP-LOSS takes absolute precedence**.
- On Gap: Fills execute at `open_price` (worse price) to reflect realistic slippage.
A full, step-by-step implementation blueprint and test plan is documented in `C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md`.

---

## 5. Verification Method

1. **Inspect Report**:
   Review `C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md` for complete code blueprints and edge case handling.
2. **Pre-Implementation Verification**:
   Inspect `backend/app/paper_trading/engine.py` lines 134, 217–237 to verify the missing methods and margin check bug.
   Inspect `backend/tests/e2e/test_tier1_features.py` lines 499–550 to verify the placeholder test implementations.
3. **Post-Implementation Verification Commands**:
   ```bash
   pytest backend/tests/e2e/test_tier1_features.py -k "f18 or f19" -v
   pytest backend/tests/e2e/test_tier3_combinations.py -v
   pytest backend/tests/e2e/test_tier4_scenarios.py -v
   pytest backend/tests/test_unified_paper_order.py -v
   ```
4. **Invalidation Condition**:
   If an incoming bar with `high >= take_profit` and `low <= stop_loss` produces an `EXIT_TARGET` event instead of `EXIT_STOP`, Feature 19 is invalidated.
   If a SHORT position with `high >= stop_loss` fails to exit, Feature 18 is invalidated.
