"""
Signal Intelligence Engine — Data Models
=========================================
All Pydantic models and data structures for the signal system.

Design principles:
- Every field has a clear semantic meaning
- Provenance is tracked on every data-bearing field
- No optional fields that silently disappear (use explicit UNAVAILABLE)
- All monetary values in INR
- All timestamps in ISO format or Unix epoch (consistent per context)
"""
import uuid
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"
    WATCHLIST = "WATCHLIST"


class SignalType(str, Enum):
    # Equity
    EQUITY_LONG = "EQUITY_LONG"
    EQUITY_SHORT = "EQUITY_SHORT"
    # Futures
    BUY_FUTURE = "BUY_FUTURE"
    SELL_FUTURE = "SELL_FUTURE"
    # Options
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    SELL_CALL = "SELL_CALL"
    SELL_PUT = "SELL_PUT"
    OPTION_SPREAD = "OPTION_SPREAD"
    # None
    NO_TRADE = "NO_TRADE"


class SignalState(str, Enum):
    CANDIDATE = "CANDIDATE"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    QUALIFIED = "QUALIFIED"
    TRIGGERED = "TRIGGERED"
    ACTIVE = "ACTIVE"
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"
    TARGET_3 = "TARGET_3"
    TARGET_REACHED = "TARGET_REACHED"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SignalQualityGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    NO_TRADE = "NO TRADE"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    INDEX = "INDEX"


class DataProvenance(str, Enum):
    RAW_AUTHENTIC_DATA = "RAW_AUTHENTIC_DATA"
    HISTORICAL_RESEARCH_RESULT = "HISTORICAL_RESEARCH_RESULT"
    SIMULATED = "SIMULATED"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"


class ValidationGateResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


class StrategyVoteDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Component Models
# ---------------------------------------------------------------------------

class StrategyVote(BaseModel):
    """A single strategy's vote on a candidate instrument."""
    strategy_id: str
    strategy_name: str
    category: str
    direction: StrategyVoteDirection
    confidence: float = Field(ge=0, le=100, description="Strategy confidence 0-100")
    strength: float = Field(ge=0, le=100, description="Signal strength 0-100")
    reason_codes: List[str] = Field(default_factory=list)
    rules_passing: int = 0
    rules_total: int = 0
    is_correlated_with: List[str] = Field(default_factory=list,
        description="Strategy IDs this strategy is correlated with (same evidence family)")


class StrategyConsensus(BaseModel):
    """Aggregated consensus across all strategy votes."""
    long_votes: int = 0
    short_votes: int = 0
    neutral_votes: int = 0
    unavailable_votes: int = 0
    total_eligible: int = 0
    # Correlation-adjusted counts (independent evidence families)
    independent_long_evidence: int = 0
    independent_short_evidence: int = 0
    # Dominant direction
    dominant_direction: StrategyVoteDirection = StrategyVoteDirection.NEUTRAL
    consensus_confidence: float = 0.0
    # Descriptions
    consensus_label: str = "MIXED"
    correlation_warning: Optional[str] = None


class TimeframeAnalysis(BaseModel):
    """Analysis for a single timeframe."""
    timeframe: str
    trend: str = "UNAVAILABLE"  # BULLISH, BEARISH, NEUTRAL, UNAVAILABLE
    trend_strength: float = 0.0  # 0-100
    momentum: str = "UNAVAILABLE"  # STRONG, MODERATE, WEAK, REVERSAL, UNAVAILABLE
    entry_quality: str = "UNAVAILABLE"  # IDEAL, ACCEPTABLE, POOR, UNAVAILABLE
    candles_available: int = 0
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    is_available: bool = True


class MultiTimeframeResult(BaseModel):
    """Multi-timeframe analysis result."""
    timeframes: List[TimeframeAnalysis] = Field(default_factory=list)
    alignment_score: float = 0.0  # 0-100
    alignment_label: str = "UNAVAILABLE"  # CONFIRMED, PARTIAL, CONFLICTING, UNAVAILABLE
    primary_trend: str = "UNKNOWN"
    execution_timeframe: str = "5m"
    confirmation_message: str = ""
    conflict_warnings: List[str] = Field(default_factory=list)


