"""
Paper Engine — Canonical Models & Signal Contracts (Phase 8)
============================================================
Defines the deterministic Paper Signal contract, research lifecycle states,
paper positions, trade audit records, and model drift metrics.

CRITICAL INVARIANTS:
1. Paper trading receives the exact same StrategyResult and ConfluenceResult as Strategy Lab.
2. Next-bar execution semantics (no same-bar lookahead).
3. Realistic Indian equity transaction cost modeling (STT, Exchange, SEBI, GST, Slippage).
4. No automated live broker order execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class ResearchLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    RESEARCHING = "RESEARCHING"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"
    PAPER_TESTING = "PAPER_TESTING"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    STRATEGY_INVALIDATION = "STRATEGY_INVALIDATION"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    TIME_EXPIRY = "TIME_EXPIRY"


@dataclass
class PaperSignal:
    """
    Immutable research and paper trading signal contract.
    Directly derived from deterministic StrategyResult and Confluence.
    """
    signal_id: str
    timestamp: int
    symbol: str
    timeframe: str
    strategy_id: str
    strategy_version: str
    strategy_state: str  # ACTIVE | PARTIAL | INACTIVE
    side: OrderSide
    intended_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    fundamental_state: str = "NEUTRAL"
    confluence_state: str = "NEUTRAL"
    rule_evidence: List[str] = field(default_factory=list)
    factor_evidence: List[str] = field(default_factory=list)
    data_freshness: str = "LIVE"
    provider: str = "UPSTOX"
    market_status: str = "OPEN"
    hypothesis_id: Optional[str] = None
    regime: str = "NORMAL"


@dataclass
class PaperTradeAudit:
    """
    Comprehensive forensic record for a completed paper trade.
    """
    trade_id: str
    signal_id: str
    symbol: str
    strategy_id: str
    strategy_version: str
    side: OrderSide
    quantity: int
    entry_timestamp: int
    entry_price: float
    exit_timestamp: int
    exit_price: float
    exit_reason: ExitReason
    gross_pnl: float
    net_pnl: float
    fees_paid: float
    slippage_paid: float
    return_pct: float
    holding_period_bars: int
    entry_evidence: List[str] = field(default_factory=list)
    exit_evidence: List[str] = field(default_factory=list)
    regime_at_entry: str = "NORMAL"
    confluence_at_entry: str = "NEUTRAL"
    regime_at_exit: str = "NORMAL"


@dataclass
class PaperPosition:
    """
    Active or historical paper trading position.
    """
    position_id: str
    symbol: str
    strategy_id: str
    strategy_version: str
    side: OrderSide
    quantity: int
    entry_timestamp: int
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    slippage_paid: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    signal: Optional[PaperSignal] = None
    regime_at_entry: str = "NORMAL"
    confluence_at_entry: str = "NEUTRAL"
    data_status: str = "LIVE"
    provider: str = "UPSTOX"
    exit_timestamp: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None


@dataclass
class ResearchCandidate:
    """
    Candidate strategy tracked in the research lifecycle ledger.
    """
    candidate_id: str
    strategy_id: str
    strategy_name: str
    lifecycle_state: ResearchLifecycleState
    created_timestamp: int
    updated_timestamp: int
    promoted_by: str = "USER"
    hypothesis_text: str = ""
    target_symbols: List[str] = field(default_factory=list)
    backtest_cagr_pct: Optional[float] = None
    backtest_sharpe: Optional[float] = None
    backtest_max_drawdown_pct: Optional[float] = None
    walk_forward_efficiency: Optional[float] = None
    notes: Optional[str] = None
