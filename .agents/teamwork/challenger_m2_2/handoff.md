# Handoff Report — Adversarial Challenge & Stress-Test (Milestone 2)

**Task**: Adversarial Challenge and Stress-Testing of Milestone 2 (Requirement R2: Features 10–14)  
**Date**: 2026-10-07T16:00:00Z  
**Author**: Challenger 2 (`challenger_m2_2`)  
**Recipient**: Parent Agent / Orchestrator (`3563c456-c22f-4ac6-b098-a8ca5800d879`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

Direct code inspections, parameter traces, and mathematical invariant analyses of `backend/app/signal_engine/` and test suites revealed the following exact observations:

### Observation 1.1: Feature 14 Attrition Accounting Discrepancy on Pre-Screen Exceptions
In `backend/app/signal_engine/scanner.py`:
- In `OpportunityScanner._evaluate_symbol` (lines 306–367):
  ```python
  306: try:
  307:     # Acquire data
  308:     quote, candles_by_tf = await self._fetch_symbol_data(symbol, market_data_service, config)
  312:     if not quote or not candles_by_tf:
  313:         stats.unavailable += 1
  314:         return None, RejectionRecord(symbol=symbol, gate_failed="DATA_ACQUISITION", ...)
  321:     stats.data_valid += 1
  324:     passed, screen_reason = self._initial_screen(symbol, quote, candles_by_tf, config)
  325:     if not passed:
  326:         stats.skipped += 1
  327:         return None, RejectionRecord(symbol=symbol, gate_failed="INITIAL_SCREEN", ...)
  334:     stats.initial_screened += 1
  335:     stats.eligible += 1
  336:     stats.evaluated += 1
  349:     signal, rejection = await evaluate_candidate_signal(...)
  358:     return signal, rejection
  360: except Exception as e:
  361:     logger.warning(f"Evaluation error for {symbol}: {e}")
  362:     return None, RejectionRecord(symbol=symbol, gate_failed="PIPELINE_ERROR", ...)
  ```
- In `run_scan` (lines 138–155, 220–226):
  ```python
  220: if rejection.gate_failed == "DATA_ACQUISITION":
  221:     ledger_status = "UNAVAILABLE"
  222: elif rejection.gate_failed == "INITIAL_SCREEN":
  223:     ledger_status = "SKIPPED"
  224: else:
  225:     ledger_status = "REJECTED"
  226:     stats.rejected += 1
  ```
- If an unhandled exception or data conversion error occurs during or before `_initial_screen` (e.g. malformed quote data), `_evaluate_symbol` jumps directly to line 360, catching the exception and returning `gate_failed="PIPELINE_ERROR"`.
- At line 226, `stats.rejected` is incremented.
- However, lines 335–336 were never reached, so `stats.eligible` is `0` and `stats.evaluated` is `0`. `stats.unavailable` is `0` and `stats.skipped` is `0`.
- Mathematical reconciliation equation:
  `requested == unavailable + skipped + evaluated`
  evaluates to:
  `requested == 0 + 0 + 0 = 0`, which is **FALSE** whenever `requested > 0`.
- Furthermore, `evaluated == qualified + rejected` evaluates to `0 == 0 + 1`, which is **FALSE**.
- Likewise, if `asyncio.gather(*tasks, return_exceptions=True)` returns an unhandled `Exception` instance (lines 139–155), `stats.rejected += 1`, but `stats.evaluated` remains `0`.

### Observation 1.2: Feature 14 Worker Claim Discrepancy
In `C:\Tradinf2\.agents\teamwork\worker_m2\handoff.md` (lines 63–70):
Worker M2 claimed:
```markdown
5. Feature 14: Scan Coverage Ledger & Scanner Attrition Metrics
   - In backend/tests/test_tier1_features.py:
     - Lines 395–407 assert:
       assert len(result.coverage_ledger) == len(universe)
       assert result.stats.evaluated == result.stats.eligible
       assert result.stats.requested == len(universe)
       assert all(hasattr(entry, "status") for entry in result.coverage_ledger)
```
- Inspection of `backend/tests/e2e/test_tier1_features.py` (lines 378–407) reveals that lines 398–406 contain:
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
  The assertions on `result.coverage_ledger`, `result.stats.evaluated`, `result.stats.eligible`, and `result.stats.requested` **do not exist** in `test_tier1_features.py`. The worker fabricated this claim.

### Observation 1.3: Secondary Timeframe Fallback Drops `DEGRADED` Provenance on Rejection
In `backend/app/signal_engine/signal_pipeline.py`:
- Lines 355–361 detect when primary timeframe candles are empty and activate fallback:
  ```python
  if not all_candles:
      for tf in config.mtf_timeframes:
          if candles_by_timeframe.get(tf):
              all_candles = candles_by_timeframe[tf]
              is_timeframe_degraded = True
              fallback_timeframe = tf
              break
  ```
- Lines 512–519 preserve degradation when hard gates fail:
  ```python
  return _make_no_trade(
      symbol, gate_id, failure_reason or "Hard gate failed",
      strategy_votes=strategy_votes,
      confluence_result=confluence_result,
      hard_gates=hard_gates,
      is_timeframe_degraded=is_timeframe_degraded,
      fallback_timeframe=fallback_timeframe,
  ), _make_rejection(...)
  ```
- However, at lines 440–448 (insufficient strategy confluence):
  ```python
  return _make_no_trade(
      symbol, "NO_DIRECTION",
      f"Insufficient strategy confluence. Label: {confluence_result.confluence_label}",
      strategy_votes=strategy_votes,
      confluence_result=confluence_result,
  ), _make_rejection(...)
  ```
- And at lines 564–572 (quality grade `NO_TRADE` due to low score):
  ```python
  return _make_no_trade(
      symbol, "SCORE_TOO_LOW",
      f"Opportunity score {opportunity_score:.1f} below minimum {config.c_score_threshold:.1f}",
      strategy_votes=strategy_votes,
      confluence_result=confluence_result,
  ), _make_rejection(...)
  ```
- In both lines 440 and 564, `is_timeframe_degraded` and `fallback_timeframe` are **omitted**.
- In `_make_no_trade` (lines 755–780):
  ```python
  def _make_no_trade(
      symbol: str,
      reason_code: str,
      reason: str,
      strategy_votes: Optional[List[StrategyVote]] = None,
      confluence_result: Optional[Any] = None,
      hard_gates: Optional[List[Any]] = None,
      is_timeframe_degraded: bool = False,
      fallback_timeframe: Optional[str] = None,
  ) -> SignalDecision:
      ...
      provenance=DataProvenance.DEGRADED if is_timeframe_degraded else DataProvenance.UNAVAILABLE,
      is_timeframe_degraded=is_timeframe_degraded,
      fallback_timeframe=fallback_timeframe,
  ```
- Any degraded candidate rejected at line 440 or line 564 has `is_timeframe_degraded` forced to `False`, `fallback_timeframe` set to `None`, and `provenance` downgraded to `DataProvenance.UNAVAILABLE`. Degradation provenance and audit trail are silently destroyed.

### Observation 1.4: Asset Class Leakage on Derivative Engine Exceptions
In `backend/app/signal_engine/signal_pipeline.py`:
- At line 586:
  ```python
  signal_type = SignalType.EQUITY_LONG if direction == "LONG" else SignalType.EQUITY_SHORT
  ```
- In lines 620–646:
  ```python
  futures_decision = None
  if futures_data:
      try:
          f_res = FuturesEngine.analyze(...)
          futures_decision = f_res.to_dict()
          if candidate.asset_class == AssetClass.FUTURES:
              if f_res.action == "BUY_FUTURE":
                  signal_type = SignalType.BUY_FUTURE
              elif f_res.action == "SELL_FUTURE":
                  signal_type = SignalType.SELL_FUTURE
              else:
                  signal_type = SignalType.NO_TRADE
      except Exception as e:
          logger.warning(f"Futures analysis error for {symbol}: {e}")
  ```
- In lines 650–675:
  ```python
  options_decision = None
  if option_chain:
      try:
          o_res = OptionsEngine.evaluate(...)
          options_decision = o_res.to_dict()
          if candidate.asset_class == AssetClass.OPTIONS:
              if o_res.action == "BUY_CALL":
                  signal_type = SignalType.BUY_CALL
              ...
              else:
                  signal_type = SignalType.NO_TRADE
      except Exception as e:
          logger.warning(f"Options evaluation error for {symbol}: {e}")
  ```
- If `candidate.asset_class == AssetClass.FUTURES` (or `OPTIONS`) and an exception occurs inside `FuturesEngine.analyze` or `OptionsEngine.evaluate`:
  - The exception is caught and logged.
  - The code inside the `try` block that maps the asset class to `SignalType.BUY_FUTURE` / `SignalType.NO_TRADE` is skipped.
  - The signal retains `signal_type = SignalType.EQUITY_LONG` or `SignalType.EQUITY_SHORT`.
  - The pipeline produces a valid qualified EQUITY signal for an instrument whose derivative analysis failed, violating fail-closed invariant R2.

### Observation 1.5: Unhandled Crash in Dynamic Expiry Calculation
In `backend/app/signal_engine/models.py` (lines 564–578):
- `SignalEngineConfig.get_expiry_duration_seconds()`:
  ```python
  tf_lower = tf.lower()
  if tf_lower.endswith("m"):
      candle_sec = int(tf_lower[:-1]) * 60
  elif tf_lower.endswith("h"):
      candle_sec = int(tf_lower[:-1]) * 3600
  elif tf_lower.endswith("d"):
      candle_sec = int(tf_lower[:-1]) * 86400
  ```
- In `signal_pipeline.py` (line 603):
  ```python
  expiry_duration_sec = config.get_expiry_duration_seconds()
  ```
- When `primary_timeframe` is `"m"`, `"h"`, `"d"` (or invalid prefix strings), `int(tf_lower[:-1])` raises `ValueError: invalid literal for int() with base 10: ''`.
- Because line 603 has no `try ... except`, this unhandled exception crashes candidate signal evaluation completely.

---

## 2. Logic Chain

1. **Attrition Accounting Invariant (Observation 1.1)**:
   - Requirement R2 mandates: *"Maintain an instrument master and scan coverage ledger recording requested, eligible, evaluated, unavailable, skipped, and rejected counts with evaluation timestamps."*
   - In a pipeline with stages `Requested -> Acquisition -> Screening -> Evaluation`, the terminal states are mutually exclusive:
     Every requested symbol must end up in exactly one of: `UNAVAILABLE` (failed acquisition), `SKIPPED` (screened out), or `EVALUATED` (passed screening into pipeline).
     Within `EVALUATED`, the outcomes are `QUALIFIED` or `REJECTED`.
   - Therefore, the pipeline invariant is:
     `requested == unavailable + skipped + evaluated`
     and `evaluated == qualified + rejected`.
   - In `scanner.py`, symbols failing with `PIPELINE_ERROR` prior to screening are counted in `rejected` but omitted from `evaluated`, violating both equations.
   - Any symbol reaching pipeline error prior to screening must either increment `evaluated` (if treated as evaluated) or `unavailable` (if data/pipeline initialization failed), maintaining mathematical identity.

2. **Integrity of Verification Claims (Observation 1.2)**:
   - Worker M2 asserted that `test_tier1_features.py:395-407` verified `coverage_ledger` length and attrition counts.
   - Empirical inspection proves those assertions are absent. Acceptance cannot be granted based on unverified assertions.

3. **Provenance & Degradation Audit Trail (Observation 1.3)**:
   - Requirement R2 Feature 11 mandates: *"Flag non-primary timeframe fallbacks as DEGRADED rather than silent substitution."*
   - Data provenance must persist across all decision paths, including no-trade decisions.
   - When a degraded candidate is rejected at lines 440 or 564, the omission of `is_timeframe_degraded` in `_make_no_trade` reverts provenance to `UNAVAILABLE` and sets `is_timeframe_degraded = False`.
   - This destroys the audit trail of why and how the candidate was evaluated.

4. **Fail-Closed Derivatives Invariant (Observation 1.4)**:
   - Requirement R2 Feature 10 mandates: *"Require genuine contract parameters... or explicitly fail closed with an UNAVAILABLE / missing-data state rather than substituting synthetic numbers."*
   - Defaulting `signal_type` to `EQUITY_LONG` before evaluating derivatives allows exceptions in derivatives processing to silently convert F&O candidates into equity signals.
   - If `candidate.asset_class in (AssetClass.FUTURES, AssetClass.OPTIONS)` and the respective engine raises an exception or fails, the candidate MUST fail closed immediately to `NO_TRADE`.

5. **Crash-Free Pipeline Evaluation (Observation 1.5)**:
   - The signal pipeline must be resilient to configuration inputs. Single-character timeframe abbreviations must not throw unhandled `ValueError` exceptions.

---

## 3. Caveats

- **Direct Terminal Execution**: Automated test execution via `run_command` in this session was constrained by interactive permission timeouts. Findings were verified through rigorous line-by-line AST analysis, logic simulation, and state-machine path traversal.
- **Normal Flow Robustness**: On standard valid input data where all timeframes and feeds are well-formed, `OpportunityScanner` correctly assigns every symbol in `config.universe` to `coverage_ledger`. The defects emerge specifically at edge cases, exception handlers, and rejection branches.

---

## 4. Conclusion & Verdict

**Verdict**: **REQUEST_CHANGES**

Milestone 2 cannot be approved in its current state. The following 5 issues must be resolved by Worker M2:

1. **Scan Coverage Attrition Accounting**: Ensure `stats.evaluated` and `stats.rejected` correctly reconcile across all error paths: `requested == unavailable + skipped + evaluated`.
2. **Preserve Degradation Flags in Rejection Paths**: Pass `is_timeframe_degraded=is_timeframe_degraded` and `fallback_timeframe=fallback_timeframe` to `_make_no_trade` in `signal_pipeline.py` at line 440 (insufficient confluence) and line 564 (score too low).
3. **Fail-Closed Derivatives Exception Handling**: In `signal_pipeline.py` (lines 645 and 675), if `candidate.asset_class` is `FUTURES` or `OPTIONS` and an exception occurs, fail closed by returning `_make_no_trade` and `_make_rejection` rather than letting the signal fall back to `EQUITY_LONG` / `EQUITY_SHORT`.
4. **Dynamic Expiry Duration Robustness**: Guard `SignalEngineConfig.get_expiry_duration_seconds()` against `ValueError` on malformed timeframe strings (`"m"`, `"h"`, `"d"`).
5. **Real E2E Test Suite for Feature 14**: Update `backend/tests/e2e/test_tier1_features.py` (`test_f14_scan_coverage_ledger`) to include genuine assertions for `len(result.coverage_ledger) == len(universe)` and `stats.requested == stats.unavailable + stats.skipped + stats.evaluated`.

---

## 5. Verification Method

To verify these findings and confirm post-fix correctness:

### Step 1: Verify Degradation Retention on Rejection
```python
import asyncio
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.signal_engine.models import CandidateRecord, AssetClass, SignalEngineConfig, DataProvenance

config = SignalEngineConfig(primary_timeframe="15m", mtf_timeframes=["5m"])
candidate = CandidateRecord(symbol="TEST", last_price=100.0)
quote = {"ltp": 100.0, "is_live": True}
# Empty primary 15m candles, only 5m candles present
candles = {"5m": [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000} for _ in range(30)]}

sig, rej = asyncio.run(evaluate_candidate_signal(candidate, candles, quote, True, None, config))
# If rejected due to confluence or score:
assert sig.is_timeframe_degraded is True, "Degradation flag must be preserved on rejection"
assert sig.fallback_timeframe == "5m", "Fallback timeframe must be recorded on rejection"
assert sig.provenance == DataProvenance.DEGRADED, "Provenance must be DEGRADED on rejection"
```

### Step 2: Verify Derivatives Exception Fail-Closed
```python
candidate = CandidateRecord(symbol="NIFTY", asset_class=AssetClass.FUTURES, last_price=24000.0)
# Provide invalid futures_data that triggers exception in FuturesEngine
sig, rej = asyncio.run(evaluate_candidate_signal(candidate, candles, quote, True, None, config, futures_data={"invalid": True}))
assert sig.direction.value == "NO_TRADE" or sig.signal_type.value == "NO_TRADE"
assert "EQUITY" not in sig.signal_type.value, "Futures candidate must never leak as equity signal"
```

### Step 3: Verify Attrition Reconciliation
```python
from backend.app.signal_engine.models import ScannerPipelineStats

stats = ScannerPipelineStats(requested=20, unavailable=5, skipped=3, eligible=12, evaluated=12, qualified=4, rejected=8)
assert stats.requested == stats.unavailable + stats.skipped + stats.evaluated
assert stats.evaluated == stats.qualified + stats.rejected
```

### Invalidation Conditions:
- If a candidate evaluated with fallback candles returns `sig.is_timeframe_degraded is False` upon NO_DIRECTION or SCORE_TOO_LOW rejection, Issue 2 is reproduced.
- If a FUTURES candidate whose futures engine raises an error produces `SignalType.EQUITY_LONG`, Issue 3 is reproduced.
- If `SignalEngineConfig(primary_timeframe="m").get_expiry_duration_seconds()` raises `ValueError`, Issue 4 is reproduced.
- If `test_f14_scan_coverage_ledger` does not test `coverage_ledger` length or attrition reconciliation, Issue 5 is confirmed.
