"""
Quantitative Risk Management & Circuit Breaker Engine
=====================================================
Validates capital limits, drawdown thresholds, portfolio concentration,
and individual trade risk before execution.
"""
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskValidationResult(BaseModel):
    """Structured result from risk validation."""
    passed: bool
    reason: str
    checks_evaluated: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    failure_details: List[str] = Field(default_factory=list)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)


class RiskEngine:
    """
    Quantitative Risk Management & Circuit Breaker Engine.
    Validates capital limits, drawdown thresholds, and position exposure.
    """

    def __init__(
        self,
        max_portfolio_risk_pct: float = 2.0,
        max_drawdown_limit_pct: float = 5.0,
        max_position_size_pct: float = 10.0,
        max_open_positions: int = 10,
        max_symbol_concentration_pct: float = 20.0,
        max_daily_loss_pct: float = 3.0,
    ):
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_drawdown_limit_pct = max_drawdown_limit_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_open_positions = max_open_positions
        self.max_symbol_concentration_pct = max_symbol_concentration_pct
        self.max_daily_loss_pct = max_daily_loss_pct

    def validate_order_risk(
        self,
        account_balance: float,
        order_value: float,
        current_drawdown_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """Validates simple individual order against drawdown and single-position size limits."""
        if current_drawdown_pct >= self.max_drawdown_limit_pct:
            return {
                "passed": False,
                "reason": f"Maximum drawdown threshold reached ({current_drawdown_pct:.2f}% >= {self.max_drawdown_limit_pct:.2f}%). Trading halted by Risk Engine.",
            }

        max_order_val = account_balance * (self.max_position_size_pct / 100.0)
        if order_value > max_order_val:
            return {
                "passed": False,
                "reason": f"Order size (₹{order_value:.2f}) exceeds maximum position risk limit (₹{max_order_val:.2f}, {self.max_position_size_pct}% of capital).",
            }

        return {"passed": True, "reason": "Order passed risk validation check."}

    def validate_signal_risk(
        self,
        signal: Any,
        portfolio_state: Dict[str, Any],
        config: Optional[Any] = None,
    ) -> RiskValidationResult:
        """
        Comprehensive pre-trade risk evaluation for a qualified SignalDecision.
        Evaluates portfolio drawdown, max open positions, symbol concentration,
        margin requirements, and maximum trade loss.
        """
        failures: List[str] = []
        checks_evaluated = 0
        checks_passed = 0

        # Extract portfolio metrics
        capital = float(portfolio_state.get("capital") or portfolio_state.get("available_capital") or 1000000.0)
        initial_capital = float(portfolio_state.get("initial_capital") or capital)
        net_worth = float(portfolio_state.get("net_worth") or capital)
        open_positions = portfolio_state.get("positions") or []
        open_count = len(open_positions) if isinstance(open_positions, list) else int(portfolio_state.get("open_positions_count") or 0)

        # Drawdown calculation
        drawdown_pct = 0.0
        if initial_capital > 0:
            drawdown_pct = max(0.0, ((initial_capital - net_worth) / initial_capital) * 100.0)

        # 1. Circuit Breaker / Drawdown limit
        checks_evaluated += 1
        if drawdown_pct >= self.max_drawdown_limit_pct:
            failures.append(
                f"Portfolio drawdown {drawdown_pct:.2f}% exceeds circuit breaker threshold {self.max_drawdown_limit_pct:.2f}%"
            )
        else:
            checks_passed += 1

        # 2. Maximum open positions
        checks_evaluated += 1
        if open_count >= self.max_open_positions:
            failures.append(
                f"Open positions count ({open_count}) has reached max capacity ({self.max_open_positions})"
            )
        else:
            checks_passed += 1

        # Extract signal properties safely (handles Pydantic model or dict)
        symbol = getattr(signal, "symbol", None) or (signal.get("symbol") if isinstance(signal, dict) else "")
        pos_size = getattr(signal, "position_size", None) or (signal.get("position_size") if isinstance(signal, dict) else None)

        capital_required = 0.0
        max_loss = 0.0
        if pos_size:
            capital_required = float(getattr(pos_size, "capital_required", 0.0) or (pos_size.get("capital_required", 0.0) if isinstance(pos_size, dict) else 0.0))
            max_loss = float(getattr(pos_size, "maximum_loss", 0.0) or (pos_size.get("maximum_loss", 0.0) if isinstance(pos_size, dict) else 0.0))
        elif hasattr(signal, "entry") and signal.entry:
            capital_required = float(signal.entry)

        # 3. Available capital check
        checks_evaluated += 1
        if capital_required > capital:
            failures.append(
                f"Capital required (₹{capital_required:,.2f}) exceeds available liquidity (₹{capital:,.2f})"
            )
        else:
            checks_passed += 1

        # 4. Position size limit
        checks_evaluated += 1
        max_allowed_position = capital * (self.max_position_size_pct / 100.0)
        if capital_required > max_allowed_position:
            failures.append(
                f"Position allocation (₹{capital_required:,.2f}) exceeds single position limit (₹{max_allowed_position:,.2f}, {self.max_position_size_pct}% of capital)"
            )
        else:
            checks_passed += 1

        # 5. Risk-per-trade limit (Maximum loss on trade <= max_portfolio_risk_pct of capital)
        checks_evaluated += 1
        max_trade_risk = capital * (self.max_portfolio_risk_pct / 100.0)
        if max_loss > max_trade_risk:
            failures.append(
                f"Trade maximum loss (₹{max_loss:,.2f}) exceeds risk-per-trade threshold (₹{max_trade_risk:,.2f}, {self.max_portfolio_risk_pct}% of capital)"
            )
        else:
            checks_passed += 1

        # 6. Symbol concentration
        checks_evaluated += 1
        existing_symbol_val = 0.0
        if isinstance(open_positions, list):
            for pos in open_positions:
                if isinstance(pos, dict) and pos.get("symbol") == symbol:
                    qty = float(pos.get("quantity") or 0)
                    price = float(pos.get("entry_price") or pos.get("ltp") or 0)
                    existing_symbol_val += qty * price

        max_symbol_val = capital * (self.max_symbol_concentration_pct / 100.0)
        if (existing_symbol_val + capital_required) > max_symbol_val:
            failures.append(
                f"Total exposure in {symbol} (₹{existing_symbol_val + capital_required:,.2f}) exceeds symbol concentration limit (₹{max_symbol_val:,.2f})"
            )
        else:
            checks_passed += 1

        passed = len(failures) == 0
        checks_failed = len(failures)
        reason = "All risk gates passed" if passed else "; ".join(failures)

        return RiskValidationResult(
            passed=passed,
            reason=reason,
            checks_evaluated=checks_evaluated,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            failure_details=failures,
            risk_metrics={
                "capital": capital,
                "net_worth": net_worth,
                "drawdown_pct": round(drawdown_pct, 2),
                "open_positions": open_count,
                "capital_required": round(capital_required, 2),
                "max_loss": round(max_loss, 2),
                "max_trade_risk": round(max_trade_risk, 2),
            },
        )


# Global default instance
risk_engine = RiskEngine()
