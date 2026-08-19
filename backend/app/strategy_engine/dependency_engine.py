"""
Strategy Engine — Canonical Dependency & Indicator Engine (V3 Hardening)
========================================================================
Implements the single-calculation invariant, canonical dependency normalization,
parameterized indicator specifications, strict history enforcement, zero-vs-missing
distinctions, and lookahead-free series evaluation.

Architecture Contract
---------------------
1. Strategy requests dependencies by canonical keys.
2. Quant engine / Dependency engine calculates each unique dependency ONCE per context.
3. Feature vector and aligned series are returned in an isolated EvaluationContext.
4. No strategy performs local or duplicated indicator calculations.
5. Missing or insufficient data yields None / UNAVAILABLE (never fabricated fallback values).
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from backend.app.quant_engine.indicators import (
    calculate_ema,
    calculate_vwap,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_relative_volume,
)


def _safe_float(val: Any) -> Optional[float]:
    """Return float or None if NaN / None / Inf / non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Canonical Dependency Key Normalization
# ---------------------------------------------------------------------------

KEY_ALIASES: Dict[str, str] = {
    "ema_20": "ema20",
    "ema_50": "ema50",
    "ema_200": "ema200",
    "rsi_14": "rsi14",
    "atr_14": "atr14",
    "rvol_20": "rvol",
    "relative_volume": "rvol",
    "bb_top": "bb_upper",
    "bb_mid": "bb_middle",
    "bb_bot": "bb_lower",
    "supertrend": "supertrend_band",
    "supertrend_proxy": "supertrend_band",
}


def normalize_dependency_key(key: str) -> str:
    """
    Normalizes dependency keys to their single canonical naming standard.
    Case-insensitive, whitespace-trimmed, and alias-resolved.
    """
    cleaned = key.strip().lower()
    return KEY_ALIASES.get(cleaned, cleaned)


# ---------------------------------------------------------------------------
# Indicator Specification Contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndicatorSpec:
    """
    Formal specification and contract for a systematic indicator.
    """
    canonical_key: str
    name: str
    category: str
    min_history: int
    requires_volume: bool = False
    requires_high_low: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


