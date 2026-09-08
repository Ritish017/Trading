# APEX Signal Intelligence Engine — Validation & Conformance

## 1. 17-Stage Validation Pipeline

Every instrument evaluated by the Signal Engine must pass a sequence of hard gates before it can qualify as an active trade opportunity.

### Hard Gates (Mandatory Pass)
1. **`DATA_ACQUISITION`**: Must have valid price data; LTP > 0.
2. **`MINIMUM_CANDLES_REQUIRED`**: Primary timeframe must have at least 15 valid candles.
3. **`ZERO_VOLUME_GATE`**: Cumulative volume across recent candles must be > 0. Zero-volume candles fail closed.
4. **`DATA_FRESHNESS`**: Candles must not exceed maximum age threshold (30 minutes).
5. **`STOP_LOSS_GEOMETRY`**: Stop price cannot equal entry price ($Stop \neq Entry$).
6. **`STOP_LOSS_DIRECTION`**: Long stop must be $< Entry$; Short stop must be $> Entry$.
7. **`STOP_DISTANCE_LIMIT`**: Stop distance cannot exceed configured max (5% of entry).
8. **`TARGET_GEOMETRY`**: Target 1 must be directionally valid ($T1 > Entry$ for LONG, $T1 < Entry$ for SHORT).
9. **`MINIMUM_RISK_REWARD`**: $R:R = \frac{|Target_1 - Entry|}{|Entry - Stop|} \ge 1.5$.
10. **`MINIMUM_CONFLUENCE`**: Must have at least 1 confirmed strategy category vote in the signal direction.
11. **`CONFLICTING_DIRECTION_GATE`**: Opposing independent category votes must not exceed agreeing votes.
12. **`REGIME_COMPATIBILITY_HARD`**: Prohibits strong trend trades directly against a confirmed opposing market regime.
13. **`LIQUIDITY_VALIDATION`**: Average volume must meet minimum market liquidity standards.
14. **`CAPITAL_REQUIREMENT`**: Required margin / trade capital must not exceed available capital.
15. **`POSITION_RISK_CAP`**: Per-trade risk cannot exceed configured risk fraction (1% of capital).
16. **`MAX_PORTFOLIO_EXPOSURE`**: Open positions must not exceed max concurrent positions or portfolio cap.
17. **`SCORE_THRESHOLD`**: Combined opportunity score must meet or exceed Grade C threshold (60.0).

---

## 2. All 20 Strategies Conformance Matrix

| # | Strategy ID | Category | Directional Support | Minimum Candles | Bullish State | Bearish State |
|---|---|---|---|---|---|---|
| 1 | `MOMENTUM_BREAKOUT` | Breakout | BOTH | 20 | LONG | SHORT |
| 2 | `EMA_CROSSOVER` | Trend Following | BOTH | 50 | LONG | SHORT |
| 3 | `PULLBACK_CONFLUENCE` | Trend Following | BOTH | 50 | LONG | SHORT |
| 4 | `VOLATILITY_EXPANSION` | Volatility | BOTH | 20 | LONG | SHORT |
| 5 | `VWAP_TREND_INTRADAY` | Institutional Flow | BOTH | 20 | LONG | SHORT |
| 6 | `OPENING_RANGE_BREAKOUT`| Breakout | BOTH | 15 | LONG | SHORT |
| 7 | `RSI_OVERSOLD_REVERSAL` | Mean Reversion | BOTH | 15 | LONG | SHORT |
| 8 | `SUPER_TREND_RHO` | Trend Following | BOTH | 20 | LONG | SHORT |
| 9 | `CHAIKIN_FLOW_ACCUM` | Institutional Flow | BOTH | 20 | LONG | SHORT |
| 10| `BOLLINGER_MEAN_REVERSION`| Mean Reversion | BOTH | 20 | LONG | SHORT |
| 11| `MACD_HISTOGRAM_IMPULSE`| Momentum | BOTH | 35 | LONG | SHORT |
| 12| `ADX_DYNAMIC_TREND` | Trend Following | BOTH | 25 | LONG | SHORT |
| 13| `VOLUME_PRICE_CONFIRMATION`| Volume/Flow | BOTH | 20 | LONG | SHORT |
| 14| `PRICE_ACTION_HAMMER` | Price Action | BOTH | 10 | LONG | SHORT |
| 15| `DONCHIAN_CHANNEL_TREND`| Trend Following | BOTH | 20 | LONG | SHORT |
| 16| `STOCHASTIC_RSI_SWING` | Momentum | BOTH | 20 | LONG | SHORT |
| 17| `KELTNER_SQUEEZE` | Volatility | BOTH | 20 | LONG | SHORT |
| 18| `FIBONACCI_RETRACEMENT` | Structure | BOTH | 30 | LONG | SHORT |
| 19| `ORDER_FLOW_IMBALANCE` | Institutional Flow | BOTH | 15 | LONG | SHORT |
| 20| `MULTIPLE_TIMEFRAME_ALIGN`| Confluence | BOTH | 30 | LONG | SHORT |

All 20 strategies are verified by automated conformance tests (`test_strategy_conformance_matrix.py`) ensuring:
- Dual Long and Short rule execution.
- Deterministic output across synthetic bull and bear market conditions.
- Strict point-in-time calculation with zero lookahead bias.
