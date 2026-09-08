import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from backend.app.config import settings

logger = logging.getLogger(__name__)

import os

# Base declarative class
Base = declarative_base()

# Async Engine Creation (supports PostgreSQL + asyncpg or SQLite for dev)
# Enforce fail-closed safety and database validation in production mode
try:
    settings.validate_production_invariants()
except Exception as e:
    logger.critical(f"[DATABASE CONFIG ERROR] {e}")
    if getattr(settings, "is_production", False):
        raise

# Async Engine Creation (supports PostgreSQL + psycopg/asyncpg or SQLite for dev)
is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
default_db_path = "/tmp/apex_quant.db" if is_vercel else "./apex_quant.db"
raw_db_url = getattr(settings, "database_url", None) or os.environ.get("DATABASE_URL")

if raw_db_url:
    database_url = raw_db_url.strip()
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        try:
            import asyncpg  # noqa: F401
            driver = "postgresql+asyncpg://"
        except ImportError:
            driver = "postgresql+psycopg://"
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", driver, 1)
        else:
            database_url = database_url.replace("postgres://", driver, 1)
    elif database_url.startswith("sqlite:///") and not database_url.startswith("sqlite+aiosqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    database_url = f"sqlite+aiosqlite:///{default_db_path}"

# SQLite's async driver owns a worker thread for every checked-out connection.
# Keeping those connections in a long-lived pool causes short-lived processes
# (tests, CLI jobs and serverless invocations) to remain alive after their work
# finishes. SQLite has a single-writer concurrency model anyway, so a
# non-pooling engine is the safer, deterministic default. PostgreSQL retains
# SQLAlchemy's regular pooling semantics.
engine_options = {
    "echo": False,
    "future": True,
}
if database_url.startswith("sqlite+"):
    engine_options["poolclass"] = NullPool
    engine_options["connect_args"] = {"timeout": 30.0}
else:
    engine_options["pool_pre_ping"] = True
    engine_options["pool_size"] = 10
    engine_options["max_overflow"] = 20
    engine_options["pool_recycle"] = 3600

engine = create_async_engine(database_url, **engine_options)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_table_columns(conn, table_name: str) -> set:
    """Returns lowercased column names for a given table in SQLite or PostgreSQL."""
    try:
        if conn.dialect.name == "sqlite":
            res = await conn.execute(text(f"PRAGMA table_info({table_name})"))
            return {row[1].lower() for row in res.fetchall()}
        else:
            res = await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
                {"t": table_name.lower()}
            )
            return {row[0].lower() for row in res.fetchall()}
    except Exception:
        return set()

