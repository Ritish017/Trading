# Frontend First-Wave Defect Repairs Analysis & Patch Specifications

**Explorer**: `teamwork_preview_explorer` (Frontend Defect Explorer)  
**Milestone**: Milestone 1 (R1)  
**Target Repository**: `Ritish017/Trading` at `C:\Tradinf2\frontend`  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\explorer_m1_1\`  
**Date**: 2026-10-06  

---

## 1. Executive Summary

This investigation analyzed four critical frontend defect areas mandated for Milestone 1 (R1):
1. **`frontend/src/stores/canonicalQuoteStore.ts`**: Unresolved `incomingTs` references breaking `tsc --noEmit` (`npm run lint`), plus missing monotonic timestamp guards for WebSocket ticks.
2. **`frontend/src/App.tsx`**: Unauthenticated paper mutation requests (`/api/paper/order`, `/api/paper/close/{id}`) failing with 401 Unauthorized against fail-closed backend security, coupled with an erroneous unconditional position deletion bug that drops open positions even when server closes fail.
3. **`frontend/src/components/pages/SignalCenterPage.tsx`**: Hardcoded credential `'X-API-Key': 'apex_default_dev_key'` leaking development secrets into frontend code, and false fill confirmations where HTTP 200 responses with `order_result.status === 'REJECTED'` were falsely announced as successful fills.
4. **`frontend/src/components/IndexTickerBar.tsx`**: Probing an external Render URL (`https://apex-market-worker-probe.onrender.com/api/worker/status`), violating local-loopback development rules.

All current code states and line references were inspected directly against the codebase. Complete drop-in replacement specifications and patch diffs are provided below for the Worker agent.

---

## 2. Detailed Findings & Root-Cause Analyses

### Area 1: `frontend/src/stores/canonicalQuoteStore.ts`

#### Current State & Diagnostics
Executing `npm.cmd run lint` (`tsc --noEmit`) outputs:
```
src/stores/canonicalQuoteStore.ts(152,27): error TS2304: Cannot find name 'incomingTs'.
src/stores/canonicalQuoteStore.ts(152,44): error TS2304: Cannot find name 'incomingTs'.
src/stores/canonicalQuoteStore.ts(163,19): error TS2304: Cannot find name 'incomingTs'.
```

#### Code Inspection (`frontend/src/stores/canonicalQuoteStore.ts:108–169`)
In method `updateFromWS(tick: any)`:
- Line 114: `const existing = this.quotes.get(symbol);`
- Line 152: `provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),`
- Line 163: `last_ws_ts: incomingTs,`

`incomingTs` is referenced at lines 152 and 163 without declaration. In contrast, `updateFromREST(rawQuote: any)` on lines 42–47 correctly extracts:
```typescript
const incomingTs = Number(rawQuote.provider_timestamp || rawQuote.timestamp || 0);
if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) {
  return existing;
}
```
Furthermore, `updateFromWS` lacks the monotonic guard (`existing.provider_timestamp > incomingTs`), which allows older/delayed WebSocket ticks to overwrite newer price data, violating market data provenance. Also, `updateFromWS` omitted populating stripped ticker aliases (`symbol.replace('.NS', '')`), which `updateFromREST` performs.

---

### Area 2: `frontend/src/App.tsx`

#### Code Inspection (`frontend/src/App.tsx:659–714`)
1. **Missing Authentication Headers**:
   - Line 671:
     ```typescript
     const res = await fetch('/api/paper/order', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' }, // No auth header
       body: JSON.stringify({ ... })
     });
     ```
   - Line 703:
     ```typescript
     const res = await fetch(`/api/paper/close/${id}`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' }, // No auth header
       body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
     });
     ```
   The backend routes `@app.post("/api/paper/order")` and `@app.post("/api/paper/close/{pos_id}")` both require `auth: AccountContext = Depends(verify_api_key)`. When called without `X-API-Key` or `Authorization: Bearer <token>`, the backend strictly returns `401 Unauthorized`.

