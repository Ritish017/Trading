# APEX — PERSONAL AI QUANT & TRADING RESEARCH LAB

A production-quality personal quantitative research workstation, event-driven backtesting platform, real-time paper trading simulator, and AI research assistant designed specifically for Indian Equities (NSE / BSE).

> [!NOTE]
> This is a **PERSONAL** application engineered for individual quantitative trading research and software engineering learning. It is not optimized as a SaaS product or multi-tenant system.

---

## Real Market Data Setup (Upstox V3 Integration)

To connect real live market data from your Upstox Developer Account:

1. Copy environment template:
   ```bash
   cp backend/.env.example .env
   ```
2. Open `.env` and set your read-only **Upstox Analytics Token**:
   ```env
   ACTIVE_BROKER_PROVIDER=UPSTOX
   UPSTOX_ENABLED=true
   UPSTOX_ANALYTICS_TOKEN=your_upstox_analytics_token_here
   ALLOW_MOCK_FALLBACK=false
   ```
3. Test your connection:
   ```bash
   python scripts/test_upstox_connection.py
   ```
4. Refer to [docs/UPSTOX_INTEGRATION.md](file:///c:/Tradinf2/docs/UPSTOX_INTEGRATION.md) for complete details.

---

## Key Features

1. **Real-Time Data Engine & Normalization**:
   - Provider abstraction layer (`MarketDataProvider`) with Upstox V3, Dhan HQ, and DevMock adapters.
   - Protobuf/Binary WebSocket stream normalization into canonical `NormalizedTick` and `NormalizedCandle` models.
   - Deterministic bar aggregation across `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `1D`.

2. **Deterministic Quantitative Analytics**:
   - EMA20, EMA50, VWAP, RSI, MACD, ATR, Bollinger Bands, ROC, Stochastic, RVOL.
   - Options Intelligence: Put-Call Ratio (PCR), Max Pain Strike, Call/Put OI Long/Short Buildup & Unwinding.
   - Market Volatility Regime classification (`TRENDING_BULLISH`, `BEARISH_DISTRIBUTION`, `HIGH_VOLATILITY`, `RANGE_BOUND`).

3. **Event-Driven Backtest & Walk-Forward Validation**:
   - Strategy rules DSL engine (`Price > VWAP AND EMA20 > EMA50 AND RSI > 55`).
   - Mandated 70% In-Sample training vs 30% Out-of-Sample forward validation.
   - Friction simulation: 0.05% slippage, ₹20 flat brokerage.
   - Overfitting detector (`STATUS = OVERFIT / REJECTED`).

4. **Multi-Agent AI System (Google Gemini 2.5 Flash)**:
   - `MarketResearchAgent`: Structured JSON market stance reports.
   - `PersonalTradingCoach`: Fact-based trade journal behavioral analytics.
   - `StrategyResearchAgent`: Translates natural language research ideas into quantitative hypotheses.

5. **Realistic Paper Trading Simulator & Journal**:
   - CNC (Delivery 100% margin) and MIS (Intraday 20% margin / 5x leverage) margin checks.
   - Live order execution against streaming market ticks, PnL monitoring, and journal analytics.

6. **Professional Workstation UI**:
   - Live Data Badges (`🟢 LIVE — UPSTOX`, `🟡 SIMULATED — DEV MOCK`, `🔴 DISCONNECTED`).
   - Command Palette (`Ctrl + K`).
   - AI Copilot drawer.
   - APEX Learn interactive quantitative engineering guide.
   - Market Replay historical simulator without look-ahead bias.

---

## Subsystem Documentation

- [docs/UPSTOX_INTEGRATION.md](file:///c:/Tradinf2/docs/UPSTOX_INTEGRATION.md)
- [ARCHITECTURE.md](file:///c:/Tradinf2/ARCHITECTURE.md)
- [API.md](file:///c:/Tradinf2/API.md)
- [DATA_MODEL.md](file:///c:/Tradinf2/DATA_MODEL.md)
- [BROKER_INTEGRATION.md](file:///c:/Tradinf2/BROKER_INTEGRATION.md)
- [QUANT_ENGINE.md](file:///c:/Tradinf2/QUANT_ENGINE.md)
- [BACKTESTING.md](file:///c:/Tradinf2/BACKTESTING.md)
- [AI_SYSTEM.md](file:///c:/Tradinf2/AI_SYSTEM.md)
- [SECURITY.md](file:///c:/Tradinf2/SECURITY.md)
- [DEPLOYMENT.md](file:///c:/Tradinf2/DEPLOYMENT.md)
- [LEARNING_GUIDE.md](file:///c:/Tradinf2/LEARNING_GUIDE.md)

---

## Quick Start Guide

### Prerequisites
- Python 3.11+
- Node.js 18+

### Setup Environment
```bash
cp backend/.env.example .env
```

### Run FastAPI Backend
```bash
uvicorn backend.app.main:app --reload --port 8000
```

### Run React Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser. Press `Ctrl + K` to bring up the Command Palette.
