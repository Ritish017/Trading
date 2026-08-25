# APEX Quant Lab — ChatGPT ↔ Antigravity Bridge Protocol

## Communication & Execution Contract

```
                     ┌──────────────────────┐
                     │       CHATGPT        │
                     │  (Architect/Reviewer)│
                     └──────────┬───────────┘
                                │ JSON Task Specification
                                ▼
                     ┌──────────────────────┐
                     │   APEX AGENT BRIDGE  │
                     │  (MCP Server Guard)  │
                     └──────────┬───────────┘
                                │ Strict Tool Dispatch
                                ▼
                     ┌──────────────────────┐
                     │     ANTIGRAVITY      │
                     │  (Execution Agent)   │
                     └──────────┬───────────┘
                                │ File Edits & Tests
                                ▼
                     ┌──────────────────────┐
                     │   C:\Tradinf2 (Repo) │
                     └──────────────────────┘
```

## Handshake Specification

### 1. Inbound Task Schema (ChatGPT → Bridge)
```json
{
  "task_id": "TASK-YYYYMMDD-XXX",
  "objective": "Concise statement of task",
  "context": "Contextual reasoning and background",
  "constraints": [
    "existing-files-only",
    "no-fabricated-data",
    "no-lookahead"
  ],
  "files_allowed": [
    "backend/app/market_data/...",
    "frontend/src/..."
  ],
  "acceptance_criteria": [
    "Pytest passes 100%",
    "Vite build passes"
  ],
  "verification": [
    "run_backend_tests",
    "run_frontend_build"
  ]
}
```

### 2. Outbound Result Schema (Bridge → ChatGPT)
```json
{
  "task_id": "TASK-YYYYMMDD-XXX",
  "status": "COMPLETED | FAILED | WAITING_FOR_APPROVAL",
  "summary": "High-level summary of execution",
  "files_modified": [
    "relative/path/to/file.py"
  ],
  "tests": {
    "passed": 180,
    "failed": 0,
    "duration_sec": 100.1
  },
  "build": {
    "status": "SUCCESS",
    "duration_sec": 4.98
  },
  "git": {
    "branch": "main",
    "commit": "b7c2cc0b0c1b5827944b266c961728344c4264ff",
    "dirty_files": []
  },
  "known_issues": [],
  "recommended_next_step": "..."
}
```

## Security Guarantees
- No credentials or `.env` files are ever transmitted.
- All tokens matching sensitive patterns are redacted to `[REDACTED]`.
- No paths outside `C:\Tradinf2` and `C:\APEX-Agent-Bridge` can be accessed.
- Git push operations require explicit manual authorization.
