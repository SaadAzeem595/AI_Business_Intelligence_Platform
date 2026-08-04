from typing import AsyncGenerator, Generator
import os
import sys
import duckdb
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Dynamic check for testing mode to use in-memory SQLite database
IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "1"

if IS_TESTING:
    # Use in-memory SQLite database for self-contained test executions
    async_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True
    )
else:
    # Async PostgreSQL Engine Setup
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injector offering async SQL transactions sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_duckdb_conn() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Provides a thread-safe connection mapping to the in-memory/disk DuckDB engine."""
    conn = duckdb.connect(database=settings.DUCKDB_PATH, read_only=False)
    try:
        yield conn
    finally:
        conn.close()
