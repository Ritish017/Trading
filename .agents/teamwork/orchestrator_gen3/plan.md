# APEX Orchestration Plan — Generation 3

## Overview
This plan governs the completion of Milestones 2 through 5 and Final Verification for the APEX workstation in `C:\Tradinf2`.

## Execution Steps

### Milestone 2: Server-Authoritative Decision Contract & Market Ingestion (R2)
- **Features**: F10, F11, F12, F13, F14 + base engine `.evaluate()` adapter wiring.
- **Iteration Cycle**:
  1. Dispatch Explorer (`teamwork_preview_explorer`) to investigate current implementations in `backend/app/signal_engine/` (`options_engine.py`, `futures_engine.py`, `validation_gates.py`, `signal_pipeline.py`, `scanner.py`, `models.py`) and corresponding tests in `backend/tests/e2e/test_tier1_features.py` and `test_tier2_boundaries.py`.
  2. Dispatch Worker (`teamwork_preview_worker`) with Explorer findings and mandatory integrity warning to implement:
     - F10: Derivatives fail-closed on incomplete parameters + attach `.evaluate()` on base `OptionsEngine` and `FuturesEngine`.
     - F11: Timeframe degradation flag (`DEGRADED`).
     - F12: Dynamic signal expiry based on timeframe.
     - F13: Strict directional geometry checks (LONG: `stop < entry < targets`, SHORT: `targets < entry < stop`).
     - F14: Scan coverage ledger (`ScannerPipelineStats`).
     - Verify with `pytest backend/tests/e2e/test_tier1_features.py -k "options or futures or geometry or scanner or expiry"` and tier 2 boundary tests.
  3. Dispatch 2 Reviewers (`teamwork_preview_reviewer`) independently.
  4. Dispatch 2 Challengers (`teamwork_preview_challenger`).
  5. Dispatch Forensic Auditor (`teamwork_preview_auditor`).
  6. Gate check -> Pass criteria met -> Advance to M3.

### Milestone 3: Authoritative Paper Execution, Ledger, Automated Exits, Journaling (R3)
- **Features**: F15, F16, F17, F18, F19, F20, F21.
- **Iteration Cycle**:
  1. Dispatch Explorer for M3 scope across `backend/app/paper_trading/`.
  2. Dispatch Worker with Explorer report and integrity warning.
  3. Dispatch Reviewers, Challengers, and Forensic Auditor.
  4. Gate check -> Advance to M4.

### Milestone 4: Grounded AI Explanations and Educational UI (R4)
- **Features**: F22, F23, F24, F25, F26.
- **Iteration Cycle**:
  1. Dispatch Explorer for UI navigation & AI explanation engine.
  2. Dispatch Worker with Explorer report and integrity warning.
  3. Dispatch Reviewers, Challengers, and Forensic Auditor.
  4. Gate check -> Advance to M5.

### Milestone 5: Security, Local Operation, Guardrails Verification (R5)
- **Features**: F27, F28, F29, F30.
- **Iteration Cycle**:
  1. Dispatch Explorer for security invariant validation.
  2. Dispatch Worker to seal any remaining security/loopback gaps.
  3. Dispatch Reviewers, Challengers, and Forensic Auditor.
  4. Gate check -> Advance to Final Verification.

### Milestone Final: 100% E2E Test Suite Pass Rate (Tiers 1-4)
- Run Tier 1 (`test_tier1_features.py`), Tier 2 (`test_tier2_boundaries.py`), Tier 3 (`test_tier3_combinations.py`), Tier 4 (`test_tier4_scenarios.py`).
- Run frontend typecheck/lint: `npm run lint` / `npm run build`.
- Final Forensic Audit: full repo audit.
- Report completion to parent Sentinel.
