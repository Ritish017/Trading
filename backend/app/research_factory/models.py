"""
Research Factory — Canonical Models & Hypothesis Contracts (Phase 9)
=====================================================================
Defines deterministic Research Hypotheses, multi-dimensional validation
scorecards, structured failure reasons, and promotion gate criteria.

CRITICAL INVARIANTS:
1. Every hypothesis is a deterministic combination of existing canonical components.
2. Multiple-testing risk factor K is strictly tracked.
3. Independent validation dimensions without arbitrary aggregated scores.
4. Structured failure catalog for every rejected candidate.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class HypothesisCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    FUNDAMENTAL = "FUNDAMENTAL"
    FACTOR = "FACTOR"
    REGIME = "REGIME"
    CONFLUENCE = "CONFLUENCE"
    MULTI_FACTOR = "MULTI_FACTOR"


class HypothesisStatus(str, Enum):
    DRAFT = "DRAFT"
    RESEARCHING = "RESEARCHING"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"
    PAPER_TESTING = "PAPER_TESTING"
    ACCEPTED_FOR_CONTINUED_RESEARCH = "ACCEPTED_FOR_CONTINUED_RESEARCH"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class RejectionReason(str, Enum):
    OVERFIT = "OVERFIT"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    OOS_FAILURE = "OOS_FAILURE"
    HIGH_COST_DRAG = "HIGH_COST_DRAG"
    ISOLATED_PEAK = "ISOLATED_PEAK"
    REGIME_DEPENDENT = "REGIME_DEPENDENT"
    SYMBOL_DEPENDENT = "SYMBOL_DEPENDENT"
    REDUNDANT = "REDUNDANT"
    MULTIPLE_TESTING_RISK = "MULTIPLE_TESTING_RISK"
    DATA_LIMITATION = "DATA_LIMITATION"
    PAPER_DRIFT = "PAPER_DRIFT"


@dataclass
class ResearchHypothesis:
    """
    Formal quantitative hypothesis contract for empirical research.
    """
    hypothesis_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: HypothesisCategory = HypothesisCategory.CONFLUENCE
    technical_dependencies: List[str] = field(default_factory=list)   # Strategy IDs e.g. ["EMA_TREND_MOMENTUM"]
    fundamental_dependencies: List[str] = field(default_factory=list) # Factor IDs e.g. ["PROFITABILITY_ROE"]
    regime_filter: Optional[str] = None                                # e.g. "TRENDING_BULLISH"
    entry_conditions: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    timeframe: str = "1D"
    universe: List[str] = field(default_factory=lambda: ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"])
    rebalance_frequency: str = "QUARTERLY"
    position_sizing: str = "EQUAL_WEIGHT"                             # EQUAL_WEIGHT | VOLATILITY_SCALED
    cost_model: str = "INDIAN_EQUITY_REALISTIC"
    created_timestamp: int = 0
    status: HypothesisStatus = HypothesisStatus.DRAFT
    rejection_reasons: List[RejectionReason] = field(default_factory=list)
    rejection_notes: Optional[str] = None
    k_tested: int = 1


@dataclass
class OOSValidationResult:
    is_return_pct: float
    oos_return_pct: float
    is_sharpe: float
    oos_sharpe: float
    is_max_drawdown_pct: float
    oos_max_drawdown_pct: float
    is_trade_count: int
    oos_trade_count: int
    oos_degradation_pct: float
    is_validated: bool


@dataclass
class CrossSymbolDispersionResult:
    median_return_pct: float
    mean_return_pct: float
    iqr_return_pct: float
    std_return_pct: float
    winning_symbols_count: int
    losing_symbols_count: int
    best_symbol: str
    worst_symbol: str
    is_generalizable: bool


@dataclass
class RegimeStressResult:
    regime_returns: Dict[str, float]
    regime_sharpes: Dict[str, float]
    regime_win_rates: Dict[str, float]
    regime_trade_counts: Dict[str, int]
    is_regime_resilient: bool
    weakest_regime: str


@dataclass
class CostStressResult:
    zero_friction_cagr: float
    normal_friction_cagr: float
    high_friction_cagr: float
    triple_friction_cagr: float
    cost_drag_pct: float
    is_cost_resilient: bool


@dataclass
class ParameterNeighborhoodResult:
    plateau_stability: str  # STABLE_PLATEAU | MODERATE_CLIFF | ISOLATED_PEAK
    optimal_config: Dict[str, Any]
    neighborhood_variance_pct: float
    is_robust: bool


@dataclass
class ValidationScorecard:
    """
    Independent multi-dimensional empirical evidence scorecard for a hypothesis.
    """
    hypothesis_id: str
    hypothesis_name: str
    sample_size: int
    benchmark_beat_pct: float
    oos_result: OOSValidationResult
    cross_symbol_result: CrossSymbolDispersionResult
    regime_result: RegimeStressResult
    cost_result: CostStressResult
    parameter_result: ParameterNeighborhoodResult
    redundancy_index: float  # 0.0 (unique) to 1.0 (redundant)
    multiple_testing_k: int
    multiple_testing_risk: str  # LOW | MODERATE | ELEVATED
    research_decay_status: str  # STABLE | DEGRADING | IMPROVING
    overall_recommendation: str # PROMOTABLE_CANDIDATE | REJECT | FURTHER_TESTING_REQUIRED
    falsification_criteria: List[str] = field(default_factory=list)
