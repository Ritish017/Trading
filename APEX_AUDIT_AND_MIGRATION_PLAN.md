# APEX Current-State Audit and Migration Plan

Date: 2026-08-09  
Scope: `C:\Tradinf2` working tree  
Decision: documentation and planning only; no production execution path was rewritten during this audit.

## Executive assessment

APEX has a useful UI prototype and a small Python quant prototype, but it is not yet a real-data personal trading system. The current working tree is also mid-migration: the committed repository contains the original root-level Vite app, while the working tree deletes that app and adds an untracked `frontend/`, `backend/`, and documentation structure.

The most important safety finding is that the current backend starts with `DevMockProvider` regardless of `ACTIVE_BROKER_PROVIDER`, while the frontend generates random prices and candles when the WebSocket is unavailable. This must be removed from the production execution path before any feature is described as live.

Baseline checks performed:

- Backend tests: `6 passed`.
- Frontend build: passes with Vite.
- Frontend lint/type check: does not run; `frontend/tsconfig.json` is missing and `tsc --noEmit` prints the compiler help.
- Database migrations: not present.
- Redis/event bus: not present; the health endpoint reports an in-memory placeholder.
- Real broker connectivity: not implemented; provider classes are stubs.

## 1. Current architecture assessment

### Repository shape

| Area | Current state | Assessment |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind v4 in `frontend/` | Reusable terminal components exist, but the app shell is still data-driven by constants and browser state. |
| Backend | FastAPI modules under `backend/app/` | Good initial module names, but `main.py` owns global provider, engine, AI, and paper-trading instances. |
| Data access | SQLAlchemy async connection and declarative models | `init_db()` calls `create_all()`; no Alembic migrations, repositories, transactions, or durable runtime state. |
| Market data | `MarketDataProvider` interface plus Upstox, Dhan, and dev mock classes | Only the dev mock produces ticks. Upstox and Dhan REST/WebSocket methods are placeholders. |
| Quant | Pandas indicator functions, options helpers, regime helper | Useful starting point, but incomplete relative to the product brief and not consistently guarded against insufficient/invalid data. |
| Strategies | One hard-coded `StrategyHypothesis` | Not yet a user-defined strategy DSL or versioned strategy registry. |
| Backtesting | Single long-only event loop | It has friction and a basic split label, but not a valid walk-forward/robustness framework. |
| Paper trading | In-memory `PaperTradingEngine` plus browser fallback | Not durable, not driven by a backend market-data stream, and risk checks are not wired into order execution. |
| AI | Three Python classes | The market report contains fabricated defaults; the strategy agent returns a fixed hypothesis; no internal retrieval/tool layer exists. |
| Observability | Logging and four health routes | Health routes report optimistic status without probing the actual database, Redis, or provider. |

### Reusable assets

Keep and adapt these rather than rewriting the terminal wholesale:

- `frontend/src/components/`: watchlist, index ticker, candle chart, options summary, FII/DII panel, command palette, AI drawer, paper modal, replay modal, and learning section.
- `frontend/src/types/indianMarket.ts`: the existing Indian-market view models are a useful presentation boundary, but should be replaced or generated from API contracts over time.
- `frontend/src/components/IndianCandleChart.tsx`: reusable chart presentation after candles and indicators come from an API/WebSocket store.
- `frontend/src/components/NSEWatchlist.tsx`, `IndexTickerBar.tsx`, `FIIDIITracker.tsx`, `OptionChainSummary.tsx`, and `SEBIAnnouncementsFeed.tsx`: good terminal panels once their props carry provenance and freshness.
- `backend/app/quant_engine/indicators.py`, `options.py`, `regime.py`, and `candle_engine/aggregator.py`: useful seeds for deterministic libraries, subject to contract and correctness tests.
- `backend/app/backtesting/event_driven.py`, `strategy_engine/dsl.py`, `paper_trading/engine.py`, and `journal/analytics.py`: useful experiments, not yet production engines.

The older generic trading components and helpers (`TradingChart`, `RightTradingPanel`, `OrderForm`, `Watchlist`, `mockAssets.ts`, and `technicalAnalysis.ts`) remain in the new frontend tree but are not imported by the current Indian-market `App.tsx`. They should be either deliberately archived or migrated behind a clear compatibility boundary; they should not silently become a second product model.

### Current request/data flow

