# Handoff Report: Milestone 2 (Requirement R2) — Feature 10 & Base Engine .evaluate() Compatibility

**Agent**: explorer_m2_1  
**Timestamp**: 2026-10-07T15:20:00Z  
**Parent Agent**: 3563c456-c22f-4ac6-b098-a8ca5800d879  
**Scope**: Feature 10 (Derivatives Contract Fail-Closed) in `options_engine.py` and `futures_engine.py`, Base Engine `.evaluate()` method compatibility across E2E test suites and pipeline callers.

---

## 1. Observation

### Obs 1.1: Test Failure in `test_tier1_features.py:244` (`test_f10_derivatives_contract_fail_closed`)
Running `python -m pytest backend/tests/e2e/test_tier1_features.py -k test_f10 -v` produced verbatim failure:
```
backend/tests/e2e/test_tier1_features.py::test_f10_derivatives_contract_fail_closed FAILED [100%]
================================== FAILURES ===================================
__________________ test_f10_derivatives_contract_fail_closed __________________
    def test_f10_derivatives_contract_fail_closed():
        options_engine = OptionsEngine()
>       decision = options_engine.evaluate(
            symbol="NIFTY",
            spot_price=24000.0,
            underlying_direction="LONG",
            chain=[],
            capital=500000.0,
        )
E       TypeError: OptionsEngine.evaluate() got an unexpected keyword argument 'chain'
backend\tests\e2e\test_tier1_features.py:244: TypeError
```

### Obs 1.2: Signature and Parameter Disconnect in `OptionsEngine.evaluate`
In `backend/app/signal_engine/options_engine.py:234-244`:
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
- Parameter name is `option_chain`, but tests pass `chain` (`test_tier1_features.py:248`, `test_tier2_boundaries.py:273`, `test_tier3_combinations.py:171`).
- `days_to_expiry` is a mandatory positional argument with no default; tests pass no `days_to_expiry`.
- `capital` is not accepted as a keyword argument; tests pass `capital=500000.0`.
- In `backend/app/signal_engine/options_engine.py:314-360`, the loop expects dicts (`raw.get(...)`), but test case 2 (`test_tier1_features.py:271`), `test_tier2_boundaries.py:273`, and `test_tier3_combinations.py:171` pass a list of `OptionContract` dataclass instances.
- An adapter subclass `OptionsDecisionEngine(OptionsEngine)` was defined at `backend/app/signal_engine/options_engine.py:596-649` that handles `chain`, `option_chain`, `OptionContract` instances, and default `days_to_expiry=14`. However, `OptionsEngine` itself does not have these capabilities, and all tests import and instantiate `OptionsEngine` directly.

### Obs 1.3: `FuturesEngine` Completely Lacks `.evaluate()` Method
In `backend/app/signal_engine/futures_engine.py`:
- `FuturesEngine` (lines 97-534) defines `@classmethod def analyze(...)` (lines 108-125). It has **no** `.evaluate()` method at all.
- Test `backend/tests/e2e/test_tier1_features.py:277-278` instantiates `futures_engine = FuturesEngine()` and calls:
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
- Because `FuturesEngine` does not define `.evaluate()`, this call site will raise `AttributeError: 'FuturesEngine' object has no attribute 'evaluate'` as soon as the test proceeds past line 276.
- An adapter subclass `FuturesDecisionEngine(FuturesEngine)` at `backend/app/signal_engine/futures_engine.py:540-588` defines `evaluate()`, but `FuturesEngine` does not have it, and tests import and instantiate `FuturesEngine` directly.

### Obs 1.4: Silent TypeErrors in `signal_pipeline.py` and `main.py`
In `backend/app/signal_engine/signal_pipeline.py:604-617`:
```python
f_res = FuturesEngine.analyze(
    underlying_symbol=symbol,
    underlying_direction=direction,
    underlying_price=ltp,
    futures_price=float(futures_data.get("futures_price", ltp)),
    dte=int(futures_data.get("dte", 15)),
    volume=int(futures_data.get("volume", 50000)),
    oi=int(futures_data.get("oi", 500000)),
    oi_change_pct=float(futures_data.get("oi_change_pct", 0.0)),
    lot_size=int(futures_data.get("lot_size", 250)),
    margin_per_lot=float(futures_data.get("margin_per_lot", 150000.0)),
    stop_loss_pts=abs(ltp - stop_result.price) if stop_result else ltp * 0.015,
    target_pts=abs(targets[0].price - ltp) if targets else ltp * 0.03,
)
```
And in `backend/app/main.py:2650-2663`:
`FuturesEngine.analyze` is called with `underlying_symbol`, `underlying_price`, `dte`, `stop_loss_pts`, `target_pts`.
Because `FuturesEngine.analyze` signature (line 108) only accepts `(cls, symbol, underlying_direction, spot_price, futures_price, days_to_expiry, oi, volume, lot_size, underlying_stop, underlying_target_1, underlying_target_2, oi_change_pct=0.0, available_capital=1000000.0, margin_per_lot=None, max_capital_allocation_pct=25.0)` and does not take `**kwargs` or alternate parameter names, these calls raise `TypeError: FuturesEngine.analyze() got an unexpected keyword argument 'underlying_symbol'`. In `signal_pipeline.py:626-627`, this is swallowed by `except Exception as e: logger.warning(...)`, leaving `futures_decision = None`.
Similarly, in `signal_pipeline.py:633` and `main.py:2676`, `OptionsEngine.evaluate` is called with `underlying_symbol`, `underlying_price`, `target_price`, `stop_loss_price`, which raises `TypeError` and is swallowed by `except Exception as e: logger.warning(...)`.

