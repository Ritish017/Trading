# Milestone 3 Technical Investigation Report: Feature 18 & Feature 19

**Agent**: `explorer_m3_2`  
**Milestone**: M3 — Paper Execution & Exit Lifecycle (Requirement R3)  
**Target Features**: 
- **Feature 18**: Side-Correct Automated Exits (Long & Short Take-Profit / Stop-Loss)
- **Feature 19**: Same-Bar Conservative Resolution Policy (Stop-Loss Priority on Conflict)

---

## 1. Executive Summary

This investigation delivers a rigorous technical audit of the automated exit evaluation mechanics, order lifecycle, portfolio tracking, and E2E test harness for the APEX trading workstation.

### Key Discoveries:
1. **Critical Gap in Authoritative Engine**: `PaperTradingEngine` (`backend/app/paper_trading/engine.py`) currently possesses **no automated exit evaluation logic**. It only has `update_market_price(symbol, current_price)` (which updates mark-to-market prices and unrealized P&L without checking stops or targets) and manual `close_position(...)`. The interface contract methods `process_market_tick` and `evaluate_exits` specified in `PROJECT.md` are **completely absent**.
2. **Ad-Hoc / Divergent Logic in `session_runner.py`**: A partial stop/target check exists only in `backend/app/live_paper/session_runner.py` (`_check_position_stops_and_targets`). However, it only evaluates a single scalar `current_price` (LTP) against the first position found, ignores high/low bar ranges, completely lacks same-bar conflict resolution, and violates the single authoritative server ledger architecture required by R3 and Feature 15.
3. **E2E Test Suites Contain Placeholders**: 
   - `test_f18_side_correct_automated_exits` in `backend/tests/e2e/test_tier1_features.py` merely places a LONG order and manually invokes `clean_paper_engine.close_position(...)`. It tests neither automated exit triggering nor SHORT position logic.
   - `test_f19_same_bar_conservative_policy` evaluates a trivial, isolated inline Python function `def resolve_same_bar(...)` and does not interact with `PaperTradingEngine` at all.
4. **Margin Check Vulnerability for Short Orders**: In `PaperTradingEngine.execute_order` line 134, the margin gate is written as `if is_buy and total_cash_needed > self.capital:`. This inadvertently bypasses margin validation for `SELL` (SHORT) orders, permitting un-margined short positions.
5. **Missing Exit Metadata in Trade Ledgers**: `PaperTradingEngine.close_position(...)` does not accept or record `exit_reason` (e.g. `STOP_LOSS`, `TAKE_PROFIT`) or `exit_type` in `closed_record`, meaning historical trade records lose the forensic context of why an exit occurred.

---

## 2. Architecture & Code Layout Audit

The prompt refers to `backend/app/paper_trading/engine.py`, `orders.py`, and `portfolio.py`. Code inspection reveals that order and portfolio management are consolidated into the following modules:

```
backend/app/
├── paper_trading/
│   ├── canonical_order.py        # CanonicalOrder, CanonicalFill, OrderState state machine
│   └── engine.py                 # PaperTradingEngine: Unified authoritative ledger, MTM, orders, portfolio
├── database/
│   ├── models.py                 # PaperPositionModel, PaperOrderModel, PaperClosedTradeModel
│   └── repositories/
│       └── paper_repository.py  # Atomic persistence (ACID execution & closure)
├── live_paper/
│   └── session_runner.py         # Live market runner with ad-hoc tick handling
└── main.py                       # FastAPI entrypoints and on_normalized_tick_received callback
```

### Module Responsibilities:
- **`canonical_order.py`**: Defines strict state progression `CREATED -> VALIDATED -> ACCEPTED -> FILLED` and statutory Indian friction models (`calculate_indian_equity_frictions`).
- **`engine.py`**: Holds in-memory portfolio state (`self.positions`, `self.closed_trades`, `self.capital`, `self.idempotency_cache`). Exposes `execute_order`, `update_market_price`, `close_position`, `get_portfolio_summary`, and database synchronization methods.
- **`main.py`**: Receives live websocket ticks via `on_normalized_tick_received(tick: NormalizedTick)` and invokes `paper_engine.update_market_price(tick.symbol, tick.ltp)`. Currently, it performs zero automated exit evaluation.

