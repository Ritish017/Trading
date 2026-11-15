# APEX personal trading workstation — Antigravity execution brief

You are the lead engineer and quantitative systems integrator for my existing APEX application. Build the working application, including tests and a usable interface. Research and plans are intermediate artifacts, not the final deliverable.

## My outcome and scope

This application is for me alone. I want automated analysis of Indian equities, futures, and options that produces understandable entry, exit, stop-loss, target, position-size, and no-trade decisions. Internally, instruments must pass through relevant calculations, market conditions, strategies, confluence, and risk checks. Externally, the interface must be simple enough that I understand each decision and learn while using it.

Automate analysis, screening, monitoring, paper execution, journal recording, and evidence-based explanations. Build for dependable personal use, not a public SaaS. Do not add subscriptions, billing, tenant onboarding, social trading, copy trading, a marketplace, or an unnecessary infrastructure fleet.

Use existing code and architecture. Preserve working features and routes. The goal is an integrated application, not a new scaffold or parallel replacement application. Do not invent guaranteed returns or require profitable test outcomes to declare software tests successful.

Personal use does not remove requirements for secure credentials, authentication, reliable accounting, backups, honest data, or safe execution.

Default completion scope is automated authentic-data signal research plus fully functional paper position management. Existing real-order prohibitions must remain enforced. Prepare broker execution interfaces or sandbox checks only where needed; do not enable live trading, place real orders, change broker permissions, or deploy publicly without my separate explicit approval. Do not label the signal/paper release as a real-broker trading release.

## Starting context and model selection

1. Confirm the real repository root. Expected local checkout: `C:\Tradinf2`; repository: `https://github.com/Ritish017/Trading`. Do not work on the unrelated `C:\Trading\trading-platform` project.
2. Read applicable `AGENTS.md` instructions and `docs/APEX_PROJECT_CONTEXT.md`, `docs/APEX_ANTIGRAVITY_RESEARCH.md`, relevant certification documents, and `.agents/KNOWN_ISSUES.md`. Historical reports are leads, not current proof. Preserve my uncommitted work, databases, logs, and session evidence.
3. Inspect actual source and run a baseline before editing. Locate the first incomplete acceptance gate. Keep FastAPI, React/Vite, existing providers and research engines unless a demonstrated defect requires a scoped change.
4. Use Gemini 3.8 Flash as the selected builder model if my account and installation expose it. Verify the selected model and quotas. Do not silently switch to Gemini 3.5, a Pro model, or another paid model. If only 3.5 is available, report that and use the same bounded workflow if I have selected it.
5. Native subagents should inherit the selected builder model where supported. Verify the resolved model: a generic `flash` tier is not proof of an exact version. Do not assume all built-in Teamwork roles are user-configurable.
6. Builder model choice is separate from the model used inside APEX's runtime AI adapter. Configure the application model server-side with a documented, verified API identifier. Do not assume Antigravity credits or subscriptions cover application API calls.
7. Use an exposed higher effort setting for concurrency, numerical correctness, security review, and hard failures. Use medium for bounded implementation and lower effort for simple formatting only where supported. Never send unsupported reasoning settings. Keep task context short, complete, and evidence-based.

## Native parallel-agent execution

Use the installed Antigravity parallel harness, not role-playing several agents in a single response. Prefer `/teamwork-preview` when available for this multi-milestone build. Follow its initial brief approval and permission requirements. If unavailable, use native subagents under the parent session with a bounded `/goal` milestone; report the actual fallback. Never claim concurrent execution unless separate agents actually ran.

Assign these work roles, with people or native agents taking one role at a time:

| Role | Responsibility | Typical scope |
|---|---|---|
| Integrator/orchestrator | Own contracts, milestone order, merges, context and final acceptance | Cross-cutting integration and shared entry points |
| Data engineer | Instrument registry, provider history/ticks, freshness, provenance, timeframe integrity | Broker providers and market data |
| Quant engineer | Strategy applicability, features, regime, confluence, risk geometry, calibration/replay | Strategy and signal engines |
| Runtime engineer | Authoritative paper state, exit handling, persistence, workers, recovery and audit | Paper engines, database, worker/live_paper |
| AI engineer | Async adapter, typed evidence-grounded assistants, budgets and failure behavior | AI engine and its API contracts |
| UI engineer | Simple daily workflow, authenticated client, signal/position/journal/learning UX | Frontend |
| Security reviewer | Independent secret/auth/input/privacy/risk review | Read-only review plus assigned regression tests |
| Verification engineer | Independent numeric, integration, browser and failure-path checks | Test and evidence artifacts |

