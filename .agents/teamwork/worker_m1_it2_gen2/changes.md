# Milestone 1 Baseline Hardening — Changes Log

**Agent**: `teamwork_preview_worker` (`worker_m1_it2_gen2`)  
**Parent Agent**: `89f607f3-2421-4e10-b882-c14724281ad4` (`parent`)  
**Milestone**: Milestone 1 Iteration 2 (R1 Baseline Integrity Repairs)  
**Date**: 2026-10-06 / 2026-10-07  

---

## 1. Summary of Modified Files

| File | Change Description |
|---|---|
| `backend/app/market_data/service.py` | Implemented async `disconnect()` method delegating cleanly to `self.active_provider.disconnect()` and resetting service status. |
| `backend/tests/test_lifespans_hardening.py` | Patched `market_data_service.disconnect` directly across 3 lifespan tests; added `test_market_data_service_disconnect_delegates_to_active_provider`. |
| `backend/app/main.py` | Removed all 6 occurrences of `RENDER_WORKER_URL` / `https://apex-market-worker-probe.onrender.com` in favor of `LOCAL_WORKER_URL` loopback checks; hardened `/api/signals/{id}/paper-trade` expiry validation with timezone awareness and fail-closed 400 rejection. |
| `backend/app/signal_engine/options_engine.py` | Added `OptionsDecisionEngine` backward-compatibility adapter class handling parameter normalization (`chain` -> `option_chain`, `OptionContract` -> dict, default `days_to_expiry`). |
| `backend/app/signal_engine/futures_engine.py` | Added `FuturesDecisionEngine` backward-compatibility adapter class mapping `.evaluate()` to `.analyze()`, mapping spot boundaries, and formatting volume rejection reasons. |
| `backend/app/signal_engine/__init__.py` | Exported `FuturesDecisionEngine` and `OptionsDecisionEngine` in `__all__` and top-level imports. |
| `backend/tests/e2e/test_tier4_scenarios.py` | Added `ValidationGateResult` to module imports from `backend.app.signal_engine.models`. |

---

## 2. Detailed File Diffs and Explanations

### 2.1 `backend/app/market_data/service.py`
- **Rationale**: `app_lifespan` in `backend/app/main.py` checks `if hasattr(market_data_service, "disconnect"):`. `MarketDataService` previously lacked this method, falling back to `market_data_service.active_provider.disconnect`. When `market_data_service.initialize()` reassigns `self.active_provider` from `DevMockProvider` to `UpstoxProvider`, tests patching `market_data_service.active_provider.disconnect` prior to startup failed because the mock was bypassed.
- **Code Added**:
  ```python
  async def disconnect(self) -> None:
      """Disconnect the active broker provider and shut down background feeds cleanly."""
      logger.info(f"[MARKET DATA HUB] Disconnecting Market Data Service (Active: {getattr(self.active_provider, 'provider_name', 'UNKNOWN')})...")
      if self.active_provider and hasattr(self.active_provider, "disconnect"):
          try:
              await self.active_provider.disconnect()
              logger.info(f"[MARKET DATA HUB] Active provider ({self.active_provider.provider_name}) disconnected cleanly.")
          except Exception as e:
              logger.warning(f"[MARKET DATA HUB] Error disconnecting active provider: {e}")
      self.status_code = "DISCONNECTED"
      self.is_live = False
  ```

### 2.2 `backend/tests/test_lifespans_hardening.py`
- **Rationale**: Tests must patch the stable `market_data_service.disconnect` method directly to avoid instance replacement pitfalls during startup. In addition, an explicit delegation test ensures `market_data_service.disconnect()` invokes `active_provider.disconnect()`.
- **Code Changed**:
  - `test_app_lifespan_normal_shutdown`: Changed `patch.object(market_data_service.active_provider, ...)` to `patch.object(market_data_service, "disconnect", mock_disconnect)`.
  - `test_app_lifespan_exception_guarantees_cleanup`: Same patch update.
  - `test_app_lifespan_cancellation_guarantees_cleanup`: Same patch update.
  - Added:
    ```python
    @pytest.mark.asyncio
    async def test_market_data_service_disconnect_delegates_to_active_provider():
        """Verify MarketDataService.disconnect() calls active_provider.disconnect()."""
        mock_provider_disconnect = AsyncMock()
        with patch.object(market_data_service.active_provider, "disconnect", mock_provider_disconnect):
            await market_data_service.disconnect()
            mock_provider_disconnect.assert_awaited_once()
    ```

### 2.3 `backend/app/main.py`
- **Rationale**:
  1. External calls to `https://apex-market-worker-probe.onrender.com` violate Requirement R5 (local loopback operation and zero external broker/cloud telemetry calls during local trading).
  2. Signal expiry check in `/api/signals/{signal_id}/paper-trade` compared naive datetimes against timezone-aware UTC datetimes, throwing `TypeError` that was caught and swallowed, causing expired signals to execute (fail open).
- **Code Changed**:
  - Replaced all 6 occurrences of `RENDER_WORKER_URL` / `https://apex-market-worker-probe.onrender.com` (endpoints `/health/worker`, `/api/worker/status`, `/api/session/report`, `/api/session/checkpoints`, `/api/audit/events`, `/api/session/status`) with:
    ```python
    local_worker_url = os.environ.get("LOCAL_WORKER_URL")
    if local_worker_url and any(h in local_worker_url for h in ("127.0.0.1", "localhost")):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{local_worker_url.rstrip('/')}/...")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    ```
  - Hardened signal expiry parsing in `/api/signals/{signal_id}/paper-trade`:
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

### 2.4 `backend/app/signal_engine/options_engine.py` & `futures_engine.py`
- **Rationale**: E2E test suites (`test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_combinations.py`) import `OptionsDecisionEngine` and `FuturesDecisionEngine`, passing keyword arguments like `chain`, `capital`, `stop_loss_spot`, and `target_spot`.
- **Code Added**:
  - `OptionsDecisionEngine(OptionsEngine)`: Normalizes `chain` to `option_chain`, converts `OptionContract` objects to dictionaries required by `calculate_black_scholes_greeks()`, defaults `days_to_expiry=14`, and delegates to `super().evaluate()`.
  - `FuturesDecisionEngine(FuturesEngine)`: Translates `.evaluate()` keyword parameters to `.analyze()`, derives default stops/targets if omitted, and appends `"Insufficient volume"` to `rejection_reason` for liquidity failures.

### 2.5 `backend/app/signal_engine/__init__.py`
- **Rationale**: Ensures top-level package exports `OptionsDecisionEngine` and `FuturesDecisionEngine` for clean modular discovery.
- **Code Changed**:
  - Added `"FuturesDecisionEngine"` and `"OptionsDecisionEngine"` to `__all__`.
  - Added `FuturesDecisionEngine` and `OptionsDecisionEngine` to the imports from `futures_engine` and `options_engine`.

### 2.6 `backend/tests/e2e/test_tier4_scenarios.py`
- **Rationale**: Lines 209 and 220 reference `ValidationGateResult.FAIL` and `ValidationGateResult.PASS` without importing `ValidationGateResult`, causing a runtime `NameError`.
- **Code Changed**:
  - Added `ValidationGateResult` to the import list from `backend.app.signal_engine.models`.
