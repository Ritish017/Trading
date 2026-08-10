from typing import Dict, Any, List
from backend.app.personalization.risk_profile import RiskPerformanceCalculator

class TraderProfileManager:
    """Manages personalized trader profiles, historical stats, and AI prompt context snapshots."""

    def __init__(self):
        self.paper_trades: List[Dict[str, Any]] = []

    def record_trade(self, trade: Dict[str, Any]):
        self.paper_trades.append(trade)

    def get_profile_summary(self) -> Dict[str, Any]:
        metrics = RiskPerformanceCalculator.calculate_metrics(self.paper_trades)
        return {
            "trader_level": "Intermediate Quant Trader",
            "experience_focus": "NSE Indian Equities & Index Options",
            "metrics": metrics
        }

trader_profile_mgr = TraderProfileManager()
