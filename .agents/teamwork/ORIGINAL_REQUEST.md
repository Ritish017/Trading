# Original User Request

## 2026-10-06T17:08:33Z

Continue the existing personal APEX trading and quantitative analysis workstation in C:\Tradinf2. Read docs/APEX_ANTIGRAVITY_MASTER_PROMPT.md as the complete implementation brief, docs/APEX_PROJECT_CONTEXT.md for prior decisions, and docs/APEX_ANTIGRAVITY_RESEARCH.md for current findings. Implement the automated signal-to-paper-entry-to-monitoring-to-exit-to-journal workflow, with a simple educational UI and evidence-grounded AI while keeping real-money broker execution strictly disabled.

Working directory: C:\Tradinf2
Integrity mode: development

## Requirements

### R1. Baseline Integrity and First-Wave Defect Repairs
- Reproduce and fix the TypeScript compilation diagnostics in `frontend/src/stores/canonicalQuoteStore.ts` (unresolved `incomingTs` references) so `npm run lint` (`tsc --noEmit`) passes cleanly.
- Guard FastAPI and worker lifespans (`backend/app/main.py` and `worker.py`) with explicit exception/cancellation handlers to ensure clean task cancellation and provider disconnection.
- Enforce authentication on paper order and close endpoints (`frontend/src/App.tsx`, `backend/app/main.py`), and ensure failed close requests do not remove positions from local client state.
- Remove hardcoded development credentials from frontend components and treat only valid backend order states (not generic HTTP 200) as fill confirmations.

### R2. Server-Authoritative Decision Contract & Market Ingestion
- Enforce one versioned, server-authoritative decision contract for Indian equities, futures, and options.
- Require genuine contract parameters (expiry, lot size, tick size, open interest, volume, spread, margin) for derivatives, or explicitly fail closed with an UNAVAILABLE / missing-data state rather than substituting synthetic numbers.
- Maintain an instrument master and scan coverage ledger recording requested, eligible, evaluated, unavailable, skipped, and rejected counts with evaluation timestamps.
- Ensure feature caching and deterministic evaluation: LONG geometry requires `stop < entry < targets`, and SHORT geometry requires `targets < entry < stop`.

### R3. Authoritative Paper Execution, Exit Lifecycle, and Journaling
- Unify paper trading and mark-to-market into a single authoritative server ledger, eliminating discrepancies between UI cache and backend state.
- Revalidate setup qualification, freshness, expiry, hard risk gates, and portfolio risk limits at order submission time using durable idempotency keys.
- Implement side-correct automated exits for long and short positions: take-profit targets, stop-losses, strategy invalidation, time/expiry exits, and manual closes with conservative fill policies during same-bar gap events.
- Persist an immutable journal linking every entry and exit to its original decision fingerprint and calculation evidence.
- Ensure crash recovery restores orders, open positions, cash balance, and monotonic audit sequence numbers.

### R4. Grounded AI Explanations and Educational UI
- Redesign the primary navigation into three clear views: **Today** (data health, actionable signals, no-trade reasons), **Positions & Journal** (canonical paper portfolio, P&L net of costs, exit logs), and **Learn** (contextual educational breakdown of setup mechanics).
- Preserve existing advanced analytical, backtest, and command-center views under an **Advanced** navigation group.
- Implement async runtime AI explanations for signals, no-trade states, and journal reviews strictly citing deterministic calculation evidence.
- Ensure AI failures, timeouts, or budget exhaustion degrade gracefully to visible notices without impairing core trading or exit execution.

### R5. Security, Local Operation, and Real-Money Guardrails
- Real-money order execution remains permanently disabled; live broker routing is strictly prohibited.
- Bind services to local loopback, keep API keys and provider tokens server-side, and isolate testing fixtures from personal session data.

## Acceptance Criteria

### Baseline & Code Quality
- [ ] `npm.cmd run lint` (`tsc --noEmit`) and `npm.cmd run build` complete with zero TypeScript errors.
- [ ] Backend test suites for safety, security, and paper accounting pass without regressions.

### Signal & Decision Pipeline
- [ ] Replay evaluation produces valid deterministic entry, stop, target, and risk metrics adhering to long/short geometry.
- [ ] Incomplete F&O chain or margin inputs fail closed with explicit missing-evidence records rather than default mock values.
- [ ] Universe scan reports full coverage metrics (eligible, evaluated, skipped, rejected) and evaluation timestamps.

### Paper Execution & Exit Lifecycle
- [ ] Submitting an expired or invalidated signal is rejected with an explicit error.
- [ ] Concurrent or duplicate order submissions do not create duplicate fills or overdraw capital.
- [ ] Replayed price movement crossing stop or target triggers side-correct position closure, updates realized P&L net of modeled costs, and generates an audit log entry.
- [ ] A simulated server restart with an open paper position cleanly recovers position state, cash balance, and monotonic audit sequence.

### UI & Security Guardrails
- [ ] Failed paper-close requests display clear error notifications and leave the open position intact in the UI.
- [ ] All mutation endpoints require valid authentication, with no API secrets exposed in frontend bundles or query strings.
- [ ] When AI explanation service times out or is offline, deterministic signals and automated paper exits remain 100% operational.

## 2026-10-07T14:59:22Z

Resume execution of APEX workstation project from current persisted state.