These are eight work roles across the project, not eight simultaneous writers. Start with three implementation workers plus the integrator and one independent reviewer. Increase to four implementation workers only after interfaces are stable and resources permit. Limit expensive numerical and browser runs so the machine stays responsive. Respect actual harness limits and quotas.

Use isolated Git worktrees for concurrent writers when available. Every worktree must start from an explicit verified integration revision containing the required contracts. Uncommitted files and secrets are not automatically copied to worktrees; provide safe, explicit context and scoped configuration. Never copy `.env` blindly or overwrite my checkout. Shared-folder fallback requires exclusive file ownership. Only the integrator may edit shared entry points such as `backend/app/main.py`, shared schemas, dependency lockfiles, or the authoritative progress log during a wave.

Every task handoff must include: objective, repository/worktree and base revision, readable context paths, allowed files, prohibited files, interface/schema version, known dependencies, test commands, acceptance examples, and exact required return artifact. Native agents may not inherit conversation history. No worker may expand its scope or merge another worker's changes without the integrator.

Return from each task: diff/commit reference, modified files, tests and exit codes, actual output excerpts, unmet criteria, and integration notes. Independent reviewers must inspect the merged candidate and run tests themselves. Their independence does not eliminate correlated mistakes from using the same model; numerical oracles and failure tests remain essential.

Freeze contracts first. Run independent tracks concurrently. Merge in dependency order. Rebase dependent workers against the approved integration revision. Rerun integration checks after merges. Stop incompatible writers instead of allowing them to overwrite shared state.

## Audit artifacts and known first repairs

Create or update `docs/APEX_IMPLEMENTATION_STATUS.md` as the single progress ledger and `docs/APEX_CAPABILITY_MATRIX.md` as the tested feature matrix. Preserve prior context documents; link them rather than rewriting history. Record planned, implemented, tested, externally verified, and blocked states separately.

For every capability record the API route, frontend action, service, persistence, tests, real-data requirement, current limitation, owner and next gate. A filename, screenshot, green mock, or successful build is not proof of end-to-end completion.

Reproduce these reported defects before fixing them:

- `frontend/src/stores/canonicalQuoteStore.ts` refers to an out-of-scope `incomingTs`; type checking currently fails although Vite builds.
- Manual paper order/close requests lack auth; failed closes remove positions locally; Signal Center embeds a development credential and treats HTTP 200 as a fill.
- Signal-to-paper submission lacks explicit state/expiry/hard-gate revalidation.
- The scanner constructs equity candidates while optional derivatives code substitutes invented contract inputs.
- Signal expiry and primary timeframe can disagree with configuration, and candle provenance is not fully propagated.
- Paper mark-to-market and a separate research bridge do not establish one side-correct authoritative automated exit lifecycle.
- Some AI paths call synchronous SDK functions inside async methods; query-string API keys and raw exceptions risk leakage.
- API and worker lifespan cancellation paths need scoped ownership-aware cleanup.

Do not assume these findings remain unchanged. Use narrow reproductions and fix real causes. The root lifecycle tracker is stale: API lifespan already uses `asynccontextmanager`. Inspect actual code rather than adding duplicate lifecycle handlers.

## Quantitative decision contract

Use one versioned, typed, server-authoritative decision contract for APIs, persistence, UI, AI explanations and replay. Adapt existing models instead of introducing competing decision types.

Required evidence includes:

- Stable instrument ID, exchange, asset class, underlying/contract identity, timeframe and completed-bar timestamp.
- Source timestamps, receipt timestamps, input provenance, adjustment basis, freshness and missingness by input.
- Strategy/configuration version and immutable input/evaluation fingerprint.
- Market regime, applicability and evaluation outcome for every registered strategy: passed, failed, not applicable, or unavailable, with reasons.
- Hard eligibility/risk gates distinct from weighted confluence and soft research scores.
- Entry trigger and valid price range, stop, ordered targets, invalidation, expiry, quantity, capital/margin need and estimated total costs.
- Risk per unit, maximum modeled loss, net reward/risk, spread/liquidity quality, exposure and portfolio correlation checks.
- Quality score separate from empirical probability; show sample size, out-of-sample window and uncertainty when calibration exists.
- Decision/action state, reasons for no trade, paper position reference and deterministic exit reason when applicable.
- Evidence references that runtime AI must use rather than manufacture.

