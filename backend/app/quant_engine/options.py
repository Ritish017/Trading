import math
from typing import List, Dict, Any

def calculate_pcr(total_put_oi: int, total_call_oi: int) -> float:
    """Calculate Put-Call Ratio (PCR)"""
    if total_call_oi <= 0:
        return 1.0
    return round(total_put_oi / total_call_oi, 2)

def calculate_max_pain(strikes: List[float], call_oi: List[int], put_oi: List[int]) -> float:
    """
    Max Pain Strike Calculation
    Finds the strike price at which option writers suffer the least total financial loss.
    """
    if not strikes or len(strikes) != len(call_oi) or len(strikes) != len(put_oi):
        return strikes[len(strikes) // 2] if strikes else 24500.0

    min_loss = float("inf")
    max_pain_strike = strikes[0]

    for expiry_spot in strikes:
        total_loss = 0.0
        for i, strike in enumerate(strikes):
            # Call loss for writers if spot > strike
            if expiry_spot > strike:
                total_loss += (expiry_spot - strike) * call_oi[i]
            # Put loss for writers if spot < strike
            if expiry_spot < strike:
                total_loss += (strike - expiry_spot) * put_oi[i]
        
        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = expiry_spot

    return max_pain_strike

def classify_oi_pattern(price_change_pct: float, oi_change_pct: float) -> str:
    """
    Classify Derivatives Market Sentiment based on Price vs Open Interest changes:
    - Price UP + OI UP   => Long Buildup (Bullish)
    - Price DOWN + OI UP => Short Buildup (Bearish)
    - Price UP + OI DOWN => Short Covering (Bullish)
    - Price DOWN + OI DOWN => Long Unwinding (Bearish)
    """
    if price_change_pct > 0 and oi_change_pct > 0:
        return "LONG_BUILDUP"
    elif price_change_pct < 0 and oi_change_pct > 0:
        return "SHORT_BUILDUP"
    elif price_change_pct > 0 and oi_change_pct < 0:
        return "SHORT_COVERING"
    elif price_change_pct < 0 and oi_change_pct < 0:
        return "LONG_UNWINDING"
    return "NEUTRAL"
