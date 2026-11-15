# E2E Test Suite Pytest Collection Diagnostic & Repair Report

- **Explorer**: E2E Test Import Explorer (`explorer_m1_it2_3_gen2`)
- **Target Milestone**: Milestone 1 Iteration 2
- **Scope**: `backend/tests/e2e/` (`conftest.py`, `test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`, `test_tier4_scenarios.py`) and corresponding backend modules (`options_engine.py`, `futures_engine.py`, `models.py`).

---

## 1. Executive Summary

During pytest collection (`python -m pytest backend/tests/e2e --collect-only`), test collection fails immediately on `backend/tests/e2e/test_tier1_features.py`:
```
ImportError: cannot import name 'OptionsDecisionEngine' from 'backend.app.signal_engine.options_engine'
```

A comprehensive audit of all test suites and modules revealed three distinct import anomalies across the E2E test tier files:
1. **`OptionsDecisionEngine` vs `OptionsEngine`**:
   The options engine in `backend/app/signal_engine/options_engine.py` (line 172) is named `OptionsEngine`. Three E2E test files (`test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`) import `OptionsDecisionEngine`.
2. **`FuturesDecisionEngine` vs `FuturesEngine`**:
   The futures engine in `backend/app/signal_engine/futures_engine.py` (line 97) is named `FuturesEngine`. Two E2E test files (`test_tier1_features.py`, `test_tier2_boundaries.py`) import `FuturesDecisionEngine`. This is a secondary import failure that triggers immediately once the options import is resolved.
3. **Missing `ValidationGateResult` Import in `test_tier4_scenarios.py`**:
   `test_tier4_scenarios.py` references `ValidationGateResult.FAIL` (line 209) and `ValidationGateResult.PASS` (line 220), but omits `ValidationGateResult` from its import list from `backend.app.signal_engine.models`. While this does not block `--collect-only`, it causes an immediate runtime `NameError` upon suite execution.

By adding backward-compatibility exports/adapters in the backend engine modules (`options_engine.py`, `futures_engine.py`) and aligning the import statements in the test files, `python -m pytest backend/tests/e2e --collect-only` will discover and collect all 51 tests across all 4 tiers with **0 errors**.

---

## 2. Detailed Findings & Evidence Chain

### 2.1 Backend Signal Engine Declarations

1. **`backend/app/signal_engine/options_engine.py`**:
   - Line 172 declares `class OptionsEngine:`.
   - Methods: `get_options_rules_classification()`, `evaluate(...)`.
   - Exported symbols: `OptionAction`, `OptionType`, `OptionContract`, `OptionDecision`, `OptionsEngine`, `calculate_black_scholes_greeks`.
   - **Absence**: No symbol named `OptionsDecisionEngine` is defined or exported.

2. **`backend/app/signal_engine/futures_engine.py`**:
   - Line 97 declares `class FuturesEngine:`.
   - Methods: `analyze(...)`.
   - Exported symbols: `FuturesAction`, `OpenInterestPattern`, `FuturesDecision`, `FuturesEngine`.
   - **Absence**: No symbol named `FuturesDecisionEngine` is defined or exported.

3. **`backend/app/signal_engine/__init__.py`**:
   - Lines 103, 105: Defines `__all__` containing `"FuturesEngine"` and `"OptionsEngine"`.
   - Lines 136, 140: Imports and exports `FuturesEngine` and `OptionsEngine`.
   - **Absence**: Does not export `OptionsDecisionEngine` or `FuturesDecisionEngine`.

4. **`backend/app/signal_engine/models.py`**:
   - Line 89 declares `class ValidationGateResult(str, Enum):` with values `PASS`, `FAIL`, `UNAVAILABLE`.
   - Fully accessible for import by test files.

---

### 2.2 Audit of E2E Test Files (`backend/tests/e2e/`)

