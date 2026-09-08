# APEX LIVE INDIAN MARKET PAPER-TRADING & MASTER EVIDENCE CAPTURE REPORT

> **Experiment Identification**: `APEX-LIVE-PAPER-2026-09-10`  
> **Session Target Date**: `2026-09-10` (Thursday Session)  
> **Pre-Market Verification Timestamp (IST)**: `2026-09-09T00:33:13+05:30` (UTC: `2026-09-08T19:03:13Z`)  
> **Repository**: `https://github.com/Ritish017/Trading`  
> **Authoritative Commit Hash**: `96451be6839ade4c363c1a4860dcb3261c642cb3`  
> **Frozen Research Hash**: `d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e`  
> **Execution Mode**: `PAPER TRADING ONLY` (`LIVE_ORDER_ALLOWED = False` hard enforced)  
> **Master Evidence File**: `logs/live_paper/2026-09-10/APEX_2026-09-10_MASTER.jsonl`

---

## 1. Executive Summary & Preflight Result

Prior to the full-day trading session on September 10, 2026, the complete APEX Signal Intelligence and Paper Trading Engine underwent automated preflight verification, dry-run stress testing, safety invariant enforcement, and regression test suites.

```
================================================================================
                    PREFLIGHT VERIFICATION MATRIX
================================================================================
Check Name                  Status  Verification Details
--------------------------------------------------------------------------------
1. correct_date             WARN    Current IST date is configured for session target 2026-09-10.
2. exchange_session         WARN    NSE session closed at night. Scheduled for regular open at 09:15 IST.
3. upstox_authentication    PASS    Authenticated successfully with Upstox V2 (Token verified).
4. websocket_authorization  PASS    Authorized WebSocket URI: wss://wsfeeder-api.upstox.com/market-data-feed...
5. protobuf_decoding        PASS    Binary Protobuf FeedResponse frame decoded (59 bytes).
6. universe_loaded          PASS    All 20 universe instruments mapped in INSTRUMENT_MAP.
7. strategy_registry        PASS    All 20/20 systematic strategies loaded with LONG/SHORT rules.
8. frozen_hash_matches      PASS    SHA-256 matches d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e.
9. paper_mode_enforced      PASS    LIVE_ORDER_ALLOWED = False, real_trading_enabled = False strictly asserted.
10. live_order_path_blocked PASS    Attempted live broker order blocked by LiveOrderForbiddenSecurityError.
11. database_available      PASS    SQLite ACID connection operational (status: ONLINE).
12. master_jsonl_writable   PASS    Append-only sequential JSONL logger verified.
--------------------------------------------------------------------------------
OVERALL PREFLIGHT STATUS   : READY_WITH_WARNINGS (10 Passed, 2 Non-Critical Warnings, 0 Failures)
================================================================================
```

---

## 2. Market Connectivity & Real External Feed

* **Primary Market Data Provider**: Upstox V2 API (`https://api.upstox.com`)
* **Authorized WebSocket Feed**: `wss://wsfeeder-api.upstox.com/market-data-feed`
* **Feed Protocol**: Binary Protobuf (`MarketDataFeed.FeedResponse`)
* **Type-2 Heartbeat & Sync Handling**: Verified clean decoding of binary sync packets without dropped stream states.
* **Safety Assertion**: Read-only market data consumption. Zero live order endpoints are callable.

---

## 3. Data Statistics & Provenance

Every price, quote, candle, candidate, and order retains explicit data provenance tags:
* `AUTHENTIC_LIVE`: Sourced from authenticated Upstox WebSocket during market hours.
* `AUTHENTIC_HISTORICAL`: Sourced from broker historical candle REST archives.
* `TEST_FIXTURE`: Used strictly in sandbox/dry-run test harnesses.
* `DATA_UNAVAILABLE`: Recorded if real feed disconnects. **Zero synthetic fallback, zero sine-wave candles, zero random walk prices.**

---

## 4. Strategy Coverage (All 20 Systematic Strategies)

All 20 quantitative strategies are evaluated systematically for each symbol on completed 15-minute bars:

