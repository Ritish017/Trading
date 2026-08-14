from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time

class DataFreshness(str, Enum):
    LIVE = "LIVE"                  # < 15 seconds old
    RECENT = "RECENT"              # < 2 minutes old
    STALE = "STALE"                # > 5 minutes old
    UNAVAILABLE = "UNAVAILABLE"    # Missing or unconfigured

class MarketRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    COMPRESSION = "COMPRESSION"
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    NEUTRAL_CONSOLIDATION = "NEUTRAL_CONSOLIDATION"

class AttentionClassification(str, Enum):
    NOISE = "NOISE"                # 0 - 30
    MONITOR = "MONITOR"            # 30 - 50
    INTERESTING = "INTERESTING"    # 50 - 70
    IMPORTANT = "IMPORTANT"        # 70 - 85
    CRITICAL = "CRITICAL"          # 85 - 100

class ImportanceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SignalStance(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNAVAILABLE = "UNAVAILABLE"

# --- Factual Domain Snapshots ---

class MarketSnapshot(BaseModel):
    symbol: str
    exchange: str = "NSE"
    timestamp: float = Field(default_factory=time.time)
    ltp: float
    open: float
    high: float
    low: float
    previous_close: float
    volume: int
    vwap: float
    change: float
    change_percent: float
    freshness: DataFreshness = DataFreshness.LIVE
    source: str = "NSE_FEED"

class TechnicalSnapshot(BaseModel):
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    atr_14: Optional[float] = None
    adx_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    relative_volume: Optional[float] = None
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)
    freshness: DataFreshness = DataFreshness.LIVE

class DerivativeSnapshot(BaseModel):
    futures_price: Optional[float] = None
    futures_oi: Optional[float] = None
    futures_oi_change: Optional[float] = None
    basis: Optional[float] = None
    pcr: Optional[float] = None
    max_pain: Optional[float] = None
    call_oi_total: Optional[float] = None
    put_oi_total: Optional[float] = None
    call_oi_change: Optional[float] = None
    put_oi_change: Optional[float] = None
    implied_volatility: Optional[float] = None
    option_walls: Dict[str, Any] = Field(default_factory=dict)
    oi_pattern: Optional[str] = None # Long Buildup, Short Covering, Short Buildup, Long Unwinding
    freshness: DataFreshness = DataFreshness.LIVE

class NewsSnapshot(BaseModel):
    id: str
    headline: str
    source: str
    published_at: str
    url: Optional[str] = None
    sentiment: str = "Neutral" # Positive, Neutral, Negative
    sentiment_confidence: float = 0.8
    entities: List[str] = Field(default_factory=list)
    sectors: List[str] = Field(default_factory=list)
    event_type: str = "GENERAL" # EARNINGS, REGULATORY, ORDER_WIN, CORPORATE_ACTION, GENERAL
    freshness: DataFreshness = DataFreshness.LIVE

class SectorSnapshot(BaseModel):
    sector_name: str
    change_percent: float
    relative_strength: float # vs NIFTY 50
    breadth_advances: int
    breadth_declines: int
    leaders: List[str] = Field(default_factory=list)
    laggards: List[str] = Field(default_factory=list)
    freshness: DataFreshness = DataFreshness.LIVE

class MacroSnapshot(BaseModel):
    nifty_50: float
    nifty_change_pct: float
    bank_nifty: float
    bank_nifty_change_pct: float
    india_vix: float
    india_vix_change_pct: float
    brent_crude_usd: Optional[float] = 84.50
    usd_inr: Optional[float] = 83.95
    gold_inr: Optional[float] = 71200.0
    global_sentiment: str = "Neutral" # Risk-On, Neutral, Risk-Off
    freshness: DataFreshness = DataFreshness.LIVE

class InstitutionalSnapshot(BaseModel):
    fii_cash_net_cr: float
    dii_cash_net_cr: float
    fii_index_futures_cr: Optional[float] = None
    fii_index_options_cr: Optional[float] = None
    fii_stock_futures_cr: Optional[float] = None
    institutional_trend: str = "Neutral"
    as_of: str = "Today"
    freshness: DataFreshness = DataFreshness.LIVE

# --- Traceable Evidence & Events ---

class EvidenceItem(BaseModel):
    type: str # PRICE, VOLUME, DERIVATIVES, TECHNICAL, NEWS, SECTOR, MACRO, INSTITUTIONAL
    statement: str
    value: Any
    source: str
    timestamp: str
    freshness: DataFreshness = DataFreshness.LIVE

class MarketEvent(BaseModel):
    event_id: str
    event_type: str # UNUSUAL_SELLING, UNUSUAL_BUYING, BREAKOUT, BREAKDOWN, VWAP_REJECTION, OI_SPIKE, EARNINGS_ANNOUNCEMENT, SECTOR_ROTATION, MACRO_SHOCK
    symbol: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    timestamp: str
    severity: int = Field(ge=0, le=100) # How unusual / impactful
    confidence: float = Field(ge=0.0, le=1.0) # Accuracy of detection
    attention_score: int = Field(ge=0, le=100)
    classification: AttentionClassification = AttentionClassification.MONITOR
    evidence: List[EvidenceItem] = Field(default_factory=list)
    affected_sector: Optional[str] = None
    affected_assets: List[str] = Field(default_factory=list)
    affected_indices: List[str] = Field(default_factory=list)

class AttentionScore(BaseModel):
    total_score: int = Field(ge=0, le=100)
    classification: AttentionClassification
    breakdown: Dict[str, float] # technical, volume, derivatives, news, sector, macro

# --- Specialized Analyst Assessments ---

class DomainAssessment(BaseModel):
    domain: str
    stance: SignalStance
    confidence: float
    key_findings: List[str] = Field(default_factory=list)
    bullish_evidence: List[EvidenceItem] = Field(default_factory=list)
    bearish_evidence: List[EvidenceItem] = Field(default_factory=list)

class ContradictionReport(BaseModel):
    has_contradiction: bool
    consensus_stance: SignalStance
    conflicting_signals: List[str] = Field(default_factory=list)
    synthesis_note: str

# --- Chief Market Analyst & Commentary Output ---

class AICommentary(BaseModel):
    id: str
    symbol: str
    company_name: str
    sector: str
    headline: str
    event_type: str
    importance: ImportanceLevel
    attention_score: int
    classification: AttentionClassification
    market_regime: MarketRegime
    
    # 7 Core Questions Answered
    what_changed: str
    why_it_matters: str
    likely_drivers: List[str]
    confirming_evidence: List[EvidenceItem]
    contradicting_evidence: List[EvidenceItem]
    company_context: str
    sector_context: str
    macro_context: str
    why_should_i_care: str # LOW, MEDIUM, HIGH, CRITICAL impact explanation
    what_to_watch: List[str] # Specific levels & triggers to watch next
    
    bullish_confirmation: List[str]
    bearish_confirmation: List[str]
    uncertainties: List[str]
    
    confidence: float
    timestamp: str
    data_freshness: DataFreshness = DataFreshness.LIVE
    sources: List[str] = Field(default_factory=list)

class MarketNarrative(BaseModel):
    date: str
    headline: str
    primary_regime: MarketRegime
    narrative_summary: str
    key_drivers: List[str]
    sector_leaders: List[str]
    sector_laggards: List[str]
    institutional_bias: str
    macro_backdrop: str
    confidence: float
    timestamp: str
