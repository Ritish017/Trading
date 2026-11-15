# Milestone 1 (R1) Backend Security & Lifespan Hardening Review Report

**Reviewer**: `teamwork_preview_reviewer` (Backend Security Reviewer & Adversarial Critic)  
**Parent Agent**: `b0e006c7-614f-4aa0-b311-d567b4a1a31b`  
**Milestone**: Milestone 1 (R1) Baseline Integrity and First-Wave Defect Repairs  
**Date**: 2026-10-06  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Review Summary

The Milestone 1 implementation by `worker_m1` demonstrates substantial engineering progress across frontend compilation repairs, authentication header propagation, client position retention on close failure, worker startup task garbage-collection protection, and account-isolated `/api/paper/positions` endpoints.

However, independent test suite execution and adversarial analysis revealed a **test regression / lifespan lifecycle coupling failure** where `test_app_lifespan_normal_shutdown` fails with an `AssertionError` (0 of 1 expected calls awaited), along with an **adversarial fail-open vulnerability** in signal expiration validation when naive or malformed timestamps are supplied to `/api/signals/{id}/paper-trade`.

Because the test suite does not pass cleanly (37 passed, 1 failed), the milestone acceptance criteria are not met, and changes are requested before milestone sign-off.

---

## 2. Findings

### [Critical] Finding 1: Test Failure in `test_app_lifespan_normal_shutdown`

- **What**: `backend/tests/test_lifespans_hardening.py::test_app_lifespan_normal_shutdown` fails with:
  `AssertionError: Expected mock to have been awaited once. Awaited 0 times.`
- **Where**: `backend/tests/test_lifespans_hardening.py:39-46` (and `backend/app/main.py:114-154`)
- **Why**:
  In `test_app_lifespan_normal_shutdown`, `patch.object(market_data_service.active_provider, "disconnect", mock_disconnect)` binds the mock to the initial `market_data_service.active_provider` object reference.
  When `app_lifespan` enters, `await ensure_initialized()` calls `await market_data_service.initialize()`. If `market_data_service.active_provider` is reassigned or reinitialized during startup, the subsequent `finally:` block in `app_lifespan` invokes `await market_data_service.active_provider.disconnect()` on the *new* object reference, leaving the original patched mock uncalled.
  Furthermore, `MarketDataService` in `backend/app/market_data/service.py` lacks a top-level `disconnect()` method to encapsulate provider lifecycle management.
- **Suggestion**:
  1. Implement a top-level `async def disconnect(self)` method in `MarketDataService` (`backend/app/market_data/service.py`):
     ```python
     async def disconnect(self) -> None:
         """Disconnect active broker/mock provider and clean up stream resources."""
         if hasattr(self.active_provider, "disconnect"):
             await self.active_provider.disconnect()
     ```
  2. In `backend/tests/test_lifespans_hardening.py`, patch `market_data_service.disconnect` directly, or mock/reset `_initialized` state and provider references deterministically across tests so that `test_app_lifespan_normal_shutdown` reliably verifies shutdown cleanup.

---

### [Major] Finding 2: Fail-Open Vulnerability on Malformed or Naive Signal Expiry Timestamps

- **What**: In `/api/signals/{signal_id}/paper-trade`, expiration validation fails open when encountering naive ISO timestamps or unparseable expiry strings.
- **Where**: `backend/app/main.py:2513-2528`
- **Why**:
  ```python
  if signal.expiry:
      try:
          from datetime import datetime, timezone
          expiry_str = signal.expiry.replace("Z", "+00:00")
          expiry_dt = datetime.fromisoformat(expiry_str)
          if datetime.now(timezone.utc) > expiry_dt:
              signal.state = "EXPIRED"
              raise HTTPException(status_code=400, detail=...)
      except HTTPException:
          raise
      except Exception as e:
          logger.warning(f"Error checking signal expiry timestamp '{signal.expiry}': {e}")
  ```
  1. If `signal.expiry` is an ISO string without timezone (e.g., `"2020-01-01T09:15:00"`), `expiry_dt` is offset-naive. The comparison `datetime.now(timezone.utc) > expiry_dt` raises `TypeError: can't compare offset-naive and offset-aware datetimes`.
  2. The generic `except Exception as e:` catches this `TypeError` (and any `ValueError` on malformed formats), logs a warning, and proceeds to execute the trade order!
  3. This allows expired or malformed setups to execute rather than failing closed, violating the core security requirement (R2/R3/R5).
