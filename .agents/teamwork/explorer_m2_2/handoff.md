# Milestone 2 (Requirement R2) Investigation Report: Features 11, 12, 13 & E2E Tests

## Executive Summary
This investigation audits the implementation and readiness of Milestone 2 (Requirement R2) in the APEX workstation codebase:
- **Feature 11 (Timeframe Degradation Flag):** **DEFICIENT / SILENT SUBSTITUTION PRESENT.** When candles for `config.primary_timeframe` are missing, `signal_pipeline.py` silently substitutes fallback candles without setting `DataProvenance.DEGRADED`, without setting any degradation indicator on `SignalDecision`, and while hardcoding `signal.timeframe = config.primary_timeframe`. Downstream consumers receive no warning of timeframe substitution.
- **Feature 12 (Dynamic Signal Expiry):** **HARDCODED / DYNAMIC CALCULATION MISSING.** `signal_pipeline.py:585` hardcodes expiry to `time.time() + 3 * 900` seconds (3 candles of 15m), completely ignoring `config.signal_expiry_candles` and `config.primary_timeframe`. `SignalEngineConfig` in `models.py` lacks a helper to compute timeframe duration.
- **Feature 13 (Directional Geometry Validation):** **GATE MISSING AT SIGNAL GENERATION.** There is **no directional geometry gate** in `validation_gates.py` or `signal_pipeline.py`. `gate_stop_determinable` uses `abs()` and ignores direction, allowing inverted stops to qualify. While `main.py:2552` performs a partial stop check on order mutation, signal generation allows geometrically invalid signals to be marked `QUALIFIED` and targets are never geometrically validated.
- **E2E Tests:** `backend/tests/e2e/test_tier1_features.py` and `backend/tests/e2e/test_tier2_boundaries.py` test these mathematical invariants using isolated local helper functions rather than asserting against production pipeline functions because the production gates and models do not yet expose them.

---

## 1. Observation

### 1.1 Feature 11: Timeframe Degradation Flag (`signal_pipeline.py`, `models.py`)
1. **Silent Fallback Loop in `signal_pipeline.py:349-358`:**
   ```python
   symbol = candidate.symbol
   primary_candles = candles_by_timeframe.get(config.primary_timeframe, [])
   all_candles = primary_candles

   # Use the first available timeframe's candles if primary not available
   if not all_candles:
       for tf in config.mtf_timeframes:
           if candles_by_timeframe.get(tf):
               all_candles = candles_by_timeframe[tf]
               break
   ```
   - Observation: When `candles_by_timeframe` does not contain `primary_candles`, it iterates through `mtf_timeframes` and picks the first available timeframe. It does not record which timeframe was selected, nor does it record that a fallback occurred.
2. **Strategy Evaluation with Mismatched Timeframe in `signal_pipeline.py:407`:**
   ```python
   observatory = evaluate_strategies_observatory(
       candles=all_candles,
       is_live_feed=False,
       strategy_ids=None,
       timeframe=config.primary_timeframe,  # Still passes primary timeframe even when all_candles is from fallback tf!
       provider=active_prov,
       symbol=symbol,
   )
   ```
3. **Data Provenance Hardcoding in `signal_pipeline.py:573-577`:**
   ```python
   # 18. Data provenance
   is_live = bool(quote.get("is_live", False))
   provenance = (
       DataProvenance.RAW_AUTHENTIC_DATA if is_live
       else DataProvenance.SIMULATED
   )
   ```
   - Observation: Provenance is chosen exclusively based on `is_live`. It never evaluates whether fallback candles were used, even though `DataProvenance.DEGRADED = "DEGRADED"` is defined in `backend/app/signal_engine/models.py:86`.
4. **Signal Decision Construction in `signal_pipeline.py:677, 705-715`:**
   ```python
   timeframe=config.primary_timeframe,  # Always claims primary_timeframe!
   ...
   data_quality="VALID",
   provenance=provenance,
   data_sources=[
       DataSourceRecord(
           data_type="MARKET_DATA",
           source="MarketDataService",
           provider=quote.get("provider", "PROVIDER"),
           freshness="LIVE" if is_live else "HISTORICAL",
           provenance=provenance,
       )
   ],
   ```
5. **Model Attributes in `backend/app/signal_engine/models.py`:**
   - `SignalDecision` (lines 254-365) contains: `timeframe: str = "15m"`, `data_quality: str = "UNAVAILABLE"`, `provenance: DataProvenance = DataProvenance.UNAVAILABLE`.
   - `SignalDecision` does NOT have an `is_timeframe_degraded: bool` field, a `fallback_timeframe: Optional[str]` field, or an explicit degraded indicator.

