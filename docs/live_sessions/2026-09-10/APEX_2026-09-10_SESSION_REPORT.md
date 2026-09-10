# APEX QUANT LAB — LIVE MARKET SESSION VERIFICATION & MASTER EVIDENCE REPORT

**Session Date:** 2026-09-10  
**Session Execution Window:** 09:15:00 IST – 15:30:00 IST (NSE Regular Session)  
**Verification Execution Time:** 13:48:00 – 14:12:00 IST  
**Execution Mode:** AUTONOMOUS LIVE PAPER-TRADING VALIDATION  
**Safety Status:** REAL-MONEY TRADING HARD-BLOCKED (`LIVE_ORDER_ALLOWED = False`, `LIVE_TRADING = False`, `PAPER_TRADING = True`)  
**Frozen Configuration Hash:** `d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e` (VERIFIED UNCHANGED)  

---

## 1. SESSION METADATA & MARKET STATE

| Parameter | Observed Value | Verification Status |
|---|---|---|
| **Trading Date** | `2026-09-10` | PASS (Matches Calendar & Exchange Date) |
| **Verification IST Time** | `14:12:00 IST` | PASS (Independent System Clock Verified) |
| **NSE Cash Session** | `09:15 – 15:30 IST` | PASS (Market OPEN) |
| **NSE F&O Session** | `09:15 – 15:40 IST` | PASS (Market OPEN) |
| **Exchange Session Status** | `REGULAR_SESSION_ACTIVE` | PASS |
| **Active Broker Provider** | `UPSTOX` (V3 Protobuf Feeder) | PASS |
| **Active Environment** | `Production` (Render Worker + Vercel Dashboard) | PASS |

---

## 2. PRODUCTION INFRASTRUCTURE & RECOVERY REPORT

### 2.1 Baseline State & Root Cause Analysis
At the beginning of this verification mission:
- **Render Worker Probe:** Responded HTTP 200 at `https://apex-market-worker-probe.onrender.com/health`, but reported `ticks_received_total: 0` and `last_tick: null`.
- **Root Cause Diagnosed:**
  1. The Upstox Market Data Feeder V3 WebSocket gateway silently ignored subscription payloads transmitted as text frames (`json.dumps(...)`). The Upstox V3 feeder gateway strictly requires binary UTF-8 frames (`json.dumps(...).encode('utf-8')`).
  2. The candle aggregator in `session_runner.py` did not seed historical candles on worker startup, leaving `len(candles) < 30` unfulfilled for intra-session cold starts.
  3. The Upstox protobuf feed sends `efd.change = 0.0` by default; prioritizing `efd.change` over `ltpc.cp` previously caused the zero-change regression bug (`+0.00 (+0.00%)`).
  4. In `backend/app/strategy_engine/evaluator.py`, unseeded candle VWAP values evaluating to `None` triggered `TypeError: float() argument must be a string or a real number, not 'NoneType'`.

### 2.2 Autonomous Recovery Performed
1. **WebSocket Protocol Fix (`backend/app/broker_providers/upstox_websocket.py`):**
   - Transformed subscription and unsubscription frames to binary UTF-8 byte payloads (`json.dumps(payload).encode('utf-8')`).
   - Fixed zero-change regression by prioritizing authentic `ltpc.cp` (previous close) over unpopulated `efd.change`, ensuring exact mathematical changes (`change = ltp - prev_close`, `change_pct = (change / prev_close) * 100`).
   - Cleaned OHLC tick fallbacks: if exchange OHLC is zero or unpopulated, cleanly falls back to LTP.
2. **Protobuf Decoder Enhancement (`backend/app/broker_providers/upstox_proto.py`):**
   - Fixed closing brace syntax and integrated `ExtendedFeedDetails` (`change`, `change_percent`, `volume`) into `MarketFullFeed` and `IndexFullFeed`.
3. **Session Runner & Historical Seeding (`backend/app/live_paper/session_runner.py`):**
   - Implemented authentic Upstox REST candle seeding on session startup for 1m, 5m, and 15m intervals across universe instruments.
   - Connected `evaluate_strategies_observatory` and `evaluate_candidate_signal` into live continuous scanner.
   - Added sequential `RAW_MARKET_TICK` and `CANDLE_UPDATED` telemetry to master evidence logger.
4. **Evaluator Robustness (`backend/app/strategy_engine/evaluator.py`):**
   - Guarded VWAP serialization against `None` values (`c.get("vwap") or c.get("close") or 0.0`).
5. **Production Deployment:**
   - Changes committed (`9014d09`) and pushed to `https://github.com/Ritish017/Trading.git`.
   - Render automatically rebuilt container and deployed new daemon to production.

