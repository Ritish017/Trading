"""
Signal Engine Integration Tests
================================
Tests the complete signal pipeline with synthetic candle data.
Verifies determinism, gate logic, and data provenance labeling.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

import numpy as np
import pandas as pd

from backend.app.signal_engine.models import (
    SignalEngineConfig,
    SignalDirection,
    SignalQualityGrade,
    CandidateRecord,
    AssetClass,
    StrategyVote,
    StrategyVoteDirection,
)
from backend.app.signal_engine.validation_gates import (
    gate_data_validation,
    gate_risk_reward,
    gate_liquidity,
    ValidationGateResult,
    validation_pipeline,
)
from backend.app.signal_engine.confluence_engine import confluence_engine
from backend.app.signal_engine.stop_target_engine import stop_loss_engine, target_engine
from backend.app.signal_engine.scoring_engine import scoring_engine
from backend.app.signal_engine.signal_store import SignalStore
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal


def _make_candles(n=80, trend="up", base=1500.0) -> list:
    """Generate synthetic OHLCV candles."""
    candles = []
    price = base
    rng = np.random.RandomState(42)  # Fixed seed for determinism
    for i in range(n):
        if trend == "up":
            drift = 0.003
        elif trend == "down":
            drift = -0.003
        else:
            drift = 0.0
        pct = drift + rng.normal(0, 0.005)
        o = price
        c = price * (1 + pct)
        h = max(o, c) * (1 + abs(rng.normal(0, 0.002)))
        l = min(o, c) * (1 - abs(rng.normal(0, 0.002)))
        vol = int(rng.uniform(100000, 500000))
        candles.append({"open": round(o, 2), "high": round(h, 2), "low": round(l, 2),
                        "close": round(c, 2), "volume": vol,
                        "timestamp": 1700000000 + i * 900})
        price = c
    return candles


def _make_quote(price: float, volume: int = 5_000_000, is_live: bool = False) -> dict:
    return {
        "ltp": price,
        "previous_close": price * 0.98,
        "change_percent": 2.0,
        "volume": volume,
        "open": price * 0.99,
        "high": price * 1.01,
        "low": price * 0.97,
        "is_live": is_live,
        "provider": "TEST",
    }


def test_data_validation_gate_passes():
    candles = _make_candles(50)
    quote = _make_quote(1500.0, 10_000_000)
    config = SignalEngineConfig()
    gate = gate_data_validation(candles, quote, config)
    assert gate.result == ValidationGateResult.PASS, f"Expected PASS, got {gate.result}: {gate.reason}"
    print("✓ Gate 1: Data validation PASS with valid candles")


def test_data_validation_gate_fails_insufficient_candles():
    candles = _make_candles(5)  # Only 5 candles
    quote = _make_quote(1500.0)
    config = SignalEngineConfig()
    gate = gate_data_validation(candles, quote, config)
    assert gate.result == ValidationGateResult.FAIL, f"Expected FAIL for insufficient candles, got {gate.result}"
    print("✓ Gate 1: Data validation FAIL with 5 candles")


def test_rr_gate_blocks_low_rr():
    config = SignalEngineConfig(min_risk_reward=1.5)
    gate = gate_risk_reward(1.2, config)
    assert gate.result == ValidationGateResult.FAIL, f"Expected FAIL for R:R 1.2 < 1.5, got {gate.result}"
    print("✓ Gate 6: R:R 1.2 < 1.5 → FAIL")


def test_rr_gate_passes_good_rr():
    config = SignalEngineConfig(min_risk_reward=1.5)
    gate = gate_risk_reward(2.0, config)
    assert gate.result == ValidationGateResult.PASS, f"Expected PASS for R:R 2.0 >= 1.5, got {gate.result}"
    print("✓ Gate 6: R:R 2.0 >= 1.5 → PASS")


def test_liquidity_gate_fails_zero_volume():
    config = SignalEngineConfig()
    quote = _make_quote(100.0, volume=0)
    candles = _make_candles(30)
    gate, _ = gate_liquidity(quote, candles, config)
    assert gate.result == ValidationGateResult.FAIL, f"Expected FAIL for zero volume"
    print("✓ Gate 4: Zero volume → FAIL")


def test_confluence_engine_long_signal():
    """Test that 3+ independent long-voting families produce LONG confluence."""
    votes = [
        StrategyVote(strategy_id="EMA_GOLDEN_CROSS", strategy_name="EMA Golden Cross",
                     category="TREND", direction=StrategyVoteDirection.LONG, confidence=85, strength=80),
        StrategyVote(strategy_id="ADX_TREND_FILTER", strategy_name="ADX Trend",
                     category="TREND", direction=StrategyVoteDirection.LONG, confidence=75, strength=70),
        StrategyVote(strategy_id="RSI_MOMENTUM", strategy_name="RSI Momentum",
                     category="MOMENTUM", direction=StrategyVoteDirection.LONG, confidence=70, strength=65),
        StrategyVote(strategy_id="OBV_TREND", strategy_name="OBV Trend",
                     category="VOLUME", direction=StrategyVoteDirection.LONG, confidence=65, strength=60),
    ]
    result = confluence_engine.evaluate(votes)
    assert result.confluence_direction == SignalDirection.LONG, (
        f"Expected LONG, got {result.confluence_direction}: {result.confluence_label}"
    )
    assert result.independent_long_signals >= 3, (
        f"Expected >= 3 independent signals, got {result.independent_long_signals}"
    )
    print(f"✓ Confluence engine: {result.confluence_label} ({result.independent_long_signals} independent families)")


def test_confluence_engine_correlation_discount():
    """Test that correlated strategies get discounted."""
    # EMA + SMA + MACD are all TREND_MOVING_AVERAGE family → correlated!
    votes = [
        StrategyVote(strategy_id="EMA_GOLDEN_CROSS", strategy_name="EMA Cross",
                     category="TREND", direction=StrategyVoteDirection.LONG, confidence=85, strength=80),
        StrategyVote(strategy_id="SMA_TREND_FOLLOWING", strategy_name="SMA Trend",
                     category="TREND", direction=StrategyVoteDirection.LONG, confidence=80, strength=75),
        StrategyVote(strategy_id="MACD_TREND", strategy_name="MACD Trend",
                     category="TREND", direction=StrategyVoteDirection.LONG, confidence=75, strength=70),
    ]
    result = confluence_engine.evaluate(votes)
    # All three are in TREND_MOVING_AVERAGE family → 1 independent signal, not 3
    assert result.independent_long_signals == 1, (
        f"Expected 1 independent signal (all correlated), got {result.independent_long_signals}"
    )
    assert result.correlation_discount > 0, "Expected non-zero correlation discount"
    print(f"✓ Correlation detection: 3 correlated → {result.independent_long_signals} independent (discount {result.correlation_discount:.1f}%)")


def test_stop_loss_computes_for_long():
    candles = _make_candles(60, trend="up", base=1500.0)
    close_price = candles[-1]["close"]
    fv = {"close": close_price, "atr14": 15.0}
    config = SignalEngineConfig(stop_atr_multiple=1.5)
    stop = stop_loss_engine.compute("LONG", close_price, fv, [1450.0, 1430.0], [], config)
    assert stop is not None, "Expected stop loss result"
    assert stop.price < close_price, f"Stop {stop.price} should be below entry {close_price}"
    assert stop.risk_per_share > 0, "Risk per share should be positive"
    print(f"✓ Stop loss: Entry ₹{close_price:.2f} → Stop ₹{stop.price:.2f} ({stop.method})")


def test_determinism():
    """Same inputs → same output (deterministic)."""
    candles = _make_candles(60)
    close_price = candles[-1]["close"]
    fv = {"close": close_price, "atr14": 12.0}
    config = SignalEngineConfig()
    stop1 = stop_loss_engine.compute("LONG", close_price, fv, [1450.0], [], config)
    stop2 = stop_loss_engine.compute("LONG", close_price, fv, [1450.0], [], config)
    assert stop1 and stop2, "Both results should be non-None"
    assert stop1.price == stop2.price, f"Non-deterministic stop: {stop1.price} vs {stop2.price}"
    print(f"✓ Determinism: Same inputs produce same stop ₹{stop1.price:.2f}")


def test_signal_store_deduplication():
    """Test that same symbol+direction deduplicates properly."""
    from backend.app.signal_engine.models import SignalDecision, SignalDirection, SignalQualityGrade, SignalState, SignalType
    store = SignalStore()

    s1 = SignalDecision(
        symbol="RELIANCE.NS", direction=SignalDirection.LONG,
        signal_type=SignalType.EQUITY_LONG, state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A, opportunity_score=82.0,
        confidence=75.0, entry=1500.0,
    )
    s2 = SignalDecision(
        symbol="RELIANCE.NS", direction=SignalDirection.LONG,
        signal_type=SignalType.EQUITY_LONG, state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A, opportunity_score=84.0,
        confidence=77.0, entry=1502.0,  # Very close price → should update
    )

    id1 = store.upsert_signal(s1)
    active_before = store.get_active_signals()
    id2 = store.upsert_signal(s2)
    active_after = store.get_active_signals()

    assert len(active_before) == 1, f"Expected 1 active signal before, got {len(active_before)}"
    assert len(active_after) == 1, f"Expected 1 active signal after (dedup), got {len(active_after)}"
    assert id1 == id2, f"Deduplicated signal should preserve original ID: {id1} vs {id2}"
    print(f"✓ Signal deduplication: Same symbol+direction → preserved ID {id1[:8]}...")


def test_candidate_generator():
    """Test candidate screening based on momentum and volume."""
    from backend.app.signal_engine.candidate_generator import CandidateGenerator
    gen = CandidateGenerator()
    candles = _make_candles(35)
    # Give last candle high volume
    candles[-1]["volume"] = 10_000_000
    quote = _make_quote(120.0, volume=10_000_000)
    cand = gen.evaluate_symbol_candidate("INFY.NS", quote, candles)
    assert cand is not None, "Candidate generator should identify candidate"
    assert cand.priority_score >= 50.0
    assert len(cand.screening_reasons) > 0
    print(f"✓ Candidate generator: INFY.NS priority score {cand.priority_score:.1f}")


def test_no_trade_engine_explicit_rejection():
    """Test NO-TRADE engine categorization, advice, and audit trail."""
    from backend.app.signal_engine.no_trade_engine import no_trade_engine, NoTradeCategory
    decision, rejection = no_trade_engine.build_no_trade_decision(
        symbol="TATAMOTORS.NS",
        gate_id="HARD_GATE_RISK_REWARD",
        reason="Risk-reward ratio 1.15 is below 1.5 threshold",
        actual_value=1.15,
        threshold_value=1.5,
    )
    assert decision.direction == SignalDirection.NO_TRADE
    assert rejection.gate_failed == "HARD_GATE_RISK_REWARD"
    assert rejection.evidence is not None
    assert "retracement" in rejection.evidence.lower()
    analytics = no_trade_engine.get_rejection_analytics()
    assert analytics["by_category"].get(NoTradeCategory.RISK_REWARD, 0) >= 1
    print(f"✓ No-trade engine: Generated rejection with actionable advice: '{rejection.evidence}'")


def test_risk_engine_signal_validation():
    """Test upgraded risk engine validate_signal_risk."""
    from backend.app.risk_engine.risk import RiskEngine
    from backend.app.signal_engine.models import (
        PositionSizing,
        SignalDecision,
        SignalDirection,
        SignalQualityGrade,
        SignalState,
        SignalType,
    )
    risk = RiskEngine(max_drawdown_limit_pct=5.0, max_portfolio_risk_pct=2.0)
    
    # Healthy portfolio
    portfolio = {
        "capital": 500000.0,
        "available_capital": 500000.0,
        "initial_capital": 500000.0,
        "net_worth": 500000.0,
        "positions": [],
        "open_positions_count": 0,
    }
    
    pos_size = PositionSizing(
        method="FIXED_RISK",
        capital=500000.0,
        risk_per_trade_pct=1.0,
        max_risk_amount=5000.0,
        entry_price=100.0,
        stop_price=95.0,
        risk_per_share=5.0,
        quantity=50,
        capital_required=5000.0,
        maximum_loss=250.0,
    )
    
    signal = SignalDecision(
        symbol="TCS.NS",
        direction=SignalDirection.LONG,
        signal_type=SignalType.EQUITY_LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        opportunity_score=85.0,
        confidence=80.0,
        entry=100.0,
        position_size=pos_size,
    )
    
    # Check 1: Normal pass
    res = risk.validate_signal_risk(signal, portfolio)
    assert res.passed is True, f"Expected risk pass: {res.reason}"
    
    # Check 2: Max drawdown circuit breaker triggered
    portfolio_drawdown = dict(portfolio)
    portfolio_drawdown["net_worth"] = 450000.0  # 10% drawdown > 5% limit
    res_dd = risk.validate_signal_risk(signal, portfolio_drawdown)
    assert res_dd.passed is False
    assert "drawdown" in res_dd.reason.lower()
    print("✓ Risk engine signal validation: Healthy pass + circuit breaker catch verified")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("APEX Signal Engine — Integration Tests")
    print("=" * 60 + "\n")

    tests = [
        test_data_validation_gate_passes,
        test_data_validation_gate_fails_insufficient_candles,
        test_rr_gate_blocks_low_rr,
        test_rr_gate_passes_good_rr,
        test_liquidity_gate_fails_zero_volume,
        test_confluence_engine_long_signal,
        test_confluence_engine_correlation_discount,
        test_stop_loss_computes_for_long,
        test_determinism,
        test_signal_store_deduplication,
        test_candidate_generator,
        test_no_trade_engine_explicit_rejection,
        test_risk_engine_signal_validation,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: FAILED — {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: ERROR — {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed / {failed} failed / {len(tests)} total")
    if failed == 0:
        print("ALL TESTS PASSED ✓")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
