# Apex NSE/BSE Market Intelligence Terminal — Complete Documentation

## 1. Executive Summary & Architecture Overview

**Apex NSE/BSE Market Intelligence Terminal** is a production-grade, high-frequency Indian Stock Market Intelligence and Trading Interface built with React 19, TypeScript, Vite, Tailwind CSS v4, and Google Gemini 2.5 Flash AI integration.

The application simulates real-time tick movements across the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE), offering institutional-grade analytics such as:
- Real-time tick engine simulating price movements every 1.2 seconds.
- Interactive SVG Candlestick & Area charts with live Technical Indicator overlays (EMA20, EMA50, VWAP, OHLC readouts, and volume bars).
- FII (Foreign Institutional Investors) & DII (Domestic Institutional Investors) Cash & Derivatives flow analytics.
- Option Chain & Derivatives Summary (PCR - Put Call Ratio, Max Pain Strike, Call/Put OI, Implied Volatility).
- Advanced NSE Watchlist & Screener with sector filtering (IT, Banking, Energy, FMCG, Auto, Pharma) and 52-week price positioning gauge.
- Real-time SEBI Filings, Corporate Announcements, and earnings sentiment stream.
- Server-side Google Gemini 2.5 Flash AI Market Analyst endpoint providing quantitative trade setups, support/resistance levels, and market stance reports.
- Paper Trading Order Terminal supporting CNC (Equity Delivery - 100% margin) and MIS (Intraday - 5x leverage / 20% margin) with real-time PnL calculation and local storage persistence.

---

## 2. Technology Stack & System Architecture

### Frontend Stack
- **Framework**: React 19 (`react`, `react-dom`)
- **Language**: TypeScript (`~5.8.2`)
- **Bundler & Dev Server**: Vite 6 (`vite`, `@vitejs/plugin-react`)
- **Styling**: Tailwind CSS v4 (`@tailwindcss/vite`, `tailwindcss`)
- **Icons**: Lucide React (`lucide-react`)
- **Charts / Visualizations**: Custom high-performance SVG Candlestick Engine & Recharts (`recharts`)
- **Animations**: Motion (`motion`)

### Backend / Server-Side Stack
- **API Middleware**: Vite Custom Server Plugin (`expressApiPlugin`)
- **AI SDK**: Google GenAI SDK (`@google/genai` v2.4.0)
- **Model**: `gemini-2.5-flash`

---

## 3. Key Application Features

### 3.1 Real-Time Tick Simulation Engine
- Runs on a **1.2-second interval loop**, calculating micro-fluctuations in stock prices, indices, intraday highs, lows, VWAP, and percentage change.
- Updates live candlestick feeds dynamically in memory.
- Recalculates open position PnL for active paper trading accounts in real time.

### 3.2 Dynamic Technical Charting Engine
- **Chart Modes**: Candlestick View & Area Chart View.
- **Timeframes**: `1m`, `5m`, `15m`, `1h`, `1D`.
- **Technical Indicators**:
  - **EMA 20** (Exponential Moving Average 20-period)
  - **EMA 50** (Exponential Moving Average 50-period)
  - **VWAP** (Volume-Weighted Average Price)
- **Interactive Controls**: Range zoom, indicator toggles, live OHLC header readout.

### 3.3 Institutional FII / DII Flow Tracker
- Tracks net institutional buying/selling in ₹ Crores.
- Breaks down flows into Cash Market, Index Futures, Index Options, and Stock Futures.
- Visual sentiment meters (Institutional Bias: Heavy Accumulation, Net Buying, Neutral, Distribution).

### 3.4 Derivatives Option Chain & Market Breadth
- Displays real-time Put-Call Ratio (PCR), Max Pain Strike Level, Total Call/Put Open Interest (OI in Lakhs), and Implied Volatility (IV %).
- Market Breadth metrics: Advances vs. Declines ratio, New 52-Week Highs/Lows count, Upper & Lower Circuit triggers.

### 3.5 Watchlist & Sector Screener
- Sector filter categories: `All`, `Favorites`, `NIFTY 50`, `IT Services`, `Banking & Financials`, `Energy & Oil`, `Automotive`, `FMCG`, `Pharmaceuticals`.
- Multi-dimensional data columns: NSE Symbol, BSE Code, Current Price (₹), 24h Change, Volume (Lakhs), Turnover (₹ Cr), P/E Ratio, and 52-Week Range indicator bar.

### 3.6 Gemini 2.5 Flash AI Market Intelligence Analyst
- **Endpoint**: `/api/indian-market-intelligence`
- Analyzes institutional flows, technical indicators, PCR, and price momentum.
- Returns a structured JSON output:
  - Market Stance (e.g. Bullish Accumulation, Strong Bullish)
  - Confidence Score (0 - 100%)
  - NIFTY Correlation Score
  - Executive Summary & Catalysts
  - Support (S1, S2) and Resistance (R1, R2) Levels
  - Tactical Trade Setup (Entry Zone, Target 1, Target 2, Stop-loss, Risk/Reward Ratio)
- Automatic offline/fallback engine generating localized quantitative analysis when no API key is provided.

### 3.7 Paper Trading Terminal & Execution Engine
- Starting Virtual Capital: **₹10,00,000 (10 Lakhs INR)**.
- **Product Types**:
  - **CNC (Delivery)**: 100% Margin requirement, hold indefinitely.
  - **MIS (Intraday)**: 20% Margin requirement (5x Leverage), auto target/stop-loss parameters.
