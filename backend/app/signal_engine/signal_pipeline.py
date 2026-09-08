"""
Signal Intelligence Engine — Signal Pipeline
=============================================
The single-candidate orchestrator. Takes one instrument and runs it through
the complete signal evaluation pipeline.

Pipeline sequence:
1. Market Data & Feature Vector
2. Market Structure (S/R levels)
3. Market Regime
4. Strategy Voting (all eligible strategies)
5. Confluence Engine (correlation-aware)
6. Determine Direction
7. Stop Loss Engine
8. Target Engine
9. Position Sizing
10. Hard Gate Validation
11. Soft Evidence Gates
12. Opportunity Scoring
13. Signal Quality Grading
14. Signal Generation or Rejection

Invariants:
- Returns SignalDecision for every input (including NO_TRADE)
- NO_TRADE always contains explicit rejection reasons
- Every QUALIFIED signal has complete audit trail
- Deterministic: same input → same output
"""
import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.signal_engine.models import (
    AssetClass,
    CandidateRecord,
    DataProvenance,
    DataSourceRecord,
    RejectionRecord,
    SignalDecision,
    SignalDirection,
    SignalEngineConfig,
    SignalQualityGrade,
    SignalState,
    SignalType,
    StrategyConsensus,
    StrategyVote,
    StrategyVoteDirection,
    ValidationGateResult,
)
from backend.app.signal_engine.confluence_engine import confluence_engine
from backend.app.signal_engine.stop_target_engine import stop_loss_engine, target_engine
from backend.app.signal_engine.position_sizing_engine import position_sizing_engine
from backend.app.signal_engine.scoring_engine import scoring_engine
from backend.app.signal_engine.multi_timeframe_engine import multi_timeframe_engine
from backend.app.signal_engine.validation_gates import validation_pipeline, _safe_float
from backend.app.signal_engine.transaction_cost import TransactionCostCalculator, AssetType
from backend.app.signal_engine.futures_engine import FuturesEngine
from backend.app.signal_engine.options_engine import OptionsEngine

