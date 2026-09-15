"""
APEX Audit & Session Report Repository
======================================
Manages persistence, retrieval, and verification of durable audit events,
periodic session checkpoints, and finalized certified session reports in PostgreSQL / SQLite.
Enforces monotonic global event ordering and idempotent session recovery.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import AuditEventModel, SessionReportModel

logger = logging.getLogger(__name__)


class AuditRepository:
    """Manages persistence and retrieval of audit events and certified session reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_audit_event(self, event_data: Dict[str, Any]) -> AuditEventModel:
        """Inserts a single audit event into the database."""
        s_date = event_data.get("session_date") or event_data.get("trading_day") or event_data.get("event_timestamp_ist", "")[:10]
        seq = event_data.get("sequence_number", 1)
        gseq = event_data.get("global_sequence_number") or seq

        event = AuditEventModel(
            event_id=event_data["event_id"],
            experiment_id=event_data["experiment_id"],
            session_date=s_date,
            trading_day=event_data.get("trading_day") or s_date,
            session_instance_id=event_data.get("session_instance_id"),
            worker_instance_id=event_data.get("worker_instance_id"),
            event_type=event_data["event_type"],
            sequence_number=seq,
            global_sequence_number=gseq,
            market_timestamp=event_data.get("market_timestamp"),
            event_timestamp_utc=event_data["event_timestamp_utc"],
            event_timestamp_ist=event_data["event_timestamp_ist"],
            processing_timestamp_utc=event_data.get("processing_timestamp_utc"),
            processing_latency_ms=event_data.get("processing_latency_ms"),
            symbol=event_data.get("symbol"),
            instrument_key=event_data.get("instrument_key"),
            source=event_data.get("source", "APEX_CORE"),
            provider=event_data.get("provider"),
            data_provenance=event_data.get("data_provenance", "AUTHENTIC_LIVE"),
            market_phase=event_data.get("market_phase", "PREMARKET"),
            git_commit=event_data.get("git_commit"),
            config_hash=event_data.get("config_hash"),
            engine_version=event_data.get("engine_version"),
            payload=event_data.get("payload") or {},
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def insert_audit_events_batch(self, events_data: List[Dict[str, Any]]) -> int:
        """Batch-inserts multiple audit events atomically."""
        if not events_data:
            return 0

        instances = []
        for d in events_data:
            s_date = d.get("session_date") or d.get("trading_day") or d.get("event_timestamp_ist", "")[:10]
            seq = d.get("sequence_number", 1)
            gseq = d.get("global_sequence_number") or seq
            instances.append(AuditEventModel(
                event_id=d["event_id"],
                experiment_id=d["experiment_id"],
                session_date=s_date,
                trading_day=d.get("trading_day") or s_date,
                session_instance_id=d.get("session_instance_id"),
                worker_instance_id=d.get("worker_instance_id"),
                event_type=d["event_type"],
                sequence_number=seq,
                global_sequence_number=gseq,
                market_timestamp=d.get("market_timestamp"),
                event_timestamp_utc=d["event_timestamp_utc"],
                event_timestamp_ist=d["event_timestamp_ist"],
                processing_timestamp_utc=d.get("processing_timestamp_utc"),
                processing_latency_ms=d.get("processing_latency_ms"),
                symbol=d.get("symbol"),
                instrument_key=d.get("instrument_key"),
                source=d.get("source", "APEX_CORE"),
                provider=d.get("provider"),
                data_provenance=d.get("data_provenance", "AUTHENTIC_LIVE"),
                market_phase=d.get("market_phase", "PREMARKET"),
                git_commit=d.get("git_commit"),
                config_hash=d.get("config_hash"),
                engine_version=d.get("engine_version"),
                payload=d.get("payload") or {},
            ))

        self.session.add_all(instances)
        await self.session.commit()
        return len(instances)

    async def get_last_sequence_numbers(self, session_date: str) -> Tuple[int, int]:
        """
        Returns (max_global_sequence_number, max_local_sequence_number) for a session date.
        Guarantees that global sequence numbers never reset upon worker restart.
        """
        stmt = select(
            func.max(AuditEventModel.global_sequence_number),
            func.max(AuditEventModel.sequence_number)
        ).where(AuditEventModel.session_date == session_date)
        res = await self.session.execute(stmt)
        row = res.first()
        max_gseq = int(row[0]) if row and row[0] is not None else 0
        max_lseq = int(row[1]) if row and row[1] is not None else 0
        return max_gseq, max_lseq

    async def has_session_started(self, session_date: str) -> bool:
        """Checks if a SESSION_START event has already been recorded for this session date."""
        stmt = select(func.count(AuditEventModel.id)).where(
            AuditEventModel.session_date == session_date,
            AuditEventModel.event_type == "SESSION_START"
        )
        res = await self.session.execute(stmt)
        cnt = res.scalar() or 0
        return cnt > 0

    async def get_session_recovery_state(self, session_date: str) -> Dict[str, Any]:
        """
        Recovers comprehensive state from database for restarting an active trading session.
        """
        max_gseq, max_lseq = await self.get_last_sequence_numbers(session_date)
        has_started = await self.has_session_started(session_date)

        # Count total events and distinct event categories
        count_stmt = select(
            func.count(AuditEventModel.id),
            func.count().filter(AuditEventModel.event_type.like("%TICK%")),
            func.count().filter(AuditEventModel.event_type.like("%CANDLE%")),
            func.count().filter(AuditEventModel.event_type.like("%EVALUATION%")),
            func.count().filter(AuditEventModel.event_type.like("%CANDIDATE%")),
            func.count().filter(AuditEventModel.event_type.like("%SIGNAL%")),
            func.count().filter(AuditEventModel.event_type.like("%ORDER%")),
        ).where(AuditEventModel.session_date == session_date)
        res_counts = await self.session.execute(count_stmt)
        c_row = res_counts.first()

        # Check existing session report
        rep = await self.get_session_report(session_date)

        return {
            "session_date": session_date,
            "has_started": has_started,
            "max_global_sequence": max_gseq,
            "max_local_sequence": max_lseq,
            "total_events_in_db": int(c_row[0]) if c_row and c_row[0] else 0,
            "report_status": rep.get("status") if rep else None,
            "is_finalized": rep.get("status") == "FINALIZED" if rep else False,
        }

    async def get_audit_events(
        self,
        session_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves paginated audit events ordered by global sequence."""
        stmt = select(AuditEventModel)
        if session_date:
            stmt = stmt.where(AuditEventModel.session_date == session_date)
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)
        if symbol:
            stmt = stmt.where(AuditEventModel.symbol == symbol)

        # Order by global_sequence_number if populated, falling back to sequence_number
        stmt = stmt.order_by(AuditEventModel.id.asc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        records = res.scalars().all()

        return {
            "session_date": session_date,
            "total_returned": len(records),
            "limit": limit,
            "offset": offset,
            "events": [
                {
                    "event_id": r.event_id,
                    "experiment_id": r.experiment_id,
                    "session_date": r.session_date,
                    "trading_day": r.trading_day or r.session_date,
                    "session_instance_id": r.session_instance_id,
                    "worker_instance_id": r.worker_instance_id,
                    "event_type": r.event_type,
                    "sequence_number": r.sequence_number,
                    "global_sequence_number": r.global_sequence_number or r.sequence_number,
                    "market_timestamp": r.market_timestamp,
                    "event_timestamp_utc": r.event_timestamp_utc,
                    "event_timestamp_ist": r.event_timestamp_ist,
                    "processing_timestamp_utc": r.processing_timestamp_utc,
                    "processing_latency_ms": r.processing_latency_ms,
                    "symbol": r.symbol,
                    "instrument_key": r.instrument_key,
                    "source": r.source,
                    "provider": r.provider,
                    "data_provenance": r.data_provenance,
                    "market_phase": r.market_phase,
                    "git_commit": r.git_commit,
                    "config_hash": r.config_hash,
                    "engine_version": r.engine_version,
                    "payload": r.payload,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
        }

    async def upsert_session_report(
        self,
        session_date: str,
        experiment_id: str,
        status: str = "FINALIZED",
        report_markdown: Optional[str] = None,
        master_log_sha256: Optional[str] = None,
        total_events: int = 0,
        final_global_sequence: Optional[int] = None,
        recovery_count: int = 0,
        first_event_id: Optional[str] = None,
        last_event_id: Optional[str] = None,
        summary_metrics: Optional[Dict[str, Any]] = None,
        checkpoints: Optional[List[Dict[str, Any]]] = None,
        is_certified: bool = True,
        trading_day: Optional[str] = None,
        session_instance_id: Optional[str] = None,
        worker_instance_id: Optional[str] = None,
    ) -> SessionReportModel:
        """Inserts or updates the certified session report for a given date."""
        stmt = select(SessionReportModel).where(SessionReportModel.session_date == session_date)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            record.experiment_id = experiment_id
            record.status = status
            record.trading_day = trading_day or session_date
            if session_instance_id is not None:
                record.session_instance_id = session_instance_id
            if worker_instance_id is not None:
                record.worker_instance_id = worker_instance_id
            if report_markdown is not None:
                record.report_markdown = report_markdown
            if master_log_sha256 is not None:
                record.master_log_sha256 = master_log_sha256
            record.total_events = total_events
            if final_global_sequence is not None:
                record.final_global_sequence = final_global_sequence
            record.recovery_count = recovery_count
            if first_event_id is not None:
                record.first_event_id = first_event_id
            if last_event_id is not None:
                record.last_event_id = last_event_id
            if summary_metrics is not None:
                record.summary_metrics = summary_metrics
            if checkpoints is not None:
                record.checkpoints = checkpoints
            record.is_certified = is_certified
        else:
            record = SessionReportModel(
                experiment_id=experiment_id,
                session_date=session_date,
                trading_day=trading_day or session_date,
                session_instance_id=session_instance_id,
                worker_instance_id=worker_instance_id,
                status=status,
                report_markdown=report_markdown,
                master_log_sha256=master_log_sha256,
                total_events=total_events,
                final_global_sequence=final_global_sequence or total_events,
                recovery_count=recovery_count,
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                summary_metrics=summary_metrics or {},
                checkpoints=checkpoints or [],
                is_certified=is_certified,
            )
            self.session.add(record)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_session_report(self, session_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetches the session report for a specific date, or the latest available."""
        stmt = select(SessionReportModel)
        if session_date:
            stmt = stmt.where(SessionReportModel.session_date == session_date)
        else:
            stmt = stmt.order_by(desc(SessionReportModel.created_at)).limit(1)

        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return None

        return {
            "id": record.id,
            "experiment_id": record.experiment_id,
            "session_date": record.session_date,
            "trading_day": record.trading_day or record.session_date,
            "session_instance_id": record.session_instance_id,
            "worker_instance_id": record.worker_instance_id,
            "status": record.status,
            "master_log_sha256": record.master_log_sha256,
            "total_events": record.total_events,
            "final_global_sequence": record.final_global_sequence,
            "recovery_count": record.recovery_count,
            "first_event_id": record.first_event_id,
            "last_event_id": record.last_event_id,
            "summary_metrics": record.summary_metrics,
            "checkpoints": record.checkpoints,
            "report_markdown": record.report_markdown,
            "is_certified": record.is_certified,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    async def get_checkpoints(self, session_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves checkpoint list from the session report or audit events."""
        report = await self.get_session_report(session_date)
        if report and report.get("checkpoints"):
            return report["checkpoints"]

        # Fallback: query SESSION_CHECKPOINT events from audit_events
        stmt = select(AuditEventModel).where(AuditEventModel.event_type == "SESSION_CHECKPOINT")
        if session_date:
            stmt = stmt.where(AuditEventModel.session_date == session_date)
        stmt = stmt.order_by(AuditEventModel.id.asc())

        res = await self.session.execute(stmt)
        events = res.scalars().all()
        return [
            {
                "checkpoint_id": e.payload.get("checkpoint_id", f"CP_{e.sequence_number}"),
                "timestamp_ist": e.event_timestamp_ist,
                "sequence_number": e.sequence_number,
                "global_sequence_number": e.global_sequence_number,
                "market_phase": e.market_phase,
                "payload": e.payload,
            }
            for e in events
        ]
