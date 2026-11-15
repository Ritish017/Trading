# Milestone 1 (R1) Frontend Defect Repairs Handoff Report

**Agent**: `teamwork_preview_explorer` (Frontend Defect Explorer)  
**Recipient**: Milestone 1 Worker (`worker_m1`) / Orchestrator (`parent`)  
**Scope**: Frontend First-Wave Defect Repairs (R1)  
**Date**: 2026-10-06  

---

## 1. Observation

Direct code observations from `C:\Tradinf2\frontend`:

1. **`frontend/src/stores/canonicalQuoteStore.ts`**:
   - Running `npm.cmd run lint` (`tsc --noEmit`) in `C:\Tradinf2\frontend` outputs verbatim:
     ```
     src/stores/canonicalQuoteStore.ts(152,27): error TS2304: Cannot find name 'incomingTs'.
     src/stores/canonicalQuoteStore.ts(152,44): error TS2304: Cannot find name 'incomingTs'.
     src/stores/canonicalQuoteStore.ts(163,19): error TS2304: Cannot find name 'incomingTs'.
     ```
   - In `updateFromWS(tick: any)` (lines 108–169), `incomingTs` is referenced at lines 152 and 163 without declaration:
     - Line 152: `provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),`
     - Line 163: `last_ws_ts: incomingTs,`
   - Unlike `updateFromREST(rawQuote: any)` (lines 42–47), `updateFromWS` contains no check for `existing.provider_timestamp > incomingTs` to reject backwards/out-of-order ticks.
   - `updateFromWS` omits alias updates for stripped symbol name (`symbol.replace('.NS', '')`) which `updateFromREST` performs at lines 101–103.

2. **`frontend/src/App.tsx`**:
   - `handlePlacePaperOrder` (lines 669–671):
     ```typescript
     const res = await fetch('/api/paper/order', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
     ...
     ```
     Ommits `X-API-Key` and `Authorization` headers.
   - `handleClosePaperPosition` (lines 701–704):
     ```typescript
     const res = await fetch(`/api/paper/close/${id}`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
     });
     ```
     Ommits `X-API-Key` and `Authorization` headers.
   - Position deletion bug (lines 710–713):
     ```typescript
       } catch {
         // quiet
       }
       setPaperPositions((prev) => prev.filter((p) => p.id !== id));
     ```
     Line 713 executes unconditionally. When the close request fails (401, 404, 500, or network drop), the position is purged from local state and `localStorage` (`apexnse_positions`), despite remaining open in backend. No error alert is displayed.

3. **`frontend/src/components/pages/SignalCenterPage.tsx`**:
   - Line 846:
     ```typescript
     headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' },
     ```
     Hardcodes development secret `'apex_default_dev_key'`.
   - Lines 850–853:
     ```typescript
     if (res.ok) {
       setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
     ```
     In backend `backend/app/main.py:2501–2511`, `paper_trade_from_signal` returns HTTP 200 even when `paper_engine.execute_order` returns `{"status": "REJECTED", "reason": "..."}`. The frontend falsely displayed a green checkmark fill confirmation.

4. **`frontend/src/components/IndexTickerBar.tsx`**:
   - Lines 83–88:
     ```typescript
     const probeRes = await fetch('https://apex-market-worker-probe.onrender.com/api/worker/status', { mode: 'cors' });
     ```
     Performs external network fetch to Render, breaking local loopback operation.

---

## 2. Logic Chain

1. **Quote Store Monotonicity & Compilation**:
   - `incomingTs` is referenced at lines 152 and 163 of `canonicalQuoteStore.ts` without being defined in the function scope (Obs 1).
   - Therefore, `tsc --noEmit` fails with three TS2304 errors.
   - Extracting `incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0)` declares the identifier and resolves all three TS2304 compiler diagnostics.
   - Adding `if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) return existing;` guarantees monotonic timestamp sequencing and drops stale out-of-order ticks.

2. **Authentication Injection & Position Retention**:
   - Backend routes `/api/paper/order` and `/api/paper/close/{id}` require `verify_api_key` (`backend/app/main.py:965, 987`). Requests without headers receive HTTP 401 Unauthorized (Obs 2).
   - Providing a helper `frontend/src/utils/auth.ts` that dynamically attaches `X-API-Key` and `Authorization: Bearer <token>` without hardcoding resolves 401s across all environments.
   - In `handleClosePaperPosition`, moving `setPaperPositions((prev) => prev.filter((p) => p.id !== id))` strictly inside `if (res.ok && (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED'))` ensures that failed requests never delete open positions from client memory or `localStorage`.
   - Adding alerts and error notifications on non-ok status ensures the user is immediately alerted to failure details.

3. **Credential Removal & Server-Authoritative Execution**:
   - Removing `'X-API-Key': 'apex_default_dev_key'` from `SignalCenterPage.tsx` and using `getAuthHeaders()` eliminates credential exposure in client source code (Obs 3).
   - Inspecting `data.order_result?.status === 'FILLED'` before showing success, and displaying error notices when `data.order_result?.status === 'REJECTED'`, prevents false fill confirmations.

4. **Loopback Isolation**:
   - Removing lines 83–88 of `IndexTickerBar.tsx` confines telemetry to local `/api/worker/status` (Obs 4), eliminating external network dependency.

---

## 3. Caveats

- **Backend Configuration Requirement**: For authenticated paper mutations to succeed, the backend must have `API_AUTH_TOKEN` configured in environment or settings (e.g. `API_AUTH_TOKEN=test-token` or matching token). In the frontend, `localStorage.setItem('apex_api_key', token)` or `VITE_APEX_API_KEY` can be set to match. If `API_AUTH_TOKEN` is not set on the backend, the backend intentionally fails closed with 401, as tested by backend security test suites.
- **Scope Limit**: Navigation view consolidation (Today, Positions & Journal, Learn, Advanced) is scheduled for Milestone 4 (R4) and is not part of this M1 repair scope.

---

## 4. Conclusion

The 4 defects are fully scoped and mapped to exact code locations. A companion helper `frontend/src/utils/auth.ts` resolves credential management cleanly without hardcoding. The drop-in diffs provided in `C:\Tradinf2\.agents\teamwork\explorer_m1_1\report.md` will completely resolve the TypeScript compilation failures (`tsc --noEmit`), protect client state integrity on failed paper closes, ensure server-authoritative fill confirmations, and eliminate external network probes.

---

## 5. Verification Method

The Worker can independently verify all repairs with these commands and inspection criteria:

1. **TypeScript Lint Check**:
   ```powershell
   cd C:\Tradinf2\frontend
   npm.cmd run lint
   ```
   *Expected Result*: Zero errors, exit code 0.

2. **Frontend Build Check**:
   ```powershell
   cd C:\Tradinf2\frontend
   npm.cmd run build
   ```
   *Expected Result*: Vite builds `dist/` cleanly without diagnostics.

3. **Residual External URL Audit**:
   ```powershell
   # In frontend/src, verify no references to onrender.com remain:
   git grep "onrender.com" frontend/src
   # Verify no references to apex_default_dev_key remain:
   git grep "apex_default_dev_key" frontend/src
   ```
   *Expected Result*: 0 matches.