---

## 3. Deep Dive: Feature 18 (Side-Correct Automated Exits)

### 3.1 Mathematical & Directional Invariants

In an exchange market, the boundary triggers for automated exits differ fundamentally between long and short positions:

```
LONG Position (Side: BUY)
=========================
  Target Price (TP)  ────> Triggered if Bar High >= TP (Profit)
       ▲
  Entry Price        ────> Reference price
       ▼
  Stop Loss (SL)     ────> Triggered if Bar Low <= SL  (Loss)


SHORT Position (Side: SELL)
===========================
  Stop Loss (SL)     ────> Triggered if Bar High >= SL (Loss)
       ▲
  Entry Price        ────> Reference price
       ▼
  Target Price (TP)  ────> Triggered if Bar Low <= TP  (Profit)
```

### 3.2 Evaluation Logic per Market Update

When processing a price update for an instrument with range `[low, high]` (or tick `ltp` where `high = low = ltp`):

#### 1. LONG Position (`pos["side"] == "BUY"`)
- **Stop-Loss Breach**: `pos["stopLoss"] is not None and low <= pos["stopLoss"]`
  - Trigger: Stop threshold breached.
  - Exit Type: `EXIT_STOP` (or `STOP_LOSS`).
  - Fill Realism (Gap Defense):
    - If `open_price <= pos["stopLoss"]`: Market gapped down below stop price. Execute fill at `open_price` (conservative slippage penalty).
    - Else: Execute fill at `pos["stopLoss"]`.
- **Take-Profit Breach**: `pos["targetPrice"] is not None and high >= pos["targetPrice"]`
  - Trigger: Profit target reached.
  - Exit Type: `EXIT_TARGET` (or `TAKE_PROFIT`).
  - Fill Realism (Gap Defense):
    - If `open_price >= pos["targetPrice"]`: Market gapped up above target. Execute fill at `open_price`.
    - Else: Execute fill at `pos["targetPrice"]`.

#### 2. SHORT Position (`pos["side"] == "SELL"`)
- **Stop-Loss Breach**: `pos["stopLoss"] is not None and high >= pos["stopLoss"]`
  - Trigger: Upward price spike breaches short stop.
  - Exit Type: `EXIT_STOP` (or `STOP_LOSS`).
  - Fill Realism (Gap Defense):
    - If `open_price >= pos["stopLoss"]`: Market gapped up above short stop. Execute fill at `open_price` (conservative slippage penalty).
    - Else: Execute fill at `pos["stopLoss"]`.
- **Take-Profit Breach**: `pos["targetPrice"] is not None and low <= pos["targetPrice"]`
  - Trigger: Downward price decline reaches profit target.
  - Exit Type: `EXIT_TARGET` (or `TAKE_PROFIT`).
  - Fill Realism (Gap Defense):
    - If `open_price <= pos["targetPrice"]`: Market gapped down below target. Execute fill at `open_price`.
    - Else: Execute fill at `pos["targetPrice"]`.

---

## 4. Deep Dive: Feature 19 (Same-Bar Conservative Resolution Policy)

### 4.1 The Same-Bar Conflict Dilemma

During any discrete observation window (a 1-minute, 5-minute, or daily OHLC candle, or high-volatility tick batch), the price span may expand sufficiently to cross **both** the Stop-Loss and Take-Profit boundaries:
- For LONG: `low <= stop_loss` **AND** `high >= take_profit`.
- For SHORT: `high >= stop_loss` **AND** `low <= take_profit`.

Without nanosecond-level intra-bar trade prints, it is impossible to know deterministically whether the price reached the target first or collapsed to the stop first.

### 4.2 The Conservative Precedence Principle

In quantitative trading research and professional risk management, the **conservative resolution policy** dictates:
> **When both Stop-Loss and Take-Profit thresholds are breached within the same bar, STOP-LOSS TAKES ABSOLUTE PRECEDENCE.**

#### Rationale:
1. **Anti-Overfitting & Survivorship Bias**: Assuming the target was hit first injects optimistic lookahead bias into paper portfolios and forward validation.
2. **Capital Preservation**: In real markets with high volatility, adverse spikes often trigger stops before liquidity rebounds to targets.
3. **Deterministic Predictability**: Guarantees worst-case, realistic equity curves under stress testing.

