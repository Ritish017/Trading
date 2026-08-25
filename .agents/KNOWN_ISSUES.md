# APEX Quant Lab — Known Issues & Technical Debt Tracker

## Open Technical Items

1. **FastAPI Lifespan Deprecation Warnings**
   - **Severity**: Low (Warning)
   - **Location**: `backend/app/main.py:122` (`@app.on_event("shutdown")`)
   - **Description**: FastAPI recommends using `asynccontextmanager` lifespan event handlers instead of `@app.on_event`.
   - **Remediation**: Refactor startup and shutdown lifecycle to modern lifespan context.

2. **Frontend Large Bundle Chunks**
   - **Severity**: Low (Optimization)
   - **Location**: `frontend/src/`
   - **Description**: Vite production build emits bundle warning that `index.js` exceeds 500 kB (523 kB uncompressed).
   - **Remediation**: Implement lazy loading / dynamic imports for heavy charting and dashboard views.

3. **Untracked Workspace Artifacts**
   - **Severity**: Low (Hygiene)
   - **Location**: `C:\Tradinf2` root (`apex_quant.db`, `scripts/probe_upstox.py`)
   - **Description**: Local database and probe scripts are present in working tree.
   - **Remediation**: Ensure appropriate `.gitignore` entries for local databases and ephemeral scripts.
