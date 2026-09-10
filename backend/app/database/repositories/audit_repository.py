"""
APEX Audit & Session Report Repository
======================================
Manages persistence, retrieval, and verification of durable audit events,
periodic session checkpoints, and finalized certified session reports in PostgreSQL / SQLite.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import AuditEventModel, SessionReportModel

logger = logging.getLogger(__name__)


class AuditRepository:
    """Manages persistence and retrieval of audit events and certified session reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_audit_event(self, event_data: Dict[str, Any]) -> AuditEventModel:
        """Inserts a single audit event into the database."""
        event = AuditEventModel(
            event_id=event_data["event_id"],
            experiment_id=event_data["experiment_id"],
            session_date=event_data.get("session_date") or event_data.get("event_timestamp_ist", "")[:10],
            event_type=event_data["event_type"],
            sequence_number=event_data["sequence_number"],
            event_timestamp_utc=event_data["event_timestamp_utc"],
            event_timestamp_ist=event_data["event_timestamp_ist"],
            symbol=event_data.get("symbol"),
            source=event_data.get("source", "APEX_CORE"),
            data_provenance=event_data.get("data_provenance", "AUTHENTIC_LIVE"),
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
            s_date = d.get("session_date") or d.get("event_timestamp_ist", "")[:10]
            instances.append(AuditEventModel(
                event_id=d["event_id"],
                experiment_id=d["experiment_id"],
                session_date=s_date,
                event_type=d["event_type"],
                sequence_number=d["sequence_number"],
                event_timestamp_utc=d["event_timestamp_utc"],
                event_timestamp_ist=d["event_timestamp_ist"],
                symbol=d.get("symbol"),
                source=d.get("source", "APEX_CORE"),
                data_provenance=d.get("data_provenance", "AUTHENTIC_LIVE"),
                git_commit=d.get("git_commit"),
                config_hash=d.get("config_hash"),
                engine_version=d.get("engine_version"),
                payload=d.get("payload") or {},
            ))

        self.session.add_all(instances)
        await self.session.commit()
        return len(instances)

    async def get_audit_events(
        self,
        session_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves paginated audit events with optional filtering."""
        stmt = select(AuditEventModel)
        if session_date:
            stmt = stmt.where(AuditEventModel.session_date == session_date)
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)
        if symbol:
            stmt = stmt.where(AuditEventModel.symbol == symbol)

        stmt = stmt.order_by(AuditEventModel.sequence_number.asc()).limit(limit).offset(offset)
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
                    "event_type": r.event_type,
                    "sequence_number": r.sequence_number,
                    "event_timestamp_utc": r.event_timestamp_utc,
                    "event_timestamp_ist": r.event_timestamp_ist,
                    "symbol": r.symbol,
                    "source": r.source,
                    "data_provenance": r.data_provenance,
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
        first_event_id: Optional[str] = None,
        last_event_id: Optional[str] = None,
        summary_metrics: Optional[Dict[str, Any]] = None,
        checkpoints: Optional[List[Dict[str, Any]]] = None,
        is_certified: bool = True,
    ) -> SessionReportModel:
        """Inserts or updates the certified session report for a given date."""
        stmt = select(SessionReportModel).where(SessionReportModel.session_date == session_date)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            record.experiment_id = experiment_id
            record.status = status
            if report_markdown is not None:
                record.report_markdown = report_markdown
            if master_log_sha256 is not None:
                record.master_log_sha256 = master_log_sha256
            record.total_events = total_events
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
                status=status,
                report_markdown=report_markdown,
                master_log_sha256=master_log_sha256,
                total_events=total_events,
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
            "status": record.status,
            "master_log_sha256": record.master_log_sha256,
            "total_events": record.total_events,
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
        stmt = stmt.order_by(AuditEventModel.sequence_number.asc())

        res = await self.session.execute(stmt)
        events = res.scalars().all()
        return [
            {
                "checkpoint_id": e.payload.get("checkpoint_id", f"CP_{e.sequence_number}"),
                "timestamp_ist": e.event_timestamp_ist,
                "sequence_number": e.sequence_number,
                "payload": e.payload,
            }
            for e in events
        ]
