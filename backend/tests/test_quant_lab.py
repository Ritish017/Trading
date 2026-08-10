import pytest
import pandas as pd
import numpy as np
from backend.app.quant_engine.indicators import (
    calculate_ema, calculate_vwap, calculate_rsi, calculate_atr, calculate_bollinger_bands, detect_support_resistance
)
from backend.app.quant_engine.options import calculate_pcr, calculate_max_pain, classify_oi_pattern
from backend.app.quant_engine.regime import classify_market_regime
from backend.app.backtesting.event_driven import EventDrivenBacktester
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.candle_engine.aggregator import CandleAggregator
from backend.app.broker_providers.base import NormalizedTick

def test_indicators():
    prices = pd.Series([100.0, 102.0, 101.0, 104.0, 105.0, 107.0, 106.0, 108.0, 110.0, 109.0])
    ema20 = calculate_ema(prices, 5)
    rsi = calculate_rsi(prices, 5)
    assert len(ema20) == len(prices)
    assert len(rsi) == len(prices)
    assert not np.isnan(ema20.iloc[-1])

def test_pcr_max_pain():
    pcr = calculate_pcr(5000, 4000)
    assert pcr == 1.25

    strikes = [100.0, 105.0, 110.0]
    call_oi = [1000, 500, 100]
    put_oi = [100, 400, 1200]
    mp = calculate_max_pain(strikes, call_oi, put_oi)
    assert mp in strikes

def test_oi_pattern():
    assert classify_oi_pattern(1.5, 2.0) == "LONG_BUILDUP"
    assert classify_oi_pattern(-1.2, 3.0) == "SHORT_BUILDUP"

def test_candle_aggregator():
    agg = CandleAggregator()
    tick1 = NormalizedTick(symbol="RELIANCE.NS", ltp=2800.0, volume=100, timestamp=1700000000.0)
    tick2 = NormalizedTick(symbol="RELIANCE.NS", ltp=2810.0, volume=150, timestamp=1700000010.0)
    agg.process_tick(tick1)
    res = agg.process_tick(tick2)
    assert "5m" in res
    c = res["5m"]
    assert c["high"] == 2810.0
    assert c["low"] == 2800.0
    assert c["volume"] == 250

def test_paper_trading_engine():
    engine = PaperTradingEngine(initial_capital=1000000.0)
    order = PaperOrderRequest(
        symbol="RELIANCE.NS",
        productType="MIS (Intraday)",
        side="BUY",
        quantity=10,
        price=2800.0
    )
    res = engine.execute_order(order)
    assert res["status"] == "FILLED"
    assert len(engine.positions) == 1

def test_backtester():
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=100, freq="5min")
    close = 100 + np.cumsum(np.random.randn(100))
    high = close + np.random.rand(100)
    low = close - np.random.rand(100)
    open_p = close + np.random.randn(100) * 0.1
    vol = np.random.randint(100, 1000, 100)

    df = pd.DataFrame({
        "time": dates.astype(int) // 10**9,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "buy_signal": [i % 10 == 0 for i in range(100)],
        "sell_signal": [i % 10 == 5 for i in range(100)]
    })

    bt = EventDrivenBacktester(initial_capital=100000.0)
    results = bt.run_backtest(df)
    assert results["status"] == "SUCCESS"
    assert "total_return_pct" in results
