# EVENT-DRIVEN BACKTESTING & WALK-FORWARD TESTING SPECIFICATION

## 1. Backtesting Engine Design

The APEX backtesting engine (`backend/app/backtesting/event_driven.py`) executes bar-by-bar simulations avoiding look-ahead bias.

## 2. Friction & Realism Parameters

- **Slippage**: 0.05% per executed order.
- **Brokerage**: Flat ₹20.00 per trade.
- **Position Sizing**: Configurable percentage of active equity capital (default 10%).

## 3. Walk-Forward & Out-of-Sample Validation

To combat curve fitting and over-optimization, APEX enforces a 70/30 split:
1. **In-Sample Data (70%)**: Parameter optimization and signal generation.
2. **Out-of-Sample Data (30%)**: Unseen forward validation.

If out-of-sample performance collapses while in-sample performance was positive:
```
STATUS = OVERFIT_REJECTED
```

## 4. Evaluated Performance Metrics

- Total Return (%)
- Win Rate (%)
- Profit Factor (Gross Profit / Gross Loss)
- Maximum Drawdown (%)
- In-Sample vs. Out-of-Sample Return Comparison
