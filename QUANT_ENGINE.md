# QUANT ENGINE & TECHNICAL INDICATORS SPECIFICATION

## 1. Overview
All quantitative indicators in APEX are computed deterministically within `backend/app/quant_engine/indicators.py` and `backend/app/quant_engine/options.py`.

## 2. Implemented Indicators

| Indicator | Implementation | Usage & Signal Logic |
| :--- | :--- | :--- |
| **EMA 20 / EMA 50** | `calculate_ema(series, period)` | Trend identification & dynamic support/resistance |
| **VWAP** | `calculate_vwap(df)` | Institutional intraday benchmark price |
| **RSI (14)** | `calculate_rsi(series, period)` | Momentum & overbought (>70) / oversold (<30) zones |
| **MACD** | `calculate_macd(series, fast, slow, signal)` | Trend momentum & signal crossovers |
| **ATR (14)** | `calculate_atr(df, period)` | Volatility measurement & dynamic stop-loss sizing |
| **Bollinger Bands** | `calculate_bollinger_bands(series, period, std)` | Volatility squeeze & mean reversion channels |
| **Relative Volume (RVOL)** | `calculate_relative_volume(series, period)` | Volume surge detector (RVOL > 1.5x) |
| **ROC** | `calculate_roc(series, period)` | Rate of change momentum percentage |
| **Stochastic Oscillator** | `calculate_stochastic(df, k, d)` | Momentum oscillator (%K, %D) |

## 3. Options Intelligence

- **PCR (Put-Call Ratio)**: `total_put_oi / total_call_oi`. PCR > 1.2 indicates put writing support.
- **Max Pain**: Strike price minimizing option writer financial loss.
- **OI Sentiment Classification**:
  - `LONG_BUILDUP`: Price UP + Open Interest UP
  - `SHORT_BUILDUP`: Price DOWN + Open Interest UP
  - `SHORT_COVERING`: Price UP + Open Interest DOWN
  - `LONG_UNWINDING`: Price DOWN + Open Interest DOWN
