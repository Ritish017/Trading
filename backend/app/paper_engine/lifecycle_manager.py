"""
Paper Engine — Research Lifecycle Manager & Promotion Ledger (Phase 8)
======================================================================
Manages candidate strategy progression through structured research states:
DRAFT -> RESEARCHING -> VALIDATION_REQUIRED -> RESEARCH_CANDIDATE -> PAPER_TESTING -> REJECTED / ARCHIVED.

CRITICAL INVARIANTS:
1. No automatic promotion to PAPER_TESTING without explicit validation gates.
2. Every lifecycle transition is recorded with timestamp and reason.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from backend.app.paper_engine.models import (
    ResearchLifecycleState,
    ResearchCandidate,
)

logger = logging.getLogger(__name__)

# Valid state progression transitions
VALID_TRANSITIONS: Dict[ResearchLifecycleState, List[ResearchLifecycleState]] = {
    ResearchLifecycleState.DRAFT: [ResearchLifecycleState.RESEARCHING, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.RESEARCHING: [ResearchLifecycleState.VALIDATION_REQUIRED, ResearchLifecycleState.REJECTED, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.VALIDATION_REQUIRED: [ResearchLifecycleState.RESEARCH_CANDIDATE, ResearchLifecycleState.REJECTED, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.RESEARCH_CANDIDATE: [ResearchLifecycleState.PAPER_TESTING, ResearchLifecycleState.REJECTED, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.PAPER_TESTING: [ResearchLifecycleState.RESEARCH_CANDIDATE, ResearchLifecycleState.REJECTED, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.REJECTED: [ResearchLifecycleState.DRAFT, ResearchLifecycleState.ARCHIVED],
    ResearchLifecycleState.ARCHIVED: [ResearchLifecycleState.DRAFT],
}


class ResearchLifecycleManager:
    """
    Manages strategy lifecycle states and promotion gates.
    """

    def __init__(self):
        self.candidates: Dict[str, ResearchCandidate] = {}
        self._seed_default_candidates()

    def _seed_default_candidates(self):
        """Seed initial canonical strategies into research lifecycle ledger."""
        now = int(time.time())
        default_strategies = [
            ("EMA_TREND_MOMENTUM", "EMA Trend Momentum Strategy", ResearchLifecycleState.RESEARCH_CANDIDATE, 1.45, 18.2, 58.0),
            ("RSI_MEAN_REVERSION", "RSI Mean Reversion Oversold", ResearchLifecycleState.PAPER_TESTING, 1.20, 14.5, 62.0),
            ("BB_SQUEEZE_BREAKOUT", "Bollinger Bands Squeeze Breakout", ResearchLifecycleState.RESEARCH_CANDIDATE, 1.60, 21.0, 54.0),
            ("MACD_ZERO_CROSS", "MACD Zero Line Momentum", ResearchLifecycleState.VALIDATION_REQUIRED, 1.10, 12.0, 48.0),
        ]

        for s_id, s_name, state, sharpe, cagr, wfe in default_strategies:
            cand = ResearchCandidate(
                candidate_id=f"CAND_{s_id}",
                strategy_id=s_id,
                strategy_name=s_name,
                lifecycle_state=state,
                created_timestamp=now,
                updated_timestamp=now,
                backtest_sharpe=sharpe,
                backtest_cagr_pct=cagr,
                walk_forward_efficiency=wfe,
                hypothesis_text=f"Deterministic rule verification for {s_name}.",
            )
            self.candidates[cand.candidate_id] = cand

    def get_candidate(self, candidate_id: str) -> Optional[ResearchCandidate]:
        return self.candidates.get(candidate_id)

    def list_candidates(self) -> List[ResearchCandidate]:
        return list(self.candidates.values())

    def transition_state(
        self,
        candidate_id: str,
        new_state: ResearchLifecycleState,
        reason: str = "",
    ) -> Tuple_Validation:
        cand = self.candidates.get(candidate_id)
        if not cand:
            return False, f"Candidate {candidate_id} not found."

        allowed = VALID_TRANSITIONS.get(cand.lifecycle_state, [])
        if new_state not in allowed:
            return False, f"Invalid transition: {cand.lifecycle_state.value} -> {new_state.value}. Allowed: {[s.value for s in allowed]}"

        # Promotion Gate for PAPER_TESTING
        if new_state == ResearchLifecycleState.PAPER_TESTING:
            if cand.backtest_sharpe is not None and cand.backtest_sharpe < 0.5:
                return False, f"Promotion gate failed: Backtest Sharpe ({cand.backtest_sharpe}) < 0.5 minimum."
            if cand.walk_forward_efficiency is not None and cand.walk_forward_efficiency < 30.0:
                return False, f"Promotion gate failed: Walk-Forward Efficiency ({cand.walk_forward_efficiency}%) < 30% minimum."

        old_state = cand.lifecycle_state
        cand.lifecycle_state = new_state
        cand.updated_timestamp = int(time.time())
        cand.notes = f"Transitioned from {old_state.value} to {new_state.value}: {reason}"

        return True, f"Successfully transitioned to {new_state.value}."


# Type alias helper
Tuple_Validation = tuple[bool, str]

# Canonical Singleton
lifecycle_manager = ResearchLifecycleManager()
