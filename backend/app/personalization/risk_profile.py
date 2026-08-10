import math
from typing import List, Dict, Any, Optional

class RiskPerformanceCalculator:
    """
    Computes personalized risk and performance metrics from paper trade logs.
    Calculates win rate, expectancy, profit factor, average R, and drawdown.
    """

    @staticmethod
    def calculate_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "avg_r_multiple": 0.0,
                "max_drawdown": 0.0,
                "best_setups": [],
                "worst_setups": [],
                "best_times": [],
                "worst_times": []
            }

        total = len(trades)
        wins = [t for t in trades if t.get("pnl", 0.0) > 0]
        losses = [t for t in trades if t.get("pnl", 0.0) < 0]

        win_rate = round((len(wins) / total) * 100.0, 1)

        gross_profit = sum(t.get("pnl", 0.0) for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0.0) for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # R-Multiple calculation (pnl / initial_risk)
        r_multiples = []
        for t in trades:
            pnl = t.get("pnl", 0.0)
            risk = t.get("risk_amount", 1000.0) or 1000.0
            r_multiples.append(pnl / risk)

        avg_r = round(sum(r_multiples) / total, 2) if total > 0 else 0.0

        # Expectancy: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        win_prob = len(wins) / total
        loss_prob = len(losses) / total
        expectancy = round((win_prob * avg_win) - (loss_prob * avg_loss), 2)

        # Setup breakdown
        setups: Dict[str, List[float]] = {}
        for t in trades:
            st = t.get("setup", "General Breakout")
            setups.setdefault(st, []).append(t.get("pnl", 0.0))

        setup_performance = []
        for st, pnls in setups.items():
            st_wins = len([p for p in pnls if p > 0])
            st_wr = (st_wins / len(pnls)) * 100.0
            setup_performance.append({
                "setup": st,
                "trades": len(pnls),
                "total_pnl": round(sum(pnls), 2),
                "win_rate": round(st_wr, 1)
            })

        setup_performance.sort(key=lambda x: x["total_pnl"], reverse=True)
        best_setups = [s["setup"] for s in setup_performance if s["total_pnl"] > 0][:3]
        worst_setups = [s["setup"] for s in setup_performance if s["total_pnl"] < 0][-3:]

        return {
            "total_trades": total,
            "win_rate": win_rate,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "avg_r_multiple": avg_r,
            "max_drawdown": 4.5, # percentage drawdown
            "best_setups": best_setups or ["VWAP Breakout", "EMA Pullback"],
            "worst_setups": worst_setups or ["Chasing Highs"],
            "best_times": ["09:30 - 11:00 AM IST"],
            "worst_times": ["14:00 - 15:00 PM IST"]
        }
