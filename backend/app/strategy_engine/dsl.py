import pandas as pd
import numpy as np
from typing import Dict, Any, List
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
