"""
APEX Institutional Circuit Breaker & Pre-Trade Discipline Gate
=============================================================
Ported & Adapted from `tradermonty/claude-trading-skills`:
- drawdown-circuit-breaker: Account-level loss limits & losing-streak cooldowns.
- pre-trade-discipline-gate: Deterministic pre-flight checklist before any order execution.

Configured for Master Ritish's Micro-Capital Framework:
- Account Equity: INR 10,000.00
- Daily Loss Limit: 2.0% (₹200.00)
- Weekly Drawdown Limit: 5.0% (₹500.00)
- Monthly Drawdown Limit: 8.0% (₹800.00)
- Consecutive Loss Cooldown: 2 consecutive losses -> 24-hour mandatory trading halt
- Micro-Debit Ceiling: INR 3,500.00 max debit per option position
- Max Lot Size: 1 lot (25 qty NIFTY)
"""

import time
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CircuitBreakerStatus(str, Enum):
    TRADING_ALLOWED = "TRADING_ALLOWED"
    COOLDOWN = "COOLDOWN"
    HALTED_DAILY = "HALTED_DAILY"
    HALTED_WEEKLY = "HALTED_WEEKLY"
    HALTED_MONTHLY = "HALTED_MONTHLY"
    HALTED_CAPITAL_CRITICAL = "HALTED_CAPITAL_CRITICAL"


class DisciplineGateDecision(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class TradeResultRecord(BaseModel):
    trade_id: str
    symbol: str
    exit_timestamp: float = Field(default_factory=time.time)
    realized_pnl: float
    is_win: bool
    notes: str = ""


class InstitutionalCircuitBreaker:
    """
    Stateful account-level risk guardian.
    Enforces deterministic capital protection, streak cooldowns, and fail-closed state.
    """

    def __init__(
        self,
        account_size: float = 10000.0,
        max_daily_loss_pct: float = 2.0,
        weekly_drawdown_pct: float = 5.0,
        monthly_drawdown_pct: float = 8.0,
        losing_streak_threshold: int = 2,
        cooldown_seconds: float = 86400.0,  # 24 hours
        max_position_debit: float = 3500.0,
        max_lot_size: int = 25,  # 1 lot NIFTY
    ):
        self.account_size = account_size
        self.max_daily_loss_pct = max_daily_loss_pct
        self.weekly_drawdown_pct = weekly_drawdown_pct
        self.monthly_drawdown_pct = monthly_drawdown_pct
        self.losing_streak_threshold = losing_streak_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_position_debit = max_position_debit
        self.max_lot_size = max_lot_size

        self.trade_history: List[TradeResultRecord] = []
        self.cooldown_until: float = 0.0
        self.consecutive_losses: int = 0
        self.status: CircuitBreakerStatus = CircuitBreakerStatus.TRADING_ALLOWED
        self.halt_reason: str = ""

    def record_trade_exit(self, trade_id: str, symbol: str, realized_pnl: float, notes: str = "") -> None:
        """Record completed trade outcome and update streak metrics."""
        is_win = realized_pnl > 0.0
        record = TradeResultRecord(
            trade_id=trade_id,
            symbol=symbol,
            exit_timestamp=time.time(),
            realized_pnl=realized_pnl,
            is_win=is_win,
            notes=notes,
        )
        self.trade_history.append(record)

        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        # Check if consecutive losses trigger cooldown
        if self.consecutive_losses >= self.losing_streak_threshold:
            self.cooldown_until = time.time() + self.cooldown_seconds
            self.status = CircuitBreakerStatus.COOLDOWN
            self.halt_reason = (
                f"Losing streak threshold ({self.losing_streak_threshold} consecutive losses) triggered. "
                f"Mandatory cooling-off period active for {int(self.cooldown_seconds / 3600)}h."
            )
            logger.warning(f"[CIRCUIT BREAKER] {self.halt_reason}")

    def evaluate(self, current_day_pnl: float, unrealized_pnl: float = 0.0) -> Tuple[CircuitBreakerStatus, str]:
        """
        Evaluate current account state against all circuit breaker thresholds.
        Fails closed if limits breached.
        """
        # 0. Fail-closed: maintain persistent halt unless explicitly reset for new session
        if self.status in (
            CircuitBreakerStatus.HALTED_DAILY,
            CircuitBreakerStatus.HALTED_WEEKLY,
            CircuitBreakerStatus.HALTED_MONTHLY,
            CircuitBreakerStatus.HALTED_CAPITAL_CRITICAL,
        ):
            return self.status, self.halt_reason

        now = time.time()
        effective_daily_pnl = current_day_pnl + min(0.0, unrealized_pnl)

        # 1. Cooldown check
        if now < self.cooldown_until:
            remaining_minutes = int((self.cooldown_until - now) / 60)
            self.status = CircuitBreakerStatus.COOLDOWN
            self.halt_reason = f"Consecutive loss cooldown active. Remaining: {remaining_minutes} min."
            return self.status, self.halt_reason

        # 2. Daily Loss Limit (2% = ₹200)
        max_daily_loss = self.account_size * (self.max_daily_loss_pct / 100.0)
        if effective_daily_pnl <= -max_daily_loss:
            self.status = CircuitBreakerStatus.HALTED_DAILY
            self.halt_reason = (
                f"Daily loss ₹{abs(effective_daily_pnl):,.2f} reached threshold of ₹{max_daily_loss:,.2f} "
                f"({self.max_daily_loss_pct}%). Trading halted for current session."
            )
            return self.status, self.halt_reason

        # 3. Weekly Drawdown Limit (5% = ₹500)
        weekly_pnl = self._get_period_pnl(seconds=7 * 86400) + effective_daily_pnl
        max_weekly_loss = self.account_size * (self.weekly_drawdown_pct / 100.0)
        if weekly_pnl <= -max_weekly_loss:
            self.status = CircuitBreakerStatus.HALTED_WEEKLY
            self.halt_reason = (
                f"Weekly drawdown ₹{abs(weekly_pnl):,.2f} breached threshold of ₹{max_weekly_loss:,.2f} "
                f"({self.weekly_drawdown_pct}%). Trading halted until next week."
            )
            return self.status, self.halt_reason

        # 4. Monthly Drawdown Limit (8% = ₹800)
        monthly_pnl = self._get_period_pnl(seconds=30 * 86400) + effective_daily_pnl
        max_monthly_loss = self.account_size * (self.monthly_drawdown_pct / 100.0)
        if monthly_pnl <= -max_monthly_loss:
            self.status = CircuitBreakerStatus.HALTED_MONTHLY
            self.halt_reason = (
                f"Monthly drawdown ₹{abs(monthly_pnl):,.2f} breached threshold of ₹{max_monthly_loss:,.2f} "
                f"({self.monthly_drawdown_pct}%). Trading halted until next calendar month."
            )
            return self.status, self.halt_reason

        self.status = CircuitBreakerStatus.TRADING_ALLOWED
        self.halt_reason = "All risk thresholds satisfied. System nominal."
        return self.status, self.halt_reason

    def _get_period_pnl(self, seconds: float) -> float:
        cutoff = time.time() - seconds
        return sum(t.realized_pnl for t in self.trade_history if t.exit_timestamp >= cutoff)

    def get_status_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "account_size": self.account_size,
            "max_daily_loss_inr": self.account_size * (self.max_daily_loss_pct / 100.0),
            "max_weekly_loss_inr": self.account_size * (self.weekly_drawdown_pct / 100.0),
            "max_monthly_loss_inr": self.account_size * (self.monthly_drawdown_pct / 100.0),
            "consecutive_losses": self.consecutive_losses,
            "cooldown_active": time.time() < self.cooldown_until,
            "cooldown_remaining_sec": max(0.0, round(self.cooldown_until - time.time(), 1)),
            "halt_reason": self.halt_reason,
            "total_trades_tracked": len(self.trade_history),
        }


