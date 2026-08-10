# APEX API SPECIFICATION

## 1. REST Endpoints

### Health & Observability
- `GET /health`: Basic system status and safety flags.
- `GET /health/data-feed`: Active market data provider connection status.
- `GET /health/database`: Async database health check.
- `GET /health/redis`: Event bus health check.

### Market Data APIs
- `GET /api/market/quote/{symbol}`: Returns live tick quote for `symbol`.
- `GET /api/market/candles/{symbol}?interval=5m&count=60`: Historical aggregated candles.
- `GET /api/market/option-chain/{symbol}`: Derivatives PCR, Max Pain, ATM strike, Call/Put OI snapshot.

### Quantitative & AI Intelligence APIs
- `POST /api/quant/indicators`: Computes EMA, VWAP, RSI, RVOL, support/resistance.
- `POST /api/quant/regime`: Classifies market regime (`TRENDING_BULLISH`, `BEARISH_DISTRIBUTION`, etc.).
- `POST /api/ai/market-analysis`: Structured JSON report from `MarketResearchAgent`.
- `POST /api/ai/trading-coach`: Data-backed behavioral review of trader journal.
- `POST /api/ai/strategy-hypothesis`: Converts text queries into quantitative rules.

### Paper Trading & Journal APIs
- `POST /api/paper/order`: Submits paper order (CNC or MIS) with margin verification.
- `GET /api/paper/positions`: Returns open positions and available capital.
- `POST /api/paper/close/{pos_id}`: Closes open paper position and updates PnL.
- `POST /api/journal/analytics`: Calculates win rate, expectancy, and profit factor over trade logs.

### Backtest Engine API
- `POST /api/backtest/run`: Runs event-driven backtest with 70/30 Walk-Forward split.

---

## 2. WebSocket Stream
- `WS /ws/ticks`: Broadcasts normalized live ticks (`type: "TICK"`) and aggregated candles every 1.2 seconds.