Reuse current lifecycle enums and add explicit transitions only where required. Separate setup status from position status: a potential entry, an armed trigger, a filled paper entry, a pending exit, and a confirmed closed position are different events. Backend order result states must determine UI success, not HTTP 200 alone.

For LONG: `stop < entry < targets`. For SHORT: `targets < entry < stop`. Model costs, tick size, lot size, margin and side correctly. Reject zero/negative/nonfinite values, impossible geometry, insufficient risk budget and invalid contract data. Quantity is computed from risk and executable lot constraints, not a fabricated default.

## Full-universe scanning and authentic inputs

Build an instrument master and configurable supported NSE/BSE equity universe with explicit instrument lifecycle and delisting/duplicate handling. Derivatives require an eligible underlying plus actual contract identifiers, expiry, tick size, lot size, quotes, OI/volume, spread and applicable margin evidence. Verify current provider and exchange requirements from official sources; do not hardcode stale schedules, fees or contracts.

Every universe member must appear in a scan coverage ledger. Report total requested, eligible, evaluated, unavailable, skipped with reason, rejected and qualified, with last evaluation timestamps. The default UI may start with a manageable watchlist; do not present it as the entire market. Expand coverage within documented provider limits. Do not silently truncate the universe or run only a small default list while claiming every stock was analyzed.

Compute and cache deterministic features once per instrument/timeframe/completed bar/input version. Apply cheap explicit eligibility filters, then all applicable strategy families. Record strategies not applicable to the asset/regime; mutually exclusive strategies need not all agree. Correlated strategy votes must not masquerade as independent confirmations.

Bound concurrency and backpressure. Avoid per-tick full-universe/full-strategy recomputation and LLM calls. Incrementally update changed bars, reuse feature snapshots, batch supported provider operations, honor rate limits and recover from backlogs. Publish coverage/freshness so slow scans are visible.

Preserve genuine gaps in OHLCV and contract data. Do not replace missing highs/lows, prices, volumes, OI, margin or option Greeks with plausible numbers. Do not substitute an unrelated primary timeframe without an explicit degraded result. Validate candle completeness, ordering, timezone, corporate actions and adjustment consistency. Market closure and data outage are distinct states.

Fail closed for actionable signals when required input is stale, missing, mixed incompatibly or synthetic. Fixtures, replay and development simulation must remain explicitly labeled and segregated from authentic shadow sessions. Read-only fallback history can be used only with clear source and quality evidence appropriate to the evaluation.

## Authoritative paper position and exit lifecycle

Trace all current paper-order, signal bridge, portfolio and persistence paths. Select and document one authoritative position/order lifecycle; adapt compatibility routes to it. Do not maintain two independent ledgers that disagree. Browser local storage is a cache, never an accounting authority.

At submission, server revalidates ownership, decision state, freshness, expiry, evaluation version, position duplication, quantity, costs and risk. Use durable idempotency keys. State, accounting, position and audit updates must have documented atomicity/recovery behavior. Concurrency must not create duplicate fills or overspend capital.

Implement side-correct stop/target exits, partial exits, strategy invalidation, time/expiry exits, session-close handling and manual closes. Define realistic fill/slippage and price-gap rules. For bar replay where stop and target both occur, use a documented conservative policy unless finer data proves ordering. Do not claim fills at unreachable prices. Handle delivery, intraday, futures and options according to their instrument rules.

On restart, restore orders, positions, cash, risk state and audit progression. Freeze on reconciliation ambiguity. Persist events before UI confirmation; refresh canonical state after operations. No false successful order, vanished position, silently forgotten stop or repeated recovered session start.

Retain existing session ownership: mid-session worker shutdown is not trading-session finalization. Preserve current finalization rules until exchange-calendar verification justifies changes. Cancel and await owned tasks, disconnect providers, flush evidence, seal and persist in the defined order. Enforce one writer or a verified durable sequence allocator for each session; parallel market workers must not race audit sequences.

Use explicit schema migrations and test upgrade/backup/restore paths. Keep useful SQLite local mode, but exercise PostgreSQL when it is the chosen private runtime. Do not add engine disposal until the owning process and in-flight/background work are understood.

## AI throughout the experience, grounded in deterministic evidence

