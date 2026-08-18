import time
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from backend.app.ai_engine.contracts import TechnicalSnapshot, DerivativeSnapshot, DataFreshness
from backend.app.quant_engine.indicators import detect_support_resistance

def determine_data_freshness(latest_timestamp: Optional[float], is_live_provider: bool = False) -> DataFreshness:
    """
    Truthful data freshness determination based on verified timestamp age and provider status.
    - LIVE: Active live feed with tick/candle timestamp within last 60 seconds.
    - RECENT: Timestamp within last 5 minutes.
    - STALE: Timestamp within last 24 hours.
    - UNAVAILABLE: Missing timestamp, older than 24 hours, or unconfigured feed.
    """
    if latest_timestamp is None or latest_timestamp <= 0:
        return DataFreshness.UNAVAILABLE

    now = time.time()
    age = now - latest_timestamp

    if age < 0: # Future or slight clock skew: treat as recent unless live
        return DataFreshness.LIVE if is_live_provider else DataFreshness.RECENT

    if is_live_provider and age <= 60.0:
        return DataFreshness.LIVE
    elif age <= 300.0:
        return DataFreshness.RECENT
    elif age <= 86400.0:
        return DataFreshness.STALE
    else:
        return DataFreshness.UNAVAILABLE

def compute_market_features(
    candles: List[Dict[str, Any]], 
    current_price: float, 
    prev_close: float,
    is_live_feed: bool = False
) -> TechnicalSnapshot:
    """
    Compute comprehensive quantitative and technical feature vector from OHLCV candles.
    Data sufficiency (candle count) determines indicator presence (returning None when insufficient).
    Data freshness is evaluated strictly from actual timestamps and provider state.
    """
    if not candles or len(candles) < 5:
        return TechnicalSnapshot(
            support_levels=[],
            resistance_levels=[],
            freshness=DataFreshness.UNAVAILABLE
        )

    # Extract latest candle timestamp for truthful freshness calculation
    last_candle = candles[-1]
    latest_ts = last_candle.get("timestamp") or last_candle.get("time")
    try:
        latest_ts = float(latest_ts) if latest_ts is not None else None
    except (ValueError, TypeError):
        latest_ts = None

    freshness_level = determine_data_freshness(latest_ts, is_live_provider=is_live_feed)

    df = pd.DataFrame(candles)
    close = df['close'].astype(float)
    high = df['high'].astype(float) if 'high' in df else close
    low = df['low'].astype(float) if 'low' in df else close
    volume = df['volume'].astype(float) if 'volume' in df else pd.Series([0.0] * len(df))

    # 1. EMAs - require actual sufficiency of bars for each period
    ema20_series = close.ewm(span=20, adjust=False).mean() if len(close) >= 20 else None
    ema50_series = close.ewm(span=50, adjust=False).mean() if len(close) >= 50 else None
    ema2000_series = close.ewm(span=200, adjust=False).mean() if len(close) >= 200 else None

    ema_20 = float(ema20_series.iloc[-1]) if ema20_series is not None and len(ema20_series) > 0 else None
    ema_50 = float(ema50_series.iloc[-1]) if ema50_series is not None and len(ema50_series) > 0 else None
    ema_200 = float(ema2000_series.iloc[-1]) if ema2000_series is not None and len(ema2000_series) > 0 else None

    # 2. RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 and not pd.isna(rsi_series.iloc[-1]) else None

    # 3. MACD (12, 26, 9)
    if len(close) >= 26:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line

        macd = float(macd_line.iloc[-1]) if len(macd_line) > 0 else None
        macd_signal = float(signal_line.iloc[-1]) if len(signal_line) > 0 else None
        macd_histogram = float(macd_hist.iloc[-1]) if len(macd_hist) > 0 else None
    else:
        macd, macd_signal, macd_histogram = None, None, None

    # 4. ATR (14)
    if len(close) >= 14:
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(window=14, min_periods=14).mean()
        atr_14 = float(atr_series.iloc[-1]) if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]) else None
    else:
        atr_14 = None

    # 5. Relative Volume (RVOL) = Current Volume / 20-period SMA Volume
    vol_sma20 = volume.rolling(window=min(20, len(volume)), min_periods=5).mean()
    current_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0.0
    if len(vol_sma20) > 0 and vol_sma20.iloc[-1] > 0 and current_vol > 0:
        rvol = float(current_vol / vol_sma20.iloc[-1])
    else:
        rvol = None

    # 6. Bollinger Bands (20, 2)
    if len(close) >= 20:
        sma20 = close.rolling(window=20, min_periods=20).mean()
        std20 = close.rolling(window=20, min_periods=20).std().fillna(0)
        bb_mid = float(sma20.iloc[-1]) if len(sma20) > 0 and not pd.isna(sma20.iloc[-1]) else None
        bb_up = float(bb_mid + 2 * std20.iloc[-1]) if bb_mid is not None else None
        bb_low = float(bb_mid - 2 * std20.iloc[-1]) if bb_mid is not None else None
    else:
        bb_mid, bb_up, bb_low = None, None, None

    # 7. Support & Resistance Levels
    levels = detect_support_resistance(df)
    sup_sorted = [s for s in levels["support"] if s < current_price][:3]
    res_sorted = [r for r in levels["resistance"] if r > current_price][:3]

    return TechnicalSnapshot(
        rsi_14=round(rsi_14, 1) if rsi_14 is not None else None,
        macd=round(macd, 2) if macd is not None else None,
        macd_signal=round(macd_signal, 2) if macd_signal is not None else None,
        macd_histogram=round(macd_histogram, 2) if macd_histogram is not None else None,
        ema_20=round(ema_20, 2) if ema_20 is not None else None,
        ema_50=round(ema_50, 2) if ema_50 is not None else None,
        ema_200=round(ema_200, 2) if ema_200 is not None else None,
        sma_20=round(bb_mid, 2) if bb_mid is not None else None,
        atr_14=round(atr_14, 2) if atr_14 is not None else None,
        bb_upper=round(bb_up, 2) if bb_up is not None else None,
        bb_middle=round(bb_mid, 2) if bb_mid is not None else None,
        bb_lower=round(bb_low, 2) if bb_low is not None else None,
        relative_volume=round(rvol, 2) if rvol is not None else None,
        support_levels=[round(x, 2) for x in sup_sorted],
        resistance_levels=[round(x, 2) for x in res_sorted],
        freshness=freshness_level
    )

def compute_z_score(price_change_pct: float, baseline_volatility: float = 1.2) -> float:
    """Computes statistical z-score of an intraday percentage price move."""
    if baseline_volatility <= 0:
        baseline_volatility = 1.0
    return round(price_change_pct / baseline_volatility, 2)
