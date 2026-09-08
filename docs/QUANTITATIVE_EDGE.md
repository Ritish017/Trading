# APEX QUANT LAB: QUANTITATIVE EDGE & EMPIRICAL METHODOLOGY

## 1. Executive Summary & Epistemic Stance
In algorithmic finance and quantitative trading, an "edge" represents a statistically persistent, economically sound expectancy of return after accounting for market friction (slippage, transaction costs, liquidity constraints, and funding costs). 

Under the **APEX Anti-Cheating & Quantitative Certification Standards**, quantitative edge is **never assumed, asserted by heuristic design, or fabricated via backtest curve-fitting**. Heuristic models produce *opportunity scores*, not calibrated probabilities. A strategy or signal combination only earns the classification of a genuine edge when:
1. It is supported by an underlying economic mechanism (e.g., structural liquidity imbalances, volatility risk premia, systematic momentum).
2. It demonstrates positive statistical expectancy ($E[R] > 0$) strictly out-of-sample (OOS).
3. It survives realistic statutory and broker friction (STT, GST, stamp duty, exchange turnover, slippage).
4. Its confidence estimates are empirically calibrated ($P(\text{Win} \mid \text{Confidence} = c) \approx c$).

---

## 2. Quantitative Architecture: The Multi-Layer Filter
APEX decomposes the search for edge into orthogonal, independent analytical dimensions:

```
[ Authentic Market Data ]
            │
            ▼
[ 17-Stage Validation Gates ] ──(Fail)──► [ REJECT / NO TRADE ]
            │
            ▼
[ Market Regime Conditioning ] (Bull/Bear/Sideways/HighVol/LowVol)
            │
            ▼
[ Multi-Timeframe Feature Matrix ] (Higher TF Context + Primary Setup + Lower TF Trigger)
            │
            ▼
[ 20 Independent Strategies ] (Trend, Mean-Reversion, Breakout, Volatility, Institutional Flow)
            │
            ▼
[ Correlation Discount Confluence ] (Downweights correlated signals within clusters)
            │
            ▼
[ Heuristic Scoring & Grading ] (A+, A, B, C opportunity buckets)
            │
            ▼
[ Capital Allocation & Sizing ] (1% Portfolio Risk Ceiling, Fractional Kelly & Volatility Scale)
            │
            ▼
[ Derivatives Dispatcher ]
     ├─ Equity Spot / Intraday
     ├─ Futures Engine (Basis, Rollover, OI Buildup)
     └─ Options Engine (Black-Scholes Greeks, IV/HV spread, Vertical Spreads)
            │
            ▼
[ Paper Execution & Lifecycle Engine ]
            │
            ▼
[ Post-Trade Outcome & Calibration Tracking ] (MAE, MFE, Realized R, Net P&L)
```

---

## 3. The 5 Analytical Strategy Families & Correlation Clustering
Counting collinear indicators as multiple confirmations introduces severe look-alike bias (e.g., EMA crossover + MACD + SMA slope are essentially the same trend factor). APEX enforces **Correlation-Aware Confluence**:

| Family ID | Description | Core Economic Hypothesis | Strategies | Redundancy Penalty |
| :--- | :--- | :--- | :--- | :--- |
| **FAM_TREND** | Trend Following | Capital persistence & institutional accumulation drive directional drift. | `trend_following`, `moving_average_crossover`, `ichimoku_cloud`, `supertrend`, `parabolic_sar` | 0.65 correlation discount factor across internal pair-votes |
| **FAM_MOMENTUM** | Momentum & Oscillators | Time-series momentum and overextension reversion. | `rsi_reversal`, `stochastic_oscillator`, `williams_r`, `macd_divergence`, `rate_of_change` | 0.60 correlation discount factor |
| **FAM_BREAKOUT** | Volatility & Range Breakouts | Compression of volatility precedes explosive institutional expansion. | `bollinger_breakout`, `donchian_breakout`, `keltner_channel`, `range_breakout`, `opening_range_breakout` | 0.70 correlation discount factor |
| **FAM_VOLUME** | Volume & Flow Profile | Volume precedes price; institutional order flow cannot hide in volume. | `volume_profile`, `vwap_cross`, `obv_trend`, `chaikin_money_flow` | 0.75 correlation discount factor |
| **FAM_VOLATILITY**| Mean Reversion / Squeeze | Asset prices exhibit mean-reverting tendencies within bounded volatility bands. | `mean_reversion`, `squeeze_momentum` | 0.65 correlation discount factor |

### Confluence Formulation
Confluence is computed using family-diversity bonuses rather than raw strategy vote counts:
$$S_{\text{confluence}} = \sum_{f \in \text{Families}} \left( w_f \cdot \max_{s \in f} (\text{vote}_s) + \sum_{s \in f \setminus \{s^*\}} \rho_{f} \cdot \text{vote}_s \right)$$
where $\rho_f < 1.0$ downweights collinear confirmation within the same family.

---