from backend.app.quant_engine.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_vwap,
    calculate_relative_volume,
    detect_support_resistance,
    calculate_macd,
    calculate_adx,
)
from backend.app.quant_engine.regime import classify_market_regime
from backend.app.strategy_engine.evaluator import evaluate_strategies_observatory
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.signal_engine.version_freeze import (
    STRATEGY_VERSION,
    SIGNAL_ENGINE_VERSION,
    CONFIGURATION_HASH,
    GIT_COMMIT,
)

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _make_feature_vector(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a comprehensive feature vector from candles."""
    fv: Dict[str, Any] = {}
    if not candles or len(candles) < 5:
        return fv

    try:
        df = pd.DataFrame(candles)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        if df.empty:
            return fv

        close = df["close"]
        fv["close"] = float(close.iloc[-1])
        fv["open"] = float(df["open"].iloc[-1]) if "open" in df.columns else None
        fv["high"] = float(df["high"].iloc[-1]) if "high" in df.columns else None
        fv["low"] = float(df["low"].iloc[-1]) if "low" in df.columns else None

        # EMA
        if len(close) >= 20:
            fv["ema20"] = float(calculate_ema(close, 20).iloc[-1])
        if len(close) >= 50:
            fv["ema50"] = float(calculate_ema(close, 50).iloc[-1])

        # RSI
        if len(close) >= 15:
            rsi = calculate_rsi(close, 14)
            fv["rsi14"] = float(rsi.iloc[-1]) if not rsi.empty else None

        # ATR
        if all(c in df.columns for c in ["high", "low", "close"]) and len(df) >= 15:
            atr = calculate_atr(df, 14)
            fv["atr14"] = float(atr.iloc[-1]) if not atr.empty else None
            if fv.get("atr14") and fv.get("close") and fv["close"] > 0:
                fv["atr_pct"] = fv["atr14"] / fv["close"] * 100

        # VWAP
        if all(c in df.columns for c in ["high", "low", "close", "volume"]):
            try:
                vwap = calculate_vwap(df)
                fv["vwap"] = float(vwap.iloc[-1]) if not vwap.empty else None
            except Exception:
                fv["vwap"] = None

        # Relative volume
        if "volume" in df.columns and len(df) >= 20:
            try:
                rvol = calculate_relative_volume(df["volume"], 20)
                fv["rvol20"] = float(rvol.iloc[-1]) if not rvol.empty else None
            except Exception:
                fv["rvol20"] = None

        # ADX
        if all(c in df.columns for c in ["high", "low", "close"]) and len(df) >= 28:
            try:
                adx_s, plus_di, minus_di = calculate_adx(df, 14)
                fv["adx14"] = float(adx_s.iloc[-1]) if not adx_s.empty else None
                fv["plus_di"] = float(plus_di.iloc[-1]) if not plus_di.empty else None
                fv["minus_di"] = float(minus_di.iloc[-1]) if not minus_di.empty else None
            except Exception:
                pass

        # MACD
        if len(close) >= 35:
            try:
                macd, signal, hist = calculate_macd(close)
                fv["macd"] = float(macd.iloc[-1]) if not macd.empty else None
                fv["macd_signal"] = float(signal.iloc[-1]) if not signal.empty else None
                fv["macd_hist"] = float(hist.iloc[-1]) if not hist.empty else None
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Feature vector computation error: {e}")

    return fv


def _extract_strategy_votes(
    observatory_result: Dict[str, Any],
    strategy_filter: Optional[List[str]] = None,
) -> List[StrategyVote]:
    """Extract StrategyVote objects from the observatory result."""
    votes: List[StrategyVote] = []
    strategies = observatory_result.get("strategies", [])

    for s in strategies:
        sid = s.get("strategy_id", "")
        if strategy_filter and sid not in strategy_filter:
            continue

        state = s.get("state", "INACTIVE")
        category = s.get("category", "UNKNOWN")
        passing = s.get("entry_rules_passing", 0)
        total = s.get("entry_rules_total", 1)

        dir_state = s.get("directional_state", "NEUTRAL")
        short_passing = s.get("short_rules_passing", 0)
        short_total = s.get("short_rules_total", 0)

        # Map strategy state and directional state to vote direction
        if state == "ACTIVE":
            if dir_state == "LONG":
                direction = StrategyVoteDirection.LONG
                confidence = min(95, int(50 + (passing / max(1, total)) * 45))
            elif dir_state == "SHORT":
                direction = StrategyVoteDirection.SHORT
                effective_p = short_passing if short_total > 0 else passing
                effective_t = short_total if short_total > 0 else total
                confidence = min(95, int(50 + (effective_p / max(1, effective_t)) * 45))
            else:
                direction = StrategyVoteDirection.NEUTRAL
                confidence = 30
        elif state == "PARTIAL":
            direction = StrategyVoteDirection.NEUTRAL
            confidence = int(30 + (passing / max(1, total)) * 25)
        elif state == "INACTIVE":
            direction = StrategyVoteDirection.NEUTRAL
            confidence = int((passing / max(1, total)) * 30)
        elif state in ("UNAVAILABLE", "CONFLICTED"):
            direction = StrategyVoteDirection.UNAVAILABLE
            confidence = 0
        else:
            direction = StrategyVoteDirection.NEUTRAL
            confidence = 20

        # Compute reason codes from rule evaluations
        reason_codes = []
        for r in s.get("rule_evaluations", []):
            if r.get("outcome") == "PASS":
                reason_codes.append(r.get("rule_id", ""))

        vote = StrategyVote(
            strategy_id=sid,
            strategy_name=s.get("strategy_name", sid),
            category=category,
            direction=direction,
            confidence=float(confidence),
            strength=float(min(95, int(passing / max(1, total) * 100))),
            reason_codes=[r for r in reason_codes if r],
            rules_passing=passing,
            rules_total=total,
        )
        votes.append(vote)

    return votes


def _determine_direction_from_confluence(
    confluence_result: Any,
) -> str:
    """Determine signal direction from confluence result."""
    label = confluence_result.confluence_label
    if "LONG" in label:
        return "LONG"
    elif "SHORT" in label:
        return "SHORT"
    return "NO_TRADE"


def _build_strategy_consensus(
    votes: List[StrategyVote],
    direction: str,
) -> StrategyConsensus:
    """Build the StrategyConsensus object from votes."""
    consensus = StrategyConsensus()
    for v in votes:
        if v.direction == StrategyVoteDirection.LONG:
            consensus.long_votes += 1
        elif v.direction == StrategyVoteDirection.SHORT:
            consensus.short_votes += 1
        elif v.direction == StrategyVoteDirection.NEUTRAL:
            consensus.neutral_votes += 1
        else:
            consensus.unavailable_votes += 1

    consensus.total_eligible = len(votes)
    consensus.dominant_direction = (
        StrategyVoteDirection.LONG if consensus.long_votes > consensus.short_votes
        else (StrategyVoteDirection.SHORT if consensus.short_votes > consensus.long_votes
              else StrategyVoteDirection.NEUTRAL)
    )

    aligned = consensus.long_votes if direction == "LONG" else consensus.short_votes
    consensus.consensus_confidence = round(
        aligned / max(1, len(votes)) * 100, 1
    )

    if aligned >= len(votes) * 0.7:
        consensus.consensus_label = "STRONG"
    elif aligned >= len(votes) * 0.5:
        consensus.consensus_label = "MODERATE"
    elif aligned >= len(votes) * 0.3:
        consensus.consensus_label = "WEAK"
    else:
        consensus.consensus_label = "MIXED"

    return consensus


def _build_invalidation_conditions(
    symbol: str,
    direction: str,
    stop_result: Any,
    entry_price: float,
    regime: str,
) -> List[str]:
    """Build explicit invalidation conditions."""
    conditions = []

    if stop_result:
        stop_price = stop_result.price
        if direction == "LONG":
            conditions.append(
                f"5M close below stop level ₹{stop_price:.2f} "
                f"({stop_result.method}: {stop_result.method_description})"
            )
        else:
            conditions.append(
                f"5M close above stop level ₹{stop_price:.2f} "
                f"({stop_result.method}: {stop_result.method_description})"
            )

    conditions.append("Volume confirmation disappears (RVOL drops below 0.5x)")
    conditions.append(f"Market regime changes from {regime} to opposing condition")

    if direction == "LONG":
        conditions.append("Price breaks below 15M EMA20 on high volume")
    else:
        conditions.append("Price breaks above 15M EMA20 on high volume")

    conditions.append("Signal expiry reached (valid for current session only)")

    return conditions


# ---------------------------------------------------------------------------
# Main Pipeline Function
# ---------------------------------------------------------------------------

async def evaluate_candidate_signal(
    candidate: CandidateRecord,
    candles_by_timeframe: Dict[str, List[Dict[str, Any]]],
    quote: Dict[str, Any],
    is_market_open: bool,
    portfolio_state: Optional[Dict[str, Any]],
    config: SignalEngineConfig,
    futures_data: Optional[Dict[str, Any]] = None,
    option_chain: Optional[Dict[str, Any]] = None,
) -> Tuple[SignalDecision, Optional[RejectionRecord]]:
    """
    Run a single candidate through the complete signal evaluation pipeline.

    Returns:
        (SignalDecision, None) if qualified
        (SignalDecision with NO_TRADE, RejectionRecord) if rejected
    """
    symbol = candidate.symbol
    primary_candles = candles_by_timeframe.get(config.primary_timeframe, [])
    all_candles = primary_candles

    # Use the first available timeframe's candles if primary not available
    if not all_candles:
        for tf in config.mtf_timeframes:
            if candles_by_timeframe.get(tf):
                all_candles = candles_by_timeframe[tf]
                break

    # 1. Feature Vector
    fv = _make_feature_vector(all_candles)
    ltp = _safe_float(quote.get("ltp")) or (fv.get("close"))
    if not ltp:
        return _make_no_trade(symbol, "DATA_UNAVAILABLE", "No price data available"), \
               _make_rejection(symbol, "DATA_VALIDATION", "HARD", "No price data available")

    fv["ltp"] = ltp

    # 2. Market Structure (Support/Resistance)
    support_levels: List[float] = []
    resistance_levels: List[float] = []
    if all_candles and len(all_candles) >= 10:
        try:
            df_struct = pd.DataFrame(all_candles)
            for col in ["open", "high", "low", "close"]:
                if col in df_struct.columns:
                    df_struct[col] = pd.to_numeric(df_struct[col], errors="coerce")
            sr = detect_support_resistance(df_struct, num_levels=5)
            support_levels = sr.get("support", [])
            resistance_levels = sr.get("resistance", [])
        except Exception as e:
            logger.warning(f"S/R detection error for {symbol}: {e}")

    # 3. Market Regime
    regime_result = {"regime": "UNAVAILABLE", "confidence": 0}
    if all_candles and len(all_candles) >= 20:
        try:
            df_regime = pd.DataFrame(all_candles)
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df_regime.columns:
                    df_regime[col] = pd.to_numeric(df_regime[col], errors="coerce")
            regime_result = classify_market_regime(df_regime)
        except Exception as e:
            logger.warning(f"Regime classification error for {symbol}: {e}")

    regime = regime_result.get("regime", "UNAVAILABLE")
    regime_confidence = float(regime_result.get("confidence", 0))

    # 4. Strategy Voting
    observatory = {"strategies": []}
    strategy_votes: List[StrategyVote] = []
    try:
        active_prov = "PROVIDER"
        observatory = evaluate_strategies_observatory(
            candles=all_candles,
            is_live_feed=False,
            strategy_ids=None,
            timeframe=config.primary_timeframe,
            provider=active_prov,
            symbol=symbol,
        )
        strategy_votes = _extract_strategy_votes(
            observatory,
            strategy_filter=None,
        )
    except Exception as e:
        logger.warning(f"Strategy evaluation error for {symbol}: {e}")

    # 5. Confluence Engine
    confluence_result = confluence_engine.evaluate(strategy_votes, fv)

    # 6. Determine Direction
    direction = _determine_direction_from_confluence(confluence_result)

    # If no clear direction from strategies, check regime-based direction
    if direction == "NO_TRADE":
        if "BULL" in regime:
            direction = "LONG"
        elif "BEAR" in regime:
            direction = "SHORT"
        else:
            # No signal — return immediately with explicit rejection
            return _make_no_trade(
                symbol, "NO_DIRECTION",
                f"Insufficient strategy confluence. Label: {confluence_result.confluence_label}",
                strategy_votes=strategy_votes,
                confluence_result=confluence_result,
            ), _make_rejection(
                symbol, "CONFLUENCE_INSUFFICIENT", "SOFT",
                f"No dominant direction from strategies ({confluence_result.confluence_label})",
            )

    # 7. Multi-Timeframe Analysis
    mtf_result = multi_timeframe_engine.analyze(candles_by_timeframe, direction, config)

    # Conflict check: if MTF is CONFLICTING on primary TF, penalize but don't block here
    # (handled by hard gates and scoring)

    # 8. Stop Loss Engine
    stop_result = stop_loss_engine.compute(
        direction=direction,
        entry_price=ltp,
        feature_vector=fv,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        config=config,
    )

    # 9. Target Engine
    targets = []
    risk_reward = None
    if stop_result:
        targets, risk_reward = target_engine.compute(
            direction=direction,
            entry_price=ltp,
            stop_loss=stop_result,
            feature_vector=fv,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            config=config,
        )

    # 10. Position Sizing
    position_sizing = None
    if stop_result:
        position_sizing = position_sizing_engine.compute(
            direction=direction,
            entry_price=ltp,
            stop_price=stop_result.price,
            config=config,
        )

    capital_required = position_sizing.capital_required if position_sizing else None

    # 11. Hard Gate Validation
    gates_passed, hard_gates, failure_reason = validation_pipeline.run_hard_gates(
        symbol=symbol,
        candles=all_candles,
        quote=quote,
        is_market_open=is_market_open,
        stop_result=stop_result,
        entry_price=ltp,
        risk_reward=risk_reward,
        capital_required=capital_required,
        portfolio_state=portfolio_state,
        config=config,
    )

    if not gates_passed:
        # Hard gate failure — NO TRADE
        gate_that_failed = next((g for g in hard_gates if g.result == ValidationGateResult.FAIL), None)
        gate_id = gate_that_failed.gate_id if gate_that_failed else "UNKNOWN"
        return _make_no_trade(
            symbol, gate_id, failure_reason or "Hard gate failed",
            strategy_votes=strategy_votes,
            confluence_result=confluence_result,
            hard_gates=hard_gates,
        ), _make_rejection(
            symbol, gate_id, "HARD", failure_reason or "Hard gate failed",
            hard_gates=hard_gates,
        )

    # 12. Soft Evidence Gates
    soft_gates = validation_pipeline.run_soft_gates(
        direction=direction,
        feature_vector=fv,
        regime=regime,
        strategy_categories=[v.category for v in strategy_votes],
    )

    all_gates = hard_gates + soft_gates

    # 13. Opportunity Scoring
    liquidity_score = 60.0  # Default
    for g in hard_gates:
        if g.gate_id == "LIQUIDITY_VALIDATION" and g.result == ValidationGateResult.PASS:
            if g.evidence:
                liquidity_score = 70.0  # Passed minimum

    scoring_result = scoring_engine.score(
        direction=direction,
        feature_vector=fv,
        regime=regime,
        regime_confidence=regime_confidence,
        strategy_votes=strategy_votes,
        confluence_result=confluence_result,
        mtf_result=mtf_result,
        risk_reward=risk_reward,
        liquidity_score=liquidity_score,
        historical_win_rate=None,  # Computed separately for top candidates
        historical_expectancy=None,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        config=config,
    )

    opportunity_score = scoring_result["opportunity_score"]
    quality_grade = scoring_result["quality_grade"]
    confidence = scoring_result["confidence"]

    # 14. Signal Quality Gate
    if quality_grade == SignalQualityGrade.NO_TRADE:
        return _make_no_trade(
            symbol, "SCORE_TOO_LOW",
            f"Opportunity score {opportunity_score:.1f} below minimum {config.c_score_threshold:.1f}",
            strategy_votes=strategy_votes,
            confluence_result=confluence_result,
        ), _make_rejection(
            symbol, "SCORE_TOO_LOW", "SOFT",
            f"Score {opportunity_score:.1f} < {config.c_score_threshold:.1f}",
        )

    # 15. Build WHY reasons and invalidation conditions
    why_reasons = validation_pipeline.build_why_reasons(all_gates, strategy_votes, mtf_result, direction)
    invalidation = _build_invalidation_conditions(symbol, direction, stop_result, ltp, regime)

    # 16. Build strategy consensus
    strategy_consensus = _build_strategy_consensus(strategy_votes, direction)

    # 17. Determine signal type
    signal_type = SignalType.EQUITY_LONG if direction == "LONG" else SignalType.EQUITY_SHORT

    # 18. Data provenance
    is_live = bool(quote.get("is_live", False))
    provenance = (
        DataProvenance.RAW_AUTHENTIC_DATA if is_live
        else DataProvenance.SIMULATED
    )

    # 19. Compute entry zone (±0.3% of LTP by default)
    entry_zone_range = ltp * 0.003
    entry_zone_low = round(ltp - entry_zone_range, 2)
    entry_zone_high = round(ltp + entry_zone_range, 2)

    # 20. Signal expiry
    expiry_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3 * 900))  # 3 candles @ 15m

    # 21. Transaction Cost Estimation
    cost_estimate = None
    try:
        cost_breakdown = TransactionCostCalculator.calculate(
            asset_type=AssetType.EQUITY_INTRADAY,
            buy_price=ltp,
            sell_price=targets[0].price if targets else ltp * 1.01,
            quantity=position_sizing.quantity if position_sizing else 100,
        )
        cost_estimate = cost_breakdown.to_dict()
    except Exception as e:
        logger.warning(f"Cost calculation warning for {symbol}: {e}")

    # 22. Futures Analysis (if data provided)
    futures_decision = None
    if futures_data:
        try:
            f_res = FuturesEngine.analyze(
                underlying_symbol=symbol,
                underlying_direction=direction,
                underlying_price=ltp,
                futures_price=float(futures_data.get("futures_price", ltp)),
                dte=int(futures_data.get("dte", 15)),
                volume=int(futures_data.get("volume", 50000)),
                oi=int(futures_data.get("oi", 500000)),
                oi_change_pct=float(futures_data.get("oi_change_pct", 0.0)),
                lot_size=int(futures_data.get("lot_size", 250)),
                margin_per_lot=float(futures_data.get("margin_per_lot", 150000.0)),
                stop_loss_pts=abs(ltp - stop_result.price) if stop_result else ltp * 0.015,
                target_pts=abs(targets[0].price - ltp) if targets else ltp * 0.03,
            )
            futures_decision = f_res.to_dict()
            if candidate.asset_class == AssetClass.FUTURES:
                if f_res.action == "BUY_FUTURE":
                    signal_type = SignalType.BUY_FUTURE
                elif f_res.action == "SELL_FUTURE":
                    signal_type = SignalType.SELL_FUTURE
                else:
                    signal_type = SignalType.NO_TRADE
        except Exception as e:
            logger.warning(f"Futures analysis error for {symbol}: {e}")

    # 23. Options Intelligence Analysis (if chain provided)
    options_decision = None
    if option_chain:
        try:
            o_res = OptionsEngine.evaluate(
                underlying_symbol=symbol,
                underlying_direction=direction,
                underlying_price=ltp,
                option_chain=option_chain,
                target_price=targets[0].price if targets else None,
                stop_loss_price=stop_result.price if stop_result else None,
            )
            options_decision = o_res.to_dict()
            if candidate.asset_class == AssetClass.OPTIONS:
                if o_res.action == "BUY_CALL":
                    signal_type = SignalType.BUY_CALL
                elif o_res.action == "BUY_PUT":
                    signal_type = SignalType.BUY_PUT
                elif o_res.action in ("BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"):
                    signal_type = SignalType.OPTION_SPREAD
                elif o_res.action == "SELL_CALL":
                    signal_type = SignalType.SELL_CALL
                elif o_res.action == "SELL_PUT":
                    signal_type = SignalType.SELL_PUT
                else:
                    signal_type = SignalType.NO_TRADE
        except Exception as e:
            logger.warning(f"Options evaluation error for {symbol}: {e}")

    # Build qualified signal
    cand_id = getattr(candidate, "candidate_id", None) or f"CAND_{symbol}_{int(time.time()*1000)}"
    signal = SignalDecision(
        signal_id=f"SIG_{symbol}_{int(time.time()*1000)}",
        candidate_id=cand_id,
        strategy_version=STRATEGY_VERSION,
        signal_engine_version=SIGNAL_ENGINE_VERSION,
        configuration_hash=CONFIGURATION_HASH,
        git_commit=GIT_COMMIT,
        market_timestamp=float(quote.get("timestamp", time.time())) if quote.get("timestamp") else time.time(),
        data_age_ms=float(quote.get("data_age_ms", 0.0)) if quote.get("data_age_ms") else 0.0,
        spread=float(quote.get("spread", 0.0)) if quote.get("spread") else None,
        effective_strategy_count=len(strategy_votes),
        symbol=symbol,
        exchange=candidate.exchange,
        instrument_id=candidate.symbol,
        asset_class=candidate.asset_class,
        direction=SignalDirection(direction),
        signal_type=signal_type,
        timeframe=config.primary_timeframe,
        state=SignalState.QUALIFIED,
        quality_grade=quality_grade,
        opportunity_score=opportunity_score,
        confidence=confidence,
        entry=ltp,
        entry_zone_low=entry_zone_low,
        entry_zone_high=entry_zone_high,
        stop_loss=stop_result,
        targets=targets,
        risk_reward=risk_reward,
        position_size=position_sizing,
        regime=regime,
        regime_confidence=regime_confidence,
        regime_compatible=("BULL" in regime and direction == "LONG") or
                          ("BEAR" in regime and direction == "SHORT"),
        strategy_votes=strategy_votes,
        strategy_consensus=strategy_consensus,
        strategy_ids=[v.strategy_id for v in strategy_votes],
        mtf_alignment=mtf_result,
        confluence_result=confluence_result,
        validation_gates=all_gates,
        hard_gates_passed=sum(1 for g in hard_gates if g.result == ValidationGateResult.PASS),
        hard_gates_total=len(hard_gates),
        soft_gates_passed=sum(1 for g in soft_gates if g.result == ValidationGateResult.PASS),
        why_reasons=why_reasons,
        invalidation_conditions=invalidation,
        liquidity_score=liquidity_score,
        data_quality="VALID",
        provenance=provenance,
        data_sources=[
            DataSourceRecord(
                data_type="MARKET_DATA",
                source="MarketDataService",
                provider=quote.get("provider", "PROVIDER"),
                freshness="LIVE" if is_live else "HISTORICAL",
                provenance=provenance,
            )
        ],
        expiry=expiry_time,
        expiry_condition=f"Valid for {config.signal_expiry_candles} candles on {config.primary_timeframe} timeframe",
        candles_used=len(all_candles),
        futures_decision=futures_decision,
        options_decision=options_decision,
        transaction_cost_estimate=cost_estimate,
    )

    return signal, None


def _make_no_trade(
    symbol: str,
    reason_code: str,
    reason: str,
    strategy_votes: Optional[List[StrategyVote]] = None,
    confluence_result: Optional[Any] = None,
    hard_gates: Optional[List[Any]] = None,
) -> SignalDecision:
    """Create a NO_TRADE signal with explicit rejection reasons."""
    return SignalDecision(
        signal_id=f"SIG_NO_TRADE_{symbol}_{int(time.time()*1000)}",
        candidate_id=f"CAND_{symbol}_{int(time.time()*1000)}",
        strategy_version=STRATEGY_VERSION,
        signal_engine_version=SIGNAL_ENGINE_VERSION,
        configuration_hash=CONFIGURATION_HASH,
        git_commit=GIT_COMMIT,
        market_timestamp=time.time(),
        symbol=symbol,
        direction=SignalDirection.NO_TRADE,
        signal_type=SignalType.NO_TRADE,
        state=SignalState.REJECTED,
        quality_grade=SignalQualityGrade.NO_TRADE,
        opportunity_score=0.0,
        confidence=0.0,
        strategy_votes=strategy_votes or [],
        confluence_result=confluence_result,
        validation_gates=hard_gates or [],
        rejection_reasons=[f"{reason_code}: {reason}"],
        provenance=DataProvenance.UNAVAILABLE,
    )


def _make_rejection(
    symbol: str,
    gate_id: str,
    gate_type: str,
    reason: str,
    hard_gates: Optional[List[Any]] = None,
) -> RejectionRecord:
    """Create a RejectionRecord for the rejected candidate."""
    return RejectionRecord(
        symbol=symbol,
        candidate_id=f"CAND_{symbol}_{int(time.time()*1000)}",
        strategy_version=STRATEGY_VERSION,
        configuration_hash=CONFIGURATION_HASH,
        git_commit=GIT_COMMIT,
        market_timestamp=time.time(),
        gate_failed=gate_id,
        gate_type=gate_type,
        reason=reason,
        validation_gates=hard_gates or [],
    )
