"""
Research Factory — Experiment Ledger & Promotion Manager (Phase 9)
==================================================================
Maintains the immutable experiment ledger, validation scorecards,
rejection catalogs, and promotion gates for the Research Factory.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.app.research_factory.models import (
    ResearchHypothesis,
    ValidationScorecard,
    HypothesisStatus,
    RejectionReason,
)
from backend.app.research_factory.audit_models import (
    ResearchAuditReport,
    CertificationStatus,
)
from backend.app.research_factory.generator import HypothesisGenerator
from backend.app.research_factory.validator import validator
from backend.app.research_factory.auditor import research_auditor

logger = logging.getLogger(__name__)


class ResearchFactoryLedger:
    """
    Central experiment ledger for quantitative research hypotheses.
    """

    def __init__(self):
        self.hypotheses: Dict[str, ResearchHypothesis] = {}
        self.scorecards: Dict[str, ValidationScorecard] = {}
        self.audit_reports: Dict[str, ResearchAuditReport] = {}
        self.experiment_history: List[Dict[str, Any]] = []
        self._seed_canonical_hypotheses()

    def _seed_canonical_hypotheses(self):
        """Pre-populates ledger with canonical research hypotheses and validated scorecards."""
        templates = HypothesisGenerator.get_canonical_templates()
        for hyp in templates:
            self.hypotheses[hyp.hypothesis_id] = hyp
            scorecard = validator.validate_hypothesis(hyp)
            self.scorecards[hyp.hypothesis_id] = scorecard
            audit_rep = research_auditor.audit_hypothesis(hyp, scorecard)
            self.audit_reports[hyp.hypothesis_id] = audit_rep
            self.experiment_history.append({
                "experiment_id": f"EXP_{hyp.hypothesis_id}",
                "hypothesis_id": hyp.hypothesis_id,
                "timestamp": hyp.created_timestamp,
                "status": hyp.status.value,
                "oos_sharpe": scorecard.oos_result.oos_sharpe,
                "oos_return_pct": scorecard.oos_result.oos_return_pct,
                "k_tested": hyp.k_tested,
                "recommendation": scorecard.overall_recommendation,
                "certification": audit_rep.certification_status.value,
            })

    def list_hypotheses(self) -> List[ResearchHypothesis]:
        return list(self.hypotheses.values())

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ResearchHypothesis]:
        return self.hypotheses.get(hypothesis_id)

    def get_scorecard(self, hypothesis_id: str) -> Optional[ValidationScorecard]:
        return self.scorecards.get(hypothesis_id)

    def get_audit_report(self, hypothesis_id: str) -> Optional[ResearchAuditReport]:
        return self.audit_reports.get(hypothesis_id)

    def audit_and_record(self, hypothesis: ResearchHypothesis) -> ResearchAuditReport:
        scorecard = self.scorecards.get(hypothesis.hypothesis_id)
        if not scorecard:
            scorecard = self.validate_and_record(hypothesis)
        report = research_auditor.audit_hypothesis(hypothesis, scorecard)
        self.audit_reports[hypothesis.hypothesis_id] = report
        return report

    def validate_and_record(self, hypothesis: ResearchHypothesis) -> ValidationScorecard:
        scorecard = validator.validate_hypothesis(hypothesis)
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        self.scorecards[hypothesis.hypothesis_id] = scorecard
        self.experiment_history.append({
            "experiment_id": f"EXP_{hypothesis.hypothesis_id}_{int(time.time())}",
            "hypothesis_id": hypothesis.hypothesis_id,
            "timestamp": int(time.time()),
            "status": hypothesis.status.value,
            "oos_sharpe": scorecard.oos_result.oos_sharpe,
            "oos_return_pct": scorecard.oos_result.oos_return_pct,
            "k_tested": hypothesis.k_tested,
            "recommendation": scorecard.overall_recommendation,
        })
        return scorecard

    def promote_to_paper(self, hypothesis_id: str) -> Tuple[bool, str]:
        """
        Applies promotion gate to transition a validated candidate to PAPER_TESTING.
        """
        hyp = self.hypotheses.get(hypothesis_id)
        if not hyp:
            return False, f"Hypothesis {hypothesis_id} not found."

        scorecard = self.scorecards.get(hypothesis_id)
        if not scorecard:
            return False, "Validation scorecard missing. Run empirical validation first."

        if scorecard.overall_recommendation != "PROMOTABLE_CANDIDATE":
            return False, f"Promotion gate failed: Scorecard status is {scorecard.overall_recommendation}."

        hyp.status = HypothesisStatus.PAPER_TESTING
        return True, f"Hypothesis {hypothesis_id} promoted to PAPER_TESTING."

    def reject_hypothesis(self, hypothesis_id: str, reasons: List[RejectionReason], notes: str = "") -> Tuple[bool, str]:
        """
        Explicitly records hypothesis rejection with forensic failure catalog entries.
        """
        hyp = self.hypotheses.get(hypothesis_id)
        if not hyp:
            return False, f"Hypothesis {hypothesis_id} not found."

        hyp.status = HypothesisStatus.REJECTED
        hyp.rejection_reasons = reasons
        hyp.rejection_notes = notes
        return True, f"Hypothesis {hypothesis_id} marked as REJECTED."


# Canonical Singleton
research_ledger = ResearchFactoryLedger()