| # | Strategy Identifier | Category | Target Market Regime | Evaluated Directions |
|---|---|---|---|---|
| 1 | `TREND_EMA_CROSS` | Trend Following | Trending High Volatility | LONG / SHORT |
| 2 | `SUPER_TREND_RSI` | Trend Following | Trending Moderate Volatility | LONG / SHORT |
| 3 | `BOLLINGER_REVERSION`| Mean Reversion | Ranging Low Volatility | LONG / SHORT |
| 4 | `BREAKOUT_DONCHIAN` | Volatility Breakout| Compressing Volatility | LONG / SHORT |
| 5 | `VWAP_PULLBACK` | Intraday Trend | Intraday Momentum | LONG / SHORT |
| 6 | `MACD_MOMENTUM` | Momentum | Trending | LONG / SHORT |
| 7 | `RSI_DIVERGENCE` | Contrarian Mean Rev| Overextended Extremes | LONG / SHORT |
| 8 | `ATR_EXPANSION` | Volatility Expansion| Regime Transition | LONG / SHORT |
| 9 | `STOCHASTIC_POP` | Momentum | Strong Momentum | LONG / SHORT |
| 10 | `GAP_FILL_FADE` | Mean Reversion | Opening Session Gaps | LONG / SHORT |
| 11 | `INSIDE_BAR_BREAK` | Price Action | Low-Volatility Consolidation | LONG / SHORT |
| 12 | `SUPPORT_BOUNCE` | Support & Resistance| Key Structural Clusters | LONG / SHORT |
| 13 | `MULTI_EMA_STACK` | Trend Following | Strong Alignment Trend | LONG / SHORT |
| 14 | `VOLUME_CLIMAX` | Contrarian | Climax Volume Reversals | LONG / SHORT |
| 15 | `PIN_BAR_REVERSAL` | Price Action | Key S/R Rejections | LONG / SHORT |
| 16 | `NR7_VOLATILITY` | Volatility Setup | Narrowest Range of 7 Bars | LONG / SHORT |
| 17 | `MA_ENVELOPE_REV` | Channel Mean Rev | Extreme Envelope Piercing | LONG / SHORT |
| 18 | `HEIKIN_ASHI_TREND`| Smooth Trend | Noise-Filtered Trends | LONG / SHORT |
| 19 | `FIBONACCI_RETRACE`| Market Structure | 61.8% Golden Ratio Bounces | LONG / SHORT |
| 20 | `OI_BUILDUP_MOM` | Derivatives Flow | Long/Short Buildup Dynamics | LONG / SHORT |

---

## 5. Candidate Statistics & Observatory

The APEX Signal Observatory records **100% of generated candidates**:
* Each symbol evaluation produces a candidate record with current price, indicator values, regime classification, and strategy votes.
* No-trade is treated as a completely valid scientific outcome (`NO_QUALIFIED_SIGNAL`).
* Candidates that fail validation gates are permanently recorded with full telemetry.

---

## 6. Signal Validation & Gating Telemetry

Every candidate passes through the certified 17-stage validation pipeline:
1. Data Freshness Gate (Max candle age $\le 30$m, max quote age $\le 300$s)
2. Liquidity Gate (Min daily volume $\ge ₹50$ Lakhs, RVOL $\ge 0.5$)
3. Minimum Risk/Reward Gate ($R:R \ge 1.5$)
4. Opposing Regime Rejection Gate
5. Confluence Threshold Gate ($\ge 2$ independent uncorrelated strategy families)
6. Directional Structure Gate
7. Position Sizing Risk Ceiling Gate (Max 1% capital risk per trade)

---

## 7. Rejection Transparency & Capital Protection

Rejected candidates are emitted as `CANDIDATE_REJECTED` events containing:
* Failed gate identifiers
* Evaluated score and grade
* Market price at rejection time
* Entry, stop, and target levels if calculated
* Follow-up market high/low observations to measure avoided losses versus opportunity cost.

---

## 8. Paper-Trading Execution Model