### 1.2 Feature 12: Dynamic Signal Expiry (`signal_pipeline.py`, `models.py`)
1. **Hardcoded Expiry Calculation in `signal_pipeline.py:585`:**
   ```python
   # 20. Signal expiry
   expiry_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3 * 900))  # 3 candles @ 15m
   ```
   - Observation: The multiplier `3` and the second duration `900` are hardcoded literals.
   - If `config.signal_expiry_candles` is set to any value other than `3` (e.g., 2, 5, 10), it is ignored.
   - If `config.primary_timeframe` is set to `"1m"` (60s), `"5m"` (300s), `"1h"` (3600s), or `"1D"` (86400s), it is ignored.
2. **Deceptive Expiry Condition Label in `signal_pipeline.py:717`:**
   ```python
   expiry=expiry_time,
   expiry_condition=f"Valid for {config.signal_expiry_candles} candles on {config.primary_timeframe} timeframe",
   ```
   - Observation: The string claims to be valid for `{config.signal_expiry_candles}` on `{config.primary_timeframe}`, but `expiry_time` above was computed using `3 * 900`.
3. **Configuration Model in `backend/app/signal_engine/models.py:502`:**
   - `SignalEngineConfig` defines `signal_expiry_candles: int = Field(default=3)`.
   - `SignalEngineConfig` lacks any helper method (e.g., `get_expiry_duration_seconds()`) to map timeframe strings to duration in seconds.
   - Interval-to-seconds mapping exists elsewhere in `backend/app/candle_engine/aggregator.py:20-28`:
     `INTERVAL_SECONDS = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "1D": 86400}`.
4. **Downstream Expiry Enforcement:**
   - `backend/app/main.py:2513-2538`: Rejects paper orders with `HTTPException(400, "Invalid or expired signal timestamp")` if `datetime.now(timezone.utc) > expiry_dt`.
   - `backend/app/signal_engine/signal_store.py:395-415`: Retires signals from `_active` to `_history` when `now > expiry_ts`.
   - Because 5m signals receive 45-minute expiry instead of 15-minute expiry, they linger 3x too long; 1h signals expire 4x too fast.

### 1.3 Feature 13: Directional Geometry Validation (`validation_gates.py`, `stop_target_engine.py`, `signal_pipeline.py`, `main.py`)
1. **Absence of Geometry Gate in `backend/app/signal_engine/validation_gates.py`:**
   - Lines 9-18 & 669-731 list all 7 HARD GATES in the pipeline:
     1. `DATA_VALIDATION`
     2. `INSTRUMENT_VALIDATION`
     3. `MARKET_SESSION`
     4. `LIQUIDITY_VALIDATION`
     5. `STOP_DETERMINABLE`
     6. `RISK_REWARD`
     7. `PORTFOLIO_RISK`
   - There is NO directional geometry gate (neither `DIRECTIONAL_GEOMETRY` nor `TRADE_GEOMETRY`).
2. **Defective Stop Check in `validation_gates.py:310-350`:**
   ```python
   def gate_stop_determinable(stop_result, entry_price, config):
       ...
       if entry_price and entry_price > 0:
           stop_pct = abs(entry_price - stop_price) / entry_price * 100
           if stop_pct > config.max_stop_pct:
               return _gate(..., FAIL, ...)
   ```
   - Observation: `gate_stop_determinable` does NOT receive `direction`. Because it uses `abs(...)`, a LONG trade with `entry = 1000.0` and `stop = 1040.0` (stop above entry!) yields `stop_pct = 4.0% <= 5.0%` and returns `ValidationGateResult.PASS`!
3. **Flawed Short Stop Check in `backend/app/signal_engine/stop_target_engine.py:170, 187`:**
   ```python
   if (stop - entry) / entry <= config.max_stop_pct / 100:
   ```
   - Observation: For a SHORT position, if `stop < entry` (e.g. stop 950, entry 1000), `(stop - entry)` is negative (-50). Since `-50 / 1000 = -0.05 <= +0.05`, the condition passes, allowing an inverted stop.
4. **Target Engine Missing Geometry Assertions in `stop_target_engine.py:247-370`:**
   - In `_compute_long_targets`: `t1` snaps to `res_near_t1` without asserting `t1 > entry`. `t2` snaps to `res_above_t1` without asserting `t2 > t1`.
   - In `_compute_short_targets`: `t1` snaps to `sup_near_t1` without asserting `t1 < entry`. `t2` computes `entry - risk * rr` without asserting `t2 < t1`.