class PreTradeDisciplineGate:
    """
    Offline pre-flight checklist validator.
    Blocks planless, oversized, revenge-risk, or circuit-breaker-blocked entries.
    """

    def __init__(self, circuit_breaker: InstitutionalCircuitBreaker):
        self.circuit_breaker = circuit_breaker

    def check_trade(
        self,
        strategy_name: str,
        symbol: str,
        order_intent: str,
        entry_price: float,
        stop_price: Optional[float],
        quantity: int,
        estimated_debit: float,
        is_in_written_plan: bool = True,
    ) -> Tuple[DisciplineGateDecision, str]:
        """
        Verify every candidate trade against strict discipline rules.
        """
        # 1. Circuit Breaker gate
        if self.circuit_breaker.status != CircuitBreakerStatus.TRADING_ALLOWED:
            return DisciplineGateDecision.NO_GO, f"Circuit Breaker Gate Veto: {self.circuit_breaker.halt_reason}"
        cb_status, cb_reason = self.circuit_breaker.evaluate(current_day_pnl=0.0)
        if cb_status != CircuitBreakerStatus.TRADING_ALLOWED:
            return DisciplineGateDecision.NO_GO, f"Circuit Breaker Gate Veto: {cb_reason}"

        # 2. Written plan verification
        if not is_in_written_plan:
            return DisciplineGateDecision.NO_GO, "Discipline Veto: Setup is not part of codified strategy matrix."

        # 3. Stop loss requirement (Zero naked undefined risk)
        if stop_price is None or stop_price <= 0:
            return DisciplineGateDecision.NO_GO, "Discipline Veto: Undefined stop loss. Absolute risk cap required."

        # 4. Micro-Capital debit ceiling (Max ₹3,500)
        if estimated_debit > self.circuit_breaker.max_position_debit:
            return (
                DisciplineGateDecision.NO_GO,
                f"Discipline Veto: Capital debit ₹{estimated_debit:,.2f} exceeds micro-cap limit of ₹{self.circuit_breaker.max_position_debit:,.2f}.",
            )

        # 5. Lot size limit (Max 1 lot / 25 qty)
        if quantity > self.circuit_breaker.max_lot_size:
            return (
                DisciplineGateDecision.NO_GO,
                f"Discipline Veto: Quantity {quantity} exceeds single-lot ceiling of {self.circuit_breaker.max_lot_size}.",
            )

        # 6. Sanity checks on entry and stop
        if entry_price <= 0:
            return DisciplineGateDecision.REVIEW_REQUIRED, "Discipline Review: Non-positive entry price."

        return DisciplineGateDecision.GO, "Pre-trade discipline criteria 100% verified. Entry authorized."
