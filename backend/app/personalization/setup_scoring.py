from typing import Dict, Any, List

class SetupScorer:
    """Scores technical setup viability against user historical edge and regime."""

    @staticmethod
    def score_setup(setup: Dict[str, Any], regime: str, user_stats: Dict[str, Any]) -> Dict[str, Any]:
        base_score = setup.get("confidence", 75)
        
        # Regime alignment bonus
        regime_bonus = 0
        if regime == "TRENDING_BULLISH" and setup.get("bias") == "BULLISH":
            regime_bonus = 10
        elif regime == "HIGH_VOLATILITY":
            regime_bonus = -10

        # User historical edge bonus
        user_edge_bonus = 0
        name = setup.get("setup_name", "")
        if name in user_stats.get("best_setups", []):
            user_edge_bonus = 12
        elif name in user_stats.get("worst_setups", []):
            user_edge_bonus = -15

        final_score = max(min(base_score + regime_bonus + user_edge_bonus, 98), 10)

        return {
            "setup_name": name,
            "bias": setup.get("bias", "NEUTRAL"),
            "base_confidence": base_score,
            "final_score": final_score,
            "regime_alignment": regime_bonus,
            "user_historical_edge": user_edge_bonus,
            "recommendation": "EXCELLENT_EDGE" if final_score >= 85 else ("VIABLE" if final_score >= 70 else "CAUTION")
        }