- **Suggestion**:
  1. Normalize timezone awareness:
     ```python
     if expiry_dt.tzinfo is None:
         expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
     ```
  2. Fail closed on parsing errors:
     ```python
     except HTTPException:
         raise
     except Exception as e:
         raise HTTPException(
             status_code=400,
             detail=f"Invalid or unparseable signal expiry timestamp '{signal.expiry}': {e}"
         )
     ```

---

### [Minor] Finding 3: Target Bounds Omitted in Endpoint Directional Geometry Validation

- **What**: `/api/signals/{signal_id}/paper-trade` verifies `stop_price < entry` for LONG and `stop_price > entry` for SHORT, but omits target directional checks (`targets[0].price > entry` for LONG, `targets[0].price < entry` for SHORT).
- **Where**: `backend/app/main.py:2542-2551`
- **Why**: While upstream signal engine gates validate target levels, the endpoint allows an order with inverted targets to be submitted if an injected or modified signal reaches the endpoint.
- **Suggestion**: Check `targetPrice` geometry before constructing `PaperOrderRequest`:
  - For LONG: verify `stop_price < signal.entry < target_price`
  - For SHORT: verify `target_price < signal.entry < stop_price`

---

### [Minor] Finding 4: Docstring Count Inconsistency in Test Suite

- **What**: The header docstring in `backend/tests/test_lifespans_hardening.py` lists 12 numbered verification items, but the file contains 11 tests.
- **Where**: `backend/tests/test_lifespans_hardening.py:4-17`
- **Why**: Documentation inaccuracy; item 12 in the list is present as test 11.
- **Suggestion**: Align docstring numbering with the actual test functions.

---

## 3. Verified Claims

| Claim | Verification Method | Status | Notes |
|-------|---------------------|--------|-------|
| `canonicalQuoteStore.ts` compiles cleanly with no TS2304 errors | Inspected code; verified `incomingTs` declaration and monotonicity check | **PASS** | Validated lines 114-124 in `canonicalQuoteStore.ts` |
| `frontend/src/App.tsx` retains position on close error | Inspected lines 695-725 in `App.tsx` | **PASS** | State filter executes strictly when `res.ok && (data.status === 'CLOSED' ...)` |
| `frontend/src` free of hardcoded `apex_default_dev_key` | AST inspection and file search | **PASS** | `getAuthHeaders()` utilized in `SignalCenterPage.tsx` |
| `IndexTickerBar.tsx` external probe eliminated | Inspected `IndexTickerBar.tsx` | **PASS** | Removed lines probing `onrender.com` |
| Worker host binds to `127.0.0.1` by default | `test_worker_host_defaults_to_loopback` in `test_lifespans_hardening.py` | **PASS** | Defaults to `127.0.0.1` when `HOST` env unset |
| Worker stop cancels and awaits startup and runner tasks | `test_worker_stop_cancels_in_flight_startup`, `test_worker_stop_awaits_runner_task_cancellation` | **PASS** | Both tests pass in pytest suite |
| Worker stop is idempotent | `test_worker_stop_is_idempotent` | **PASS** | Pass |
| `/api/paper/positions` requires authentication (401) | `test_unauthenticated_paper_positions_rejected` | **PASS** | Pass |
| `/api/paper/positions` enforces cross-account isolation (403) | `test_cross_account_positions_query_rejected` | **PASS** | Pass |
| `/api/signals/{id}/paper-trade` requires authentication (401) | `test_unauthenticated_signal_paper_trade_rejected` | **PASS** | Pass |
| `/api/signals/{id}/paper-trade` blocks cross-account trades (403) | `test_signal_paper_trade_cross_account_rejected` | **PASS** | Pass |
| `/api/signals/{id}/paper-trade` rejects unqualified signals (400) | `test_signal_paper_trade_unqualified_rejected` | **PASS** | Pass |
| `/api/signals/{id}/paper-trade` rejects expired signals (400) | `test_signal_paper_trade_expired_rejected` | **PASS** | Pass |
| `/api/signals/{id}/paper-trade` fills valid qualified signals (200) | `test_authenticated_signal_paper_trade_succeeds` | **PASS** | Pass |
| `app_lifespan` clean shutdown disconnects provider | `test_app_lifespan_normal_shutdown` | **FAIL** | Failed with `AssertionError` |

