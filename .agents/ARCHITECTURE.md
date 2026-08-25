# APEX Quant Lab — System Architecture

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (React/Vite)                  │
│  - Presentation & Visualization (IndianCandleChart)         │
│  - PriceTracePanel, NSEWatchlist, Strategy Dashboard        │
│  - Zero Quantitative Calculations (Presentation Only)       │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                      │
│                                                             │
│  ┌────────────────────────┐    ┌─────────────────────────┐  │
│  │   Market Data Engine   │    │      Quant Engine       │  │
│  │ - Canonical Store      │    │ - Strategy Lab          │  │
│  │ - Upstox REST / WS     │    │ - Robustness Testing    │  │
│  │ - Dev Mock Provider    │    │ - Forward Validation    │  │
│  └───────────┬────────────┘    └────────────┬────────────┘  │
│              │                              │               │
│  ┌───────────▼────────────┐    ┌────────────▼────────────┐  │
│  │  Intelligence Engine   │    │      Paper Trading      │  │
│  │ - Regime Classifier    │    │ - Order Lifecycle       │  │
│  │ - Evidence Provenance  │    │ - Canonical Matching    │  │
│  │ - Research Decisions   │    │ - Portfolio Accounting  │  │
│  └────────────────────────┘    └─────────────────────────┘  │
│                                                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ SQLite / Parquet
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATABASE & PERSISTENCE                     │
│  - apex_quant.db (Transactions, Strategy Runs, State)       │
└─────────────────────────────────────────────────────────────┘
```

## Layer Descriptions
1. **Frontend Presentation**: Pure consumer of canonical API endpoints. Never alters or calculates financial metrics.
2. **Market Data Layer**: Ingests ticks/candles, unifies them through `canonical_store.py`, tracks data freshness, timestamps, and provider origin.
3. **Quant & Strategy Engine**: Executes quantitative research, indicator generation, parameter optimization, Monte Carlo, and walk-forward validation.
4. **Intelligence Engine**: Synthesizes market signals into structured research decisions with full evidence provenance and confidence bounds.
5. **Paper Engine**: Matches simulated orders against true market tick sequences with realistic slippage models.