2. **Client State Desynchronization on Close Failure**:
   Lines 697–714:
   ```typescript
   const handleClosePaperPosition = async (id: string, closePrice?: number) => {
     const pos = paperPositions.find((p) => p.id === id);
     if (!pos) return;
     try {
       const res = await fetch(`/api/paper/close/${id}`, {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
       });
       if (res.ok) {
         const data = await res.json();
         if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
       }
     } catch {
       // quiet
     }
     setPaperPositions((prev) => prev.filter((p) => p.id !== id));
   };
   ```
   **Defect**: Line 713 executes unconditionally outside the `if (res.ok)` block!
   If the API call returns 401 Unauthorized, 403 Forbidden, 404 Not Found, 500 Server Error, or network drops, line 713 removes the position from `paperPositions` and updates `localStorage`. The UI shows the position as closed, while the authoritative backend engine continues holding the position and marking it to market. No error alert or notification is shown to the user.

---

### Area 3: `frontend/src/components/pages/SignalCenterPage.tsx`

#### Code Inspection (`frontend/src/components/pages/SignalCenterPage.tsx:842–861`)
```typescript
const handlePaperTrade = useCallback(async (signal: SignalDecision) => {
  try {
    const res = await fetch(`${API}/api/signals/${signal.signal_id}/paper-trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' },
      body: JSON.stringify({ signal_id: signal.signal_id }),
    });
    const data = await res.json();
    if (res.ok) {
      setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
      setTimeout(() => setPaperTradeStatus(null), 4000);
    } else {
      setPaperTradeStatus(`✗ ${data.detail || 'Paper trade failed'}`);
      setTimeout(() => setPaperTradeStatus(null), 4000);
    }
  } catch (err) {
    setPaperTradeStatus('✗ Paper trade request failed');
    setTimeout(() => setPaperTradeStatus(null), 4000);
  }
}, []);
```

#### Defect 1: Hardcoded Credential
Line 846 hardcodes `'X-API-Key': 'apex_default_dev_key'`. This violates requirement R1/R5 prohibiting hardcoded secrets in frontend source files.

#### Defect 2: False Fill Confirmation on Rejection
In backend `backend/app/main.py:2501-2511`:
```python
res = paper_engine.execute_order(order_req, account_id=target_account)
if res.get("status") == "FILLED":
    await paper_engine.sync_order_to_db(...)
    signal.state = "TRIGGERED"

return {
    "order_result": res,
    "signal": signal.dict(),
    "signal_id": signal_id,
}
```
If `paper_engine.execute_order` rejects the order (e.g., insufficient margin, daily drawdown hit, invalid lot size), `res` is `{"status": "REJECTED", "reason": "Insufficient margin..."}`. The backend returns HTTP 200 OK.
Because `SignalCenterPage.tsx` only evaluated `if (res.ok)`, it displayed a green checkmark saying `✓ LONG RELIANCE — Paper order placed`, misleading the user that the trade executed when it was actually rejected.

---

### Area 4: `frontend/src/components/IndexTickerBar.tsx`

#### Code Inspection (`frontend/src/components/IndexTickerBar.tsx:82–91`)
```typescript
// Direct probe fallback if serverless proxy is cold or not started
try {
  const probeRes = await fetch('https://apex-market-worker-probe.onrender.com/api/worker/status', { mode: 'cors' });
  if (probeRes.ok) {
    const probeData = await probeRes.json();
    setWorkerData(probeData);
  }
} catch {
  // quiet if probe offline
}
```
Line 84 makes an external request to Render. This leaks telemetry externally and violates Requirement R5: "Bind services to local loopback ... isolate testing fixtures". The frontend should strictly poll `/api/worker/status` on the local server.

---

## 3. Recommended Architectural Fixes & Drop-in Diffs

### Module 1: Centralized Auth Header Provider (`frontend/src/utils/auth.ts`)
Create a dedicated utility module to resolve auth tokens dynamically from environment variables, localStorage, or runtime config without hardcoding.

#### New File: `frontend/src/utils/auth.ts`
```typescript
/**
 * Dynamic Authentication Header Helper
 * 
 * Safely resolves API credentials for state-mutating requests:
 * 1. Checks localStorage for user-configured credentials ('apex_api_key' or 'apex_auth_token')
 * 2. Checks global window runtime configuration ((window as any).__APEX_API_KEY__)
 * 3. Checks environment variables (VITE_APEX_API_KEY or VITE_API_AUTH_TOKEN)
 * 
 * Never hardcodes default credentials into client bundles.
 */

