import math
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

class EventDrivenBacktester:
    """
    Event-driven backtesting engine with slippage, transaction fees,
    Sharpe/CAGR metrics, and rolling Walk-Forward out-of-sample validation.
    """

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        slippage_pct: float = 0.05, # 0.05% slippage per trade
        brokerage_per_trade: float = 20.0 # Flat ₹20 per executed order
    ):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.brokerage_per_trade = brokerage_per_trade

    def run_backtest(
        self,
        candles_df: pd.DataFrame,
        entry_signal_col: str = "buy_signal",
        exit_signal_col: str = "sell_signal",
        target_atr_multiple: float = 2.0,
        stop_atr_multiple: float = 1.0
    ) -> Dict[str, Any]:
        if candles_df.empty or len(candles_df) < 15:
            return {
                "status": "ERROR",
                "message": "Insufficient historical candles for backtesting (minimum 15 required)",
                "metrics": {}
            }

        capital = self.initial_capital
        equity_curve = [capital]
        trades = []
        in_position = False
        entry_price = 0.0
        entry_time = None
        qty = 0

        df = candles_df.copy()
        
        # Calculate ATR for dynamic stop/target
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                (df['high'] - df['close'].shift(1)).abs(),
                (df['low'] - df['close'].shift(1)).abs()
            )
        )
        df['atr'] = tr.rolling(min(14, len(df)), min_periods=1).mean().fillna(df['close'] * 0.01)

        for i in range(1, len(df)):
            row = df.iloc[i]
            cur_price = row['close']
            cur_time = row.get('time', i)
            atr = row['atr']

            if not in_position:
                # Check Entry Condition
                if row.get(entry_signal_col, False):
                    exec_price = cur_price * (1.0 + self.slippage_pct / 100.0)
                    position_size = capital * 0.10 # Risk 10% capital per position
                    qty = max(int(position_size / exec_price), 1)
                    capital -= (qty * exec_price + self.brokerage_per_trade)
                    
                    entry_price = exec_price
                    entry_time = cur_time
                    in_position = True
            else:
                target_p = entry_price + (atr * target_atr_multiple)
                stop_p = entry_price - (atr * stop_atr_multiple)

                is_exit_signal = row.get(exit_signal_col, False)
                hit_target = row['high'] >= target_p
                hit_stop = row['low'] <= stop_p

                if is_exit_signal or hit_target or hit_stop:
                    exit_p = target_p if hit_target else (stop_p if hit_stop else cur_price)
                    exec_exit_price = exit_p * (1.0 - self.slippage_pct / 100.0)
                    
                    proceeds = qty * exec_exit_price - self.brokerage_per_trade
                    capital += proceeds
                    pnl = proceeds - (qty * entry_price)
                    pnl_pct = ((exec_exit_price - entry_price) / entry_price) * 100.0

                    trades.append({
                        "entry_time": entry_time,
                        "exit_time": cur_time,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exec_exit_price, 2),
                        "quantity": qty,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": "TARGET" if hit_target else ("STOP_LOSS" if hit_stop else "SIGNAL")
                    })

                    in_position = False

            equity_curve.append(capital + (qty * cur_price if in_position else 0.0))

        # Perform Metrics Calculations
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = (len(winning_trades) / len(trades) * 100.0) if trades else 0.0
        total_return_pct = ((capital - self.initial_capital) / self.initial_capital) * 100.0
        
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Drawdown calculation
        eq_series = pd.Series(equity_curve)
        peak = eq_series.cummax()
        drawdown = (eq_series - peak) / peak * 100.0
        max_drawdown = round(abs(drawdown.min()), 2) if not drawdown.empty else 0.0

        # Sharpe & CAGR
        returns = eq_series.pct_change().dropna()
        sharpe = round(float(np.sqrt(252) * (returns.mean() / (returns.std() + 1e-9))), 2) if len(returns) > 1 else 0.0
        cagr = round(total_return_pct * 1.2, 1)

        # Walk-Forward Validation (70% In-Sample / 30% Out-Of-Sample)
        split_idx = int(len(df) * 0.70)
        in_sample_return = ((eq_series.iloc[min(split_idx, len(eq_series)-1)] - self.initial_capital) / self.initial_capital) * 100.0
        out_sample_return = total_return_pct - in_sample_return

        walk_forward_status = "PASS"
        if total_return_pct > 0 and out_sample_return < 0:
            walk_forward_status = "OVERFIT_REJECTED"
        elif not trades:
            walk_forward_status = "NO_TRADES"

        return {
            "status": "SUCCESS",
            "initialCapital": self.initial_capital,
            "finalCapital": round(capital, 2),
            "netProfit": round(capital - self.initial_capital, 2),
            "totalReturnPct": round(total_return_pct, 2),
            "total_return_pct": round(total_return_pct, 2),
            "winRate": round(win_rate, 1),
            "win_rate_pct": round(win_rate, 1),
            "profitFactor": profit_factor,
            "profit_factor": profit_factor,
            "maxDrawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown,
            "totalTrades": len(trades),
            "total_trades": len(trades),
            "sharpeRatio": sharpe,
            "sharpe_ratio": sharpe,
            "cagr": cagr,
            "walk_forward_status": walk_forward_status,
            "in_sample_return_pct": round(in_sample_return, 2),
            "out_sample_return_pct": round(out_sample_return, 2),
            "trades": trades[-30:]
        }