5. **Partial Validation only in `backend/app/main.py:2552-2570`:**
   ```python
   # 5. Directional Geometry Validation (in /api/paper/order)
   if sig_dir == "LONG" and stop_price >= signal.entry:
       raise HTTPException(400, detail=f"Invalid LONG trade geometry: stop loss (₹{stop_price}) must be below entry (₹{signal.entry})")
   elif sig_dir == "SHORT" and stop_price <= signal.entry:
       raise HTTPException(400, detail=f"Invalid SHORT trade geometry: stop loss (₹{stop_price}) must be above entry (₹{signal.entry})")
   ```
   - Observation: This check occurs only at the HTTP paper order submission endpoint, NOT during signal pipeline generation.
   - Observation: It only checks stop vs entry. It does NOT validate target geometry (`target_1`, `target_2`, `target_3`). Geometrically invalid targets are never rejected here.

### 1.4 E2E Test Expectations (`test_tier1_features.py`, `test_tier2_boundaries.py`)
1. **`backend/tests/e2e/test_tier1_features.py`:**
   - Lines 299-304 (`test_f11_timeframe_degradation_flag`): Only asserts config attribute presence (`config.primary_timeframe == "15m"`). Does not test pipeline behavior when fallback occurs.
   - Lines 309-318 (`test_f12_signal_expiry_alignment`): Computes arithmetic multiplication (`3 * 15 * 60 == 2700`, `3 * 5 * 60 == 900`) inside the test function rather than testing `signal_pipeline.py` or a method on `SignalEngineConfig`.
   - Lines 323-373 (`test_f13_directional_geometry_validation`): Defines an inline dummy function `is_geometry_valid(...)` inside the test rather than calling a production validation gate.
2. **`backend/tests/e2e/test_tier2_boundaries.py`:**
   - Lines 129-180 (`test_t2_long_geometry_boundary_violations` & `test_t2_short_geometry_boundary_violations`):
     Defines inline functions `validate_long_geometry` and `validate_short_geometry` testing the 5 boundary violations:
     - LONG: Stop == Entry, Stop > Entry, Target 1 == Entry, Target 1 < Entry, Target 2 < Target 1.
     - SHORT: Stop == Entry, Stop < Entry, Target 1 == Entry, Target 1 > Entry, Target 2 > Target 1.
     These boundary conditions clearly specify the exact expected behavior of the required production gate.

---

## 2. Logic Chain

1. **Feature 11 (Degradation Flag):**
   - *Premise 1:* R2 and `docs/APEX_ANTIGRAVITY_MASTER_PROMPT.md:104` dictate: "Do not substitute an unrelated primary timeframe without an explicit degraded result."
   - *Premise 2:* `signal_pipeline.py:353-357` falls back to secondary timeframes when primary candles are missing.
   - *Premise 3:* Neither `provenance = DataProvenance.DEGRADED` nor any degradation attribute/flag is assigned to the resulting `SignalDecision`, and `signal.timeframe` is reported as the primary timeframe.
   - *Deduction:* The signal engine currently performs silent substitution, directly violating Requirement R2. Downstream consumers have no way of knowing a non-primary timeframe was evaluated.

2. **Feature 12 (Dynamic Expiry):**
   - *Premise 1:* R2 and PROJECT.md Feature 12 require signal expiry duration to be dynamically calculated based on primary timeframe duration (candle duration * candle count).
   - *Premise 2:* `signal_pipeline.py:585` executes `time.time() + 3 * 900` unconditionally.
   - *Deduction:* Any configuration where `primary_timeframe != "15m"` or `signal_expiry_candles != 3` results in an incorrect expiry timestamp, causing either premature expiration or stale signal persistence.

3. **Feature 13 (Directional Geometry):**
   - *Premise 1:* R2 and PROJECT.md § Interface Contracts define:
     - LONG: `stop_loss < entry_price < target_1 < target_2`
     - SHORT: `target_2 < target_1 < entry_price < stop_loss`
   - *Premise 2:* `validation_gates.py` hard gates do not inspect directional geometry or compare targets against entry or stops against direction.
   - *Premise 3:* `signal_pipeline.py` marks signals `QUALIFIED` as long as `run_hard_gates` passes.
   - *Deduction:* Signals with invalid geometry (inverted stops or reversed targets) pass validation unnoticed during candidate evaluation. Order submission in `main.py` catches inverted stops but ignores inverted targets, and the rejection comes too late (at order execution rather than signal generation).

4. **Test Suite Status:**
   - *Premise 1:* `test_tier1_features.py` and `test_tier2_boundaries.py` define mathematical requirements in inline test closures.
   - *Deduction:* When the production gate `gate_directional_geometry` is implemented in `validation_gates.py`, and `get_expiry_duration_seconds()` is implemented in `models.py`, the test suite can be upgraded from asserting on mock closures to asserting directly against production components.

