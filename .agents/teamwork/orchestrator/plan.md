# APEX Workstation Orchestration Plan

## Objectives
Execute full end-to-end implementation and verification for Requirements R1 through R5 and all Acceptance Criteria defined in `ORIGINAL_REQUEST.md` and documentation:
1. R1: Baseline integrity & defect repairs (canonicalQuoteStore.ts, FastAPI & worker lifespans, authentication & client state).
2. R2: Server-authoritative decision contract & market ingestion (Indian F&O + equities, contract parameters, scan coverage, LONG/SHORT geometry).
3. R3: Authoritative paper execution, exit lifecycle, and journaling (server ledger, durable idempotency, side-correct automated exits, immutable journal, crash recovery).
4. R4: Grounded AI explanations & educational UI (Today, Positions & Journal, Learn views; Advanced group preserved; deterministic evidence citations; graceful degradation).
5. R5: Security, local operation, and real-money guardrails (real-money execution permanently disabled, localhost binding, isolated fixtures).

## Phase 0: Survey & Scoping (Current)
- Dispatch 3 parallel survey explorers:
  - `explorer_survey_spec` (`teamwork_preview_spec_miner`): Deep probe of `docs/APEX_ANTIGRAVITY_MASTER_PROMPT.md`, `docs/APEX_PROJECT_CONTEXT.md`, and `docs/APEX_ANTIGRAVITY_RESEARCH.md`.
  - `explorer_survey_backend` (`teamwork_preview_explorer`): Codebase investigation of backend (FastAPI lifespan, auth, quotes, scans, paper broker, ledger, exit engine, tests).
  - `explorer_survey_frontend` (`teamwork_preview_explorer`): Codebase investigation of frontend (TypeScript compilation errors, quote stores, navigation structure, paper order/close handling).
- Merge findings into `PROJECT.md` (Architecture, Feature Inventory, Milestones, Interface Contracts, Code Layout).

## Phase 1: Dual Track Launch
- Track A (E2E Testing Track):
  - Design test infrastructure and runner (`TEST_INFRA.md`).
  - Generate comprehensive Tier 1-4 test cases (Feature, Boundary, Combinatorial, Real-world).
  - Publish `TEST_READY.md`.
- Track B (Implementation Track):
  - Milestone 1 (R1): Baseline defect repairs (TypeScript errors, lifespans, auth, client state).
  - Milestone 2 (R2): Server-authoritative decision contract & market ingestion.
  - Milestone 3 (R3): Paper execution, ledger, exit lifecycle, crash recovery, journaling.
  - Milestone 4 (R4): Grounded AI explanations & educational UI redesign (Today, Positions & Journal, Learn, Advanced).
  - Milestone 5 (R5): Security, local loopback, guardrails verification.

## Phase 2: Final Milestone & Hardening
- Phase 2.1: Pass 100% of E2E test suite (Tiers 1-4).
- Phase 2.2: Adversarial coverage hardening (Tier 5) with Challenger -> Worker -> Reviewer loop.
- Phase 2.3: Forensic Integrity Audit across entire solution.

## Phase 3: Reporting & Closure
- Verify all acceptance criteria.
- Produce final report and notify Sentinel.
