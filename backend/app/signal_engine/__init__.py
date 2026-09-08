"""
APEX Signal Intelligence Engine
================================
The core Signal Intelligence Engine evaluates the entire eligible market universe
through a deterministic, multi-stage validation pipeline and produces only
qualified, explainable, auditable trade opportunities.
"""
from backend.app.signal_engine.models import (
    AssetClass,
    CandidateRecord,
    ConfluenceResult,
    DataProvenance,
    DataSourceRecord,
    MultiTimeframeResult,
    PositionSizing,
    RejectionRecord,
    ScannerPipelineStats,
    ScannerResult,
    SignalDecision,
    SignalDirection,
    SignalEngineConfig,
    SignalQualityGrade,
    SignalState,
    SignalType,
    StopLossResult,
    StrategyConsensus,
    StrategyVote,
    StrategyVoteDirection,
    TargetLevel,
    TimeframeAnalysis,
    ValidationGate,
    ValidationGateResult,
)
from backend.app.signal_engine.candidate_generator import CandidateGenerator, candidate_generator
from backend.app.signal_engine.confluence_engine import ConfluenceEngine, confluence_engine
from backend.app.signal_engine.multi_timeframe_engine import MultiTimeframeEngine, multi_timeframe_engine
from backend.app.signal_engine.no_trade_engine import NoTradeEngine, no_trade_engine
from backend.app.signal_engine.position_sizing_engine import PositionSizingEngine, position_sizing_engine
from backend.app.signal_engine.scanner import OpportunityScanner, MAX_CONCURRENT_EVALS
from backend.app.signal_engine.scoring_engine import ScoringEngine, scoring_engine
OpportunityScoringEngine = ScoringEngine
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.signal_engine.signal_store import SignalStore, signal_store
from backend.app.signal_engine.stop_target_engine import (
    StopLossEngine,
    TargetEngine,
    stop_loss_engine,
    target_engine,
)

__all__ = [
    # Models
    "AssetClass",
    "CandidateRecord",
    "ConfluenceResult",
    "DataProvenance",
    "DataSourceRecord",
    "MultiTimeframeResult",
    "PositionSizing",
    "RejectionRecord",
    "ScannerPipelineStats",
    "ScannerResult",
    "SignalDecision",
    "SignalDirection",
    "SignalEngineConfig",
    "SignalQualityGrade",
    "SignalState",
    "SignalType",
    "StopLossResult",
    "StrategyConsensus",
    "StrategyVote",
    "StrategyVoteDirection",
    "TargetLevel",
    "TimeframeAnalysis",
    "ValidationGate",
    "ValidationGateResult",
    # Engines & Singletons
    "CandidateGenerator",
    "candidate_generator",
    "ConfluenceEngine",
    "confluence_engine",
    "MultiTimeframeEngine",
    "multi_timeframe_engine",
    "NoTradeEngine",
    "no_trade_engine",
    "OpportunityScanner",
    "OpportunityScoringEngine",
    "scoring_engine",
    "PositionSizingEngine",
    "position_sizing_engine",
    "SignalStore",
    "signal_store",
    "StopLossEngine",
    "TargetEngine",
    "stop_loss_engine",
    "target_engine",
    "evaluate_candidate_signal",
    "MAX_CONCURRENT_EVALS",
    # F&O and Costs
    "TransactionCostCalculator",
    "AssetType",
    "CostBreakdown",
    "FuturesEngine",
    "FuturesDecision",
    "OptionsEngine",
    "OptionDecision",
    "OptionContract",
    "OptionAction",
    "OptionType",
    # Lifecycle, Outcome, Performance, Calibration & Walk-Forward
    "SignalLifecycleManager",
    "lifecycle_manager",
    "InvalidStateTransitionError",
    "OutcomeEngine",
    "outcome_engine",
    "SignalOutcome",
    "PerformanceEngine",
    "performance_engine",
    "PerformanceMetrics",
    "CalibrationEngine",
    "calibration_engine",
    "CalibrationBucket",
    "CalibrationReport",
    "WalkForwardEngine",
    "walk_forward_engine",
    "WalkForwardResult",
    "RobustnessStressResult",
]

from backend.app.signal_engine.transaction_cost import (
    TransactionCostCalculator,
    AssetType,
    CostBreakdown,
)
from backend.app.signal_engine.futures_engine import (
    FuturesEngine,
    FuturesDecision,
)
from backend.app.signal_engine.options_engine import (
    OptionsEngine,
    OptionDecision,
    OptionContract,
    OptionAction,
    OptionType,
)
from backend.app.signal_engine.lifecycle import (
    SignalLifecycleManager,
    lifecycle_manager,
    InvalidStateTransitionError,
)
from backend.app.signal_engine.outcome_engine import (
    OutcomeEngine,
    outcome_engine,
    SignalOutcome,
)
from backend.app.signal_engine.performance_engine import (
    PerformanceEngine,
    performance_engine,
    PerformanceMetrics,
)
from backend.app.signal_engine.calibration_engine import (
    CalibrationEngine,
    calibration_engine,
    CalibrationBucket,
    CalibrationReport,
)
from backend.app.signal_engine.walk_forward import (
    WalkForwardEngine,
    walk_forward_engine,
    WalkForwardResult,
    RobustnessStressResult,
)
