# E2E Test Suite Pytest Collection Diagnostic & Fix Report

**Explorer**: E2E Test Import Explorer (`explorer_m1_it2_3`)  
**Target Milestone**: Milestone 1 Iteration 2  
**Investigation Scope**: `backend/tests/e2e/` (`conftest.py`, `test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`, `test_tier4_scenarios.py`) and corresponding backend modules (`options_engine.py`, `futures_engine.py`).

---

## 1. Executive Summary

During pytest collection (`python -m pytest backend/tests/e2e --collect-only`), `test_tier1_features.py` fails with:
```
ImportError: cannot import name 'OptionsDecisionEngine' from 'backend.app.signal_engine.options_engine'
```

An exhaustive investigation across all four test tiers identified:
1. **`OptionsDecisionEngine` vs `OptionsEngine`**: The options engine class defined in `backend/app/signal_engine/options_engine.py` (line 172) is named `OptionsEngine`. However, three test files (`test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`) import `OptionsDecisionEngine`.
2. **`FuturesDecisionEngine` vs `FuturesEngine`**: The futures engine class defined in `backend/app/signal_engine/futures_engine.py` (line 97) is named `FuturesEngine`. However, two test files (`test_tier1_features.py`, `test_tier2_boundaries.py`) import `FuturesDecisionEngine`. This creates a secondary import failure immediately behind the first.
3. **Missing `ValidationGateResult` Import in `test_tier4_scenarios.py`**: In `test_tier4_scenarios.py`, lines 209 and 220 assert `res_gate.result == ValidationGateResult.FAIL` and `ValidationGateResult.PASS`, but `ValidationGateResult` is omitted from the imports from `backend.app.signal_engine.models`.

Providing canonical import mappings in the test files (`OptionsEngine as OptionsDecisionEngine`, `FuturesEngine as FuturesDecisionEngine`) plus backward-compatibility aliases in `options_engine.py` and `futures_engine.py` completely eliminates all collection errors and guarantees that `python -m pytest backend/tests/e2e --collect-only` completes with 0 errors.

---

## 2. Evidence Chain & Observations

### 2.1 Observation: Root Cause in `backend/app/signal_engine/options_engine.py`
- **File**: `backend/app/signal_engine/options_engine.py`
- **Line 172**: `class OptionsEngine:`
- **Exported Symbols**: `OptionAction`, `OptionType`, `OptionContract`, `OptionDecision`, `OptionsEngine`, `calculate_black_scholes_greeks`.
- **Finding**: No class or attribute named `OptionsDecisionEngine` exists in `options_engine.py`.

### 2.2 Observation: Secondary Error in `backend/app/signal_engine/futures_engine.py`
- **File**: `backend/app/signal_engine/futures_engine.py`
- **Line 97**: `class FuturesEngine:`
- **Exported Symbols**: `FuturesAction`, `OpenInterestPattern`, `FuturesDecision`, `FuturesEngine`.
- **Finding**: No class or attribute named `FuturesDecisionEngine` exists in `futures_engine.py`.

### 2.3 Observation: Broken Imports Across Test Files
- **`backend/tests/e2e/test_tier1_features.py`**:
  - Line 40: `OptionsDecisionEngine` from `backend.app.signal_engine.options_engine` [FAILS COLLECTION]
  - Line 46: `FuturesDecisionEngine` from `backend.app.signal_engine.futures_engine` [FAILS COLLECTION]
- **`backend/tests/e2e/test_tier2_boundaries.py`**:
  - Line 41: `OptionsDecisionEngine` from `backend.app.signal_engine.options_engine` [FAILS COLLECTION]
  - Line 47: `FuturesDecisionEngine` from `backend.app.signal_engine.futures_engine` [FAILS COLLECTION]
- **`backend/tests/e2e/test_tier3_combinations.py`**:
  - Line 33: `OptionsDecisionEngine` from `backend.app.signal_engine.options_engine` [FAILS COLLECTION]
- **`backend/tests/e2e/test_tier4_scenarios.py`**:
  - Lines 209, 220: References `ValidationGateResult`, but `ValidationGateResult` is not imported from `backend.app.signal_engine.models` [RUNTIME NAMEERROR].
- **`backend/tests/e2e/conftest.py`**:
  - Verified clean: Imports `OptionContract, OptionType` only.

---

## 3. Systematic Audit Table

| File | Line | Broken Import / Symbol | Authoritative Name / Location | Status |
|---|---|---|---|---|
| `backend/tests/e2e/test_tier1_features.py` | 40 | `OptionsDecisionEngine` | `OptionsEngine` (`options_engine.py:172`) | ❌ Collection Failure |
| `backend/tests/e2e/test_tier1_features.py` | 46 | `FuturesDecisionEngine` | `FuturesEngine` (`futures_engine.py:97`) | ❌ Collection Failure |
| `backend/tests/e2e/test_tier2_boundaries.py` | 41 | `OptionsDecisionEngine` | `OptionsEngine` (`options_engine.py:172`) | ❌ Collection Failure |
| `backend/tests/e2e/test_tier2_boundaries.py` | 47 | `FuturesDecisionEngine` | `FuturesEngine` (`futures_engine.py:97`) | ❌ Collection Failure |
| `backend/tests/e2e/test_tier3_combinations.py` | 33 | `OptionsDecisionEngine` | `OptionsEngine` (`options_engine.py:172`) | ❌ Collection Failure |
| `backend/tests/e2e/test_tier4_scenarios.py` | 209, 220 | Missing `ValidationGateResult` | `ValidationGateResult` (`models.py`) | ⚠️ Runtime NameError |
| `backend/tests/e2e/conftest.py` | N/A | None | Clean | ✅ Valid |

---

## 4. Formulated Code Diffs for Worker

### Diff 1: `backend/app/signal_engine/options_engine.py`
Add backward-compatibility alias at the end of `backend/app/signal_engine/options_engine.py`:
```python
# Backward compatibility alias
OptionsDecisionEngine = OptionsEngine
```

### Diff 2: `backend/app/signal_engine/futures_engine.py`
Add backward-compatibility alias at the end of `backend/app/signal_engine/futures_engine.py`:
```python
# Backward compatibility alias
FuturesDecisionEngine = FuturesEngine
```

### Diff 3: `backend/tests/e2e/test_tier1_features.py`
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

### Diff 4: `backend/tests/e2e/test_tier2_boundaries.py`
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

### Diff 5: `backend/tests/e2e/test_tier3_combinations.py`
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
 )
```

### Diff 6: `backend/tests/e2e/test_tier4_scenarios.py`
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