## 4. Market Regime Conditioning
A strategy's edge is non-stationary; strategies optimized for trending regimes suffer severe capital destruction in mean-reverting or high-volatility sideways regimes.
APEX classifies market state into 5 regimes using ATR, ADX, and long-term moving average slopes:
1. **BULL_TRENDING**: Trend strategies given 1.25x weight; short breakouts penalized.
2. **BEAR_TRENDING**: Short trend and momentum breakdowns given 1.25x weight.
3. **SIDEWAYS_RANGE**: Mean-reversion and Bollinger band bounces given 1.30x weight; trend-following signals throttled.
4. **HIGH_VOLATILITY**: Position sizes scaled inversely to ATR; stop-loss distances widened; strict risk ceiling.
5. **LOW_VOLATILITY_COMPRESSION**: Breakout strategies primed; mean reversion suppressed anticipating regime transition.

---

## 5. Opportunity Score vs. Empirical Calibration
A critical flaw in standard algorithmic systems is confusing heuristic scores ($0 \dots 100$) with probabilistic win rates ($P(\text{Win})$). 

### Heuristic Scoring Engine
The APEX Opportunity Score is a weighted index:
$$\text{Score} = w_s S_{\text{strategy}} + w_m S_{\text{mtf}} + w_r S_{\text{regime}} + w_v S_{\text{volume}} + w_{rr} S_{\text{rr}} - P_{\text{risk}}$$
- Score $\ge 80 \implies$ Grade **A+**
- Score $\ge 70 \implies$ Grade **A**
- Score $\ge 60 \implies$ Grade **B**
- Score $< 60 \implies$ Grade **C** (Rejection threshold)

### Empirical Probability Calibration
APEX isolates heuristic confidence into an explicit `IS_HEURISTIC` category until $N \ge 30$ historical forward outcomes are recorded in durable persistence. Calibration is monitored across 5 bins:
- `BIN_50_60`: Heuristic confidence $[50\%, 60\%)$
- `BIN_60_70`: Heuristic confidence $[60\%, 70\%)$
- `BIN_70_80`: Heuristic confidence $[70\%, 80\%)$
- `BIN_80_90`: Heuristic confidence $[80\%, 90\%)$
- `BIN_90_100`: Heuristic confidence $[90\%, 100\%]$

**Expected Calibration Error (ECE)** is calculated as:
$$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$
If $\text{ECE} > 0.15$, the calibration engine flags the model as `MISCALIBRATED` and forces confidence downscaling before position sizing.

---

## 6. Friction & Transaction Drag
Gross paper profits routinely evaporate in production due to statutory charges and bid-ask slippage. APEX builds in the comprehensive Indian statutory schedule via `TransactionCostCalculator`:
- **Brokerage**: Flat ₹20 per executed order or 0.05% (whichever is lower).
- **STT (Securities Transaction Tax)**:
  - Equity Delivery: 0.1% both sides.
  - Equity Intraday: 0.025% sell side.
  - Futures: 0.02% sell side.
  - Options: 0.125% on intrinsic value/premium (sell side).
- **Exchange Turnover Charges**: NSE ₹3.25 per ₹100,000 turnover.
- **GST**: 18% on (Brokerage + Exchange Charges + SEBI Turnover Charges).
- **SEBI Turnover Charges**: ₹10 per crore.
- **Stamp Duty**: 0.003% (equity intraday) / 0.002% (futures) / 0.003% (options).
- **Modeled Slippage**:
  - Equity Liquid: 0.05%
  - Equity Mid-cap: 0.10%
  - Futures: 0.02%
  - Options: 0.50% of premium or 1 tick.

---

## 7. Out-Of-Sample Walk-Forward & Overfitting Protection
APEX explicitly forbids full-sample optimization. The walk-forward framework partitions data into:
$$\text{Total Window} = \text{Train Window } (60\%) + \text{Validation Window } (20\%) + \text{Out-of-Sample Window } (20\%)$$
- **Deflated Sharpe Ratio (DSR)** and **Haircut Sharpe Ratios** are applied to discount for selection bias when testing multiple strategy parameters.
- **Parameter Sensitivity Stress**: Key parameters ($\pm 10\%, \pm 20\%$) are tested. If small parameter shifts cause expectancy to collapse from positive to negative, the strategy is marked `ROBUSTNESS_FAILED` and denied live execution.

---

## 8. Current Certification Status: Honest Disclosure
1. **Strategy Logic**: Verified deterministic dual-directional (`LONG`, `SHORT`, `NEUTRAL`) across all 20 strategies with zero lookahead bias.
2. **Infrastructure**: Fully persistent via PostgreSQL/SQLite, state-machine validated, transaction cost aware.
3. **Empirical Edge Status**: `PASS_WITH_LIMITATION`. While the pipeline, risk limits, and math engines are fully verified, an empirical edge can only be certified after gathering a statistically significant sample size ($N \ge 250$ live recorded authentic trades) under live Indian market trading hours. APEX strictly refuses to claim positive profitability on synthetic data.
