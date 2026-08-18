import pandas as pd
import numpy as np
from typing import Dict, Any
from backend.app.quant_engine.indicators import calculate_ema, calculate_atr, calculate_rsi

def classify_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Deterministic Market Regime Classification Engine.
    Inputs: OHLCV DataFrame
    Outputs: Dict containing regime_name, confidence score, volatility metrics, and trend strength.
    Returns UNAVAILABLE if data is insufficient (< 20 candles).
    """
    if df.empty or len(df) < 20:
        return {
            "regime": "UNAVAILABLE",
            "confidence": 0,
            "trend_strength": 0.0,
            "volatility_status": "UNAVAILABLE",
            "evidence": "Insufficient historical candle data for regime classification (requires at least 20 periods)",
            "metrics": {}
        }

    close = df['close'].astype(float)
    ema20_series = calculate_ema(close, 20)
    ema20 = float(ema20_series.iloc[-1])
    
    ema50_series = calculate_ema(close, min(50, len(df)))
    ema50 = float(ema50_series.iloc[-1])
    
    rsi_series = calculate_rsi(close, 14)
    rsi = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 and not pd.isna(rsi_series.iloc[-1]) else None
    if rsi is None:
        return {
            "regime": "UNAVAILABLE",
            "confidence": 0,
            "trend_strength": 0.0,
            "volatility_status": "UNAVAILABLE",
            "evidence": "RSI indicator unavailable for regime classification",
            "metrics": {}
        }
    
    atr_series = calculate_atr(df, 14)
    atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]) else 0.0
    
    current_price = float(close.iloc[-1])
    atr_pct = (atr / current_price) * 100.0 if current_price > 0 else 0.0

    # Trend Determination
    is_above_ema20 = current_price > ema20
    is_ema_bullish = ema20 > ema50
    
    # Classification Logic
    if is_above_ema20 and is_ema_bullish and rsi > 55:
        regime = "TRENDING_BULLISH"
        confidence = min(95, max(60, int(75 + (rsi - 55) * 0.6)))
        evidence = f"Price (₹{current_price:.2f}) > EMA20 (₹{ema20:.2f}) > EMA50 (₹{ema50:.2f}), RSI strong at {rsi:.1f}"
    elif not is_above_ema20 and not is_ema_bullish and rsi < 45:
        regime = "TRENDING_BEARISH"
        confidence = min(95, max(60, int(75 + (45 - rsi) * 0.6)))
        evidence = f"Price (₹{current_price:.2f}) < EMA20 (₹{ema20:.2f}) < EMA50 (₹{ema50:.2f}), RSI weak at {rsi:.1f}"
    elif is_above_ema20 and 45 <= rsi <= 55:
        regime = "BULLISH_ACCUMULATION"
        dist_pct = abs(current_price - ema20) / ema20 * 100 if ema20 > 0 else 0.0
        confidence = min(85, max(50, int(55 + dist_pct * 10)))
        evidence = f"Price holding above EMA20 (₹{ema20:.2f}) in neutral RSI zone ({rsi:.1f})"
    elif not is_above_ema20 and 45 <= rsi <= 55:
        regime = "BEARISH_DISTRIBUTION"
        dist_pct = abs(ema20 - current_price) / ema20 * 100 if ema20 > 0 else 0.0
        confidence = min(85, max(50, int(55 + dist_pct * 10)))
        evidence = f"Price below EMA20 (₹{ema20:.2f}) showing persistent selling pressure on rallies"
    elif atr_pct > 2.5:
        regime = "HIGH_VOLATILITY"
        confidence = min(90, max(55, int(60 + (atr_pct - 2.5) * 8)))
        evidence = f"Intraday ATR percentage ({atr_pct:.2f}%) indicates heightened volatility"
    else:
        regime = "RANGE_BOUND"
        confidence = min(75, max(45, int(70 - abs(rsi - 50) * 2)))
        evidence = f"Oscillating between bounds with neutral RSI ({rsi:.1f})"

    return {
        "regime": regime,
        "confidence": confidence,
        "trend_strength": round(abs(current_price - ema50) / current_price * 100, 2) if current_price > 0 else 0.0,
        "volatility_status": "HIGH" if atr_pct > 2.5 else "NORMAL",
        "evidence": evidence,
        "metrics": {
            "ema20": round(float(ema20), 2),
            "ema50": round(float(ema50), 2),
            "rsi14": round(float(rsi), 1),
            "atr14": round(float(atr), 2),
        }
    }
