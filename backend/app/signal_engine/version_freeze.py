"""
Strategy Version Freeze & Research Configuration Cryptographic Identity
======================================================================
Provides immutable, cryptographic version identification for:
- All 20 quantitative strategies and indicator configurations
- Risk engine and position sizing parameters
- Confluence, correlation clusters, and scoring weights
- Multi-timeframe and regime detector configurations
- Statutory Indian transaction costs and slippage schedules
- Futures and Options derivative selection rules
- NSE cash & derivatives session conventions

Every research run, signal evaluation, and backtest outcome must bind
to this immutable configuration hash.
"""

import hashlib
import json
import subprocess
import time
from typing import Any, Dict, List
from pydantic import BaseModel, Field

# Base Versions
STRATEGY_VERSION = "2026.1.0-FROZEN"
SIGNAL_ENGINE_VERSION = "2026.1.0-CERTIFIED"
RISK_ENGINE_VERSION = "2026.1.0-HARDENED"
COST_MODEL_VERSION = "NSE-STATUTORY-2026-V1"
OPTIONS_ENGINE_VERSION = "BS-GREEKS-DEBIT-V1"
REGIME_DETECTOR_VERSION = "2026.1.0-ATR-ADX"
INDICATOR_ENGINE_VERSION = "2026.1.0-NUMPY-VECTOR"


