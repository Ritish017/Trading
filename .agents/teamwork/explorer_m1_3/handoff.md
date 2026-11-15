# Handoff Report — Milestone 1: Security & Auth Explorer

**Agent**: `explorer_m1_3` (Security & Auth Explorer)  
**Parent Agent**: `b0e006c7-614f-4aa0-b311-d567b4a1a31b`  
**Working Directory**: `C:\Tradinf2\.agents\teamwork\explorer_m1_3\`  
**Date**: 2026-10-06  

---

## 1. Observation

1. **`backend/app/main.py:974-984` (`/api/paper/positions`)**:
   ```python
   @app.get("/api/paper/positions")
   async def get_paper_positions(account_id: Optional[str] = None, auth: Optional[AccountContext] = Depends(verify_api_key_optional)):
       if account_id:
           if not auth:
               raise HTTPException(status_code=401, detail="Authentication required to view specific account positions.")
           authorize_account_access(auth, account_id)
       summary = paper_engine.get_portfolio_summary(account_id=account_id or (auth.account_id if auth else None))
       if not summary.get("performance", {}).get("total_trades"):
           summary["performance"] = paper_bridge.get_performance_summary()
       return summary
   ```
   - When `account_id` is omitted in the query string, `if account_id:` is False.
   - An anonymous caller (`auth is None`) bypasses the authentication check entirely.
   - `summary = paper_engine.get_portfolio_summary(account_id=None)` evaluates `not account_id` as True for all positions in `self.positions`, disclosing the full global portfolio without credentials.

2. **`backend/app/main.py:2451-2511` (`/api/signals/{signal_id}/paper-trade`)**:
   - The route enforces `verify_api_key` and caller authorization (`authorize_account_access(auth, target_account)`).
   - However, lines 2468–2473 only check:
     ```python
     q_grade = getattr(signal.quality_grade, "value", signal.quality_grade)
     if q_grade in ("NO TRADE", "NO_TRADE"):
         raise HTTPException(status_code=400, detail="Cannot paper trade a NO TRADE signal")
     if not signal.entry or not signal.stop_loss:
         raise HTTPException(status_code=400, detail="Signal missing entry price or stop loss")
     ```
   - It omits checking `signal.state == "QUALIFIED"`. Expired, invalidated, cancelled, candidate, or already-triggered signals are accepted.
   - It omits checking `signal.expiry` against current UTC time.
   - It omits checking directional geometry (`stop < entry` for LONG; `stop > entry` for SHORT).
   - When order execution is rejected by the risk engine, it returns HTTP 200 with `{ "order_result": { "status": "REJECTED" } }`.

3. **`frontend/src/App.tsx` (Lines 533, 669–672, 701–714)**:
   - Line 533: `fetch('/api/paper/positions')` sends no auth headers.
   - Line 669: `handlePlacePaperOrder` sends `fetch('/api/paper/order', { headers: { 'Content-Type': 'application/json' } })` with no auth headers.
   - Line 701: `handleClosePaperPosition` sends `fetch('/api/paper/close/${id}', ...)` with no auth headers.
   - Line 713:
     ```typescript
     setPaperPositions((prev) => prev.filter((p) => p.id !== id));
     ```
     executes unconditionally outside `if (res.ok)`. When a close request fails (HTTP 401, 500, network failure), the position is removed from local client state while remaining open on the server ledger.

4. **`frontend/src/components/pages/SignalCenterPage.tsx:846, 850`**:
   - Line 846: Hardcoded dev key:
     `headers: { 'Content-Type': 'application/json', 'X-API-Key': 'apex_default_dev_key' }`
   - Line 850: Checks only `if (res.ok)`:
     ```typescript
     if (res.ok) {
       setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Paper order placed`);
     ```
     Falsely displays order placement even if backend returned `{ "order_result": { "status": "REJECTED" } }`.

5. **`backend/tests/test_routing_canonical.py:32`**:
   - Line 32: `resp = await client.get("/api/paper/positions")` executes without auth headers and asserts `resp.status_code == 200`.

---

## 2. Logic Chain

1. **Information Leakage via Auth Bypass**:
   - From Observation 1, `GET /api/paper/positions` without query parameters never invokes `authorize_account_access` or verifies `auth`.
   - In `paper_trading/engine.py:370-373`, `account_id=None` causes all stored positions to pass the filter `not account_id or ...`.
   - Therefore, any unauthenticated attacker on the local network or loopback can extract the complete portfolio state.
   - Remediation requires switching the dependency from `verify_api_key_optional` to `verify_api_key`, setting `target_account = account_id or auth.account_id`, and verifying `authorize_account_access(auth, target_account)`.

2. **Invalid Order Execution via State/Expiry Bypass**:
   - From Observation 2, `paper_trade_from_signal` relies on `apex_signal_store.get_signal_by_id(signal_id)`.
   - Because `signal.state` and `signal.expiry` are not checked, an expired or invalidated signal can still create a live paper order.
   - Remediation requires validating `signal.state == "QUALIFIED"` (raising HTTP 400 otherwise), verifying `datetime.now(timezone.utc) <= expiry_dt` (raising HTTP 400 otherwise), and validating directional geometry.

3. **Frontend Desynchronization and Auth Rejection**:
   - From Observation 3, when `/api/paper/positions`, `/api/paper/order`, and `/api/paper/close/{id}` require `verify_api_key`, frontend calls without headers will fail with HTTP 401.
   - From Observation 3 (line 713), if the close request returns 401, the position is stripped from client UI while open on the backend.
   - Remediation requires:
     1. Implementing `getAuthHeaders()` in `frontend/src/utils/apiAuth.ts` resolving from `VITE_API_KEY` or `localStorage`.
     2. Passing `getAuthHeaders()` in `App.tsx`, `SignalCenterPage.tsx`, and `PortfolioPage.tsx`.
     3. Moving position deletion in `handleClosePaperPosition` strictly inside `if (res.ok && (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED'))`, and displaying user notifications on failure.
     4. Removing hardcoded `'apex_default_dev_key'` from `SignalCenterPage.tsx` and verifying `order_result.status === 'FILLED'` before showing fill confirmations.

4. **Test Suite Adaptation**:
   - From Observation 5, enforcing `verify_api_key` on `/api/paper/positions` will cause `test_canonical_paper_positions_http_payload` in `test_routing_canonical.py` to receive 401 unless auth headers are supplied.
   - `test_security_hardening.py` needs 8 new explicit tests covering unauthenticated positions (401), authenticated positions (200), cross-account query (403), unauthenticated signal trade (401), cross-account signal trade (403), unqualified signal trade (400), expired signal trade (400), and valid signal trade fill (200).

---

## 3. Caveats

- **No Caveats**: All investigations were performed directly against current source files on disk in `C:\Tradinf2`. Exact line numbers, AST signatures, and execution flows were mapped and verified.

---

## 4. Conclusion

The security hardening for Milestone 1 (R1/R5) requires four coordinated, non-breaking modifications:
1. **`backend/app/main.py`**:
   - Enforce `auth: AccountContext = Depends(verify_api_key)` on `GET /api/paper/positions` and scope to `target_account = account_id or auth.account_id`.
   - Add state validation (`QUALIFIED`), expiration time check, geometry check, and URL/body identity check to `POST /api/signals/{signal_id}/paper-trade`.
2. **`frontend/src/utils/apiAuth.ts`**:
   - Create centralized token resolution utility checking `import.meta.env.VITE_API_KEY` then `localStorage.getItem('apex_api_key')`, outputting both `X-API-Key` and `Authorization: Bearer <token>`.
3. **Frontend Component Hardening**:
   - `frontend/src/App.tsx`: Inject auth headers on `/api/paper/positions`, `/api/paper/order`, and `/api/paper/close/{id}`; retain open positions on close request failures.
   - `frontend/src/components/pages/SignalCenterPage.tsx`: Strip hardcoded dev key; inspect `data.order_result?.status === 'FILLED'`.
   - `frontend/src/components/pages/PortfolioPage.tsx`: Inject auth headers on candidate promotion.
4. **Backend Test Suite Hardening**:
   - Add 8 unit and integration tests to `backend/tests/test_security_hardening.py`.
   - Add auth header monkeypatch to `backend/tests/test_routing_canonical.py`.

---

## 5. Verification Method

1. **Verify Backend Security Hardening**:
   ```powershell
   python -m pytest backend/tests/test_security_hardening.py backend/tests/acceptance/test_security_acceptance.py -v
   ```
   *Expected*: All tests pass, verifying HTTP 401 for anonymous calls, HTTP 403 for cross-account attempts, HTTP 400 for unqualified/expired signals, and HTTP 200 for authenticated calls.

2. **Verify Canonical Routing and Paper Trading Regression**:
   ```powershell
   python -m pytest backend/tests/test_routing_canonical.py backend/tests/test_unified_paper_order.py -v
   ```
   *Expected*: Passes with 100% success.

3. **Verify Frontend Clean Build & Lint**:
   ```powershell
   cd frontend
   npm.cmd run lint
   ```
   *Expected*: Zero TypeScript compilation errors (`tsc --noEmit` exit code 0).

4. **Inspection Locations**:
   - Backend diff: `C:\Tradinf2\.agents\teamwork\explorer_m1_3\report.md` Section 2
   - Frontend diff: `C:\Tradinf2\.agents\teamwork\explorer_m1_3\report.md` Section 3
   - Pytest code: `C:\Tradinf2\.agents\teamwork\explorer_m1_3\report.md` Section 4