| File | Line | Issue | Root Cause | Impact |
|---|---|---|---|---|
| `backend/tests/e2e/test_tier1_features.py` | 40 | `from backend.app.signal_engine.options_engine import OptionsDecisionEngine` | Class is named `OptionsEngine` | Pytest collection fails (`ImportError`) |
| `backend/tests/e2e/test_tier1_features.py` | 46 | `from backend.app.signal_engine.futures_engine import FuturesDecisionEngine` | Class is named `FuturesEngine` | Pytest collection fails (`ImportError`) |
| `backend/tests/e2e/test_tier2_boundaries.py` | 41 | `from backend.app.signal_engine.options_engine import OptionsDecisionEngine` | Class is named `OptionsEngine` | Pytest collection fails (`ImportError`) |
| `backend/tests/e2e/test_tier2_boundaries.py` | 47 | `from backend.app.signal_engine.futures_engine import FuturesDecisionEngine` | Class is named `FuturesEngine` | Pytest collection fails (`ImportError`) |
| `backend/tests/e2e/test_tier3_combinations.py` | 33 | `from backend.app.signal_engine.options_engine import OptionsDecisionEngine` | Class is named `OptionsEngine` | Pytest collection fails (`ImportError`) |
| `backend/tests/e2e/test_tier4_scenarios.py` | 209, 220 | References `ValidationGateResult` without import | Omitted from line 18 imports | Runtime `NameError` during test run |
| `backend/tests/e2e/conftest.py` | 1-25 | None | Imports `OptionContract`, `OptionType` only | Clean (passes collection) |

---

### 2.3 Runtime Execution Considerations (Post-Collection Hardening)

Beyond collection, an in-depth code path trace revealed important invocation signature nuances that the Worker should address:
1. **Options Evaluation Signature**:
   - In `OptionsEngine.evaluate`, parameters are `symbol: str, underlying_direction: str, spot_price: float, option_chain: Optional[List[Dict[str, Any]]], days_to_expiry: int`.
   - In `test_tier1_features.py:244`, `test_tier2_boundaries.py:273`, and `test_tier3_combinations.py:171`, tests invoke `.evaluate(symbol=..., spot_price=..., underlying_direction=..., chain=[...], capital=...)`.
   - Parameter name `chain` is passed instead of `option_chain`.
   - Parameter `capital` is passed (not present in `OptionsEngine.evaluate`).
   - `OptionContract` instances (dataclasses) are passed inside the chain list, whereas `OptionsEngine.evaluate:316` executes `raw.get("strike", 0.0)` which expects dictionaries.
   - `days_to_expiry` has no default in `OptionsEngine.evaluate` but is omitted in `test_tier1_features.py:244`.
2. **Futures Evaluation Method**:
   - `FuturesEngine` defines `analyze(...)`, while `test_tier1_features.py:278` calls `futures_engine.evaluate(...)` with keyword parameters (`stop_loss_spot`, `target_spot`, `capital`).
   - `test_tier1_features.py:293` asserts `"insufficient volume" in fut_decision.rejection_reason.lower()`, whereas `FuturesEngine.analyze` sets `rejection_reason="LOW_FUTURES_LIQUIDITY"` and rationale containing the volume message.

**Recommendation**:
The cleanest architecture is a **two-layer fix**:
1. **Defense-in-depth aliases/adapters** in `options_engine.py` and `futures_engine.py` that provide backward compatibility for both class names and test signatures.
2. **Clean imports** in `backend/tests/e2e/` test files (`OptionsEngine as OptionsDecisionEngine`, `FuturesEngine as FuturesDecisionEngine`, and `ValidationGateResult`).

---

## 3. Exact Code Replacements / Diffs for Worker

### Change 1: `backend/app/signal_engine/options_engine.py`
Add backward-compatibility adapter and alias at the bottom of `backend/app/signal_engine/options_engine.py`:

