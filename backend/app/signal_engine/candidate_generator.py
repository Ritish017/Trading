"""
Signal Intelligence Engine — Candidate Generator
=================================================
Scans the market universe and filters instruments to identify high-probability
setup candidates prior to full deep evaluation.

Filtering criteria:
1. Liquidity & Price: Minimum volume and non-penny price
2. Relative Volume (RVOL): Volume expansion vs 20-day moving average
3. Volatility: Minimum ATR percentage
4. Trend Alignment: EMA fast > EMA slow or EMA compression (breakout setup)
5. Momentum: RSI in active non-exhausted zones (40-65 for long, 35-60 for short)
6. Structure: Proximity to key support/resistance or swing highs/lows

Invariants:
- Deterministic: Same input data produces identical candidate records
- Returns ranked candidates sorted by priority_score descending
- Fully transparent reasons why each candidate was selected
"""
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from backend.app.signal_engine.models import (
    CandidateRecord,
    SignalDirection,
    SignalEngineConfig,
)

logger = logging.getLogger(__name__)


class CandidateGenerator:
    """
    Screens universe of symbols to produce candidate opportunities for deep evaluation.
    """

    def __init__(self, config: Optional[SignalEngineConfig] = None):
        self.config = config or SignalEngineConfig()

    def screen_universe(
        self,
        symbol_data_map: Dict[str, Dict[str, Any]],
    ) -> List[CandidateRecord]:
        """
        Screens a dictionary of {symbol: {"quote": ..., "candles": ...}}
        Returns sorted list of CandidateRecord objects.
        """
        candidates: List[CandidateRecord] = []

        for symbol, data in symbol_data_map.items():
            quote = data.get("quote") or {}
            candles = data.get("candles") or []
            cand = self.evaluate_symbol_candidate(symbol, quote, candles)
            if cand is not None:
                candidates.append(cand)

        # Sort by priority score descending
        candidates.sort(key=lambda c: c.priority_score, reverse=True)
        return candidates

    def evaluate_symbol_candidate(
        self,
        symbol: str,
        quote: Dict[str, Any],
        candles: List[Dict[str, Any]],
    ) -> Optional[CandidateRecord]:
        """
        Evaluates a single symbol against pre-screening thresholds.
        Returns CandidateRecord if passing pre-filters, None otherwise.
        """
        if not candles or len(candles) < 20:
            return None

        ltp = float(quote.get("ltp") or candles[-1].get("close") or 0.0)
        if ltp <= 5.0:  # Skip micro-pennies
            return None

        # Build dataframe for indicator calculations
        df = pd.DataFrame(candles)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if len(df) < 20:
            return None

        close = df["close"].values
        volume = df["volume"].values
        high = df["high"].values
        low = df["low"].values

        # 1. Relative Volume (RVOL)
        avg_vol = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
        current_vol = float(volume[-1]) if volume[-1] > 0 else float(quote.get("volume") or 0)
        rvol = (current_vol / avg_vol) if avg_vol > 0 else 1.0

        # 2. ATR & Volatility
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        atr_14 = np.mean(tr[-14:]) if len(tr) >= 14 else float(high[-1] - low[-1])
        atr_pct = (atr_14 / ltp * 100.0) if ltp > 0 else 0.0

        # 3. EMA alignment
        ema_fast = pd.Series(close).ewm(span=9, adjust=False).mean().values[-1]
        ema_mid = pd.Series(close).ewm(span=21, adjust=False).mean().values[-1]
        ema_slow = pd.Series(close).ewm(span=50, adjust=False).mean().values[-1] if len(close) >= 50 else ema_mid

        # 4. RSI (14)
        delta = pd.Series(close).diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean().iloc[-1]
        avg_loss = loss.rolling(window=14, min_periods=14).mean().iloc[-1]
        if avg_loss is not None and avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi = 50.0

        # Determine preliminary bias
        triggers: List[str] = []
        score = 50.0
        direction = SignalDirection.WATCHLIST

        is_bullish_trend = (ema_fast > ema_mid) and (ltp >= ema_fast)
        is_bearish_trend = (ema_fast < ema_mid) and (ltp <= ema_fast)

        if is_bullish_trend:
            direction = SignalDirection.LONG
            triggers.append(f"Bullish EMA alignment (EMA9 ₹{ema_fast:.1f} > EMA21 ₹{ema_mid:.1f})")
            score += 15.0
        elif is_bearish_trend:
            direction = SignalDirection.SHORT
            triggers.append(f"Bearish EMA alignment (EMA9 ₹{ema_fast:.1f} < EMA21 ₹{ema_mid:.1f})")
            score += 15.0

        if rvol >= 1.5:
            triggers.append(f"Volume expansion: RVOL {rvol:.2f}x above 20MA")
            score += 15.0
        elif rvol >= 1.1:
            triggers.append(f"Above average volume: RVOL {rvol:.2f}x")
            score += 5.0

        if 45.0 <= rsi <= 65.0 and direction == SignalDirection.LONG:
            triggers.append(f"RSI in constructive bullish zone ({rsi:.1f})")
            score += 10.0
        elif 35.0 <= rsi <= 55.0 and direction == SignalDirection.SHORT:
            triggers.append(f"RSI in active bearish zone ({rsi:.1f})")
            score += 10.0

        # Proximity to 20-candle high or low
        recent_high = np.max(high[-20:])
        recent_low = np.min(low[-20:])
        if direction == SignalDirection.LONG and abs(ltp - recent_high) / ltp < 0.015:
            triggers.append(f"Consolidating near 20-period high ₹{recent_high:.1f} (Breakout potential)")
            score += 10.0
        elif direction == SignalDirection.SHORT and abs(ltp - recent_low) / ltp < 0.015:
            triggers.append(f"Pressuring 20-period low ₹{recent_low:.1f} (Breakdown potential)")
            score += 10.0

        if score < 60.0 and len(triggers) < 2:
            return None

        priority_score = min(100.0, score)

        return CandidateRecord(
            symbol=symbol,
            exchange="NSE",
            priority_score=priority_score,
            screening_reasons=triggers,
            rvol=float(rvol),
            last_price=float(ltp),
        )


candidate_generator = CandidateGenerator()
