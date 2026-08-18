import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_vwap, calculate_rsi, calculate_atr, calculate_relative_volume
)

class StrategyHypothesis:
    """
    Quantitative Strategy Definition & Signal Generator
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
# Strategy Lab Data Models
# ---------------------------------------------------------------------------

class StrategyState(str, Enum):
    ACTIVE = "ACTIVE"           # All entry rules pass
    PARTIAL = "PARTIAL"         # >=50% entry rules pass (all computable)
    INACTIVE = "INACTIVE"       # All rules computable, none pass
    CONFLICTED = "CONFLICTED"   # Entry AND exit signals simultaneously active
    UNAVAILABLE = "UNAVAILABLE" # >50% of rules cannot be evaluated (missing data)
    STALE = "STALE"             # Data is too old to be trusted


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"  # Dependency value is None / NaN


@dataclass
class StrategyRule:
    """A single evaluable condition within a strategy."""
    rule_id: str
    label: str                    # Human-readable description
    dependency_keys: List[str]    # Indicator keys required from the feature vector
    # condition_fn: (feature_vector: Dict[str, Any]) -> Optional[bool]
    # Returns True (PASS), False (FAIL), None (UNAVAILABLE)
    condition_fn: Callable        # Not serialised — lives only in the evaluator


@dataclass
class StrategyDefinition:
    """Immutable description of a systematic strategy."""
    strategy_id: str
    name: str
    category: str                 # e.g. "Momentum", "Mean-Reversion", "Breakout"
    description: str
    timeframe_hint: str           # Suggested timeframe e.g. "5m", "15m"
    min_candles: int              # Minimum bars before evaluation is meaningful
    entry_rules: List[StrategyRule] = field(default_factory=list)
    exit_rules: List[StrategyRule] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
