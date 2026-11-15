# Milestone 1: Authentication Enforcement & Endpoint Protection Report

**Author**: Security & Auth Explorer (`explorer_m1_3`)  
**Date**: 2026-10-06  
**Scope**: Milestone 1 (R1/R5) Security Hardening, Endpoint Auth Enforcement, Frontend Auth Alignment, and Pytest Suite Verification.  
**Target Repository**: `C:\Tradinf2`  

---

## 1. Executive Summary

A comprehensive, read-only architectural investigation was conducted across the backend authentication layer (`backend/app/security/auth.py`), route endpoints (`backend/app/main.py`), frontend mutation handlers (`frontend/src/App.tsx`, `SignalCenterPage.tsx`, `PortfolioPage.tsx`), and the automated security test suite (`backend/tests/test_security_hardening.py`).

### Key Discoveries & Vulnerabilities:
1. **Unauthenticated Portfolio Disclosure in `/api/paper/positions` (`main.py:974-984`)**:
   - The route depends on `verify_api_key_optional`.
   - When callers omit the optional `account_id` query parameter, authentication is never checked (`if account_id:` evaluates to `False`).
   - The endpoint invokes `paper_engine.get_portfolio_summary(account_id=None)`, returning all open positions, balances, margin locked, and closed trades across all accounts on the platform to anonymous callers.
2. **Missing State, Expiry, and Geometry Guards in `/api/signals/{id}/paper-trade` (`main.py:2451-2511`)**:
   - The route enforces `verify_api_key` and tenant isolation via `authorize_account_access`.
   - However, it **does not verify** that the signal is in `SignalState.QUALIFIED`. Expired, invalidated, cancelled, or already-triggered signals are accepted.
   - It **does not verify** signal expiration timestamps against the current time.
   - It **does not verify** directional trade geometry (`stop < entry` for LONG; `stop > entry` for SHORT).
   - If the paper engine rejects the order, the endpoint returns HTTP 200 with `{ "order_result": { "status": "REJECTED" } }`, which naive frontend callers mistake for an execution fill.
3. **Frontend Auth Absence, Credential Leaks, and Desynchronization Bugs**:
   - `App.tsx` sends unauthenticated requests to `/api/paper/positions`, `/api/paper/order`, and `/api/paper/close/{id}`.
   - `SignalCenterPage.tsx:846` leaks a hardcoded dev key (`'X-API-Key': 'apex_default_dev_key'`).
   - `SignalCenterPage.tsx:850` treats any HTTP 200 `res.ok` as fill confirmation, falsely displaying "Paper order placed" on rejected orders.
   - `App.tsx:713` contains a critical desynchronization bug: upon a failed close request (e.g., HTTP 401 Unauthorized or network error), it unconditionally purges the position from client state, leaving the server ledger still holding and marking the open position to market.
4. **Test Suite Coverage Gaps**:
   - Existing `test_security_hardening.py` covers mutations but misses unauthenticated queries to `/api/paper/positions`.
   - Existing `test_routing_canonical.py` calls `/api/paper/positions` without headers, which currently passes only because of the auth bypass bug.

---

## 2. Backend Endpoint Investigation & Proposed Changes

### 2.1 `/api/paper/positions` (line 974)

#### Root Cause Analysis:
In `backend/app/main.py:974-984`:
```python
@app.get("/api/paper/positions")
async def get_paper_positions(account_id: Optional[str] = None, auth: Optional[AccountContext] = Depends(verify_api_key_optional)):
    """Returns the canonical unified paper trading portfolio."""
    if account_id:
        if not auth:
            raise HTTPException(status_code=401, detail="Authentication required to view specific account positions.")
        authorize_account_access(auth, account_id)
    summary = paper_engine.get_portfolio_summary(account_id=account_id or (auth.account_id if auth else None))
    if not summary.get("performance", {}).get("total_trades"):
        summary["performance"] = paper_bridge.get_performance_summary()
    return summary
```
When a caller makes a request to `GET /api/paper/positions`:
- `account_id` is `None` (omitted).
- `auth` is `None` (omitted).
- `if account_id:` evaluates to `False`, so lines 978–980 are completely skipped.
- `account_id or (auth.account_id if auth else None)` evaluates to `None`.
- `paper_engine.get_portfolio_summary(account_id=None)` evaluates:
  ```python
  relevant_positions = [
      p for p in self.positions.values()
      if not account_id or p.get("account_id", "primary_personal_account") == account_id
  ]
  ```
  Since `not account_id` is `True`, every open position across all users is returned.

