import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.app.config import settings

logger = logging.getLogger(__name__)

import os

# Base declarative class
Base = declarative_base()

# Async Engine Creation (supports PostgreSQL + asyncpg or SQLite for dev)
# Async Engine Creation (supports PostgreSQL + psycopg/asyncpg or SQLite for dev)
is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
default_db_path = "/tmp/apex_quant.db" if is_vercel else "./apex_quant.db"
raw_db_url = getattr(settings, "database_url", None) or os.environ.get("DATABASE_URL")

if raw_db_url:
    database_url = raw_db_url.strip()
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("sqlite:///") and not database_url.startswith("sqlite+aiosqlite:///"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    database_url = f"sqlite+aiosqlite:///{default_db_path}"

engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Create database tables if they do not exist, and ensure schema migrations/columns are present."""
    try:
        from backend.app.database import models  # noqa: F401 - ensure models register with Base metadata
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Auto-migrate SQLite missing columns if table already exists
            if engine.dialect.name == "sqlite":
                # Check paper_orders columns
                res = await conn.execute(text("PRAGMA table_info(paper_orders)"))
                cols = {row[1] for row in res.fetchall()}
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

                # Check paper_fills columns
                res_fills = await conn.execute(text("PRAGMA table_info(paper_fills)"))
                cols_fills = {row[1] for row in res_fills.fetchall()}
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

        logger.info("[DATABASE] Database initialized successfully.")
    except Exception as e:
        logger.warning(f"[DATABASE] Database initialization warning: {e}")

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