# Registry of known indicator specifications
INDICATOR_SPECS: Dict[str, IndicatorSpec] = {
    "close": IndicatorSpec(
        canonical_key="close",
        name="Closing Price",
        category="price",
        min_history=1,
        description="Latest bar closing price"
    ),
    "open": IndicatorSpec(
        canonical_key="open",
        name="Opening Price",
        category="price",
        min_history=1,
        description="Latest bar opening price"
    ),
    "high": IndicatorSpec(
        canonical_key="high",
        name="High Price",
        category="price",
        min_history=1,
        description="Latest bar high price"
    ),
    "low": IndicatorSpec(
        canonical_key="low",
        name="Low Price",
        category="price",
        min_history=1,
        description="Latest bar low price"
    ),
    "volume": IndicatorSpec(
        canonical_key="volume",
        name="Trading Volume",
        category="volume",
        min_history=1,
        requires_volume=True,
        description="Latest bar recorded volume"
    ),
    "ema20": IndicatorSpec(
        canonical_key="ema20",
        name="Exponential Moving Average (20)",
        category="trend",
        min_history=20,
        parameters={"period": 20},
        description="20-period exponential moving average of closing price"
    ),
    "ema50": IndicatorSpec(
        canonical_key="ema50",
        name="Exponential Moving Average (50)",
        category="trend",
        min_history=50,
        parameters={"period": 50},
        description="50-period exponential moving average of closing price"
    ),
    "ema200": IndicatorSpec(
        canonical_key="ema200",
        name="Exponential Moving Average (200)",
        category="trend",
        min_history=200,
        parameters={"period": 200},
        description="200-period exponential moving average of closing price"
    ),
    "vwap": IndicatorSpec(
        canonical_key="vwap",
        name="Volume Weighted Average Price",
        category="volume",
        min_history=5,
        requires_volume=True,
        requires_high_low=True,
        description="Session-anchored volume weighted average price"
    ),
    "rsi14": IndicatorSpec(
        canonical_key="rsi14",
        name="Relative Strength Index (14)",
        category="momentum",
        min_history=15,
        parameters={"period": 14},
        description="14-period standard Relative Strength Index"
    ),
    "macd": IndicatorSpec(
        canonical_key="macd",
        name="MACD Line (12, 26)",
        category="momentum",
        min_history=35,
        parameters={"fast": 12, "slow": 26, "signal": 9},
        description="Difference between 12-period and 26-period EMAs"
    ),
    "macd_signal": IndicatorSpec(
        canonical_key="macd_signal",
        name="MACD Signal Line (9)",
        category="momentum",
        min_history=35,
        parameters={"fast": 12, "slow": 26, "signal": 9},
        description="9-period EMA of the MACD line"
    ),
    "macd_histogram": IndicatorSpec(
        canonical_key="macd_histogram",
        name="MACD Histogram",
        category="momentum",
        min_history=35,
        parameters={"fast": 12, "slow": 26, "signal": 9},
        description="MACD line minus MACD Signal line"
    ),
    "atr14": IndicatorSpec(
        canonical_key="atr14",
        name="Average True Range (14)",
        category="volatility",
        min_history=15,
        requires_high_low=True,
        parameters={"period": 14},
        description="14-period Average True Range of price volatility"
    ),
    "bb_upper": IndicatorSpec(
        canonical_key="bb_upper",
        name="Bollinger Band Upper (20, 2σ)",
        category="volatility",
        min_history=20,
        parameters={"period": 20, "std": 2.0},
        description="Upper Bollinger band at SMA20 + 2 standard deviations"
    ),
    "bb_middle": IndicatorSpec(
        canonical_key="bb_middle",
        name="Bollinger Band Middle (20)",
        category="volatility",
        min_history=20,
        parameters={"period": 20, "std": 2.0},
        description="Middle Bollinger band (20-period simple moving average)"
    ),
    "bb_lower": IndicatorSpec(
        canonical_key="bb_lower",
        name="Bollinger Band Lower (20, 2σ)",
        category="volatility",
        min_history=20,
        parameters={"period": 20, "std": 2.0},
        description="Lower Bollinger band at SMA20 - 2 standard deviations"
    ),
    "rvol": IndicatorSpec(
        canonical_key="rvol",
        name="Relative Volume (20)",
        category="volume",
        min_history=21,
        requires_volume=True,
        parameters={"period": 20},
        description="Current volume divided by 20-period rolling average volume"
    ),
    "supertrend_band": IndicatorSpec(
        canonical_key="supertrend_band",
        name="Supertrend ATR Proxy Band",
        category="trend",
        min_history=50,
        requires_volume=True,
        requires_high_low=True,
        description="Dynamic support band derived from VWAP - 1.5 * ATR14"
    ),
    "orb_high": IndicatorSpec(
        canonical_key="orb_high",
        name="Opening Range High",
        category="breakout",
        min_history=15,
        requires_high_low=True,
        description="Highest high of initial opening bars"
    ),
    "orb_low": IndicatorSpec(
        canonical_key="orb_low",
        name="Opening Range Low",
        category="breakout",
        min_history=15,
        requires_high_low=True,
        description="Lowest low of initial opening bars"
    ),
}


# ---------------------------------------------------------------------------
# Evaluation Context (Single-Calculation & Isolation Container)
# ---------------------------------------------------------------------------

@dataclass
class DependencyEvaluationContext:
    """
    Isolated execution container holding calculated features and series for one symbol/timeframe context.
    Guarantees no cross-symbol contamination and tracks calculation instrumentation.
    """
    symbol: str
    timeframe: str
    candles_count: int
    feature_vector: Dict[str, Optional[float]] = field(default_factory=dict)
    series: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    calculation_counts: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Canonical Dependency Engine
# ---------------------------------------------------------------------------