### Obs 1.5: Feature 10 Synthetic Mock Numbers vs Fail-Closed Semantics
Audit of the 7 contract parameters in `options_engine.py` and `futures_engine.py`:
1. **Expiry (`expiry` / `days_to_expiry`)**:
   - `options_engine.py:290`: `if days_to_expiry < 2: return OptionDecision(action=OptionAction.NO_TRADE, rejection_reason="EXPIRY_CYCLE_RESTRICTION")`. In individual contracts, `raw.get("expiry", "")` allows empty string without failing closed.
   - `futures_engine.py:221`: `if days_to_expiry < cls.MIN_DAYS_TO_EXPIRY: return FuturesDecision(action=FuturesAction.NO_TRADE, rejection_reason="EXPIRY_CYCLE_RESTRICTION")`.
2. **Lot Size (`lot_size`)**:
   - `options_engine.py:242`: defaults to `lot_size: int = 50`.
   - `futures_engine.py:251`: `volume_lots = volume // max(1, lot_size)`. If `lot_size <= 0` or missing, silently substitutes 1.
3. **Tick Size (`tick_size`)**:
   - Neither `OptionContract`, `OptionsEngine`, nor `FuturesEngine` models or validates `tick_size`.
4. **Open Interest (`oi`)**:
   - `options_engine.py:389`: requires `c.oi >= cls.MIN_OI (300)`. Rejection yields `OptionAction.NO_TRADE` with `"INSUFFICIENT_OPTION_LIQUIDITY"`.
   - `futures_engine.py:253`: requires `oi_lots >= cls.MIN_OI_LOTS (200)`. Rejection yields `FuturesAction.NO_TRADE` with `"LOW_FUTURES_LIQUIDITY"`.
5. **Volume (`volume`)**:
   - `options_engine.py:388`: requires `c.volume >= cls.MIN_VOLUME (100)`. Rejection yields `OptionAction.NO_TRADE`.
   - `futures_engine.py:253`: requires `volume_lots >= cls.MIN_VOLUME_LOTS (50)`. Rejection yields `FuturesAction.NO_TRADE`.
6. **Spread (`bid_ask_spread_pct`)**:
   - `options_engine.py:334`:
     ```python
     mid = (bid + ask) / 2.0 if (bid + ask) > 0 else ltp
     spread_pct = ((ask - bid) / mid * 100.0) if mid > 0 and ask >= bid else 0.0
     ```
     **Defect / Synthetic Substitution**: If `bid` and `ask` are 0.0 or missing from a contract, `ask >= bid` is True (`0.0 >= 0.0`), resulting in `spread_pct = 0.0%`. This fabricated tight spread bypasses `c.bid_ask_spread_pct <= cls.MAX_BID_ASK_SPREAD_PCT` instead of failing closed.
   - Futures does not model or check bid-ask spread.
7. **Margin (`margin_per_lot` / `margin_required`)**:
   - `futures_engine.py:455`:
     ```python
     estimated_margin_per_lot = margin_per_lot if margin_per_lot else contract_value_per_lot * 0.20  # ~20% SPAN+Exposure
     ```
     **Defect / Synthetic Substitution**: If genuine `margin_per_lot` is missing, it fabricates a synthetic 20% margin rather than failing closed.
8. **Missing-Data Actions (`OPTIONS_DATA_INSUFFICIENT` / `FUTURES_DATA_INSUFFICIENT`)**:
   - `OptionAction` has `OPTIONS_DATA_INSUFFICIENT` (`options_engine.py:39`). Returned when `not option_chain or len(option_chain) == 0` (line 272).
   - `FuturesAction` (`futures_engine.py:25-28`) **does not define** `FUTURES_DATA_INSUFFICIENT`. It only defines `BUY_FUTURE`, `SELL_FUTURE`, `NO_TRADE`.

---

## 2. Logic Chain

