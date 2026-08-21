"""
Research Command Center — Orchestration Models & Contracts (Phase 13)
====================================================================
Defines the presentation/orchestration layer models for the unified Live Quant
Research Command Center. Connects all 20 technical strategies, point-in-time
fundamentals, confluence, historical analogues, paper validation, and Copilot.

CRITICAL INVARIANTS:
1. Orchestration only; zero ad-hoc indicator recalculations.
2. Rule coverage factual counts (NEVER fake confidence/profit probabilities).
3. Confluence explicitly labeled as RESEARCH CLASSIFICATION (NOT buy signals).
4. Evidence hierarchy (Levels 1 to 7) clearly demarcated.
5. Historical analogues labeled as PAST OBSERVATIONS (NOT predictions).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class ResearchWorkflowStatus(str, Enum):
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    RESEARCH_INTEREST = "RESEARCH_INTEREST"
    MULTI_STRATEGY_CONFLUENCE = "MULTI_STRATEGY_CONFLUENCE"
    FUNDAMENTAL_SUPPORT = "FUNDAMENTAL_SUPPORT"
    PAPER_TESTING = "PAPER_TESTING"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    PAPER_VALIDATED = "PAPER_VALIDATED"
    PAPER_DEGRADED = "PAPER_DEGRADED"
    PAPER_REJECTED = "PAPER_REJECTED"


@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: str
    current_price: float
    change_pct: float
    market_regime: str
    volatility_state: str
    trend_state: str
    volume_state: str
    technical_freshness: str
    fundamental_freshness: str
    provider: str
    timestamp: int
    market_status: str


@dataclass
class StrategyMatrixItem:
    strategy_id: str
    strategy_name: str
    category: str
    description: str
    state: str  # ACTIVE | PARTIAL | INACTIVE | CONFLICTED | UNAVAILABLE
    passing_rules: int
    total_rules: int
    rule_coverage_pct: float
    tags: List[str]
    rule_evaluations: List[Dict[str, Any]]
    feature_vector: Dict[str, float]


@dataclass
class StrategyAlignmentScore:
    active_count: int
    partial_count: int
    inactive_count: int
    conflicted_count: int
    unavailable_count: int
    total_strategies: int
    passing_rules_total: int
    total_rules_count: int
    rule_coverage_pct: float
    label: str = "RULE COVERAGE (Factual count, NOT probability of profit)"


@dataclass
class ConfluenceClassification:
    technical_state: str
    fundamental_state: str
    confluence_quadrant: str
    research_classification: str
    disclaimer: str = "RESEARCH CLASSIFICATION (NOT a buy/sell signal, NOT probability of profit)"


@dataclass
class FundamentalMetricItem:
    metric_name: str
    raw_value: Optional[float]
    display_value: str
    unit: str
    source: str
    publication_date: str
    data_status: str


@dataclass
class HistoricalAnalogueResult:
    total_similar_observations: int
    matched_regime: str
    matched_technical: str
    matched_fundamental: str
    forward_1_bar_median: float
    forward_3_bar_median: float
    forward_5_bar_median: float
    forward_10_bar_median: float
    forward_20_bar_median: float
    mae_median: float
    mfe_median: float
    win_rate_forward_5: float
    disclaimer: str = "HISTORICAL ANALOGUE EVIDENCE (NOT expected return, NOT prediction)"


@dataclass
class ContradictionAnalysis:
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    unknowns: List[str]


@dataclass
class PaperValidationStatusCard:
    hypothesis_id: str
    version: str
    decision: str
    trade_count: int
    required_sample_size: int
    progress_pct: float
    fingerprint: str
    survivorship_warning: str


@dataclass
class EvidenceHierarchy:
    level_1_live_market: Dict[str, Any]
    level_2_pit_fundamentals: Dict[str, Any]
    level_3_deterministic_strategies: Dict[str, Any]
    level_4_historical_research: Dict[str, Any]
    level_5_backtest: Dict[str, Any]
    level_6_forward_paper: Dict[str, Any]
    level_7_model_interpretation: Dict[str, Any]


@dataclass
class EvidenceTimelineEvent:
    time: str
    event_type: str
    source: str
    evidence: str


@dataclass
class WatchlistItem:
    symbol: str
    company_name: str
    price: float
    change_pct: float
    regime: str
    active_strategies_count: int
    technical_state: str
    fundamental_state: str
    confluence: str
    research_status: ResearchWorkflowStatus
    data_freshness: str


@dataclass
class CrossStockComparisonRow:
    symbol: str
    price: float
    regime: str
    active_strategies: int
    rule_coverage_pct: float
    roe: Optional[float]
    pe: Optional[float]
    technical_state: str
    fundamental_state: str
    research_status: str


@dataclass
class CommandCenterSnapshot:
    market: MarketSnapshot
    strategies: List[StrategyMatrixItem]
    alignment: StrategyAlignmentScore
    confluence: ConfluenceClassification
    fundamentals: List[FundamentalMetricItem]
    historical_analogues: HistoricalAnalogueResult
    contradictions: ContradictionAnalysis
    paper_status: PaperValidationStatusCard
    evidence_hierarchy: EvidenceHierarchy
    timeline: List[EvidenceTimelineEvent]
    watchlist: List[WatchlistItem]
    cross_stock: List[CrossStockComparisonRow]
    provenance: Dict[str, Any] = field(default_factory=dict)
