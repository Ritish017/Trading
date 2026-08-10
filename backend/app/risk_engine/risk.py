from typing import Dict, Any, List

class RiskEngine:
    """
    Quantitative Risk Management & Circuit Breaker Engine
    Validates capital limits, drawdown thresholds, and position exposure.
    """

    def __init__(
        self,
        max_portfolio_risk_pct: float = 2.0,
        max_drawdown_limit_pct: float = 5.0,
        max_position_size_pct: float = 10.0
    ):
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_drawdown_limit_pct = max_drawdown_limit_pct
        self.max_position_size_pct = max_position_size_pct

    def validate_order_risk(
        self,
        account_balance: float,
        order_value: float,
        current_drawdown_pct: float = 0.0
    ) -> Dict[str, Any]:
        if current_drawdown_pct >= self.max_drawdown_limit_pct:
            return {
                "passed": False,
                "reason": f"Maximum drawdown threshold reached ({current_drawdown_pct:.2f}% >= {self.max_drawdown_limit_pct:.2f}%). Trading halted by Risk Engine."
            }

        max_order_val = account_balance * (self.max_position_size_pct / 100.0)
        if order_value > max_order_val:
            return {
                "passed": False,
                "reason": f"Order size (₹{order_value:.2f}) exceeds maximum position risk limit (₹{max_order_val:.2f}, {self.max_position_size_pct}% of capital)."
            }

        return {"passed": True, "reason": "Order passed risk validation check."}
