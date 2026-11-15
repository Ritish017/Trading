# Orchestration Plan — Generation 4

## Objective
Lead APEX trading workstation development through completion of Milestone 3 (R3: Features 15-21), Milestone 4 (R4: Features 22-26), Milestone 5 (R5: Features 27-30), and Final E2E Suite Verification (100% pass on Tiers 1-4).

---

## Phase 1: Milestone 3 (Requirement R3) — Paper Execution, Exit Lifecycle & Journaling
- **Features**:
  - Feature 15: Paper Engine Unification (`PaperTradingEngine` and `PaperTradingBridge` consolidated into single server-authoritative engine).
  - Feature 16: Order Pre-Submission Validation (`QUALIFIED` status, expiry timestamp, price bounds, portfolio risk limits revalidated).
  - Feature 17: Durable Idempotency Keys (Persistent cache / DB preventing duplicate execution across restarts).
  - Feature 18: Side-Correct Automated Exits (LONG: `low <= stop_loss` -> SL, `high >= take_profit` -> TP; SHORT: `high >= stop_loss` -> SL, `low <= take_profit` -> TP).
  - Feature 19: Same-Bar Conservative Policy (SL takes precedence if both crossed on the same bar).
  - Feature 20: Immutable Paper Journal (Persist entry/exit trades linked to signal fingerprint, evidence, realized P&L net of friction).
  - Feature 21: Crash Recovery (Snapshot restoration of orders, open positions, cash balance, monotonic audit sequence).
- **Execution Workflow**:
  1. Dispatch 3 Explorers (`teamwork_preview_explorer`) to audit existing paper trading files, database models, and test requirements for Features 15–21.
  2. Synthesize Explorer recommendations into unified Worker brief.
  3. Dispatch Worker (`teamwork_preview_worker`) with mandatory integrity warning to implement M3 deliverables and execute tests.
  4. Sequentially dispatch Reviewer (`teamwork_preview_reviewer`), Challenger (`teamwork_preview_challenger`), and Forensic Auditor (`teamwork_preview_auditor`).
  5. Gate check in `GATE_STATUS.md`.

---

## Phase 2: Milestone 4 (Requirement R4) — Grounded AI Explanations & Educational UI
- **Features**:
  - Feature 22: Primary Navigation Restructure (3 primary tabs: Today, Positions & Journal, Learn).
  - Feature 23: Advanced Group Preservation (9 analytical modules preserved under Advanced dropdown/container).
  - Feature 24: Async AI Explanation Engine (`client.aio` non-blocking).
  - Feature 25: Evidence-Grounded Citations (Explanations strictly citing quantitative calculation evidence).
  - Feature 26: Graceful AI Offline Degradation (Deterministic fallback templates and visible status badges).
- **Execution Workflow**:
  1. Dispatch Explorers for frontend structure and AI engine code.
  2. Dispatch Worker for implementation.
  3. Sequential Reviewer, Challenger, and Auditor verification.
  4. Gate check in `GATE_STATUS.md`.

---

## Phase 3: Milestone 5 (Requirement R5) — Security & Guardrails
- **Features**:
  - Feature 27: Permanent Live Order Ban (`LIVE_ORDER_ALLOWED = False` hard assertions).
  - Feature 28: Header Secret Storage (`x-goog-api-key` header compliance).
  - Feature 29: Authenticated Portfolio Query (`/api/paper/positions` auth enforcement).
  - Feature 30: Isolated Test Fixtures (Zero interference with production session data).
- **Execution Workflow**:
  1. Dispatch Explorers.
  2. Dispatch Worker.
  3. Sequential Reviewer, Challenger, and Auditor verification.
  4. Gate check in `GATE_STATUS.md`.

---

## Phase 4: Final Acceptance Verification
- Full 4-Tier E2E test execution:
  - `test_tier1_features.py`
  - `test_tier2_boundaries.py`
  - `test_tier3_combinations.py`
  - `test_tier4_scenarios.py`
- Forensic Integrity Audit on complete system.
- Final report to Sentinel (`b8286548-1eca-406e-b823-2353a97db035`) and User.
