# APEX — consolidated project context

Compiled 6 October 2026 from accessible prior chats and the lifecycle review in the current chat. The user confirmed that “FX trading” meant APEX. This document preserves project history and decisions; it is not a new production certification or authorization to enable live orders.

## 1. The user's actual goal

Build a personal, agentic trading and quantitative research system for Indian stocks, futures, and options. This is for the user's own use, not a client product or a subscription business.

The desired result is a clear trading decision: instrument, entry, exit, stop loss, and the supporting evidence. Automate data collection, calculations, strategy evaluation, research, and signal generation so the user can act on the resulting entry and exit guidance.

The user's later clarification in **Plan Production Trading App** is more authoritative than an earlier assistant interpretation:

- Base decisions on calculations, statistics, probability, mathematics, and explicit strategy conditions.
- Evaluate the applicable strategies for each instrument rather than presenting isolated indicators or an unexplained AI opinion.
- Expand strategy knowledge, reasoning, and research capability over time.
- Use AI extensively as a supplement to quantitative computation while keeping decisions grounded in tested conditions.
- Produce granular entry, exit, and stop-loss signals across Indian equities and derivatives.
- Preserve the personal-project scope.

The user also expressed an ambition to perform real trades. This is a desired future capability, not evidence that the existing paper engine can safely route broker orders. Automatic analysis and automatic real-money execution are distinct capabilities. The exact approval policy for future live execution remains unresolved.

## 2. Project identity and separate historical work