async def init_db():
    """Create database tables if they do not exist, and ensure schema migrations/columns are present."""
    try:
        from backend.app.database import models  # noqa: F401 - ensure models register with Base metadata
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Auto-migrate missing columns if table already exists (dialect-agnostic)
            # 1. Check paper_orders columns
            cols = await get_table_columns(conn, "paper_orders")
            if cols:
                if "exchange" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN exchange VARCHAR(20) DEFAULT 'NSE'"))
                if "order_type" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN order_type VARCHAR(20) DEFAULT 'MARKET'"))
                if "requested_price" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN requested_price FLOAT"))
                if "rejection_reason" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN rejection_reason VARCHAR(255)"))
                if "filled_at" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN filled_at TIMESTAMP"))
                if "signal_id" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN signal_id VARCHAR(100)"))
                if "candidate_id" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN candidate_id VARCHAR(100)"))
                if "strategy_version" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN strategy_version VARCHAR(50)"))
                if "signal_engine_version" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN signal_engine_version VARCHAR(50)"))
                if "configuration_hash" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN configuration_hash VARCHAR(100)"))
                if "decision_reason" not in cols:
                    await conn.execute(text("ALTER TABLE paper_orders ADD COLUMN decision_reason TEXT"))

            # 2. Check paper_fills columns
            cols_fills = await get_table_columns(conn, "paper_fills")
            if cols_fills:
                if "stt" not in cols_fills:
                    await conn.execute(text("ALTER TABLE paper_fills ADD COLUMN stt FLOAT DEFAULT 0.0"))
                if "exchange_charges" not in cols_fills:
                    await conn.execute(text("ALTER TABLE paper_fills ADD COLUMN exchange_charges FLOAT DEFAULT 0.0"))
                if "sebi_charges" not in cols_fills:
                    await conn.execute(text("ALTER TABLE paper_fills ADD COLUMN sebi_charges FLOAT DEFAULT 0.0"))
                if "gst" not in cols_fills:
                    await conn.execute(text("ALTER TABLE paper_fills ADD COLUMN gst FLOAT DEFAULT 0.0"))
                if "stamp_duty" not in cols_fills:
                    await conn.execute(text("ALTER TABLE paper_fills ADD COLUMN stamp_duty FLOAT DEFAULT 0.0"))

            # 3. Check option_snapshots columns
            cols_opts = await get_table_columns(conn, "option_snapshots")
            if cols_opts:
                if "bid" not in cols_opts:
                    await conn.execute(text("ALTER TABLE option_snapshots ADD COLUMN bid FLOAT DEFAULT 0.0"))
                if "ask" not in cols_opts:
                    await conn.execute(text("ALTER TABLE option_snapshots ADD COLUMN ask FLOAT DEFAULT 0.0"))
                if "source" not in cols_opts:
                    await conn.execute(text("ALTER TABLE option_snapshots ADD COLUMN source VARCHAR(50) DEFAULT 'UPSTOX'"))
                if "provenance" not in cols_opts:
                    await conn.execute(text("ALTER TABLE option_snapshots ADD COLUMN provenance VARCHAR(50) DEFAULT 'RECORDED_AUTHENTIC'"))
                if "provider_instrument_key" not in cols_opts:
                    await conn.execute(text("ALTER TABLE option_snapshots ADD COLUMN provider_instrument_key VARCHAR(100)"))

            # 4. Check signals columns
            cols_signals = await get_table_columns(conn, "signals")
            if cols_signals:
                if "futures_decision_json" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN futures_decision_json JSON"))
                if "options_decision_json" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN options_decision_json JSON"))
                if "cost_estimate_json" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN cost_estimate_json JSON"))
                if "candidate_id" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN candidate_id VARCHAR(100)"))
                if "strategy_version" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN strategy_version VARCHAR(50)"))
                if "signal_engine_version" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN signal_engine_version VARCHAR(50)"))
                if "configuration_hash" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN configuration_hash VARCHAR(100)"))
                if "git_commit" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN git_commit VARCHAR(100)"))
                if "market_timestamp" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN market_timestamp FLOAT"))
                if "data_age_ms" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN data_age_ms FLOAT"))
                if "spread" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN spread FLOAT"))
                if "effective_strategy_count" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN effective_strategy_count INTEGER DEFAULT 0"))
                if "volatility_regime" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN volatility_regime VARCHAR(50)"))
                if "trend_regime" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN trend_regime VARCHAR(50)"))
                if "breadth_regime" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN breadth_regime VARCHAR(50)"))
                if "liquidity_regime" not in cols_signals:
                    await conn.execute(text("ALTER TABLE signals ADD COLUMN liquidity_regime VARCHAR(50)"))

            # 5. Check signal_rejections columns
            cols_rej = await get_table_columns(conn, "signal_rejections")
            if cols_rej:
                if "candidate_id" not in cols_rej:
                    await conn.execute(text("ALTER TABLE signal_rejections ADD COLUMN candidate_id VARCHAR(100)"))
                if "strategy_version" not in cols_rej:
                    await conn.execute(text("ALTER TABLE signal_rejections ADD COLUMN strategy_version VARCHAR(50)"))
                if "configuration_hash" not in cols_rej:
                    await conn.execute(text("ALTER TABLE signal_rejections ADD COLUMN configuration_hash VARCHAR(100)"))
                if "git_commit" not in cols_rej:
                    await conn.execute(text("ALTER TABLE signal_rejections ADD COLUMN git_commit VARCHAR(100)"))
                if "market_timestamp" not in cols_rej:
                    await conn.execute(text("ALTER TABLE signal_rejections ADD COLUMN market_timestamp FLOAT"))

        logger.info(f"[DATABASE] Database initialized successfully on dialect: {engine.dialect.name}")
    except Exception as e:
        logger.warning(f"[DATABASE] Database initialization warning: {e}")
        if getattr(settings, "is_production", False):
            raise RuntimeError(f"PRODUCTION FAIL-CLOSED: Database initialization failed: {e}") from e

async def check_db_health() -> Dict[str, Any]:
    """Execute active query on database connection to verify connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "ONLINE",
            "database": "CONNECTED",
            "dialect": engine.dialect.name
        }
    except Exception as e:
        logger.error(f"[DB HEALTH CHECK FAILED] {e}")
        return {
            "status": "DEGRADED",
            "database": "DISCONNECTED",
            "error": str(e)
        }

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions to FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