class ConfluenceResult(BaseModel):
    """Result from the confluence engine."""
    raw_long_votes: int = 0
    raw_short_votes: int = 0
    raw_neutral_votes: int = 0
    # After correlation adjustment
    independent_long_signals: int = 0
    independent_short_signals: int = 0
    # Evidence categories confirmed
    trend_evidence: Optional[str] = None        # BULLISH / BEARISH / MIXED / NONE
    momentum_evidence: Optional[str] = None
    volume_evidence: Optional[str] = None
    structure_evidence: Optional[str] = None
    volatility_evidence: Optional[str] = None
    # Scores
    confluence_score: float = 0.0  # 0-100
    confluence_direction: SignalDirection = SignalDirection.NO_TRADE
    confluence_label: str = "INSUFFICIENT"
    # Correlation analysis
    correlated_strategy_clusters: List[List[str]] = Field(default_factory=list)
    correlation_discount: float = 0.0  # How much we discounted for correlation
    correlation_warning: Optional[str] = None
    # Meta
    strategies_evaluated: int = 0
    strategies_unavailable: int = 0


class StopLossResult(BaseModel):
    """Computed stop loss with method explanation."""
    price: float
    method: str  # ATR_STRUCTURAL | SWING_LOW | SUPPORT_LEVEL | PERCENTAGE
    method_description: str = ""  # Human-readable: "1.5x ATR below structural support at ₹X"
    atr_value: Optional[float] = None
    structural_level: Optional[float] = None
    risk_per_share: float = 0.0
    is_deterministic: bool = True


class TargetLevel(BaseModel):
    """A single price target."""
    level: int  # 1, 2, or 3
    price: float
    method: str  # RISK_REWARD | RESISTANCE | ATR_PROJECTION | FIBONACCI | PREVIOUS_HIGH
    method_description: str
    expected_rr: float = 0.0


class PositionSizing(BaseModel):
    """Risk-based position sizing result."""
    method: str  # FIXED_RISK | PERCENTAGE | FIXED_QTY
    capital: float
    risk_per_trade_pct: float
    max_risk_amount: float
    entry_price: float
    stop_price: float
    risk_per_share: float
    quantity: int
    capital_required: float
    maximum_loss: float
    sizing_notes: Optional[str] = None
    lot_size: Optional[int] = None  # For F&O


class ValidationGate(BaseModel):
    """Result of a single validation gate."""
    gate_id: str
    gate_name: str
    gate_type: str  # HARD | SOFT
    result: ValidationGateResult
    reason: Optional[str] = None
    actual_value: Optional[Any] = None
    threshold_value: Optional[Any] = None
    evidence: Optional[str] = None


class DataSourceRecord(BaseModel):
    """Provenance record for a specific data input."""
    data_type: str  # MARKET_DATA | INDICATOR | STRATEGY | REGIME | RESEARCH
    source: str
    provider: str
    timestamp: Optional[str] = None
    freshness: str  # LIVE | RECENT | STALE | UNAVAILABLE
    provenance: DataProvenance = DataProvenance.UNAVAILABLE


# ---------------------------------------------------------------------------
# Core Signal Models
# ---------------------------------------------------------------------------

class SignalDecision(BaseModel):
    """
    The complete, authoritative signal object.
    Every qualified signal must contain all required fields.
    Every NO_TRADE must contain explicit rejection reasons.
    """
    # Identity
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    symbol: str
    exchange: str = "NSE"
    instrument_id: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    direction: SignalDirection
    signal_type: SignalType = SignalType.NO_TRADE
    timeframe: str = "15m"
    state: SignalState = SignalState.CANDIDATE

    # Version Freeze Identity
    strategy_version: str = "2026.1.0-FROZEN"
    signal_engine_version: str = "2026.1.0-CERTIFIED"
    configuration_hash: str = "d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e"
    git_commit: str = "96451be6a256dfeb81f8f3c3066eb4cb9ffdbb53"

    # Timing & Market Tick Observation
    market_timestamp: Optional[float] = None
    data_age_ms: Optional[float] = None
    spread: Optional[float] = None

    # Quality & Calibration
    quality_grade: SignalQualityGrade = SignalQualityGrade.NO_TRADE
    opportunity_score: float = Field(ge=0, le=100, default=0.0)
    confidence: float = Field(ge=0, le=100, default=0.0)
    is_heuristic_confidence: bool = True
    calibrated_probability: Optional[float] = None
    historical_win_rate: Optional[float] = None   # From research engine
    historical_expectancy: Optional[float] = None  # In R multiples
    historical_trades_sample: Optional[int] = None
    effective_strategy_count: int = 0

    # Market Regime Dimensions
    volatility_regime: Optional[str] = None
    trend_regime: Optional[str] = None
    breadth_regime: Optional[str] = None
    liquidity_regime: Optional[str] = None

    # Entry
    entry: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    entry_notes: Optional[str] = None

    # Stop Loss
    stop_loss: Optional[StopLossResult] = None

    # Targets
    targets: List[TargetLevel] = Field(default_factory=list)
    risk_reward: Optional[float] = None  # To first target

    # Position Sizing
    position_size: Optional[PositionSizing] = None

    # Market Context
    regime: str = "UNKNOWN"
    regime_confidence: float = 0.0
    regime_compatible: bool = False
    vix_level: Optional[float] = None

    # Strategy Evidence
    strategy_votes: List[StrategyVote] = Field(default_factory=list)
    strategy_consensus: Optional[StrategyConsensus] = None
    strategy_ids: List[str] = Field(default_factory=list)
    strategy_versions: List[str] = Field(default_factory=list)

    # Multi-Timeframe
    mtf_alignment: Optional[MultiTimeframeResult] = None

    # Confluence
    confluence_result: Optional[ConfluenceResult] = None

    # Validation Gates
    validation_gates: List[ValidationGate] = Field(default_factory=list)
    hard_gates_passed: int = 0
    hard_gates_total: int = 0
    soft_gates_passed: int = 0

    # Explanation
    why_reasons: List[str] = Field(default_factory=list,
        description="Human-readable list of reasons this signal qualified (✓/✗)")
    invalidation_conditions: List[str] = Field(default_factory=list,
        description="Explicit conditions that would cancel this signal")
    rejection_reasons: List[str] = Field(default_factory=list,
        description="For NO_TRADE: specific reasons for rejection")

    # Liquidity & Data Quality
    liquidity_score: float = 0.0
    data_quality: str = "UNAVAILABLE"
    provenance: DataProvenance = DataProvenance.UNAVAILABLE
    data_sources: List[DataSourceRecord] = Field(default_factory=list)

    # Lifecycle
    expiry: Optional[str] = None
    expiry_condition: str = "Valid until end of session"
    candles_used: int = 0

    # F&O and Transaction Costs
    futures_decision: Optional[Dict[str, Any]] = None
    options_decision: Optional[Dict[str, Any]] = None
    transaction_cost_estimate: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(use_enum_values=True)


