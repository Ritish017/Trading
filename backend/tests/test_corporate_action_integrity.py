import pytest
import time
import datetime
from backend.app.market_data.corporate_actions.models import (
    CorporateActionType,
    PriceAdjustmentMode,
    AnomalyClassification,
    CorporateActionEvent,
)
from backend.app.market_data.corporate_actions.registry import (
    CorporateActionRegistry,
    _date_to_epoch_start,
)
from backend.app.market_data.corporate_actions.adjuster import (
    CorporateActionAdjuster,
)
from backend.app.market_data.corporate_actions.integrity_guard import (
    MarketDataIntegrityGuard,
)
from backend.app.quant_engine.indicators import calculate_ema, calculate_vwap, calculate_rsi

def test_hdfcbank_bonus_critical_regression():
    """
    CRITICAL REGRESSION TEST (Section 24):
    Proves that for HDFCBANK (1:1 Bonus, Ex-Date: 2025-08-26, factor: 2.0):
    1. Pre-bonus historical price (₹1960) becomes ₹980 in ADJUSTED mode.
    2. In RAW mode, pre-bonus price remains ₹1960.
    3. Current post-bonus live price (₹725.50) strictly remains ₹725.50 (NOT ₹362.50, NOT ₹1450).
    4. Post-bonus historical candles (e.g. from Sep 2025) are NOT double-adjusted.
    """
    registry = CorporateActionRegistry()
    adjuster = CorporateActionAdjuster(registry=registry)

    # Pre-bonus candle: Aug 15, 2025 (timestamp: 1755216000)
    pre_bonus_ts = _date_to_epoch_start("2025-08-15")
    pre_bonus_candle = {
        "timestamp": pre_bonus_ts,
        "time": pre_bonus_ts,
        "open": 1950.0,
        "high": 1980.0,
        "low": 1940.0,
        "close": 1960.0,
        "volume": 100000,
        "vwap": 1960.0,
    }

    # Post-bonus candle: Sep 05, 2025 (timestamp: 1757030400)
    post_bonus_ts = _date_to_epoch_start("2025-09-05")
    post_bonus_candle = {
        "timestamp": post_bonus_ts,
        "time": post_bonus_ts,
        "open": 720.0,
        "high": 735.0,
        "low": 718.0,
        "close": 730.0,
        "volume": 200000,
        "vwap": 728.0,
    }

    # 1. Pre-bonus candle in ADJUSTED mode
    adj_pre = adjuster.adjust_candle(pre_bonus_candle, "HDFCBANK.NS", mode=PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE)
    assert adj_pre["open"] == 975.0
    assert adj_pre["high"] == 990.0
    assert adj_pre["low"] == 970.0
    assert adj_pre["close"] == 980.0
    assert adj_pre["volume"] == 200000 # Volume doubled for 1:1 bonus
    assert adj_pre["vwap"] == 980.0
    assert adj_pre["price_adjustment_mode"] == "ADJUSTED"
    assert adj_pre["adjustment_factor_applied"] == 2.0

    # 2. Pre-bonus candle in RAW mode
    raw_pre = adjuster.adjust_candle(pre_bonus_candle, "HDFCBANK.NS", mode=PriceAdjustmentMode.RAW_EXCHANGE_PRICE)
    assert raw_pre["open"] == 1950.0
    assert raw_pre["close"] == 1960.0
    assert raw_pre["volume"] == 100000
    assert raw_pre["price_adjustment_mode"] == "RAW"
    assert raw_pre["adjustment_factor_applied"] == 1.0

    # 3. Post-bonus candle in ADJUSTED mode (MUST NOT be double adjusted!)
    adj_post = adjuster.adjust_candle(post_bonus_candle, "HDFCBANK.NS", mode=PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE)
    assert adj_post["open"] == 720.0
    assert adj_post["close"] == 730.0
    assert adj_post["volume"] == 200000
    assert adj_post["adjustment_factor_applied"] == 1.0

    # 4. Live Quote Rule: Live quote of ₹725.50 must NEVER be divided or multiplied
    raw_live_quote = {
        "symbol": "HDFCBANK.NS",
        "ltp": 725.50,
        "previous_close": 722.00,
        "open": 722.00,
        "high": 728.00,
        "low": 720.50,
        "close": 725.50,
        "volume": 500000,
        "timestamp": time.time(),
        "source": "UPSTOX"
    }
    validated_live = adjuster.validate_live_quote(raw_live_quote, "HDFCBANK.NS")
    assert validated_live["ltp"] == 725.50
    assert validated_live["close"] == 725.50
    assert validated_live["price_domain"] == "CURRENT_EXCHANGE_PRICE"
    assert validated_live["adjustment"] == "N/A — live quote"
    assert validated_live["ltp"] != 362.50
    assert validated_live["ltp"] != 1450.0