1. From **Obs 1.1** and **Obs 1.2**, when `test_tier1_features.py:244` invokes `options_engine.evaluate(..., chain=[], capital=500000.0)`, Python inspects the parameter list of `OptionsEngine.evaluate`. Because `OptionsEngine.evaluate` accepts `option_chain` and does not accept `chain`, `capital`, or `**kwargs`, Python raises a `TypeError`.
2. From **Obs 1.2**, the adapter `OptionsDecisionEngine` already implemented parameter normalization for `chain`, `OptionContract` instances, and default `days_to_expiry`. However, because all test files (`test_tier1_features.py:40`, `test_tier2_boundaries.py:41`, `test_tier3_combinations.py:33`) directly import and instantiate the base class `OptionsEngine()`, the adapter in `OptionsDecisionEngine` is bypassed and never executed.
3. From **Obs 1.3**, `test_tier1_features.py:277` instantiates `futures_engine = FuturesEngine()` and calls `futures_engine.evaluate(...)`. Because `FuturesEngine` does not have an `.evaluate()` method, fixing the `OptionsEngine` issue alone will immediately uncover an `AttributeError` on line 278.
4. From **Obs 1.4**, `signal_pipeline.py` and `main.py` call `FuturesEngine.analyze` with keyword arguments `underlying_symbol`, `underlying_price`, `dte`, `stop_loss_pts`, `target_pts`, and call `OptionsEngine.evaluate` with `underlying_symbol`, `underlying_price`, `target_price`, `stop_loss_price`. Because neither base method accepts these arguments, both derivative evaluations currently crash at runtime in production and are silently ignored by `try...except` blocks.
5. From **Obs 1.5**, requirement R2 / Feature 10 dictates that missing or incomplete derivatives parameters must fail closed with explicit UNAVAILABLE states rather than synthetic mock numbers. While empty option chains correctly return `OptionAction.OPTIONS_DATA_INSUFFICIENT`, incomplete contracts currently substitute synthetic values (0.20 IV, 0.0% bid-ask spread on missing bid/ask, 20% margin fallback on futures). Furthermore, `FuturesAction` lacks `FUTURES_DATA_INSUFFICIENT`.

---

## 3. Caveats

1. In `test_tier1_features.py:274`, `test_tier2_boundaries.py:276`, and `test_tier2_boundaries.py:298`, assertions accept either `OptionAction.NO_TRADE` or `OptionAction.OPTIONS_DATA_INSUFFICIENT` for illiquid/defective contracts (`assert decision.action in [OptionAction.NO_TRADE, OptionAction.OPTIONS_DATA_INSUFFICIENT]`). Therefore, retaining `NO_TRADE` with explicit rejection reasons or returning `OPTIONS_DATA_INSUFFICIENT` are both compliant with existing test assertions.
2. In `test_tier1_features.py:292`, the futures low-volume test asserts `assert fut_decision.action == FuturesAction.NO_TRADE` and `assert "insufficient volume" in fut_decision.rejection_reason.lower()`. Therefore, low volume must continue returning `FuturesAction.NO_TRADE` with `insufficient volume` in `rejection_reason`.
3. In `conftest.py:159`, an `incomplete_option_chain` fixture exists (`[{"strike": 24000.0, "option_type": "CE"}]`), but it is not currently referenced in `test_tier1_features.py`. Implementing contract parameter validation will make the engine robust against this fixture when Tier 2/4 boundary tests run.

---

## 4. Conclusion

1. **Root Cause of E2E Failure**: An architectural misalignment where compatibility adapters (`OptionsDecisionEngine`, `FuturesDecisionEngine`) were placed on child subclasses instead of the base classes (`OptionsEngine`, `FuturesEngine`) that test suites, pipelines, and routers actually instantiate.
2. **Engine Gaps**:
   - `OptionsEngine.evaluate`: misses keyword aliases (`chain` vs `option_chain`, `capital`, `underlying_symbol`, `underlying_price`), cannot ingest `OptionContract` instances directly, substitutes synthetic 0.0% spread if bid/ask are missing, and defaults IV to 0.20.
   - `FuturesEngine`: completely lacks `.evaluate()`, rejects pipeline kwargs (`underlying_symbol`, `underlying_price`, `dte`, `stop_loss_pts`, `target_pts`), falls back to synthetic 20% margin calculation, and lacks `FUTURES_DATA_INSUFFICIENT` in `FuturesAction`.

---

## 5. Recommended Implementation Strategy

### A. Modifications to `backend/app/signal_engine/options_engine.py`

1. **Move Adapter Logic Directly into `OptionsEngine.evaluate`**:
   Update `OptionsEngine.evaluate` signature to accept all caller variants:
   ```python
   @classmethod
   def evaluate(
       cls,
       symbol: Optional[str] = None,
       underlying_direction: str = "NO_TRADE",
       spot_price: float = 0.0,
       chain: Optional[Any] = None,
       option_chain: Optional[Any] = None,
       days_to_expiry: Optional[int] = None,
       capital: Optional[float] = None,
       underlying_symbol: Optional[str] = None,
       underlying_price: Optional[float] = None,
       iv_percentile: Optional[float] = None,
       lot_size: int = 50,
       underlying_target_pct: float = 2.0,
       target_price: Optional[float] = None,
       stop_loss_price: Optional[float] = None,
       **kwargs,
   ) -> OptionDecision:
   ```
