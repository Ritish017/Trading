# APEX Signal Intelligence Engine — System Architecture

## 1. Architectural Vision

The APEX Signal Intelligence Engine is a deterministic, evidence-backed trading opportunity system for Indian Equities, Futures, and Options (NSE/BSE). It translates raw, authenticated market data into actionable decisions with strict financial invariants and durable persistence.

```
+-----------------------------------------------------------------------------------+
|                            REAL MARKET DATA / UPSTOX                              |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                        CANONICAL DATA & PROVENANCE LAYER                          |
|     * Raw Authentic Data (Provider feeds)                                        |
|     * Point-in-time candle slicing (Zero lookahead protection)                   |
|     * Provenance Tagging: RAW_AUTHENTIC_DATA / HISTORICAL / SIMULATED            |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                         MULTI-TIMEFRAME FEATURE VECTOR                            |
|     * Daily (1D), Hourly (1H), 15-Minute (15M), 5-Minute (5M)                    |
|     * EMAs (20, 50), RSI(14), ATR(14), VWAP, RVOL, MACD, ADX, Support/Resistance  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                              20 STRATEGY REGISTRY                                 |
|     * Trend Following, Mean Reversion, Breakout, Volatility, Institutional Momentum|
|     * Dual Long & Short Canonical Rules for Every Registered Strategy             |
|     * Strictly Point-In-Time Evaluation with Context Dependency Engine            |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                   CORRELATION-AWARE CONFLUENCE & REGIME FILTER                    |
|     * Correlation clustering (Trend, Momentum, Volatility, Volume, Structure)    |
|     * Independent evidence thresholding & family discounting                      |
|     * Regime compatibility gating (BULL_TRENDING, BEAR_TRENDING, CHOPPY, etc.)    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                          17-STAGE HARD VALIDATION GATES                           |
|     * Data freshness, Minimum candles, Zero-volume rejection                      |
|     * Minimum R:R (>= 1.5), Stop distance limit (<= 5%), Confluence thresholds     |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                           ENTRY, STOP, TARGETS & SIZING                           |
|     * ATR / Structural Support & Resistance Stops                                 |
|     * Progressive Targets (Target 1, Target 2, Target 3)                          |
|     * Fixed Risk Capital Allocation (1% per trade max, integer share sizing)      |
+-----------------------------------------------------------------------------------+
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
+--------------------------------+ +--------------------+ +-------------------------+
|         EQUITY SIGNAL          | |   FUTURES ENGINE   | |     OPTIONS ENGINE      |
|  * LONG / SHORT                | |  * BUY FUTURE      | |  * BUY CALL / PUT       |
|  * Quality Grade (A+, A, B, C) | |  * SELL FUTURE     | |  * BULL/BEAR SPREADS    |
|  * Opportunity Score (0-100)   | |  * Basis & OI Gate | |  * Greeks & Strike Pick |
+--------------------------------+ +--------------------+ +-------------------------+
                 │                       │                       │
                 └───────────────────────┼───────────────────────┘
                                         ▼
+-----------------------------------------------------------------------------------+
|                     DURABLE POSTGRESQL / SQLITE PERSISTENCE                       |
|     * Authoritative Tables: signals, signal_events, signal_strategy_votes,        |
|       signal_rejections, signal_outcomes, signal_performance_snapshots            |
|     * Process Restart Recovery & Multi-Worker State Synchronization               |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                       AUTHORITATIVE PAPER TRADING LEDGER                          |
|     * One Single Shared Portfolio State                                           |
|     * Order Execution, Margin Validation, Fills, Mark-to-Market                   |
+-----------------------------------------------------------------------------------+
```

## 2. Core Operational Modules

1. **`models.py`**: Domain definitions for signals, rejections, candidates, and configuration using Pydantic V2.
2. **`validation_gates.py`**: 17 deterministic hard and soft gates. Rejects candidates failing data quality, volume, or risk criteria.
3. **`confluence_engine.py`**: Aggregates strategy votes across 5 independent correlation clusters (Trend, Momentum, Volatility, Volume, Structure) to prevent duplicate indicator bias.
4. **`stop_target_engine.py`**: Geometry engine generating ATR and structural swing stops and ascending/descending targets.
5. **`position_sizing_engine.py`**: Capital-conserving integer lot and share sizer guaranteeing risk $\le 1.0\%$ of capital.
6. **`scoring_engine.py`**: Multi-factor opportunity scoring producing grades $A+, A, B, C,$ and $NO\_TRADE$.
7. **`multi_timeframe_engine.py`**: High-to-low timeframe alignment engine (1D down to 5M).
8. **`signal_pipeline.py`**: Orchestrator executing the complete evaluation pipeline for a candidate.
9. **`scanner.py`**: Parallel, bounded-concurrency market scanner evaluating universes with error isolation.
10. **`signal_store.py`**: In-memory cache coupled with background and explicit durable database persistence.
11. **`lifecycle.py`**: Strict state machine enforcing legal progression (`CANDIDATE` to `TARGET_3` or terminal exits).
12. **`futures_engine.py`**: Dedicated futures decision engine analyzing basis, rollover, and OI buildup patterns.
13. **`options_engine.py`**: Black-Scholes Greeks engine evaluating liquid strikes and multi-leg vertical debit spreads.
14. **`transaction_cost.py`**: Centralized SEBI/NSE statutory schedule covering brokerage, STT, turnover charges, SEBI, GST, stamp duty, and slippage.
15. **`outcome_engine.py`**: Forward-market outcome tracker calculating MAE, MFE, realized R, holding times, and net PnL.
16. **`performance_engine.py`**: Empirical statistical engine calculating expectancy, profit factor, drawdown in R, and win rates with sample size flags.
17. **`calibration_engine.py`**: Audits heuristic confidence scores against empirical outcomes in 5 buckets (50-60 to 90-100).
18. **`walk_forward.py`**: Chronological train/validation/test splitter and parameter perturbation stress harness.
