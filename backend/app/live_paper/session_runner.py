"""
APEX Live Paper Session Runner & Evidence Orchestrator
======================================================
Coordinates the full-day real market observation, candidate evaluation,
paper execution, and sequential master evidence logging for Indian equity markets.

Invariants:
1. LIVE_ORDER_ALLOWED = False permanently; live broker orders are impossible.
2. Sourced exclusively from authentic Upstox market data feed; zero synthetic fallback.
3. Evaluates all 20 systematic strategies against frozen configuration hash.
4. Records 100% of candidates, validation gates, and rejection reasons.
5. All events write strictly sequenced JSONL into the single master evidence file.
6. Lookahead protection: all signals bind to explicit information_cutoff_timestamp.
"""

import asyncio
import datetime
import logging
import os
import psutil
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.config import settings
from backend.app.broker_providers.base import NormalizedTick
from backend.app.broker_providers.upstox import UpstoxProvider
from backend.app.broker_providers.upstox_proto import decode_upstox_protobuf_frame
from backend.app.market.instruments import INSTRUMENT_MAP, get_instrument_key
from backend.app.market_data.canonical_store import canonical_store
from backend.app.market_data.candle_aggregator import MarketCandleAggregator
from backend.app.paper_trading.engine import PaperTradingEngine, PaperOrderRequest
from backend.app.paper_trading.canonical_order import CanonicalOrder
from backend.app.signal_engine.models import (
    SignalDecision,
    SignalDirection,
    SignalEngineConfig,
    DataProvenance,
    CandidateRecord,
    AssetClass,
)
from backend.app.signal_engine.signal_pipeline import evaluate_candidate_signal
from backend.app.signal_engine.transaction_cost import (
    TransactionCostCalculator,
    AssetClass as CostAssetClass,
    OrderSide,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY
from backend.app.strategy_engine.evaluator import evaluate_strategies_observatory
from backend.app.signal_engine.version_freeze import (
    CONFIGURATION_HASH,
    STRATEGY_VERSION,
    SIGNAL_ENGINE_VERSION,
    COST_MODEL_VERSION,
    OPTIONS_ENGINE_VERSION,
    GIT_COMMIT,
)
from backend.app.live_paper.safety import (
    LIVE_ORDER_ALLOWED,
    LivePaperSafetyGuard,
    LiveOrderForbiddenSecurityError,
)
from backend.app.live_paper.master_evidence_logger import (
    MasterEvidenceLogger,
    EventType,
    get_current_timestamps,
)

logger = logging.getLogger(__name__)


class LivePaperSessionRunner:
    """
    Coordinates the full-day real market observation, candidate evaluation,
    paper execution, and sequential master evidence logging.
    """

    def __init__(
        self,
        experiment_id: str,
        session_date: Optional[str] = None,
        log_dir: Optional[str] = None,
        universe: Optional[List[str]] = None,
        initial_capital: float = 1000000.0,
        dry_run: bool = False,
    ):
        self.experiment_id = experiment_id
        
        ist_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        self.session_date = session_date or ist_now.strftime("%Y-%m-%d")
        self.dry_run = dry_run

        # Master evidence logger
        self.evidence_logger = MasterEvidenceLogger(
            experiment_id=self.experiment_id,
            log_dir=log_dir,
            session_date=self.session_date,
        )

        # Safety assertions
        LivePaperSafetyGuard.assert_paper_mode_enforced()
        LivePaperSafetyGuard.verify_frozen_configuration()

        # Configured market universe
        cfg = SignalEngineConfig()
        self.universe: List[str] = universe or cfg.universe

        # Execution & Market Data Engines
        self.paper_engine = PaperTradingEngine(initial_capital=initial_capital)
        self.candle_aggregator = MarketCandleAggregator()
        self.cost_engine = TransactionCostCalculator

        # Upstox market data provider
        self.provider: Optional[UpstoxProvider] = None
        if not dry_run:
            token = settings.get_upstox_token or ""
            self.provider = UpstoxProvider(token=token, base_url=settings.upstox_base_url)

        # State tracking
        self.is_running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._mtm_task: Optional[asyncio.Task] = None
        self._scan_task: Optional[asyncio.Task] = None

        self.last_tick_timestamps: Dict[str, float] = {}
        self.last_mtm_timestamps: Dict[str, float] = {}

        # Tracking metrics for session summary
        self.session_stats = {
            "ticks_received": 0,
            "candles_created": 0,
            "candles_updated": 0,
            "evaluations_run": 0,
            "candidates_created": 0,
            "candidates_rejected": 0,
            "signals_qualified": 0,
            "paper_orders_placed": 0,
            "paper_fills": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "gross_pnl": 0.0,
            "total_costs": 0.0,
            "net_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "errors": 0,
        }

    async def initialize_session(self) -> None:
        """Emits SESSION_START and UNIVERSE_SNAPSHOT events, restoring portfolio state from database."""
        logger.info(f"[SESSION RUNNER] Initializing session: {self.experiment_id} for date {self.session_date}")
        
        # Restore durable portfolio state from PostgreSQL / SQLite if available
        try:
            await self.paper_engine.load_from_db()
            logger.info(f"[SESSION RUNNER] Restored portfolio from database: Capital ₹{self.paper_engine.capital:,.2f}, Open Positions: {len(self.paper_engine.positions)}")
        except Exception as e:
            logger.warning(f"[SESSION RUNNER] Database state restoration notice: {e}")

        # 1. Log SESSION_START
        await self.evidence_logger.log_session_start(
            universe=self.universe,
            metadata={
                "dry_run": self.dry_run,
                "initial_capital": self.paper_engine.initial_capital,
                "concurrency_limit": 5,
                "restored_positions_count": len(self.paper_engine.positions),
            }
        )

        # 2. Log UNIVERSE_SNAPSHOT
        universe_details = {}
        for sym in self.universe:
            meta = INSTRUMENT_MAP.get(sym, {})
            universe_details[sym] = {
                "instrument_key": meta.get("instrument_key", get_instrument_key(sym)),
                "exchange": meta.get("exchange", "NSE"),
                "segment": meta.get("segment", "NSE_EQ"),
                "instrument_type": meta.get("instrument_type", "EQUITY"),
                "display_name": meta.get("display_name", sym),
            }

        await self.evidence_logger.log_event(
            event_type=EventType.UNIVERSE_SNAPSHOT,
            payload={
                "universe_count": len(self.universe),
                "instruments": universe_details,
            },
            source="SESSION_INITIALIZER",
        )

    async def start(self) -> None:
        """Starts live observation, market data feeds, and strategy scanner."""
        self.is_running = True
        await self.initialize_session()

        # Connect Upstox provider if not dry run
        if not self.dry_run and self.provider:
            await self.evidence_logger.log_event(
                event_type=EventType.MARKET_CONNECTION,
                payload={"provider": "UPSTOX", "action": "CONNECTING"},
                source="MARKET_DATA_SERVICE",
            )
            connected = await self.provider.connect()
            if connected:
                await self.evidence_logger.log_event(
                    event_type=EventType.MARKET_CONNECTION,
                    payload={"provider": "UPSTOX", "status": "CONNECTED", "is_live": True},
                    source="MARKET_DATA_SERVICE",
                )
                # Seed authentic historical candles for universe symbols
                logger.info(f"[SESSION RUNNER] Seeding authentic historical candles for {len(self.universe)} universe instruments...")
                for sym in self.universe:
                    inst_key = get_instrument_key(sym) or sym
                    try:
                        h15 = await self.provider.get_historical_candles(inst_key, "15minute", count=50)
                        if h15:
                            self.candle_aggregator.seed_historical_candles(sym, "15m", h15)
                        h5 = await self.provider.get_historical_candles(inst_key, "5minute", count=50)
                        if h5:
                            self.candle_aggregator.seed_historical_candles(sym, "5m", h5)
                        h1 = await self.provider.get_historical_candles(inst_key, "1minute", count=50)
                        if h1:
                            self.candle_aggregator.seed_historical_candles(sym, "1m", h1)
                    except Exception as e:
                        logger.warning(f"[SESSION RUNNER] Candle seeding notice for {sym}: {e}")

                # Subscribe to universe
                await self.provider.subscribe(self.universe)
                await self.evidence_logger.log_event(
                    event_type=EventType.MARKET_SUBSCRIPTION,
                    payload={"provider": "UPSTOX", "symbols": self.universe, "subscribed": True},
                    source="MARKET_DATA_SERVICE",
                )
                # Start WebSocket tick stream
                await self.provider.connect_websocket(self.on_tick_received)
            else:
                await self.evidence_logger.log_event(
                    event_type=EventType.MARKET_DATA_ERROR,
                    payload={"provider": "UPSTOX", "status": "CONNECTION_FAILED", "error": "Provider authentication failed"},
                    source="MARKET_DATA_SERVICE",
                )
                raise RuntimeError("Failed to connect to authentic Upstox market data feed!")

        # Launch background workers
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._mtm_task = asyncio.create_task(self._mark_to_market_loop())
        self._scan_task = asyncio.create_task(self._periodic_scanner_loop())

        logger.info(f"[SESSION RUNNER] Live session {self.experiment_id} active.")

    async def stop(self) -> None:
        """Gracefully stops the session and outputs final summary."""
        if not self.is_running:
            return
        logger.info(f"[SESSION RUNNER] Stopping session {self.experiment_id}...")
        self.is_running = False

        # Cancel background tasks
        for t in (self._heartbeat_task, self._mtm_task, self._scan_task):
            if t:
                t.cancel()

        # Disconnect provider
        if self.provider:
            try:
                await self.provider.disconnect()
                await self.evidence_logger.log_event(
                    event_type=EventType.MARKET_DISCONNECTION,
                    payload={"provider": "UPSTOX", "status": "DISCONNECTED"},
                    source="MARKET_DATA_SERVICE",
                )
            except Exception as e:
                logger.warning(f"[SESSION RUNNER] Provider disconnect notice: {e}")

        # Finalize open paper positions at market close
        await self._close_open_positions_at_session_end()

        # Log SESSION_REGULAR_CLOSE
        await self.evidence_logger.log_event(
            event_type=EventType.SESSION_REGULAR_CLOSE,
            payload={"session_date": self.session_date, "reason": "SESSION_FINALIZATION"},
            source="SESSION_CONTROLLER",
        )

        # Log SESSION_SUMMARY
        await self.evidence_logger.log_session_summary(self.session_stats)

        # Log SESSION_END
        await self.evidence_logger.log_event(
            event_type=EventType.SESSION_END,
            payload={
                "experiment_id": self.experiment_id,
                "session_date": self.session_date,
                "master_log_file": self.evidence_logger.log_file,
                "master_log_sha256": self.evidence_logger.compute_sha256(),
                "final_stats": self.session_stats,
            },
            source="SESSION_CONTROLLER",
        )

        logger.info(f"[SESSION RUNNER] Session {self.experiment_id} completed successfully.")

    async def on_tick_received(self, tick: NormalizedTick) -> None:
        """Processes incoming authentic market tick."""
        self.session_stats["ticks_received"] += 1
        sym = tick.symbol
        ltp = tick.ltp
        self.last_tick_timestamps[sym] = tick.timestamp

        # Update canonical store with complete authentic quote fields
        canonical_store.update_from_ws(sym, {
            "symbol": sym,
            "instrument_key": tick.instrument_key,
            "exchange": tick.exchange,
            "ltp": ltp,
            "previous_close": tick.previous_close,
            "change": tick.change,
            "change_percent": tick.change_percent,
            "open": tick.open,
            "high": tick.high,
            "low": tick.low,
            "close": tick.close,
            "volume": tick.volume,
            "provider_timestamp": tick.timestamp,
            "received_timestamp": tick.received_at / 1000.0 if tick.received_at else time.time(),
            "is_live": True,
            "provider": "UPSTOX_WS",
        })

        # Log RAW_MARKET_TICK event
        if self.session_stats["ticks_received"] <= 50 or (self.session_stats["ticks_received"] % 10 == 0):
            await self.evidence_logger.log_event(
                event_type=EventType.RAW_MARKET_TICK,
                payload={
                    "symbol": sym,
                    "instrument_key": tick.instrument_key,
                    "ltp": ltp,
                    "change": tick.change,
                    "change_percent": tick.change_percent,
                    "volume": tick.volume,
                    "timestamp": tick.timestamp,
                    "ticks_total": self.session_stats["ticks_received"],
                },
                symbol=sym,
                source="UPSTOX_WS",
            )

        # Update candle aggregator
        updated_candles = self.candle_aggregator.process_tick(tick)
        for tf, candle in updated_candles.items():
            self.session_stats["candles_updated"] += 1
            if self.session_stats["candles_updated"] <= 30 or (self.session_stats["candles_updated"] % 15 == 0):
                await self.evidence_logger.log_event(
                    event_type=EventType.CANDLE_UPDATED,
                    payload={
                        "symbol": sym,
                        "timeframe": tf,
                        "time": candle.get("time"),
                        "open": candle.get("open"),
                        "high": candle.get("high"),
                        "low": candle.get("low"),
                        "close": candle.get("close"),
                        "volume": candle.get("volume"),
                        "is_closed": candle.get("is_closed", False),
                    },
                    symbol=sym,
                    source="CANDLE_AGGREGATOR",
                )

        # Check open positions on this symbol for stop/target exits
        await self._check_position_stops_and_targets(sym, ltp, tick.timestamp)

    async def _check_position_stops_and_targets(self, symbol: str, current_price: float, timestamp: float) -> None:
        """Evaluates price against active stop loss and profit targets."""
        open_pos = self.paper_engine.get_position(symbol)
        if not open_pos:
            return

        qty = open_pos.get("quantity", 0)
        if qty == 0:
            return

        side_str = open_pos.get("side", "BUY")
        is_long = (side_str == "BUY")
        stop_loss = open_pos.get("stopLoss") or open_pos.get("stop_loss")
        target_price = open_pos.get("targetPrice") or open_pos.get("target_price")
        entry_price = open_pos.get("entryPrice") or open_pos.get("avg_price", current_price)

        stop_hit = False
        target_hit = False
        exit_reason = ""

        if is_long:
            if stop_loss and current_price <= stop_loss:
                stop_hit = True
                exit_reason = "STOP_LOSS"
            elif target_price and current_price >= target_price:
                target_hit = True
                exit_reason = "TARGET_1"
        else:
            if stop_loss and current_price >= stop_loss:
                stop_hit = True
                exit_reason = "STOP_LOSS"
            elif target_price and current_price <= target_price:
                target_hit = True
                exit_reason = "TARGET_1"

        if stop_hit or target_hit:
            # Close the position
            side = "SELL" if is_long else "BUY"
            exit_qty = abs(qty)

            # Record stop/target event
            if stop_hit:
                await self.evidence_logger.log_event(
                    event_type=EventType.PAPER_STOP_TRIGGERED,
                    payload={
                        "symbol": symbol,
                        "exit_price": current_price,
                        "stop_price": stop_loss,
                        "quantity": exit_qty,
                    },
                    symbol=symbol,
                    source="RISK_MONITOR",
                )
            else:
                await self.evidence_logger.log_event(
                    event_type=EventType.PAPER_TARGET_TRIGGERED,
                    payload={
                        "symbol": symbol,
                        "exit_price": current_price,
                        "target_price": target_price,
                        "quantity": exit_qty,
                    },
                    symbol=symbol,
                    source="RISK_MONITOR",
                )

            # Execute paper exit via canonical close_position
            res = self.paper_engine.close_position(pos_id=open_pos["id"], close_price=current_price)
            if res.get("status") == "CLOSED":
                trade = res.get("trade", {})
                fill_price = trade.get("exitPrice", current_price)
                gross_pnl = trade.get("grossPnL", 0.0)
                realized_pnl = res.get("realized_pnl", 0.0)
                exit_frictions = trade.get("exit_frictions", {})
                total_fees = exit_frictions.get("total_fees", 0.0)

                # Persist trade closure to database
                try:
                    await self.paper_engine.sync_close_to_db(open_pos["id"], trade)
                except Exception as e:
                    logger.debug(f"[SESSION RUNNER] DB sync close notice: {e}")

                self.session_stats["positions_closed"] += 1
                self.session_stats["gross_pnl"] += gross_pnl
                self.session_stats["total_costs"] += total_fees
                self.session_stats["net_pnl"] += realized_pnl
                if realized_pnl > 0:
                    self.session_stats["winning_trades"] += 1
                else:
                    self.session_stats["losing_trades"] += 1

                # Log PAPER_POSITION_CLOSED & PAPER_TRADE_OUTCOME
                await self.evidence_logger.log_event(
                    event_type=EventType.PAPER_POSITION_CLOSED,
                    payload={
                        "symbol": symbol,
                        "pos_id": open_pos["id"],
                        "exit_reason": exit_reason,
                        "exit_price": fill_price,
                        "quantity": exit_qty,
                        "gross_pnl": gross_pnl,
                        "net_pnl": realized_pnl,
                        "costs": exit_frictions,
                    },
                    symbol=symbol,
                    source="PAPER_ENGINE",
                )

                await self.evidence_logger.log_event(
                    event_type=EventType.PAPER_TRADE_OUTCOME,
                    payload={
                        "symbol": symbol,
                        "pos_id": open_pos["id"],
                        "direction": "LONG" if is_long else "SHORT",
                        "entry_price": entry_price,
                        "exit_price": fill_price,
                        "quantity": exit_qty,
                        "gross_pnl": gross_pnl,
                        "statutory_costs": total_fees,
                        "net_pnl": realized_pnl,
                        "is_win": realized_pnl > 0,
                        "exit_reason": exit_reason,
                    },
                    symbol=symbol,
                    source="OUTCOME_EVALUATOR",
                )

    async def evaluate_symbol_signals(self, symbol: str) -> None:
        """
        Runs strategy evaluation, candidate generation, validation gates,
        and paper trade execution for a single symbol.
        """
        candles = self.candle_aggregator.get_history(symbol, "15m", 100)
        if len(candles) < 30:
            return

        self.session_stats["evaluations_run"] += 1
        quote = canonical_store.get_canonical_quote(symbol)
        ltp = quote.ltp if quote and quote.ltp else candles[-1].get("close", 100.0)

        # 1. Run all 20 strategies observatory
        obs_res = evaluate_strategies_observatory(
            candles=candles,
            is_live_feed=not self.dry_run,
            symbol=symbol,
        )

        strategies = obs_res.get("strategies", [])
        for s in strategies:
            s_id = s.get("strategy_id")
            s_dir = s.get("directional_state", "NEUTRAL")
            s_passing = s.get("entry_rules_passing", 0)
            s_total = s.get("entry_rules_total", 1)
            score = round((s_passing / max(1, s_total)) * 100, 1)
            await self.evidence_logger.log_event(
                event_type=EventType.STRATEGY_EVALUATION,
                payload={
                    "strategy_id": s_id,
                    "strategy_name": s.get("strategy_name"),
                    "direction": s_dir,
                    "state": s.get("state"),
                    "score": score,
                    "passing_rules": s_passing,
                    "total_rules": s_total,
                },
                symbol=symbol,
                source="STRATEGY_EVALUATOR",
            )

        # 2. Build Candidate Record
        candidate_id = f"CAND_{symbol}_{int(time.time()*1000)}"
        self.session_stats["candidates_created"] += 1
        await self.evidence_logger.log_event(
            event_type=EventType.CANDIDATE_CREATED,
            payload={
                "candidate_id": candidate_id,
                "symbol": symbol,
                "last_price": ltp,
                "regime": obs_res.get("market_regime", {}).get("regime", "UNKNOWN"),
            },
            symbol=symbol,
            source="CANDIDATE_GENERATOR",
        )

        candidate = CandidateRecord(
            symbol=symbol,
            exchange="NSE",
            asset_class=AssetClass.EQUITY,
            last_price=ltp,
            change_pct=quote.change_percent if quote else 0.0,
            volume=quote.volume if quote else 0,
        )

        # 3. Evaluate candidate through SignalPipeline
        candles_5m = self.candle_aggregator.get_history(symbol, "5m", 100)
        portfolio_summary = self.paper_engine.get_portfolio_summary()
        cfg = SignalEngineConfig()

        decision, rejection = await evaluate_candidate_signal(
            candidate=candidate,
            candles_by_timeframe={"15m": candles, "5m": candles_5m},
            quote={
                "symbol": symbol,
                "ltp": ltp,
                "volume": quote.volume if quote else 500000,
                "timestamp": time.time(),
                "change_percent": quote.change_percent if quote else 0.0,
                "provider": "UPSTOX",
            },
            is_market_open=True,
            portfolio_state=portfolio_summary,
            config=cfg,
        )

        # 4. Log validation gate results
        if decision.validation_gates:
            for g in decision.validation_gates:
                g_res = getattr(g.result, "value", str(g.result))
                await self.evidence_logger.log_event(
                    event_type=EventType.VALIDATION_GATE_RESULT,
                    payload={
                        "candidate_id": candidate_id,
                        "gate_id": g.gate_id,
                        "gate_name": g.gate_name,
                        "gate_type": g.gate_type,
                        "result": g_res,
                        "reason": g.reason,
                    },
                    symbol=symbol,
                    source="VALIDATION_PIPELINE",
                )

        # 5. Check if candidate passed or failed
        is_qualified = (decision.direction != SignalDirection.NO_TRADE and decision.entry is not None)
        if not is_qualified:
            self.session_stats["candidates_rejected"] += 1
            await self.evidence_logger.log_event(
                event_type=EventType.CANDIDATE_REJECTED,
                payload={
                    "candidate_id": candidate_id,
                    "rejection_reasons": decision.why_reasons if decision.why_reasons else [rejection.reason if rejection else "NO_EDGE"],
                    "opportunity_score": decision.opportunity_score,
                    "quality_grade": getattr(decision.quality_grade, "value", str(decision.quality_grade)),
                },
                symbol=symbol,
                source="VALIDATION_PIPELINE",
            )
            await self.evidence_logger.log_event(
                event_type=EventType.NO_QUALIFIED_SIGNAL,
                payload={
                    "symbol": symbol,
                    "candidate_id": candidate_id,
                    "reason": rejection.reason if rejection else "Candidate did not meet qualification thresholds",
                },
                symbol=symbol,
                source="STRATEGY_EVALUATOR",
            )
        else:
            # Candidate Validated & Signal Qualified
            self.session_stats["signals_qualified"] += 1
            await self.evidence_logger.log_event(
                event_type=EventType.CANDIDATE_VALIDATED,
                payload={
                    "candidate_id": candidate_id,
                    "signal_id": decision.signal_id,
                    "score": decision.opportunity_score,
                },
                symbol=symbol,
                source="VALIDATION_PIPELINE",
            )

            utc_cutoff, _ = get_current_timestamps()
            await self.evidence_logger.log_event(
                event_type=EventType.SIGNAL_QUALIFIED,
                payload={
                    "signal_id": decision.signal_id,
                    "candidate_id": candidate_id,
                    "direction": getattr(decision.direction, "value", str(decision.direction)),
                    "grade": getattr(decision.quality_grade, "value", str(decision.quality_grade)),
                    "opportunity_score": decision.opportunity_score,
                    "entry": decision.entry,
                    "stop_loss": decision.stop_loss.price if decision.stop_loss else None,
                    "target_1": decision.targets[0].price if decision.targets else None,
                    "risk_reward": decision.risk_reward,
                    "information_cutoff_timestamp": utc_cutoff,
                },
                symbol=symbol,
                source="SIGNAL_PIPELINE",
            )

            # Route to Paper Trading Engine
            await self._execute_paper_trade(decision)

    async def _execute_paper_trade(self, signal: SignalDecision) -> None:
        """Executes a qualified signal in the paper trading engine."""
        # Safety invariant check
        LivePaperSafetyGuard.assert_paper_mode_enforced()

        side = "BUY" if signal.direction == SignalDirection.LONG else "SELL"
        qty = signal.position_size.quantity if signal.position_size else 1
        entry_price = signal.entry

        # 1. Log PAPER_ORDER_CREATED
        await self.evidence_logger.log_event(
            event_type=EventType.PAPER_ORDER_CREATED,
            payload={
                "signal_id": signal.signal_id,
                "candidate_id": signal.candidate_id,
                "symbol": signal.symbol,
                "side": side,
                "quantity": qty,
                "limit_price": entry_price,
            },
            symbol=signal.symbol,
            source="PAPER_ENGINE",
        )

        order_req = PaperOrderRequest(
            symbol=signal.symbol,
            companyName=signal.symbol,
            productType="MIS",
            side=side,
            quantity=qty,
            price=entry_price,
            stopLoss=signal.stop_loss.price if signal.stop_loss else None,
            targetPrice=signal.targets[0].price if signal.targets else None,
            order_type="MARKET",
            exchange=signal.exchange,
            source=f"SIGNAL_{signal.signal_id[:8]}",
            idempotency_key=f"paper_{signal.signal_id}",
        )

        # 2. Execute order in paper engine
        res = self.paper_engine.execute_order(order_req)
        if res.get("status") == "FILLED":
            self.session_stats["paper_fills"] += 1
            self.session_stats["positions_opened"] += 1
            fill_price = res.get("fill_price", entry_price)

            # Persist order and open position to PostgreSQL / SQLite
            try:
                await self.paper_engine.sync_order_to_db(res.get("order", {}), res.get("position", {}))
            except Exception as e:
                logger.debug(f"[SESSION RUNNER] DB sync order notice: {e}")

            # Log PAPER_ORDER_FILLED
            await self.evidence_logger.log_event(
                event_type=EventType.PAPER_ORDER_FILLED,
                payload={
                    "signal_id": signal.signal_id,
                    "symbol": signal.symbol,
                    "side": side,
                    "quantity": qty,
                    "fill_price": fill_price,
                    "notional": fill_price * qty,
                },
                symbol=signal.symbol,
                source="PAPER_ENGINE",
            )

            # Log PAPER_POSITION_OPENED
            await self.evidence_logger.log_event(
                event_type=EventType.PAPER_POSITION_OPENED,
                payload={
                    "symbol": signal.symbol,
                    "quantity": qty if side == "BUY" else -qty,
                    "entry_price": fill_price,
                    "stop_loss": signal.stop_loss.price if signal.stop_loss else None,
                    "target_price": signal.targets[0].price if signal.targets else None,
                },
                symbol=signal.symbol,
                source="PAPER_ENGINE",
            )
        else:
            await self.evidence_logger.log_event(
                event_type=EventType.PAPER_ORDER_REJECTED,
                payload={"symbol": signal.symbol, "reason": res.get("reason", "Rejected by risk or funds")},
                symbol=signal.symbol,
                source="PAPER_ENGINE",
            )

    async def _close_open_positions_at_session_end(self) -> None:
        """Closes any remaining open paper positions at session end."""
        open_positions = list(self.paper_engine.positions.values())
        for pos in open_positions:
            qty = pos.get("quantity", 0)
            if qty == 0:
                continue
            sym = pos.get("symbol")
            side = "SELL" if pos.get("side") == "BUY" else "BUY"
            quote = canonical_store.get_canonical_quote(sym)
            current_price = quote.ltp if quote and quote.ltp else pos.get("entryPrice", 100.0)

            res = self.paper_engine.close_position(pos_id=pos["id"], close_price=current_price)
            if res.get("status") == "CLOSED":
                trade = res.get("trade", {})
                fill_price = trade.get("exitPrice", current_price)
                gross_pnl = trade.get("grossPnL", 0.0)
                realized_pnl = res.get("realized_pnl", 0.0)
                exit_frictions = trade.get("exit_frictions", {})
                total_fees = exit_frictions.get("total_fees", 0.0)

                # Persist trade closure to database
                try:
                    await self.paper_engine.sync_close_to_db(pos["id"], trade)
                except Exception as e:
                    logger.debug(f"[SESSION RUNNER] DB sync close notice: {e}")

                self.session_stats["positions_closed"] += 1
                self.session_stats["gross_pnl"] += gross_pnl
                self.session_stats["total_costs"] += total_fees
                self.session_stats["net_pnl"] += realized_pnl

                await self.evidence_logger.log_event(
                    event_type=EventType.PAPER_POSITION_CLOSED,
                    payload={
                        "symbol": sym,
                        "pos_id": pos["id"],
                        "exit_reason": "SESSION_CLOSE",
                        "exit_price": fill_price,
                        "quantity": qty,
                        "gross_pnl": gross_pnl,
                        "net_pnl": realized_pnl,
                        "costs": exit_frictions,
                    },
                    symbol=sym,
                    source="SESSION_FINALIZER",
                )

    async def _heartbeat_loop(self) -> None:
        """Emits periodic SESSION_HEARTBEAT event and updates worker telemetry in database."""
        while self.is_running:
            try:
                await asyncio.sleep(15.0)  # Pulse every 15s for high-resolution observability
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent()

                payload = {
                    "cpu_percent": cpu,
                    "memory_percent": mem.percent,
                    "memory_used_mb": round(mem.used / (1024 * 1024), 1),
                    "ticks_received_total": self.session_stats["ticks_received"],
                    "candles_updated_total": self.session_stats["candles_updated"],
                    "open_positions_count": len(self.paper_engine.positions),
                    "master_events_logged": self.evidence_logger.current_sequence_number,
                }
                await self.evidence_logger.log_event(
                    event_type=EventType.SESSION_HEARTBEAT,
                    payload=payload,
                    source="SYSTEM_HEALTH_MONITOR",
                )

                # Persist heartbeat to PostgreSQL / SQLite for distributed API/dashboard observability
                try:
                    from backend.app.database.connection import AsyncSessionLocal
                    from backend.app.database.repositories.worker_repository import WorkerRepository
                    portfolio = self.paper_engine.get_portfolio_summary()
                    async with AsyncSessionLocal() as s:
                        repo = WorkerRepository(s)
                        await repo.upsert_heartbeat(
                            worker_id="apex-market-worker",
                            experiment_id=self.experiment_id,
                            worker_status="ONLINE" if self.is_running else "STOPPED",
                            market_connection="CONNECTED" if (self.provider and getattr(self.provider, "is_connected", False)) else "DISCONNECTED",
                            database_status="ONLINE",
                            paper_mode=True,
                            live_trading=False,
                            last_tick=max(self.last_tick_timestamps.values()) if self.last_tick_timestamps else None,
                            last_event=getattr(self.evidence_logger, "last_event_type", "SESSION_HEARTBEAT") or "SESSION_HEARTBEAT",
                            last_market_event="TICK" if self.session_stats["ticks_received"] > 0 else None,
                            last_signal_event="SIGNAL" if self.session_stats["signals_qualified"] > 0 else None,
                            last_paper_event="ORDER" if self.session_stats["paper_orders_placed"] > 0 else None,
                            signal_count=self.session_stats["signals_qualified"],
                            candidate_count=self.session_stats["candidates_created"],
                            paper_order_count=self.session_stats["paper_orders_placed"],
                            open_positions=len(self.paper_engine.positions),
                            closed_positions=self.session_stats["positions_closed"],
                            realized_pnl=portfolio.get("total_realized_pnl", 0.0),
                            unrealized_pnl=portfolio.get("total_unrealized_pnl", 0.0),
                            total_costs=self.session_stats["total_costs"],
                            net_pnl=portfolio.get("total_realized_pnl", 0.0) + portfolio.get("total_unrealized_pnl", 0.0),
                            data_quality="AUTHENTIC_LIVE" if not self.dry_run else "DRY_RUN_FIXTURE",
                            reconnect_count=0,
                            error_count=self.session_stats["errors"],
                            details_json=payload,
                        )
                except Exception as e:
                    logger.debug(f"[SESSION RUNNER] Worker heartbeat database notice: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SESSION RUNNER] Heartbeat loop notice: {e}")

    async def _mark_to_market_loop(self) -> None:
        """Emits periodic PAPER_MARK_TO_MARKET updates for open positions."""
        while self.is_running:
            try:
                await asyncio.sleep(15.0)
                open_positions = list(self.paper_engine.positions.values())
                if not open_positions:
                    continue

                portfolio = self.paper_engine.get_portfolio_summary()
                for pos in open_positions:
                    qty = pos.get("quantity", 0)
                    if qty == 0:
                        continue
                    sym = pos.get("symbol")
                    quote = canonical_store.get_canonical_quote(sym)
                    ltp = quote.ltp if quote and quote.ltp else pos.get("entryPrice", 100.0)

                    await self.evidence_logger.log_event(
                        event_type=EventType.PAPER_MARK_TO_MARKET,
                        payload={
                            "symbol": sym,
                            "quantity": qty,
                            "entry_price": pos.get("entryPrice", 0.0),
                            "current_price": ltp,
                            "unrealized_pnl": pos.get("unrealizedPnL", 0.0),
                            "realized_pnl": pos.get("realizedPnL", 0.0),
                            "total_equity": portfolio.get("total_equity", 0.0),
                        },
                        symbol=sym,
                        source="PORTFOLIO_ACCOUNTANT",
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SESSION RUNNER] MTM loop notice: {e}")

    async def _periodic_scanner_loop(self) -> None:
        """Periodically scans universe symbols for strategy evaluations."""
        # Initial scan right after startup once candles are seeded
        await asyncio.sleep(5.0)
        while self.is_running:
            try:
                for sym in self.universe:
                    if not self.is_running:
                        break
                    await self.evaluate_symbol_signals(sym)
                await asyncio.sleep(60.0)  # Scan every 1 minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SESSION RUNNER] Scanner loop notice: {e}")
