"""
Research Factory — Independent Audit Models & Contracts (Phase 10)
==================================================================
Defines authoritative data structures for independent quant research auditing,
mathematical validation, dataset integrity checks, bootstrap statistics,
and research certification states.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple


class AuditStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    WARNING = "WARNING"
    FAILED = "FAILED"


class CertificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    AUDIT_IN_PROGRESS = "AUDIT_IN_PROGRESS"
    AUDITED = "AUDITED"
    AUDITED_WITH_LIMITATIONS = "AUDITED_WITH_LIMITATIONS"
    AUDIT_FAILED = "AUDIT_FAILED"


class DatasetIntegrityStatus(str, Enum):
    DATASET_VALID = "DATASET_VALID"
    DATASET_LIMITATION = "DATASET_LIMITATION"
    SURVIVORSHIP_BIAS_RISK = "SURVIVORSHIP_BIAS_RISK"


class ReplicationVerdict(str, Enum):
    INDEPENDENTLY_REPRODUCED = "INDEPENDENTLY_REPRODUCED"
    REPLICATION_FAILED = "REPLICATION_FAILED"
    REPRODUCED_WITH_DISCREPANCIES = "REPRODUCED_WITH_DISCREPANCIES"


@dataclass
class AuditDimensionResult:
    """
    Independent audit result for a single validation dimension.
    """
    dimension_name: str
    status: AuditStatus  # PASS | PASS_WITH_LIMITATIONS | WARNING | FAILED
    metrics: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass
class StatisticalInferenceResult:
    """
    Formal statistical inference, bootstrap intervals, and multiple-testing corrections.
    """
    sample_size: int
    standard_error_sharpe: float
    standard_error_cagr: float
    bootstrap_sharpe_ci_95: Tuple[float, float]
    bootstrap_cagr_ci_95: Tuple[float, float]
    trade_autocorrelation_lag1: float
    is_trade_independent: bool
    multiple_testing_k: int
    selection_intensity: float
    holm_bonferroni_p_adjusted: float
    fdr_benjamini_hochberg_q: float
    data_snooping_warning: bool


@dataclass
class IndependentReplicationResult:
    """
    Side-by-side comparison of original reported metrics vs independently recomputed values.
    """
    verdict: ReplicationVerdict
    original_metrics: Dict[str, Any]
    recomputed_metrics: Dict[str, Any]
    discrepancies: List[str] = field(default_factory=list)
    match_rate_pct: float = 100.0


@dataclass
class ResearchAuditReport:
    """
    Authoritative quantitative audit certificate for a research hypothesis.
    """
    hypothesis_id: str
    hypothesis_name: str
    audit_timestamp: int
    certification_status: CertificationStatus
    overall_status: AuditStatus
    dataset_integrity: AuditDimensionResult
    point_in_time_integrity: AuditDimensionResult
    execution_integrity: AuditDimensionResult
    cost_integrity: AuditDimensionResult
    corporate_action_integrity: AuditDimensionResult
    walk_forward_integrity: AuditDimensionResult
    statistical_integrity: AuditDimensionResult
    multiple_testing_integrity: AuditDimensionResult
    cross_symbol_integrity: AuditDimensionResult
    regime_integrity: AuditDimensionResult
    paper_equivalence: AuditDimensionResult
    replication_result: IndependentReplicationResult
    statistical_inference: StatisticalInferenceResult
    limitations: List[str] = field(default_factory=list)
    auditor_verdict_summary: str = ""