---

## 3. Caveats

1. **Existing Test Coverage:** The E2E tests (`test_tier1_features.py` and `test_tier2_boundaries.py`) pass currently *because* they test internal helper closures rather than asserting against `signal_pipeline.py` or `validation_gates.py`. Refactoring production code without updating these tests will leave the tests decoupled from production behavior.
2. **Derivatives Engines (F&O):** `FuturesEngine` in `futures_engine.py:386, 417` already contains an internal check (`INVALID_FUTURES_GEOMETRY`) for `f_stop` vs `entry` and `f_t1` vs `entry`, but it does not check `f_t2`. `OptionsEngine` delegates spot geometry to underlying spot inputs.
3. **Multi-Timeframe Fallback Policy:** Requirement R2 requires an explicit degraded result rather than silent substitution. Downstream callers must decide whether a degraded signal should still be `QUALIFIED` with `provenance=DataProvenance.DEGRADED` or fail closed as `REJECTED`/`NO_TRADE` with gate failure `TIMEFRAME_DEGRADED`. The master prompt states: "Fail closed for actionable signals when required input is stale, missing, mixed incompatibly or synthetic."

---

## 4. Conclusion

Milestone 2 (Requirement R2) currently has critical gaps in the signal generation engine:
1. **F11:** Timeframe fallback in `signal_pipeline.py` is silent; `DataProvenance.DEGRADED` is never assigned.
2. **F12:** Expiry calculation in `signal_pipeline.py` is static (`3 * 900`), ignoring timeframe and configured candle multiplier.
3. **F13:** Directional geometry validation is completely missing from `validation_gates.py` and the hard gate sequence in `signal_pipeline.py`.

All three features require concrete implementation in `backend/app/signal_engine/` before Milestone 2 can be considered complete.

---

## 5. Recommended Implementation Strategy

### 5.1 Implement Feature 11 (Timeframe Degradation Flag)
1. **In `backend/app/signal_engine/models.py`:**
   - Add fields to `SignalDecision`:
     ```python
     is_timeframe_degraded: bool = False
     fallback_timeframe: Optional[str] = None
     ```
2. **In `backend/app/signal_engine/signal_pipeline.py`:**
   - Track fallback state when retrieving candles:
     ```python
     primary_candles = candles_by_timeframe.get(config.primary_timeframe, [])
     all_candles = primary_candles
     is_timeframe_degraded = False
     active_timeframe = config.primary_timeframe

     if not all_candles:
         for tf in config.mtf_timeframes:
             if candles_by_timeframe.get(tf):
                 all_candles = candles_by_timeframe[tf]
                 is_timeframe_degraded = True
                 active_timeframe = tf
                 break
     ```
   - Update provenance:
     ```python
     if is_timeframe_degraded:
         provenance = DataProvenance.DEGRADED
     else:
         provenance = DataProvenance.RAW_AUTHENTIC_DATA if is_live else DataProvenance.SIMULATED
     ```
   - Pass `active_timeframe` to `evaluate_strategies_observatory` and populate `SignalDecision` with `is_timeframe_degraded=is_timeframe_degraded`, `fallback_timeframe=active_timeframe if is_timeframe_degraded else None`, and record a warning in `why_reasons`.

### 5.2 Implement Feature 12 (Dynamic Signal Expiry)
1. **In `backend/app/signal_engine/models.py`:**
   - Add helper method to `SignalEngineConfig`:
     ```python
     TIMEFRAME_SECONDS: Dict[str, int] = {
         "1m": 60,
         "3m": 180,
         "5m": 300,
         "15m": 900,
         "30m": 1800,
         "1h": 3600,
         "1D": 86400,
     }

     def get_expiry_duration_seconds(self) -> int:
         candle_sec = self.TIMEFRAME_SECONDS.get(self.primary_timeframe, 900)
         return int(self.signal_expiry_candles * candle_sec)
     ```
2. **In `backend/app/signal_engine/signal_pipeline.py`:**
   - Replace line 585 with dynamic duration:
     ```python
     expiry_duration_sec = config.get_expiry_duration_seconds()
     expiry_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expiry_duration_sec))
     ```
   - Set `expiry_condition=f"Valid for {config.signal_expiry_candles} candles on {config.primary_timeframe} timeframe ({expiry_duration_sec}s)"`.

