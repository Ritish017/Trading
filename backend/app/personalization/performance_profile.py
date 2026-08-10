from typing import Dict, Any, List
from backend.app.personalization.risk_profile import RiskPerformanceCalculator

def build_performance_snapshot(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Helper to generate structured performance profile snapshot."""
    return RiskPerformanceCalculator.calculate_metrics(trades)
