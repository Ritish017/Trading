"""
Database Repository — Signal Intelligence Engine
=================================================
Provides durable, async PostgreSQL & SQLite storage for:
- Signals and their complete metadata
- State machine transition events (audit trail)
- Strategy consensus votes
- Candidate rejections
- Forward market outcomes (MAE, MFE, realized R, net PnL)
- Aggregated performance snapshots & calibration buckets
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, update, delete, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import (
    SignalModel,
    SignalEventModel,
    SignalStrategyVoteModel,
    SignalRejectionModel,
    CandidateObservationModel,
    SignalOutcomeModel,
    SignalPerformanceSnapshotModel,
    SignalCalibrationBucketModel,
)

logger = logging.getLogger(__name__)


class SignalRepository:
    """Async database repository for signal engine domain entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # Signal CRUD
    # -----------------------------------------------------------------------

    async def save_signal(self, signal_dict: Dict[str, Any]) -> str:
        """
        Durable upsert of a SignalDecision dictionary.
        Returns signal_id.
        """
        sig_id = signal_dict.get("signal_id")
        stmt = select(SignalModel).where(SignalModel.signal_id == sig_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        direction = signal_dict.get("direction")
        if hasattr(direction, "value"):
            direction = direction.value

        state = signal_dict.get("state")
        if hasattr(state, "value"):
            state = state.value

        grade = signal_dict.get("quality_grade")
        if hasattr(grade, "value"):
            grade = grade.value

        sig_type = signal_dict.get("signal_type")
        if hasattr(sig_type, "value"):
            sig_type = sig_type.value

        asset_class = signal_dict.get("asset_class")
        if hasattr(asset_class, "value"):
            asset_class = asset_class.value

        stop_loss = signal_dict.get("stop_loss")
        stop_price = None
        stop_method = None
        if isinstance(stop_loss, dict):
            stop_price = stop_loss.get("price")
            stop_method = stop_loss.get("method")
        elif hasattr(stop_loss, "price"):
            stop_price = stop_loss.price
            stop_method = getattr(stop_loss, "method", None)

        targets = signal_dict.get("targets") or []
        t1, t2, t3 = None, None, None
        t_method = None
        if targets and len(targets) > 0:
            first_t = targets[0]
            t1 = first_t.get("price") if isinstance(first_t, dict) else getattr(first_t, "price", None)
            t_method = first_t.get("method") if isinstance(first_t, dict) else getattr(first_t, "method", None)
            if len(targets) > 1:
                sec_t = targets[1]
                t2 = sec_t.get("price") if isinstance(sec_t, dict) else getattr(sec_t, "price", None)
            if len(targets) > 2:
                third_t = targets[2]
                t3 = third_t.get("price") if isinstance(third_t, dict) else getattr(third_t, "price", None)

        pos_size = signal_dict.get("position_size")
        pos_size_json = pos_size if isinstance(pos_size, dict) else (pos_size.dict() if hasattr(pos_size, "dict") else None)

        confluence_res = signal_dict.get("confluence_result")
        conf_score = 0.0
        conf_label = None
        conf_json = None
        if isinstance(confluence_res, dict):
            conf_score = float(confluence_res.get("confluence_score", 0.0))
            conf_label = confluence_res.get("confluence_label")
            conf_json = confluence_res
        elif confluence_res is not None:
            conf_score = getattr(confluence_res, "confluence_score", 0.0)
            conf_label = getattr(confluence_res, "confluence_label", None)
            conf_json = confluence_res.dict() if hasattr(confluence_res, "dict") else None

        mtf_res = signal_dict.get("mtf_alignment")
        mtf_score = 0.0
        mtf_json = None
        if isinstance(mtf_res, dict):
            mtf_score = float(mtf_res.get("alignment_score", 0.0))
            mtf_json = mtf_res
        elif mtf_res is not None:
            mtf_score = getattr(mtf_res, "alignment_score", 0.0)
            mtf_json = mtf_res.dict() if hasattr(mtf_res, "dict") else None

        if existing:
            existing.state = str(state)
            existing.opportunity_score = float(signal_dict.get("opportunity_score", existing.opportunity_score))
            existing.confidence = float(signal_dict.get("confidence", existing.confidence))
            existing.entry = float(signal_dict.get("entry") or existing.entry or 0.0)
            existing.stop_loss = stop_price or existing.stop_loss
            existing.target_1 = t1 or existing.target_1
            existing.target_2 = t2 or existing.target_2
            existing.target_3 = t3 or existing.target_3
            existing.risk_reward = float(signal_dict.get("risk_reward", existing.risk_reward))
            existing.position_size_json = pos_size_json or existing.position_size_json
            existing.futures_decision_json = signal_dict.get("futures_decision") or existing.futures_decision_json
            existing.options_decision_json = signal_dict.get("options_decision") or existing.options_decision_json
            existing.cost_estimate_json = signal_dict.get("transaction_cost_estimate") or signal_dict.get("cost_estimate") or existing.cost_estimate_json
            existing.updated_at = func.now()
            await self.session.commit()
            return existing.signal_id
        else:
            model = SignalModel(
                signal_id=sig_id,
                symbol=signal_dict.get("symbol", ""),
                exchange=signal_dict.get("exchange", "NSE"),
                instrument_id=signal_dict.get("instrument_id", ""),
                asset_class=str(asset_class or "EQUITY"),
                direction=str(direction or "NO_TRADE"),
                signal_type=str(sig_type or "NO_TRADE"),
                timeframe=signal_dict.get("timeframe", "15m"),
                state=str(state or "QUALIFIED"),
                quality_grade=str(grade or "A"),
                opportunity_score=float(signal_dict.get("opportunity_score", 0.0)),
                confidence=float(signal_dict.get("confidence", 0.0)),
                is_heuristic_confidence=bool(signal_dict.get("is_heuristic_confidence", True)),
                calibrated_probability=signal_dict.get("calibrated_probability"),
                entry=float(signal_dict.get("entry")) if signal_dict.get("entry") else None,
                entry_zone_low=float(signal_dict.get("entry_zone_low")) if signal_dict.get("entry_zone_low") else None,
                entry_zone_high=float(signal_dict.get("entry_zone_high")) if signal_dict.get("entry_zone_high") else None,
                stop_loss=stop_price,
                stop_method=stop_method,
                target_1=t1,
                target_2=t2,
                target_3=t3,
                target_method=t_method,
                risk_reward=float(signal_dict.get("risk_reward", 0.0)),
                position_size_json=pos_size_json,
                liquidity_score=float(signal_dict.get("liquidity_score", 0.0)),
                market_regime=str(signal_dict.get("regime", "UNKNOWN")),
                regime_compatible=bool(signal_dict.get("regime_compatible", True)),
                mtf_alignment_score=mtf_score,
                mtf_result_json=mtf_json,
                confluence_score=conf_score,
                confluence_label=conf_label,
                confluence_json=conf_json,
                why_reasons_json=signal_dict.get("why_reasons"),
                invalidation_conditions_json=signal_dict.get("invalidation_conditions"),
                rejection_reasons_json=signal_dict.get("rejection_reasons"),
                provenance=str(signal_dict.get("provenance", "RAW_AUTHENTIC_DATA")),
                expiry=signal_dict.get("expiry"),
                expiry_condition=str(signal_dict.get("expiry_condition", "Valid until end of session")),
                candles_used=int(signal_dict.get("candles_used", 0)),
                candidate_id=signal_dict.get("candidate_id"),
                strategy_version=signal_dict.get("strategy_version"),
                signal_engine_version=signal_dict.get("signal_engine_version"),
                configuration_hash=signal_dict.get("configuration_hash"),
                git_commit=signal_dict.get("git_commit"),
                market_timestamp=float(signal_dict["market_timestamp"]) if signal_dict.get("market_timestamp") else None,
                data_age_ms=float(signal_dict["data_age_ms"]) if signal_dict.get("data_age_ms") else None,
                spread=float(signal_dict["spread"]) if signal_dict.get("spread") else None,
                effective_strategy_count=int(signal_dict.get("effective_strategy_count", 0)),
                volatility_regime=signal_dict.get("volatility_regime"),
                trend_regime=signal_dict.get("trend_regime"),
                breadth_regime=signal_dict.get("breadth_regime"),
                liquidity_regime=signal_dict.get("liquidity_regime"),
                futures_decision_json=signal_dict.get("futures_decision"),
                options_decision_json=signal_dict.get("options_decision"),
                cost_estimate_json=signal_dict.get("transaction_cost_estimate") or signal_dict.get("cost_estimate"),
            )
            self.session.add(model)
            await self.session.commit()
            return sig_id

    async def get_signal_by_id(self, signal_id: str) -> Optional[SignalModel]:
        stmt = select(SignalModel).where(SignalModel.signal_id == signal_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_signals(
        self,
        direction: Optional[str] = None,
        min_grade: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[SignalModel]:
        """Query active qualified signals."""
        conditions = [SignalModel.state.in_(["QUALIFIED", "TRIGGERED", "ACTIVE"])]
        if direction:
            conditions.append(SignalModel.direction == direction)
        if symbol:
            conditions.append(SignalModel.symbol == symbol)
        if min_grade:
            grade_ranks = {"A+": ["A+"], "A": ["A+", "A"], "B": ["A+", "A", "B"], "C": ["A+", "A", "B", "C"]}
            allowed = grade_ranks.get(min_grade, ["A+", "A", "B", "C"])
            conditions.append(SignalModel.quality_grade.in_(allowed))

        stmt = select(SignalModel).where(and_(*conditions)).order_by(desc(SignalModel.opportunity_score)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------------------------------------------------
    # Signal Lifecycle Events
    # -----------------------------------------------------------------------

    async def record_event(
        self,
        signal_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        trigger_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records an immutable state transition event."""
        evt = SignalEventModel(
            signal_id=signal_id,
            from_state=from_state,
            to_state=to_state,
            transition_reason=reason,
            trigger_price=trigger_price,
            event_timestamp=time.time(),
            event_metadata_json=metadata,
        )
        self.session.add(evt)

        # Update signal state in main table
        stmt = update(SignalModel).where(SignalModel.signal_id == signal_id).values(state=to_state)
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_signal_events(self, signal_id: str) -> List[SignalEventModel]:
        stmt = select(SignalEventModel).where(SignalEventModel.signal_id == signal_id).order_by(SignalEventModel.event_timestamp)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------------------------------------------------
    # Strategy Votes
    # -----------------------------------------------------------------------

    async def record_votes(self, signal_id: str, votes: List[Dict[str, Any]]) -> None:
        for v in votes:
            model = SignalStrategyVoteModel(
                signal_id=signal_id,
                strategy_id=v.get("strategy_id", ""),
                strategy_name=v.get("strategy_name", ""),
                category=v.get("category", "UNKNOWN"),
                direction=str(v.get("direction", "NEUTRAL")),
                confidence=float(v.get("confidence", 0.0)),
                strength=float(v.get("strength", 0.0)),
                rules_passing=int(v.get("rules_passing", 0)),
                rules_total=int(v.get("rules_total", 1)),
                is_correlated=bool(v.get("is_correlated", False)),
                correlated_family=v.get("correlated_family"),
            )
            self.session.add(model)
        await self.session.commit()

    # -----------------------------------------------------------------------
    # Rejections
    # -----------------------------------------------------------------------

    async def record_rejection(self, rejection: Dict[str, Any]) -> None:
        model = SignalRejectionModel(
            symbol=rejection.get("symbol", ""),
            gate_failed=rejection.get("gate_failed", ""),
            gate_type=rejection.get("gate_type", "HARD"),
            category=rejection.get("category", "UNKNOWN"),
            reason=rejection.get("reason", ""),
            evidence=rejection.get("evidence"),
            actual_value=float(rejection["actual_value"]) if rejection.get("actual_value") is not None else None,
            threshold_value=float(rejection["threshold_value"]) if rejection.get("threshold_value") is not None else None,
            partial_score=float(rejection.get("partial_score", 0.0)),
            actionable_advice=rejection.get("actionable_advice"),
            candidate_id=rejection.get("candidate_id"),
            strategy_version=rejection.get("strategy_version"),
            configuration_hash=rejection.get("configuration_hash"),
            git_commit=rejection.get("git_commit"),
            market_timestamp=float(rejection["market_timestamp"]) if rejection.get("market_timestamp") else None,
        )
        self.session.add(model)
        await self.session.commit()

    async def get_recent_rejections(self, limit: int = 50) -> List[SignalRejectionModel]:
        stmt = select(SignalRejectionModel).order_by(desc(SignalRejectionModel.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------------------------------------------------
    # Candidate Observations (Signal Observatory)
    # -----------------------------------------------------------------------

    async def record_candidate_observation(self, candidate_dict: Dict[str, Any]) -> None:
        """Durable record of every evaluated market candidate in the Observatory."""
        cand_id = candidate_dict.get("candidate_id") or f"CAND_{candidate_dict.get('symbol')}_{int(time.time()*1000)}"
        model = CandidateObservationModel(
            candidate_id=cand_id,
            signal_id=candidate_dict.get("signal_id"),
            symbol=candidate_dict.get("symbol", ""),
            exchange=candidate_dict.get("exchange", "NSE"),
            asset_class=str(candidate_dict.get("asset_class", "EQUITY")),
            evaluation_status=str(candidate_dict.get("evaluation_status", "QUALIFIED")),
            direction=str(candidate_dict.get("direction", "NO_TRADE")),
            strategy_version=candidate_dict.get("strategy_version"),
            signal_engine_version=candidate_dict.get("signal_engine_version"),
            configuration_hash=candidate_dict.get("configuration_hash"),
            git_commit=candidate_dict.get("git_commit"),
            market_timestamp=float(candidate_dict["market_timestamp"]) if candidate_dict.get("market_timestamp") else None,
            data_provenance=str(candidate_dict.get("data_provenance", "RAW_AUTHENTIC_DATA")),
            is_live=bool(candidate_dict.get("is_live", False)),
            data_age_ms=float(candidate_dict["data_age_ms"]) if candidate_dict.get("data_age_ms") else None,
            last_price=float(candidate_dict["last_price"]) if candidate_dict.get("last_price") is not None else None,
            volume=int(candidate_dict.get("volume", 0)),
            liquidity_score=float(candidate_dict.get("liquidity_score", 0.0)),
            spread=float(candidate_dict["spread"]) if candidate_dict.get("spread") is not None else None,
            market_regime=str(candidate_dict.get("market_regime", "UNKNOWN")),
            regime_confidence=float(candidate_dict.get("regime_confidence", 0.0)),
            opportunity_score=float(candidate_dict.get("opportunity_score", 0.0)),
            heuristic_confidence=float(candidate_dict.get("heuristic_confidence", 0.0)),
            calibrated_probability=float(candidate_dict["calibrated_probability"]) if candidate_dict.get("calibrated_probability") is not None else None,
            quality_grade=str(candidate_dict.get("quality_grade", "NO TRADE")),
            decision_reason=candidate_dict.get("decision_reason"),
            rejection_gate=candidate_dict.get("rejection_gate"),
            rejection_reason=candidate_dict.get("rejection_reason"),
            actionable_advice=candidate_dict.get("actionable_advice"),
            mtf_state_json=candidate_dict.get("mtf_state_json"),
            strategy_votes_json=candidate_dict.get("strategy_votes_json"),
            confluence_json=candidate_dict.get("confluence_json"),
            hard_gates_passed=int(candidate_dict.get("hard_gates_passed", 0)),
            hard_gates_failed=int(candidate_dict.get("hard_gates_failed", 0)),
        )
        self.session.add(model)
        await self.session.commit()

    async def get_candidate_observations(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[CandidateObservationModel]:
        stmt = select(CandidateObservationModel)
        if symbol:
            stmt = stmt.where(CandidateObservationModel.symbol == symbol)
        if status:
            stmt = stmt.where(CandidateObservationModel.evaluation_status == status)
        stmt = stmt.order_by(desc(CandidateObservationModel.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------------------------------------------------
    # Outcomes
    # -----------------------------------------------------------------------

    async def save_outcome(self, outcome: Dict[str, Any]) -> None:
        sig_id = outcome.get("signal_id", "")
        stmt = select(SignalOutcomeModel).where(SignalOutcomeModel.signal_id == sig_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            for k, v in outcome.items():
                if hasattr(existing, k) and k != "id":
                    setattr(existing, k, v)
        else:
            model = SignalOutcomeModel(**{k: v for k, v in outcome.items() if hasattr(SignalOutcomeModel, k)})
            self.session.add(model)
        await self.session.commit()

    async def get_outcomes(self, symbol: Optional[str] = None, limit: int = 100) -> List[SignalOutcomeModel]:
        stmt = select(SignalOutcomeModel)
        if symbol:
            stmt = stmt.where(SignalOutcomeModel.symbol == symbol)
        stmt = stmt.order_by(desc(SignalOutcomeModel.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
