# APEX Options Intelligence Engine (`OPTIONS_ENGINE.md`)

## 1. Overview

The APEX Options Engine implements closed-form Black-Scholes analytics, full Greeks calculation (Delta, Gamma, Theta, Vega), liquid strike selection, and multi-leg spread structures.

Supported Options Decisions:
- `BUY_CALL`
- `BUY_PUT`
- `SELL_CALL`
- `SELL_PUT`
- `BULL_CALL_SPREAD` (Vertical Debit Spread)
- `BEAR_PUT_SPREAD` (Vertical Debit Spread)
- `NO_TRADE`
- `OPTIONS_DATA_INSUFFICIENT`

---

## 2. Quantitative Architecture

### 1. Black-Scholes & Greeks Computation
- **Delta ($\Delta$)**: First derivative of option price with respect to underlying price.
  - Call $\Delta = N(d_1)$
  - Put $\Delta = N(d_1) - 1$
- **Gamma ($\Gamma$)**: Second derivative of option price with respect to underlying price: $\Gamma = \frac{N'(d_1)}{S \sigma \sqrt{T}}$.
- **Theta ($\Theta$)**: Time decay in INR points per day.
- **Vega ($\nu$)**: Sensitivity of option price to a 1% change in implied volatility.

### 2. Contract Selection Policy
Rather than defaulting blindly to At-The-Money (ATM), the contract selection policy optimizes:
1. **Moneyness & Delta Target**:
   - Outright Long Call: Targets Slightly OTM or ATM with Delta between $0.45$ and $0.60$.
   - Outright Long Put: Targets Delta between $-0.45$ and $-0.60$.
2. **Liquidity Hard Gate**:
   - Bid-Ask Spread: $(Ask - Bid) / Mid \le 4.0\%$. Rejects wide spreads.
   - Minimum Volume: $\ge 200$ contracts.
   - Minimum Open Interest: $\ge 500$ contracts.
3. **Volatility Environment & Spread Selection**:
   - If Implied Volatility Percentile (IVP) > 65% or DTE is short (< 7 days), outright long option buying suffers severe Theta decay.
   - In high-IV or short-DTE regimes, the engine recommends a **Vertical Debit Spread** (e.g. Bull Call Spread: Buy ATM Call + Sell OTM Call) to cap volatility crush and finance time decay.

### 3. Vertical Spread Payoff Analysis
For a Bull Call Spread ($K_1 < K_2$):
- Net Debit = $Premium_{K_1} - Premium_{K_2}$
- Maximum Loss = $NetDebit$
- Maximum Gain = $(K_2 - K_1) - NetDebit$
- Breakeven = $K_1 + NetDebit$
- Risk:Reward Ratio = $\frac{MaxGain}{MaxLoss}$

### 4. Fail-Closed Invariant
If option chain data is empty, missing, or corrupt, the engine strictly outputs `OPTIONS_DATA_INSUFFICIENT` rather than fabricating simulated strikes or theoretical prices.