def test_generic_stock_split_and_reverse_split():
    """Test generic 2:1 split and 1:2 reverse split corporate actions."""
    registry = CorporateActionRegistry()
    adjuster = CorporateActionAdjuster(registry=registry)

    # Register 2:1 split for ABC.NS on 2026-01-10 (factor: 2.0)
    registry.register_action(
        CorporateActionEvent(
            symbol="ABC.NS",
            action_type=CorporateActionType.SPLIT,
            ex_date="2026-01-10",
            ratio_before=1.0,
            ratio_after=2.0,
            adjustment_factor=2.0,
            effective_timestamp=_date_to_epoch_start("2026-01-10"),
        )
    )

    # Register 1:2 reverse split for XYZ.NS on 2026-01-15 (factor: 0.5)
    registry.register_action(
        CorporateActionEvent(
            symbol="XYZ.NS",
            action_type=CorporateActionType.REVERSE_SPLIT,
            ex_date="2026-01-15",
            ratio_before=2.0,
            ratio_after=1.0,
            adjustment_factor=0.5,
            effective_timestamp=_date_to_epoch_start("2026-01-15"),
        )
    )

    # Pre-split ABC.NS (Jan 05, 2026)
    abc_candle = {
        "timestamp": _date_to_epoch_start("2026-01-05"),
        "open": 3000.0, "high": 3050.0, "low": 2980.0, "close": 3000.0,
        "volume": 50000, "vwap": 3010.0
    }
    abc_adj = adjuster.adjust_candle(abc_candle, "ABC.NS")
    assert abc_adj["close"] == 1500.0
    assert abc_adj["volume"] == 100000
    assert abc_adj["vwap"] == 1505.0

    # Pre-reverse-split XYZ.NS (Jan 05, 2026)
    xyz_candle = {
        "timestamp": _date_to_epoch_start("2026-01-05"),
        "open": 50.0, "high": 52.0, "low": 49.0, "close": 50.0,
        "volume": 200000, "vwap": 50.3
    }
    xyz_adj = adjuster.adjust_candle(xyz_candle, "XYZ.NS")
    assert xyz_adj["close"] == 100.0
    assert xyz_adj["volume"] == 100000 # Reverse split halves the share quantity
    assert xyz_adj["vwap"] == 100.6

def test_indicator_consistency_across_adjusted_series():
    """Verify EMA and VWAP calculations operate on continuous adjusted domain without artificial discontinuities."""
    registry = CorporateActionRegistry()
    adjuster = CorporateActionAdjuster(registry=registry)

    # Build sequence of candles spanning across the HDFCBANK bonus ex-date (Aug 26, 2025)
    # Pre-bonus unadjusted raw prices were ~1450, post-bonus raw prices are ~725
    raw_series = []
    # 5 candles before ex-date
    for d in range(15, 20):
        raw_series.append({
            "timestamp": _date_to_epoch_start(f"2025-08-{d:02d}"),
            "open": 1440.0, "high": 1460.0, "low": 1435.0, "close": 1450.0,
            "volume": 100000, "vwap": 1448.0
        })
    # 5 candles after ex-date
    for d in range(27, 32):
        raw_series.append({
            "timestamp": _date_to_epoch_start(f"2025-08-{d:02d}"),
            "open": 720.0, "high": 730.0, "low": 718.0, "close": 725.0,
            "volume": 200000, "vwap": 724.0
        })

    # Adjust the series
    adj_series = adjuster.adjust_candle_series(raw_series, "HDFCBANK.NS", mode=PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE)
    
    # Check that pre-bonus prices adjusted from 1450 to 725
    for c in adj_series[:5]:
        assert c["close"] == 725.0
        assert c["volume"] == 200000
    for c in adj_series[5:]:
        assert c["close"] == 725.0
        assert c["volume"] == 200000

    # Indicators calculated over adj_series have 0 discontinuity variance
    import pandas as pd
    closes = pd.Series([c["close"] for c in adj_series])
    ema_vals = calculate_ema(closes, period=5)
    assert round(float(ema_vals.iloc[-1]), 2) == 725.00

    df = pd.DataFrame(adj_series)
    vwap_vals = calculate_vwap(df)
    assert round(float(vwap_vals.iloc[-1]), 2) == 724.25

def test_market_data_integrity_guard_and_live_claim():
    """Verify live claim validation and price anomaly classification."""
    guard = MarketDataIntegrityGuard()

    # 1. Dev Mock Provider must NOT claim LIVE • UPSTOX
    mock_claim = guard.validate_live_claim(
        provider="MOCK",
        is_provider_authenticated=False,
        is_provider_connected=True,
        provider_timestamp=time.time(),
        current_price=725.50,
        previous_close=722.00
    )
    assert mock_claim["can_claim_live"] is False
    assert mock_claim["provenance_status"] == "DEV_MOCK"
    assert mock_claim["display_label"] == "SIMULATED • DEV MOCK"

    # 2. Authentic fresh UPSTOX feed must claim LIVE • UPSTOX
    live_claim = guard.validate_live_claim(
        provider="UPSTOX",
        is_provider_authenticated=True,
        is_provider_connected=True,
        provider_timestamp=time.time(),
        current_price=725.50,
        previous_close=722.00
    )
    assert live_claim["can_claim_live"] is True
    assert live_claim["provenance_status"] == "AUTHENTIC_LIVE"
    assert live_claim["display_label"] == "LIVE • UPSTOX"

    # 3. Stale Upstox tick (>120s old)
    stale_claim = guard.validate_live_claim(
        provider="UPSTOX",
        is_provider_authenticated=True,
        is_provider_connected=True,
        provider_timestamp=time.time() - 300, # 5 min old
        current_price=725.50,
        previous_close=722.00
    )
    assert stale_claim["can_claim_live"] is False
    assert stale_claim["provenance_status"] == "STALE"

    # 4. Anomaly classification: 1:1 Bonus detection for HDFCBANK
    classification, reason = guard.classify_price_movement(
        symbol="HDFCBANK.NS",
        current_price=725.0,
        previous_close=1450.0, # ~50% drop matching 1:1 bonus
        timestamp=_date_to_epoch_start("2025-08-26")
    )
    assert classification == AnomalyClassification.BONUS
    assert "Bonus" in reason

    # 5. Unexplained price corruption (e.g. dropped by 70% with no corporate action)
    unexplained_cls, _ = guard.classify_price_movement(
        symbol="TCS.NS",
        current_price=1000.0,
        previous_close=4200.0,
        timestamp=time.time()
    )
    assert unexplained_cls == AnomalyClassification.PRICE_INTEGRITY_ERROR