### 5.3 Implement Feature 13 (Directional Geometry Validation Gate)
1. **In `backend/app/signal_engine/validation_gates.py`:**
   - Add dedicated hard gate function:
     ```python
     def gate_directional_geometry(
         direction: str,
         stop_result: Optional[StopLossResult],
         entry_price: Optional[float],
         targets: List[TargetLevel],
     ) -> ValidationGate:
         gate_id = "DIRECTIONAL_GEOMETRY"
         gate_name = "Directional Geometry Validation"

         if entry_price is None or entry_price <= 0:
             return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                          reason="Entry price unavailable or invalid")
         if stop_result is None or not hasattr(stop_result, "price"):
             return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                          reason="Stop loss price unavailable")

         stop_price = stop_result.price
         target_prices = [t.price for t in targets] if targets else []

         if direction == "LONG":
             # Requirement: stop < entry < target_1 < target_2
             if stop_price >= entry_price:
                 return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                              reason=f"LONG geometry violation: stop ₹{stop_price:.2f} >= entry ₹{entry_price:.2f}")
             if target_prices:
                 if target_prices[0] <= entry_price:
                     return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                                  reason=f"LONG geometry violation: target 1 ₹{target_prices[0]:.2f} <= entry ₹{entry_price:.2f}")
                 for i in range(len(target_prices) - 1):
                     if target_prices[i + 1] <= target_prices[i]:
                         return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                                      reason=f"LONG geometry violation: target {i+2} ₹{target_prices[i+1]:.2f} <= target {i+1} ₹{target_prices[i]:.2f}")
         elif direction == "SHORT":
             # Requirement: target_2 < target_1 < entry < stop
             if stop_price <= entry_price:
                 return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                              reason=f"SHORT geometry violation: stop ₹{stop_price:.2f} <= entry ₹{entry_price:.2f}")
             if target_prices:
                 if target_prices[0] >= entry_price:
                     return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                                  reason=f"SHORT geometry violation: target 1 ₹{target_prices[0]:.2f} >= entry ₹{entry_price:.2f}")
                 for i in range(len(target_prices) - 1):
                     if target_prices[i + 1] >= target_prices[i]:
                         return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                                      reason=f"SHORT geometry violation: target {i+2} ₹{target_prices[i+1]:.2f} >= target {i+1} ₹{target_prices[i]:.2f}")
         else:
             return _gate(gate_id, gate_name, "HARD", ValidationGateResult.FAIL,
                          reason=f"Invalid signal direction '{direction}'")

         return _gate(gate_id, gate_name, "HARD", ValidationGateResult.PASS,
                      evidence=f"Direction {direction} geometry validated (stop: {stop_price}, entry: {entry_price}, targets: {target_prices})")
     ```
2. **Wire into `ValidationPipeline.run_hard_gates`:**
   - Add parameters `direction: str` and `targets: List[TargetLevel]` to `run_hard_gates`.
   - Call `gate_directional_geometry` immediately following `gate_stop_determinable`.
   - If it fails, fail closed returning `False, gates, g.reason`.
3. **Wire into `signal_pipeline.py:485`:**
   - Pass `direction=direction` and `targets=targets` into `validation_pipeline.run_hard_gates(...)`.
4. **Update E2E Tests:**
   - In `backend/tests/e2e/test_tier1_features.py`:
     - Update `test_f11_timeframe_degradation_flag` to test `SignalDecision.is_timeframe_degraded` and `DataProvenance.DEGRADED`.
     - Update `test_f12_signal_expiry_alignment` to test `config.get_expiry_duration_seconds()`.
     - Update `test_f13_directional_geometry_validation` to import and assert against `gate_directional_geometry`.
   - In `backend/tests/e2e/test_tier2_boundaries.py`:
     - Update `test_t2_long_geometry_boundary_violations` and `test_t2_short_geometry_boundary_violations` to assert against `gate_directional_geometry`.

---

## 6. Verification Method

To verify these findings and subsequently verify the implementation:
1. **Inspect Code Files:**
   - `backend/app/signal_engine/signal_pipeline.py` lines 349-358, 573-577, 585, 677, 705-717.
   - `backend/app/signal_engine/models.py` lines 86, 260-365, 451-505.
   - `backend/app/signal_engine/validation_gates.py` lines 310-356, 662-731.
   - `backend/app/signal_engine/stop_target_engine.py` lines 102-148, 170-210, 247-370.
   - `backend/tests/e2e/test_tier1_features.py` lines 297-374.
   - `backend/tests/e2e/test_tier2_boundaries.py` lines 126-180.
2. **Run Pytest Test Command:**
   ```powershell
   pytest backend/tests/e2e/test_tier1_features.py backend/tests/e2e/test_tier2_boundaries.py -v
   ```
   (Verify zero regressions across all tier 1 and tier 2 boundary tests).
