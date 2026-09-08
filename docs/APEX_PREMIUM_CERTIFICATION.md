# APEX Premium Certification

**Run date:** 2026-09-08  
**Scope:** Signal Intelligence, risk, F&O, persistence, paper-trading safety, API acceptance, and frontend build.  
**Verdict:** **ENGINEERING PASS_WITH_LIMITATION — STATISTICAL EDGE NOT ESTABLISHED**

## Executive summary

APEX now has an implemented, test-covered path matching the requested architecture:

`authentic/canonical data -> data-quality gates -> features -> regime + MTF -> 20 strategies -> correlation-aware confluence -> decision -> equity/futures/options -> risk -> paper ledger -> observatory/persistence -> outcomes -> performance/calibration/walk-forward`.

This run fixed three correctness defects discovered through regression testing:

1. SQLite async connections remained pooled in short-lived processes, leaving `aiosqlite` worker threads alive and preventing persistence tests from exiting. SQLite now uses `NullPool`; PostgreSQL retains normal SQLAlchemy pooling.
2. The command-center snapshot exposed an Upstox transport label (`UPSTOX_WS_PROTOBUF`) as if it were a separate market-data provider. It now reports the canonical broker identity (`UPSTOX`), while transport provenance remains on the canonical quote.
3. Historical research treated a bidirectional strategy (`BOTH`) as bearish for every activation. It now records the activated `LONG` or `SHORT` side per episode, closes an episode on a side change, and calculates return/MAE/MFE from that actual side.

The implementation is not evidence that any strategy is profitable. The checked research and calibration code is an engineering capability; no authenticated historical performance dataset or live forward outcome sample was supplied or independently validated during this run.

## Architecture and repository audit

The implementation is distributed across these verified layers:

| Requested layer | Implemented location |
| --- | --- |
| Authentic data and canonical store | `backend/app/broker_providers/`, `backend/app/market_data/`, `backend/app/candle_engine/` |
| Data quality and provenance | `market_data/service.py`, `signal_engine/validation_gates.py`, acceptance provenance tests |
| Market features, regime, MTF | `quant_engine/features.py`, `quant_engine/regime.py`, `signal_engine/multi_timeframe_engine.py` |
| 20 strategies and correlation-aware confluence | `strategy_engine/registry.py`, `evaluator.py`, `signal_engine/confluence_engine.py` |
| Signal decision, risk, entry/stop/targets | `signal_engine/signal_pipeline.py`, `risk_engine/risk.py`, sizing and stop/target engines |
| Equity, futures, options | `signal_engine/futures_engine.py`, `options_engine.py`, `transaction_cost.py` |
| Paper ledger and observatory | `paper_trading/`, `paper_engine/`, `signal_store.py`, database repositories |
| Outcomes, performance, calibration, walk-forward | `outcome_engine.py`, `performance_engine.py`, `calibration_engine.py`, `walk_forward.py`, `strategy_engine/research_engine.py` |

The worktree contained substantial pre-existing uncommitted APEX implementation. This certification pass preserved that work and made only scoped corrections listed above.

## Verification evidence

| Command / check | Observed result |
| --- | --- |
| `python -m pytest backend/tests/signal_engine -q --durations=15` | **39 passed** in 67.27s; lifecycle, restart, lookahead, financial invariants, F&O, costs, calibration, and walk-forward coverage passed. |
| `python -m pytest backend/tests/strategy_engine -q --durations=10` | **6 passed** in 21.04s; all 20 registered strategies and long/short conformance fixtures covered. |
| `python -m pytest backend/tests/acceptance -q --durations=15` | **26 passed** in 50.18s; database, security, provenance, paper, websocket, and quant acceptance coverage passed. |
| `python -m pytest backend/tests -q --durations=20` | **295 passed** in 282.30s (4m42s). |
| `npm run lint` | Passed (`tsc --noEmit`). |
| `npm run build` | Passed. Vite reports one non-blocking 551.91 kB minified JavaScript bundle warning. |
| Redacted Upstox read-only REST probe | `connected=True`, normalized `NIFTY 50` quote received, `source=UPSTOX`, `is_live=True`; no order endpoint was called. |

The backend suite emits five dependency warnings: FastAPI `on_event` deprecation and a third-party Google GenAI typing deprecation. They are not test failures but should be addressed before the next framework upgrade.

## Signal, risk, and F&O findings

