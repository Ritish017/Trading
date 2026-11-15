## 2026-10-07T15:17:11Z
You are the Worker subagent (worker_m2) implementing Milestone 2 (Requirement R2): Server-Authoritative Decision Contract & Market Ingestion.
Your dedicated working directory is:
C:\Tradinf2\.agents\teamwork\worker_m2\

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

First, read:
1. C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md
2. C:\Tradinf2\.agents\teamwork\PROJECT.md
3. The 3 explorer handoff reports:
   - C:\Tradinf2\.agents\teamwork\explorer_m2_1\handoff.md (Feature 10 & Base Engine .evaluate())
   - C:\Tradinf2\.agents\teamwork\explorer_m2_2\handoff.md (Features 11, 12, 13)
   - C:\Tradinf2\.agents\teamwork\spec_miner_m2_3\handoff.md (Feature 14 Scan Coverage Ledger & E2E Contracts)

Your assigned scope and tasks (Features 10 through 14):
1. Feature 10: Derivatives Contract Fail-Closed & Base Engine .evaluate():
   - In `backend/app/signal_engine/options_engine.py`:
     * Update `OptionsEngine.evaluate` to accept `chain` alias for `option_chain`, `capital`, `underlying_symbol`, `underlying_price`, `target_price`, `stop_loss_price`, `**kwargs`.
     * Handle both `OptionContract` dataclass instances and raw dicts. Default `days_to_expiry=14` if omitted.
     * Return `OptionAction.OPTIONS_DATA_INSUFFICIENT` when chain is empty/None (`is_valid=False`, `structure="UNAVAILABLE"`, `rejection_reason="OPTION_CHAIN_DATA_UNAVAILABLE"`).
     * If bid and ask are 0.0 or missing on a contract, set spread to 999.0% rather than 0.0% so missing quote spreads fail liquidity validation.
     * Keep alias `OptionsDecisionEngine = OptionsEngine`.
   - In `backend/app/signal_engine/futures_engine.py`:
     * Add `FUTURES_DATA_INSUFFICIENT = "FUTURES_DATA_INSUFFICIENT"` to `FuturesAction`.
     * Implement `.evaluate()` method directly on `FuturesEngine` accepting `(cls, symbol=None, spot_price=0.0, futures_price=0.0, days_to_expiry=14, oi=0, oi_change_pct=0.0, volume=0, lot_size=50, capital=1000000.0, underlying_direction="LONG", stop_loss_spot=None, underlying_stop=None, target_spot=None, underlying_target_1=None, underlying_target_2=None, underlying_symbol=None, underlying_price=None, dte=None, available_capital=None, **kwargs) -> FuturesDecision`.
     * Ensure that when volume is insufficient (`volume // max(1, lot_size) < cls.MIN_VOLUME_LOTS`), the rejection reason contains `"insufficient volume"` (e.g. `rejection_reason = f"LOW_FUTURES_LIQUIDITY: Insufficient volume ({volume_lots} lots < min {cls.MIN_VOLUME_LOTS})"`), so `assert "insufficient volume" in fut_decision.rejection_reason.lower()` passes.
     * Update `FuturesEngine.analyze` to accept pipeline kwargs (`underlying_symbol=None`, `underlying_price=None`, `dte=None`, `stop_loss_pts=None`, `target_pts=None`, `**kwargs`) without TypeError.
     * Keep alias `FuturesDecisionEngine = FuturesEngine`.

2. Feature 11: Timeframe Degradation Flag:
   - In `backend/app/signal_engine/models.py`: add `is_timeframe_degraded: bool = False` and `fallback_timeframe: Optional[str] = None` to `SignalDecision`.
   - In `backend/app/signal_engine/signal_pipeline.py`: when fallback candles from secondary timeframes are used, set `is_timeframe_degraded = True`, `provenance = DataProvenance.DEGRADED`, and populate them on the resulting `SignalDecision`.

3. Feature 12: Dynamic Signal Expiry:
   - In `backend/app/signal_engine/models.py`: add `get_expiry_duration_seconds()` to `SignalEngineConfig` that maps `primary_timeframe` (e.g., 1m=60, 3m=180, 5m=300, 15m=900, 30m=1800, 1h=3600, 1D=86400) * `signal_expiry_candles`.
   - In `backend/app/signal_engine/signal_pipeline.py`: compute `expiry_time` dynamically using `config.get_expiry_duration_seconds()`.

4. Feature 13: Directional Geometry Validation:
   - In `backend/app/signal_engine/validation_gates.py`: implement `gate_directional_geometry(direction: str, stop_result: Optional[StopLossResult], entry_price: Optional[float], targets: List[TargetLevel]) -> ValidationGate`.
     Enforce LONG (`stop < entry < targets`) and SHORT (`targets < entry < stop`). Fail closed with `ValidationGateResult.FAIL` on violations.
   - Wire `gate_directional_geometry` into `ValidationPipeline.run_hard_gates` with `direction` and `targets`.
   - In `backend/app/signal_engine/signal_pipeline.py`: pass `direction` and `targets` into `run_hard_gates`.

5. Feature 14: Scan Coverage Ledger:
   - In `backend/app/signal_engine/models.py`: extend `ScannerPipelineStats` with R2 fields: `requested`, `eligible`, `evaluated`, `unavailable`, `skipped`, `rejected`, `evaluation_timestamp`. Maintain full backward compatibility for existing fields with `model_post_init` sync.
   - Add `ScanCoverageLedgerEntry` model and `coverage_ledger: List[ScanCoverageLedgerEntry]` field on `ScannerResult`.
   - In `backend/app/signal_engine/scanner.py`: track attrition counts (`unavailable`, `skipped`, `eligible`, `evaluated`, `rejected`) and build the `coverage_ledger`.

6. Run verification tests:
   - Run: `pytest backend/tests/e2e/test_tier1_features.py -k "test_f10 or test_f11 or test_f12 or test_f13 or test_f14" -v`
   - Run: `pytest backend/tests/e2e/test_tier2_boundaries.py -k "geometry or options" -v`
   - Run: `pytest backend/tests/signal_engine/ -v`
   - Document commands, console outputs, and results in your handoff report.


## 2026-10-07T15:40:22Z
**Context**: Milestone 2 Implementation Status Check
**Content**: Your progress.md has not been updated since 15:17:45Z. Please update progress.md with your current progress across Features 10-14, and report your current status or blockers.
**Action**: Update progress.md and reply with your status.