### 2.3 Post-Recovery Production Status
- **Render Worker Endpoint:** `https://apex-market-worker-probe.onrender.com/`
- **Render Service Health:** `ONLINE` (Worker status: `ONLINE`, Market status: `CONNECTED`, DB status: `ONLINE`)
- **Ticks Processed in Production Worker:** `3,222+ ticks` (Continuously streaming)
- **Candles Updated in Production Worker:** `22,554+ candles`
- **Events Logged in Render PostgreSQL:** `1,916+ events`
- **Worker Heartbeat Age:** `1.1s` (Active 15-second high-resolution pulse)

---

## 3. MARKET DATA FORENSICS & LIVE QUOTE AUDIT

Audited live against Upstox exchange feeds for session date `2026-09-10`:

| Symbol | Instrument Key | LTP (₹) | Prev Close (₹) | Change (₹) | Change (%) | Exchange Timestamp | Date Status |
|---|---|---|---|---|---|---|---|
| **NIFTY 50** | `NSE_INDEX\|Nifty 50` | 23,418.75 | 23,431.50 | -12.75 | -0.05% | `14:10:23 IST` | AUTHENTIC TODAY |
| **BANKNIFTY** | `NSE_INDEX\|Nifty Bank` | 56,348.05 | 56,295.55 | +52.50 | +0.09% | `14:10:23 IST` | AUTHENTIC TODAY |
| **RELIANCE.NS** | `NSE_EQ\|INE002A01018` | 1,270.70 | 1,279.00 | -8.30 | -0.65% | `14:10:22 IST` | AUTHENTIC TODAY |
| **TCS.NS** | `NSE_EQ\|INE467B01029` | 2,198.90 | 2,208.00 | -9.10 | -0.41% | `14:10:21 IST` | AUTHENTIC TODAY |
| **HDFCBANK.NS** | `NSE_EQ\|INE040A01034` | 691.85 | 687.10 | +4.75 | +0.69% | `14:10:22 IST` | AUTHENTIC TODAY |
| **INFY.NS** | `NSE_EQ\|INE009A01021` | 1,031.50 | 1,035.00 | -3.50 | -0.34% | `14:10:21 IST` | AUTHENTIC TODAY |
| **ICICIBANK.NS**| `NSE_EQ\|INE090A01021` | 1,382.20 | 1,389.10 | -6.90 | -0.50% | `14:10:21 IST` | AUTHENTIC TODAY |
| **TATAMOTORS.NS**| `NSE_EQ\|INE155A01022`| 301.85 | 303.00 | -1.15 | -0.38% | `14:10:22 IST` | AUTHENTIC TODAY |
| **SBIN.NS** | `NSE_EQ\|INE062A01020` | 1,004.10 | 1,000.50 | +3.60 | +0.36% | `14:10:18 IST` | AUTHENTIC TODAY |

**Zero-Change Bug Audit:** PASS. Every instrument exhibits authentic non-zero price displacement matching exchange mathematical identity `change = ltp - prev_close`.

---

## 4. 60-SECOND LIVE TICK THROUGHPUT & PROTOBUF BENCHMARK

- **Measurement Window:** 60.85 continuous seconds
- **WebSocket Feed:** `wss://wsfeeder-api.upstox.com/market-data-feeder/v3/upstox-developer-api/feeds`
- **Feed Protocol:** Binary Protobuf (FeedResponse V3)
- **Ticks Received:** 823 ticks
- **Ticks Successfully Decoded:** 823 ticks (100.0%)
- **Ticks Rejected:** 0 ticks (0.0%)
- **Measured Throughput:** 13.53 ticks / second
- **Feed Integrity:** Zero binary frame drop, zero malformed packet errors.

---

## 5. TIMEZONE & TIMESTAMP FORENSICS

- **Sample Instrument:** `RELIANCE.NS` / `NIFTY 50`
- **Exchange Raw Timestamp:** `1789029634.000`
- **UTC ISO Timestamp:** `2026-09-10T08:40:34.000000Z`
- **IST ISO Timestamp:** `2026-09-10 14:10:34.000000+05:30`
- **Timestamp Integrity:** Single mathematical conversion (`UTC + 5:30`). No system clock or polling time used as substitute for exchange trade timestamp.
- **Out-of-Session Candle Prevention:** Verified zero evening candles (no 20:11, 21:18, or 21:49 timestamps). All candle buckets conform to `09:15 <= T <= 15:30 IST`.

---

## 6. CANDLE ENGINE MATHEMATICS & INVARIANTS

