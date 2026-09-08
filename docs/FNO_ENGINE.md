# APEX Futures Decision Engine (`FNO_ENGINE.md`)

## 1. Overview

The APEX Futures Engine evaluates underlying directional opportunities against futures market microstructure. It guarantees that equity signals are never blindly converted into futures trades without rigorous validation of basis risk, liquidity, and open interest dynamics.

Supported Futures Decisions:
- `BUY_FUTURE`: High-conviction long underlying signal + healthy basis + strong OI buildup + adequate market liquidity.
- `SELL_FUTURE`: High-conviction short underlying signal + negative/neutral basis + short buildup/long unwinding + adequate liquidity.
- `NO_TRADE`: Fails any basis, liquidity, margin, or rollover filter.

---

## 2. Futures Validation Gates

### 1. Liquidity & Volume Gates
- Minimum Volume: 50 lots traded in current session.
- Minimum Open Interest: 1,000 lots outstanding.
- If volume or OI falls below these thresholds, the engine immediately outputs `NO_TRADE` with reason `FUTURES_LIQUIDITY_INSUFFICIENT`.

### 2. Basis & Cost-of-Carry Filter
- Basis is defined as $Basis = FuturesPrice - SpotPrice$.
- Basis % is defined as $Basis\% = \frac{Basis}{SpotPrice} \times 100$.
- For `BUY_FUTURE`: If Basis % > +2.5%, the contract is over-extended in premium; flagged or rejected as expensive.
- For `SELL_FUTURE`: If Basis % < -2.5%, the contract trades at deep discount; shorting carries mean-reversion basis risk.

### 3. Rollover & Expiry Protection
- If Days to Expiry (DTE) $\le 2$, trading the near-month contract incurs extreme rollover pressure and margin delivery spikes.
- The engine rejects near-month contracts within 2 DTE or recommends the next-month contract.

### 4. Open Interest (OI) Patterns
The engine classifies market activity into 4 canonical quadrants:
- **Long Buildup**: Price Up + OI Up $\rightarrow$ Confirms Bullish continuation.
- **Short Buildup**: Price Down + OI Up $\rightarrow$ Confirms Bearish continuation.
- **Short Covering**: Price Up + OI Down $\rightarrow$ Weak/temporary bounce; caution on aggressive longs.
- **Long Unwinding**: Price Down + OI Down $\rightarrow$ Exhaustion selloff; caution on aggressive shorts.

### 5. Position Sizing & Margin Invariants
- Minimum allocation is 1 lot (e.g. 250 shares for Nifty/stock future).
- Lot size is non-fractional; total quantity is strictly $Lots \times LotSize$.
- Margin required = $Lots \times MarginPerLot$. Must not exceed available capital.
