# APEX Antigravity implementation research

Checked 6 October 2026. Repository: `C:\Tradinf2`, commit `34849a90596eb8af218268cdebabb561ca627ede`. Two read-only agents inspected quantitative/runtime and frontend/AI/security paths. This work produces a build brief; it does not implement or deploy the application.

## Model and harness findings

Both requested model names are real API models: `gemini-3.5-flash` and `gemini-3.8-flash`. The current Antigravity model table lists Gemini 3.8 Flash across its plan tiers. Account availability, quotas, and the selected installed model still require an in-app check. [Gemini model catalog](https://ai.google.dev/gemini-api/docs/models), [Antigravity models](https://antigravity.google/docs/models/).

| Published evaluation | Gemini 3.5 Flash, May 2026 | Gemini 3.8 Flash, September 2026 |
|---|---:|---:|
| Terminal-Bench 2.1 | 76.2% | 89.4% |
| SWE-Bench Pro Public | 55.1% | Not reported in this card |
| DeepSWE v1.1 | Not reported in this card | 73.7% |
| Terminal-Bench 4.0 | Not reported in this card | 19.1% |

These are vendor-published results from different release snapshots, not an APEX comparison experiment. The two software-engineering benchmarks are different tasks; do not subtract their scores or interpret a missing result as zero. [3.5 model card](https://deepmind.google/models/model-cards/gemini-3-5-flash/), [3.8 model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/).

Google's 3.8 methodology says DeepSWE uses mini-swe with high thinking and Terminal-Bench 2.1 uses Terminus 2. Those results do not quantify the Antigravity harness. No controlled end-to-end Antigravity-versus-Codex result for this repository was found. Finance-task benchmarks likewise are not market profitability or signal win rates. [Evaluation methodology](https://deepmind.com/models/evals-methodology/gemini-3-8-flash).

Recommendation, inferred from these capabilities: select 3.8 Flash if available, give it bounded implementation tasks, maintain written contracts and independent verification, and use a higher exposed effort setting for numerical/race-condition reviews. The API supports low/medium/high thinking and rejects minimal; an IDE selector need not expose every API setting. [Model capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

Antigravity supports native subagents and isolated Git worktrees. Custom agents do not inherit the parent's conversation context, so every task needs a complete handoff. Model metadata supports tiers such as `inherit`, not arbitrary API IDs. Validate actual invocation and tool names; writing role Markdown alone does not start agents. [Subagents](https://antigravity.google/docs/subagents/).

For the whole build, `/teamwork-preview` is the documented paid-plan workflow with milestone coordination and independent verification. It first creates a brief for approval. `/goal` is documented for continuous execution and is a fallback for a bounded milestone. Respect the installed harness's approval flow. [Teamwork](https://antigravity.google/docs/teamwork/), [Slash commands](https://antigravity.google/docs/slash-commands/).

The proposed eight work roles and concurrency limits are project engineering choices, not claimed optimal benchmark settings. They are distinct from runtime AI assistants inside APEX.

## Actual capabilities and gaps

| Area | Existing implementation | Current gaps and priority |
|---|---|---|
| Strategy and signal pipeline | Twenty strategy definitions; features, regime, multi-timeframe analysis, confluence, gates, sizing, entry/stop/targets, rejection records. `backend/app/strategy_engine/registry.py:54`; `backend/app/signal_engine/signal_pipeline.py:331`. | Preserve the pipeline. Fix expiry configuration mismatch (`:585`, `:717`), primary-timeframe substitution (`:352`), and provenance inferred from quote alone (`:572`). |
| Derivatives | Optional futures/options engines and UI exist. | Main scanner creates EQUITY candidates only (`scanner.py:278`). Futures defaults invent volume/OI/lot/margin/DTE (`signal_pipeline.py:608`). Require real contract inputs and explicit unavailable states. |
| Data | Upstox history and named Yahoo fallback (`broker_providers/upstox_client.py:455`). | Yahoo fills missing high/low from open/close and volume with zero (`:492`). Preserve missingness and source/adjustment/freshness evidence. |
| Paper lifecycle | Authenticated backend paper order/close APIs, accounting and persistence tests. | Default mark-to-market only changes unrealized P&L (`paper_trading/engine.py:217`). Separate bridge has long-biased exit arithmetic (`paper_engine/bridge.py:219`). Unify authoritative state and test LONG/SHORT automatic exits. |
| Browser mutations | UI order and close actions already wired. | Missing auth (`frontend/src/App.tsx:669`, `:701`), failed close removes position (`:713`), hardcoded development credential (`SignalCenterPage.tsx:846`), HTTP 200 misread as fill (`:850`). |
| Submission validity | Backend signal-to-paper endpoint exists. | It does not explicitly enforce its documented QUALIFIED state or expiry (`backend/app/main.py:2464`). Revalidate stale/invalidated signals and risk at action time. |
| UI | Existing Signal Center shows meaningful entry, risk, targets, reasons and gates (`SignalCenterPage.tsx:543`). | Simplify default navigation, preserve advanced pages, remove placeholder metrics and commentary-derived tactical prices (`App.tsx:637`; `indianTechnicalAnalysis.ts:101`). |
| Runtime AI | Existing research, coaching, copilot and async REST adapter. | Some async methods call sync SDK functions (`ai_engine/agents.py:11`; `chief_analyst.py:245`). Hardcoded older models, key-bearing query URLs and raw exception handling need review (`gemini_client.py:37`, `:66`). |
| Private security | Mutation auth and ownership checks fail closed. | Unauthenticated portfolio read with no account ID can expose aggregate positions (`main.py:975`; `paper_trading/engine.py:368`). Protect personal/costly endpoints and broker secrets. |
| Worker and audit | Session recovery, monotonic audit sequence, shutdown rules, flushing and sealing. | API and worker lifespans have bare yield; worker startup task is not retained (`worker.py:231`). Migration/restore and real PostgreSQL behavior remain unverified. |

## Verification performed now

- Selected backend security, paper accounting/idempotency and safety tests: **16 passed**. Isolated SQLite, development config, live trading and worker auto-start disabled. One Google SDK Python 3.14 deprecation warning.
- `npm.cmd run lint`: **failed** with three TS2304 diagnostics at `frontend/src/stores/canonicalQuoteStore.ts:152,163`: `Cannot find name 'incomingTs'.`
- `npm.cmd run build`: **passed**, but the Vite build does not perform the failed type check. JS bundle warning: **563.26 kB**, not the old tracker's 523 kB figure.
- No whole-backend rerun, real PostgreSQL test, broker call, browser E2E, or deployment test in this turn.
- No application source changed. Frontend build produced ignored output; research and prompt documents are the deliverables.

## Scope decision

Build a dependable personal application with a simple interface and deep internal analysis. No SaaS subscriptions, tenant onboarding, payment system, public marketplace, Kubernetes mandate, or architecture rewrite. Preserve existing account isolation checks rather than deleting them.

Acceptance centers on a complete signal-to-paper-position-to-exit-to-journal flow, honest full-universe scan coverage, real-data provenance, durable recovery, and explainable decisions. Live broker execution remains a separately approved capability. Engineering completion does not establish trading edge.

Use `APEX_ANTIGRAVITY_MASTER_PROMPT.md` as the execution brief. Re-audit the repository at execution time because line numbers and dependencies can change.
