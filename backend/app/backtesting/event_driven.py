import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import pandas as pd
import numpy as np


@dataclass
class StrategyHypothesis:
    """
    Explicit Backtestable Trading Hypothesis.
    A strategy activation is strictly NOT a trade without an explicit hypothesis.
    """
    strategy_id: str
    strategy_version: str = "1.0.0"
    symbol: str = "UNKNOWN"
    timeframe: str = "5m"
    direction: str = "BULLISH" # BULLISH | BEARISH | BOTH
    initial_capital: float = 1000000.0 # Default ₹10,00,000
    position_sizing_model: str = "PERCENT_CAPITAL" # PERCENT_CAPITAL | FIXED_QUANTITY | RISK_BASED
    position_size_value: float = 0.10 # 10% capital per position
    target_atr_multiple: float = 2.0
    stop_atr_multiple: float = 1.0
    max_holding_bars: Optional[int] = 50
    slippage_pct: float = 0.05 # 0.05% slippage per trade
    brokerage_per_trade: float = 20.0 # Flat ₹20 per trade (e.g. Upstox/Zerodha)
    walk_forward_split: float = 0.70 # 70% In-Sample / 30% Out-of-Sample

    def is_valid(self) -> Tuple[bool, Optional[str]]:
        if not self.strategy_id:
            return False, "HYPOTHESIS_INCOMPLETE: strategy_id is required"
        if self.initial_capital <= 0:
            return False, "HYPOTHESIS_INCOMPLETE: initial_capital must be > 0"
        if self.position_size_value <= 0:
            return False, "HYPOTHESIS_INCOMPLETE: position_size_value must be > 0"
        if self.target_atr_multiple <= 0 or self.stop_atr_multiple <= 0:
            return False, "HYPOTHESIS_INCOMPLETE: target and stop ATR multiples must be > 0"
        return True, None


@dataclass
class BacktestTradeEvidence:
    """
    Rich Trade-Level Evidence Retention.
    Allows inspecting WHY each simulated trade occurred.
    """
    trade_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    direction: str
    entry_index: int
    entry_time: Any
    entry_price: float
    exit_index: int
    exit_time: Any
    exit_price: float
    quantity: int
    gross_pnl: float
    gross_return_pct: float
    slippage_cost: float
    brokerage_cost: float
    total_costs: float
    net_pnl: float
    net_return_pct: float
    exit_reason: str # TARGET | STOP_LOSS | SIGNAL_INVAL | MAX_HOLD | EOD
    duration_bars: int
    regime_at_entry: str
    confluence_state: Dict[str, Any] = field(default_factory=dict)
    entry_rule_evidence: List[Dict[str, Any]] = field(default_factory=list)
    exit_rule_evidence: List[Dict[str, Any]] = field(default_factory=list)
    is_in_sample: bool = True