### 4.3 Conflict Handling Mechanics

```python
is_same_bar_conflict = (stop_breached and target_breached)

if is_same_bar_conflict:
    # Conservative Policy: Stop-Loss overrides Take-Profit
    exit_type = "EXIT_STOP"
    exit_reason = "STOP_LOSS"
    # Tag audit metadata
    conflict_flag = True
    # Fill price follows stop-loss rules (including gap defense)
    execution_price = open_price if is_gap_past_stop else stop_loss
```

---

## 5. Test Suite Audit (`test_tier1_features.py` & Related)

### 5.1 Current Deficiencies in `backend/tests/e2e/test_tier1_features.py`

#### Feature 18 (`test_f18_side_correct_automated_exits` lines 499–518):
```python
def test_f18_side_correct_automated_exits(clean_paper_engine: PaperTradingEngine):
    """F18: Automated exits trigger correctly for LONG (low <= SL) and SHORT (high >= SL)."""
    # 1. LONG Position Stop-Loss Exit
    long_order = PaperOrderRequest(
        symbol="HDFCBANK.NS",
        side="BUY",
        quantity=20,
        price=1600.0,
        stopLoss=1550.0,
        targetPrice=1700.0,
    )
    res_long = clean_paper_engine.execute_order(long_order)
    pos_id = res_long["position"]["id"]

    # Price drops to 1540 (crosses stop of 1550)
    res_exit = clean_paper_engine.close_position(pos_id, close_price=1545.0)
    assert res_exit["status"] == "CLOSED"
    assert res_exit["trade"]["realizedPnL"] < 0
    assert pos_id not in clean_paper_engine.positions
```
- **Flaws**:
  1. Does not call `process_market_tick` or any automated trigger. It calls `close_position(...)` manually.
  2. Does not test automated take-profit.
  3. Does not test SHORT stop-loss or SHORT take-profit.

#### Feature 19 (`test_f19_same_bar_conservative_policy` lines 523–549):
```python
def test_f19_same_bar_conservative_policy():
    """F19: When bar high >= target AND bar low <= stop, stop loss takes conservative precedence."""
    bar_high = 2600.0
    bar_low = 2400.0
    pos_entry = 2500.0
    pos_sl = 2450.0
    pos_tp = 2550.0

    target_crossed = bar_high >= pos_tp
    stop_crossed = bar_low <= pos_sl

    assert target_crossed is True
    assert stop_crossed is True

    def resolve_same_bar(target_hit: bool, stop_hit: bool) -> str:
        if stop_hit and target_hit:
            return "STOP_LOSS"
        if stop_hit:
            return "STOP_LOSS"
        if target_hit:
            return "TARGET"
        return "NONE"

    assert resolve_same_bar(target_crossed, stop_crossed) == "STOP_LOSS"
```
- **Flaws**:
  1. Tests an inline function `resolve_same_bar` defined inside the test body.
  2. Never touches `PaperTradingEngine`. The engine has no knowledge of this policy.

### 5.2 Analysis of `test_tier3_combinations.py` & `test_tier4_scenarios.py`

- In `test_tier3_combinations.py` (line 95), Step 5 manually calls `clean_paper_engine.close_position(pos_id, close_price=3005.0)`.
- In `test_tier4_scenarios.py` (lines 92, 97, 139), tests simulate automated exits and gap-down exits by manually passing calculated exit prices to `close_position(...)`.
- **Conclusion**: Adding `process_market_tick` and updating `close_position` with backward-compatible defaults will **not break any existing Tier 2, 3, or 4 tests**, while enabling genuine automated execution testing.

---

## 6. Concrete Implementation Blueprint for Worker

The Worker agent should implement the following changes:

### Step 1: Define `PaperExitEvent` Model in `engine.py`