```text
React App
  -> hard-coded INITIAL_* market objects
  -> browser localStorage for watchlist/balance/positions
  -> WebSocket /ws/ticks when available
  -> random browser fallback when unavailable
  -> POST /api/ai/* and /api/paper/order for selected actions

FastAPI main.py
  -> global DevMockProvider (always selected)
  -> in-memory candle aggregator
  -> in-memory paper engine
  -> placeholder Upstox/Dhan adapters
  -> create_all() database startup attempt
```

## 2. Technical debt report

### Blockers before real-data or real-money claims

1. **Provider selection is ignored.** `active_provider` is assigned to `mock_provider`; settings do not select Upstox or Dhan.
2. **Provider integrations are not implemented.** The provider methods log intent or return empty/static values. There is no authenticated REST client, WebSocket reader, protobuf decoding, reconnect loop, or subscription protocol.
3. **Browser simulation masks feed failure.** `frontend/src/App.tsx` generates random ticks and candles if the WebSocket is unavailable. A disconnected feed must instead show stale/offline state and last-known data.
4. **Market values are not sourced.** Indices, stock fundamentals, FII/DII, breadth, option summary, and announcements are rendered from `INITIAL_*` constants.
5. **AI output can fabricate facts.** Prompts and local fallbacks hard-code FII/DII values, PCR interpretation, catalysts, support/resistance, and trade setups. Missing data is not represented as `DATA_UNAVAILABLE`.
6. **Paper execution is not a controlled simulator.** The risk engine is never called; positions and orders are in memory; the browser can execute a local fallback when the backend fails; live ticks do not update backend positions.
7. **Persistence is not production-ready.** `database_url` is not declared in `Settings`, so the connection falls back to in-memory SQLite; database initialization errors are swallowed; migrations do not exist.
8. **Safety and network controls are incomplete.** CORS is `*` with credentials, there is no authentication boundary, rate limiting, audit log, kill-switch route, or provider credential lifecycle.

### High-priority correctness debt

- `NormalizedTick` is defined twice with incompatible field names (`open_interest` versus `oi`, `buy_qty` versus `bid_quantity`). Providers import the base model, while `data_engine/normalizer.py` defines another model that is not on the feed path.
- Candle aggregation does not deduplicate ticks, reject out-of-order data, handle cumulative-versus-per-tick volume, apply exchange sessions/time zones, or handle holidays and gaps. A late tick can move the active candle to an older bucket.
- Indicator functions do not establish a consistent insufficient-history policy and do not sanitize NaN/infinite values. `detect_support_resistance()` fabricates levels for empty/short input, which violates `DATA_UNAVAILABLE` semantics.
- Regime classification fabricates an EMA50 proxy when there are fewer than 50 rows and mentions VWAP in evidence without calculating VWAP.
- The event engine detects only two event families and its event model lacks the requested source, expiry, and evidence structure.
- The strategy engine has one fixed rule set; it has no safe parser, versioning, validation errors, universe/session model, or parameter provenance.
- The backtester uses the same bar's close to enter, checks target and stop on the same bar with a fixed precedence, supports one long position, and labels a 70/30 split as walk-forward without rerunning the strategy across rolling windows. It does not calculate the requested risk/performance set.
- The paper engine assumes a fixed 20% MIS margin and flat fees, without provider-specific configuration, taxes, order types, partial fills, stop/target triggering, short-position semantics, or mark-to-market updates.
- API payloads are mostly unbounded dictionaries/lists. Missing candle columns become server errors instead of structured validation responses.
- The frontend has no API client or query/cache layer, uses different UI and backend field naming conventions, and has no central data freshness/provenance model.
- `frontend/package.json` contains unused template-era dependencies and there is no local `tsconfig.json`, ESLint configuration, CI workflow, Docker/dev-compose setup, or repository `.gitignore`.

## 3. Mock-data dependency map

