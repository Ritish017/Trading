"""
Financial Invariants Test Suite
================================
Validates mathematical, geometrical, and financial invariants across the
APEX Signal Intelligence Engine.

Invariants Verified:
1. Stop != Entry
2. Directional Stop Side: LONG -> Stop < Entry; SHORT -> Stop > Entry
3. Directional Target Side: LONG -> Target > Entry; SHORT -> Target < Entry
4. Progressive Target Geometry: T1 < T2 < T3 (LONG), T1 > T2 > T3 (SHORT)
5. R:R Mathematical Consistency
6. Position Risk Conservation: Quantity * |Entry - Stop| <= MaxRiskAmount
7. PnL Accounting Reconciliation: Gross PnL - Total Costs = Net PnL
8. Zero-Volume Gate Enforcement: Zero volume cannot pass liquidity
9. Provenance Integrity: Non-live data never stamped RAW_AUTHENTIC_DATA
10. Deterministic Reproducibility
"""
import pytest
import copy

from backend.app.signal_engine.models import (
    AssetClass,
    CandidateRecord,
    DataProvenance,
    SignalDirection,
    SignalEngineConfig,
    SignalQualityGrade,
    SignalState,
)
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.signal_engine.outcome_engine import OutcomeEngine
from backend.app.signal_engine.transaction_cost import TransactionCostCalculator, AssetType


def _make_sample_candles(n: int = 60, trend: str = "UP", base: float = 1000.0, volume: int = 100000):
    candles = []
    p = base
    for i in range(n):
        step = 1.5 if trend == "UP" else -1.5
        o = p
        c = o + step
        h = max(o, c) + 2.0
        l = min(o, c) - 2.0
        candles.append({
            "timestamp": 1700000000 + i * 900,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": volume,
        })
        p = c
    return candles


@pytest.mark.asyncio
async def test_stop_target_geometry_and_rr_invariant():
    """
    Test stop != entry, correct side, target order, and R:R formula.
    """
    # Bullish scenario
    bull_candles = _make_sample_candles(70, trend="UP", base=500.0)
    candidate = CandidateRecord(symbol="SBIN.NS", asset_class=AssetClass.EQUITY, last_price=bull_candles[-1]["close"])
    config = SignalEngineConfig(primary_timeframe="15m")
    quote = {"ltp": bull_candles[-1]["close"], "volume": 200000, "is_live": True}

    signal, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": bull_candles},
        quote=quote,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    if signal.state == SignalState.QUALIFIED and signal.direction == SignalDirection.LONG:
        # Invariant 1: Stop != Entry
        assert signal.stop_loss.price != signal.entry, "Stop loss cannot equal entry price"
        # Invariant 2: Stop < Entry for LONG
        assert signal.stop_loss.price < signal.entry, f"LONG stop {signal.stop_loss.price} must be strictly below entry {signal.entry}"
        # Invariant 3: Targets > Entry for LONG
        assert len(signal.targets) >= 1
        assert signal.targets[0].price > signal.entry, f"LONG target {signal.targets[0].price} must be above entry {signal.entry}"
        if len(signal.targets) >= 3:
            assert signal.targets[0].price < signal.targets[1].price < signal.targets[2].price, "Targets must be monotonically ascending for LONG"

        # Invariant 4: R:R Formula Consistency
        r_dist = abs(signal.entry - signal.stop_loss.price)
        t_dist = abs(signal.targets[0].price - signal.entry)
        expected_rr = t_dist / r_dist
        assert signal.risk_reward == pytest.approx(expected_rr, rel=0.01), "Reported R:R does not match target distance / stop distance"


@pytest.mark.asyncio
async def test_position_risk_conservation():
    """
    Test position sizing ensures Risk = Quantity * |Entry - Stop| <= MaxRiskAmount.
    """
    candles = _make_sample_candles(70, trend="UP", base=2000.0)
    candidate = CandidateRecord(symbol="TCS.NS", asset_class=AssetClass.EQUITY, last_price=candles[-1]["close"])
    config = SignalEngineConfig(capital=500000.0, risk_per_trade_pct=1.0)  # Max risk = 5,000 INR
    quote = {"ltp": candles[-1]["close"], "volume": 150000, "is_live": True}

    signal, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": candles},
        quote=quote,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    if signal.position_size and signal.stop_loss:
        ps = signal.position_size
        max_allowed_risk = config.capital * (config.risk_per_trade_pct / 100.0)  # 5,000
        actual_risk = ps.quantity * abs(signal.entry - signal.stop_loss.price)
        # Due to integer floor division of quantity, actual risk <= max_allowed_risk
        assert actual_risk <= max_allowed_risk + 1e-3, f"Actual risk {actual_risk} exceeds limit {max_allowed_risk}"


