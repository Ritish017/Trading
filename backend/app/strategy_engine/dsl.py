import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_vwap, calculate_rsi, calculate_atr, calculate_relative_volume
)

# ---------------------------------------------------------------------------
# Strategy Hypothesis (Backtest & Simulation Model)
# ---------------------------------------------------------------------------

class StrategyHypothesis:
    """
    Quantitative Strategy Definition & Signal Generator for Backtesting.
    """

    def __init__(
        self,
        name: str = "VWAP_Momentum_Breakout",
        timeframe: str = "5m",
        min_rsi: float = 55.0,
        min_rvol: float = 1.2,
        use_ema_filter: bool = True
    ):
        self.name = name
        self.timeframe = timeframe
        self.min_rsi = min_rsi
        self.min_rvol = min_rvol
        self.use_ema_filter = use_ema_filter

    def evaluate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates indicators and appends boolean buy_signal and sell_signal columns.
        """
        if df.empty or len(df) < 30:
            df['buy_signal'] = False
            df['sell_signal'] = False
            return df

        res = df.copy()
        close = res['close']

        res['ema20'] = calculate_ema(close, 20)
        res['ema50'] = calculate_ema(close, 50)
        res['vwap'] = calculate_vwap(res) if 'high' in res and 'low' in res and 'volume' in res else close
        res['rsi14'] = calculate_rsi(close, 14)
        res['rvol'] = calculate_relative_volume(res['volume'], 20) if 'volume' in res else 1.0

        # Entry Rule: Price > VWAP & EMA20 > EMA50 & RSI > min_rsi & Relative Volume > min_rvol
        c_vwap = res['close'] > res['vwap']
        c_ema = (res['ema20'] > res['ema50']) if self.use_ema_filter else True
        c_rsi = res['rsi14'] > self.min_rsi
        c_rvol = res['rvol'] >= self.min_rvol

        res['buy_signal'] = c_vwap & c_ema & c_rsi & c_rvol

        # Exit Rule: Price < EMA20 or RSI < 45
        res['sell_signal'] = (res['close'] < res['ema20']) | (res['rsi14'] < 45.0)

        return res


# ---------------------------------------------------------------------------
# Controlled Taxonomy & State Contracts
# ---------------------------------------------------------------------------

class StrategyCategory(str, Enum):
    TREND = "Trend Following"
    MOMENTUM = "Momentum"
    MEAN_REVERSION = "Mean-Reversion"
    BREAKOUT = "Breakout"
    VOLUME = "Volume"
    VOLATILITY = "Volatility"
    # Future extensibility categories
    STATISTICAL = "Statistical"
    FACTOR = "Factor"
    FUNDAMENTAL = "Fundamental"
    OPTIONS = "Options"
    EVENT_DRIVEN = "Event-Driven"
    SECTOR = "Sector"


class StrategyDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    BOTH = "BOTH"


class StrategyState(str, Enum):
    ACTIVE = "ACTIVE"           # All entry rules pass
    PARTIAL = "PARTIAL"         # >=50% entry rules pass (all computable)
    INACTIVE = "INACTIVE"       # All rules computable, none pass
    CONFLICTED = "CONFLICTED"   # Entry AND exit signals simultaneously active
    UNAVAILABLE = "UNAVAILABLE" # >50% of rules cannot be evaluated (missing data)
    STALE = "STALE"             # Legacy compatibility alias for data freshness


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"  # Dependency value is None / NaN


# ---------------------------------------------------------------------------
# Visualization & Data Requirements Contracts
# ---------------------------------------------------------------------------

@dataclass
class StrategyVisualization:
    """Declares chart overlays, oscillator subpanels, and visual markers."""
    overlays: List[str] = field(default_factory=list)      # e.g. ["ema20", "ema50"], ["vwap"], ["bb_upper", "bb_middle", "bb_lower"]
    subpanels: List[str] = field(default_factory=list)     # e.g. ["rsi14"], ["macd"]
    markers: List[str] = field(default_factory=lambda: ["ACTIVATED", "INVALIDATED", "PARTIAL", "CONFLICT"])
    highlight_active_regions: bool = True
    color: str = "#10b981"


@dataclass
class StrategyDataRequirements:
    """Declares data dependencies and historical depth requirements."""
    min_candles: int = 50
    requires_volume: bool = True
    requires_vwap: bool = False
    requires_ohlc: bool = True
    requires_intraday: bool = False
    supported_timeframes: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "1h", "1D"])


# ---------------------------------------------------------------------------
# Strategy Rule & Evidence Contract
# ---------------------------------------------------------------------------

@dataclass
class StrategyRule:
    """A single evaluable condition within a systematic strategy."""
    rule_id: str
    label: str                    # Human-readable description
    dependency_keys: List[str]    # Indicator keys required from the feature vector
    condition_fn: Callable        # (feature_vector: Dict[str, Any]) -> Optional[bool]
    operator: str = ">"           # e.g. ">", "<", ">=", "<=", "between"
    threshold: Optional[float] = None
    is_entry_rule: bool = True
    explanation: Optional[str] = None


# ---------------------------------------------------------------------------
# Research Parameter Contract (Phase 6 Discovery & Robustness)
# ---------------------------------------------------------------------------

@dataclass
class ResearchParameter:
    """
    Formal bounded research parameter specification.
    Exposes only explicitly defined valid domains for parameter sweeps and stability analysis.
    Prevents combinatorial explosion and unrestricted parameter tampering.
    """
    parameter_id: str
    name: str
    param_type: str = "int"          # "int" | "float" | "choice" | "bool"
    default_value: Any = None
    allowed_values: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    description: str = ""

    def validate_value(self, val: Any) -> Tuple[bool, Optional[str]]:
        if self.allowed_values is not None:
            if val not in self.allowed_values:
                return False, f"Value {val} not in allowed choices {self.allowed_values}"
            return True, None

        if self.param_type in ("int", "float"):
            try:
                num = float(val)
                if self.minimum is not None and num < self.minimum:
                    return False, f"Value {num} below minimum {self.minimum}"
                if self.maximum is not None and num > self.maximum:
                    return False, f"Value {num} above maximum {self.maximum}"
                return True, None
            except (ValueError, TypeError):
                return False, f"Value {val} is not a valid number"

        return True, None


# ---------------------------------------------------------------------------
# Extensible Strategy Definition Contract
# ---------------------------------------------------------------------------

@dataclass
class StrategyDefinition:
    """
    Immutable canonical description of a quantitative strategy.
    Acts as the single source of truth for Evaluator, Backtester, Chart & Copilot.
    """
    strategy_id: str
    name: str
    short_name: str
    category: Union[StrategyCategory, str]
    description: str
    direction: StrategyDirection = StrategyDirection.BULLISH
    version: str = "1.0.0"
    enabled: bool = True
    experimental: bool = False
    deprecated: bool = False
    timeframe_hint: str = "5m"
    min_candles: int = 50
    requirements: StrategyDataRequirements = field(default_factory=StrategyDataRequirements)
    entry_rules: List[StrategyRule] = field(default_factory=list)
    exit_rules: List[StrategyRule] = field(default_factory=list)
    invalidation_rules: List[StrategyRule] = field(default_factory=list)
    visualization: StrategyVisualization = field(default_factory=StrategyVisualization)
    research_parameters: List[ResearchParameter] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Sync min_candles and requirements
        if self.min_candles != 50 and self.requirements.min_candles == 50:
            self.requirements.min_candles = self.min_candles
        elif self.requirements.min_candles != 50 and self.min_candles == 50:
            self.min_candles = self.requirements.min_candles

        # Convert string category to StrategyCategory if possible
        if isinstance(self.category, str):
            for c in StrategyCategory:
                if c.value.lower() == self.category.lower() or c.name.lower() == self.category.lower():
                    self.category = c
                    break
