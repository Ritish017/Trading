import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from backend.app.ai_engine.contracts import TechnicalSnapshot, DerivativeSnapshot

def compute_market_features(candles: List[Dict[str, Any]], current_price: float, prev_close: float) -> TechnicalSnapshot:
    """
    Compute comprehensive quantitative and technical feature vector from historical OHLCV candles.
    """
    if not candles or len(candles) < 5:
        # Minimalist fallback
        return TechnicalSnapshot(
            rsi_14=50.0,
            ema_20=round(current_price * 0.99, 2),
            ema_50=round(current_price * 0.98, 2),
            relative_volume=1.0,
            support_levels=[round(current_price * 0.97, 2), round(current_price * 0.95, 2)],
            resistance_levels=[round(current_price * 1.03, 2), round(current_price * 1.05, 2)]
        )

    df = pd.DataFrame(candles)
    close = df['close'].astype(float)
    high = df['high'].astype(float) if 'high' in df else close
    low = df['low'].astype(float) if 'low' in df else close
    volume = df['volume'].astype(float) if 'volume' in df else pd.Series([1.0] * len(df))

    # 1. EMAs
    ema20_series = close.ewm(span=20, adjust=False).mean()
    ema50_series = close.ewm(span=50, adjust=False).mean() if len(close) >= 50 else ema20_series
    ema200_series = close.ewm(span=200, adjust=False).mean() if len(close) >= 200 else ema50_series

    ema_20 = float(ema20_series.iloc[-1])
    ema_50 = float(ema50_series.iloc[-1])
    ema_200 = float(ema200_series.iloc[-1])

    # 2. RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi_series.iloc[-1])

    # 3. MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    macd = float(macd_line.iloc[-1])
    macd_signal = float(signal_line.iloc[-1])
    macd_histogram = float(macd_hist.iloc[-1])

    # 4. ATR (14)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_series = tr.rolling(window=14, min_periods=1).mean()
    atr_14 = float(atr_series.iloc[-1])

    # 5. Relative Volume (RVOL) = Current Volume / 20-period SMA Volume
    vol_sma20 = volume.rolling(window=min(20, len(volume)), min_periods=1).mean()
    current_vol = float(volume.iloc[-1]) if len(volume) > 0 else 1.0
    rvol = float(current_vol / (vol_sma20.iloc[-1] + 1e-9)) if len(vol_sma20) > 0 else 1.0

    # 6. Bollinger Bands (20, 2)
    sma20 = close.rolling(window=min(20, len(close)), min_periods=1).mean()
    std20 = close.rolling(window=min(20, len(close)), min_periods=1).std().fillna(0)
    bb_mid = float(sma20.iloc[-1])
    bb_up = float(bb_mid + 2 * std20.iloc[-1])
    bb_low = float(bb_mid - 2 * std20.iloc[-1])

    # 7. Support & Resistance Levels (Local extrema)
    supports = []
    resistances = []
    window = 5
    for i in range(window, len(df) - window):
        if low.iloc[i] == low.iloc[i - window:i + window + 1].min():
            supports.append(float(low.iloc[i]))
        if high.iloc[i] == high.iloc[i - window:i + window + 1].max():
            resistances.append(float(high.iloc[i]))

    # Filter and sort closest to current price
    sup_sorted = sorted([s for s in set(supports) if s < current_price], reverse=True)[:3]
    res_sorted = sorted([r for r in set(resistances) if r > current_price])[:3]

    if not sup_sorted:
        sup_sorted = [round(current_price * 0.98, 2), round(current_price * 0.95, 2)]
    if not res_sorted:
        res_sorted = [round(current_price * 1.02, 2), round(current_price * 1.05, 2)]

    return TechnicalSnapshot(
        rsi_14=round(rsi_14, 1),
        macd=round(macd, 2),
        macd_signal=round(macd_signal, 2),
        macd_histogram=round(macd_histogram, 2),
        ema_20=round(ema_20, 2),
        ema_50=round(ema_50, 2),
        ema_200=round(ema_200, 2),
        sma_20=round(bb_mid, 2),
        atr_14=round(atr_14, 2),
        bb_upper=round(bb_up, 2),
        bb_middle=round(bb_mid, 2),
        bb_lower=round(bb_low, 2),
        relative_volume=round(rvol, 2),
        support_levels=[round(x, 2) for x in sup_sorted],
        resistance_levels=[round(x, 2) for x in res_sorted]
    )

def compute_z_score(price_change_pct: float, baseline_volatility: float = 1.2) -> float:
    """Computes statistical z-score of an intraday percentage price move."""
    if baseline_volatility <= 0:
        baseline_volatility = 1.0
    return round(price_change_pct / baseline_volatility, 2)
