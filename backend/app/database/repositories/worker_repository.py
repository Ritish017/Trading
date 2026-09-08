"""
APEX Worker Repository
======================
Manages persistence, retrieval, and freshness evaluation of stateful market worker
heartbeats and operational telemetry in PostgreSQL / SQLite.
"""

import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import WorkerHeartbeatModel

logger = logging.getLogger(__name__)


class WorkerRepository:
    """Manages worker state persistence in PostgreSQL / SQLite."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_heartbeat(
        self,
        worker_id: str,
        experiment_id: str,
        worker_status: str,
        market_connection: str,
        database_status: str = "ONLINE",
        paper_mode: bool = True,
        live_trading: bool = False,
        last_tick: Optional[float] = None,
        last_event: Optional[str] = None,
        last_market_event: Optional[str] = None,
        last_signal_event: Optional[str] = None,
        last_paper_event: Optional[str] = None,
        signal_count: int = 0,
        candidate_count: int = 0,
        paper_order_count: int = 0,
        open_positions: int = 0,
        closed_positions: int = 0,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        total_costs: float = 0.0,
        net_pnl: float = 0.0,
        data_quality: str = "AUTHENTIC_LIVE",
        reconnect_count: int = 0,
        error_count: int = 0,
        details_json: Optional[Dict[str, Any]] = None,
    ) -> WorkerHeartbeatModel:
        """Atomically inserts or updates worker telemetry heartbeat."""
        stmt = select(WorkerHeartbeatModel).where(WorkerHeartbeatModel.worker_id == worker_id)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            record.experiment_id = experiment_id
            record.worker_status = worker_status
            record.market_connection = market_connection
            record.database_status = database_status
            record.paper_mode = paper_mode
            record.live_trading = live_trading
            if last_tick is not None:
                record.last_tick = last_tick
            if last_event is not None:
                record.last_event = last_event
            if last_market_event is not None:
                record.last_market_event = last_market_event
            if last_signal_event is not None:
                record.last_signal_event = last_signal_event
            if last_paper_event is not None:
                record.last_paper_event = last_paper_event
            record.signal_count = signal_count
            record.candidate_count = candidate_count
            record.paper_order_count = paper_order_count
            record.open_positions = open_positions
            record.closed_positions = closed_positions
            record.realized_pnl = round(realized_pnl, 2)
            record.unrealized_pnl = round(unrealized_pnl, 2)
            record.total_costs = round(total_costs, 2)
            record.net_pnl = round(net_pnl, 2)
            record.data_quality = data_quality
            record.reconnect_count = reconnect_count
            record.error_count = error_count
            if details_json is not None:
                record.details_json = details_json
        else:
            record = WorkerHeartbeatModel(
                worker_id=worker_id,
                experiment_id=experiment_id,
                worker_status=worker_status,
                market_connection=market_connection,
                database_status=database_status,
                paper_mode=paper_mode,
                live_trading=live_trading,
                last_tick=last_tick,
                last_event=last_event,
                last_market_event=last_market_event,
                last_signal_event=last_signal_event,
                last_paper_event=last_paper_event,
                signal_count=signal_count,
                candidate_count=candidate_count,
                paper_order_count=paper_order_count,
                open_positions=open_positions,
                closed_positions=closed_positions,
                realized_pnl=round(realized_pnl, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                total_costs=round(total_costs, 2),
                net_pnl=round(net_pnl, 2),
                data_quality=data_quality,
                reconnect_count=reconnect_count,
                error_count=error_count,
                details_json=details_json or {},
            )
            self.session.add(record)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_worker_status(self, worker_id: str = "apex-market-worker") -> Dict[str, Any]:
        """Retrieves formatted worker status and evaluates heartbeat staleness."""
        stmt = select(WorkerHeartbeatModel).where(WorkerHeartbeatModel.worker_id == worker_id)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            return {
                "worker_id": worker_id,
                "worker_status": "NOT_STARTED",
                "market_connection": "DISCONNECTED",
                "database_status": "CONNECTED",
                "paper_mode": True,
                "live_trading": False,
                "live_orders_blocked": True,
                "safety_assertion": "REAL MARKET DATA | PAPER TRADING | LIVE ORDERS BLOCKED",
                "last_tick": None,
                "last_event": None,
                "signal_count": 0,
                "candidate_count": 0,
                "paper_order_count": 0,
                "open_positions": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "data_quality": "WAITING_FOR_WORKER",
                "reconnect_count": 0,
                "error_count": 0,
                "heartbeat_age_seconds": None,
                "is_stale": True,
                "message": "No active stateful worker registered in database.",
            }

        # Calculate staleness
        heartbeat_age = 0.0
        if record.updated_at:
            if record.updated_at.tzinfo is None:
                updated_ts = record.updated_at.replace(tzinfo=datetime.timezone.utc).timestamp()
            else:
                updated_ts = record.updated_at.timestamp()
            heartbeat_age = max(0.0, time.time() - updated_ts)

        is_stale = heartbeat_age > 60.0
        effective_status = "STALE" if is_stale and record.worker_status == "ONLINE" else record.worker_status

        return {
            "worker_id": record.worker_id,
            "experiment_id": record.experiment_id,
            "worker_status": effective_status,
            "market_connection": record.market_connection if not is_stale else "DISCONNECTED",
            "database_status": record.database_status,
            "paper_mode": record.paper_mode,
            "live_trading": False,  # Hard enforced
            "live_orders_blocked": True,  # Hard enforced
            "safety_assertion": "REAL MARKET DATA | PAPER TRADING | LIVE ORDERS BLOCKED",
            "last_tick": record.last_tick,
            "last_event": record.last_event,
            "last_market_event": record.last_market_event,
            "last_signal_event": record.last_signal_event,
            "last_paper_event": record.last_paper_event,
            "signal_count": record.signal_count,
            "candidate_count": record.candidate_count,
            "paper_order_count": record.paper_order_count,
            "open_positions": record.open_positions,
            "closed_positions": record.closed_positions,
            "realized_pnl": record.realized_pnl,
            "unrealized_pnl": record.unrealized_pnl,
            "total_costs": record.total_costs,
            "net_pnl": record.net_pnl,
            "data_quality": record.data_quality,
            "reconnect_count": record.reconnect_count,
            "error_count": record.error_count,
            "heartbeat_age_seconds": round(heartbeat_age, 1),
            "is_stale": is_stale,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            "details": record.details_json or {},
        }