class DependencyEngine:
    """
    Authoritative computation engine for indicator dependencies.
    Satisfies:
    - Single-calculation invariant per evaluation context.
    - Zero vs missing volume/price distinction.
    - Warm-up null alignment.
    - Lookahead prevention.
    """

    @staticmethod
    def extract_ohlcv_dataframe(candles: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, bool, bool]:
        """
        Parses candles into clean DataFrame.
        Returns (df, has_ohlc, has_volume).
        """
        if not candles:
            return pd.DataFrame(), False, False

        df = pd.DataFrame(candles)
        if "close" not in df.columns:
            return pd.DataFrame(), False, False

        df["close"] = pd.to_numeric(df["close"], errors="coerce")

        has_high_low = "high" in df.columns and "low" in df.columns
        if has_high_low:
            df["high"] = pd.to_numeric(df["high"], errors="coerce")
            df["low"] = pd.to_numeric(df["low"], errors="coerce")

        has_volume = "volume" in df.columns
        if has_volume:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

        return df, has_high_low, has_volume

    @classmethod
    def compute_context(
        cls,
        candles: List[Dict[str, Any]],
        requested_keys: Optional[Set[str]] = None,
        symbol: str = "UNKNOWN",
        timeframe: str = "5m",
    ) -> DependencyEvaluationContext:
        """
        Computes requested or all canonical dependencies ONCE for the given dataset.
        Produces both the scalar feature vector at candle T and full-length aligned series.
        """
        ctx = DependencyEvaluationContext(
            symbol=symbol,
            timeframe=timeframe,
            candles_count=len(candles) if candles else 0,
        )

        n = ctx.candles_count
        if n == 0:
            return ctx

        df, has_hl, has_vol = cls.extract_ohlcv_dataframe(candles)
        if df.empty or "close" not in df.columns:
            return ctx

        close = df["close"]
        high = df["high"] if has_hl else close
        low = df["low"] if has_hl else close
        volume = df["volume"] if has_vol else None

        # Normalize requested keys if provided, else compute full standard set
        keys_to_compute = set(INDICATOR_SPECS.keys())
        if requested_keys:
            keys_to_compute = {normalize_dependency_key(k) for k in requested_keys}
            # Always ensure close is available as baseline
            keys_to_compute.add("close")

        def _to_aligned_list(s: Optional[pd.Series], min_bars: int) -> List[Optional[float]]:
            if s is None or n < min_bars:
                return [None] * n
            res: List[Optional[float]] = []
            for i, val in enumerate(s):
                if i < min_bars - 1:
                    res.append(None)
                else:
                    res.append(_safe_float(val))
            return res

        def _record(key: str, series_val: Optional[pd.Series], min_bars: int):
            ctx.calculation_counts[key] = ctx.calculation_counts.get(key, 0) + 1
            arr = _to_aligned_list(series_val, min_bars)
            ctx.series[key] = arr
            ctx.feature_vector[key] = arr[-1] if arr else None

        # 1. Price Basics
        if "close" in keys_to_compute:
            _record("close", close, 1)
        if "open" in keys_to_compute and "open" in df.columns:
            _record("open", df["open"], 1)
        if "high" in keys_to_compute and has_hl:
            _record("high", high, 1)
        if "low" in keys_to_compute and has_hl:
            _record("low", low, 1)
        if "volume" in keys_to_compute and has_vol and volume is not None:
            _record("volume", volume, 1)

        # 2. EMAs
        if "ema20" in keys_to_compute:
            ema20_s = calculate_ema(close, 20) if n >= 20 else None
            _record("ema20", ema20_s, 20)

        if "ema50" in keys_to_compute:
            ema50_s = calculate_ema(close, 50) if n >= 50 else None
            _record("ema50", ema50_s, 50)

        if "ema200" in keys_to_compute:
            ema200_s = calculate_ema(close, 200) if n >= 200 else None
            _record("ema200", ema200_s, 200)

        # 3. VWAP (Strict Volume & Intraday Check)
        if "vwap" in keys_to_compute:
            vwap_s = None
            if has_hl and has_vol and volume is not None and n >= 5:
                # If total cumulative volume is 0 or all volume is NaN, VWAP is None
                tot_vol = volume.sum()
                if not (math.isnan(tot_vol) or tot_vol <= 0):
                    vwap_s = calculate_vwap(df)
            _record("vwap", vwap_s, 5)

        # 4. RSI(14)
        if "rsi14" in keys_to_compute:
            rsi_s = calculate_rsi(close, 14) if n >= 15 else None
            _record("rsi14", rsi_s, 15)

        # 5. MACD (12, 26, 9)
        if any(k in keys_to_compute for k in ["macd", "macd_signal", "macd_histogram"]):
            macd_l, macd_s, macd_h = (None, None, None)
            if n >= 35:
                macd_l, macd_s, macd_h = calculate_macd(close, 12, 26, 9)
            _record("macd", macd_l, 35)
            _record("macd_signal", macd_s, 35)
            _record("macd_histogram", macd_h, 35)

        # 6. ATR(14)
        if "atr14" in keys_to_compute:
            atr_s = calculate_atr(df, 14) if (has_hl and n >= 15) else None
            _record("atr14", atr_s, 15)

        # 7. Bollinger Bands (20, 2σ)
        if any(k in keys_to_compute for k in ["bb_upper", "bb_middle", "bb_lower"]):
            bb_mid, bb_u, bb_l = (None, None, None)
            if n >= 20:
                bb_mid, bb_u, bb_l = calculate_bollinger_bands(close, 20, 2.0)
            _record("bb_middle", bb_mid, 20)
            _record("bb_upper", bb_u, 20)
            _record("bb_lower", bb_l, 20)

        # 8. Relative Volume (20)
        if "rvol" in keys_to_compute:
            rvol_s = None
            if has_vol and volume is not None and n >= 21:
                # If volume is available and non-trivial
                tot_vol = volume.sum()
                if not (math.isnan(tot_vol) or tot_vol <= 0):
                    rvol_s = calculate_relative_volume(volume, 20)
            _record("rvol", rvol_s, 21)

        # 9. Supertrend ATR Proxy Band
        if "supertrend_band" in keys_to_compute:
            st_s = None
            if "vwap" in ctx.series and "atr14" in ctx.series:
                vwap_arr = ctx.series["vwap"]
                atr_arr = ctx.series["atr14"]
                st_list: List[Optional[float]] = []
                for v, a in zip(vwap_arr, atr_arr):
                    if v is not None and a is not None:
                        st_list.append(round(v - 1.5 * a, 4))
                    else:
                        st_list.append(None)
                ctx.series["supertrend_band"] = st_list
                ctx.feature_vector["supertrend_band"] = st_list[-1] if st_list else None
                ctx.calculation_counts["supertrend_band"] = 1

        # 10. Opening Range Breakout (ORB) High & Low
        if any(k in keys_to_compute for k in ["orb_high", "orb_low"]):
            orb_h_list: List[Optional[float]] = [None] * n
            orb_l_list: List[Optional[float]] = [None] * n
            if has_hl and n >= 6:
                # Opening 6 candles define session initial range
                first_6_h = high.iloc[:6].max()
                first_6_l = low.iloc[:6].min()
                if not math.isnan(first_6_h) and not math.isnan(first_6_l):
                    for i in range(n):
                        if i >= 5:
                            orb_h_list[i] = round(float(first_6_h), 2)
                            orb_l_list[i] = round(float(first_6_l), 2)
            ctx.series["orb_high"] = orb_h_list
            ctx.series["orb_low"] = orb_l_list
            ctx.feature_vector["orb_high"] = orb_h_list[-1] if orb_h_list else None
            ctx.feature_vector["orb_low"] = orb_l_list[-1] if orb_l_list else None
            ctx.calculation_counts["orb_high"] = 1
            ctx.calculation_counts["orb_low"] = 1

        return ctx


# Global dependency engine instance
dependency_engine = DependencyEngine()
