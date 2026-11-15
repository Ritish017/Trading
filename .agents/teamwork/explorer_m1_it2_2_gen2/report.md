# Investigation Report: Security & Probe Removal & Signal Expiry Validation

**Date:** 2026-10-06  
**Investigator:** Teamwork Explorer (Security & Probe Removal Explorer)  
**Target File:** `backend/app/main.py`  
**Milestone:** Milestone 1 Iteration 2  

---

## Executive Summary
This investigation covers two critical security and architectural integrity defects identified in `backend/app/main.py`:
1. **External Render Probe Leakage (6 occurrences):** Lines 195, 234, 264, 333, 382, and 406 fall back to an external URL `https://apex-market-worker-probe.onrender.com` when the local worker heartbeat is stale or unstarted. This violates Task 4, Requirement R5 (local loopback isolation), and creates external network dependencies, privacy leaks, and potential hangs in offline/airgapped environments.
2. **Signal Expiry Validation Failure in `/api/signals/{signal_id}/paper-trade`:** Lines 2513–2528 use naive ISO parsing followed by offset-aware datetime comparison. When `signal.expiry` is offset-naive, Python raises `TypeError: can't compare offset-naive and offset-aware datetimes`. The enclosing broad `except Exception as e:` catches this exception, logs a warning, and allows the request to proceed (fail-open), executing potentially expired or corrupt trading setups. Furthermore, invalid timestamp formats also bypass rejection.

This report provides the full evidence chain, root-cause analysis, and exact drop-in code replacements for the implementation agent.

---

## Defect 1: External Render Probe Fallback

### Observations
Ripgrep across `backend/` confirmed exactly 6 references to `onrender.com` and `RENDER_WORKER_URL`:
- `backend/app/main.py:195` in `worker_health()`
- `backend/app/main.py:234` in `get_worker_status()`
- `backend/app/main.py:264` in `get_session_report()`
- `backend/app/main.py:333` in `get_session_checkpoints()`
- `backend/app/main.py:382` in `get_audit_events()`
- `backend/app/main.py:406` in `get_session_status()`

### Impact
- In dev or local mode when the background worker daemon is stopped or its heartbeat is stale (>15 seconds), endpoints attempt external HTTP requests to `https://apex-market-worker-probe.onrender.com` with a 3.0s or 4.0s timeout.
- This breaks local loopback isolation (R5: *"Bind services to local loopback, keep API keys and provider tokens server-side"*).
- `IndexTickerBar.tsx` polls `/api/worker/status` every 10 seconds, repeatedly triggering outbound traffic.

### Solution Design
1. Completely remove `https://apex-market-worker-probe.onrender.com` and `RENDER_WORKER_URL`.
2. Introduce optional `LOCAL_WORKER_URL` lookup (e.g. `http://127.0.0.1:8001`) with strict loopback validation (`127.0.0.1` or `localhost`).
3. If `LOCAL_WORKER_URL` is not set (default) or fails, rely purely on local state checks (local PostgreSQL/SQLite database repository, disk reports, and `SessionLifecycleManager`).

---

## Defect 2: Expiry Parsing & Fail-Open in `/api/signals/{signal_id}/paper-trade`

### Observations
Lines 2512–2528 in `backend/app/main.py`:
```python
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
```

### Flaws
1. If `signal.expiry` is an offset-naive timestamp (e.g. `"2026-10-06T18:00:00"`), `expiry_dt.tzinfo` is `None`. `datetime.now(timezone.utc) > expiry_dt` raises `TypeError`.
2. `except Exception as e:` catches the `TypeError` (or any `ValueError` from invalid date format), logs a warning, and swallows the error without raising an `HTTPException`.
3. Execution continues to line 2530+ and places the paper order, completely bypassing the expiration gate.

### Solution Design
1. Strip leading/trailing whitespace and normalize `'Z'` suffix to `'+00:00'`.
2. Parse with `datetime.fromisoformat()`.
3. Check `if expiry_dt.tzinfo is None:` and attach `timezone.utc`: `expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)`. If already aware, normalize to UTC: `expiry_dt = expiry_dt.astimezone(timezone.utc)`.
4. If `datetime.now(timezone.utc) > expiry_dt`, set `signal.state = "EXPIRED"` and raise `HTTPException(status_code=400, detail="Invalid or expired signal timestamp")`.
5. On any parsing or validation exception (`ValueError`, `TypeError`, etc.), log warning and **fail closed** by raising `HTTPException(status_code=400, detail="Invalid or expired signal timestamp")`.

---

## Detailed Drop-In Code Replacements

### 1. `backend/app/main.py` lines 193–205 in `worker_health()`

**Existing (lines 193–205):**
```python
        # If database has no heartbeat or is stale, attempt fallback read from live Render worker probe
        if st.get("worker_status") in ("NOT_STARTED", "UNKNOWN") or st.get("is_stale", True):
            render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
            if render_worker_url:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(f"{render_worker_url.rstrip('/')}/health/worker")
                        if resp.status_code == 200:
                            return resp.json()
                except Exception:
                    pass
```

**Replacement:**
```python
        # If database has no heartbeat or is stale, attempt fallback read from local loopback worker probe if configured
        if st.get("worker_status") in ("NOT_STARTED", "UNKNOWN") or st.get("is_stale", True):
            local_worker_url = os.environ.get("LOCAL_WORKER_URL")
            if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get(f"{local_worker_url.rstrip('/')}/health/worker")
                        if resp.status_code == 200:
                            return resp.json()
                except Exception:
                    pass
```