export function getApiAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    try {
      const fromStorage = localStorage.getItem('apex_api_key') || localStorage.getItem('apex_auth_token');
      if (fromStorage && fromStorage.trim()) {
        return fromStorage.trim();
      }
      const fromWindow = (window as any).__APEX_API_KEY__;
      if (typeof fromWindow === 'string' && fromWindow.trim()) {
        return fromWindow.trim();
      }
    } catch {
      // LocalStorage access restricted in some private modes
    }
  }

  // Vite environment variables
  try {
    const envToken = (import.meta as any).env?.VITE_APEX_API_KEY || (import.meta as any).env?.VITE_API_AUTH_TOKEN;
    if (typeof envToken === 'string' && envToken.trim()) {
      return envToken.trim();
    }
  } catch {
    // env not available
  }

  return null;
}

export function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  const token = getApiAuthToken();
  if (token) {
    headers['X-API-Key'] = token;
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}
```

---

### Module 2: `frontend/src/stores/canonicalQuoteStore.ts`

#### Proposed Changes
Replace lines 114–168 in `updateFromWS`:
- Look up `existing` using `this.getQuote(symbol) || this.quotes.get(symbol)`.
- Declare and extract `incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0)`.
- If `incomingTs > 1e11`, normalize to epoch seconds (`Math.floor(incomingTs / 1000)`).
- Implement monotonic protection: `if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) return existing;`.
- Use `incomingTs` on lines 152 and 163.
- Store aliases for stripped symbol and `.NS` suffix to keep WS ingestion identical to REST.

#### Unified Diff: `frontend/src/stores/canonicalQuoteStore.ts`
```diff
--- a/frontend/src/stores/canonicalQuoteStore.ts
+++ b/frontend/src/stores/canonicalQuoteStore.ts
@@ -113,4 +113,15 @@
     const symbol = tick.symbol;
-    const existing = this.quotes.get(symbol);
+    const existing = this.getQuote(symbol) || this.quotes.get(symbol);
+    
+    let incomingTs = Number(tick.provider_timestamp || tick.timestamp || tick.last_trade_time || 0);
+    if (incomingTs > 1e11) {
+      incomingTs = Math.floor(incomingTs / 1000);
+    }
+
+    // Guard against out-of-order stale ticks (monotonic timestamp protection)
+    if (existing && existing.provider_timestamp > incomingTs && incomingTs > 0) {
+      return existing;
+    }
+
     const rawChange = tick.change !== undefined && tick.change !== null ? Number(tick.change) : null;
@@ -151,3 +162,3 @@
       provider_mode: tick.provider_mode || existing?.provider_mode || 'AUTHENTIC_LIVE',
-      provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),
+      provider_timestamp: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),
       received_timestamp: Math.floor(Date.now() / 1000),
@@ -162,3 +173,3 @@
       last_ws_ltp: ltp,
-      last_ws_ts: incomingTs,
+      last_ws_ts: incomingTs > 0 ? incomingTs : Math.floor(Date.now() / 1000),
     };
 
     this.quotes.set(symbol, canonical);
+    const stripped = symbol.replace('.NS', '').replace('.BO', '');
+    this.quotes.set(stripped, canonical);
+    this.quotes.set(`${stripped}.NS`, canonical);
     this.notify();
     return canonical;
```

---

### Module 3: `frontend/src/App.tsx`

#### Proposed Changes
1. Import `getAuthHeaders` from `./utils/auth`.
2. Update `handlePlacePaperOrder`:
   - Use `headers: getAuthHeaders()`.
   - On error or non-ok response, display error alert with message from backend.
3. Update `handleClosePaperPosition`:
   - Use `headers: getAuthHeaders()`.
   - Check `res.ok` and `data.status`: only remove position if `res.ok` AND `data.status` is `'CLOSED'` or `'PARTIALLY_CLOSED'` (or `data.success !== false`).
   - If non-ok or error, do **not** remove the position from `paperPositions`.
   - Display error notification and alert to user indicating why close failed.

#### Unified Diff: `frontend/src/App.tsx`
```diff
--- a/frontend/src/App.tsx
+++ b/frontend/src/App.tsx
@@ -28,2 +28,3 @@
 import { getMarketStatus } from './utils/marketStatus';
