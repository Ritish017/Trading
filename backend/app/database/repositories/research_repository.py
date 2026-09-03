import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import (
    ResearchHypothesisModel,
    ResearchExperimentModel,
)

logger = logging.getLogger(__name__)

class ResearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_hypothesis(self, hyp_dict: Dict[str, Any]) -> None:
        hyp_id = hyp_dict.get("id") or hyp_dict.get("hypothesis_id")
        stmt = select(ResearchHypothesisModel).where(ResearchHypothesisModel.hypothesis_id == hyp_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.status = hyp_dict.get("status", existing.status)
            if "scorecard" in hyp_dict:
                existing.scorecard_json = hyp_dict["scorecard"]
        else:
            new_hyp = ResearchHypothesisModel(
                hypothesis_id=hyp_id,
                name=hyp_dict.get("name", "Unnamed Hypothesis"),
                technical_strategy_id=hyp_dict.get("technical_strategy_id", ""),
                fundamental_factor_id=hyp_dict.get("fundamental_factor_id", ""),
                regime_filter=hyp_dict.get("regime_filter"),
                universe=hyp_dict.get("universe", "NIFTY50"),
                timeframe=hyp_dict.get("timeframe", "1D"),
                status=hyp_dict.get("status", "HYPOTHESIS_FORMULATED"),
                scorecard_json=hyp_dict.get("scorecard"),
            )
            self.session.add(new_hyp)
        await self.session.commit()

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(ResearchHypothesisModel).where(ResearchHypothesisModel.hypothesis_id == hypothesis_id)
        res = await self.session.execute(stmt)
        hyp = res.scalar_one_or_none()
        if not hyp:
            return None
        return {
            "hypothesis_id": hyp.hypothesis_id,
            "name": hyp.name,
            "technical_strategy_id": hyp.technical_strategy_id,
            "fundamental_factor_id": hyp.fundamental_factor_id,
            "regime_filter": hyp.regime_filter,
            "universe": hyp.universe,
            "timeframe": hyp.timeframe,
            "status": hyp.status,
            "scorecard": hyp.scorecard_json,
            "created_at": hyp.created_at.isoformat() if hyp.created_at else None,
        }

    async def save_experiment(self, exp_dict: Dict[str, Any]) -> None:
        exp_id = exp_dict.get("id") or exp_dict.get("experiment_id")
        stmt = select(ResearchExperimentModel).where(ResearchExperimentModel.experiment_id == exp_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.workflow_state = exp_dict.get("workflow_state", existing.workflow_state)
            existing.notes = exp_dict.get("notes", existing.notes)
        else:
            new_exp = ResearchExperimentModel(
                experiment_id=exp_id,
                strategy_id=exp_dict.get("strategy_id", ""),
                symbol=exp_dict.get("symbol", ""),
                timeframe=exp_dict.get("timeframe", "5m"),
                parameters_json=exp_dict.get("parameters", {}),
                metrics_json=exp_dict.get("metrics", {}),
                workflow_state=exp_dict.get("workflow_state", "RESEARCH_CANDIDATE"),
                notes=exp_dict.get("notes"),
            )
            self.session.add(new_exp)
        await self.session.commit()

    async def list_experiments(self, strategy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        stmt = select(ResearchExperimentModel)
        if strategy_id:
            stmt = stmt.where(ResearchExperimentModel.strategy_id == strategy_id)
        res = await self.session.execute(stmt)
        experiments = res.scalars().all()
        return [
            {
                "experiment_id": e.experiment_id,
                "strategy_id": e.strategy_id,
                "symbol": e.symbol,
                "timeframe": e.timeframe,
                "parameters": e.parameters_json,
                "metrics": e.metrics_json,
                "workflow_state": e.workflow_state,
                "notes": e.notes,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in experiments
        ]