Reuse the existing research/coach/copilot agents and one async provider adapter. Runtime roles should explain a signal, explain no trade, analyze risks and opposing evidence, summarize session/journal outcomes, teach relevant concepts, and draft research hypotheses. Use richer analysis where useful, not an LLM per tick, indicator, instrument or strategy.

AI may provide narrative and research proposals; it must not invent numerical facts, set authoritative entry/stop/target values, bypass hard gates, mutate a frozen live configuration, auto-promote a strategy, or execute an order. Numeric claims must reference validated decision/portfolio evidence and agree with it. Strategy ideas enter an isolated research workflow with tests and out-of-sample evaluation.

Use typed input/output schemas, evidence identifiers, timestamp/config hashes, timeouts, total retry budgets, bounded concurrency, cancellation, caching keyed by evidence version, per-day cost controls and usage visibility. Verify the installed SDK's real async interface; avoid blocking network calls inside the event loop. Handle malformed JSON, unavailable model, rate limit, timeout and unknown evidence IDs explicitly.

Protect prompt boundaries: news, documents, market metadata and model responses are untrusted data, not executable instructions. Tool access is allowlisted and least-privileged. Never expose shell, secrets, browser control or broker write tools to the runtime explanation model. Redact tokens, account identifiers and unnecessary private holdings from prompts/logs.

When AI is unavailable, deterministic signals, risk controls, paper position monitoring and exits continue working. Show AI unavailable honestly; do not fill the UI with a fake explanation or fabricated confidence. Existing 0–100 heuristic quality scores are not win probabilities. An empirical probability requires actual calibration evidence and uncertainty.

## Simple, educational interface

Default navigation: **Today**, **Positions & Journal**, **Learn**. Keep existing research/backtest/derivative/command-center features available under **Advanced** rather than deleting them.

Today answers: Is data healthy? What is actionable? What am I waiting for? What changed? Why is there no trade? Show scan coverage and last evaluation time. For each signal show instrument/direction, WAIT/ENTRY/EXIT guidance, exact trigger, entry/stop/targets, estimated quantity and rupee risk, validity, and a short factual reason. Expand for calculation evidence, gates, strategies, source provenance and audit history.

Positions show canonical state, P&L net of modeled costs, stop/target status, last update, pending actions and actual exit reasons. Journal links every entry and exit to the original decision and evidence version. Show real filled/rejected/queued/partial states and visible errors; never remove a position after an unsuccessful close.

Learn offers contextual definitions and a plain-language explanation of this specific setup. Explain uncertainty, missing evidence, risk/reward, stop-loss behavior and why the system waits. Avoid an overwhelming table of technical indicators by default.

Use readable responsive layouts, keyboard access, clear loading/error/empty/offline states, and meaningful status labels. No hardcoded market-close/flow figures, simulated live badges, fake confidence, decorative success metrics or AI-derived tactical price levels. Paper/real mode and input authenticity must be unmistakable.

## Security and personal operation

Protect mutations and private portfolio/journal/report/AI endpoints. Establish a simple owner session; keep broker and model keys server-side. Do not compile development credentials into the frontend or expose key-bearing URLs/raw provider exceptions. Use appropriate secure cookie/session behavior and CSRF protection when applicable. Retain account ownership checks even though there is one user.

Default local binding to loopback. If private remote access is chosen, document authenticated HTTPS access, strict origins and a least-privilege deployment. No public self-registration. Avoid unnecessary services. Credentials, DB paths, worker startup and test fixtures must be isolated from real session data.

Validate API inputs, quotas and expensive request limits. Keep dependency versions reproducible. Back up personal data and test restore. Document startup, shutdown, provider-token renewal, outages, disabled trading, update rollback and recovery in a concise runbook.

Proceed with reversible scoped work without repeatedly asking me routine design questions. Ask before destructive migrations/deletion, external publication, real orders, permission changes, or new purchases. Honor actual harness tool approvals. When one external prerequisite is unavailable, finish independent work and record the blocked gate; never fabricate credentials or test evidence.

## Milestones and parallel waves

**M0 — Baseline and contracts.** Run targeted baseline, inspect real integration paths, classify capability gaps, define decision/data/order/AI contracts and task scopes. Gate: evidence-backed plan and isolated reproducible test setup. Do not rebuild existing working architecture.

**M1 — Truthful data and reliable interaction.** Parallelize provider/provenance/timeframe fixes, frontend type/auth/error-state repairs, and AI adapter/security repairs. Shared contracts stay integrator-owned. Gate: type check/build pass, malformed/stale data is non-actionable, unauthorized actions visibly fail, failed close preserves position, no secret in bundle/logs.

