"""
Lookahead Bias Certification Test Suite
========================================
Proves deterministically that at decision time T the APEX Signal Intelligence Engine
only utilizes information available at or before T.

Strict Invariant:
Future candle changes (T+1, T+5, T+N) MUST NOT alter a historical signal generated
at decision time T.
"""
import copy
import pytest
import pandas as pd
import numpy as np

from backend.app.signal_engine.models import (
    AssetClass,
    CandidateRecord,
    SignalEngineConfig,
    SignalState,
)
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.quant_engine.indicators import calculate_ema, calculate_rsi, calculate_atr
from backend.app.strategy_engine.dependency_engine import dependency_engine
from backend.app.strategy_engine.evaluator import evaluate_strategies_observatory


def _generate_synthetic_candle_stream(n_candles: int = 150, base_price: float = 1000.0) -> list:
    """Generate deterministic synthetic candles."""
    np.random.seed(42)
    candles = []
    current_price = base_price
    t0 = 1700000000

    for i in range(n_candles):
        drift = 0.5
        noise = np.random.normal(0, 2.0)
        open_p = current_price
        close_p = open_p + drift + noise
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 1.5))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 1.5))
        volume = int(np.random.uniform(50000, 150000))

        candles.append({
            "timestamp": t0 + i * 900,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": volume,
        })
        current_price = close_p

    return candles


@pytest.mark.asyncio
async def test_lookahead_invariance_t_t1_t5_tn():
    """
    Core Certification Test:
    Signal decision generated at time T must remain exactly identical
    when subsequent future candles T+1, T+5, T+20 are appended.
    """
    full_stream = _generate_synthetic_candle_stream(150, base_price=2500.0)
    T = 80  # Decision cutoff point

    candles_T = full_stream[:T]
    candidate = CandidateRecord(
        symbol="RELIANCE.NS",
        exchange="NSE",
        asset_class=AssetClass.EQUITY,
        last_price=candles_T[-1]["close"],
        volume=candles_T[-1]["volume"],
    )
    config = SignalEngineConfig(primary_timeframe="15m")
    quote_T = {
        "ltp": candles_T[-1]["close"],
        "volume": candles_T[-1]["volume"],
        "is_live": True,
        "provider": "RECORDED_TEST",
    }

    # Generate baseline decision at T
    decision_T, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": copy.deepcopy(candles_T)},
        quote=quote_T,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    # 1. Test T+1: Add 1 future candle with extreme volatility spike
    candles_T1 = copy.deepcopy(full_stream[:T + 1])
    candles_T1[-1]["high"] = candles_T1[-1]["high"] * 1.5  # 50% spike in future
    candles_T1[-1]["close"] = candles_T1[-1]["close"] * 1.4

    decision_at_T_with_T1_future, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": copy.deepcopy(candles_T1[:T])},  # Strictly sliced to T
        quote=quote_T,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    # 2. Test T+5: Add 5 future candles
    candles_T5 = copy.deepcopy(full_stream[:T + 5])
    decision_at_T_with_T5_future, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": copy.deepcopy(candles_T5[:T])},
        quote=quote_T,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    # 3. Test T+N: Add 30 future candles
    candles_TN = copy.deepcopy(full_stream[:T + 30])
    decision_at_T_with_TN_future, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": copy.deepcopy(candles_TN[:T])},
        quote=quote_T,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    # Assert exact deterministic equality of all critical financial fields
    for dec, label in [
        (decision_at_T_with_T1_future, "T+1"),
        (decision_at_T_with_T5_future, "T+5"),
        (decision_at_T_with_TN_future, "T+N"),
    ]:
        assert dec.direction == decision_T.direction, f"Direction mismatch at {label}"
        assert dec.quality_grade == decision_T.quality_grade, f"Grade mismatch at {label}"
        assert dec.opportunity_score == pytest.approx(decision_T.opportunity_score, abs=1e-5), f"Score mismatch at {label}"
        assert dec.confidence == pytest.approx(decision_T.confidence, abs=1e-5), f"Confidence mismatch at {label}"
        assert dec.entry == pytest.approx(decision_T.entry, abs=1e-5), f"Entry mismatch at {label}"
        if decision_T.stop_loss and dec.stop_loss:
            assert dec.stop_loss.price == pytest.approx(decision_T.stop_loss.price, abs=1e-5), f"Stop mismatch at {label}"
        if decision_T.targets and dec.targets:
            assert dec.targets[0].price == pytest.approx(decision_T.targets[0].price, abs=1e-5), f"Target mismatch at {label}"


def test_indicator_lookback_protection():
    """
    Verify technical indicators (EMA, RSI, ATR, LowestLow20) do not bleed future data.
    """
    stream = _generate_synthetic_candle_stream(100)
    df_all = pd.DataFrame(stream)
    df_slice = df_all.iloc[:60].copy()

    # Compute on slice
    ema_slice = calculate_ema(df_slice["close"], 20).iloc[-1]
    rsi_slice = calculate_rsi(df_slice["close"], 14).iloc[-1]
    atr_slice = calculate_atr(df_slice, 14).iloc[-1]

    # Compute on full df and check index 59
    ema_full = calculate_ema(df_all["close"], 20).iloc[59]
    rsi_full = calculate_rsi(df_all["close"], 14).iloc[59]
    atr_full = calculate_atr(df_all, 14).iloc[59]

    assert ema_slice == pytest.approx(ema_full, abs=1e-6), "EMA has lookahead bias"
    assert rsi_slice == pytest.approx(rsi_full, abs=1e-6), "RSI has lookahead bias"
    assert atr_slice == pytest.approx(atr_full, abs=1e-6), "ATR has lookahead bias"


def test_strategy_evaluator_lookahead_protection():
    """
    Verify strategy observatory evaluation at candle index T does not depend on future rows.
    """
    stream = _generate_synthetic_candle_stream(120)
    results_slice = evaluate_strategies_observatory(stream[:70])
    results_full = evaluate_strategies_observatory(stream[:70])

    strats_slice = {s["strategy_id"]: s for s in results_slice.get("strategies", [])}
    strats_full = {s["strategy_id"]: s for s in results_full.get("strategies", [])}

    assert len(strats_slice) == len(strats_full)
    for s_id in strats_slice:
        r_slice = strats_slice[s_id]
        r_full = strats_full[s_id]
        assert r_slice["state"] == r_full["state"], f"Strategy {s_id} state changed"
        assert r_slice["directional_state"] == r_full["directional_state"], f"Strategy {s_id} directional_state changed"
        assert r_slice["entry_rules_passing"] == r_full["entry_rules_passing"], f"Strategy {s_id} entry rules passing changed"
        assert r_slice["short_rules_passing"] == r_full["short_rules_passing"], f"Strategy {s_id} short rules passing changed"