```python
class PaperExitType(str, Enum):
    EXIT_STOP = "EXIT_STOP"
    EXIT_TARGET = "EXIT_TARGET"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    STRATEGY_INVALIDATION = "STRATEGY_INVALIDATION"
    TIME_EXPIRY = "TIME_EXPIRY"


class PaperExitEvent(BaseModel):
    pos_id: str
    order_id: Optional[str] = None
    account_id: str = "primary_personal_account"
    symbol: str
    side: str  # "BUY" or "SELL"
    exit_type: str  # "EXIT_STOP" or "EXIT_TARGET"
    exit_reason: str  # "STOP_LOSS", "TAKE_PROFIT"
    trigger_price: float
    exit_price: float
    effective_exit_price: float
    quantity: int
    gross_pnl: float
    realized_pnl: float
    same_bar_conflict: bool = False
    timestamp: float = Field(default_factory=time.time)
    trade: Dict[str, Any]
```

### Step 2: Implement `evaluate_exits` and `process_market_tick` in `PaperTradingEngine`

```python
    def process_market_tick(
        self,
        symbol: str,
        ltp: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        open_price: Optional[float] = None,
        timestamp: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> List[PaperExitEvent]:
        """
        Processes market tick or candle update for symbol:
        1. Validates tick prices.
        2. Updates mark-to-market prices & unrealized P&L.
        3. Evaluates side-correct automated exits (SL/TP) with same-bar conservative resolution.
        """
        if ltp <= 0:
            return []

        # Update MTM first
        self.update_market_price(symbol, ltp)

        # Normalize bar ranges
        eff_high = high if (high is not None and high > 0) else ltp
        eff_low = low if (low is not None and low > 0) else ltp
        if eff_high < eff_low:
            eff_high, eff_low = eff_low, eff_high
        eff_open = open_price if (open_price is not None and open_price > 0) else ltp

        return self.evaluate_exits(
            symbol=symbol,
            high=eff_high,
            low=eff_low,
            open_price=eff_open,
            ltp=ltp,
            timestamp=timestamp,
            account_id=account_id,
        )

    def evaluate_exits(
        self,
        symbol: str,
        high: float,
        low: float,
        open_price: Optional[float] = None,
        ltp: Optional[float] = None,
        timestamp: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> List[PaperExitEvent]:
        """
        Evaluates open positions on symbol against bar range [low, high].
        Enforces:
        - LONG: low <= SL -> EXIT_STOP; high >= TP -> EXIT_TARGET
        - SHORT: high >= SL -> EXIT_STOP; low <= TP -> EXIT_TARGET
        - Same-Bar Conflict: Stop-Loss takes absolute precedence.
        - Conservative Gap Defense: Fills at open_price if bar opened past stop level.
        """
        exit_events: List[PaperExitEvent] = []
        eff_open = open_price or ltp or high

        # Safe iteration over snapshot of positions
        for pos_id, pos in list(self.positions.items()):
            if pos.get("symbol") != symbol:
                continue
            if account_id and pos.get("account_id") != account_id:
                continue

            side = pos.get("side", "BUY").upper()
            is_long = (side == "BUY")
            sl = pos.get("stopLoss")
            tp = pos.get("targetPrice")

            stop_triggered = False
            target_triggered = False

            if is_long:
                if sl is not None and sl > 0 and low <= sl:
                    stop_triggered = True
                if tp is not None and tp > 0 and high >= tp:
                    target_triggered = True
            else:  # SHORT
                if sl is not None and sl > 0 and high >= sl:
                    stop_triggered = True
                if tp is not None and tp > 0 and low <= tp:
                    target_triggered = True

            if not (stop_triggered or target_triggered):
                continue

            # Same-Bar Conflict Resolution (Feature 19)
            same_bar_conflict = (stop_triggered and target_triggered)

            if same_bar_conflict or stop_triggered:
                exit_type = "EXIT_STOP"
                exit_reason = "STOP_LOSS"
                trigger_price = sl

                # Conservative Gap Defense
                if is_long:
                    # Gapped down below stop
                    exec_price = eff_open if (eff_open <= sl) else sl
                else:
                    # Gapped up above stop
                    exec_price = eff_open if (eff_open >= sl) else sl
            else:
                exit_type = "EXIT_TARGET"
                exit_reason = "TAKE_PROFIT"
                trigger_price = tp

                # Gap favorable fill
                if is_long:
                    exec_price = eff_open if (eff_open >= tp) else tp
                else:
                    exec_price = eff_open if (eff_open <= tp) else tp

            # Close position through authoritative close_position
            close_res = self.close_position(
                pos_id=pos_id,
                close_price=exec_price,
                account_id=pos.get("account_id"),
                exit_reason=exit_reason,
                exit_type=exit_type,
            )

            if close_res.get("status") in ["CLOSED", "PARTIALLY_CLOSED"]:
                trade = close_res.get("trade", {})
                trade["same_bar_conflict"] = same_bar_conflict
                event = PaperExitEvent(
                    pos_id=pos_id,
                    order_id=pos.get("order_id"),
                    account_id=pos.get("account_id", "primary_personal_account"),
                    symbol=symbol,
                    side=side,
                    exit_type=exit_type,
                    exit_reason=exit_reason,
                    trigger_price=trigger_price,
                    exit_price=exec_price,
                    effective_exit_price=trade.get("exitPrice", exec_price),
                    quantity=trade.get("quantity", pos.get("quantity", 0)),
                    gross_pnl=trade.get("grossPnL", 0.0),
                    realized_pnl=trade.get("realizedPnL", 0.0),
                    same_bar_conflict=same_bar_conflict,
                    timestamp=timestamp or time.time(),
                    trade=trade,
                )
                exit_events.append(event)

        return exit_events
```