#### Proposed Exact Replacement:
Change `auth: Optional[AccountContext] = Depends(verify_api_key_optional)` to `auth: AccountContext = Depends(verify_api_key)` and strictly scope to `target_account`:

```python
@app.get("/api/paper/positions")
async def get_paper_positions(
    account_id: Optional[str] = None,
    auth: AccountContext = Depends(verify_api_key),
):
    """
    Returns the canonical unified paper trading portfolio for the authenticated account.
    Enforces fail-closed authentication: unauthenticated callers are rejected with 401.
    Enforces account isolation: callers cannot inspect other accounts' positions (403).
    """
    target_account = account_id or auth.account_id
    authorize_account_access(auth, target_account)
    summary = paper_engine.get_portfolio_summary(account_id=target_account)
    if not summary.get("performance", {}).get("total_trades"):
        summary["performance"] = paper_bridge.get_performance_summary()
    return summary
```

#### Invariants Enforced:
1. **Fail-Closed**: If `settings.api_auth_token` is unconfigured, or if the client omits or sends an invalid token, `verify_api_key` immediately raises `HTTP 401 Unauthorized`.
2. **Strict Account Scoping**: If `account_id` is omitted, the portfolio is scoped to `auth.account_id`.
3. **Cross-Account Isolation**: If `account_id` is provided, `authorize_account_access(auth, target_account)` verifies `target_account == auth.account_id`, returning `HTTP 403 Forbidden` on mismatched accounts.

---

### 2.2 `/api/signals/{signal_id}/paper-trade` (lines 2451-2511)

#### Root Cause Analysis:
In `backend/app/main.py:2451-2511`:
```python
@app.post("/api/signals/{signal_id}/paper-trade")
async def paper_trade_from_signal(
    signal_id: str,
    req: PaperTradeFromSignalRequest,
    auth: AccountContext = Depends(verify_api_key),
):
    signal = apex_signal_store.get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    q_grade = getattr(signal.quality_grade, "value", signal.quality_grade)
    if q_grade in ("NO TRADE", "NO_TRADE"):
        raise HTTPException(status_code=400, detail="Cannot paper trade a NO TRADE signal")

    if not signal.entry or not signal.stop_loss:
        raise HTTPException(status_code=400, detail="Signal missing entry price or stop loss")

    target_account = req.account_id or auth.account_id
    authorize_account_access(auth, target_account)
    ...
```
Defects identified:
1. **No State Check**: The route does not check `signal.state`. Signals in `EXPIRED`, `INVALIDATED`, `CANCELLED`, `TRIGGERED`, `ACTIVE`, or `REJECTED` are accepted.
2. **No Expiry Timestamp Check**: Signals with an `expiry` timestamp in the past are accepted.
3. **No Directional Geometry Validation**: If `signal.direction == "LONG"` and `signal.stop_loss.price >= signal.entry`, the trade is submitted despite an inverted stop.
4. **URL vs Body Discrepancy**: If `req.signal_id != signal_id`, the endpoint proceeds using the URL `signal_id`, potentially masking client bugs.