Current APEX repository: [Ritish017/Trading](https://github.com/Ritish017/Trading).

Local checkout: `C:\Tradinf2`.

Previously supplied deployment: [apex-trading-lab.vercel.app](https://apex-trading-lab.vercel.app/). Deployment health was not rechecked while compiling this document.

The current application combines a FastAPI backend, React/Vite frontend, live market-data integration, paper trading, research engines, and a separate persistent market worker. PostgreSQL is the intended production persistence layer; SQLite serves local development and tests.

An older **Build trading platform** chat worked in `C:\Trading\trading-platform`. Its India-and-crypto master prompt specified a much broader stack: Next.js, NautilusTrader, InfluxDB, Redis, Redpanda, PostgreSQL, MLflow, Grafana, and rule-based/ML/RL strategies. That is a separate historical implementation track. Do not assume its infrastructure, phase numbering, or completion status applies to APEX.

The earlier broad prompt included commodities and crypto. The later APEX clarification prioritizes Indian stocks, futures, and options. No separate forex broker, currency-pair universe, or forex execution requirement was established in the retrieved APEX chats.

## 3. Target architecture already discussed

The **Build APEX quant architecture** chat supplied this intended pipeline:

1. Authentic data and data-quality checks.
2. Market-feature computation.
3. Regime classification and multi-timeframe analysis.
4. Evaluation of 20 strategies.
5. Correlation analysis and confluence.
6. Signal decision for equity, futures, or options.
7. Risk engine and entry/stop/target construction.
8. Paper trading and signal observatory.
9. Future market observations and outcome measurement.
10. Performance assessment, walk-forward validation, confidence calibration, and research feedback.

The architecture is a research loop, not only an order-entry screen. A signal must have traceable inputs and outcomes. An absence of a qualified opportunity must remain an honest no-trade result.

The historical 20-strategy pipeline is an existing architecture target, not proof that all 20 strategies provide an edge. The later request to add strategies does not establish a new fixed strategy count or a requirement that every strategy agree on every trade.

## 4. AI and development workflow preferences

The user requested research, an implementation plan, and prompts for building the full application using Antigravity and `/goal`. The request named “gemini flash3.8”; availability and the exact intended model were not verified in the retrieved exchange. Do not silently assume that model identifier is valid.

The latest visible planning message requests those build prompts. The retrieved planning chat contains no completed response to that final request. Do not mark the prompt pack as delivered.

The earlier implementation request also required a `context.md` file, updated after each phase, and continuation from the first incomplete phase. Apply that continuation principle to APEX: inspect actual state, preserve completed work, and record concrete evidence at each milestone.

AI roles discussed include research assistance, explanations, coaching, strategy research, and copilot analysis. Quantitative calculations, risk checks, durable records, and actual broker responses must remain distinguishable from generated narrative.

## 5. Reported earlier implementation and validation

These are historical chat results, not checks rerun for this context document.

### APEX engineering pass

**Build APEX quant architecture** reported:

- Corrected SQLite pooling to prevent retained `aiosqlite` threads from keeping short-lived processes alive; PostgreSQL pooling was preserved.
- Updated Pydantic serialization.
- Corrected command-center provider identity to canonical `UPSTOX`.
- Corrected activated LONG/SHORT direction and forward-window MAE/MFE handling in strategy research.
- Added `docs/APEX_PREMIUM_CERTIFICATION.md`.
- Final backend run: **295 passed**.
- Frontend type check and production build: passed.
- Authenticated, read-only Upstox quote probe: normalized quote received.
- No real orders placed.

The recorded verdict was **ENGINEERING PASS_WITH_LIMITATION**. Statistical edge and live-trading readiness were not established. Recorded limitations included PostgreSQL runtime verification, browser E2E, live WebSocket/session recovery, live options-chain validation, and authentic historical/forward outcome evidence.

### Older India-and-crypto implementation

**Build trading platform** reported a Phase 2 market-data implementation in `C:\Trading\trading-platform`, including publishing, Binance streaming/reconnects, NSE historical ingestion, feature-gated Kite integration, metrics, and a Grafana dashboard.

Reported validation: focused lint passed and **10 selected tests passed**. The one-hour live NSE ingestion acceptance remained pending. Those results do not certify current APEX.

## 6. Later production review and its implications

**Plan Production Trading App** reviewed the repository and deployment and produced `APEX_Production_Development_Plan.md` in a cloud workspace. The visible response described 18 findings, 20 implementation tickets, and an inventory of 283 files. The full downloadable plan was not retrieved into this local document; its exact ticket contents must not be reconstructed from its summary.

Reported findings requiring fresh verification before repair:

- Frontend paper-order requests omitted required authentication.
- A failed position-close request could still remove a position from the UI.
- Some paths used synthetic historical candles or substitute prices/volumes.
- A claimed successful live-session report contained zero ticks and fixture data.
- A complete real-broker order lifecycle and reconciliation subsystem was absent.
- Fee schedules required updating and dating.
- Broker-compatible static outbound-IP hosting needed verification.

This review reported syntax parsing of 179 Python files, but functional tests were blocked by dependency-installation/network limitations in that environment.

The apparent difference from the earlier 295-test engineering pass is not evidence that either review should be ignored. Passing local tests does not establish correct deployed UI behavior, authentic live-session evidence, production database behavior, or real-broker execution reliability. Preserve both sets of evidence and verify each relevant issue against the current checkout.

Do not reuse historical tax rates, broker restrictions, hosting-address counts, licensing interpretations, or provider-model claims as current facts. Those need primary-source verification when implementation depends on them.

## 7. Proposed development sequence from the prior plan

This sequence was an assistant proposal, not a completed implementation or a fully accepted execution policy:

1. Repair data truthfulness, authenticated requests, portfolio consistency, and reproducible CI.
2. Establish durable production runtime: PostgreSQL migrations, instrument master, exchange calendar, dated costs, and persistent workers.
3. Build broker execution separately: trading authentication, order previews, risk checks, durable order states, fills, and reconciliation.
4. Validate sandbox/failure behavior, backup recovery, and complete shadow sessions.
5. Begin restricted live capability with user-confirmed limit orders for an approved NSE delivery-equity universe.
6. Expand to intraday, BSE, supervised automation, and derivatives after the relevant validation.

Upstox was proposed as the first execution integration because its data integration already existed. Read-only market-data access was explicitly distinguished from separate trading authentication. Existing protections must not be bypassed by treating live execution as a flag change.

The user subsequently emphasized the broader signal-generation and agentic-analysis goal. The next plan should serve that goal explicitly rather than reducing the project to manual order entry alone.

## 8. Current lifecycle review: narrow supporting work

The current chat inspected local and remote `main` at commit `34849a90596eb8af218268cdebabb561ca627ede`.

The known-issues entry for `@app.on_event("shutdown")` is stale: `main.py` already uses `asynccontextmanager`. The remaining demonstrated issue is an unguarded lifespan `yield`, which skips provider disconnect when an exception or cancellation is injected into the context.

A proposed `try/finally` patch and tests were created under:

`C:\Users\kurma\OneDrive\Documents\ChatGPT\AirBNB\lifecycle-review`.

Production source was not patched. The proposal passed **17 focused checks**; the original app failed the two exceptional-exit checks. Selected existing worker/lifecycle/safety/database suites passed **34 checks** using isolated SQLite. PostgreSQL and cloud behavior remain unverified.

Preserved ownership:

- API: initialize DB/state/provider, subscribe symbols, conditionally start market WebSocket, disconnect its provider.
- Worker: enforce paper-only and frozen-config rules, preflight, heartbeat, runner startup, recovery, and shutdown.
- Session runner: cancel and await background tasks, disconnect provider, record shutdown without premature finalization, finalize at the existing close boundary, then close/flush evidence.
- Audit system: recover sequence maxima, preserve event order, flush, seal, and persist reports.

Equity close remains 15:30 IST; F&O/session close remains 15:40 IST in the reviewed implementation. This is application behavior, not a newly verified exchange timetable. A mid-session worker shutdown must not falsely certify the trading session as completed.

This lifecycle issue supports reliability but does not replace the larger APEX product objective. The frontend bundle warning is unrelated to the context-recovery request.

## 9. Unresolved work to carry forward

- Recover the full cloud production plan and reconcile its tickets with the current checkout.
- Deliver the requested Antigravity build prompts, using a verified available model and clear milestone evidence.
- Verify the reported frontend authentication and failed-close behavior.
- Remove or clearly separate misleading synthetic/substitute data from authentic research inputs.
- Prove durable production persistence, migrations, recovery, and backup restore.
- Validate signal quality on authentic historical and forward data; measure costs, sample size, calibration, and regime robustness.
- Define the future live-execution approval policy and risk limits.
- Build and validate the broker order state machine, reconciliation, and interruption handling before live use.
- Keep actual progress, proposed work, historical results, and current verification separate in subsequent context updates.

## 10. Retrieved discussion sources

Titles are copied verbatim from the app:

| Chat | ID | Context recovered |
|---|---|---|
| Plan Production Trading App | `6ac3be22-c044-83ee-94ef-07144b2513cd` | Personal-project clarification, desired signal automation, real-trading ambition, production findings, requested Antigravity prompts |
| Build APEX quant architecture | `01a081a0-86b5-7533-ab7f-47d206a35bd1` | Target pipeline, scoped repairs, 295-test historical pass, certification limits |
| Build trading platform | `019e2735-7107-7250-a9d6-6173820a9d71` | Separate India/crypto build prompt, phase/context tracking, Phase 2 work |
| Open Source Trading Tools | `6a09bdc8-c7f0-8320-8547-6629db1a51f5` | Earlier open-source research, including OpenAlgo, Freqtrade, OctoBot, Lumibot, and Lean in the retrieved portion |
| Review FastAPI lifespan refactor | `01a111f9-5959-7d40-bb77-fa072d9a523e` | Separate lifecycle proposal and paper/worker ownership notes |
| Refactor FastAPI lifespan | `01a111f7-1e68-7473-9420-48d561467657` | This chat's tested proposal and confirmation that FX meant APEX |

Coverage is limited to accessible retrieved chats and their visible content. No claim that every past APEX conversation or every attachment has been recovered.

## 11. Antigravity build brief delivered, 6 October 2026

The subsequent user request clarified the build harness as Antigravity and the desired builder as Gemini 3.8 Flash, while also mentioning 3.5 Flash. Both model identifiers were verified in official Google documentation. Current Antigravity documentation lists 3.8 Flash; the installed account/model still needs verification. Public model benchmarks are not a measured Antigravity-versus-Codex result for APEX.

Delivered `docs/APEX_ANTIGRAVITY_RESEARCH.md` and `docs/APEX_ANTIGRAVITY_MASTER_PROMPT.md`. The brief specifies a private single-user application, eight scoped engineering roles with bounded native parallelism, milestone gates, complete signal/paper/exit/journal workflows, simple UI, evidence-grounded runtime AI, and preserved live-order restrictions.

Fresh verification: 16 selected backend security/paper/safety tests passed. Frontend type checking failed with three `incomingTs` TS2304 diagnostics. Vite build passed with a 563.26 kB JS bundle warning. Targeted source audits identified actionable integration/data/derivatives/exit/security gaps recorded in the research document. No application source was edited or live trading enabled.
