import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (SMA)"""
    return series.rolling(window=period).mean()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average (EMA)"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price (VWAP)
    Requires df columns: 'high', 'low', 'close', 'volume'
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    tp_vol = typical_price * df['volume']
    cum_tp_vol = tp_vol.cumsum()
    cum_vol = df['volume'].cumsum()
    vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, df['close'])
    return pd.Series(vwap, index=df.index)

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    
    rs = np.where(avg_loss == 0, 100.0, avg_gain / avg_loss)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return pd.Series(rsi, index=series.index)

def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD Indicator
    Returns: (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(series, fast)
    slow_ema = calculate_ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (ATR)
    Requires df columns: 'high', 'low', 'close'
    """
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr

def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands
    Returns: (middle_band, upper_band, lower_band)
    """
    middle = calculate_sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return middle, upper, lower

def detect_support_resistance(df: pd.DataFrame, num_levels: int = 3) -> Dict[str, List[float]]:
    """
    Pivot Point & Historical Level Support & Resistance Finder based on factual swing extrema.
    Returns authentic levels or empty lists if data is insufficient.
    """
    if df.empty or len(df) < 5:
        return {"support": [], "resistance": []}

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    ltp = closes[-1]

    # Calculate Local Minima & Maxima
    res = []
    sup = []

    for i in range(2, len(df) - 2):
        if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
            if highs[i] > ltp:
                res.append(round(float(highs[i]), 2))
        if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
            if lows[i] < ltp:
                sup.append(round(float(lows[i]), 2))

    # If no local pivot was formed (e.g. strong monotonic trend), include session extremes
    if not sup:
        session_low = round(float(np.min(lows)), 2)
        if session_low < ltp:
            sup.append(session_low)
    if not res:
        session_high = round(float(np.max(highs)), 2)
        if session_high > ltp:
            res.append(session_high)

    res = sorted(list(set(res)))[:num_levels]
    sup = sorted(list(set(sup)), reverse=True)[:num_levels]

    return {"support": sup, "resistance": res}

def calculate_roc(series: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (ROC)"""
    return ((series - series.shift(period)) / series.shift(period)) * 100.0

def calculate_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Stochastic Oscillator (%K, %D)
    Requires df columns: 'high', 'low', 'close'
    """
    lowest_low = df['low'].rolling(window=k_period).min()
    highest_high = df['high'].rolling(window=k_period).max()
    denom = highest_high - lowest_low
    stoch_k = np.where(denom != 0, ((df['close'] - lowest_low) / denom) * 100.0, 50.0)
    k_series = pd.Series(stoch_k, index=df.index)
    d_series = k_series.rolling(window=d_period).mean()
    return k_series, d_series

def calculate_relative_volume(series: pd.Series, period: int = 20) -> pd.Series:
    """Relative Volume (RVOL) = Current Volume / Average Volume(period)"""
    avg_vol = series.rolling(window=period).mean()
    return np.where(avg_vol > 0, series / avg_vol, 1.0)

