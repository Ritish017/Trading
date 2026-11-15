# M1 Signal Engine & E2E Review Report

**Agent**: `teamwork_preview_reviewer` (`reviewer_m1_2_gen2`)  
**Parent Agent**: `89f607f3-2421-4e10-b882-c14724281ad4` (`parent`)  
**Milestone**: M1 Signal Engine & E2E Review  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\reviewer_m1_2_gen2\`  
**Date**: 2026-10-06 / 2026-10-07  
**Verdict**: **REQUEST_CHANGES**  

---

## 1. Observation

Direct code observations from static inspection and structural analysis:

### 1.1 E2E Test Suite Call Sites vs. Adapter Classes Discrepancy
1. In `backend/tests/e2e/test_tier1_features.py:39–48`:
   ```python
   from backend.app.signal_engine.options_engine import (
       OptionsEngine,
       OptionAction,
       OptionContract,
       OptionType,
   )
   from backend.app.signal_engine.futures_engine import (
       FuturesEngine,
       FuturesAction,
   )
   ```
   The test imports base `OptionsEngine` and base `FuturesEngine`, **NOT** `OptionsDecisionEngine` or `FuturesDecisionEngine`.
2. In `backend/tests/e2e/test_tier1_features.py:242–252`:
   ```python
   options_engine = OptionsEngine()
   # Case 1: Empty chain -> returns OPTIONS_DATA_INSUFFICIENT
   decision = options_engine.evaluate(
       symbol="NIFTY",
       spot_price=24000.0,
       underlying_direction="LONG",
       chain=[],
       capital=500000.0,
   )
   ```
   The test instantiates `OptionsEngine()` and invokes `.evaluate(symbol=..., spot_price=..., underlying_direction=..., chain=[], capital=...)`.
3. In `backend/app/signal_engine/options_engine.py:234–244`:
   ```python
   @classmethod
   def evaluate(
       cls,
       symbol: str,
       underlying_direction: str,  # "LONG" | "SHORT" | "NO_TRADE"
       spot_price: float,
       option_chain: Optional[List[Dict[str, Any]]],
       days_to_expiry: int,
       iv_percentile: Optional[float] = None,  # 0 to 100
       lot_size: int = 50,
       underlying_target_pct: float = 2.0,
   ) -> OptionDecision:
   ```
   `OptionsEngine.evaluate()` requires `option_chain` and `days_to_expiry`. It does **not** accept `chain`, does **not** accept `capital`, does **not** provide a default for `days_to_expiry`, and has no `**kwargs`. Invoking `OptionsEngine.evaluate(chain=[], capital=500000.0)` triggers:
   `TypeError: OptionsEngine.evaluate() got an unexpected keyword argument 'chain'`.
4. In `backend/tests/e2e/test_tier1_features.py:277–291`:
   ```python
   futures_engine = FuturesEngine()
   fut_decision = futures_engine.evaluate(
       symbol="NIFTY",
       spot_price=24000.0,
       futures_price=24050.0,
       days_to_expiry=10,
       oi=50000,
       oi_change_pct=5.0,
       volume=50,  # Insufficient volume
       lot_size=25,
       capital=500000.0,
       underlying_direction="LONG",
       stop_loss_spot=23900.0,
       target_spot=24200.0,
   )
   ```
   The test instantiates `FuturesEngine()` and calls `futures_engine.evaluate(...)`.
5. In `backend/app/signal_engine/futures_engine.py:97–125`:
   `FuturesEngine` defines `@classmethod def analyze(...)` and has **no method named `evaluate()`**. Calling `FuturesEngine().evaluate(...)` triggers:
   `AttributeError: type object 'FuturesEngine' has no attribute 'evaluate'`.
6. Similar calls to `OptionsEngine().evaluate(..., chain=..., capital=...)` occur in:
   - `backend/tests/e2e/test_tier2_boundaries.py:254, 269–275`
   - `backend/tests/e2e/test_tier3_combinations.py:164, 167–173`
   Both files import `OptionsEngine` (not `OptionsDecisionEngine`).
7. In `backend/app/signal_engine/signal_pipeline.py:633–640`:
   ```python
   o_res = OptionsEngine.evaluate(
       underlying_symbol=symbol,
       underlying_direction=direction,
       underlying_price=ltp,
       option_chain=option_chain,
       target_price=targets[0].price if targets else None,
       stop_loss_price=stop_result.price if stop_result else None,
   )
   ```
   `signal_pipeline.py` calls `OptionsEngine.evaluate()` with keyword arguments `underlying_symbol` and `underlying_price`, which are missing from `OptionsEngine.evaluate()` and only handled in `OptionsDecisionEngine.evaluate()`.
8. The worker implemented `OptionsDecisionEngine` and `FuturesDecisionEngine` in `options_engine.py:596–648` and `futures_engine.py:540–588`. However, neither `OptionsEngine` nor `FuturesEngine` delegates to or exposes these methods, and the test suites do not import the adapter classes.

### 1.2 Pytest Collection Verification
- Inspected module imports across all 4 tier test files:
  - `backend/tests/e2e/test_tier1_features.py`: 29 test functions.
  - `backend/tests/e2e/test_tier2_boundaries.py`: 13 test functions.
  - `backend/tests/e2e/test_tier3_combinations.py`: 5 test functions.
  - `backend/tests/e2e/test_tier4_scenarios.py`: 4 test functions.
- Total collected test items: **51 tests**.
- All top-level symbols (`ValidationGateResult`, `OptionsEngine`, `FuturesEngine`, `OrderState`, etc.) are defined and importable without syntax or module load errors.
- Therefore, `python -m pytest backend/tests/e2e --collect-only` discovers all 51 tests with 0 collection errors.
- **However**, collection-only success masked the runtime execution failures described in Observation 1.1 because pytest does not execute test bodies during collection.

### 1.3 Frontend Quote Store Verification (`frontend/src/stores/canonicalQuoteStore.ts`)
1. In `frontend/src/stores/canonicalQuoteStore.ts`:
   - Line 42: `const incomingTs = Number(rawQuote.provider_timestamp || rawQuote.timestamp || 0);`
   - Line 45: `if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) { return existing; }`
   - Line 116: `let incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0);`
   - Line 117–119: Millisecond epoch timestamps (`incomingTs > 1e11`) normalized to seconds (`Math.floor(incomingTs / 1000)`).
   - Line 122–124: `if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) { return existing; }`
2. `incomingTs` is properly declared in both REST and WebSocket methods, resolving TS2304.
3. Monotonicity rule is strictly enforced: incoming ticks with timestamps older than the existing quote's `provider_timestamp` are safely discarded without overwriting.

### 1.4 Backend Lifespans & Security Guardrails
1. `backend/app/market_data/service.py:172–183`: `disconnect()` implemented as an async method cleanly delegating to `self.active_provider.disconnect()` and updating status.
2. `backend/tests/test_lifespans_hardening.py:61–69, 101–108`: Added tests verifying `market_data_service.disconnect()` execution and provider delegation.
3. `backend/app/main.py`: All 6 occurrences of `RENDER_WORKER_URL` and `onrender.com` removed; loopback verified (`127.0.0.1` / `localhost`). Signal expiry in `/api/signals/{id}/paper-trade:2513–2545` correctly parses timezone-aware UTC timestamps and fails closed with HTTP 400 on expiration or invalid format.

---

## 2. Logic Chain

1. **Step 1 (Collection vs. Execution Disconnect — Supported by Observations 1.1 & 1.2)**:
   The worker's task was to resolve collection errors and ensure adapter compatibility. The worker created `OptionsDecisionEngine` and `FuturesDecisionEngine` adapters, and verified that `pytest backend/tests/e2e --collect-only` succeeded. However, `--collect-only` only evaluates top-level AST and module imports; it never calls `evaluate()`.
2. **Step 2 (Runtime Failure Identification — Supported by Observations 1.1 & 1.3)**:
   Because the test files (`test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`) and `signal_pipeline.py` instantiate and call base classes `OptionsEngine` and `FuturesEngine`, the adapter code in `OptionsDecisionEngine` and `FuturesDecisionEngine` is never executed. When the tests run, they fail immediately with `TypeError` and `AttributeError`.
3. **Step 3 (Worker Self-Certification Gap — Supported by Observations 1.1 & 1.2)**:
   The worker reported in `changes.md` and `handoff.md` that E2E test suites import `OptionsDecisionEngine` and `FuturesDecisionEngine` and that parameter mismatches were resolved. Direct inspection shows the test files do not import these classes. This represents a self-certification gap where passing collection-only status was conflated with functional runtime execution.
4. **Step 4 (Resolution Strategy)**:
   The adapter logic must be accessible directly through `OptionsEngine.evaluate()` and `FuturesEngine.evaluate()`, or aliased such that base class calls route through the normalized parameter converters.

---

## 3. Caveats

1. Direct execution of shell commands (`run_command`) timed out in this environment due to interactive PowerShell permissions. All findings are verified through static AST analysis, precise symbol tracking, and line-by-line inspection of code paths.
2. The core logic of the normalization adapters (`OptionsDecisionEngine.evaluate` and `FuturesDecisionEngine.evaluate`) is structurally sound and handles the necessary transformations (`OptionContract` -> dict, `chain` -> `option_chain`, spot boundaries, default DTE); the issue is solely that they are not attached to the classes being called.

---

## 4. Conclusion & Verdict

**Verdict**: **REQUEST_CHANGES**

### Findings

#### [Critical] Finding 1: Adapter Classes Disconnected from Call Sites (Runtime Failure)
- **What**: `OptionsDecisionEngine` and `FuturesDecisionEngine` are not invoked by the tests or pipeline. Calls to `OptionsEngine.evaluate(chain=..., capital=...)` fail with `TypeError: unexpected keyword argument 'chain'`, and calls to `FuturesEngine.evaluate(...)` fail with `AttributeError: type object 'FuturesEngine' has no attribute 'evaluate'`.
- **Where**:
  - `backend/tests/e2e/test_tier1_features.py:244, 278`
  - `backend/tests/e2e/test_tier2_boundaries.py:269`
  - `backend/tests/e2e/test_tier3_combinations.py:167`
  - `backend/app/signal_engine/signal_pipeline.py:633`
  - `backend/app/signal_engine/options_engine.py:596`
  - `backend/app/signal_engine/futures_engine.py:540`
- **Why**: Worker certified that the adapter classes solved E2E test execution based solely on `pytest --collect-only`. The tests import `OptionsEngine` and `FuturesEngine`, leaving the adapters bypassed.
- **Suggestion**:
  1. In `backend/app/signal_engine/options_engine.py`: Update `OptionsEngine.evaluate()` to handle `chain`, `option_chain`, `OptionContract` normalization, `underlying_symbol`, `underlying_price`, and default `days_to_expiry=14`, OR alias `OptionsEngine.evaluate = OptionsDecisionEngine.evaluate`.
  2. In `backend/app/signal_engine/futures_engine.py`: Expose `evaluate` on `FuturesEngine`: `FuturesEngine.evaluate = FuturesDecisionEngine.evaluate`.
  3. Alternatively, update the test imports in `test_tier1_features.py`, `test_tier2_boundaries.py`, and `test_tier3_combinations.py` to import `OptionsDecisionEngine as OptionsEngine` and `FuturesDecisionEngine as FuturesEngine`.

---

## 5. Verified Claims

- `canonicalQuoteStore.ts` TypeScript validity and monotonicity → verified via static inspection → **PASS**
- Render external worker probe eliminated from `backend/app/main.py` → verified 0 occurrences → **PASS**
- Signal expiry timestamp timezone awareness and 400 fail-closed validation → verified → **PASS**
- `MarketDataService.disconnect()` implementation and delegation → verified → **PASS**
- `pytest backend/tests/e2e --collect-only` discovers all 51 tests across all 4 tiers → verified → **PASS**
- E2E runtime adapter execution → verified against signatures → **FAIL (REQUEST_CHANGES)**

---

## 6. Verification Method

To independently verify these findings:
1. Inspect `backend/tests/e2e/test_tier1_features.py` lines 40, 46, 244, 278: observe `OptionsEngine` and `FuturesEngine` imports and `.evaluate(...)` calls.
2. Compare with `backend/app/signal_engine/options_engine.py` line 234 (`OptionsEngine.evaluate` signature) and line 596 (`OptionsDecisionEngine` definition).
3. Observe that `FuturesEngine` (line 97) lacks `evaluate()`.
4. In shell / python environment:
   ```python
   from backend.app.signal_engine.options_engine import OptionsEngine
   from backend.app.signal_engine.futures_engine import FuturesEngine
   # This will raise TypeError:
   OptionsEngine.evaluate(symbol="NIFTY", spot_price=24000.0, underlying_direction="LONG", chain=[], capital=500000.0)
   # This will raise AttributeError:
   FuturesEngine().evaluate(symbol="NIFTY", spot_price=24000.0, futures_price=24050.0)
   ```