### Step 3: Enhance `close_position` to Record Exit Metadata

Update `close_position` in `engine.py`:
```python
    def close_position(
        self,
        pos_id: str,
        close_price: Optional[float] = None,
        account_id: Optional[str] = None,
        close_quantity: Optional[int] = None,
        exit_reason: str = "MANUAL_CLOSE",
        exit_type: Optional[str] = None,
    ) -> Dict[str, Any]:
```
And populate in `closed_record`:
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
            "exit_reason": exit_reason,
            "exit_type": exit_type or ("EXIT_STOP" if exit_reason == "STOP_LOSS" else "EXIT_TARGET" if exit_reason == "TAKE_PROFIT" else "MANUAL"),
            "timestamp": pos.get("timestamp", time.time()),
            "closedAt": time.time(),
        }
```

### Step 4: Fix Short Order Margin Bug in `execute_order`

In `PaperTradingEngine.execute_order` line 134:
**Current**:
```python
if is_buy and total_cash_needed > self.capital:
    ...
```
**Fix**:
```python
if total_cash_needed > self.capital:
    canonical_order.transition_to(
        OrderState.REJECTED,
        reason=f"Insufficient margin. Required ₹{total_cash_needed:,.2f}, Available ₹{self.capital:,.2f}"
    )
    return {
        "status": "REJECTED",
        "order_id": order_id,
        "reason": canonical_order.rejection_reason,
    }
```

### Step 5: Wire into `main.py` Tick Pipeline

In `backend/app/main.py:on_normalized_tick_received`:
```python
async def on_normalized_tick_received(tick: NormalizedTick):
    """Callback triggered whenever a normalized tick is received from MarketDataService."""
    updated_candles = candle_aggregator.process_tick(tick)
    
    # Authoritative tick processing and automated exit evaluation
    exit_events = paper_engine.process_market_tick(
        symbol=tick.symbol,
        ltp=tick.ltp,
        high=tick.high,
        low=tick.low,
        open_price=tick.open,
    )
    
    # Persist any triggered automated exits
    for ev in exit_events:
        try:
            await paper_engine.sync_close_to_db(ev.pos_id, ev.trade, ev.account_id)
        except Exception as e:
            logger.warning(f"[DB PAPER] Failed to persist automated exit: {e}")