class RejectionRecord(BaseModel):
    """Records a rejected candidate with full explanation."""
    symbol: str
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    gate_failed: str
    gate_type: str  # HARD | SOFT
    reason: str
    evidence: Optional[str] = None
    actual_value: Optional[Any] = None
    threshold_value: Optional[Any] = None
    validation_gates: List[ValidationGate] = Field(default_factory=list)
    partial_score: float = 0.0  # Score before rejection
    would_have_been: str = ""  # LONG/SHORT based on strategy consensus
    why_reasons_so_far: List[str] = Field(default_factory=list)
    actionable_advice: Optional[str] = None
    candidate_id: Optional[str] = None
    strategy_version: str = "2026.1.0-FROZEN"
    configuration_hash: str = "d3e94bea101d71505e19c20c2086da9cbf629cdce04c46044eb5a62d9cace94e"
    git_commit: str = "96451be6a256dfeb81f8f3c3066eb4cb9ffdbb53"
    market_timestamp: Optional[float] = None


class CandidateRecord(BaseModel):
    """A market instrument that has passed initial screening."""
    symbol: str
    exchange: str = "NSE"
    asset_class: AssetClass = AssetClass.EQUITY
    priority_score: float = 0.0  # Initial priority before full evaluation
    screening_reasons: List[str] = Field(default_factory=list)
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    rvol: Optional[float] = None  # Relative volume


class ScannerPipelineStats(BaseModel):
    """Pipeline statistics showing how many instruments were evaluated at each stage."""
    universe_size: int = 0
    data_valid: int = 0
    initial_screened: int = 0
    trend_candidates: int = 0
    momentum_candidates: int = 0
    breakout_candidates: int = 0
    liquidity_pass: int = 0
    rr_pass: int = 0
    strategy_confluence_pass: int = 0
    qualified: int = 0
    scan_duration_ms: float = 0.0
    scan_timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class ScannerResult(BaseModel):
    """Complete result from the market-wide opportunity scanner."""
    pipeline_stats: ScannerPipelineStats = Field(default_factory=ScannerPipelineStats)
    qualified_signals: List[SignalDecision] = Field(default_factory=list)
    watchlist_signals: List[SignalDecision] = Field(default_factory=list)
    rejected_records: List[RejectionRecord] = Field(default_factory=list)
    market_regime: str = "UNKNOWN"
    market_regime_confidence: float = 0.0
    scanner_universe: str = "NIFTY50"
    scan_timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    data_provenance: DataProvenance = DataProvenance.UNAVAILABLE
    is_market_open: bool = False


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------

