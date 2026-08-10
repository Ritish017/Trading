# APEX PERSONAL LEARNING GUIDE

## 1. Executive Learning Goals
APEX is designed as a hands-on learning environment for:
1. Modern Software Engineering (React 19, TypeScript, FastAPI, WebSockets, TimescaleDB, Async Python).
2. Quantitative Finance & Technical Analysis (VWAP, EMA, Options PCR, Max Pain, Volatility Regimes).
3. Backtesting & Risk Management (Walk-forward testing, Out-of-sample validation, Slippage, Brokerage).

## 2. Interactive Learning Modules (APEX Learn)

Every major quantitative topic maps directly to implementation code inside APEX:

- **VWAP Calculation**:
  - *Concept*: Volume-Weighted Average Price
  - *Location*: `backend/app/quant_engine/indicators.py#L13-L23`
  - *Formula*: `(Typical Price * Volume).cumsum() / Volume.cumsum()`

- **Exponential Moving Average (EMA)**:
  - *Concept*: Lag-reduced moving average
  - *Location*: `backend/app/quant_engine/indicators.py#L9-L11`

- **Put-Call Ratio (PCR) & Max Pain**:
  - *Concept*: Derivatives positioning
  - *Location*: `backend/app/quant_engine/options.py#L4-L35`

- **Walk-Forward Validation**:
  - *Concept*: Overfitting prevention (70% In-Sample / 30% Out-of-Sample)
  - *Location*: `backend/app/backtesting/event_driven.py#L125-L133`