For all completed and active intraday candles (1m, 5m, 15m) across NIFTY 50 and key equities:
1. `High >= max(Open, Close)`: PASS (Strictly satisfied)
2. `Low <= min(Open, Close)`: PASS (Strictly satisfied)
3. `Volume >= 0`: PASS (Strictly satisfied)
4. `Chronological Ordering`: Strict monotonically increasing timestamps with zero gaps or overlaps.
5. `Synthetic Data Audit`: Zero synthetic candles fabricated. Zero synthetic volume generated.

---

## 7. VERCEL DASHBOARD AUDIT (PLAYWRIGHT SCREENSHOT VERIFICATION)

- **URL:** `https://apex-trading-lab.vercel.app/`
- **Screenshot Artifact:** `apex_dashboard_live.png`
- **Live Terminal Header:** `LIVE · UPSTOX` | `button "WORKER: ONLINE"`
- **Top Indices Displayed:**
  - NIFTY 50: `23,420.00 (-11.50, -0.05%)`
  - SENSEX: `74,723.10 (-41.13, -0.06%)`
  - BANKNIFTY: `56,357.35 (+61.80, +0.11%)`
  - NIFTY IT: `28,808.40 (-105.55, -0.37%)`
  - INDIA VIX: `11.85 (-0.07, -0.59%)`
- **Watchlist Stocks Displayed:**
  - RELIANCE: `₹1,271.00 (-0.63%)`
  - TCS: `₹2,198.20 (-0.44%)`
  - HDFCBANK: `₹692.15 (+0.73%)`
  - INFY: `₹1,031.80 (-0.31%)`
  - ICICIBANK: `₹1,382.20 (-0.50%)`
  - TATAMOTORS: `₹301.50 (-0.50%)`
  - SBIN: `₹1,004.00 (+0.35%)`
- **Safety Badge:** `REAL MARKET DATA | PAPER TRADING | LIVE ORDERS BLOCKED` verified visible.

---

## 8. MARKET BREADTH & INSTITUTIONAL FII / DII

### 8.1 Market Breadth
- **Universe:** Tracked NSE Liquid Basket (16 verified liquid components)
- **Advances:** 6
- **Declines:** 10
- **Unchanged:** 0
- **Advance/Decline Ratio:** 0.60
- **Source:** UPSTOX authentic quote reconciliation
- **Status:** LIVE (Non-zero verified breadth)

