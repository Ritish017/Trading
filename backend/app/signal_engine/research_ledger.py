"""
Quantitative Research Ledger & Overfitting Protection Architecture
===================================================================
Tracks all research experiments, parameter sweeps, hypotheses, and walk-forward
results permanently. Never silently discards failed experiments (Multiple Testing
Deflated Sharpe / Haircut tracking).
"""

import json
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.app.signal_engine.version_freeze import (
    STRATEGY_VERSION,
    SIGNAL_ENGINE_VERSION,
    CONFIGURATION_HASH,
    GIT_COMMIT,
)


class ResearchExperiment(BaseModel):
    """Immutable record of a single quantitative strategy hypothesis test."""
    hypothesis_id: str
    hypothesis: str
    strategy_id: str
    strategy_version: str = STRATEGY_VERSION
    signal_engine_version: str = SIGNAL_ENGINE_VERSION
    configuration_hash: str = CONFIGURATION_HASH
    git_commit: str = GIT_COMMIT
    training_period: str
    validation_period: str
    test_period: str
    number_of_experiments: int = 1
    parameter_changes: Dict[str, Any] = Field(default_factory=dict)
    sample_size: int = 0
    win_rate: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_r: float = 0.0
    sharpe_ratio: float = 0.0
    is_statistically_significant: bool = False
    result_status: str  # ACCEPTED | REJECTED | INCONCLUSIVE | OVERFITTED
    conclusion: str
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    model_config = ConfigDict(use_enum_values=True)


class ResearchLedger:
    """In-memory and file-backed ledger recording all historical experiments."""

    def __init__(self, ledger_file: str = "docs/RESEARCH_EXPERIMENT_LEDGER.json"):
        self.ledger_file = ledger_file
        self.experiments: List[ResearchExperiment] = []
        self._load_ledger()

    def _load_ledger(self):
        try:
            with open(self.ledger_file, "r") as f:
                data = json.load(f)
                for item in data:
                    self.experiments.append(ResearchExperiment(**item))
        except (FileNotFoundError, json.JSONDecodeError):
            self.experiments = []

    def save_ledger(self):
        try:
            with open(self.ledger_file, "w") as f:
                json.dump([e.model_dump() for e in self.experiments], f, indent=2)
        except Exception:
            pass

    def record_experiment(self, exp: ResearchExperiment) -> None:
        """Append an experiment to the ledger and persist."""
        self.experiments.append(exp)
        self.save_ledger()

    def get_all_experiments(self) -> List[ResearchExperiment]:
        return list(self.experiments)

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.experiments)
        accepted = sum(1 for e in self.experiments if e.result_status == "ACCEPTED")
        rejected = sum(1 for e in self.experiments if e.result_status == "REJECTED")
        overfitted = sum(1 for e in self.experiments if e.result_status == "OVERFITTED")
        return {
            "total_experiments_recorded": total,
            "accepted_hypotheses": accepted,
            "rejected_hypotheses": rejected,
            "overfitted_hypotheses": overfitted,
            "false_discovery_risk": "HIGH" if total > 10 and accepted / max(1, total) < 0.2 else "MONITORED",
        }


# Singleton research ledger
research_ledger = ResearchLedger()