#### Proposed Exact Replacement:
```python
@app.post("/api/signals/{signal_id}/paper-trade")
async def paper_trade_from_signal(
    signal_id: str,
    req: PaperTradeFromSignalRequest,
    auth: AccountContext = Depends(verify_api_key),
):
    """
    Converts a qualified signal into an authoritative paper trade order.
    Uses the signal's computed entry price, stop, targets, and sizing.
    Passes through the risk engine before executing.

    Requires authentication. The signal must be in QUALIFIED state and unexpired.
    """
    if req.signal_id and req.signal_id != signal_id:
        raise HTTPException(
            status_code=400,
            detail=f"Mismatched signal_id between path ('{signal_id}') and body ('{req.signal_id}')."
        )

    signal = apex_signal_store.get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    # 1. State Validation: Only QUALIFIED signals can be converted into orders
    sig_state = getattr(signal.state, "value", signal.state)
    if sig_state != "QUALIFIED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot paper trade signal in '{sig_state}' state. Only QUALIFIED signals can be executed."
        )

    # 2. Quality Grade Validation
    q_grade = getattr(signal.quality_grade, "value", signal.quality_grade)
    if q_grade in ("NO TRADE", "NO_TRADE"):
        raise HTTPException(status_code=400, detail="Cannot paper trade a NO TRADE signal")

    # 3. Expiration Timestamp Validation
    if signal.expiry:
        try:
            from datetime import datetime, timezone
            expiry_str = signal.expiry.replace("Z", "+00:00")
            expiry_dt = datetime.fromisoformat(expiry_str)
            if datetime.now(timezone.utc) > expiry_dt:
                signal.state = "EXPIRED"
                raise HTTPException(
                    status_code=400,
                    detail=f"Signal {signal_id} expired at {signal.expiry}. Cannot execute expired setup."
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking signal expiry timestamp '{signal.expiry}': {e}")

    # 4. Entry and Stop Loss Presence
    if not signal.entry or not signal.stop_loss:
        raise HTTPException(status_code=400, detail="Signal missing entry price or stop loss")

    # 5. Directional Geometry Validation
    sig_dir = getattr(signal.direction, "value", signal.direction)
    stop_price = getattr(signal.stop_loss, "price", None)
    if stop_price is None:
        try:
            stop_price = float(signal.stop_loss)
        except (ValueError, TypeError):
            stop_price = signal.entry

    if sig_dir == "LONG" and stop_price >= signal.entry:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid LONG trade geometry: stop loss (₹{stop_price}) must be below entry (₹{signal.entry})"
        )
    elif sig_dir == "SHORT" and stop_price <= signal.entry:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SHORT trade geometry: stop loss (₹{stop_price}) must be above entry (₹{signal.entry})"
        )

    # 6. Tenant and Account Authorization
    target_account = req.account_id or auth.account_id
    authorize_account_access(auth, target_account)

    # 7. Order Construction
    side = "BUY" if sig_dir == "LONG" else "SELL"
    quantity = req.quantity_override or (
        signal.position_size.quantity if signal.position_size else 1
    )

    order_req = PaperOrderRequest(
        symbol=signal.symbol,
        companyName=signal.symbol,
        productType="MIS",  # Intraday for systematic signal trades
        side=side,
        quantity=quantity,
        price=signal.entry,
        targetPrice=signal.targets[0].price if signal.targets else None,
        stopLoss=stop_price,
        order_type="MARKET",
        exchange=signal.exchange,
        source=f"SIGNAL_{signal_id[:8]}",
        account_id=target_account,
        idempotency_key=f"signal_{signal_id}",
    )

    # 8. Execution through Authoritative Paper Engine
    res = paper_engine.execute_order(order_req, account_id=target_account)
    if res.get("status") == "FILLED":
        await paper_engine.sync_order_to_db(order_req.model_dump(), res["position"], target_account)
        signal.state = "TRIGGERED"

    return {
        "order_result": res,
        "signal": signal.dict(),
        "signal_id": signal_id,
    }
```

---

## 3. Frontend Authentication Architecture & Propagation

### 3.1 Token Resolution Hierarchy & Helper (`frontend/src/utils/apiAuth.ts`)

To eliminate hardcoded credentials (`apex_default_dev_key`) and provide seamless authentication across the application, create `frontend/src/utils/apiAuth.ts`:

```typescript
/**
 * APEX Quantitative Trading Workstation — Centralized API Authentication Utility
 * 
 * Manages authentication credentials across environment configuration and local storage,
 * formatting standard headers conforming to backend FastAPI dependencies (X-API-Key and HTTP Bearer).
 */

const STORAGE_KEY = 'apex_api_key';
const LEGACY_STORAGE_KEY = 'apexnse_api_key';

/**
 * Resolves the active authentication token.
 * Priority:
 * 1. Vite environment variable: import.meta.env.VITE_API_KEY
 * 2. Browser localStorage: 'apex_api_key' or 'apexnse_api_key'
 * 3. Empty string if unconfigured
 */
export function getApiAuthToken(): string {
  const envKey = (import.meta as any).env?.VITE_API_KEY;
  if (typeof envKey === 'string' && envKey.trim()) {
    return envKey.trim();
  }

  try {
    const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
    if (stored && stored.trim()) {
      return stored.trim();
    }
  } catch (err) {
    console.warn('[APEX Auth] Failed reading token from localStorage:', err);
  }

  return '';
}

/**
 * Persists an API authentication token to browser storage.
 */
export function setApiAuthToken(token: string): void {
  try {
    if (token && token.trim()) {
      localStorage.setItem(STORAGE_KEY, token.trim());
    } else {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
  } catch (err) {
    console.error('[APEX Auth] Failed saving token to localStorage:', err);
  }
}

/**
 * Generates HTTP request headers including authentication credentials.
 * Supplies both X-API-Key and Authorization Bearer headers for seamless alignment
 * with backend FastAPI `verify_api_key`.
 */
export function getAuthHeaders(additionalHeaders: Record<string, string> = {}): Record<string, string> {
  const token = getApiAuthToken();
  const headers: Record<string, string> = {
    ...additionalHeaders,
  };

  if (token) {
    headers['X-API-Key'] = token;
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}
```

### 3.2 Exact Changes in `frontend/src/App.tsx`

#### 1. Fetching Initial Positions (`line 532`):
```typescript
// Before:
useEffect(() => {
  fetch('/api/paper/positions')
    .then((res) => res.json())
    .then((data) => {
      if (data && Array.isArray(data.positions)) {
        setPaperPositions(data.positions);
        if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
      }
    })
    .catch(() => {});
}, []);

// After:
useEffect(() => {
  fetch('/api/paper/positions', {
    headers: getAuthHeaders(),
  })
    .then(async (res) => {
      if (!res.ok) {
        if (res.status === 401) {
          console.warn('[APEX Auth] /api/paper/positions requires authentication. Configure VITE_API_KEY or localStorage.');
        }
        return null;
      }
      return res.json();
    })
    .then((data) => {
      if (data && Array.isArray(data.positions)) {
        setPaperPositions(data.positions);
        if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
      }
    })
    .catch((err) => {
      console.error('[APEX Auth] Error fetching initial paper positions:', err);
    });
}, []);
```

#### 2. Placing Paper Orders (`line 669`):
```typescript
// Before:
const res = await fetch('/api/paper/order', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ... }),
});

// After:
const res = await fetch('/api/paper/order', {
  method: 'POST',
  headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
  body: JSON.stringify({
    symbol: targetStock.symbol,
    companyName: targetStock.name,
    productType: order.productType,
    side: order.side,
    quantity: order.quantity,
    price: targetStock.price,
    targetPrice: order.targetPrice,
    stopLoss: order.stopLoss,
  }),
});
if (res.status === 401) {
  alert('Authentication required: Please configure a valid API key in settings or environment.');
  return;
}
```

#### 3. Closing Paper Position & State Retention (`lines 697-714`):
```typescript
// Before (BUGGY):
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
  setPaperPositions((prev) => prev.filter((p) => p.id !== id)); // Deletes even on failure!
};

// After (FIXED):
const handleClosePaperPosition = async (id: string, closePrice?: number) => {
  const pos = paperPositions.find((p) => p.id === id);
  if (!pos) return;
  try {
    const res = await fetch(`/api/paper/close/${id}`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ close_price: closePrice || pos.currentPrice }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to close position for ${pos.symbol}: ${err.detail || 'Server returned HTTP ' + res.status}`);
      return; // CRITICAL: Retain position in client state!
    }
    const data = await res.json();
    if (data.status === 'CLOSED' || data.status === 'PARTIALLY_CLOSED') {
      if (data.available_capital !== undefined) setPaperBalance(data.available_capital);
      setPaperPositions((prev) => prev.filter((p) => p.id !== id));
    } else {
      alert(`Order rejected: ${data.reason || 'Failed to close position'}`);
      // Position is retained
    }
  } catch (err: any) {
    alert(`Network error closing position for ${pos.symbol}: ${err.message}`);
    // Position is retained
  }
};
```

---

### 3.3 Exact Changes in `frontend/src/components/pages/SignalCenterPage.tsx`

#### Removing Hardcoded Dev Key & Validating Order Fill State (`lines 842-861`):
```typescript
// Before:
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

