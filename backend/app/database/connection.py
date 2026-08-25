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
is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
default_db_path = "/tmp/apex_quant.db" if is_vercel else "./apex_quant.db"
database_url = getattr(settings, "database_url", None) or f"sqlite+aiosqlite:///{default_db_path}"
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

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
    """Create database tables if they do not exist."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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