---

## 4. Adversarial Attack Surface & Stress Test Results

### Attack 1: Naive ISO Timestamp Expiration Bypass on `/api/signals/{id}/paper-trade`
- **Assumption Challenged**: All signal timestamps are valid timezone-aware strings ending in `"Z"`.
- **Attack Scenario**: Attacker or external feed produces an expired signal with naive timestamp `"2025-01-01T10:00:00"`.
- **Observed Behavior**: `datetime.now(timezone.utc) > expiry_dt` raises `TypeError`, caught by generic `except Exception: logger.warning(...)`, bypassing rejection and allowing execution of an expired trade.
- **Result**: **FAIL** (Vulnerability confirmed, see Finding 2).

### Attack 2: Startup State Transition During `app_lifespan` Provider Disconnect
- **Assumption Challenged**: `market_data_service.active_provider` remains constant from pre-lifespan through post-lifespan teardown.
- **Attack Scenario**: Subsystem startup initializes market data, potentially modifying `self.active_provider`.
- **Observed Behavior**: The provider reference transitions during `initialize()`, causing mocks/handlers attached to the initial provider to be detached during teardown.
- **Result**: **FAIL** (Confirmed via test failure, see Finding 1).

### Attack 3: Unauthorized Cross-Account Position Inspection
- **Assumption Challenged**: Caller with valid token for Account A can inspect Account B's portfolio by appending `?account_id=AccountB`.
- **Attack Scenario**: `GET /api/paper/positions?account_id=account_b` with `X-API-Key: token_a`.
- **Observed Behavior**: Server invokes `authorize_account_access(auth, target_account)`, detects `auth.account_id != clean_target`, logs security alert, and returns HTTP 403 Forbidden.
- **Result**: **PASS** (Protected).

### Attack 4: IDOR Position Liquidation
- **Assumption Challenged**: Caller with valid token for Account A can close a position owned by Account B via `POST /api/paper/close/{pos_id}`.
- **Attack Scenario**: Position `pos_123` belongs to Account B; caller provides valid Token A and requests closure.
- **Observed Behavior**: Server checks ownership: `pos_owner != target_account` raises HTTP 403 Forbidden ("IDOR violation: Account 'account_a' does not own position 'pos_123'").
- **Result**: **PASS** (Protected).

---

## 5. Unverified Items

None. All 38 tests across the test suites were executed directly. All ASTs and endpoint code paths were inspected.

---

## 6. Recommendations & Next Steps

1. Implement `MarketDataService.disconnect()` in `backend/app/market_data/service.py` and fix the test harness in `backend/tests/test_lifespans_hardening.py` so that all 38 tests pass with 0 failures.
2. Update `/api/signals/{id}/paper-trade` in `backend/app/main.py` to handle naive datetime comparisons safely and fail closed on invalid expiry timestamps with HTTP 400.
3. Once changes are applied, re-run:
   `python -m pytest backend/tests/test_lifespans_hardening.py backend/tests/test_security_hardening.py backend/tests/acceptance/test_security_acceptance.py -v`
   to achieve 38 passed / 0 failed before approving Milestone 1.