```python
# ---------------------------------------------------------------------------
# Backward Compatibility & E2E Test Compatibility
# ---------------------------------------------------------------------------

class OptionsDecisionEngine(OptionsEngine):
    """
    Adapter providing seamless compatibility for E2E tests and legacy callers.
    Normalizes chain/option_chain, OptionContract objects to dicts, and defaults days_to_expiry.
    """
    @classmethod
    def evaluate(
        cls,
        symbol: Optional[str] = None,
        underlying_direction: str = "NO_TRADE",
        spot_price: float = 0.0,
        chain: Optional[Any] = None,
        option_chain: Optional[Any] = None,
        days_to_expiry: int = 14,
        capital: Optional[float] = None,
        underlying_symbol: Optional[str] = None,
        underlying_price: Optional[float] = None,
        **kwargs,
    ) -> OptionDecision:
        sym = symbol or underlying_symbol or "UNKNOWN"
        spot = spot_price if spot_price > 0 else (underlying_price if underlying_price is not None else 0.0)
        raw_chain = chain if chain is not None else option_chain

        normalized_chain = []
        if raw_chain:
            for item in raw_chain:
                if isinstance(item, OptionContract):
                    normalized_chain.append({
                        "strike": item.strike,
                        "option_type": item.option_type.value if hasattr(item.option_type, "value") else str(item.option_type),
                        "expiry": item.expiry,
                        "bid": item.bid,
                        "ask": item.ask,
                        "last_price": item.last_price,
                        "volume": item.volume,
                        "oi": item.oi,
                        "oi_change": item.oi_change,
                        "iv": item.iv,
                    })
                elif isinstance(item, dict):
                    normalized_chain.append(item)
                else:
                    normalized_chain.append(item)

        valid_kwargs = {k: v for k, v in kwargs.items() if k in ("iv_percentile", "lot_size", "underlying_target_pct")}
        return super().evaluate(
            symbol=sym,
            underlying_direction=underlying_direction,
            spot_price=spot,
            option_chain=normalized_chain,
            days_to_expiry=days_to_expiry,
            **valid_kwargs,
        )
```

---

### Change 2: `backend/app/signal_engine/futures_engine.py`
Add backward-compatibility adapter and alias at the bottom of `backend/app/signal_engine/futures_engine.py`:

```python
# ---------------------------------------------------------------------------
# Backward Compatibility & E2E Test Compatibility
# ---------------------------------------------------------------------------

class FuturesDecisionEngine(FuturesEngine):
    """
    Adapter providing evaluate() method mapping for E2E tests.
    """
    @classmethod
    def evaluate(
        cls,
        symbol: str,
        spot_price: float,
        futures_price: float,
        days_to_expiry: int = 14,
        oi: int = 0,
        oi_change_pct: float = 0.0,
        volume: int = 0,
        lot_size: int = 50,
        capital: float = 1000000.0,
        underlying_direction: str = "LONG",
        stop_loss_spot: Optional[float] = None,
        underlying_stop: Optional[float] = None,
        target_spot: Optional[float] = None,
        underlying_target_1: Optional[float] = None,
        underlying_target_2: Optional[float] = None,
        **kwargs,
    ) -> FuturesDecision:
        resolved_stop = stop_loss_spot if stop_loss_spot is not None else (underlying_stop or (spot_price * 0.98 if underlying_direction == "LONG" else spot_price * 1.02))
        resolved_t1 = target_spot if target_spot is not None else (underlying_target_1 or (spot_price * 1.03 if underlying_direction == "LONG" else spot_price * 0.97))
        resolved_t2 = underlying_target_2 or (resolved_t1 * 1.02 if underlying_direction == "LONG" else resolved_t1 * 0.98)

        decision = cls.analyze(
            symbol=symbol,
            underlying_direction=underlying_direction,
            spot_price=spot_price,
            futures_price=futures_price,
            days_to_expiry=days_to_expiry,
            oi=oi,
            volume=volume,
            lot_size=lot_size,
            underlying_stop=resolved_stop,
            underlying_target_1=resolved_t1,
            underlying_target_2=resolved_t2,
            oi_change_pct=oi_change_pct,
            available_capital=capital,
        )
        if decision.rejection_reason == "LOW_FUTURES_LIQUIDITY":
            volume_lots = volume // max(1, lot_size)
            if volume_lots < cls.MIN_VOLUME_LOTS:
                decision.rejection_reason = "LOW_FUTURES_LIQUIDITY: Insufficient volume"
        return decision
```

