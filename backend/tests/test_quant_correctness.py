import pytest
import numpy as np
import pandas as pd

from backend.app.backtesting.event_driven import (
    get_bars_per_year_for_timeframe,
    EventDrivenBacktester,
    StrategyHypothesis,
)
from backend.app.paper_engine.drift_engine import ModelDriftDetector
from backend.app.paper_engine.models import PaperTradeAudit, OrderSide, ExitReason


def test_annualization_factors_for_indian_equity_market():
    """
    Assert that annualization correctly reflects the NSE 375-min session (09:15 to 15:30 IST)
    and 252 trading days per calendar year.
    """
    # 1D: 1 bar per session -> 252 bars/year
    assert get_bars_per_year_for_timeframe("1D") == 252.0
    assert get_bars_per_year_for_timeframe("1d") == 252.0

    # 5m: 375 / 5 = 75 bars per session -> 75 * 252 = 18,900 bars/year
    assert get_bars_per_year_for_timeframe("5m") == 18900.0

    # 15m: 375 / 15 = 25 bars per session -> 25 * 252 = 6,300 bars/year
    assert get_bars_per_year_for_timeframe("15m") == 6300.0

    # 1h (60m): 375 / 60 = 6.25 bars per session -> 6.25 * 252 = 1,575 bars/year
    assert get_bars_per_year_for_timeframe("1h") == 1575.0

    # Weekly: 52 bars/year
    assert get_bars_per_year_for_timeframe("1w") == 52.0


def test_zero_volatility_sharpe_guard():
    """
    Assert that zero volatility or constant returns yield Sharpe = 0.0 without NaN or infinity.
    """
    # Constant equity curve (zero returns)
    eq_series = pd.Series([1000000.0] * 50)
    returns = eq_series.pct_change().dropna()
    assert len(returns) > 1
    ret_std = float(returns.std(ddof=1))
    assert ret_std == 0.0

    # Simulation with EventDrivenBacktester on flat data
    backtester = EventDrivenBacktester(initial_capital=1000000.0)
    flat_data = []
    for i in range(50):
        flat_data.append({
            "timestamp": 1700000000 + i * 300,
            "open": 2500.0,
            "high": 2500.0,
            "low": 2500.0,
            "close": 2500.0,
            "volume": 1000,
        })
    df = pd.DataFrame(flat_data)
    hyp = StrategyHypothesis(
        strategy_id="TEST",
        symbol="RELIANCE.NS",
        timeframe="5m",
    )
    res = backtester.run_backtest(df, hypothesis=hyp)
    # With zero trades or flat equity, Sharpe must be 0.0, not NaN or inf
    assert res["sharpe_ratio"] == 0.0
    assert not np.isnan(res["sharpe_ratio"])
    assert not np.isinf(res["sharpe_ratio"])


def test_drift_engine_zero_volatility_guard():
    """
    Assert that drift engine handles zero variance paper returns safely.
    """
    detector = ModelDriftDetector()
    trades = [
        PaperTradeAudit(
            trade_id=f"TRD_0{i}",
            signal_id="SIG_01",
            symbol="INFY.NS",
            strategy_id="TEST_STRAT",
            strategy_version="1.0.0",
            side=OrderSide.BUY,
            quantity=10,
            entry_timestamp=1700000000 + i * 3600,
            entry_price=1500.0,
            exit_timestamp=1700000000 + (i + 1) * 3600,
            exit_price=1550.0,
            exit_reason=ExitReason.TAKE_PROFIT,
            gross_pnl=500.0,
            net_pnl=480.0,
            fees_paid=20.0,
            slippage_paid=0.0,
            return_pct=3.2,  # identical return for all trades (zero variance)
            holding_period_bars=1,
        )
        for i in range(6)
    ]

    report = detector.evaluate_drift("TEST_STRAT", {"win_rate_pct": 80.0, "sharpe_ratio": 2.0}, trades)
    assert report.sample_size == 6
    # Finding sharpe metric
    sharpe_metric = next((m for m in report.metrics if "Sharpe" in m.metric_name), None)
    if sharpe_metric:
        # Must not be NaN or Infinity
        assert not np.isnan(sharpe_metric.paper_realized)
        assert not np.isinf(sharpe_metric.paper_realized)