+import { getAuthHeaders } from './utils/auth';
 import {
@@ -668,5 +669,5 @@
     try {
       const res = await fetch('/api/paper/order', {
         method: 'POST',
-        headers: { 'Content-Type': 'application/json' },
+        headers: getAuthHeaders(),
         body: JSON.stringify({
@@ -689,6 +690,11 @@
           alert(`Order Rejected: ${data.reason}`);
+        } else {
+          alert(`Order Error: ${data.detail || data.reason || 'Unexpected order status'}`);
         }
+      } else {
+        const errData = await res.json().catch(() => ({}));
+        alert(`Failed to place paper order: ${errData.detail || 'Server returned HTTP ' + res.status}`);
       }
-    } catch {
-      // fallback
+    } catch (err: any) {
+      alert(`Network error placing paper order: ${err?.message || 'Connection failure'}`);
     }
   };
@@ -700,16 +706,23 @@
     try {
       const res = await fetch(`/api/paper/close/${id}`, {
         method: 'POST',
-        headers: { 'Content-Type': 'application/json' },
+        headers: getAuthHeaders(),
         body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
       });
       if (res.ok) {
         const data = await res.json();
-        if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
+        if (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED' || data.success !== false) {
+          if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
+          setPaperPositions((prev) => prev.filter((p) => p.id !== id));
+        } else {
+          alert(`Failed to close position for ${pos.symbol}: ${data.reason || data.detail || 'Execution rejected'}`);
+        }
+      } else {
+        const errData = await res.json().catch(() => ({}));
+        alert(`Failed to close position for ${pos.symbol}: ${errData.detail || 'Server returned HTTP ' + res.status}`);
       }
-    } catch {
-      // quiet
+    } catch (err: any) {
+      alert(`Network error closing position for ${pos.symbol}: ${err?.message || 'Connection failure'}`);
     }
-    setPaperPositions((prev) => prev.filter((p) => p.id !== id));
   };
```

---

### Module 4: `frontend/src/components/pages/SignalCenterPage.tsx`

#### Proposed Changes
1. Import `getAuthHeaders` from `../../utils/auth`.
2. In `handlePaperTrade`:
   - Replace `{ 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' }` with `getAuthHeaders()`.
   - Inspect `data.order_result?.status`:
     - If `order_result?.status === 'FILLED'`: Show green checkmark with fill price: `✓ ${signal.direction} ${symbol} — Filled at ₹${fillPrice}`.
     - If `order_result?.status === 'REJECTED'`: Show red error: `✗ Order Rejected: ${order_result.reason || 'Risk check failed'}`.
     - Else: Show warning status.
   - If `!res.ok`: Show red error with `data.detail` or HTTP status.
   - If network catch: Show network failure message.

#### Unified Diff: `frontend/src/components/pages/SignalCenterPage.tsx`
```diff
--- a/frontend/src/components/pages/SignalCenterPage.tsx
+++ b/frontend/src/components/pages/SignalCenterPage.tsx
@@ -10,2 +10,3 @@
 import { SignalDecision, ScannerCoverageSummary } from '../../types/intelligence';
+import { getAuthHeaders } from '../../utils/auth';
 
@@ -843,18 +844,26 @@
     try {
       const res = await fetch(`${API}/api/signals/${signal.signal_id}/paper-trade`, {
         method: 'POST',
-        headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' },
+        headers: getAuthHeaders(),
         body: JSON.stringify({ signal_id: signal.signal_id }),
       });
-      const data = await res.json();
+      const data = await res.json().catch(() => ({}));
       if (res.ok) {
-        setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
+        const orderResult = data.order_result;
+        if (orderResult?.status === 'FILLED') {
+          const fillPrice = orderResult.fill?.price ?? orderResult.fill_price ?? signal.entry;
+          setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Filled at ₹${Number(fillPrice).toFixed(2)}`);
+        } else if (orderResult?.status === 'REJECTED') {
+          setPaperTradeStatus(`✗ Order Rejected: ${orderResult.reason || 'Risk check failed'}`);
+        } else {
+          setPaperTradeStatus(`⚠ Order Status: ${orderResult?.status || 'Unknown'}`);
+        }
         setTimeout(() => setPaperTradeStatus(null), 4000);
       } else {
-        setPaperTradeStatus(`✗ ${data.detail || 'Paper trade failed'}`);
+        setPaperTradeStatus(`✗ ${data.detail || data.reason || `Paper trade failed (${res.status})`}`);
         setTimeout(() => setPaperTradeStatus(null), 4000);
       }
