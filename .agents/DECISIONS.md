# APEX Quant Lab — Architectural & Quantitative Decision Log

## ADR-001: Centralized Canonical Market Store
- **Date**: 2026-08-20
- **Status**: Accepted & Implemented
- **Context**: Disparate components previously accessed prices through ad-hoc mocks or direct provider calls, leading to potential inconsistency and unverified pricing.
- **Decision**: All current prices, historical candles, and live quotes must resolve through `backend/app/market_data/canonical_store.py`. Every quote must contain timestamp, provider mode (`LIVE` vs `MOCK`), and freshness indicators.

## ADR-002: Backend Single-Source of Truth for Indicators
- **Date**: 2026-08-20
- **Status**: Accepted & Implemented
- **Context**: Frontend had auxiliary technical calculation utilities that diverged from Python pandas/numpy calculations.
- **Decision**: Frontend indicator calculations are deprecated for trading logic. Strategy evaluations and signal indicators must be calculated in Python backend.

## ADR-003: Isolated Development Bridge for ChatGPT/Antigravity Collaboration
- **Date**: 2026-08-21
- **Status**: Accepted
- **Context**: Iterating between ChatGPT architecture suggestions and local Antigravity code modifications required excessive manual copy-pasting and lacked sandboxed security controls.
- **Decision**: Implement `C:\APEX-Agent-Bridge` as an MCP service with workspace allowlists, secret redaction, and a structured task ledger.
