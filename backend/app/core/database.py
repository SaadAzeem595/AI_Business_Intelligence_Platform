from typing import AsyncGenerator, Generator
import os
import sys
import duckdb
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings

import logging

logger = logging.getLogger(__name__)

# Dynamic check for testing mode to use in-memory SQLite database
IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "1"

def get_target_db_host_and_port() -> tuple[str, int]:
    """Resolves target database host and port from DATABASE_URL or settings."""
    if settings.DATABASE_URL:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(settings.DATABASE_URL)
            if parsed.hostname:
                return parsed.hostname, parsed.port or 5432
        except Exception:
            pass
    return settings.POSTGRES_SERVER, settings.POSTGRES_PORT

def check_postgres_availability() -> bool:
    import socket
    host, port = get_target_db_host_and_port()
    try:
        # Simple TCP connection probe with a 5.0s timeout
        with socket.create_connection((host, port), timeout=5.0):
            return True
    except Exception:
        return False

postgres_available = check_postgres_availability()

if settings.is_production and not postgres_available and not IS_TESTING:
    host, port = get_target_db_host_and_port()
    error_msg = (
        f"CRITICAL DATABASE ERROR: Production PostgreSQL database at '{host}:{port}' is unreachable! "
        f"Refusing to fall back to ephemeral SQLite in production environment."
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg)

USE_SQLITE = IS_TESTING or (not postgres_available and not settings.is_production)

if USE_SQLITE:
    if not IS_TESTING:
        host, port = get_target_db_host_and_port()
        logger.warning(
            f"PostgreSQL server at {host}:{port} is unreachable. "
            f"Automatically falling back to local persistent SQLite database ('local_dev.db') for local development resiliency."
        )
    sqlite_url = "sqlite+aiosqlite:///:memory:" if IS_TESTING else "sqlite+aiosqlite:///local_dev.db"
    async_engine = create_async_engine(
        sqlite_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True
    )
else:
    # Async PostgreSQL Engine Setup with robust SSL support for Azure
    db_url = settings.DATABASE_URL
    connect_args = {}
    if "postgres" in db_url.lower() and ("azure.com" in db_url.lower() or "ssl=" in db_url.lower() or "sslmode=" in db_url.lower()):
        import ssl
        from urllib.parse import urlparse, urlunparse
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx
        # Strip query params like ssl=require from URL since we configure via connect_args
        parsed = urlparse(db_url)
        db_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, "", parsed.fragment))

    async_engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
        connect_args=connect_args,
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
        try:
            conn.close()
        except Exception:
            pass