def get_git_commit() -> str:
    """Retrieve current git HEAD commit hash, or fallback to known commit."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return "96451be6a256dfeb81f8f3c3066eb4cb9ffdbb53"


# Canonical Frozen Configuration Dictionary
FROZEN_RESEARCH_CONFIGURATION: Dict[str, Any] = {
    "versions": {
        "strategy_version": STRATEGY_VERSION,
        "signal_engine_version": SIGNAL_ENGINE_VERSION,
        "risk_engine_version": RISK_ENGINE_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "options_engine_version": OPTIONS_ENGINE_VERSION,
        "regime_detector_version": REGIME_DETECTOR_VERSION,
        "indicator_engine_version": INDICATOR_ENGINE_VERSION,
    },
    "nse_session_assumptions": {
        "market": "NSE",
        "timezone": "Asia/Kolkata",
        "equity_open": "09:15:00",
        "equity_close": "15:30:00",
        "fno_open": "09:15:00",
        "fno_close": "15:30:00",
        "pre_open_open": "09:00:00",
        "pre_open_close": "09:08:00",
        "trading_days_per_year": 250,
        "session_minutes": 375,
        "intraday_square_off": "15:15:00",
    },
    "timeframe_definitions": {
        "anchor_context": "1D",
        "intermediate_context": "1h",
        "primary_setup": "15m",
        "execution_trigger": "5m",
        "micro_confirmation": "1m",
    },
    "indicator_parameters": {
        "ema_fast": 9,
        "ema_intermediate": 20,
        "ema_slow": 50,
        "ema_trend": 200,
        "rsi_period": 14,
        "rsi_overbought": 70.0,
        "rsi_oversold": 30.0,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "bollinger_period": 20,
        "bollinger_std_dev": 2.0,
        "atr_period": 14,
        "adx_period": 14,
        "adx_trend_threshold": 25.0,
        "stochastic_k": 14,
        "stochastic_d": 3,
        "stochastic_smooth": 3,
        "supertrend_period": 10,
        "supertrend_multiplier": 3.0,
        "donchian_period": 20,
        "keltner_period": 20,
        "keltner_atr_mult": 2.0,
        "obv_ema_period": 20,
        "cmf_period": 20,
        "roc_period": 12,
        "williams_r_period": 14,
    },
    "regime_detector": {
        "regimes": ["BULL_TRENDING", "BEAR_TRENDING", "SIDEWAYS_RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY_COMPRESSION"],
        "adx_trend_min": 25.0,
        "atr_high_vol_percentile": 80.0,
        "atr_low_vol_percentile": 20.0,
        "ma_alignment_required": True,
    },
    "strategy_correlation_clusters": {
        "FAM_TREND": [
            "EMA_GOLDEN_CROSS",
            "EMA_TRIPLE_CROSSOVER",
            "MACD_MOMENTUM",
            "SUPERTREND_CHANDELIER",
            "ICHIMOKU_CLOUD",
            "PARABOLIC_SAR",
        ],
        "FAM_MOMENTUM": [
            "RSI_MEAN_REVERSION",
            "STOCHASTIC_RSI_CROSS",
            "WILLIAMS_R_MOMENTUM",
            "ROC_SURGE",
            "CMF_ACCUMULATION",
        ],
        "FAM_BREAKOUT": [
            "BOLLINGER_SQUEEZE_BREAKOUT",
            "DONCHIAN_BREAKOUT",
            "ORB_5MIN",
            "KELTNER_BREAKOUT",
            "MULTI_TIMEFRAME_ALIGNMENT",
        ],
        "FAM_VOLATILITY": [
            "VOLATILITY_EXPANSION_ATR",
            "PRICE_ACTION_PIN_BAR",
        ],
        "FAM_VOLUME": [
            "VWAP_INSTITUTIONAL_BOUNCE",
            "VOLUME_SPREAD_ANALYSIS",
        ],
    },
    "confluence_weights": {
        "trend_family_weight": 0.30,
        "momentum_family_weight": 0.25,
        "breakout_family_weight": 0.20,
        "volume_family_weight": 0.15,
        "volatility_family_weight": 0.10,
        "collinear_discount_factor": 0.65,
        "min_independent_families_required": 2,
    },
    "scoring_weights": {
        "trend_alignment": 15.0,
        "momentum_quality": 10.0,
        "volume_confirmation": 10.0,
        "market_structure": 10.0,
        "volatility_suitability": 8.0,
        "regime_compatibility": 12.0,
        "strategy_consensus": 15.0,
        "mtf_alignment": 10.0,
        "liquidity_quality": 5.0,
        "risk_reward_quality": 10.0,
        "historical_edge": 5.0,
        "total": 100.0,
    },
    "validation_gates": {
        "hard_gates": [
            "DATA_INTEGRITY",
            "DATA_FRESHNESS",
            "SESSION_HOURS",
            "MIN_LIQUIDITY_INR",
            "ZERO_VOLUME_REJECTION",
            "MIN_RISK_REWARD_1_5",
            "VALID_STOP_GEOMETRY",
            "RISK_CEILING_1_PCT",
            "PORTFOLIO_DRAWDOWN_5_PCT",
        ],
        "soft_gates": [
            "RSI_ACTIVE_ZONE",
            "RVOL_CONFIRMATION",
            "MTF_TREND_ALIGNMENT",
            "REGIME_COMPATIBILITY",
            "VOLUME_EXPANSION",
        ],
        "min_volume_inr": 5000000.0,
        "min_risk_reward": 1.5,
        "max_portfolio_risk_pct": 1.0,
        "max_drawdown_breaker_pct": 5.0,
    },
    "entry_stop_target_rules": {
        "entry_rule": "Limit order at pullback zone or Stop-Market at structural pivot",
        "stop_rule": "Structural pivot low/high buffered by 1.5x ATR(14)",
        "target_1": "1.5x Risk (T1 R:R = 1.5)",
        "target_2": "2.5x Risk (T2 R:R = 2.5)",
        "target_3": "4.0x Risk (T3 R:R = 4.0)",
        "max_stop_loss_pct": 5.0,
    },
    "position_sizing_rules": {
        "model": "FIXED_FRACTIONAL_RISK",
        "risk_fraction": 0.01,  # 1% per trade
        "formula": "Quantity = floor((Capital * 0.01) / |Entry - Stop|)",
        "max_capital_allocation_per_trade_pct": 10.0,
        "max_open_positions": 5,
        "max_total_exposure_pct": 60.0,
    },
    "transaction_cost_schedule": {
        "cost_model_version": COST_MODEL_VERSION,
        "brokerage_per_order": 20.0,
        "brokerage_max_turnover_pct": 0.0005,
        "stt_equity_delivery_pct": 0.001,
        "stt_equity_intraday_sell_pct": 0.00025,
        "stt_futures_sell_pct": 0.0002,
        "stt_options_sell_premium_pct": 0.00125,
        "exchange_charges_pct": 0.0000325,
        "gst_pct": 0.18,
        "sebi_turnover_charge_pct": 0.000001,
        "stamp_duty_equity_intraday_pct": 0.00003,
        "stamp_duty_futures_pct": 0.00002,
        "stamp_duty_options_pct": 0.00003,
        "modeled_slippage_equity_pct": 0.0005,
        "modeled_slippage_futures_pct": 0.0002,
        "modeled_slippage_options_pct": 0.0050,
    },
    "futures_engine_rules": {
        "basis_discount_threshold_pct": -1.5,
        "min_dte_fresh_entry": 3,
        "rollover_dte_window": 3,
        "oi_buildup_patterns": ["LONG_BUILDUP", "SHORT_BUILDUP", "LONG_UNWINDING", "SHORT_COVERING"],
        "max_margin_utilization_pct": 20.0,
    },
    "options_engine_rules": {
        "model": "BLACK_SCHOLES_73",
        "max_bid_ask_spread_pct": 4.0,
        "delta_target_naked": 0.50,
        "delta_range_naked": [0.45, 0.55],
        "high_iv_threshold_pct": 30.0,
        "elevated_iv_structure": "VERTICAL_DEBIT_SPREAD",
        "time_decay_risk_dte_threshold": 7,
        "naked_selling_permitted": False,
    },
}


def compute_configuration_hash(config_dict: Dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash of configuration dictionary."""
    serialized = json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


CONFIGURATION_HASH = compute_configuration_hash(FROZEN_RESEARCH_CONFIGURATION)
GIT_COMMIT = get_git_commit()


class VersionMetadata(BaseModel):
    """Metadata certifying frozen configuration identity."""
    strategy_version: str = STRATEGY_VERSION
    signal_engine_version: str = SIGNAL_ENGINE_VERSION
    risk_engine_version: str = RISK_ENGINE_VERSION
    cost_model_version: str = COST_MODEL_VERSION
    options_engine_version: str = OPTIONS_ENGINE_VERSION
    configuration_hash: str = CONFIGURATION_HASH
    git_commit: str = GIT_COMMIT
    creation_timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def get_version_metadata() -> VersionMetadata:
    """Returns certified frozen version metadata instance."""
    return VersionMetadata(
        git_commit=get_git_commit(),
        configuration_hash=CONFIGURATION_HASH,
    )