// After:
const handlePaperTrade = useCallback(async (signal: SignalDecision) => {
  try {
    const res = await fetch(`${API}/api/signals/${signal.signal_id}/paper-trade`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ signal_id: signal.signal_id }),
    });
    const data = await res.json();
    if (res.ok) {
      const orderResult = data.order_result;
      if (orderResult?.status === 'FILLED') {
        const fillPrice = orderResult.fill_price ? Number(orderResult.fill_price).toFixed(2) : signal.entry;
        setPaperTradeStatus(`✓ ${signal.direction} ${signal.symbol.replace('.NS', '')} — Filled at ₹${fillPrice}`);
      } else if (orderResult?.status === 'REJECTED') {
        setPaperTradeStatus(`✗ Order Rejected: ${orderResult.reason || 'Risk limit exceeded'}`);
      } else {
        setPaperTradeStatus(`⚠ Order Status: ${orderResult?.status || 'Unknown'}`);
      }
      setTimeout(() => setPaperTradeStatus(null), 4000);
    } else {
      setPaperTradeStatus(`✗ ${data.detail || 'Paper trade failed (' + res.status + ')'}`);
      setTimeout(() => setPaperTradeStatus(null), 4000);
    }
  } catch (err: any) {
    setPaperTradeStatus(`✗ Paper trade error: ${err.message || 'Network failure'}`);
    setTimeout(() => setPaperTradeStatus(null), 4000);
  }
}, []);
```

---

### 3.4 Exact Changes in `frontend/src/components/pages/PortfolioPage.tsx`

#### Adding Auth Headers on Lifecycle Candidate Promotion (`lines 67-80`):
```typescript
// Before:
const handlePromoteCandidate = async (candidateId: string, newState: string) => {
  try {
    const res = await fetch('/api/paper/lifecycle/transition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId, new_state: newState, reason: 'User Promotion' }),
    });
    if (res.ok) {
      await loadCandidates();
    }
  } catch (e) {
    // ignore
  }
};

