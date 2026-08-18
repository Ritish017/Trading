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

def test_zero_volume_vwap():
    df = pd.DataFrame({
        "high": [100.0, 102.0],
        "low": [98.0, 99.0],
        "close": [100.0, 101.0],
        "volume": [0.0, 0.0]
    })
    vwap_series = calculate_vwap(df)
    assert pd.isna(vwap_series.iloc[0])
    assert pd.isna(vwap_series.iloc[1])

    agg = CandleAggregator()
    tick_zero = NormalizedTick(symbol="TEST.NS", ltp=100.0, volume=0, timestamp=1700000000.0)
    res = agg.process_tick(tick_zero)
    assert res["5m"]["vwap"] is None

def test_cumulative_volume_deltas_and_reset():
    agg = CandleAggregator()
    # Sequence: 1000, 1100, 1250, 1300
    t1 = NormalizedTick(symbol="TCS.NS", ltp=3500.0, volume=1000, timestamp=1700000000.0, is_cumulative_volume=True)
    r1 = agg.process_tick(t1)
    assert r1["5m"]["volume"] == 0 # Baseline

    t2 = NormalizedTick(symbol="TCS.NS", ltp=3505.0, volume=1100, timestamp=1700000005.0, is_cumulative_volume=True)
    r2 = agg.process_tick(t2)
    assert r2["5m"]["volume"] == 100

    t3 = NormalizedTick(symbol="TCS.NS", ltp=3510.0, volume=1250, timestamp=1700000010.0, is_cumulative_volume=True)
    r3 = agg.process_tick(t3)
    assert r3["5m"]["volume"] == 250 # 100 + 150

    t4 = NormalizedTick(symbol="TCS.NS", ltp=3515.0, volume=1300, timestamp=1700000015.0, is_cumulative_volume=True)
    r4 = agg.process_tick(t4)
    assert r4["5m"]["volume"] == 300 # 100 + 150 + 50

    # Reset: 1300 -> 50
    t5 = NormalizedTick(symbol="TCS.NS", ltp=3520.0, volume=50, timestamp=1700000020.0, is_cumulative_volume=True)
    r5 = agg.process_tick(t5)
    assert r5["5m"]["volume"] == 350 # Added 50 with no negative volume

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

def test_backtester_conservative_execution():
    # Construct bars (len >= 15) where bar 2 touches BOTH target and stop
    n_bars = 20
    df = pd.DataFrame({
        "time": [1700000000 + i * 300 for i in range(n_bars)],
        "open": [100.0] * n_bars,
        "high": [101.0 if i != 2 else 150.0 for i in range(n_bars)], # Bar 2 high touches target
        "low": [99.0 if i != 2 else 50.0 for i in range(n_bars)],    # Bar 2 low touches stop
        "close": [100.0] * n_bars,
        "volume": [1000] * n_bars,
        "buy_signal": [True if i == 1 else False for i in range(n_bars)],
        "sell_signal": [False] * n_bars
    })
    bt = EventDrivenBacktester(initial_capital=100000.0, slippage_pct=0.0, brokerage_per_trade=0.0)
    results = bt.run_backtest(df, target_atr_multiple=1.0, stop_atr_multiple=1.0)
    assert results["status"] == "SUCCESS"
    assert results["totalTrades"] == 1
    # Conservative policy: stop loss prioritized over target on ambiguous bar
    assert results["trades"][0]["reason"] == "STOP_LOSS"
