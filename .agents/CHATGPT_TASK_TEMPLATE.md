# APEX Quant Lab — ChatGPT Task Template

When ChatGPT acts as the Architect / Quant Researcher / Code Reviewer, it generates a structured task according to the canonical specification below.

The JSON payload is authoritative. Antigravity and the APEX Agent Bridge ingest and execute the JSON directly.

---

## 1. Standard Implementation Task Template

### Markdown Representation (Human-Readable)

```markdown
# TASK: TASK-YYYYMMDD-001

## Objective
Refactor market data service fallback logic to ensure canonical store is checked prior to mock provider.

## Context
Market quotes must resolve from verified exchange data first. Mock providers are strictly for local fallback testing.

## Files to Inspect
- backend/app/market_data/service.py
- backend/app/market_data/canonical_store.py

## Files Allowed to Modify
- backend/app/market_data/service.py

## Files Forbidden to Modify
- backend/app/broker_providers/live_upstox.py
- backend/tests/test_canonical_market_integrity.py

## Constraints
- no_fabricated_financial_data
- no_synthetic_current_prices
- preserve_existing_architecture

## Acceptance Criteria
- All 180 backend pytest tests pass.
- Frontend build succeeds.
- No regression in canonical quote resolution.

## Verification
- backend_tests
- frontend_build

## Approval Required
- Modify: false
- Commit: true
- Push: true
```

### Authoritative JSON Payload (Save to `C:\APEX-Agent-Bridge\inbox\TASK-YYYYMMDD-001.json`)

```json
{
  "task_id": "TASK-20260821-001",
  "created_at": "2026-08-21T16:45:00Z",
  "objective": "Refactor market data service fallback logic to ensure canonical store is checked prior to mock provider",
  "context": "Market quotes must resolve from verified exchange data first. Mock providers are strictly for local fallback testing.",
  "priority": "normal",
  "mode": "DEVELOPMENT",
  "operation": "IMPLEMENTATION",
  "constraints": [
    "no_fabricated_financial_data",
    "no_synthetic_current_prices",
    "preserve_existing_architecture"
  ],
  "files_allowed": [
    "backend/app/market_data/service.py"
  ],
  "files_forbidden": [
    "backend/app/broker_providers/live_upstox.py",
    "backend/tests/test_canonical_market_integrity.py"
  ],
  "acceptance_criteria": [
    "All 180 backend pytest tests pass",
    "Frontend build succeeds",
    "Zero mock-data leakage in canonical store"
  ],
  "verification": [
    "backend_tests",
    "frontend_build"
  ],
  "approval_required": {
    "modify": false,
    "commit": true,
    "push": true
  }
}
```

---

## 2. Standard Diagnostic / Price Debugging Task Template

```json
{
  "task_id": "TASK-20260821-DIAG-01",
  "created_at": "2026-08-21T16:45:00Z",
  "objective": "Trace why HDFCBANK current price differs from the expected exchange price",
  "priority": "high",
  "mode": "SAFE",
  "operation": "DIAGNOSTIC",
  "symbol": "NSE:HDFCBANK",
  "timeframe": "1m",
  "constraints": [
    "no_fabricated_financial_data",
    "no_lookahead",
    "read_only_inspection"
  ],
  "files_allowed": [],
  "files_forbidden": [],
  "acceptance_criteria": [
    "Audit 10 pipeline layers from exchange feed to React chart",
    "Identify provider and timestamp at each layer",
    "Identify normalizer transformation and cache state",
    "Do not modify code"
  ],
  "verification": [],
  "approval_required": {
    "modify": false,
    "commit": false,
    "push": false
  }
}
```

---

## 3. Execution Lifecycle

1. **ChatGPT generates Task JSON**.
2. **Task is placed in `C:\APEX-Agent-Bridge\inbox\TASK-xxxx.json`** (or submitted via `tool_submit_task_file`).
3. **Bridge loads `.agents` context** (`INVARIANTS.md`, `ARCHITECTURE.md`, `PROJECT_STATE.md`).
4. **Antigravity executes and verifies**.
5. **Deterministic result is written to `C:\APEX-Agent-Bridge\outbox\TASK-xxxx.result.json`**.
6. **Task is archived to `C:\APEX-Agent-Bridge\archive\TASK-xxxx.json`** and recorded in [TASK_LEDGER.md](file:///C:/Tradinf2/.agents/TASK_LEDGER.md).