```

### Step 6: Upgrade E2E Tests in `test_tier1_features.py`

Update `test_f18_side_correct_automated_exits` and `test_f19_same_bar_conservative_policy` to test the real engine implementation:

```python
def test_f18_side_correct_automated_exits(clean_paper_engine: PaperTradingEngine):
    """F18: Automated exits trigger correctly for LONG (low <= SL, high >= TP) and SHORT (high >= SL, low <= TP)."""
    # 1. LONG Position Stop-Loss Exit via process_market_tick
    long_order = PaperOrderRequest(
        symbol="HDFCBANK.NS",
        side="BUY",
        quantity=20,
        price=1600.0,
        stopLoss=1550.0,
        targetPrice=1700.0,
    )
    res_long = clean_paper_engine.execute_order(long_order)
    pos_id = res_long["position"]["id"]

    # Market tick drops through stop (low 1540 <= 1550)
    events = clean_paper_engine.process_market_tick("HDFCBANK.NS", ltp=1545.0, high=1560.0, low=1540.0)
    assert len(events) == 1
    assert events[0].exit_type == "EXIT_STOP"
    assert events[0].exit_reason == "STOP_LOSS"
    assert events[0].realized_pnl < 0
    assert pos_id not in clean_paper_engine.positions

    # 2. SHORT Position Stop-Loss Exit via process_market_tick
    short_order = PaperOrderRequest(
        symbol="INFY.NS",
        side="SELL",
        quantity=10,
        price=1800.0,
        stopLoss=1850.0,
        targetPrice=1700.0,
        productType="MIS",
    )
    res_short = clean_paper_engine.execute_order(short_order)
    pos_short_id = res_short["position"]["id"]

    # Market tick rallies through stop (high 1860 >= 1850)
    events_short = clean_paper_engine.process_market_tick("INFY.NS", ltp=1855.0, high=1860.0, low=1790.0)
    assert len(events_short) == 1
    assert events_short[0].exit_type == "EXIT_STOP"
    assert events_short[0].exit_reason == "STOP_LOSS"
    assert events_short[0].realized_pnl < 0
    assert pos_short_id not in clean_paper_engine.positions


def test_f19_same_bar_conservative_policy(clean_paper_engine: PaperTradingEngine):
    """F19: When bar high >= target AND bar low <= stop, stop loss takes conservative precedence."""
    order = PaperOrderRequest(
        symbol="RELIANCE.NS",
        side="BUY",
        quantity=10,
        price=2500.0,
        stopLoss=2450.0,
        targetPrice=2550.0,
    )
    clean_paper_engine.execute_order(order)

    # Wide bar crossing both TP (2550) and SL (2450)
    events = clean_paper_engine.process_market_tick("RELIANCE.NS", ltp=2500.0, high=2600.0, low=2400.0)
    assert len(events) == 1
    assert events[0].exit_type == "EXIT_STOP"
    assert events[0].exit_reason == "STOP_LOSS"
    assert events[0].same_bar_conflict is True
    assert events[0].realized_pnl < 0
    assert len(clean_paper_engine.positions) == 0
```

---

## 7. Edge Cases & Hardening Matrix

| Scenario | Potential Failure | Hardening Rule |
|---|---|---|
| **Gap-Down Open (Long SL)** | Fill at theoretical stop price gives trader unrealistic profit / less loss | If `open_price <= stop_loss`, fill at `open_price`. Applied before slippage. |
| **Gap-Up Open (Short SL)** | Fill at theoretical stop price gives trader unrealistic profit / less loss | If `open_price >= stop_loss`, fill at `open_price`. Applied before slippage. |
| **Zero or Negative Ticks** | Corrupts MTM, causes division by zero | Drop ticks with `ltp <= 0`; do not trigger exits or modify position prices. |
| **Inverted Bar Range** | Inverted high/low (`high < low`) breaks range check | Normalize: `high, low = max(high, low), min(high, low)`. |
| **Multiple Positions per Symbol** | Exiting only first matching position leaves others orphaned | Loop over all positions matching `symbol` using `list(self.positions.items())`. |
| **Collection Mutation During Loop** | `RuntimeError: dictionary changed size during iteration` | Always take `list(self.positions.items())` before iterating. |
| **Missing Stop or Target** | `TypeError: '<=' not supported between float and NoneType` | Explicit `is not None and val > 0` guard for both SL and TP. |
| **Account Isolation / IDOR** | Tick evaluation inadvertently leaks or closes wrong account | Pass `pos.get("account_id")` into `close_position` to preserve tenant boundaries. |

---

## 8. Verification Strategy

The Worker agent can verify implementation with:
```bash
pytest backend/tests/e2e/test_tier1_features.py -k "f18 or f19" -v
pytest backend/tests/e2e/test_tier3_combinations.py -v
pytest backend/tests/e2e/test_tier4_scenarios.py -v
pytest backend/tests/test_unified_paper_order.py -v
```
All tests must pass cleanly with zero regressions.