- Persistent state using browser `localStorage` (`apexnse_stocks`, `apexnse_balance`, `apexnse_positions`).

---

## 4. API Specification & Endpoints

### 1. `POST /api/indian-market-intelligence`
Generates comprehensive market intelligence reports using Gemini 2.5 Flash.

#### Request Body Schema:
```json
{
  "symbol": "RELIANCE.NS",
  "name": "Reliance Industries Ltd",
  "sector": "Energy & Oil",
  "price": 2845.50,
  "change24h": 1.45,
  "niftyPrice": 24580,
  "fiiFlow": "+1,840.5",
  "diiFlow": "+1,210.8",
  "pcr": 1.18
}
```

#### Response Body Schema:
```json
{
  "symbol": "RELIANCE.NS",
  "name": "Reliance Industries Ltd",
  "sector": "Energy & Oil",
  "marketStance": "Bullish Accumulation",
  "confidence": 88,
  "niftyCorrel": "0.82 High Positive",
  "fiiDiiSentiment": "FII Buying Acceleration",
  "executiveSummary": "Strong institutional order flow driven by quarterly earnings resilience...",
  "supportLevels": [2774.36, 2703.23],
  "resistanceLevels": [2916.64, 2987.78],
  "technicalMetrics": {
    "rsi14": 58.4,
    "ema20": 2802.82,
    "ema50": 2731.68,
    "vwap": 2831.27,
    "pcrSignal": "Bullish Put Writing at 2788.59"
  },
  "catalysts": [
    "Q3 YoY Revenue Growth beat consensus estimates by 4.2%",
    "FII Net cash inflows reached 3-week peak in Energy & Oil basket"
  ],
  "tacticalTradeSetup": {
    "action": "Buy / Delivery CNC",
    "entryZone": "₹2817.05 - ₹2845.5",
    "target1": "₹2959.32",
    "target2": "₹3073.14",
    "stopLoss": "₹2745.91",
    "riskReward": "1 : 2.8"
  }
}
```

---

## 5. Directory & File Structure

```
c:\Tradinf2/
├── index.html                   # HTML Entry point
├── metadata.json                # Project Metadata & Capabilities
├── package.json                 # Project dependencies and npm scripts
├── vite.config.ts               # Vite configuration + Gemini Express API plugin
├── bun.lock                     # Lockfile for Bun package manager
└── src/
    ├── App.tsx                  # Main Workspace Layout & State Orchestrator
    ├── main.tsx                 # React DOM Root Mounting Point
    ├── index.css                # Global Tailwind CSS Styles
    ├── components/              # Component Library
    │   ├── AIAnalystModal.tsx             # Legacy AI Modal Component
    │   ├── AssetStoryCards.tsx            # Market Stories Card Component
    │   ├── DepositModal.tsx               # Virtual Deposit Modal
    │   ├── FIIDIITracker.tsx              # Institutional Flow Visualization
    │   ├── Header.tsx                     # Generic Navigation Header
    │   ├── IndexTickerBar.tsx             # Live Indices Ticker Header Bar
    │   ├── IndianCandleChart.tsx          # SVG Candlestick & Indicator Chart
    │   ├── MarketIntelligenceModal.tsx    # Gemini AI Market Intelligence Modal
    │   ├── MarketNews.tsx                 # Market Headlines Component
    │   ├── NSEWatchlist.tsx               # Sector Screener & Stock Table
    │   ├── Navbar.tsx                     # Secondary Navigation Bar
    │   ├── OptionChainSummary.tsx         # Derivatives PCR & OI Summary
    │   ├── OrderBook.tsx                  # Market Depth / Order Book View
    │   ├── OrderForm.tsx                  # Direct Order Form Component
    │   ├── PaperTradingModal.tsx          # Paper Order & Position Manager
    │   ├── PositionsPanel.tsx             # Open Positions PnL Monitor
    │   ├── RightTradingPanel.tsx          # Side Order Execution Panel
    │   ├── SEBIAnnouncementsFeed.tsx      # Corporate Filings Feed
    │   ├── Sidebar.tsx                    # Left Navigation Drawer
    │   ├── TerminalHeader.tsx             # Primary Market Navigation Bar
    │   ├── TradeTape.tsx                  # Real-Time Time & Sales Stream
    │   ├── TradingChart.tsx               # Recharts Trading Chart Component
    │   ├── TransactionsTable.tsx          # Transaction Logs Component
    │   └── Watchlist.tsx                  # Generic Asset Watchlist
    ├── data/                    # Mock Data Sets & Initial Feeds
    │   ├── indianMarketData.ts            # Stocks, Indices, FII/DII, Option Chains
    │   └── mockAssets.ts                  # Supplementary Asset Data
    ├── types/                   # TypeScript Interfaces & Types
    │   ├── indianMarket.ts                # NSE Stock, FII Flow, SEBI, Paper Trading types
    │   └── trading.ts                     # Generic Asset & Order Types
    └── utils/                   # Quantitative Functions & Technical Analysis
        ├── indianTechnicalAnalysis.ts     # EMA, VWAP, Local AI Fallback Engine
        └── technicalAnalysis.ts           # Standard Indicators (RSI, MACD, SMA)
```

---

## 6. How to Run & Develop

### Prerequisites
- Node.js (v18+) or Bun

### Installation
```bash
npm install
```

### Environment Variables
Set your Gemini API Key in `.env` (optional, fallback engine active if omitted):
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

### Run Local Development Server
```bash
npm run dev
```
Starts dev server on `http://localhost:3000`.

### Type Check & Build
```bash
npm run lint
npm run build
```
