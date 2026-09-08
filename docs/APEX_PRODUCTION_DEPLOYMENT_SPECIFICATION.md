# APEX Quant Lab — Production Deployment Specification
## Multi-Tier Architecture: Vercel, Render & PostgreSQL

**Revision**: 2026.1.0-PRODUCTION-CERTIFIED  
**Target Environment**: Indian Equities & Derivatives (NSE / NIFTY 50 / BANKNIFTY)  
**Operating Mode**: Real Market Data Feed (Upstox WebSocket) + Hard-Enforced Paper Trading  
**Status**: `LIVE & SYNCHRONIZED`

---

## 1. Executive Summary & Topology

The APEX Quant Lab deployment is architected across two cloud platforms to circumvent the serverless runtime limitations of Vercel while preserving its high-performance edge frontend and REST API delivery:

1. **Vercel** (`https://apex-trading-lab.vercel.app`):
   - Hosts the React + TypeScript frontend dashboard and serverless ASGI REST API routes.
   - Serves high-speed UI assets, charts, and public endpoints.
   - Reads background worker state from PostgreSQL with transparent proxy fallback to the Render probe.
2. **Render Background Worker** (`https://apex-market-worker-probe.onrender.com`):
   - Executes a dedicated, long-running Python process outside Vercel.
   - Maintains a continuous WebSocket connection to the Upstox Market Data Feed.
   - Decodes binary Protobuf ticks, aggregates 15m candles, runs the Signal Intelligence Engine, executes paper orders, logs master JSONL evidence, and publishes 15-second telemetry heartbeats.
3. **Render Managed PostgreSQL** (`apex-postgres`):
   - Hosted in Singapore (`singapore` region) for low-latency routing to Indian exchange feeds.
   - Provides durable state persistence for open positions, filled orders, trade history, and worker heartbeats.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT BROWSER                                      │
│                (Desktop / Mobile Dashboard at apex-trading-lab.vercel.app)             │
└───────────────────┬─────────────────────────────────────────────────┬──────────────────┘
                    │ HTTPS (Static UI / REST API)                     │ Direct Fallback Poller (10s)
                    ▼                                                 ▼