| Location | Mock/synthetic behavior | Current consumer | Required disposition |
| --- | --- | --- | --- |
| `frontend/src/data/indianMarketData.ts` | Hard-coded indices, stocks, FII/DII, breadth, options, and announcements | `frontend/src/App.tsx` renders these directly | Replace with API query/store data; retain only as test fixtures. |
| `frontend/src/utils/indianTechnicalAnalysis.ts` | Random initial candles, random depth, local AI report | `App.tsx`, chart, and fallback AI path | Remove from production imports; move deterministic fixtures to `tests/fixtures` or an explicit demo build. |
| `frontend/src/App.tsx` | `Math.random()` price fallback, random candle volume, localStorage as portfolio source of truth | Main application shell | Delete production fallback; display stale/offline status and make backend authoritative. |
| `backend/app/broker_providers/dev_mock.py` | Random ticks, historical candles, and option snapshot | Backend startup and WebSocket path | Keep only behind explicit `ENVIRONMENT=development`/test feature flag. Never default. |
| `backend/app/main.py` | Always instantiates and uses `DevMockProvider`; real-provider branch returns `LIVE_FEED_READY` without data | All quote/candle/WebSocket routes | Replace with provider factory and an explicit unavailable response until a provider is connected. |
| `backend/app/broker_providers/upstox.py` | Empty candle list and static option metrics | Provider abstraction | Implement only after checking current official docs; otherwise return a typed `NOT_CONFIGURED`/`NOT_IMPLEMENTED` state. |
| `backend/app/broker_providers/dhan.py` | Empty candle list and static option metrics | Provider abstraction | Same as Upstox; no fake success. |
| `backend/app/ai_engine/agents.py` | Local fallback produces bullish analysis and trade setup; prompt includes fixed FII/DII and catalysts; strategy ID is fixed `HYP-042` | AI endpoints and copilot | Use structured input snapshots and explicit unavailable/uncertain output; never fabricate market facts. |
| `frontend/src/data/mockAssets.ts` and `technicalAnalysis.ts` | Legacy generic asset/news/candle/order-book generators | Not imported by current Indian App, but still present | Archive or move to fixtures after confirming no legacy route depends on them. |
| `localStorage` keys in `App.tsx` | Watchlist, balance, and positions are persisted in browser | Paper trading and UI | Allow UI preferences only; migrate orders, positions, trades, and capital to backend persistence. |

## 4. Proposed architecture

The target remains a personal single-user system, not a SaaS platform. The design should be modular without adding tenants, billing, signup, or enterprise administration.

```text
React terminal
  API client + query cache + WebSocket store
        |
FastAPI routers (health, market, quant, options, strategies, backtests,
                paper, journal, AI, replay)
        |
Application services / command handlers
        |
Repositories       Event bus / stream       AI tool gateway
        |                    |                    |
PostgreSQL + TimescaleDB   Redis              specialist agents
        |
Provider adapters -> connection manager -> normalizer -> validator
                                  -> tick store / candle engine
                                  -> features -> events -> paper engine
```

Recommended backend boundaries:

- `app/api/`: thin FastAPI routers and Pydantic request/response contracts.
- `app/core/`: settings, clock, logging, feature flags, error types, and safety policy.
- `app/data_engine/`: provider factory, authenticated REST clients, WebSocket connection manager, subscription manager, retry/backoff, normalization, freshness, and provenance.
- `app/candle_engine/`: session-aware deterministic aggregation with idempotency and late-tick policy.
- `app/quant_engine/`: pure functions and immutable feature outputs; no provider or database imports.
- `app/event_engine/`: typed event detectors with source, evidence, confidence, and expiry.
- `app/strategy_engine/`: versioned rule schema, parser/compiler, validation, and signal generation.
- `app/backtesting/`: event clock, execution model, costs, portfolio accounting, metrics, walk-forward, robustness, and Monte Carlo.
- `app/paper_trading/`: order lifecycle, fills, margin policy, mark-to-market, risk gates, positions, and journal events.
- `app/ai_engine/`: specialist agents that call read-only internal tools and return validated JSON with facts, calculations, model output, interpretation, and uncertainty.
- `app/database/`: migrations, models, repositories, and transaction boundaries.

Frontend state should separate server state from UI state. Server state includes quotes, candles, options, flows, events, positions, orders, journal, and AI analyses. Local storage may retain panel layout, theme, selected watchlist, and command-palette preferences only.

## 5. Proposed database schema

Use PostgreSQL as the source of truth and TimescaleDB hypertables for high-volume timestamped data. Use UTC storage, an explicit exchange timezone/session calendar, decimal/numeric money and price fields where appropriate, provider/source metadata, and idempotency keys.

### Reference and market data