// After:
const handlePromoteCandidate = async (candidateId: string, newState: string) => {
  try {
    const res = await fetch('/api/paper/lifecycle/transition', {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ candidate_id: candidateId, new_state: newState, reason: 'User Promotion' }),
    });
    if (res.ok) {
      await loadCandidates();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Candidate transition failed: ${err.detail || 'HTTP ' + res.status}`);
    }
  } catch (e: any) {
    alert(`Network error transitioning candidate: ${e.message}`);
  }
};
```

---

## 4. Test Verification Suite Hardening

### 4.1 Test Additions for `backend/tests/test_security_hardening.py`

Add the following 8 tests to `backend/tests/test_security_hardening.py` to prove both negative (unauthenticated/unauthorized) and positive (authenticated/valid) behavior:

```python
from backend.app.signal_engine.signal_store import signal_store as apex_signal_store
from backend.app.signal_engine.models import (
    SignalDecision, SignalDirection, SignalState, SignalQualityGrade, StopLossResult, TargetLevel, PositionSizing
)

def test_unauthenticated_paper_positions_rejected(client, monkeypatch):
    """FAIL-CLOSED: Unauthenticated GET /api/paper/positions must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.get("/api/paper/positions")
    assert res.status_code == 401
    assert "Invalid or missing API authentication token" in res.json()["detail"]


def test_authenticated_paper_positions_succeeds(client, monkeypatch):
    """GET /api/paper/positions with valid X-API-Key returns portfolio summary."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.get(
        "/api/paper/positions",
        headers={"X-API-Key": "secret-test-token-xyz"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "positions" in data
    assert "available_capital" in data
    assert "capital" in data


def test_cross_account_positions_query_rejected(client, monkeypatch):
    """Cross-account GET /api/paper/positions?account_id=... must return 403."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    res = client.get(
        "/api/paper/positions?account_id=account_b",
        headers={"X-API-Key": "token_a"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]


def test_unauthenticated_signal_paper_trade_rejected(client, monkeypatch):
    """Anonymous POST /api/signals/{id}/paper-trade must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.post(
        "/api/signals/test_sig_001/paper-trade",
        json={"signal_id": "test_sig_001"}
    )
    assert res.status_code == 401


def test_signal_paper_trade_cross_account_rejected(client, monkeypatch):
    """Account A cannot execute a signal trade for Account B (403 Forbidden)."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    
    # Setup test signal
    sig = SignalDecision(
        signal_id="sig_auth_cross",
        symbol="SBIN.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=800.0,
        stop_loss=StopLossResult(price=780.0, method="ATR"),
        targets=[TargetLevel(price=840.0, level=1)],
        position_size=PositionSizing(quantity=10, capital_allocated=8000.0),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_auth_cross/paper-trade",
        headers={"X-API-Key": "token_a"},
        json={"signal_id": "sig_auth_cross", "account_id": "account_b"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]


def test_signal_paper_trade_unqualified_rejected(client, monkeypatch):
    """Signals not in QUALIFIED state must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_unqualified",
        symbol="INFY.NS",
        direction=SignalDirection.LONG,
        state=SignalState.CANDIDATE,  # Not QUALIFIED!
        quality_grade=SignalQualityGrade.A,
        entry=1800.0,
        stop_loss=StopLossResult(price=1750.0, method="ATR"),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_unqualified/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_unqualified"}
    )
    assert res.status_code == 400
    assert "Only QUALIFIED signals can be executed" in res.json()["detail"]


def test_signal_paper_trade_expired_rejected(client, monkeypatch):
    """Expired signals must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_expired",
        symbol="RELIANCE.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=2800.0,
        stop_loss=StopLossResult(price=2750.0, method="ATR"),
        expiry="2020-01-01T00:00:00Z",  # Expired in past
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_expired/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_expired"}
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_authenticated_signal_paper_trade_succeeds(client, monkeypatch):
    """Valid QUALIFIED signal executed by authenticated caller fills order."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_valid_exec",
        symbol="TCS.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=3800.0,
        stop_loss=StopLossResult(price=3700.0, method="ATR"),
        targets=[TargetLevel(price=4000.0, level=1)],
        position_size=PositionSizing(quantity=5, capital_allocated=19000.0),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_valid_exec/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_valid_exec"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["order_result"]["status"] == "FILLED"
    assert data["signal"]["state"] == "TRIGGERED"
```

### 4.2 Updating `backend/tests/test_routing_canonical.py`
In `backend/tests/test_routing_canonical.py:28-34`:
```python
@pytest.mark.asyncio
async def test_canonical_paper_positions_http_payload(monkeypatch):
    """Execute HTTP GET /api/paper/positions and verify canonical unified portfolio payload."""
    monkeypatch.setattr(settings, "api_auth_token", "test-canonical-token")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/paper/positions", headers={"X-API-Key": "test-canonical-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert "positions" in data
        assert isinstance(data["positions"], list)
        ...
```
Passing the auth header prevents regression when `verify_api_key` is enforced.

---

## 5. Verification Commands

Run the following commands to verify:

1. **Security & Auth Suite**:
   ```powershell
   python -m pytest backend/tests/test_security_hardening.py -v
   ```
2. **Acceptance Security Suite**:
   ```powershell
   python -m pytest backend/tests/acceptance/test_security_acceptance.py -v
   ```
3. **Canonical Routing Suite**:
   ```powershell
   python -m pytest backend/tests/test_routing_canonical.py -v
   ```
4. **Combined Regression Suite**:
   ```powershell
   python -m pytest backend/tests/test_security_hardening.py backend/tests/test_unified_paper_order.py backend/tests/signal_engine/test_financial_invariants.py backend/tests/acceptance/test_security_acceptance.py backend/tests/test_routing_canonical.py -q
   ```
5. **Frontend TypeCheck & Lint**:
   ```powershell
   cd frontend
   npm.cmd run lint
   ```