- Data-quality gates reject insufficient history and zero-volume inputs; provenance tests cover synthetic/live-claim separation.
- The signal pipeline has deterministic confluence, stop/target geometry, R:R, and position-risk checks. Lookahead invariance tests passed at `T`, `T+1`, `T+5`, and later appended windows.
- Futures and options engines have independent decision and cost tests. Options calculations are guarded by available chain/Greek inputs rather than inventing missing values.
- Signal lifecycle and SQLite restart recovery passed. The signal observatory persists signal metadata, votes, rejection records, outcomes, and performance/calibration records through the signal repository.
- The one authoritative paper-trading flow is covered by paper acceptance tests, including idempotency and accounting checks.

## Quantitative findings

The system correctly separates opportunity score/heuristic confidence from calibrated probability, and reports insufficient sample conditions. This run did **not** establish expectancy, significance, out-of-sample stability, or live performance from authentic historical/forward samples. Therefore:

**Do not treat grades, heuristic confidence, or passing synthetic tests as evidence of alpha.**

## Certification matrix

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| Data provenance | PASS | Provenance/zero-trust acceptance tests and authenticated read-only Upstox quote passed. |
| Data quality | PASS | Validation and market-data acceptance tests passed. |
| Canonical data | PASS | Canonical market integrity tests passed. |
| 20 strategies, LONG/SHORT | PASS | Registry/conformance and acceptance determinism tests passed. |
| Lookahead, indicators, MTF, regime | PASS | Signal-engine lookahead suite passed. |
| Confluence and scoring | PASS | Confluence/correlation and scoring tests passed; score is not a probability. |
| Entry, stop, target, R:R, sizing, risk | PASS | Financial invariant tests passed. |
| Equity, futures, options, option selection | PASS_WITH_LIMITATION | Logic and fixtures pass; a live option chain/Greek E2E run was not performed. |
| Transaction costs | PASS_WITH_LIMITATION | Calculation tests pass; statutory rate source freshness/applicability must be periodically reviewed. |
| Signal lifecycle, persistence, observatory | PASS_WITH_LIMITATION | SQLite restart recovery passed; PostgreSQL runtime was not available. |
| Outcome, performance, calibration, walk-forward | PASS_WITH_LIMITATION | Engineering tests pass; no authentic empirical sample establishes edge. |
| Paper trading | PASS_WITH_LIMITATION | Acceptance tests pass on the local durable ledger; multi-process PostgreSQL reconciliation was not run. |
| API security | PASS | Security acceptance tests include fail-closed auth, ownership, IDOR, and CORS checks. |
| Realtime | PASS_WITH_LIMITATION | Websocket/protobuf acceptance tests pass; a live websocket market-session E2E was not run. |
| Frontend | PASS_WITH_LIMITATION | Type check and production build pass; browser/E2E interaction was not run. |
| Database | PASS_WITH_LIMITATION | SQLite persistence/atomic rollback/restart passed; PostgreSQL execution is **NOT_VERIFIABLE**. |
| Deployment | NOT_VERIFIABLE | No deployed environment, logs, worker lifecycle, or production configuration was exercised. |
| Live market data | PASS_WITH_LIMITATION | Read-only authenticated REST quote passed; this does not certify sustained session, websocket, or data completeness. |
| Statistical edge / live performance | NOT_VERIFIABLE | No validated authentic historical sample or live forward outcome dataset was available. |

## Remaining blockers and recommended next evidence

1. Run PostgreSQL integration tests against an isolated disposable PostgreSQL instance, including restart and multi-process reads.
2. Capture recorded authentic candles and option-chain snapshots with immutable provenance, then run chronological walk-forward and outcome studies.
3. Accumulate forward paper outcomes without parameter changes; report expectancy intervals, drawdown distribution, calibration, and regime stability only after the stated sample-size gates are met.
4. Run browser E2E against the deployed frontend/API and validate frontend/backend value agreement.
5. Perform a live-market-session websocket test with stale-feed/disconnect recovery. Never place a real order as part of certification.
6. Migrate FastAPI startup/shutdown decorators to a lifespan handler and plan code splitting for the frontend bundle.

## Final decision

**Engineering correctness:** PASS_WITH_LIMITATION. The checked code paths are deterministic, tested, provenance-aware, risk-gated, and fail closed for the exercised failure cases.  
**Statistical edge:** NOT ESTABLISHED.  
**Live trading readiness:** NOT CERTIFIED. APEX remains appropriate for controlled, provenance-tagged research and paper-trading validation until the external evidence above is collected.
