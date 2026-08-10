# BROKER INTEGRATION & MARKET DATA SPECIFICATION

## 1. Provider Abstraction Architecture

APEX decouples core quant, backtesting, and UI logic from specific broker APIs via `MarketDataProvider` (`backend/app/broker_providers/base.py`).

## 2. Integrated Provider Adapters

1. **Upstox V3 Provider (`UpstoxProvider`)**:
   - Authentication: OAuth 2.0 flow with Access Tokens.
   - REST API: Historical candles (`/v2/historical-candle`), Option chain (`/v2/option/chain`).
   - WebSocket: Protobuf binary feed (`wss://api.upstox.com/v2/feed/market-data-feed`).

2. **Dhan HQ Provider (`DhanProvider`)**:
   - Authentication: Client ID & Access Token headers.
   - REST API: Intraday historical charts (`/charts/historical`), Option chain (`/optionchain`).
   - WebSocket: Binary market data feed (`wss://api-feed.dhan.co`).

3. **Development Mock Provider (`DevMockProvider`)**:
   - Generates synthetic tick and candle feeds obeying financial bounds for offline development and testing.

## 3. Resilience & Failure Handling

- Connection health monitoring with exponential backoff reconnect.
- Graceful degradation: If a broker feed disconnects, the UI displays `DATA DEGRADED / TICK RECOVERY` without crashing the application.