class SignalEngineConfig(BaseModel):
    """Configuration for the signal engine. All parameters are documented."""
    # Universe
    universe: List[str] = Field(
        default_factory=lambda: [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
            "SBIN.NS", "TATAMOTORS.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
            "LT.NS", "HINDUNILVR.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
            "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "NESTLEIND.NS", "TITAN.NS",
        ],
        description="Market universe to scan"
    )

    # Timeframes for multi-timeframe analysis
    mtf_timeframes: List[str] = Field(
        default=["1D", "1h", "15m", "5m"],
        description="Timeframes for multi-timeframe analysis (high to low)"
    )
    primary_timeframe: str = Field(default="15m", description="Primary signal timeframe")

    # Risk/Reward Gates
    min_risk_reward: float = Field(default=1.5, description="Minimum R:R to qualify (HARD GATE)")
    min_confidence: float = Field(default=60.0, description="Minimum confidence to qualify")
    min_opportunity_score: float = Field(default=60.0, description="Minimum score for grade C")

    # Position Sizing
    capital: float = Field(default=1000000.0, description="Capital base (INR)")
    risk_per_trade_pct: float = Field(default=1.0, description="Max risk per trade as % of capital")
    max_positions: int = Field(default=5, description="Max concurrent positions")
    max_portfolio_exposure_pct: float = Field(default=60.0, description="Max % of capital in positions")

    # Quality Thresholds for Grades
    a_plus_score_threshold: float = Field(default=90.0, description="Minimum score for A+ grade")
    a_score_threshold: float = Field(default=80.0, description="Minimum score for A grade")
    b_score_threshold: float = Field(default=70.0, description="Minimum score for B grade")
    c_score_threshold: float = Field(default=60.0, description="Minimum score for C grade")

    # Stop Loss Engine
    stop_atr_multiple: float = Field(default=1.5, description="ATR multiple for stop loss")
    max_stop_pct: float = Field(default=5.0, description="Max stop distance as % of entry price")

    # Target Engine
    target_1_rr: float = Field(default=1.5, description="R:R for Target 1")
    target_2_rr: float = Field(default=2.5, description="R:R for Target 2")
    target_3_rr: float = Field(default=4.0, description="R:R for Target 3")

    # Data Freshness
    max_data_age_minutes: float = Field(default=30.0, description="Max candle age in minutes (HARD GATE)")
    max_quote_age_seconds: float = Field(default=300.0, description="Max quote age in seconds (HARD GATE)")

    # Liquidity
    min_volume_inr: float = Field(default=5000000.0, description="Minimum daily volume in INR (HARD GATE)")
    min_rvol: float = Field(default=0.5, description="Minimum relative volume vs 20-day avg")

    # Confluence
    min_independent_long_signals: int = Field(default=2, description="Minimum independent evidence families for LONG")
    min_independent_short_signals: int = Field(default=2, description="Min independent evidence for SHORT")

    # Strategy Filter
    blocked_strategies: List[str] = Field(
        default_factory=list,
        description="Strategy IDs to exclude from signal generation"
    )

    # Signal Lifecycle
    signal_expiry_candles: int = Field(default=3, description="Signal expires after this many primary-timeframe candles")
    deduplicate_signals: bool = Field(default=True, description="Prevent duplicate signals for same setup")


# ---------------------------------------------------------------------------
# Scoring Weight Configuration
# ---------------------------------------------------------------------------

class ScoringWeights(BaseModel):
    """
    Configurable weights for the opportunity scoring engine.
    All weights must sum to 100.
    These weights are DOCUMENTED and not arbitrary.
    """
    trend_alignment: float = Field(default=15.0, description="Trend direction alignment across timeframes")
    momentum_quality: float = Field(default=10.0, description="Momentum indicator quality (RSI, ROC, Stochastic)")
    volume_confirmation: float = Field(default=10.0, description="Volume expansion and OBV confirmation")
    market_structure: float = Field(default=10.0, description="S/R levels, swing structure, breakout quality")
    volatility_suitability: float = Field(default=8.0, description="ATR suitable for stop placement")
    regime_compatibility: float = Field(default=12.0, description="Strategy performance in current regime")
    strategy_consensus: float = Field(default=15.0, description="Correlation-adjusted strategy agreement")
    mtf_alignment: float = Field(default=10.0, description="Multi-timeframe direction alignment")
    liquidity_quality: float = Field(default=5.0, description="Volume and spread quality")
    risk_reward_quality: float = Field(default=10.0, description="R:R above minimum and quality")
    historical_edge: float = Field(default=5.0, description="Historical performance in comparable setups")

    def validate_sum(self) -> bool:
        """Returns True if weights sum to 100 (within float tolerance)."""
        total = (
            self.trend_alignment + self.momentum_quality + self.volume_confirmation +
            self.market_structure + self.volatility_suitability + self.regime_compatibility +
            self.strategy_consensus + self.mtf_alignment + self.liquidity_quality +
            self.risk_reward_quality + self.historical_edge
        )
        return abs(total - 100.0) < 0.01