**M2 — Complete equity signal-to-paper path.** Integrate full-universe coverage, applicability records, deterministic entry/stop/targets/risk, submission revalidation and one authoritative paper ledger. Gate: controlled replay of scan → valid signal → entry → monitor → exit → journal; duplicate/concurrent submissions cannot duplicate a fill.

**M3 — Genuine F&O paths and exits.** Extend the same contracts with actual derivative data and side-correct position lifecycles. Parallelize contract ingestion, derivatives evaluation and replay/exit tests after contracts stabilize. Gate: valid equity/futures/options fixture workflows and authentic-data checks; missing chain/margin/OI/lot data blocks the affected action explicitly.

**M4 — Durable private runtime.** Validate migrations, recovery, task ownership, audit ordering, backups/restore and deployment architecture. Gate: forced restart during a paper position preserves state; before/after-close shutdown rules and terminal finalized sessions remain correct. Chosen PostgreSQL runtime must be exercised, not inferred from SQLite.

**M5 — Simple UI and evidence-grounded AI.** Integrate Today/Positions/Learn, progressive Advanced views, contextual explanations and coaching against merged stable APIs. Gate: independent browser journey, rejection/partial-close/outage states, AI timeout with deterministic exits still working, no fabricated numeric explanation.

**M6 — Validation and personal handoff.** Run all relevant backend tests, frontend type/build checks, meaningful browser tests and reproducible performance/coverage measurements. Execute authentic shadow checks when credentials and market conditions allow. Deliver runbook, launch instructions, configuration guide and final evidence matrix. Keep paper completion, authentic shadow verification and statistical-edge assessment separate.

Do not mark an external gate passed from fixtures. A blocked real-data or database prerequisite prevents an unconditional fully-verified verdict but does not prevent completing independent implementation.

## Regression and adversarial requirements

Preserve and extend existing tests rather than weakening them or replacing real computations with mocks. Mock external boundaries for deterministic tests and label them. Use separate authentic integration checks. Test selected numerical outputs against hand-calculated or independently implemented oracles.

Required coverage:

- Invalid OHLCV, NaN/Inf, stale quotes, wrong timeframe, out-of-order/duplicate ticks, missing candles, corporate-action mismatch and market holiday/closure.
- Strategy applicability, conflicting correlated votes, no-lookahead, deterministic replay, long/short geometry, lot rounding, insufficient margin, costs and zero risk distance.
- Expired/triggered/invalidated signal submission, simultaneous duplicate orders, accounting conservation, partial/manual/stop/target/gap exits and same-bar ambiguity.
- Mid-position crash/restart, task cancellation/startup failure, duplicate session starts, monotonic durable audit sequence, rollback, evidence flush and report checksum.
- Unauthorized/invalid auth, ownership bypass, CSRF where relevant, token exposure, malicious news prompts, malformed AI output, forged evidence, timeout/retry exhaustion and model outage.
- Browser success/rejection/pending/error journeys, failed close keeps position, partial close refreshes, expired signal cannot execute, keyboard operation, narrow-screen layout and honest data-health states.
- Universe coverage and scan latency under replayed load. Measure p50/p95, processed instruments/strategies, backlog, memory, event-loop responsiveness and provider-call counts. Choose explicit budgets after baseline; do not invent benchmark numbers or flood external APIs.

Run relevant suites per task, then merged integration suites at milestones, and one final appropriate regression pass. Capture command, revision, configuration, duration, exit code, pass/fail/skip counts and limitations. Builds and type checks are separate gates. A skipped or hanging test is not passed.

## Completion and continuing work

After every milestone update the progress ledger with verified changes, evidence and first incomplete gate. Give short updates with result, remaining uncertainty and next action. Keep working through authorized implementation until the brief is met or a concrete prerequisite blocks progress. Do not finish with only a plan, scaffold, TODO list, screenshot, or offer to continue.

At handoff provide: runnable application, startup instructions, mode/security configuration, capability matrix, signal decision examples from labeled replay, validation evidence, source-of-truth journal/audit access, recovery runbook, and unresolved external gates. State actual readiness honestly. Functional correctness and a high model benchmark do not prove market edge, calibrated profitability, or real-money readiness.

Begin with M0 now. Preserve this brief, establish the real baseline, define the first worker contracts, and dispatch native scoped agents for the first independent work wave.