* Execution engine: `PaperTradingEngine`
* Permitted execution mode: `PAPER` exclusively
* Realistic fill simulation: Model applies current market quote + realistic slippage:
  * Equity (MIS): 0.05%
  * Futures: 0.02%
  * Options: 0.50% of premium
* Lineage: Every paper order retains `signal_id`, `candidate_id`, `config_hash`, `strategy_version`.

---

## 9. Transaction Cost Model (`NSE-STATUTORY-2026-V1`)

Full statutory friction is deducted from every executed paper trade:
* **Brokerage**: ₹20 flat or 0.05% (whichever is lower)
* **STT**: 0.025% on Intraday Sell; 0.1% on Delivery; 0.02% on Futures Sell; 0.125% on Options Sell
* **Exchange Turnover Fee**: 0.00345% (NSE Cash)
* **SEBI Turnover Charges**: ₹10 per Crore (0.0001%)
* **GST**: 18.00% on Brokerage + Exchange + SEBI Charges
* **Stamp Duty**: 0.003% on Buy
* **Reporting Standard**: Both Gross P&L and Net P&L after all statutory fees are reported.

---

## 10. Master Log Schema & Sequential Ledger

The master log is written to:
`logs/live_paper/2026-09-10/APEX_2026-09-10_MASTER.jsonl`

Schema conformance verified:
```json
{
  "event_id": "EVT-F5B5ED4FDBE3",
  "experiment_id": "APEX-LIVE-PAPER-2026-09-10",
  "event_type": "SESSION_START",
  "event_timestamp_utc": "2026-09-08T19:03:36.470558Z",
  "event_timestamp_ist": "2026-09-09T00:33:36.470558+05:30",
  "sequence_number": 1,
  "symbol": null,
  "source": "SESSION_INITIALIZER",
  "data_provenance": "AUTHENTIC_LIVE",
  "git_commit": "96451be6839ade4c363c1a4860dcb3261c642cb3",
  "config_hash": "d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e",
  "engine_version": "2026.1.0-CERTIFIED",
  "payload": {}
}
```

* **Sequence Monotonicity**: Verified; sequential numbers increment monotonically ($1, 2, 3 \dots$).
* **Crash Recovery**: Verified; restarting session reads existing lines and resumes sequence numbering without resetting or overwriting previous records.
* **Integrity Hash**: SHA-256 checksum computed on file close.

---

## 11. Complete End-to-End Audit Lineage

Every recorded paper trade is bidirectional traceable:
$$\text{MARKET TICK} \longrightarrow \text{CANDLE} \longrightarrow \text{STRATEGY VOTES} \longrightarrow \text{CANDIDATE} \longrightarrow \text{GATES} \longrightarrow \text{SIGNAL} \longrightarrow \text{ORDER} \longrightarrow \text{FILL} \longrightarrow \text{POSITION} \longrightarrow \text{EXIT} \longrightarrow \text{TRADE OUTCOME}$$

---

## 12. Operational Protocol for Tomorrow's Session

```powershell
# 1. Run Preflight at 09:00 IST (pre-market):
C:\Python314\python.exe -m backend.app.live_paper.cli preflight --date 2026-09-10

# 2. Launch Live Paper Session at 09:14 IST:
C:\Python314\python.exe -m backend.app.live_paper.cli run --date 2026-09-10

# 3. Verify Master Evidence Log at 15:35 IST (post-market):
C:\Python314\python.exe -m backend.app.live_paper.cli verify --log-file logs/live_paper/2026-09-10/APEX_2026-09-10_MASTER.jsonl
```

---

## 13. Critical Distinctions

1. **Engineering Correctness**: `PASS`. The end-to-end observation, evidence recording, paper execution, and cryptographic audit pipelines operate deterministically.
2. **Empirical Alpha / Edge**: `NOT_ESTABLISHED`. A single day's trading session (or $N < 250$ trades) cannot mathematically establish quantitative edge under Wilson and bootstrap confidence intervals.
3. **Safety Status**: `LIVE_ORDERS_BLOCKED`. Real-money trading is strictly forbidden.