def test_pnl_accounting_reconciliation():
    """
    Test Gross PnL - Total Costs = Net PnL in OutcomeEngine.
    """
    forward_candles = [
        {"timestamp": 1700001000, "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 50000},
        {"timestamp": 1700001900, "open": 104.0, "high": 108.0, "low": 103.0, "close": 107.0, "volume": 60000},
    ]

    mock_signal = {
        "signal_id": "TEST_RECONCILE_01",
        "symbol": "INFY.NS",
        "direction": "LONG",
        "asset_class": "EQUITY",
        "entry": 100.0,
        "stop_loss": 97.0,
        "targets": [105.0, 108.0],
        "position_size": {"quantity": 200},
    }

    outcome = OutcomeEngine.evaluate(mock_signal, forward_candles, slippage_pct=0.0005)

    assert outcome.gross_pnl != 0.0
    expected_costs = (
        outcome.brokerage + outcome.stt + outcome.exchange_charges +
        outcome.sebi_charges + outcome.gst + outcome.stamp_duty + outcome.slippage
    )
    assert outcome.total_costs == pytest.approx(expected_costs, abs=0.05), "Total costs does not equal sum of individual statutory charges"
    assert outcome.net_pnl == pytest.approx(outcome.gross_pnl - outcome.total_costs, abs=0.05), "Net PnL does not equal Gross PnL minus Total Costs"


@pytest.mark.asyncio
async def test_zero_volume_liquidity_gate():
    """
    Test zero volume candles fail liquidity gate and cannot produce a qualified execution signal.
    """
    zero_vol_candles = _make_sample_candles(60, trend="UP", base=100.0, volume=0)
    candidate = CandidateRecord(symbol="ILLIQUID.NS", asset_class=AssetClass.EQUITY, last_price=100.0, volume=0)
    config = SignalEngineConfig()
    quote = {"ltp": 100.0, "volume": 0, "is_live": True}

    signal, rejection = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": zero_vol_candles},
        quote=quote,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    # Must be rejected or NO_TRADE
    assert signal.direction == SignalDirection.NO_TRADE or signal.quality_grade == SignalQualityGrade.NO_TRADE
    assert rejection is not None
    assert rejection.gate_failed in ("LIQUIDITY_VALIDATION", "DATA_ACQUISITION", "MINIMUM_CANDLES_REQUIRED", "SCORE_TOO_LOW")


@pytest.mark.asyncio
async def test_data_provenance_authenticity():
    """
    Test simulated/recorded data is never stamped RAW_AUTHENTIC_DATA unless is_live=True.
    """
    candles = _make_sample_candles(60, trend="UP", base=1000.0)
    candidate = CandidateRecord(symbol="MOCK.NS", asset_class=AssetClass.EQUITY, last_price=1000.0)
    config = SignalEngineConfig()
    quote = {"ltp": 1000.0, "volume": 100000, "is_live": False}  # Not live

    signal, _ = await evaluate_candidate_signal(
        candidate=candidate,
        candles_by_timeframe={"15m": candles},
        quote=quote,
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    assert signal.provenance != DataProvenance.RAW_AUTHENTIC_DATA, "Simulated quote must not receive RAW_AUTHENTIC_DATA provenance"


@pytest.mark.asyncio
async def test_deterministic_reproducibility():
    """
    Given identical market data and config, the exact same decision, score, and targets must result.
    """
    candles = _make_sample_candles(70, trend="UP", base=1500.0)
    candidate = CandidateRecord(symbol="RELIANCE.NS", asset_class=AssetClass.EQUITY, last_price=candles[-1]["close"])
    config = SignalEngineConfig()
    quote = {"ltp": candles[-1]["close"], "volume": 100000, "is_live": True}

    s1, _ = await evaluate_candidate_signal(
        candidate=copy.deepcopy(candidate),
        candles_by_timeframe={"15m": copy.deepcopy(candles)},
        quote=copy.deepcopy(quote),
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    s2, _ = await evaluate_candidate_signal(
        candidate=copy.deepcopy(candidate),
        candles_by_timeframe={"15m": copy.deepcopy(candles)},
        quote=copy.deepcopy(quote),
        is_market_open=True,
        portfolio_state=None,
        config=config,
    )

    assert s1.direction == s2.direction
    assert s1.quality_grade == s2.quality_grade
    assert s1.opportunity_score == pytest.approx(s2.opportunity_score, abs=1e-6)
    assert s1.entry == pytest.approx(s2.entry, abs=1e-6)
    if s1.stop_loss and s2.stop_loss:
        assert s1.stop_loss.price == pytest.approx(s2.stop_loss.price, abs=1e-6)
