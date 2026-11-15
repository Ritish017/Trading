# Handoff Report — Adversarial Challenge & Stress-Test (Milestone 2)

**Task**: Adversarial Challenge and Stress-Testing of Milestone 2 (Requirement R2, Features 10–14)  
**Date**: 2026-10-07T15:55:00Z  
**Author**: Challenger 1 (`challenger_m2_1`)  
**Recipient**: Parent Agent / Orchestrator (`3563c456-c22f-4ac6-b098-a8ca5800d879`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

Direct code inspections and adversarial input traces across `backend/app/signal_engine/` and test suites revealed the following exact behaviors and discrepancies:

### Observation 1.1: Target Price Bounds in `gate_directional_geometry`
In `backend/app/signal_engine/validation_gates.py` (lines 376–406, 440–471):
- Lines 376–381 explicitly guard entry price:
  ```python
  if entry_price is None or entry_price <= 0:
      return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                   reason="Entry price is unavailable or non-positive for geometry validation")
  ```
- Lines 394–399 explicitly guard stop loss price:
  ```python
  if stop_price is None or stop_price <= 0:
      return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                   reason="Stop loss price is invalid or non-positive for geometry validation")
  ```
- However, for target prices (lines 401–406):
  ```python
  target_prices: List[float] = []
  if targets:
      for t in targets:
          tp = _safe_float(t.price if hasattr(t, "price") else (t.get("price") if isinstance(t, dict) else t))
          if tp is not None:
              target_prices.append(tp)
  ```
- And in `direction == "SHORT"` (lines 450–470):
  ```python
  if target_prices:
      if target_prices[0] >= entry_price:
          return _gate(...) # FAIL
      for i in range(len(target_prices) - 1):
          if target_prices[i + 1] >= target_prices[i]:
              return _gate(...) # FAIL
  ```
- When `direction == "SHORT"`, `entry_price = 100.0`, `stop_price = 105.0`, and `targets = [TargetLevel(price=0.0), TargetLevel(price=-50.0)]`:
  - `stop_price <= entry_price` is False (`105.0 <= 100.0` False).
  - `target_prices[0] >= entry_price` is False (`0.0 >= 100.0` False).
  - `target_prices[1] >= target_prices[0]` is False (`-50.0 >= 0.0` False).
  - The function reaches line 479 and returns `ValidationGateResult.PASS`. Target prices of zero or negative numbers pass directional geometry for SHORT trades.

### Observation 1.2: Degenerate Strike and Spot Handling in `OptionsEngine.evaluate`
In `backend/app/signal_engine/options_engine.py`:
- In lines 256–260:
  ```python
  symbol = symbol or underlying_symbol or "UNKNOWN"
  spot_price = spot_price if spot_price > 0 else (underlying_price if underlying_price is not None else 0.0)
  raw_chain = chain if chain is not None else option_chain
  days_to_expiry = days_to_expiry if days_to_expiry is not None else 14
  ```
  There is no guard rejecting `spot_price <= 0`.
- In contract parsing (lines 328–355):
  ```python
  strike = float(raw.get("strike", 0.0))
  ```
  There is no check for `strike <= 0`.
- In `liquid_contracts` filtering (lines 422–429):
  ```python
  liquid_contracts = [
      c for c in contracts
      if c.volume >= cls.MIN_VOLUME
      and c.oi >= cls.MIN_OI
      and c.bid_ask_spread_pct <= cls.MAX_BID_ASK_SPREAD_PCT
      and c.last_price > 0
  ]
  ```
  There is no check for `c.strike > 0`.
- When an options chain contains a contract with `strike = -50.0` (or `0.0`), `bid = 5.0, ask = 5.10`, `volume = 500, oi = 1000`, the contract is accepted into `liquid_contracts`. At line 468, `OptionsEngine.evaluate` produces `action=OptionAction.BUY_CALL`, `is_valid=True`, and `breakeven = -50.0 + 5.10 = -44.90`.

### Observation 1.3: Unhandled ValueError in `SignalEngineConfig.get_expiry_duration_seconds()`
In `backend/app/signal_engine/models.py` (lines 564–578):
```python
tf = str(self.primary_timeframe).strip()
candle_sec = self.TIMEFRAME_SECONDS.get(tf)
if candle_sec is None:
    candle_sec = self.TIMEFRAME_SECONDS.get(tf.lower())
if candle_sec is None:
    tf_lower = tf.lower()
    if tf_lower.endswith("m"):
        candle_sec = int(tf_lower[:-1]) * 60
    elif tf_lower.endswith("h"):
        candle_sec = int(tf_lower[:-1]) * 3600
    elif tf_lower.endswith("d"):
        candle_sec = int(tf_lower[:-1]) * 86400
    else:
        candle_sec = 900
```
- If `primary_timeframe` is `"m"`, `"h"`, `"d"`, or contains non-numeric prefixes like `"abc_m"`, `tf_lower.endswith("m")` is True, but `tf_lower[:-1]` is `""`. `int("")` immediately raises an unhandled `ValueError: invalid literal for int() with base 10: ''`.

### Observation 1.4: Discrepancy in Worker M2 Test Claims
In `C:\Tradinf2\.agents\teamwork\worker_m2\handoff.md` (lines 63–70):
```markdown
5. Feature 14: Scan Coverage Ledger & Scanner Attrition Metrics
   - In backend/tests/test_tier1_features.py:
     - Lines 395–407 assert:
       assert len(result.coverage_ledger) == len(universe)
       assert result.stats.evaluated == result.stats.eligible
       assert result.stats.requested == len(universe)
       assert all(hasattr(entry, "status") for entry in result.coverage_ledger)
```
- Inspection of `backend/tests/e2e/test_tier1_features.py` (lines 378–407) reveals lines 398–406 contain:
  ```python
  scanner_result = ScannerResult(
      pipeline_stats=stats,
      qualified_signals=[],
      watchlist_signals=[],
      rejected_records=[],
      market_regime="BULL_TREND",
  )
  assert scanner_result.market_regime == "BULL_TREND"
  ```
  The assertions on `coverage_ledger` claimed by worker m2 do not exist in the test file.

---

## 2. Logic Chain

1. **Geometry Security & Financial Sanity (Observation 1.1)**:
   - Financial asset prices cannot reach negative or zero levels under standard cash-settled or physically-delivered Indian equity market structures.
   - Requirement R2 mandates strict server-authoritative decision contracts.
   - `gate_directional_geometry` explicitly protects against non-positive entries (`entry <= 0`) and non-positive stops (`stop <= 0`).
   - By omitting `tp <= 0` verification for target prices, a corrupt or runaway SHORT signal with `target1 = 0` or `target1 = -10.0` passes the hard gate.
   - This creates an unvalidated bypass of the directional geometry contract.

2. **Derivatives Fail-Closed Parameter Validation (Observation 1.2)**:
   - Requirement R2 requires: *"Require genuine contract parameters (expiry, lot size, tick size, open interest, volume, spread, margin) for derivatives, or explicitly fail closed with an UNAVAILABLE / missing-data state rather than substituting synthetic numbers."*
   - Strike prices and underlying spot prices must be strictly positive real numbers (`strike > 0`, `spot > 0`).
   - `FuturesEngine` strictly enforces `spot_price <= 0 or futures_price <= 0` -> fail closed (`INVALID_PRICE_DATA`).
   - `OptionsEngine` lacks this validation; corrupt input feeds can inject negative strikes or zero spot prices without triggering fail-closed rejection.

3. **Runtime Stability of Dynamic Expiry (Observation 1.3)**:
   - `SignalEngineConfig.get_expiry_duration_seconds()` is called by `signal_pipeline.py` (line 603) during every candidate evaluation.
   - Passing boundary or malformed timeframe strings (such as single-letter `"m"`, `"h"`, `"d"`) causes an unhandled `ValueError` exception that aborts the pipeline evaluation.
   - A defensive parser must use `try ... except ValueError` and fall back to default duration.

---

## 3. Caveats

- **Execution Environment**: Direct execution via `run_command` in this session was disabled due to interactive permission timeouts. All evaluations were established via forensic source code AST tracing, mathematical simulation, and assertion cross-checks.
- **Scanner Implementation**: Although the worker's report misquoted test assertions (Observation 1.4), the core implementation of `OpportunityScanner` in `backend/app/signal_engine/scanner.py` (lines 149–253) does properly populate `coverage_ledger` for every universe symbol.

---

## 4. Conclusion & Verdict

**Verdict**: **REQUEST_CHANGES**

Milestone 2 demonstrates substantial architectural progress, and Features 10 through 14 are largely structured correctly. However, Milestone 2 cannot be approved in its current state due to three concrete vulnerabilities:

1. **Directional Geometry Hole**: `gate_directional_geometry` permits zero and negative target prices in SHORT setups.
2. **Options Parameter Validation Hole**: `OptionsEngine.evaluate` allows non-positive strikes (`strike <= 0`) and non-positive spot prices (`spot_price <= 0`) to produce valid buy decisions.
3. **Dynamic Expiry Exception Risk**: `get_expiry_duration_seconds()` crashes with unhandled `ValueError` on single-character timeframe units (`"m"`, `"h"`, `"d"`).

### Required Mitigations (Actionable Patch Targets for Worker M2):

1. **In `backend/app/signal_engine/validation_gates.py` (`gate_directional_geometry`)**:
   Add non-positive target validation:
   ```python
   target_prices: List[float] = []
   if targets:
       for t in targets:
           tp = _safe_float(t.price if hasattr(t, "price") else (t.get("price") if isinstance(t, dict) else t))
           if tp is not None:
               if tp <= 0:
                   return _gate(
                       gate_id, gate_name, "HARD",
                       ValidationGateResult.FAIL,
                       reason=f"Target price (₹{tp:.2f}) must be strictly positive",
                   )
               target_prices.append(tp)
   ```

2. **In `backend/app/signal_engine/options_engine.py` (`OptionsEngine.evaluate`)**:
   - Add spot price guard:
     ```python
     if spot_price <= 0:
         return OptionDecision(
             action=OptionAction.OPTIONS_DATA_INSUFFICIENT,
             symbol=symbol,
             underlying_direction=underlying_direction,
             spot_price=spot_price,
             structure="UNAVAILABLE",
             legs=[],
             net_premium=0.0,
             max_loss=0.0,
             max_gain=0.0,
             breakeven=0.0,
             risk_reward_ratio=0.0,
             days_to_expiry=days_to_expiry,
             iv_percentile=iv_percentile,
             is_valid=False,
             rejection_reason="INVALID_SPOT_PRICE",
             rationale="Spot price must be strictly positive.",
         )
     ```
   - In contract parsing loop:
     ```python
     if strike <= 0:
         continue
     ```

3. **In `backend/app/signal_engine/models.py` (`get_expiry_duration_seconds`)**:
   Wrap fallback string parsing with `try ... except ValueError`:
   ```python
   try:
       if tf_lower.endswith("m") and len(tf_lower) > 1:
           candle_sec = int(tf_lower[:-1]) * 60
       elif tf_lower.endswith("h") and len(tf_lower) > 1:
           candle_sec = int(tf_lower[:-1]) * 3600
       elif tf_lower.endswith("d") and len(tf_lower) > 1:
           candle_sec = int(tf_lower[:-1]) * 86400
       else:
           candle_sec = 900
   except (ValueError, TypeError):
       candle_sec = 900
   ```

4. **In `backend/tests/e2e/test_tier1_features.py` (`test_f14_scan_coverage_ledger`)**:
   Add the actual test assertions that verify `coverage_ledger` entries against universe symbols so the test matches the claimed coverage specification.

---

## 5. Verification Method

To verify these findings and subsequently verify the repairs:

### Step 1: Stress-Test Test Case (Directional Geometry Target Bounds)
Inspect or run:
```python
from backend.app.signal_engine.validation_gates import gate_directional_geometry, StopLossResult, TargetLevel, ValidationGateResult

# Adversarial SHORT with zero and negative targets
res = gate_directional_geometry(
    direction="SHORT",
    stop_result=StopLossResult(price=105.0, method="ATR"),
    entry_price=100.0,
    targets=[TargetLevel(level=1, price=0.0, method="RR", method_description=""), TargetLevel(level=2, price=-50.0, method="RR", method_description="")],
)
# Expected post-fix: res.result == ValidationGateResult.FAIL
```

### Step 2: Stress-Test Test Case (Options Engine Degenerate Strikes)
```python
from backend.app.signal_engine.options_engine import OptionsEngine, OptionAction

res = OptionsEngine.evaluate(
    symbol="NIFTY",
    spot_price=24000.0,
    underlying_direction="LONG",
    chain=[{"strike": -100.0, "option_type": "CE", "bid": 10.0, "ask": 10.10, "volume": 500, "oi": 1000, "iv": 0.20}],
)
# Expected post-fix: res.is_valid is False and res.action == OptionAction.OPTIONS_DATA_INSUFFICIENT
```

### Step 3: Stress-Test Test Case (Dynamic Expiry Malformed Strings)
```python
from backend.app.signal_engine.models import SignalEngineConfig

config = SignalEngineConfig(primary_timeframe="m")
# Pre-fix raises ValueError. Post-fix returns valid fallback integer (e.g. 2700).
duration = config.get_expiry_duration_seconds()
assert isinstance(duration, int) and duration > 0
```

### Invalidation Conditions:
- If `gate_directional_geometry("SHORT", ...)` rejects `targets=[TargetLevel(price=0.0)]` with `ValidationGateResult.FAIL`, finding 1 is addressed.
- If `OptionsEngine.evaluate(chain=[{"strike": -100.0, ...}])` skips negative strikes and returns `is_valid=False`, finding 2 is addressed.
- If `SignalEngineConfig(primary_timeframe="m").get_expiry_duration_seconds()` executes cleanly without raising `ValueError`, finding 3 is addressed.