-    } catch (err) {
-      setPaperTradeStatus('✗ Paper trade request failed');
+    } catch (err: any) {
+      setPaperTradeStatus(`✗ Paper trade request failed: ${err?.message || 'Network error'}`);
       setTimeout(() => setPaperTradeStatus(null), 4000);
     }
```

---

### Module 5: `frontend/src/components/IndexTickerBar.tsx`

#### Proposed Changes
Remove lines 82–91 (`https://apex-market-worker-probe.onrender.com/api/worker/status` probe) so that worker telemetry strictly polls local `/api/worker/status`.

#### Unified Diff: `frontend/src/components/IndexTickerBar.tsx`
```diff
--- a/frontend/src/components/IndexTickerBar.tsx
+++ b/frontend/src/components/IndexTickerBar.tsx
@@ -70,22 +70,12 @@
   // Poll worker status from API every 10 seconds
   useEffect(() => {
     const fetchWorker = async () => {
       try {
         const res = await fetch('/api/worker/status');
         if (res.ok) {
           const data = await res.json();
           if (data && data.worker_status && data.worker_status !== 'NOT_STARTED') {
             setWorkerData(data);
-            return;
           }
         }
-        // Direct probe fallback if serverless proxy is cold or not started
-        try {
-          const probeRes = await fetch('https://apex-market-worker-probe.onrender.com/api/worker/status', { mode: 'cors' });
-          if (probeRes.ok) {
-            const probeData = await probeRes.json();
-            setWorkerData(probeData);
-          }
-        } catch {
-          // quiet if probe offline
-        }
       } catch {
         // quiet in dev or offline
       }
```

---

### Module 6 (Extra Hardening): `frontend/src/components/pages/PortfolioPage.tsx`
Line 69 in `PortfolioPage.tsx` calls `/api/paper/lifecycle/transition`. The Worker should also update it to use `headers: getAuthHeaders()`:
```diff
--- a/frontend/src/components/pages/PortfolioPage.tsx
+++ b/frontend/src/components/pages/PortfolioPage.tsx
@@ -10,2 +10,3 @@
 import { PaperPosition } from '../../types/indianMarket';
+import { getAuthHeaders } from '../../utils/auth';
 
@@ -69,3 +70,3 @@
       const res = await fetch('/api/paper/lifecycle/transition', {
         method: 'POST',
-        headers: { 'Content-Type': 'application/json' },
+        headers: getAuthHeaders(),
         body: JSON.stringify({ candidate_id: candidateId, new_state: newState, reason: 'User Promotion' }),
```

---

## 4. Verification Protocol

The Worker should verify the implementations using the following exact commands:

1. **Typecheck & Linting**:
   ```powershell
   cd C:\Tradinf2\frontend
   npm.cmd run lint
   ```
   **Expected Result**: Exit code 0, 0 errors.

2. **Frontend Production Build**:
   ```powershell
   cd C:\Tradinf2\frontend
   npm.cmd run build
   ```
   **Expected Result**: Vite builds production bundles into `dist/` cleanly without syntax or typing errors.

3. **Behavioral Invariant Checks**:
   - Backward tick test: Feed ticks with timestamp 100 followed by timestamp 50. Verify `canonicalQuoteStore` rejects timestamp 50.
   - Close failure test: Trigger `handleClosePaperPosition` when server returns 401 or 500. Verify the position remains in `paperPositions` and an error alert is displayed.
   - Signal execution test: Place paper trade from `SignalCenterPage` with backend returning `{ order_result: { status: 'REJECTED', reason: 'Insufficient margin' } }`. Verify notification displays `✗ Order Rejected: Insufficient margin`.
   - Loopback verification: Search `frontend/src` for `onrender.com` or external URLs; confirm zero external probes remain.