┌───────────────────────────────────────┐            ┌───────────────────────────────────┐
│           VERCEL DEPLOYMENT           │            │       RENDER WORKER PROBE         │
│   apex-trading-lab.vercel.app         │            │ apex-market-worker-probe.onrender │
│                                       │            │                                   │
│  - React 18 + Vite Production Bundle  │            │  - Embedded FastAPI Probe Server  │
│  - ASGI Serverless Handlers (api/*.py)│            │  - /health (Container Probe)      │
│  - GET /api/worker/status             │            │  - /api/worker/status (Telemetry) │
│  - GET /health/worker                 │            │  - /api/worker/preflight (Matrix) │
│  - Upstream Proxy Fallback to Render  │            │                                   │
└───────────────────┬───────────────────┘            └─────────────────┬─────────────────┘
                    │ Reads State                                      │ Writes Heartbeats (15s)
                    │                                                  │ Restores Portfolio on Reboot
                    ▼                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        RENDER MANAGED POSTGRESQL (apex-postgres)                       │
│                       postgresql://apex_user:***@...singapore-postgres                 │
│                                                                                        │
│  - worker_heartbeats (Worker status, error counts, telemetry metrics)                  │
│  - paper_positions (Authoritative open paper positions)                               │
│  - paper_orders (Validated and filled paper order records)                            │
│  - paper_trades (Closed positions, realized PnL, statutory frictions)                  │
└───────────────────────────────────────────────────▲────────────────────────────────────┘
                                                    │
                                                    │ Syncs Trades & Positions
                                                    │
┌───────────────────────────────┐                   │
│   UPSTOX MARKET DATA FEED     │                   │
│                               │                   │
│ - Authorized WebSocket V2/V3  │                   │
│ - Binary Protobuf Decoding    │                   │
│ - 20 NSE Liquid Universe Syms │                   │
└───────────────┬───────────────┘                   │
                │ Real Ticks                        │
                ▼                                   │
┌───────────────────────────────────────────────────┴────────────────────────────────────┐
│                      RENDER STATEFUL DAEMON (backend.app.worker)                       │
│                                                                                        │
│  1. Startup Preflight Check (18 Checks: Auth, WS, Proto, Universe, Hash, DB)           │
│  2. Fail-Closed Invariants: LIVE_TRADING=False, PAPER_TRADING=True                     │
│  3. Canonical Market Store & 15m Candle Aggregation                                    │
│  4. Signal Intelligence Engine (20 Systematic Strategies, SHA-256: d3e94bea...94e)     │
│  5. 17-Stage Validation Gates + Confluence Engine                                      │
│  6. Candidate Observatory (100% Candidates & Rejection Reasons Logged)                 │
│  7. Paper Trading Engine (Slippage Model + NSE-STATUTORY-2026-V1 Cost Calculator)      │
│  8. Restart State Recovery (Preserves capital and open trades across reboots)           │
│  9. Append-Only Master JSONL Logger (logs/live_paper/YYYY-MM-DD/APEX_..._MASTER.jsonl) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure Identity & Endpoints

### 2.1 Vercel Edge & Frontend
* **Dashboard URL**: [`https://apex-trading-lab.vercel.app/`](https://apex-trading-lab.vercel.app/)
* **Project ID**: `prj_e6bWNRdHtAcp1118AcbX0BkCM2ZT`
* **Team ID**: `team_pAWm7lYVYnJAJVm0TNCthatR`
* **Project Name**: `apex-trading-lab`
* **Repository**: [`Ritish017/Trading`](https://github.com/Ritish017/Trading) (Branch: `main`)
* **Primary Function**: UI rendering, REST proxying, static asset delivery.
* **Serverless Configuration**: Configured via [`vercel.json`](file:///c:/Tradinf2/vercel.json) with dedicated [`api/requirements.txt`](file:///c:/Tradinf2/api/requirements.txt) to satisfy AWS Lambda/Vercel 250MB bundle ceiling.

### 2.2 Render Worker & API Probe
* **Dashboard URL**: [`https://dashboard.render.com/web/srv-dag6c9142hec739bb860`](https://dashboard.render.com/web/srv-dag6c9142hec739bb860)
* **Public Probe URL**: [`https://apex-market-worker-probe.onrender.com`](https://apex-market-worker-probe.onrender.com)
* **Service ID**: `srv-dag6c9142hec739bb860`
* **Service Name**: `apex-market-worker-probe`
* **Runtime**: Python 3.11.9
* **Region**: `singapore`
* **Start Command**: `python -m backend.app.worker`
* **Build Command**: `pip install -r requirements.txt`

### 2.3 Render Managed PostgreSQL
* **Dashboard URL**: [`https://dashboard.render.com/d/dpg-dag6bl0hchos73826v50-a`](https://dashboard.render.com/d/dpg-dag6bl0hchos73826v50-a)
* **Database ID**: `dpg-dag6bl0hchos73826v50-a`
* **Database Name**: `apex_quant`
* **Database User**: `apex_user`
* **Database Version**: PostgreSQL 16
* **Region**: `singapore`
* **Access Control**: IP Allowlist includes `0.0.0.0/0` (Enables external connections from Vercel Serverless Functions).
* **Connection String Format**: `postgresql://apex_user:[PASS]@dpg-dag6bl0hchos73826v50-a.singapore-postgres.render.com:5432/apex_quant`
* **SQLAlchemy Async Driver**: `postgresql+asyncpg://...` (Automatically normalized in [`backend/app/database/connection.py`](file:///c:/Tradinf2/backend/app/database/connection.py)).

---

## 3. Real-Time Telemetry & Health Endpoints

| Endpoint | Method | Source | Response | Description |
|---|---|---|---|---|
| `/health` | `GET` | Vercel / Render | `200 OK` | General container/application health probe. |
| `/health/worker` | `GET` | Vercel / Render | `200 OK` | Lightweight monitoring health check with connection status and event counts. |
| `/api/worker/status` | `GET` | Vercel / Render | `200 OK` | Full 13-field operational telemetry dictionary for the live dashboard. |
| `/api/worker/preflight` | `GET` | Render | `200 OK` | Complete 18-stage preflight checklist execution report. |

### Verified Live Telemetry Payload
```json
{
  "worker_id": "apex-market-worker",
  "experiment_id": "APEX-WORKER-2026-09-09",
  "worker_status": "ONLINE",
  "market_connection": "CONNECTED",
  "database_status": "ONLINE",
  "paper_mode": true,
  "live_trading": false,
  "live_orders_blocked": true,
  "safety_assertion": "REAL MARKET DATA | PAPER TRADING | LIVE ORDERS BLOCKED",
  "last_tick": null,
  "last_event": "SESSION_HEARTBEAT",
  "signal_count": 0,
  "candidate_count": 0,
  "paper_order_count": 0,
  "open_positions": 0,
  "closed_positions": 0,
  "realized_pnl": 0.0,
  "unrealized_pnl": 0.0,
  "total_costs": 0.0,
  "net_pnl": 0.0,
  "data_quality": "AUTHENTIC_LIVE",
  "reconnect_count": 0,
  "error_count": 0,
  "heartbeat_age_seconds": 10.1,
  "is_stale": false,
  "updated_at": "2026-09-08T20:35:06"
}
```

---

## 4. Operational Invariants & Safety Locks

The system enforces non-bypassable guards against accidental capital risk and configuration drift:

1. **Permanent Paper-Only Assertion**:
   - `LIVE_ORDER_ALLOWED = False` hard-coded as a frozen boolean constant in [`backend/app/live_paper/safety.py`](file:///c:/Tradinf2/backend/app/live_paper/safety.py).
   - Any execution path invoking broker order transmission raises `LiveOrderForbiddenSecurityError` and emits a `SECURITY_BLOCKED_EVENT` to the master evidence log.
2. **Fail-Closed Environment Gate**:
   - [`backend/app/config.py`](file:///c:/Tradinf2/backend/app/config.py) checks `validate_production_invariants()` on startup.
   - If `APEX_ENV=production` and `DATABASE_URL` is missing, SQLite, or `/tmp/apex_quant.db`, the worker **immediately halts**.
   - If `LIVE_TRADING=True`, the worker **immediately halts**.
3. **Cryptographic Strategy Freeze**:
   - Strategy weights, thresholds, scoring coefficients, and parameters are validated against SHA-256 hash:
     ```text
     d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e
     ```
   - Any unauthorized edit to strategy files or parameters causes preflight verification to fail.
4. **Authentic Data Only (Zero Synthetic Fallback)**:
   - Synthetic ticks, simulated sine-wave prices, and random candle generators are strictly forbidden during live sessions via `SyntheticDataForbiddenError`.
   - If broker feeds disconnect, the system enters backoff-reconnect and logs `DATA_UNAVAILABLE`.

---

## 5. Execution Pipeline & Market Hours

The background worker automatically aligns with the Indian market schedule:

* **Pre-Market Initialization** (08:45–09:14 IST):
  - Worker starts, performs 18-stage preflight validation, connects to PostgreSQL, restores portfolio state from database, obtains authorized Upstox WebSocket redirect URI, and connects.
* **NSE Regular Session** (09:15–15:30 IST):
  - Processes streaming ticks into the canonical store.
  - Aggregates completed 15-minute bars.
  - Runs all 20 systematic strategies.
  - Dispatches qualified candidates through 17 validation gates.
  - Emits paper orders for qualifying signals.
  - Simulates fills with realistic market slippage and statutory deductions (`NSE-STATUTORY-2026-V1`).
  - Computes mark-to-market valuations every 15 seconds.
  - Enforces stop-loss and profit-target exits.
* **Derivatives Expiry Finalization** (15:30–15:40 IST):
  - Closes intraday MIS positions.
  - Records trade outcomes and reconciles gross and net PnL.
* **Session Finalization** (Post 15:40 IST):
  - Emits `SESSION_SUMMARY` event.
  - Computes final SHA-256 checksum of `logs/live_paper/YYYY-MM-DD/APEX_YYYY-MM-DD_MASTER.jsonl`.
  - Transitions to standby mode.

---

## 6. Multi-Tier Synchronization Architecture

To guarantee that the Vercel dashboard never displays disconnected or outdated state, a three-tier synchronization strategy is implemented:

1. **Direct Database Persistence**:
   - The Render worker writes telemetry into `worker_heartbeats` every 15 seconds.
   - When Vercel Serverless Functions have `DATABASE_URL` configured, they query PostgreSQL directly.
2. **Dynamic Serverless Proxy Fallback**:
   - If `DATABASE_URL` is cold, unconfigured, or unreachable from Vercel, [`backend/app/main.py`](file:///c:/Tradinf2/backend/app/main.py) automatically issues a sub-second upstream query to the live Render probe (`https://apex-market-worker-probe.onrender.com/api/worker/status`).
3. **Browser Direct Probe Fallback**:
   - If the Vercel serverless function itself times out or encounters network latency, [`frontend/src/components/IndexTickerBar.tsx`](file:///c:/Tradinf2/frontend/src/components/IndexTickerBar.tsx) performs an automatic client-side CORS fetch directly against the Render probe.

---

## 7. Operational Runbook

### How to Monitor Worker Health
1. Open the Vercel dashboard: [`https://apex-trading-lab.vercel.app`](https://apex-trading-lab.vercel.app).
2. Look at the **Ticker Bar** at the top:
   - `🟢 WORKER ONLINE`: Worker is pulsing heartbeats every 15 seconds.
   - `⚪ WORKER STANDBY`: Worker is outside trading hours or starting up.
   - `🔴 WORKER STALE`: Heartbeat age exceeds 120 seconds (investigate logs).
3. Click the **🟢 WORKER ONLINE** badge to open the interactive **Stateful Worker Telemetry Modal**, which displays live tick counts, candle counts, open positions, realized/unrealized PnL, statutory transaction costs, and error counts.

### How to Restart or Redeploy Worker
1. Via Render API:
   ```bash
   curl -X POST "https://api.render.com/v1/services/srv-dag6c9142hec739bb860/deploys" \
     -H "Authorization: Bearer <RENDER_API_KEY>" \
     -H "Content-Type: application/json" \
     -d '{"clearCache": "do_not_clear"}'
   ```
2. Via Git:
   ```bash
   git commit --allow-empty -m "trigger(deploy): restart apex market worker"
   git push origin main
   ```
   Render automatically detects commits to `main` and deploys zero-downtime container updates.

---

## 8. File Manifest

| File Path | Description |
|---|---|
| [`backend/app/worker.py`](file:///c:/Tradinf2/backend/app/worker.py) | Stateful background worker daemon with embedded FastAPI telemetry probe. |
| [`backend/app/live_paper/session_runner.py`](file:///c:/Tradinf2/backend/app/live_paper/session_runner.py) | Live market session runner executing Upstox WS, strategy scan, and paper engine. |
| [`backend/app/live_paper/master_evidence_logger.py`](file:///c:/Tradinf2/backend/app/live_paper/master_evidence_logger.py) | Thread-safe append-only master JSONL evidence logger with crash recovery. |
| [`backend/app/live_paper/safety.py`](file:///c:/Tradinf2/backend/app/live_paper/safety.py) | Hard safety guards preventing live order execution and configuration modification. |
| [`backend/app/live_paper/preflight.py`](file:///c:/Tradinf2/backend/app/live_paper/preflight.py) | 18-stage pre-market verification matrix checking auth, feed, universe, and DB. |
| [`backend/app/database/models.py`](file:///c:/Tradinf2/backend/app/database/models.py) | SQLAlchemy ORM models including `WorkerHeartbeatModel` and composite indices. |
| [`backend/app/database/connection.py`](file:///c:/Tradinf2/backend/app/database/connection.py) | Dialect-agnostic migrations and PostgreSQL connection pool configuration. |
| [`backend/app/database/repositories/worker_repository.py`](file:///c:/Tradinf2/backend/app/database/repositories/worker_repository.py) | Atomic heartbeat upserts and staleness-aware telemetry retrieval. |
| [`render.yaml`](file:///c:/Tradinf2/render.yaml) | Render Infrastructure as Code blueprint for worker and PostgreSQL. |
| [`vercel.json`](file:///c:/Tradinf2/vercel.json) | Vercel build, output directory, and serverless bundle exclusion configuration. |
| [`api/requirements.txt`](file:///c:/Tradinf2/api/requirements.txt) | Lean requirements manifest specifically tailored for Vercel serverless size limit. |
| [`requirements.txt`](file:///c:/Tradinf2/requirements.txt) | Production requirements manifest for Render background worker. |
| [`frontend/src/components/IndexTickerBar.tsx`](file:///c:/Tradinf2/frontend/src/components/IndexTickerBar.tsx) | Live worker status polling, badging, and glassmorphic telemetry modal. |