2. **Normalize Arguments & Contracts**:
   - `sym = symbol or underlying_symbol or "UNKNOWN"`
   - `spot = spot_price if spot_price > 0 else (underlying_price if underlying_price is not None else 0.0)`
   - `raw_chain = chain if chain is not None else option_chain`
   - If `raw_chain is None or len(raw_chain) == 0`: return `OPTIONS_DATA_INSUFFICIENT` with `structure="UNAVAILABLE"`, `rejection_reason="OPTION_CHAIN_DATA_UNAVAILABLE"`.
   - Iterate `raw_chain`: if item is `OptionContract`, extract attributes (`item.strike`, `item.bid`, `item.ask`, `item.last_price`, `item.volume`, `item.oi`, `item.oi_change`, `item.iv`, `item.expiry`, `item.option_type`); if dict, extract with `.get()`.
   - Default `days_to_expiry = 14` if `days_to_expiry is None`.
3. **Fail-Closed on Incomplete Contract Parameters (No Synthetic Defaults)**:
   - If `bid <= 0 and ask <= 0`: do NOT compute `spread_pct = 0.0`. Set `spread_pct = 999.0` (unverifiable spread) so contracts with missing quotes fail liquidity validation rather than masquerading as 0% spread.
   - If `iv is None or iv <= 0`: do not inject synthetic 0.20 if genuine IV is missing.
4. **Subclass Compatibility**:
   Keep `OptionsDecisionEngine = OptionsEngine` as an alias to prevent breaking any callers importing `OptionsDecisionEngine`.

### B. Modifications to `backend/app/signal_engine/futures_engine.py`

1. **Add `FUTURES_DATA_INSUFFICIENT` to `FuturesAction`**:
   ```python
   class FuturesAction(str, Enum):
       BUY_FUTURE = "BUY_FUTURE"
       SELL_FUTURE = "SELL_FUTURE"
       NO_TRADE = "NO_TRADE"
       FUTURES_DATA_INSUFFICIENT = "FUTURES_DATA_INSUFFICIENT"
   ```
2. **Add `.evaluate()` Directly to `FuturesEngine`**:
   ```python
   @classmethod
   def evaluate(
       cls,
       symbol: Optional[str] = None,
       spot_price: float = 0.0,
       futures_price: float = 0.0,
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
       underlying_symbol: Optional[str] = None,
       underlying_price: Optional[float] = None,
       dte: Optional[int] = None,
       available_capital: Optional[float] = None,
       **kwargs,
   ) -> FuturesDecision:
   ```
   Map kwargs and invoke `cls.analyze(...)`.
   If `decision.rejection_reason == "LOW_FUTURES_LIQUIDITY"` and `volume // max(1, lot_size) < cls.MIN_VOLUME_LOTS`:
   ensure `decision.rejection_reason = "LOW_FUTURES_LIQUIDITY: Insufficient volume"`.
3. **Update `FuturesEngine.analyze` for Pipeline Compatibility**:
   Add keyword parameters `underlying_symbol=None`, `underlying_price=None`, `dte=None`, `stop_loss_pts=None`, `target_pts=None`, and `**kwargs` so pipeline calls from `signal_pipeline.py:604` and `main.py:2650` resolve without `TypeError`.
4. **Subclass Compatibility**:
   Keep `FuturesDecisionEngine = FuturesEngine` as an alias.

---

## 6. Verification Method

To verify these changes after implementation:

1. **Targeted E2E Tests**:
   - `python -m pytest backend/tests/e2e/test_tier1_features.py -k test_f10 -v` (Must pass: Case 1 empty chain, Case 2 illiquid/missing parameters, Case 3 low volume futures).
   - `python -m pytest backend/tests/e2e/test_tier2_boundaries.py -k test_t2_options_chain_liquidity_boundaries -v` (Must pass: wide spread rejection, zero OI rejection).
   - `python -m pytest backend/tests/e2e/test_tier3_combinations.py -k test_t3_options_bull_call_spread_pipeline -v` (Must pass: full pipeline with `OptionContract` chain).
2. **Existing Unit Tests**:
   - `python -m pytest backend/tests/signal_engine/test_fno_and_costs.py -v` (All 12 tests must continue passing cleanly).
3. **Signal Pipeline Integration**:
   - Inspect that `signal_pipeline.py` evaluations of options and futures do not trigger `Futures analysis error` or `Options analysis error` warnings in logs.