class EventDrivenBacktester:
    """
    Canonical Event-Driven Backtesting Engine with next-bar execution,
    rigorous transaction friction, full trade-level evidence,
    Walk-Forward Out-Of-Sample validation, and Overfitting classification.
    """

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        slippage_pct: float = 0.05,
        brokerage_per_trade: float = 20.0
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
        stop_atr_multiple: float = 1.0,
        hypothesis: Optional[StrategyHypothesis] = None,
        regimes_series: Optional[List[str]] = None,
        confluences_series: Optional[List[Dict[str, Any]]] = None,
        rule_evidence_series: Optional[List[List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes point-in-time event-driven simulation with strict next-bar execution.
        Signal on bar T close -> simulated entry occurs on bar T+1.
        """
        if candles_df.empty or len(candles_df) < 15:
            return {
                "status": "ERROR",
                "message": "DATA_UNAVAILABLE: Insufficient historical candles for backtesting (minimum 15 required)",
                "metrics": {}
            }

        # Check hypothesis validity if provided
        if hypothesis:
            is_valid, err_msg = hypothesis.is_valid()
            if not is_valid:
                return {
                    "status": "ERROR",
                    "message": err_msg,
                    "metrics": {}
                }
            cap = hypothesis.initial_capital
            slip_pct = hypothesis.slippage_pct
            brok = hypothesis.brokerage_per_trade
            pos_val = hypothesis.position_size_value
            tgt_atr = hypothesis.target_atr_multiple
            stp_atr = hypothesis.stop_atr_multiple
            strat_id = hypothesis.strategy_id
            strat_ver = hypothesis.strategy_version
            sym = hypothesis.symbol
            tf = hypothesis.timeframe
            direction = hypothesis.direction
            max_hold = hypothesis.max_holding_bars or 100
            wf_split = hypothesis.walk_forward_split
        else:
            cap = self.initial_capital
            slip_pct = self.slippage_pct
            brok = self.brokerage_per_trade
            pos_val = 0.10
            tgt_atr = target_atr_multiple
            stp_atr = stop_atr_multiple
            strat_id = "GENERIC_STRATEGY"
            strat_ver = "1.0.0"
            sym = "UNKNOWN"
            tf = "5m"
            direction = "BULLISH"
            max_hold = 100
            wf_split = 0.70

        capital = cap
        equity_curve = [capital]
        drawdown_curve = [0.0]
        trades: List[BacktestTradeEvidence] = []
        in_position = False
        entry_price = 0.0
        entry_time = None
        entry_idx = 0
        qty = 0
        bars_in_trade = 0
        entry_regime = "UNAVAILABLE"
        entry_confluence: Dict[str, Any] = {}
        entry_evidence: List[Dict[str, Any]] = []

        df = candles_df.copy().reset_index(drop=True)
        n_bars = len(df)
        split_bar_idx = int(n_bars * wf_split)

        # Calculate ATR for dynamic stop/target
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                (df['high'] - df['close'].shift(1)).abs(),
                (df['low'] - df['close'].shift(1)).abs()
            )
        )
        df['atr'] = tr.rolling(min(14, len(df)), min_periods=1).mean().shift(1).bfill().fillna(df['close'] * 0.01)

        # Pending entry signal from candle T to execute at candle T+1
        pending_entry = False
        pending_signal_regime = "UNAVAILABLE"
        pending_signal_confluence: Dict[str, Any] = {}
        pending_signal_evidence: List[Dict[str, Any]] = []

        for i in range(len(df)):
            row = df.iloc[i]
            cur_price = row['close']
            cur_open = row['open']
            cur_time = row.get('timestamp') or row.get('time') or i
            atr = max(float(row['atr']), cur_price * 0.005)

            # 1. Execute Pending Entry from previous bar's signal (Next-Bar Execution Invariant)
            if pending_entry and not in_position:
                # Enter at next bar's open price + slippage
                fill_price = cur_open if cur_open > 0 else cur_price
                if direction == "BEARISH":
                    exec_price = fill_price * (1.0 - slip_pct / 100.0)
                else:
                    exec_price = fill_price * (1.0 + slip_pct / 100.0)

                pos_capital = capital * pos_val
                qty = max(int(pos_capital / max(exec_price, 1.0)), 1)
                cost_of_entry = qty * exec_price + brok

                if capital >= cost_of_entry:
                    capital -= cost_of_entry
                    entry_price = exec_price
                    entry_time = cur_time
                    entry_idx = i
                    in_position = True
                    bars_in_trade = 0
                    entry_regime = pending_signal_regime
                    entry_confluence = pending_signal_confluence
                    entry_evidence = pending_signal_evidence

                pending_entry = False

            # 2. Manage Active Position
            if in_position:
                bars_in_trade += 1
                is_bullish = (direction == "BULLISH" or direction == "BOTH")

                if is_bullish:
                    target_p = entry_price + (atr * tgt_atr)
                    stop_p = entry_price - (atr * stp_atr)
                    hit_target = row['high'] >= target_p
                    hit_stop = row['low'] <= stop_p
                else:
                    target_p = entry_price - (atr * tgt_atr)
                    stop_p = entry_price + (atr * stp_atr)
                    hit_target = row['low'] <= target_p
                    hit_stop = row['high'] >= stop_p

                is_exit_signal = bool(row[exit_signal_col]) if exit_signal_col in row else False
                hit_max_hold = bars_in_trade >= max_hold
                is_last_bar = (i == n_bars - 1)

                if hit_target or hit_stop or is_exit_signal or hit_max_hold or is_last_bar:
                    # Conservative deterministic execution: if both target and stop touched on same bar, assume stop hit first
                    if hit_target and hit_stop:
                        exit_p = stop_p
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_p = stop_p
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_p = target_p
                        exit_reason = "TARGET"
                    elif is_exit_signal:
                        exit_p = cur_price
                        exit_reason = "SIGNAL_INVAL"
                    elif hit_max_hold:
                        exit_p = cur_price
                        exit_reason = "MAX_HOLD"
                    else:
                        exit_p = cur_price
                        exit_reason = "EOD"

                    # Calculate exit execution with slippage
                    if is_bullish:
                        exec_exit_price = exit_p * (1.0 - slip_pct / 100.0)
                        gross_pnl = qty * (exec_exit_price - entry_price)
                    else:
                        exec_exit_price = exit_p * (1.0 + slip_pct / 100.0)
                        gross_pnl = qty * (entry_price - exec_exit_price)

                    slippage_cost = qty * abs(exit_p - exec_exit_price) + qty * abs(entry_price * (slip_pct / 100.0))
                    brokerage_cost = brok * 2.0 # Round-trip brokerage
                    total_costs = slippage_cost + brokerage_cost
                    net_pnl = gross_pnl - brokerage_cost # Slippage already incorporated into execution price
                    
                    gross_ret_pct = (gross_pnl / (qty * entry_price)) * 100.0 if entry_price > 0 else 0.0
                    net_ret_pct = (net_pnl / (qty * entry_price)) * 100.0 if entry_price > 0 else 0.0

                    proceeds = (qty * exec_exit_price if is_bullish else qty * entry_price + gross_pnl) - brok
                    capital += proceeds
                    in_position = False

                    exit_ev = (rule_evidence_series[i] if rule_evidence_series and i < len(rule_evidence_series) else [])

                    trades.append(BacktestTradeEvidence(
                        trade_id=f"TRD_{strat_id}_{i}",
                        strategy_id=strat_id,
                        strategy_version=strat_ver,
                        symbol=sym,
                        timeframe=tf,
                        direction=direction,
                        entry_index=entry_idx,
                        entry_time=entry_time,
                        entry_price=round(entry_price, 2),
                        exit_index=i,
                        exit_time=cur_time,
                        exit_price=round(exec_exit_price, 2),
                        quantity=qty,
                        gross_pnl=round(gross_pnl, 2),
                        gross_return_pct=round(gross_ret_pct, 2),
                        slippage_cost=round(slippage_cost, 2),
                        brokerage_cost=round(brokerage_cost, 2),
                        total_costs=round(total_costs, 2),
                        net_pnl=round(net_pnl, 2),
                        net_return_pct=round(net_ret_pct, 2),
                        exit_reason=exit_reason,
                        duration_bars=bars_in_trade,
                        regime_at_entry=entry_regime,
                        confluence_state=entry_confluence,
                        entry_rule_evidence=entry_evidence,
                        exit_rule_evidence=exit_ev,
                        is_in_sample=(entry_idx < split_bar_idx)
                    ))

            # 3. Check for new Signal at Candle T Close (to trigger next bar)
            if not in_position and not pending_entry:
                is_entry = bool(row[entry_signal_col]) if entry_signal_col in row else False
                if is_entry:
                    pending_entry = True
                    pending_signal_regime = (regimes_series[i] if regimes_series and i < len(regimes_series) else "UNAVAILABLE")
                    pending_signal_confluence = (confluences_series[i] if confluences_series and i < len(confluences_series) else {})
                    pending_signal_evidence = (rule_evidence_series[i] if rule_evidence_series and i < len(rule_evidence_series) else [])

            # Update Equity Curve
            unrealized_pnl = 0.0
            if in_position:
                if direction == "BEARISH":
                    unrealized_pnl = qty * (entry_price - cur_price)
                else:
                    unrealized_pnl = qty * (cur_price - entry_price)
            cur_equity = capital + (qty * entry_price if in_position else 0.0) + unrealized_pnl
            equity_curve.append(cur_equity)

        # -----------------------------------------------------------------------
        # Compute Quantitative Performance Metrics
        # -----------------------------------------------------------------------
        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl <= 0]
        total_trades = len(trades)
        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
        
        gross_profit = sum(t.gross_pnl for t in winning_trades)
        gross_loss = abs(sum(t.gross_pnl for t in losing_trades))
        total_fees = sum(t.brokerage_cost for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)
        total_costs = sum(t.total_costs for t in trades)
        
        net_profit = sum(t.net_pnl for t in trades)
        total_return_pct = ((capital - cap) / cap) * 100.0
        gross_return_pct = ((capital + total_costs - cap) / cap) * 100.0

        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Drawdown Curve
        eq_series = pd.Series(equity_curve)
        peak = eq_series.cummax()
        drawdown_series = (eq_series - peak) / peak * 100.0
        max_drawdown = round(abs(float(drawdown_series.min())), 2) if not drawdown_series.empty else 0.0
        drawdown_curve = [round(float(d), 2) for d in drawdown_series.tolist()]

        # Sharpe & CAGR
        returns = eq_series.pct_change().dropna()
        sharpe = round(float(np.sqrt(252) * (returns.mean() / (returns.std() + 1e-9))), 2) if len(returns) > 1 else 0.0

        start_ts = df.iloc[0].get('timestamp') or df.iloc[0].get('time')
        end_ts = df.iloc[-1].get('timestamp') or df.iloc[-1].get('time')
        try:
            start_val = float(start_ts)
            end_val = float(end_ts)
            elapsed_seconds = max(0.0, end_val - start_val)
            seconds_per_year = 365.25 * 86400.0
            elapsed_years = max(elapsed_seconds / seconds_per_year, 0.01) if elapsed_seconds > 0 else max(len(df) / (75.0 * 252.0), 0.01)
        except (ValueError, TypeError):
            elapsed_years = max(len(df) / (75.0 * 252.0), 0.01)

        if capital > 0 and cap > 0:
            cagr = round((((capital / cap) ** (1.0 / elapsed_years)) - 1.0) * 100.0, 2)
        else:
            cagr = -100.0

        # Trade Durations & Streaks
        durations = [t.duration_bars for t in trades]
        avg_duration = round(float(np.mean(durations)), 1) if durations else 0.0
        median_duration = round(float(np.median(durations)), 1) if durations else 0.0

        # Consecutive Win/Loss streaks
        max_consec_wins = 0
        max_consec_losses = 0
        cur_wins = 0
        cur_losses = 0
        for t in trades:
            if t.net_pnl > 0:
                cur_wins += 1
                cur_losses = 0
                max_consec_wins = max(max_consec_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_consec_losses = max(max_consec_losses, cur_losses)

        # Average and Median trade return %
        net_rets = [t.net_return_pct for t in trades]
        avg_trade_return = round(float(np.mean(net_rets)), 2) if net_rets else 0.0
        median_trade_return = round(float(np.median(net_rets)), 2) if net_rets else 0.0

        # -----------------------------------------------------------------------
        # Walk-Forward Validation (In-Sample 70% vs Out-of-Sample 30%)
        # -----------------------------------------------------------------------
        is_trades = [t for t in trades if t.is_in_sample]
        oos_trades = [t for t in trades if not t.is_in_sample]

        is_pnl = sum(t.net_pnl for t in is_trades)
        oos_pnl = sum(t.net_pnl for t in oos_trades)
        is_return_pct = round((is_pnl / cap) * 100.0, 2)
        oos_return_pct = round((oos_pnl / cap) * 100.0, 2)

        is_win_rate = round(len([t for t in is_trades if t.net_pnl > 0]) / len(is_trades) * 100.0, 1) if is_trades else 0.0
        oos_win_rate = round(len([t for t in oos_trades if t.net_pnl > 0]) / len(oos_trades) * 100.0, 1) if oos_trades else 0.0

        # Overfitting Classification
        if total_trades < 4:
            overfitting_status = "INSUFFICIENT_TRADES"
        elif is_return_pct > 0 and oos_return_pct < -5.0:
            overfitting_status = "OVERFIT"
        elif is_return_pct > 0 and oos_return_pct < 0.0:
            overfitting_status = "DEGRADED_OOS"
        elif total_return_pct <= -15.0:
            overfitting_status = "REJECTED"
        else:
            overfitting_status = "ACCEPTABLE"

        # -----------------------------------------------------------------------
        # Cost Sensitivity Scenarios
        # -----------------------------------------------------------------------
        zero_friction_pnl = sum(t.gross_pnl for t in trades)
        zero_friction_return = round((zero_friction_pnl / cap) * 100.0, 2)

        # High friction: double slippage and double brokerage
        high_friction_costs = sum((t.slippage_cost * 2.0) + (t.brokerage_cost * 2.0) for t in trades)
        high_friction_pnl = sum(t.gross_pnl for t in trades) - high_friction_costs
        high_friction_return = round((high_friction_pnl / cap) * 100.0, 2)

        return {
            "status": "SUCCESS",
            "hypothesis": asdict(hypothesis) if hypothesis else None,
            "strategy_id": strat_id,
            "strategy_version": strat_ver,
            "symbol": sym,
            "timeframe": tf,
            "initialCapital": cap,
            "finalCapital": round(capital, 2),
            "netProfit": round(net_profit, 2),
            "totalReturnPct": round(total_return_pct, 2),
            "total_return_pct": round(total_return_pct, 2),
            "grossReturnPct": round(gross_return_pct, 2),
            "winRate": round(win_rate, 1),
            "win_rate_pct": round(win_rate, 1),
            "profitFactor": profit_factor,
            "profit_factor": profit_factor,
            "maxDrawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown,
            "totalTrades": total_trades,
            "total_trades": total_trades,
            "winningTrades": len(winning_trades),
            "losingTrades": len(losing_trades),
            "sharpeRatio": sharpe,
            "sharpe_ratio": sharpe,
            "cagr": cagr,
            "avg_trade_return_pct": avg_trade_return,
            "median_trade_return_pct": median_trade_return,
            "avg_trade_duration_bars": avg_duration,
            "median_trade_duration_bars": median_duration,
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
            "total_fees": round(total_fees, 2),
            "total_slippage": round(total_slippage, 2),
            "total_friction_costs": round(total_costs, 2),
            "walk_forward": {
                "split_ratio": wf_split,
                "in_sample_bars": split_bar_idx,
                "out_of_sample_bars": n_bars - split_bar_idx,
                "in_sample_trades": len(is_trades),
                "out_of_sample_trades": len(oos_trades),
                "in_sample_return_pct": is_return_pct,
                "out_of_sample_return_pct": oos_return_pct,
                "in_sample_win_rate": is_win_rate,
                "out_of_sample_win_rate": oos_win_rate,
                "overfitting_status": overfitting_status,
            },
            "cost_sensitivity": {
                "zero_friction_return_pct": zero_friction_return,
                "configured_friction_return_pct": round(total_return_pct, 2),
                "high_friction_return_pct": high_friction_return,
                "cost_drag_pct": round(zero_friction_return - total_return_pct, 2),
            },
            "equity_curve": [round(e, 2) for e in equity_curve],
            "drawdown_curve": drawdown_curve,
            "trades": [
                {
                    **asdict(t),
                    "reason": t.exit_reason,
                    "pnl": t.net_pnl,
                    "pnl_pct": t.net_return_pct,
                }
                for t in trades
            ]
        }
