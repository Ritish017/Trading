# APEX Quant Lab — Deployment & Environment Setup

This document describes the multi-tier production architecture, live environments, and local setup procedures for the APEX Quant Lab.

> **Full Production Specification**: See [`docs/APEX_PRODUCTION_DEPLOYMENT_SPECIFICATION.md`](docs/APEX_PRODUCTION_DEPLOYMENT_SPECIFICATION.md) for detailed architecture, sequence diagrams, safety invariants, and operational runbooks.

---

## 1. Live Production Deployments

| Tier | Service | URL / Host | Operating Role |
|---|---|---|---|
| **Frontend & API** | Vercel (`apex-trading-lab`) | [`https://apex-trading-lab.vercel.app/`](https://apex-trading-lab.vercel.app/) | Serves React dashboard UI and serverless REST endpoints. |
| **Market Worker** | Render (`apex-market-worker-probe`) | [`https://apex-market-worker-probe.onrender.com`](https://apex-market-worker-probe.onrender.com) | Stateful daemon executing Upstox WS, strategy scan, paper execution, and health probe. |
| **Operational DB** | Render PostgreSQL (`apex-postgres`) | `dpg-dag6bl0hchos73826v50-a...singapore-postgres` | Shared PostgreSQL 16 database storing heartbeats, positions, orders, and trades. |

### Live Monitoring Endpoints
* **Worker Telemetry**: `https://apex-trading-lab.vercel.app/api/worker/status` (also via Render probe: `/api/worker/status`)
* **Container Health**: `https://apex-market-worker-probe.onrender.com/health`
* **Preflight Verification**: `https://apex-market-worker-probe.onrender.com/api/worker/preflight`

---

## 2. Local Environment Requirements
* Python 3.11 or greater
* Node.js 18 or greater (with npm)
* SQLite (development default) or PostgreSQL 14+ (production-aligned)

---

## 3. Local Installation & Launch

1. **Clone repository & prepare configuration**:
   ```bash
   cp .env.example .env
   ```

2. **Backend Setup**:
   ```bash
   pip install -r requirements.txt
   # Run main FastAPI application
   uvicorn backend.app.main:app --reload --port 8000
   ```

3. **Stateful Worker Launch (Local Simulation or Live Test)**:
   ```bash
   python -m backend.app.worker
   ```

4. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Production Bundle Build (Frontend)**:
   ```bash
   cd frontend
   npm run build
   ```

---

## 4. Operational Invariants
* **Paper-Only Enforced**: `LIVE_ORDER_ALLOWED = False`, `LIVE_TRADING = false`, `PAPER_TRADING = true`.
* **Zero Synthetic Fallback**: Real market sessions require authentic Upstox feeds; synthetic data is strictly prohibited during live experiments.
* **Frozen Configuration**: Quantitative rules and strategy weights locked to SHA-256 hash `d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e`.
