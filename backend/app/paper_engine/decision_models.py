"""
Paper Engine — Continuous Validation & Research Decision Models (Phase 12)
==========================================================================
Defines cryptographic hypothesis fingerprints, persistent forward observation state,
signal lifecycle ledgers (eligible/executed/skipped/invalidated), 9 validation gates,
decision timeline checkpoints, and the Research Decision Engine contracts.

CRITICAL INVARIANTS:
1. Frozen hypothesis fingerprint is cryptographically immutable (SHA-256).
2. Exactly 5 real forward paper trades tracked; zero synthetic forward trades.
3. Decision remains CONTINUE_OBSERVATION while N < 30.
4. Regimes without trades display NO_PAPER_OBSERVATION (never 0% fabricated return).
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple


class SignalState(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"
    UNAVAILABLE = "UNAVAILABLE"


class SkipReason(str, Enum):
    NONE = "NONE"
    STALE_DATA = "STALE_DATA"
    MARKET_CLOSED = "MARKET_CLOSED"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    PRICE_LIMIT_REACHED = "PRICE_LIMIT_REACHED"
    INVALIDATED_BEFORE_EXECUTION = "INVALIDATED_BEFORE_EXECUTION"
    EXECUTION_UNAVAILABLE = "EXECUTION_UNAVAILABLE"


class ResearchDecision(str, Enum):
    CONTINUE_OBSERVATION = "CONTINUE_OBSERVATION"
    PAPER_VALIDATED = "PAPER_VALIDATED"
    PAPER_DEGRADED = "PAPER_DEGRADED"
    PAPER_REJECTED = "PAPER_REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ComparisonStatus(str, Enum):
    WITHIN_EXPECTATION = "WITHIN_EXPECTATION"
    WATCH = "WATCH"
    OUTSIDE_EXPECTATION = "OUTSIDE_EXPECTATION"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


class RegimeObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


class GateDecisionStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class HypothesisFingerprint:
    """
    Cryptographic SHA-256 fingerprint of the complete frozen hypothesis configuration.
    """
    hypothesis_id: str
    version: str
    sha256_hash: str
    canonical_payload: str

    @classmethod
    def compute(cls, hypothesis_id: str, version: str, parameters: Dict[str, Any], rules: List[str], universe: List[str]) -> "HypothesisFingerprint":
        payload = json.dumps({
            "hypothesis_id": hypothesis_id,
            "version": version,
            "parameters": sorted(parameters.items()),
            "rules": sorted(rules),
            "universe": sorted(universe),
        }, sort_keys=True)
        sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cls(
            hypothesis_id=hypothesis_id,
            version=version,
            sha256_hash=sha,
            canonical_payload=payload,
        )


@dataclass
class ContinuousObservationState:
    """
    Persistent forward validation telemetry surviving restarts.
    """
    hypothesis_id: str
    fingerprint: str
    first_paper_timestamp: int
    last_paper_timestamp: int
    paper_trade_count: int
    paper_signal_count: int
    closed_trade_count: int
    open_trade_count: int
    elapsed_days: int
    observed_regimes: List[str]
    observed_symbols: List[str]
    observed_timeframes: List[str]


@dataclass
class PersistentPaperSignalRecord:
    """
    Forensic record for every paper signal, including skipped/missed audits.
    """
    signal_id: str
    timestamp: int
    symbol: str
    strategy_id: str
    hypothesis_id: str
    hypothesis_fingerprint: str
    state: SignalState
    skip_reason: SkipReason
    decision_price: float
    rule_evidence: List[str]
    factor_evidence: List[str]
    regime: str
    confluence: str
    market_status: str
    data_quality: str
    execution_eligibility: bool
    notes: Optional[str] = None


@dataclass
class MetricSampleController:
    """
    Controls statistical truthfulness: never display misleading numbers when N < minimum.
    """
    metric_name: str
    value: Optional[float]
    display_text: str
    sample_size: int
    minimum_required: int
    status: str  # VALID | INSUFFICIENT_DATA


@dataclass
class BacktestComparisonRow:
    """
    Side-by-side distribution comparison between historical backtest and forward paper.
    """
    metric_name: str
    historical_value: str
    forward_value: str
    difference: str
    status: ComparisonStatus
    sample_size: int
    notes: str


@dataclass
class TimelineCheckpoint:
    """
    Milestone on the forward validation journey from Audited to 30 Trades.
    """
    checkpoint_id: str
    name: str
    target_trades: int
    status: str  # COMPLETED | CURRENT | PENDING
    current_trades: int
    summary: str


@dataclass
class ContinuousValidationGate:
    """
    Individual validation gate result among the 9 formal gates.
    """
    gate_name: str
    status: GateDecisionStatus
    metric_value: str
    sample_size: int
    threshold_description: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class RegimeObservationSummary:
    """
    Regime coverage report preserving truth layer (never fake 0% on unobserved regimes).
    """
    regime_name: str
    observation_status: RegimeObservationStatus
    trade_count: int
    signal_count: int
    net_return_pct: Optional[float]
    win_rate_pct: Optional[float]
    max_drawdown_pct: Optional[float]
    display_status: str


@dataclass
class ForwardValidationDecisionReport:
    """
    Comprehensive Phase 12 Research Decision Report for HYP_QUALITY_TREND_01.
    """
    hypothesis_id: str
    hypothesis_name: str
    version: str
    fingerprint: str
    observation_period_days: int
    decision: ResearchDecision
    decision_summary: str
    decision_reasons: List[str]
    trade_count: int
    required_sample_size: int
    progress_pct: float
    signal_count: int
    missed_signal_count: int
    observation_state: ContinuousObservationState
    gates: List[ContinuousValidationGate]
    timeline: List[TimelineCheckpoint]
    backtest_comparison: List[BacktestComparisonRow]
    regime_coverage: List[RegimeObservationSummary]
    metric_controllers: List[MetricSampleController]
    drift_status: str
    survivorship_status: str
    unknowns: List[str]
    next_required_evidence: List[str]
    potential_future_hypotheses: List[str]
    skeptic_audit: Dict[str, List[str]]