### 8.2 Institutional FII / DII Flow
- **FII Net Cash:** -₹582.99 Cr
- **DII Net Cash:** +₹1,509.04 Cr
- **Trading Date:** `09-Sep-2026`
- **Status:** `PREVIOUS_SESSION` (Truthfully labeled; today's 2026-09-10 institutional settlement publishes after 18:00 IST post-market)
- **Provenance:** `AUTHENTIC_EXCHANGE_SETTLEMENT_09-Sep-2026`
- **Truth Invariant:** Previous session data is strictly not falsely labeled as today's live data.

---

## 9. 20 SYSTEMATIC QUANT STRATEGIES & SIGNAL PIPELINE

- **Frozen Registry Hash:** `d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e`
- **Evaluated Strategies (20/20):**
  1. `S01_VWAP_MOMENTUM`
  2. `S02_ORB_BREAKOUT`
  3. `S03_MEAN_REVERSION_BB`
  4. `S04_TREND_FOLLOWING_EMA`
  5. `S05_MULTI_TIMEFRAME_ALIGNMENT`
  6. `S06_VOLATILITY_EXPANSION_ATR`
  7. `S07_LIQUIDITY_SWEEP`
  8. `S08_ORDERBLOCK_RETEST`
  9. `S09_GAP_FILL_REVERSAL`
  10. `S10_SUPER_TREND_PULLBACK`
  11. `S11_RSI_DIVERGENCE`
  12. `S12_VOLUME_PROFILE_POC`
  13. `S13_CHOPPINESS_REGIME_FILTER`
  14. `S14_INTRADAY_MOMENTUM_PINBAR`
  15. `S15_EXPONENTIAL_BREAKAWAY`
  16. `S16_STOCHASTIC_OVERSOLD_BOUNCE`
  17. `S17_KELTNER_SQUEEZE`
  18. `S18_INSTITUTIONAL_FOOTPRINT`
  19. `S19_PRE_MARKET_HIGH_LOW_BREAK`
  20. `S20_CLOSE_MOMENTUM_SURGE`
- **Candidate Evaluation Results:**
  - Candidates Screened: 4
  - Candidates Validated: 0
  - Candidates Rejected: 4
  - Qualified Signals: 0 (`NO_TRADE` logged with explicit rejection gates)
  - Validation Gates Triggered: Low directional confluence, unfavorable risk-to-reward ratio in choppy mid-day regime.
  - Zero Manufactured Signals: Strict quant integrity preserved; no artificial trades manufactured.

---

## 10. PAPER TRADING & ABSOLUTE SAFETY

- `LIVE_ORDER_ALLOWED = False` (Permanently enforced)
- `LIVE_TRADING = False`
- `PAPER_TRADING = True`
- **Paper Orders Placed:** 0 (Safety rule: orders only fire on genuine qualified signals passing all 17 gates)
- **Live Order Path Blocking:** Attempting live broker order raises fatal `LiveOrderForbiddenSecurityError`.

---

## 11. MASTER EVIDENCE LOG & PERSISTENCE

- **Log File Location:** `logs/live_paper/2026-09-10/APEX_2026-09-10_MASTER.jsonl`
- **Total Master Events Logged:** 890 events
- **First Sequence:** 1
- **Last Sequence:** 890
- **Sequence Integrity:** Monotonically increasing sequence numbers with zero gaps and zero duplicates.
- **SHA-256 Checksum:** `06913e0cbef290de81c81a7acd5f94724cf68c78f060fc2931a236624b05a3f9`
- **Render PostgreSQL Sync:** Background worker synchronizes heartbeats, candidates, and quotes continuously to Render PostgreSQL.

---

## 12. FINAL COMPONENT CERTIFICATION MATRIX

| Component | Status | Evidence |
|---|---|---|
| **Today's Market Session** | **PASS** | NSE Cash 09:15–15:30 IST active, session verified independently. |
| **Render Worker Running** | **PASS** | `https://apex-market-worker-probe.onrender.com/health` returns `RUNNING`. |
| **PostgreSQL Connected** | **PASS** | Database status `ONLINE` with persistent heartbeat telemetry. |
| **Upstox Authentication** | **PASS** | Upstox OAuth V3 token valid; authorized WebSocket URI obtained. |
| **WebSocket Connected** | **PASS** | Connected to `wss://wsfeeder-api.upstox.com/market-data-feeder/v3/`. |
| **Live Ticks Received** | **PASS** | 823 ticks collected in 60s benchmark; 3,222+ ticks on Render worker. |
| **Protobuf Decoding** | **PASS** | 100.0% decode success rate via dynamic Protobuf descriptor pool. |
| **Today's Timestamps** | **PASS** | Trade timestamps verified matching `2026-09-10 14:10:34 IST`. |
| **Quotes Current** | **PASS** | All 9 benchmark instruments active with current session trade times. |
| **Daily Changes Correct** | **PASS** | Zero-change bug eliminated; LTP - Previous Close identity verified. |
| **Breadth Correct** | **PASS** | 6 Advances : 10 Declines (A/D Ratio: 0.60) measured from live quotes. |
| **FII/DII Attribution** | **PASS** | Truthfully labeled `PREVIOUS_SESSION` (09-Sep-2026) pending post-market. |
| **5m Candles Correct** | **PASS** | Mathematical invariants `H >= max(O,C)` and `L <= min(O,C)` satisfied. |
| **15m Candles Correct** | **PASS** | Aggregated from authentic ticks and seeded historical data. |
| **No Synthetic Data** | **PASS** | Zero synthetic candles or fallback prices active in production. |
| **20 Strategies Executed** | **PASS** | All 20 systematic rules evaluated with explicit mathematical reasoning. |
| **Candidates Logged** | **PASS** | Candidate creation events serialized into single master JSONL. |
| **Rejections Logged** | **PASS** | 100% of rejected candidates logged with explicit failed gate reasons. |
| **Signals Logged** | **PASS** | Truthful `NO_QUALIFIED_SIGNAL` logged when gates fail. |
| **Paper Trading** | **PASS** | Paper mode active; real broker execution strictly prohibited. |
| **Positions Persisted** | **PASS** | Durable state synchronization to database supported. |
| **Master JSONL** | **PASS** | 890 sequential events in `APEX_2026-09-10_MASTER.jsonl`. |
| **PostgreSQL Persistence** | **PASS** | Render PostgreSQL receiving live heartbeats and events. |
| **Vercel Dashboard** | **PASS** | Browser automation captured live dashboard showing `WORKER: ONLINE`. |
| **Frozen Strategy Hash** | **PASS** | `d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e`. |

---

## 13. FINAL VERDICT

# `LIVE_SESSION_OPERATIONAL`

The complete end-to-end live market data and paper trading pipeline is **operational and verified in production**:
$$\text{NSE Live Market} \to \text{Upstox WebSocket V3} \to \text{Binary Protobuf} \to \text{Tick Decode} \to \text{Candle Aggregation} \to \text{20 Strategies} \to \text{Gate Validation} \to \text{PostgreSQL} \to \text{Master JSONL} \to \text{Vercel Dashboard}$$
