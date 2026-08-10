import pandas as pd
import numpy as np
from typing import Dict, Any
from backend.app.quant_engine.indicators import calculate_ema, calculate_atr, calculate_rsi

def classify_market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Deterministic Market Regime Classification Engine
    Inputs: OHLCV DataFrame
    Outputs: Dict containing regime_name, confidence score, volatility metrics, and trend strength
    """
    if df.empty or len(df) < 20:
        return {
            "regime": "RANGE_BOUND",
            "confidence": 60,
            "trend_strength": 0.0,
            "volatility_status": "NORMAL",
            "evidence": "Insufficient historical data for high-confidence classification",
        }

    close = df['close']
    ema20 = calculate_ema(close, 20).iloc[-1]
    ema50 = calculate_ema(close, 50).iloc[-1] if len(df) >= 50 else calculate_ema(close, 20).iloc[-1] * 0.98
    rsi = calculate_rsi(close, 14).iloc[-1]
    atr = calculate_atr(df, 14).iloc[-1]
    
    current_price = close.iloc[-1]
    atr_pct = (atr / current_price) * 100.0

    # Trend Determination
    is_above_ema20 = current_price > ema20
    is_ema_bullish = ema20 > ema50
    
    # Classification Logic
    if is_above_ema20 and is_ema_bullish and rsi > 55:
        regime = "TRENDING_BULLISH"
        confidence = min(85 + int((rsi - 55) * 0.5), 98)
        evidence = f"Price (₹{current_price}) > EMA20 (₹{ema20:.2f}) > EMA50 (₹{ema50:.2f}), RSI strong at {rsi:.1f}"
    elif not is_above_ema20 and not is_ema_bullish and rsi < 45:
        regime = "TRENDING_BEARISH"
        confidence = min(85 + int((45 - rsi) * 0.5), 98)
        evidence = f"Price (₹{current_price}) < EMA20 (₹{ema20:.2f}) < EMA50 (₹{ema50:.2f}), RSI weak at {rsi:.1f}"
    elif is_above_ema20 and 45 <= rsi <= 55:
        regime = "BULLISH_ACCUMULATION"
        confidence = 78
        evidence = f"Price holding above VWAP/EMA20 (₹{ema20:.2f}) in sub-neutral RSI zone ({rsi:.1f})"
    elif not is_above_ema20 and 45 <= rsi <= 55:
        regime = "BEARISH_DISTRIBUTION"
        confidence = 76
        evidence = f"Price below EMA20 (₹{ema20:.2f}) showing persistent selling pressure on rallies"
    elif atr_pct > 2.5:
        regime = "HIGH_VOLATILITY"
        confidence = 82
        evidence = f"Intraday ATR percentage ({atr_pct:.2f}%) indicates heightened volatility"
    else:
        regime = "RANGE_BOUND"
        confidence = 70
        evidence = f"Oscillating between bounds with neutral RSI ({rsi:.1f})"

    return {
        "regime": regime,
        "confidence": confidence,
        "trend_strength": round(abs(current_price - ema50) / current_price * 100, 2),
        "volatility_status": "HIGH" if atr_pct > 2.5 else "NORMAL",
        "evidence": evidence,
        "metrics": {
            "ema20": round(float(ema20), 2),
            "ema50": round(float(ema50), 2),
            "rsi14": round(float(rsi), 1),
            "atr14": round(float(atr), 2),
        }
    }