| Table | Purpose | Important constraints/columns |
| --- | --- | --- |
| `instruments` | NSE/BSE equity, index, future, and option contracts | Unique provider instrument key + exchange + tradingsymbol; active dates; tick/lot size. |
| `ticks` | Normalized market ticks | Hypertable on `timestamp`; instrument FK; provider event ID/idempotency key; freshness and received time. |
| `candles` | Deterministic OHLCV bars | Hypertable on `timestamp`; unique instrument/timeframe/start; session ID; source revision. |
| `indices` | Index snapshots/metadata | Instrument reference and index composition/source metadata. |
| `option_contracts` | Contract master | Underlying, expiry, strike, CE/PE, lot size, tradability dates. |
| `option_snapshots` | OI/IV/Greeks snapshots | Hypertable; contract FK; provider timestamp; raw/provenance fields. |
| `fii_dii` | Institutional cash/F&O flow | Session/date, segment, participant, net buy/sell, source. |
| `market_breadth` | Advances/declines/highs/lows/circuits | Session timestamp, exchange/universe, source. |
| `sectors` | Sector membership and snapshots | Instrument/sector relationship and relative-strength observations. |
| `news` | News and filings | Source URL/id, published time, retrieved time, symbol/entity links, content hash. |
| `corporate_events` | Results, dividends, splits, announcements | Event type, effective date, source, affected instruments. |

### Derived research and trading data

| Table | Purpose |
| --- | --- |
| `technical_features` | Versioned indicator/feature values by instrument, timeframe, and timestamp. |
| `market_events` | Detected events with type, severity, evidence, source, confidence, and expiry. |
| `signals` | Strategy-generated signals with strategy version and feature snapshot reference. |
| `strategies` | User strategy identity, status, and description. |
| `strategy_versions` | Immutable executable rule/config snapshots and code/schema version. |
| `backtests` | Run metadata, assumptions, data range, result summary, and validation status. |
| `backtest_trades` | Every simulated entry, exit, fill, cost, and reason. |
| `paper_orders` | Full order lifecycle and rejection/fill state. |
| `paper_positions` | Open/closed position accounting and mark-to-market state. |
| `paper_trades` | Realized fills and P&L ledger. |
| `portfolio_snapshots` | Equity, cash, margin, exposure, and NAV over time. |
| `risk_metrics` | Drawdown, VaR/expected shortfall if implemented, exposure, and circuit state. |
| `trade_journal` | Context, setup, rationale, emotion, mistake, lesson, and references. |
| `ai_analysis` | Prompt/input snapshot hash, structured output, model, latency, uncertainty, and provenance. |
| `research_experiments` | Hypothesis, parameters, datasets, runs, and conclusions. |

Use migrations for all schema changes. `create_all()` should not be the deployment mechanism.

## 6. Real API integration strategy

### Provider contract

Define one canonical provider-neutral contract for:

- authentication/session status;
- instrument lookup and provider instrument keys;
- historical candles;
- quote snapshots;
- live tick streaming;
- option chain snapshots;
- order execution capability metadata, kept separate from market data;
- rate limits, retries, and provider error classification.

`NormalizedTick` must exist in exactly one module and include `instrument_id`, provider event ID, exchange timestamp, receive timestamp, LTP, OHLC, volume semantics, bid/ask quantities, OI/OI change, provider, and freshness/live status. Preserve raw provider payloads only in a controlled raw-data boundary for debugging and replay.

### Rollout order

1. Choose one provider for the first live-data slice based on the available account and current official documentation.
2. Implement instrument master mapping and historical candles first; verify timestamps, intervals, symbol keys, and pagination against official examples.
3. Implement authenticated quote/WebSocket connection with heartbeat, subscription acknowledgement, reconnect/backoff, rate-limit handling, and explicit provider errors.
4. Normalize and validate provider messages before they enter the event bus or database.
5. Add a provider contract test suite using recorded fixtures; recorded payloads must be clearly marked and must not be presented as live.
6. Add the second provider only after the first provider passes data-quality and disconnect-recovery gates.

Do not invent endpoints, message formats, authentication flows, or option-chain semantics. Provider implementation work must consult and pin the current official API documentation at the time it is coded. Credentials remain backend-only and load from environment/secret storage.

### Failure behavior

Provider failure must produce a typed health state such as `DISCONNECTED`, `AUTH_REQUIRED`, `RATE_LIMITED`, `STALE`, or `NOT_CONFIGURED`. The UI may show the last valid value with `DATA STALE` and its age; it must never generate a replacement price.

## 7. Migration plan

### Safety rules for this working tree

