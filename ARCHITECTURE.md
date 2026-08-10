# APEX — PERSONAL AI QUANT & TRADING RESEARCH LAB: ARCHITECTURE

## 1. System Architecture Overview

Apex is engineered as a modular, personal quantitative research laboratory for Indian Equities (NSE/BSE).

```
FRONTEND (React 19 + TypeScript + Vite + Tailwind v4)
 ↓ WebSocket Stream (/ws/ticks) & REST API (/api/*)
FASTAPI BACKEND SERVICE
 ↓ Provider Abstraction (MarketDataProvider)
BROKER STREAMING ADAPTERS (Upstox V3 / Dhan HQ / DevMock)
 ↓
QUANT ENGINE | STRATEGY DSL | BACKTESTER | MULTI-AGENT AI SYSTEM
 ↓
POSTGRESQL + TIMESCALEDB & REDIS
```

## 2. Key Subsystems & Execution Flow

1. **Broker Streaming & Normalization**:
   - `MarketDataProvider`: Abstract base class enforcing provider isolation (`UpstoxProvider`, `DhanProvider`, `DevMockProvider`).
   - `NormalizedTick`: Canonical schema (`symbol`, `exchange`, `timestamp`, `ltp`, `volume`, `bid`, `ask`, `open_interest`).

2. **Candle Aggregator Engine**:
   - `CandleAggregator`: Deterministic aggregation across 1m, 3m, 5m, 15m, 30m, 1h, 1D.

3. **Deterministic Quantitative Analytics**:
   - Technical Indicators: SMA, EMA, VWAP, RSI, MACD, ATR, Bollinger Bands, ROC, Stochastic, RVOL.
   - Options Intelligence: PCR, Max Pain Strike, OI Long/Short Buildup and Unwinding.
   - Regime Classifier: Categorizes regimes into `TRENDING_BULLISH`, `BEARISH_DISTRIBUTION`, `HIGH_VOLATILITY`, `RANGE_BOUND`.

4. **Event-Driven Backtest & Walk-Forward Engine**:
   - Evaluates Strategy Hypotheses across 70% In-Sample training and 30% Out-Of-Sample validation.
   - Simulates slippage (0.05%) and flat brokerage (₹20 per order).
   - Rejects overfit strategies (`STATUS = OVERFIT / REJECTED`).

5. **Multi-Agent AI System**:
   - `MarketResearchAgent`: Produces structured JSON market stance reports.
   - `PersonalTradingCoach`: Data-backed behavioral journal review.
   - `StrategyResearchAgent`: Converts human queries into quantitative rules.

6. **Paper Simulator**:
   - Support for CNC (Delivery 100% margin) and MIS (Intraday 20% margin / 5x leverage).
