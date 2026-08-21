"""
Paper Engine — Forward Validation Models & Frozen Contracts (Phase 11)
======================================================================
Defines immutable frozen research snapshots, authentic market-data reconciliation,
forward paper trading validation gates, and model drift telemetry.

CRITICAL INVARIANTS:
1. Frozen hypothesis contracts are immutable; any parameter variation requires a new version.
2. Next-bar open execution (signal at bar T close -> execution at bar T+1 open).
3. 7 explicit forward validation gates with zero fabricated numbers.
4. Separate tracking of all statutory transaction friction items.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple


class ForwardValidationState(str, Enum):
    PAPER_NOT_STARTED = "PAPER_NOT_STARTED"
    PAPER_RUNNING = "PAPER_RUNNING"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    PAPER_VALIDATION = "PAPER_VALIDATION"
    PAPER_DEGRADED = "PAPER_DEGRADED"
    PAPER_DRIFT_ALERT = "PAPER_DRIFT_ALERT"
    PAPER_REJECTED = "PAPER_REJECTED"
    PAPER_VALIDATED = "PAPER_VALIDATED"


class GateStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DataFeedStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    UNAVAILABLE = "UNAVAILABLE"


class ReconciliationStatus(str, Enum):
    MATCH = "MATCH"
    MINOR_DISCREPANCY = "MINOR_DISCREPANCY"
    MAJOR_DISCREPANCY = "MAJOR_DISCREPANCY"
    UNAVAILABLE = "UNAVAILABLE"


class ExecutionDriftStatus(str, Enum):
    MATCH = "MATCH"
    MINOR_DRIFT = "MINOR_DRIFT"
    MATERIAL_DRIFT = "MATERIAL_DRIFT"
    EXECUTION_UNAVAILABLE = "EXECUTION_UNAVAILABLE"


class PriceSeriesType(str, Enum):
    ADJUSTED = "ADJUSTED"
    UNADJUSTED = "UNADJUSTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FrozenResearchHypothesis:
    """
    Immutable frozen snapshot of an independently audited research hypothesis.
    Cannot be modified during paper trading.
    """
    hypothesis_id: str
    strategy_id: str
    strategy_version: str
    parameter_values: Dict[str, Any]
    indicator_dependencies: List[str]
    entry_rules: List[str]
    exit_rules: List[str]
    risk_model: str
    holding_period: str
    timeframe: str
    universe: List[str]
    fundamental_factor_definitions: List[str]
    regime_definitions: List[str]
    cost_assumptions: Dict[str, Any]
    slippage_assumptions: Dict[str, Any]
    backtest_dataset_identifier: str
    backtest_date_range: Tuple[str, str]
    audit_certification: str
    audit_timestamp: int
    frozen_timestamp: int
    is_frozen: bool = True


@dataclass
class MarketDataQualityReport:
    """
    Real-time market data feed health and reconciliation report.
    """
    status: DataFeedStatus
    provider: str
    symbol: str
    timeframe: str
    last_timestamp: int
    data_age_seconds: float
    missing_count: int
    duplicate_count: int
    invalid_count: int
    gap_count: int
    price_series_type: PriceSeriesType
    reconciliation: ReconciliationStatus
    reconciliation_notes: str


@dataclass
class ForwardPaperSignal:
    """
    Authentic forward paper signal generated from live market data + frozen hypothesis.
    """
    signal_id: str
    hypothesis_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    signal_timestamp: int
    expected_execution_timestamp: int
    decision_price: float
    rule_evidence: List[str]
    factor_evidence: List[str]
    regime: str
    confluence_state: str
    provider: str
    data_freshness: str
    market_status: str


@dataclass
class PaperJournalEntry:
    """
    Immutable forensic paper trade execution record.
    """
    trade_id: str
    hypothesis_id: str
    symbol: str
    side: str
    quantity: int
    signal_timestamp: int
    entry_timestamp: int
    entry_price: float
    exit_timestamp: Optional[int]
    exit_price: Optional[float]
    exit_reason: Optional[str]
    gross_pnl: float
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    gst: float
    stamp_duty: float
    slippage: float
    total_costs: float
    net_pnl: float
    return_pct: float
    holding_duration_bars: int
    mae: float  # Maximum Adverse Excursion
    mfe: float  # Maximum Favorable Excursion
    regime: str
    technical_evidence: List[str]
    fundamental_evidence: List[str]
    confluence: str
    execution_drift: ExecutionDriftStatus
    data_quality_status: DataFeedStatus


@dataclass
class ValidationGateResult:
    """
    Individual forward validation gate verdict.
    """
    gate_name: str
    status: GateStatus  # PASS | WARNING | FAIL | INSUFFICIENT_DATA
    metric_value: Any
    threshold_description: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class BearishRegimeDiagnostic:
    """
    Research diagnostic isolating performance in Bearish Distribution vs other regimes.
    """
    regime_name: str
    sample_size_trades: int
    net_return_pct: float
    sharpe_ratio: Optional[float]
    max_drawdown_pct: float
    win_rate_pct: float
    cost_drag_pct: float
    is_sufficient_sample: bool


@dataclass
class ForwardValidationReport:
    """
    Comprehensive Phase 11 production forward paper trading validation report.
    """
    hypothesis_id: str
    hypothesis_name: str
    frozen_version: str
    validation_state: ForwardValidationState
    validation_timestamp: int
    sample_size_trades: int
    paper_win_rate_pct: Optional[float]
    paper_profit_factor: Optional[float]
    paper_net_pnl: float
    paper_sharpe: Optional[float]
    paper_max_drawdown_pct: float
    paper_cost_drag_pct: float
    backtest_cagr_pct: float
    backtest_sharpe: float
    drift_status: str  # NO_MATERIAL_DRIFT | WATCH | MATERIAL_DRIFT | MODEL_DRIFT_ALERT
    gates: List[ValidationGateResult]
    bearish_diagnostic: List[BearishRegimeDiagnostic]
    data_quality: MarketDataQualityReport
    recent_signals: List[ForwardPaperSignal]
    recent_trades: List[PaperJournalEntry]
    known_limitations: List[str]
    skeptic_audit_summary: Dict[str, List[str]]
