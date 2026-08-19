"""
Paper Engine — Paper Trading Bridge & Next-Bar Execution (Phase 8)
==================================================================
Provides the deterministic bridge connecting StrategyResult + ConfluenceResult
directly to the Paper Trading simulator with strict next-bar execution semantics
and Indian equity transaction cost breakdown.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from backend.app.paper_engine.models import (
    PaperSignal,
    PaperPosition,
    PaperTradeAudit,
    OrderSide,
    PositionStatus,
    ExitReason,
)
from backend.app.strategy_engine.dsl import StrategyState
from backend.app.strategy_engine.evaluator import StrategyEvaluationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Indian Equity Transaction Frictions Model (NSE Equity Delivery/Intraday)
# ---------------------------------------------------------------------------

def calculate_indian_equity_frictions(
    price: float,
    quantity: int,
    is_buy: bool,
    slippage_pct: float = 0.05,
) -> Dict[str, float]:
    """
    Computes realistic Indian exchange friction breakdown.
    - Brokerage: min(20.0, turnover * 0.0005)
    - STT / CTT: 0.1% on delivery (both buy & sell), or 0.025% sell on intraday
    - Exchange Turnover Charge: 0.00345%
    - SEBI Turnover Charge: 0.0001%
    - GST: 18% on (Brokerage + Exchange + SEBI)
    - Stamp Duty: 0.015% on buy
    - Slippage: slippage_pct / 100 * turnover
    """
    turnover = price * quantity
    brokerage = min(20.0, turnover * 0.0005)
    stt = turnover * 0.001 if not is_buy else turnover * 0.001
    exchange_charges = turnover * 0.0000345
    sebi_charges = turnover * 0.000001
    gst = (brokerage + exchange_charges + sebi_charges) * 0.18
    stamp_duty = (turnover * 0.00015) if is_buy else 0.0
    slippage = (slippage_pct / 100.0) * turnover

    total_fees = brokerage + stt + exchange_charges + sebi_charges + gst + stamp_duty

    return {
        "turnover": round(turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(exchange_charges, 2),
        "sebi_charges": round(sebi_charges, 2),
        "gst": round(gst, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_fees": round(total_fees, 2),
        "slippage": round(slippage, 2),
        "total_friction": round(total_fees + slippage, 2),
    }


class PaperTradingBridge:
    """
    Authoritative quantitative bridge from strategy evidence to paper execution.
    """

    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.available_cash = initial_capital
        self.positions: Dict[str, PaperPosition] = {}
        self.trade_audits: List[PaperTradeAudit] = []
        self.signals_history: List[PaperSignal] = []

    def generate_signal_from_strategy(
        self,
        strategy_result: Any,
        current_price: float,
        confluence_state: str = "NEUTRAL",
        fundamental_state: str = "NEUTRAL",
        data_freshness: str = "LIVE",
        provider: str = "UPSTOX",
        regime: str = "NORMAL",
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        timestamp: Optional[int] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Optional[PaperSignal]:
        """
        Derives an immutable PaperSignal directly from canonical StrategyEvaluationResult.
        """
        def _g(o, k, d=None):
            return o.get(k, d) if isinstance(o, dict) else getattr(o, k, d)

        st = _g(strategy_result, "state")
        st_val = st.value if hasattr(st, "value") else str(st)
        if st_val != StrategyState.ACTIVE.value and st_val != "ACTIVE":
            return None

        strat_id = _g(strategy_result, "strategy_id", "STRATEGY")
        version = _g(strategy_result, "version", "1.0.0")
        sym = symbol or _g(strategy_result, "symbol", "RELIANCE.NS")
        tf = timeframe or _g(strategy_result, "timeframe", "1D")
        ts = timestamp or _g(strategy_result, "timestamp", int(time.time()))

        # Extract deterministic evidence
        rule_evals = _g(strategy_result, "rule_evaluations", []) or _g(strategy_result, "matched_rules", []) or []
        rule_evidence = []
        for r in rule_evals:
            r_name = _g(r, "name", _g(r, "rule_id", "Rule"))
            r_desc = _g(r, "description", "")
            rule_evidence.append(f"{r_name}: {r_desc}")

        if not rule_evidence:
            rule_evidence.append(f"Strategy {strat_id} entry conditions met.")

        sig_id = f"SIG_{strat_id}_{sym}_{ts}"
        signal = PaperSignal(
            signal_id=sig_id,
            timestamp=ts,
            symbol=sym,
            timeframe=tf,
            strategy_id=strat_id,
            strategy_version=version,
            strategy_state="ACTIVE",
            side=OrderSide.BUY,
            intended_price=current_price,
            stop_loss=stop_loss or _g(strategy_result, "primary_stop"),
            take_profit=take_profit or _g(strategy_result, "primary_target"),
            fundamental_state=fundamental_state,
            confluence_state=confluence_state,
            rule_evidence=rule_evidence,
            factor_evidence=[f"Confluence: {confluence_state}"],
            data_freshness=data_freshness,
            provider=provider,
            regime=regime,
        )

        self.signals_history.append(signal)
        return signal

    def execute_next_bar_entry(
        self,
        signal: PaperSignal,
        next_bar_open: float,
        next_bar_timestamp: int,
        quantity: Optional[int] = None,
        allocation_amount: float = 100000.0,
    ) -> Optional[PaperPosition]:
        """
        Strict next-bar execution: executes at next bar's open price with slippage and fees.
        """
        if quantity is None or quantity <= 0:
            quantity = max(1, int(allocation_amount / next_bar_open))

        frictions = calculate_indian_equity_frictions(next_bar_open, quantity, is_buy=True)
        effective_entry_price = round(next_bar_open + (frictions["slippage"] / quantity), 2)
        total_cost = (effective_entry_price * quantity) + frictions["total_fees"]

        if self.available_cash < total_cost:
            logger.warning("Insufficient cash for paper trade. Required: %s, Available: %s", total_cost, self.available_cash)
            return None

        pos_id = f"POS_{signal.strategy_id}_{signal.symbol}_{next_bar_timestamp}"
        pos = PaperPosition(
            position_id=pos_id,
            symbol=signal.symbol,
            strategy_id=signal.strategy_id,
            strategy_version=signal.strategy_version,
            side=signal.side,
            quantity=quantity,
            entry_timestamp=next_bar_timestamp,
            entry_price=effective_entry_price,
            current_price=next_bar_open,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            fees_paid=frictions["total_fees"],
            slippage_paid=frictions["slippage"],
            signal=signal,
            regime_at_entry=signal.regime,
            confluence_at_entry=signal.confluence_state,
            data_status=signal.data_freshness,
            provider=signal.provider,
        )

        self.available_cash -= total_cost
        self.positions[pos_id] = pos
        return pos

    def update_positions_mark_to_market(
        self,
        symbol: str,
        current_candle_high: float,
        current_candle_low: float,
        current_candle_close: float,
        current_timestamp: int,
    ) -> List[PaperTradeAudit]:
        """
        Updates unrealized P&L and checks stop-loss / take-profit triggers.
        """
        closed_audits: List[PaperTradeAudit] = []

        for pos_id, pos in list(self.positions.items()):
            if pos.symbol != symbol or pos.status != PositionStatus.OPEN:
                continue

            pos.current_price = current_candle_close
            gross_unrealized = (pos.current_price - pos.entry_price) * pos.quantity
            pos.unrealized_pnl = round(gross_unrealized - pos.fees_paid, 2)
            pos.unrealized_pnl_pct = round((pos.unrealized_pnl / (pos.entry_price * pos.quantity)) * 100.0, 2)

            # Check Stop Loss Trigger
            if pos.stop_loss is not None and current_candle_low <= pos.stop_loss:
                audit = self.close_position(pos_id, pos.stop_loss, current_timestamp, ExitReason.STOP_LOSS)
                if audit:
                    closed_audits.append(audit)
                continue

            # Check Take Profit Trigger
            if pos.take_profit is not None and current_candle_high >= pos.take_profit:
                audit = self.close_position(pos_id, pos.take_profit, current_timestamp, ExitReason.TAKE_PROFIT)
                if audit:
                    closed_audits.append(audit)
                continue

        return closed_audits

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_timestamp: int,
        exit_reason: ExitReason = ExitReason.MANUAL_CLOSE,
    ) -> Optional[PaperTradeAudit]:
        """
        Closes an open position, computes net P&L with exit frictions, and creates a PaperTradeAudit.
        """
        pos = self.positions.get(position_id)
        if not pos or pos.status != PositionStatus.OPEN:
            return None

        exit_frictions = calculate_indian_equity_frictions(exit_price, pos.quantity, is_buy=False)
        effective_exit_price = round(exit_price - (exit_frictions["slippage"] / pos.quantity), 2)

        gross_pnl = (effective_exit_price - pos.entry_price) * pos.quantity
        total_fees = pos.fees_paid + exit_frictions["total_fees"]
        total_slippage = pos.slippage_paid + exit_frictions["slippage"]
        net_pnl = round(gross_pnl - exit_frictions["total_fees"], 2)
        ret_pct = round((net_pnl / (pos.entry_price * pos.quantity)) * 100.0, 2)

        pos.status = PositionStatus.CLOSED
        pos.exit_price = effective_exit_price
        pos.exit_timestamp = exit_timestamp
        pos.exit_reason = exit_reason
        pos.realized_pnl = net_pnl
        pos.unrealized_pnl = 0.0

        proceeds = (effective_exit_price * pos.quantity) - exit_frictions["total_fees"]
        self.available_cash += proceeds

        audit = PaperTradeAudit(
            trade_id=f"TRD_{pos.position_id}",
            signal_id=pos.signal.signal_id if pos.signal else "UNKNOWN",
            symbol=pos.symbol,
            strategy_id=pos.strategy_id,
            strategy_version=pos.strategy_version,
            side=pos.side,
            quantity=pos.quantity,
            entry_timestamp=pos.entry_timestamp,
            entry_price=pos.entry_price,
            exit_timestamp=exit_timestamp,
            exit_price=effective_exit_price,
            exit_reason=exit_reason,
            gross_pnl=round(gross_pnl, 2),
            net_pnl=net_pnl,
            fees_paid=round(total_fees, 2),
            slippage_paid=round(total_slippage, 2),
            return_pct=ret_pct,
            holding_period_bars=max(1, int((exit_timestamp - pos.entry_timestamp) / 3600)),
            entry_evidence=pos.signal.rule_evidence if pos.signal else [],
            exit_evidence=[f"Exit triggered by: {exit_reason.value}"],
            regime_at_entry=pos.regime_at_entry,
            confluence_at_entry=pos.confluence_at_entry,
        )

        self.trade_audits.append(audit)
        return audit

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Aggregates complete paper performance statistics.
        """
        closed_trades = self.trade_audits
        n_trades = len(closed_trades)

        if n_trades == 0:
            return {
                "total_trades": 0,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "fees_paid": 0.0,
                "slippage_paid": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
                "avg_holding_bars": 0,
                "available_cash": round(self.available_cash, 2),
                "open_positions_count": sum(1 for p in self.positions.values() if p.status == PositionStatus.OPEN),
            }

        pnls = [t.net_pnl for t in closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]

        win_rate = (len(wins) / n_trades) * 100.0
        profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else (99.0 if sum(wins) > 0 else 0.0)

        # Consecutive Wins/Losses
        max_cw, max_cl, curr_cw, curr_cl = 0, 0, 0, 0
        for p in pnls:
            if p > 0:
                curr_cw += 1
                curr_cl = 0
                max_cw = max(max_cw, curr_cw)
            elif p < 0:
                curr_cl += 1
                curr_cw = 0
                max_cl = max(max_cl, curr_cl)

        return {
            "total_trades": n_trades,
            "gross_pnl": round(sum(t.gross_pnl for t in closed_trades), 2),
            "net_pnl": round(sum(pnls), 2),
            "fees_paid": round(sum(t.fees_paid for t in closed_trades), 2),
            "slippage_paid": round(sum(t.slippage_paid for t in closed_trades), 2),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_consecutive_wins": max_cw,
            "max_consecutive_losses": max_cl,
            "avg_holding_bars": round(float(np.mean([t.holding_period_bars for t in closed_trades])), 1),
            "available_cash": round(self.available_cash, 2),
            "open_positions_count": sum(1 for p in self.positions.values() if p.status == PositionStatus.OPEN),
        }


# Canonical Singleton
paper_bridge = PaperTradingBridge()
