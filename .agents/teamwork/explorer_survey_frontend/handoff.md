# Frontend Architecture Survey — Handoff Report

**Agent**: `teamwork_preview_explorer` (Frontend Codebase Explorer)  
**Date**: 2026-10-06  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\explorer_survey_frontend\`  
**Handoff Type**: Hard (Task Complete)

---

## 1. Observation

1. **TypeScript Diagnostics**:
   - Tool Command: `npm.cmd run lint` executed in `C:\Tradinf2\frontend`.
   - Tool Result: Exited with code 1:
     ```
     src/stores/canonicalQuoteStore.ts(152,27): error TS2304: Cannot find name 'incomingTs'.
     src/stores/canonicalQuoteStore.ts(152,44): error TS2304: Cannot find name 'incomingTs'.
     src/stores/canonicalQuoteStore.ts(163,19): error TS2304: Cannot find name 'incomingTs'.
     ```
   - Target File: `C:\Tradinf2\frontend\src\stores\canonicalQuoteStore.ts`:
     - Line 42: `updateFromREST` defines `const incomingTs = Number(rawQuote.provider_timestamp || rawQuote.timestamp || 0);`
     - Lines 108–169: `updateFromWS(tick: any)` uses `incomingTs` at line 152 and line 163 without declaring or computing it.

2. **Authentication & Paper Order / Close Handling**:
   - Target File: `C:\Tradinf2\frontend\src\App.tsx`:
     - Lines 669–672 (`handlePlacePaperOrder`): Calls `fetch('/api/paper/order', { method: 'POST', headers: { 'Content-Type': 'application/json' }, ... })` with no `Authorization` or `X-API-Key` headers.
     - Lines 701–704 (`handleClosePaperPosition`): Calls `fetch(`/api/paper/close/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, ... })` with no `Authorization` or `X-API-Key` headers.
     - Lines 706–714:
       ```typescript
       if (res.ok) {
         const data = await res.json();
         if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
       }
       } catch {
         // quiet
       }
       setPaperPositions((prev) => prev.filter((p) => p.id !== id));
       ```
       Line 713 executes unconditionally outside the `if (res.ok)` block.
   - Backend Reference: `C:\Tradinf2\backend\app\main.py`:
     - Line 965: `place_paper_order(order: PaperOrderRequest, auth: AccountContext = Depends(verify_api_key))`
     - Line 987: `close_paper_position(pos_id: str, payload: Dict[str, Any], auth: AccountContext = Depends(verify_api_key))`
     - Missing auth headers produce `HTTP 401 Unauthorized` (`detail: "Invalid or missing API authentication token."`).

3. **Hardcoded Credentials & Order State Validation**:
   - Target File: `C:\Tradinf2\frontend\src\components\pages\SignalCenterPage.tsx`:
     - Line 846:
       `headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' },`
     - Lines 850–856:
       ```typescript
       if (res.ok) {
         setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
         setTimeout(() => setPaperTradeStatus(null), 4000);
       } else {
         setPaperTradeStatus(`✗ ${data.detail || 'Paper trade failed'}`);
         setTimeout(() => setPaperTradeStatus(null), 4000);
       }
       ```
   - Backend Reference: `C:\Tradinf2\backend\app\main.py`:
     - Lines 2501–2510: `paper_trade_from_signal` executes `paper_engine.execute_order(...)`. When an order is rejected (e.g. insufficient capital), it returns `{ "order_result": { "status": "REJECTED", "reason": "..." } }` with HTTP 200.

4. **Navigation Structure**:
   - Target File: `C:\Tradinf2\frontend\src\components\NavigationTabs.tsx`:
     - Lines 19–31 & 48–143: 12 flat tabs (`terminal`, `intelligence`, `derivatives`, `institutional`, `portfolio`, `backtest`, `learn`, `strategylab`, `fundamentals`, `researchfactory`, `commandcenter`, `signalcenter`).
   - Target File: `C:\Tradinf2\frontend\src\App.tsx`:
     - Lines 835–958: Flat conditional switches for each of the 12 tabs.

5. **AI Explanations & Educational UI**:
   - Components inspected:
     - `C:\Tradinf2\frontend\src\components\ApexLearnSection.tsx`
     - `C:\Tradinf2\frontend\src\components\pages\QuantLearnPage.tsx`
     - `C:\Tradinf2\frontend\src\components\AICopilotDrawer.tsx`
     - `C:\Tradinf2\frontend\src\components\intelligence\SecurityIntelligencePanel.tsx`
     - `C:\Tradinf2\frontend\src\utils\indianTechnicalAnalysis.ts`: `generateLocalIndianAIReport` fallback.

6. **External Network Call Anomaly**:
   - Target File: `C:\Tradinf2\frontend\src\components\IndexTickerBar.tsx`:
     - Line 84: `const probeRes = await fetch('https://apex-market-worker-probe.onrender.com/api/worker/status', { mode: 'cors' });`

---

## 2. Logic Chain

1. From Observation 1, `updateFromWS` in `canonicalQuoteStore.ts` references `incomingTs` at lines 152 and 163, but lacks the declaration `const incomingTs = ...`. Because `tsc` compiles with `noEmit: true`, this directly causes the three `TS2304` errors that fail `npm run lint`.
2. From Observation 2, backend routes `/api/paper/order` and `/api/paper/close/{id}` enforce `verify_api_key`. Because `App.tsx` sends requests without auth headers, all paper order submissions and position closures fail with HTTP 401.
3. In `handleClosePaperPosition` (Observation 2), line 713 executes unconditionally. When the close request receives HTTP 401, the position is still removed from `paperPositions` and deleted from `localStorage`. Therefore, the client state diverges from the server ledger, concealing open positions from the trader without notifying them of the failure.
4. From Observation 3, `SignalCenterPage.tsx` leaks the dev key `'apex_default_dev_key'` in source code. Furthermore, because it only checks `res.ok` (HTTP 200) instead of inspecting `data.order_result?.status === 'FILLED'`, rejected trades are misreported to the user as successfully placed paper orders.
5. From Observation 4, the current 12-tab navigation violates requirement R4, which mandates consolidating into 3 primary user views: **Today**, **Positions & Journal**, and **Learn**, while grouping analytical/backtesting tools under an **Advanced** container.
6. From Observation 6, the external Render fetch in `IndexTickerBar.tsx` breaches requirement R5 (strict local-loopback operation and zero external broker/cloud telemetry).

---

## 3. Caveats

1. The survey is strictly read-only; no frontend files were modified during this investigation.
2. The exact mechanism for user authentication token storage (e.g. `localStorage`, cookie, or `.env` injection in dev) should be coordinated with the backend security design. A shared helper `getAuthHeaders()` reading from environment or session state is recommended.
3. Bundle size warning: The Vite build produces a 563.26 kB JS bundle chunk. This is functional and non-breaking, but dynamic imports (`React.lazy`) for advanced lab views (`StrategyLabPage`, `ResearchFactoryPage`) can optimize initial page load.

---

## 4. Conclusion

The APEX frontend requires five targeted repairs:
1. **Fix `canonicalQuoteStore.ts`**: Declare `incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0)` and add the timestamp monotonicity check in `updateFromWS` to achieve a clean `npm run lint` pass.
2. **Harden Paper Mutation Endpoints**: Include authentication headers on `/api/paper/order`, `/api/paper/close/{id}`, and `/api/paper/lifecycle/transition`.
3. **Guard Local Position State**: In `handleClosePaperPosition`, keep the position intact in local state when the close request fails, and display an error alert/toast.
4. **Enforce Backend Order State Checks**: Remove the hardcoded dev key from `SignalCenterPage.tsx` and verify `data.order_result?.status === 'FILLED'` before showing fill confirmations.
5. **Restructure Navigation**: Reorganize `NavigationTabs.tsx` into **Today**, **Positions & Journal**, **Learn**, and an **Advanced** dropdown group containing the specialized lab views, and remove the external Render probe URL.

---

## 5. Verification Method

1. **TypeScript Type Checking**:
   - Run: `cd C:\Tradinf2\frontend && npm.cmd run lint`
   - Invalidation Condition: Any diagnostic output or exit code other than 0.
2. **Build Verification**:
   - Run: `cd C:\Tradinf2\frontend && npm.cmd run build`
   - Expected Result: Successful compilation to `dist/`.
3. **Paper Close Error Retention Verification**:
   - Simulate a failed close request (e.g., return HTTP 401 or HTTP 400 from `/api/paper/close/{id}`).
   - Verify that the position remains visible in `paperPositions` state and that an error notification is displayed.
4. **Order Confirmation Verification**:
   - Trigger a paper order that returns `{ "order_result": { "status": "REJECTED", "reason": "Insufficient margin" } }` with HTTP 200.
   - Verify that the UI displays an error message (`Order Rejected: Insufficient margin`) and does NOT show a green fill confirmation.