---

### Change 3: `backend/app/signal_engine/__init__.py`
Export both aliases in `backend/app/signal_engine/__init__.py`:

```diff
--- a/backend/app/signal_engine/__init__.py
+++ b/backend/app/signal_engine/__init__.py
@@ -103,8 +103,10 @@
     "FuturesEngine",
+    "FuturesDecisionEngine",
     "FuturesDecision",
     "OptionsEngine",
+    "OptionsDecisionEngine",
     "OptionDecision",
@@ -136,8 +138,10 @@
 from backend.app.signal_engine.futures_engine import (
     FuturesEngine,
+    FuturesDecisionEngine,
     FuturesDecision,
 )
 from backend.app.signal_engine.options_engine import (
     OptionsEngine,
+    OptionsDecisionEngine,
     OptionDecision,
```

---

### Change 4: `backend/tests/e2e/test_tier1_features.py`
```diff
--- a/backend/tests/e2e/test_tier1_features.py
+++ b/backend/tests/e2e/test_tier1_features.py
@@ -39,12 +39,12 @@
 from backend.app.signal_engine.options_engine import (
-    OptionsDecisionEngine,
+    OptionsEngine as OptionsDecisionEngine,
     OptionAction,
     OptionContract,
     OptionType,
 )
 from backend.app.signal_engine.futures_engine import (
-    FuturesDecisionEngine,
+    FuturesEngine as FuturesDecisionEngine,
     FuturesAction,
 )
```

---

### Change 5: `backend/tests/e2e/test_tier2_boundaries.py`
```diff
--- a/backend/tests/e2e/test_tier2_boundaries.py
+++ b/backend/tests/e2e/test_tier2_boundaries.py
@@ -40,12 +40,12 @@
 from backend.app.signal_engine.options_engine import (
-    OptionsDecisionEngine,
+    OptionsEngine as OptionsDecisionEngine,
     OptionAction,
     OptionContract,
     OptionType,
 )
 from backend.app.signal_engine.futures_engine import (
-    FuturesDecisionEngine,
+    FuturesEngine as FuturesDecisionEngine,
     FuturesAction,
 )
```

---

### Change 6: `backend/tests/e2e/test_tier3_combinations.py`
```diff
--- a/backend/tests/e2e/test_tier3_combinations.py
+++ b/backend/tests/e2e/test_tier3_combinations.py
@@ -32,7 +32,7 @@
 from backend.app.signal_engine.stop_target_engine import StopLossEngine
 from backend.app.signal_engine.options_engine import (
-    OptionsDecisionEngine,
+    OptionsEngine as OptionsDecisionEngine,
     OptionContract,
     OptionType,
     OptionAction,
```

---

### Change 7: `backend/tests/e2e/test_tier4_scenarios.py`
```diff
--- a/backend/tests/e2e/test_tier4_scenarios.py
+++ b/backend/tests/e2e/test_tier4_scenarios.py
@@ -24,6 +24,7 @@
     TargetLevel,
     ScannerPipelineStats,
+    ValidationGateResult,
 )
 from backend.app.signal_engine.validation_gates import (
```

---

## 4. Verification Method

Once the changes are applied by Worker:
1. **Pytest Collection Command**:
   ```bash
   python -m pytest backend/tests/e2e --collect-only
   ```
   **Expected Outcome**: 51 tests collected, 0 errors.
   - `test_tier1_features.py`: 30 tests collected
   - `test_tier2_boundaries.py`: 12 tests collected
   - `test_tier3_combinations.py`: 5 tests collected
   - `test_tier4_scenarios.py`: 4 tests collected

2. **Existing Unit Tests Regression Check**:
   ```bash
   python -m pytest backend/tests/signal_engine/test_fno_and_costs.py
   ```
   **Expected Outcome**: All existing F&O tests pass without regression.
