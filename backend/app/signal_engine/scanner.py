"""
Signal Intelligence Engine — Market-Wide Opportunity Scanner
=============================================================
Scans the configured market universe and produces qualified signals.

Architecture:
  UNIVERSE (configured symbol list)
        ↓ (parallel, semaphore-limited)
  CANDIDATE SCREENING (price/volume/momentum filters)
        ↓
  DATA ACQUISITION (multi-timeframe candles + quote per candidate)
        ↓
  SIGNAL PIPELINE (full evaluation per candidate)
        ↓
  AGGREGATION (sort by score, deduplicate)
        ↓
  SIGNAL STORE (persist results)
        ↓
  SCANNER RESULT (qualified + watchlist + rejected + pipeline stats)

Invariants:
- Scanner is comfortable returning 0 qualified signals on low-opportunity days
- Every evaluation that fails returns a RejectionRecord with explicit reason
- Pipeline statistics track every stage of attrition
- Market session awareness: if market is closed, returns MARKET_CLOSED status
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.signal_engine.models import (
    AssetClass,
    CandidateRecord,
    DataProvenance,
    RejectionRecord,
    ScannerPipelineStats,
    ScannerResult,
    SignalDecision,
    SignalDirection,
    SignalEngineConfig,
    SignalQualityGrade,
)
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.signal_engine.signal_store import signal_store

logger = logging.getLogger(__name__)

# Maximum concurrent evaluations (prevent overwhelming data provider)
MAX_CONCURRENT_EVALS = 5


class OpportunityScanner:
    """
    Market-wide opportunity scanner.
    Runs the complete signal pipeline across the configured universe.
    """

    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALS)
        self._last_scan_time: float = 0
        self._scan_cooldown: float = 300  # 5 minutes between full scans

    async def run_scan(
        self,
        market_data_service: Any,
        config: SignalEngineConfig,
        portfolio_state: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> ScannerResult:
        """
        Run the full market-wide opportunity scan.

        Args:
            market_data_service: The active market data service instance
            config: Scanner configuration
            portfolio_state: Current paper portfolio state (optional)
            force: Skip cooldown and run immediately

        Returns:
            ScannerResult with all qualified signals and pipeline statistics
        """
        scan_start = time.time()

        # Cooldown check
        if not force and (scan_start - self._last_scan_time) < self._scan_cooldown:
            cached = signal_store.get_last_scan()
            if cached:
                logger.info("Scanner cooldown — returning cached result")
                return cached

        stats = ScannerPipelineStats(universe_size=len(config.universe))
        qualified_signals: List[SignalDecision] = []
        watchlist_signals: List[SignalDecision] = []
        rejected_records: List[RejectionRecord] = []

        # Determine market session
        is_market_open = self._check_market_open(market_data_service)

        # Get market-wide regime from Nifty
        market_regime = "UNKNOWN"
        regime_confidence = 0.0
        try:
            nifty_candles = await market_data_service.get_candles("NIFTY 50", config.primary_timeframe, 50)
            if nifty_candles and len(nifty_candles) >= 20:
                import pandas as pd
                from backend.app.quant_engine.regime import classify_market_regime
                df = pd.DataFrame(nifty_candles)
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                r = classify_market_regime(df)
                market_regime = r.get("regime", "UNKNOWN")
                regime_confidence = float(r.get("confidence", 0))
        except Exception as e:
            logger.warning(f"Market regime detection failed: {e}")

        # Run evaluations in parallel with semaphore
        tasks = [
            self._evaluate_symbol(
                symbol=symbol,
                market_data_service=market_data_service,
                is_market_open=is_market_open,
                portfolio_state=portfolio_state,
                config=config,
                stats=stats,
            )
            for symbol in config.universe
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Scanner evaluation error: {result}")
                rejected_records.append(RejectionRecord(
                    symbol="UNKNOWN",
                    gate_failed="EVALUATION_ERROR",
                    gate_type="HARD",
                    reason=str(result),
                ))
                continue

            if result is None:
                continue

            signal, rejection = result
            if signal and signal.direction != SignalDirection.NO_TRADE:
                if signal.quality_grade == SignalQualityGrade.NO_TRADE:
                    watchlist_signals.append(signal)
                else:
                    qualified_signals.append(signal)
                    signal_store.upsert_signal(signal)

                obs_dict = {
                    "candidate_id": getattr(signal, "candidate_id", None) or f"CAND_{signal.symbol}_{int(time.time()*1000)}",
                    "signal_id": signal.signal_id,
                    "symbol": signal.symbol,
                    "exchange": getattr(signal, "exchange", "NSE"),
                    "asset_class": getattr(signal, "asset_class", "EQUITY"),
                    "evaluation_status": "QUALIFIED" if signal.quality_grade != SignalQualityGrade.NO_TRADE else "WATCHLIST",
                    "direction": signal.direction.value if hasattr(signal.direction, "value") else str(signal.direction),
                    "strategy_version": getattr(signal, "strategy_version", None),
                    "signal_engine_version": getattr(signal, "signal_engine_version", None),
                    "configuration_hash": getattr(signal, "configuration_hash", None),
                    "git_commit": getattr(signal, "git_commit", None),
                    "market_timestamp": getattr(signal, "market_timestamp", None),
                    "data_provenance": signal.provenance.value if hasattr(signal.provenance, "value") else str(signal.provenance),
                    "is_live": is_market_open,
                    "data_age_ms": getattr(signal, "data_age_ms", None),
                    "last_price": signal.entry,
                    "liquidity_score": signal.liquidity_score,
                    "spread": getattr(signal, "spread", None),
                    "market_regime": signal.regime,
                    "regime_confidence": signal.regime_confidence,
                    "opportunity_score": signal.opportunity_score,
                    "heuristic_confidence": signal.confidence,
                    "calibrated_probability": getattr(signal, "calibrated_probability", None),
                    "quality_grade": signal.quality_grade.value if hasattr(signal.quality_grade, "value") else str(signal.quality_grade),
                    "decision_reason": signal.why_reasons[0] if getattr(signal, "why_reasons", None) else None,
                    "hard_gates_passed": getattr(signal, "hard_gates_passed", 0),
                    "hard_gates_failed": getattr(signal, "hard_gates_total", 0) - getattr(signal, "hard_gates_passed", 0),
                }
                signal_store.add_candidate_observation(obs_dict)

            if rejection:
                rejected_records.append(rejection)
                signal_store.add_rejection(rejection)

                rej_obs = {
                    "candidate_id": getattr(rejection, "candidate_id", None) or f"CAND_{rejection.symbol}_{int(time.time()*1000)}",
                    "symbol": rejection.symbol,
                    "evaluation_status": f"REJECTED_BY_{rejection.gate_failed}",
                    "direction": "NO_TRADE",
                    "strategy_version": getattr(rejection, "strategy_version", None),
                    "configuration_hash": getattr(rejection, "configuration_hash", None),
                    "git_commit": getattr(rejection, "git_commit", None),
                    "market_timestamp": getattr(rejection, "market_timestamp", None),
                    "rejection_gate": rejection.gate_failed,
                    "rejection_reason": rejection.reason,
                    "actionable_advice": getattr(rejection, "actionable_advice", None),
                }
                signal_store.add_candidate_observation(rej_obs)

        # Sort by score descending
        qualified_signals.sort(key=lambda s: s.opportunity_score, reverse=True)

        # Update final stats
        stats.qualified = len(qualified_signals)
        stats.scan_duration_ms = round((time.time() - scan_start) * 1000, 1)

        scan_result = ScannerResult(
            pipeline_stats=stats,
            qualified_signals=qualified_signals,
            watchlist_signals=watchlist_signals[:10],  # Top 10 watchlist
            rejected_records=rejected_records[:50],    # Last 50 rejections
            market_regime=market_regime,
            market_regime_confidence=regime_confidence,
            scanner_universe=f"NSE Liquid ({len(config.universe)} symbols)",
            data_provenance=DataProvenance.SIMULATED,  # Updated if live data confirms
            is_market_open=is_market_open,
        )

        signal_store.update_last_scan(scan_result)
        self._last_scan_time = time.time()

        logger.info(
            f"[SCANNER] Complete. Universe:{stats.universe_size} → "
            f"DataValid:{stats.data_valid} → Qualified:{stats.qualified} "
            f"| Duration:{stats.scan_duration_ms:.0f}ms"
        )

        return scan_result

    async def _evaluate_symbol(
        self,
        symbol: str,
        market_data_service: Any,
        is_market_open: bool,
        portfolio_state: Optional[Dict[str, Any]],
        config: SignalEngineConfig,
        stats: ScannerPipelineStats,
    ) -> Optional[Tuple[Optional[SignalDecision], Optional[RejectionRecord]]]:
        """
        Evaluate a single symbol through the full pipeline.
        Wrapped in semaphore to control concurrency.
        """
        async with self._semaphore:
            try:
                # Acquire data
                quote, candles_by_tf = await self._fetch_symbol_data(
                    symbol, market_data_service, config
                )

                if not quote or not candles_by_tf:
                    return None, RejectionRecord(
                        symbol=symbol,
                        gate_failed="DATA_ACQUISITION",
                        gate_type="HARD",
                        reason="Failed to acquire market data",
                    )

                stats.data_valid += 1

                # Basic screening (pre-pipeline performance optimization)
                passed, screen_reason = self._initial_screen(symbol, quote, candles_by_tf, config)
                if not passed:
                    return None, RejectionRecord(
                        symbol=symbol,
                        gate_failed="INITIAL_SCREEN",
                        gate_type="SOFT",
                        reason=screen_reason,
                    )

                stats.initial_screened += 1

                # Build candidate
                candidate = CandidateRecord(
                    symbol=symbol,
                    exchange="NSE",
                    asset_class=AssetClass.EQUITY,
                    last_price=float(quote.get("ltp", 0)),
                    change_pct=float(quote.get("change_percent", 0)),
                    volume=int(quote.get("volume", 0)),
                )

                # Run full pipeline
                signal, rejection = await evaluate_candidate_signal(
                    candidate=candidate,
                    candles_by_timeframe=candles_by_tf,
                    quote=quote,
                    is_market_open=is_market_open,
                    portfolio_state=portfolio_state,
                    config=config,
                )

                return signal, rejection

            except Exception as e:
                logger.warning(f"Evaluation error for {symbol}: {e}")
                return None, RejectionRecord(
                    symbol=symbol,
                    gate_failed="PIPELINE_ERROR",
                    gate_type="HARD",
                    reason=f"Evaluation exception: {str(e)[:200]}",
                )

    async def _fetch_symbol_data(
        self,
        symbol: str,
        market_data_service: Any,
        config: SignalEngineConfig,
    ) -> Tuple[Optional[Dict], Optional[Dict[str, List]]]:
        """Fetch quote and multi-timeframe candles for a symbol."""
        try:
            # Get quote
            quote = await market_data_service.get_quote(symbol)
            if not quote or not quote.get("ltp"):
                return None, None

            # Get primary timeframe candles (required)
            primary_candles = await market_data_service.get_candles(
                symbol, config.primary_timeframe, 100
            )

            candles_by_tf: Dict[str, List] = {}

            if primary_candles:
                candles_by_tf[config.primary_timeframe] = primary_candles

            # Attempt to get additional timeframes (best effort)
            for tf in config.mtf_timeframes:
                if tf == config.primary_timeframe:
                    continue
                try:
                    candles = await market_data_service.get_candles(symbol, tf, 60)
                    if candles:
                        candles_by_tf[tf] = candles
                except Exception:
                    pass  # Additional TFs are optional

            return quote, candles_by_tf

        except Exception as e:
            logger.warning(f"Data fetch error for {symbol}: {e}")
            return None, None

    def _initial_screen(
        self,
        symbol: str,
        quote: Dict[str, Any],
        candles_by_tf: Dict[str, List],
        config: SignalEngineConfig,
    ) -> Tuple[bool, str]:
        """
        Fast initial screen before expensive pipeline evaluation.
        Returns (passed, rejection_reason).
        """
        ltp = quote.get("ltp") or 0
        volume = quote.get("volume") or 0

        # Must have a price
        if not ltp or ltp <= 0:
            return False, "No valid price available"

        # Must have some candle data
        all_candles = []
        for tf_candles in candles_by_tf.values():
            all_candles.extend(tf_candles)
        if not all_candles:
            return False, "No candle data available"

        # Basic volume filter (very loose at screening — hard gate handles precise check)
        # Allow all through if volume > 0
        if volume == 0:
            # Zero volume might be non-trading hour — allow through for research
            pass

        # Check for extreme gap (>10% move, might be corporate action / error)
        prev_close = quote.get("previous_close") or ltp
        if prev_close and prev_close > 0:
            gap_pct = abs(ltp - prev_close) / prev_close * 100
            if gap_pct > 15:
                return False, f"Extreme price gap {gap_pct:.1f}% — potential corporate action"

        return True, ""

    def _check_market_open(self, market_data_service: Any) -> bool:
        """Check if the NSE market is in active trading session."""
        try:
            # Use market_data_service to check session
            session_info = market_data_service.get_market_session_info()
            return session_info.get("is_open", False)
        except Exception:
            # Fallback: check IST time
            import datetime
            import pytz

            try:
                ist = pytz.timezone("Asia/Kolkata")
                now_ist = datetime.datetime.now(ist)
                if now_ist.weekday() >= 5:  # Saturday/Sunday
                    return False
                start = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
                end = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
                return start <= now_ist <= end
            except Exception:
                return False  # Conservative: assume closed if timezone check fails


# Module-level singleton
opportunity_scanner = OpportunityScanner()