- Do not reset or discard the existing uncommitted migration. First create a checkpoint commit or branch outside this audit.
- Keep the current `DevMockProvider` only for tests/demo mode while the real provider path is built.
- Do not enable real broker execution. Keep `REAL_TRADING_ENABLED=false` and make the execution router reject all real orders until every safety gate exists.
- Avoid changing the legacy generic UI and the Indian terminal in the same phase unless the change is a shared contract migration.

### Incremental migration sequence

1. **Baseline and contracts:** add repository ignore rules, frontend `tsconfig`, real lint/type-check configuration, API error envelope, typed health/freshness/provenance contracts, and a checkpoint of the current split.
2. **Runtime foundation:** add typed settings (`DATABASE_URL`, `REDIS_URL`, provider selection), dependency injection, structured logging, actual health probes, database migrations, and a Redis abstraction with a safe degraded mode.
3. **Market data vertical slice:** implement one provider's historical candles and quotes, instrument mapping, normalization, provenance, and a read-only `/api/market` slice. Remove browser random fallback from this slice.
4. **Streaming and candles:** implement provider connection management, subscriptions, reconnects, idempotency, session/calendar handling, deterministic candle tests, persistence, and frontend stale-state handling.
5. **Quant and event engine:** harden indicators, add missing indicators, typed feature snapshots, options events, market regime evidence, and event persistence. Keep calculations deterministic and independent of AI.
6. **Strategy and backtesting:** define a safe strategy schema, compile/validate rules, add cost/slippage/position models, eliminate look-ahead, implement train/validation/test and rolling walk-forward, then add robustness/Monte Carlo.
7. **Paper trading and journal:** move orders/positions/trades to the backend database, consume live normalized ticks, apply configurable provider-specific margin/cost policies, wire risk gates, and produce journal records from fills.
8. **AI research layer:** add read-only internal data tools, specialist agents, JSON schemas, provenance, uncertainty, timeouts, model output logging, and explicit `DATA_UNAVAILABLE`. AI may explain calculated results but cannot create market facts or execute orders.
9. **Terminal migration:** replace `INITIAL_*` props with server state one panel at a time; add freshness/source labels, options/FII/news/event panels, strategy lab, backtest results, journal, replay, and command actions only when their endpoint exists.
10. **Safety review:** run failure drills, security review, paper-trading acceptance tests, kill-switch tests, and an explicit human approval workflow. Real execution remains disabled by default and is outside the first production milestone.

## 8. Development phases and completion gates

| Phase | Deliverable | Exit gate |
| --- | --- | --- |
| 0. Baseline | Checkpoint current tree, fix tooling visibility, define contracts | Type-check/build/test commands all have meaningful pass/fail behavior. |
| 1. Foundations | Settings, migrations, health, logging, Redis interface | Database and Redis health endpoints probe reality; no swallowed startup failures. |
| 2. One real provider | Instrument mapping, historical candles, quote snapshot | Recorded contract tests pass; no mock values in the live route. |
| 3. Streaming | WS manager, normalizer, reconnect, freshness, candle persistence | Forced disconnect/reconnect and malformed-message tests pass. |
| 4. Quant | Indicator library, features, options, regime, events | Deterministic unit tests cover insufficient data, NaN, duplicates, and session boundaries. |
| 5. Research | Strategy schema, backtests, walk-forward, robustness | No look-ahead test passes; in/out-of-sample and assumptions are visible and reproducible. |
| 6. Paper trading | Live-data simulator, risk, costs, journal | Every fill is persisted, mark-to-market is reproducible, and risk rejection is enforced server-side. |
| 7. AI | Tool-using specialist agents and structured output | AI cannot answer with invented facts when required data is absent; latency/errors are observable. |
| 8. Terminal | Data-backed dashboard, lab, replay, learn, copilot | Every visible live value has source/timestamp/freshness; no nonfunctional buttons or random fallbacks. |
| 9. Safety hardening | Audit log, kill switch, security and operational drills | Real trading remains disabled unless explicit gates are configured and human confirmation is required. |

## Immediate next actions

The next implementation pass should be deliberately small:

1. Add the missing frontend type-check configuration and a repository checkpoint.
2. Make settings and provider selection truthful without yet pretending a provider is connected.
3. Remove the browser random fallback for the first market-data panel and show stale/offline status.
4. Add migration infrastructure and a real database health check before moving paper state out of memory.
5. Write provider-contract and data-quality tests before implementing a current official provider API.

Until those actions are complete, the app should be described as an Indian-market terminal prototype with simulated/degraded data paths, not as a live trading or production quant system.
