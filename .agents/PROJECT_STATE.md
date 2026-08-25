# APEX Quant Lab — Project State

- **Current Phase**: Phase 4 — Strategy & Intelligence Engine / Agent Bridge Integration
- **Repository Root**: `C:\Tradinf2`
- **Git HEAD Commit**: `b7c2cc0b0c1b5827944b266c961728344c4264ff`
- **Branch**: `main`
- **Last Verification**: 180 pytest tests passing (100%), Frontend Vite build passing (1707 modules transformed)
- **Deployment Target**: Vercel (Frontend & Serverless endpoints) + Local Backend FastAPI Engine

## Active Architecture Overview
- **Backend Core**: FastAPI, SQLite (`apex_quant.db`), Python 3.14
- **Market Data Engine**: `backend/app/market_data/` with `canonical_store.py`, `service.py`, Upstox REST/WebSocket providers, DevMock provider
- **Quant & Strategy Engine**: `backend/app/strategy_engine/` (research engine, strategy lab, robustness tests, forward validation)
- **Intelligence Engine**: `backend/app/intelligence_engine/` (evidence provenance, market regime classification, decision factory)
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS / Lucide / Recharts, `src/components/IndianCandleChart.tsx`
- **Agent Bridge**: `C:\APEX-Agent-Bridge` (MCP server for ChatGPT ↔ Antigravity execution)

## Active Work & Focus
- Establishing the ChatGPT ↔ Antigravity development bridge with strict isolation and secret redaction.
- Ensuring zero mock-data leakage in production price displays.
- Maintaining complete evidence provenance across all research decisions.

## Known Blockers & Bugs
- None blocking. All 180 backend tests are green.

<!-- Bridge Verification Note: Verified on 2026-08-21 by APEX Agent Bridge dry-run -->
