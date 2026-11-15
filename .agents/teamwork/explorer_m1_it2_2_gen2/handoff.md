# Handoff Report: Security Probe Removal and Signal Expiry Hardening

**Date:** 2026-10-06  
**From:** Security & Probe Removal Explorer (`explorer_m1_it2_2_gen2`)  
**To:** Implementer / Orchestrator Parent Agent  
**Milestone:** Milestone 1 Iteration 2  
**Handoff Type:** Hard (Task complete)  

---

## 1. Observation

### Observation 1.1: 6 Fallback Occurrences of External Render Probe in `backend/app/main.py`
Running pattern search for `onrender.com` in `C:\Tradinf2\backend\` returned verbatim matches at lines:
- `backend/app/main.py:195`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
- `backend/app/main.py:234`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
- `backend/app/main.py:264`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
- `backend/app/main.py:333`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
- `backend/app/main.py:382`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
- `backend/app/main.py:406`:
  ```python
  render_worker_url = os.environ.get("RENDER_WORKER_URL", "https://apex-market-worker-probe.onrender.com")
  ```
All 6 occurrences invoke `httpx.AsyncClient` with external network targets if `st.get("worker_status")` is not started or stale, violating local loopback isolation (Task 4 & Requirement R5).

### Observation 1.2: Expiry Parsing Fail-Open in `backend/app/main.py`
Inspecting lines 2512–2528 in `backend/app/main.py`:
```python
2512:     # 3. Expiration Timestamp Validation
2513:     if signal.expiry:
2514:         try:
2515:             from datetime import datetime, timezone
2516:             expiry_str = signal.expiry.replace("Z", "+00:00")
2517:             expiry_dt = datetime.fromisoformat(expiry_str)
2518:             if datetime.now(timezone.utc) > expiry_dt:
2519:                 signal.state = "EXPIRED"
2520:                 raise HTTPException(
2521:                     status_code=400,
2522:                     detail=f"Signal {signal_id} expired at {signal.expiry}. Cannot execute expired setup."
2523:                 )
2524:         except HTTPException:
2525:             raise
2526:         except Exception as e:
2527:             logger.warning(f"Error checking signal expiry timestamp '{signal.expiry}': {e}")
```
- Line 2516–2517: If `signal.expiry` is an offset-naive datetime string (e.g. `"2026-10-06T18:00:00"`), `datetime.fromisoformat` returns naive datetime (`tzinfo=None`).
- Line 2518: `datetime.now(timezone.utc) > expiry_dt` raises `TypeError: can't compare offset-naive and offset-aware datetimes`.
- Line 2526–2527: Caught by `except Exception as e: logger.warning(...)`, execution continues and the order is placed (fails open).
- In addition, malformed strings (raising `ValueError`) are also swallowed without failing closed.

---

## 2. Logic Chain

1. **Step 1 (Loopback Invariant):** Requirement R5 in `PROJECT.md` specifies *"Bind services to local loopback, keep API keys and provider tokens server-side"*. External probe URLs to `https://apex-market-worker-probe.onrender.com` violate this invariant by opening outbound HTTP calls to third-party infrastructure.
2. **Step 2 (Local State Sufficiency):** Observations 1.1 show that every endpoint querying `render_worker_url` (`/health/worker`, `/api/worker/status`, `/api/session/report`, `/api/session/checkpoints`, `/api/audit/events`, `/api/session/status`) already contains comprehensive local database queries (`WorkerRepository`, `AuditRepository`, `check_db_health()`, and `SessionLifecycleManager`).
3. **Step 3 (Loopback Fallback):** Replacing `RENDER_WORKER_URL` with optional `LOCAL_WORKER_URL` (with an explicit check ensuring the host contains `127.0.0.1` or `localhost`) allows local inter-process communication if the worker is run as a separate HTTP daemon, while defaulting to immediate local state evaluation when unset.
4. **Step 4 (Timezone-Aware Expiry Enforcement):** In Observation 1.2, coercing `expiry_dt` to UTC timezone awareness (`replace(tzinfo=timezone.utc)` if naive, `astimezone(timezone.utc)` if aware) completely eliminates `TypeError`.
5. **Step 5 (Fail-Closed Gate):** Replacing the permissive `except Exception as e: logger.warning(...)` with an explicit `raise HTTPException(status_code=400, detail="Invalid or expired signal timestamp")` ensures any parsing defect or expired setup is immediately rejected, preserving financial safety and fulfilling R3/R5 requirements.

---

## 3. Caveats

- In test fixtures where mock signals are instantiated without an `expiry` property (e.g. `test_authenticated_signal_paper_trade_succeeds`), preserving `if signal.expiry:` ensures existing tests continue to pass without regression.
- `LOCAL_WORKER_URL` is intentionally optional and defaults to `None`. This ensures zero network latency overhead during unit testing and standalone backend execution.
- Alternative considered: Hardcoding `http://127.0.0.1:8001` as a default. Rejected because if the worker is not running on port 8001, each health check would incur socket connection attempts. Local database state checks are superior and already implemented.

---

## 4. Conclusion

The required changes in `backend/app/main.py` are scoped and precise:
1. **Probe Removal:** Replace lines 195–204, 234–243, 264–274, 333–343, 382–398, and 406–415 with `LOCAL_WORKER_URL` loopback checks.
2. **Expiry Hardening:** Replace lines 2513–2528 with robust timezone-aware parsing and fail-closed exception handling.

### Exact Patch / Drop-In Blocks

#### A. Probe Replacement Block (lines 193–205 and lines 232–244)
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
*(Apply corresponding `/api/worker/status`, `/api/session/report`, `/api/session/checkpoints`, `/api/audit/events`, and `/api/session/status` paths for lines 234, 264, 333, 382, 406 as documented in `report.md`).*

#### B. Expiry Validation Block (lines 2512–2528)
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

## 5. Verification Method

### 1. Zero External Domain Audit
Execute:
```powershell
python -c "content = open('backend/app/main.py', encoding='utf-8').read(); assert 'onrender.com' not in content; assert 'RENDER_WORKER_URL' not in content; print('PASS: No external probes found in backend/app/main.py')"
```
Expected Result: PASS (0 occurrences).

### 2. Signal Expiry Edge Case Tests
Execute:
```powershell
pytest backend/tests/test_security_hardening.py -k "test_signal_trade_expired"
pytest backend/tests/test_adversarial_m1_challenger.py -k "test_signal_trade_expired"
```
Expected Result: 100% PASS with HTTP 400 status and fail-closed rejection.

### 3. Invalidation Conditions
- Any occurrence of `onrender.com` remaining in `backend/app/main.py`.
- Any unhandled `TypeError` when evaluating naive timestamps on `/api/signals/{id}/paper-trade`.
- Any non-400 response when submitting expired or corrupt timestamp signals.