---

### 2. `backend/app/main.py` lines 232–244 in `get_worker_status()`

**Existing (lines 232–244):**
```python
        # If database has no heartbeat or is stale, attempt fallback read from live Render worker probe
        if st.get("worker_status") in ("NOT_STARTED", "UNKNOWN") or st.get("is_stale", True):
            render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
            if render_worker_url:
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(f"{render_worker_url.rstrip('/')}/api/worker/status")
                        if resp.status_code == 200:
                            return resp.json()
                except Exception:
                    pass
```

**Replacement:**
```python
        # If database has no heartbeat or is stale, attempt fallback read from local loopback worker probe if configured
        if st.get("worker_status") in ("NOT_STARTED", "UNKNOWN") or st.get("is_stale", True):
            local_worker_url = os.environ.get("LOCAL_WORKER_URL")
            if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get(f"{local_worker_url.rstrip('/')}/api/worker/status")
                        if resp.status_code == 200:
                            return resp.json()
                except Exception:
                    pass
```

---

### 3. `backend/app/main.py` lines 263–275 in `get_session_report()`

**Existing (lines 263–275):**
```python
    # Fallback read from live Render worker probe if database returned nothing
    render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
    if render_worker_url:
        try:
            import httpx
            params = {"session_date": session_date} if session_date else {}
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{render_worker_url.rstrip('/')}/api/session/report", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

**Replacement:**
```python
    # Fallback read from local loopback worker probe if database returned nothing
    local_worker_url = os.environ.get("LOCAL_WORKER_URL")
    if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
        try:
            import httpx
            params = {"session_date": session_date} if session_date else {}
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{local_worker_url.rstrip('/')}/api/session/report", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

---

### 4. `backend/app/main.py` lines 333–344 in `get_session_checkpoints()`

**Existing (lines 333–344):**
```python
    render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
    if render_worker_url:
        try:
            import httpx
            params = {"session_date": session_date} if session_date else {}
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{render_worker_url.rstrip('/')}/api/session/checkpoints", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

**Replacement:**
```python
    local_worker_url = os.environ.get("LOCAL_WORKER_URL")
    if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
        try:
            import httpx
            params = {"session_date": session_date} if session_date else {}
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{local_worker_url.rstrip('/')}/api/session/checkpoints", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

---

### 5. `backend/app/main.py` lines 382–399 in `get_audit_events()`

**Existing (lines 382–399):**
```python
    render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
    if render_worker_url:
        try:
            import httpx
            params = {"limit": limit, "offset": offset}
            if session_date:
                params["session_date"] = session_date
            if event_type:
                params["event_type"] = event_type
            if symbol:
                params["symbol"] = symbol
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{render_worker_url.rstrip('/')}/api/audit/events", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

**Replacement:**
```python
    local_worker_url = os.environ.get("LOCAL_WORKER_URL")
    if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
        try:
            import httpx
            params = {"limit": limit, "offset": offset}
            if session_date:
                params["session_date"] = session_date
            if event_type:
                params["event_type"] = event_type
            if symbol:
                params["symbol"] = symbol
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{local_worker_url.rstrip('/')}/api/audit/events", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

---

### 6. `backend/app/main.py` lines 406–415 in `get_session_status()`

**Existing (lines 406–415):**
```python
    render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
    if render_worker_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{render_worker_url.rstrip('/')}/api/session/status")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

**Replacement:**
```python
    local_worker_url = os.environ.get("LOCAL_WORKER_URL")
    if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{local_worker_url.rstrip('/')}/api/session/status")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
```

---

### 7. `backend/app/main.py` lines 2512–2528 in `paper_trade_from_signal()`

**Existing (lines 2512–2528):**
```python
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
```

**Replacement:**
```python
    # 3. Expiration Timestamp Validation
    if signal.expiry:
        try:
            from datetime import datetime, timezone
            expiry_raw = str(signal.expiry).strip()
            if expiry_raw.endswith("Z"):
                expiry_raw = expiry_raw[:-1] + "+00:00"
            expiry_dt = datetime.fromisoformat(expiry_raw)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            else:
                expiry_dt = expiry_dt.astimezone(timezone.utc)

            if datetime.now(timezone.utc) > expiry_dt:
                signal.state = "EXPIRED"
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired signal timestamp"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Invalid signal expiry timestamp '{signal.expiry}': {e}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired signal timestamp"
            )
```

---

## Verification Plan

1. **Static Pattern Audit:**
   - Run grep across `backend/app/main.py` for `onrender.com` -> must yield 0 results.
   - Run grep across `backend/app/main.py` for `RENDER_WORKER_URL` -> must yield 0 results.

2. **Automated Unit & Adversarial Tests:**
   - Run `pytest backend/tests/test_security_hardening.py`
     - Confirms `test_signal_trade_expired_state_fails_closed` and `test_signal_trade_expired_timestamp_fails_closed` pass.
   - Run `pytest backend/tests/test_adversarial_m1_challenger.py`
     - Confirms signal trade edge cases on `/api/signals/{id}/paper-trade` pass.
   - Run `pytest backend/tests/live_paper/test_cloud_autonomy.py`
     - Confirms `/api/session/report`, `/api/session/checkpoints`, and `/api/session/status` pass without external network calls.
