import sentry_sdk
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import settings
from app.core.exceptions import setup_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.telemetry import setup_telemetry

# Import feature routers endpoints
from app.features.auth.router import router as auth_router
from app.features.projects.router import router as projects_router
from app.features.datasets.router import router as datasets_router
from app.features.analytics.router import router as analytics_router
from app.features.chat.router import router as chat_router
from app.features.reports.router import router as reports_router
from app.features.settings.router import router as settings_router
from app.features.ml.router import router as ml_router
from app.features.rag.router import router as rag_router
from app.features.agents.router import router as agents_router


# Initialize structured logging dict config
setup_logging()

# Sentry setup
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Setup CORS policies middleware for Next.js queries
raw_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] if settings.ALLOWED_ORIGINS else []
origins = [o for o in raw_origins if o != "*"]

# If "*" is in ALLOWED_ORIGINS or no origins are found, set explicit local development origins
# to support allow_credentials=True since wildcards are disallowed when sending credentials.
if "*" in raw_origins or not origins:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Setup execution timing tracking middleware
app.add_middleware(RequestLoggingMiddleware)

# Wire global exception handler envelopes
setup_exception_handlers(app)

# Setup Prometheus exporter
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Setup OpenTelemetry
setup_telemetry(settings.PROJECT_NAME)
FastAPIInstrumentor.instrument_app(app)



@app.on_event("startup")
async def startup_event():
    """Automatically create all tables in Postgres/SQLite at startup for dev/testing ease."""
    import logging
    startup_logger = logging.getLogger(__name__)

    # Defensive check for production environment + DEV_AUTH_BYPASS
    env_vars = [settings.ENVIRONMENT, settings.NODE_ENV, settings.APP_ENV]
    is_prod = any(v and v.strip().lower() == "production" for v in env_vars)
    if is_prod and settings.DEV_AUTH_BYPASS:
        import sys
        startup_logger.error("CRITICAL CONFIGURATION ERROR: DEV_AUTH_BYPASS cannot be enabled in a production environment!")
        sys.exit("CRITICAL CONFIGURATION ERROR: DEV_AUTH_BYPASS cannot be enabled in a production environment!")
    
    from app.core.database import async_engine, USE_SQLITE
    from app.db.base import Base
    # Import all models to ensure they register on Base
    try:
        from app.features.auth.models import User
        from app.features.projects.models import Project
        from app.features.datasets.models import Dataset
        from app.features.reports.models import Report, ReportSchedule
    except ImportError:
        pass
        
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        from sqlalchemy import text
        def check_and_upgrade_datasets_table(sync_conn):
            try:
                # SQLite
                cols = sync_conn.execute(text("PRAGMA table_info(datasets)"))
                col_names = [row[1] for row in cols.fetchall()]
            except Exception:
                try:
                    # Postgres
                    cols = sync_conn.execute(text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='datasets'"
                    ))
                    col_names = [row[0] for row in cols.fetchall()]
                except Exception:
                    col_names = []
            
            if col_names:
                new_cols = {
                    "workspace_id": "VARCHAR",
                    "display_name": "VARCHAR",
                    "storage_path": "VARCHAR",
                    "duckdb_table": "VARCHAR",
                    "columns_json": "VARCHAR",
                    "schema_json": "VARCHAR",
                    "project_id": "VARCHAR",
                    "owner_id": "VARCHAR",
                    "original_filename": "VARCHAR",
                    "error_message": "VARCHAR",
                    "created_at": "TIMESTAMP",
                    "updated_at": "TIMESTAMP"
                }
                for col, col_type in new_cols.items():
                    if col not in col_names:
                        try:
                            sync_conn.execute(text(f"ALTER TABLE datasets ADD COLUMN {col} {col_type}"))
                            startup_logger.info(f"Dynamically added missing column {col} to datasets table")
                        except Exception as e:
                            startup_logger.warning(f"Could not add column {col} to datasets: {e}")

        def check_and_upgrade_users_table(sync_conn):
            try:
                # SQLite
                cols = sync_conn.execute(text("PRAGMA table_info(users)"))
                col_names = [row[1] for row in cols.fetchall()]
            except Exception:
                try:
                    # Postgres
                    cols = sync_conn.execute(text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
                    ))
                    col_names = [row[0] for row in cols.fetchall()]
                except Exception:
                    col_names = []
            
            if col_names:
                new_cols = {
                    "clerk_user_id": "VARCHAR",
                    "role": "VARCHAR DEFAULT 'Viewer'",
                    "created_at": "TIMESTAMP",
                    "updated_at": "TIMESTAMP"
                }
                for col, col_type in new_cols.items():
                    if col not in col_names:
                        try:
                            sync_conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                            startup_logger.info(f"Dynamically added missing column {col} to users table")
                        except Exception as e:
                            startup_logger.warning(f"Could not add column {col} to users: {e}")
                
                if not USE_SQLITE:
                    try:
                        sync_conn.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"))
                        startup_logger.info("Successfully dropped NOT NULL constraint on users.hashed_password")
                    except Exception as e:
                        startup_logger.warning(f"Could not drop NOT NULL on users.hashed_password: {e}")

        def check_and_upgrade_projects_table(sync_conn):
            try:
                # SQLite
                cols = sync_conn.execute(text("PRAGMA table_info(projects)"))
                col_names = [row[1] for row in cols.fetchall()]
            except Exception:
                try:
                    # Postgres
                    cols = sync_conn.execute(text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='projects'"
                    ))
                    col_names = [row[0] for row in cols.fetchall()]
                except Exception:
                    col_names = []
            
            if col_names:
                new_cols = {
                    "status": "VARCHAR DEFAULT 'Active'",
                }
                for col, col_type in new_cols.items():
                    if col not in col_names:
                        try:
                            sync_conn.execute(text(f"ALTER TABLE projects ADD COLUMN {col} {col_type}"))
                            startup_logger.info(f"Dynamically added missing column {col} to projects table")
                        except Exception as e:
                            startup_logger.warning(f"Could not add column {col} to projects: {e}")

        await conn.run_sync(check_and_upgrade_datasets_table)
        await conn.run_sync(check_and_upgrade_users_table)
        await conn.run_sync(check_and_upgrade_projects_table)

    if settings.DEV_AUTH_BYPASS and not is_prod:
        startup_logger.warning("!" * 80)
        startup_logger.warning("WARNING: Development authentication bypass is ENABLED.")
        startup_logger.warning("Development user: developer@datapilot.com")
        startup_logger.warning("This mode MUST NOT be used in production.")
        startup_logger.warning("!" * 80)
    from app.core.llm import LLMService
    llm_diag = LLMService.get_diagnostic_status()
    startup_logger.info("=" * 80)
    startup_logger.info("AI Business Intelligence Platform FastAPI backend started successfully!")
    startup_logger.info(f"Database engine in use: {'SQLite (resilient dev fallback)' if USE_SQLITE else 'PostgreSQL'}")
    startup_logger.info(
        f"LLM Provider Diagnostic: provider={llm_diag['provider']} "
        f"provider_configured={'yes' if llm_diag['provider_configured'] else 'no'} "
        f"model={llm_diag['model']} "
        f"model_configured={'yes' if llm_diag['model_configured'] else 'no'} "
        f"api_key_configured={'yes' if llm_diag['api_key_configured'] else 'no'} "
        f"base_url_configured={'yes' if llm_diag['base_url_configured'] else 'no'} "
        f"base_url={llm_diag['base_url']}"
    )
    startup_logger.info(f"Local API gateway prefix: http://localhost:8000{settings.API_V1_STR}")
    startup_logger.info("API Server listening on host: 0.0.0.0, port: 8000")
    startup_logger.info("Interactive OpenAPI Swagger Documentation: http://localhost:8000/docs")
    startup_logger.info("=" * 80)


@app.get("/health", tags=["Health & Status Checks"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health & Status Checks"])
async def health_check() -> dict:
    """Core health check route inspecting databases and analytics layers connectivity."""
    from app.core.llm import LLMService
    from app.core.database import AsyncSessionLocal, get_duckdb_conn
    from app.core.cache import cache_client
    from sqlalchemy import text

    status_info = {
        "status": "healthy",
        "fastapi": "healthy",
        "postgresql": "unhealthy",
        "duckdb": "unhealthy",
        "redis": "unhealthy",
        "llm": LLMService.get_diagnostic_status()
    }

    # 1. Probe PostgreSQL/SQLite
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            status_info["postgresql"] = "healthy"
    except Exception:
        pass

    # 2. Probe Redis Caching client connection
    try:
        await cache_client.connect()
        if cache_client.is_connected:
            status_info["redis"] = "healthy"
        else:
            status_info["redis"] = "healthy (fallback active)"
    except Exception:
        pass

    # 3. Probe DuckDB
    try:
        conn = next(get_duckdb_conn())
        conn.execute("SELECT 1")
        conn.close()
        status_info["duckdb"] = "healthy"
    except Exception:
        pass

    # 4. Probe LLM
    status_info["llm"] = LLMService.get_diagnostic_status()

    return status_info


@app.get(f"{settings.API_V1_STR}/health/llm", tags=["Health & Status Checks"])
async def llm_health_probe() -> dict:
    """Performs an active probe test request against the configured LLM service."""
    from app.core.llm import LLMService
    return LLMService.health_check()


@app.get("/live", tags=["Health & Status Checks"])
async def live_check() -> dict:
    """Liveness probe verifying that the container application is running."""
    return {"status": "alive"}


@app.get("/ready", tags=["Health & Status Checks"])
async def ready_check() -> dict:
    """Readiness probe checking PostgreSQL, Redis, and DuckDB health status."""
    from sqlalchemy import text
    from fastapi import Response
    import json
    from app.core.database import AsyncSessionLocal, get_duckdb_conn
    from app.core.cache import cache_client
    from app.core.llm import LLMService

    status_info = {
        "status": "ready",
        "fastapi": "healthy",
        "postgresql": "unknown",
        "duckdb": "unknown",
        "redis": "unknown",
        "llm": "unconfigured"
    }

    # 1. Probe PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            status_info["postgresql"] = "healthy"
    except Exception as e:
        status_info["postgresql"] = f"unhealthy: {str(e)}"
        status_info["status"] = "unready"

    # 2. Probe Redis Caching client connection
    try:
        await cache_client.connect()
        if cache_client.is_connected:
            status_info["redis"] = "healthy"
        else:
            status_info["redis"] = "unhealthy (fallback active)"
    except Exception as e:
        status_info["redis"] = f"unhealthy: {str(e)}"

    # 3. Probe DuckDB view execution
    try:
        conn = next(get_duckdb_conn())
        conn.execute("SELECT 1")
        conn.close()
        status_info["duckdb"] = "healthy"
    except Exception as e:
        status_info["duckdb"] = f"unhealthy: {str(e)}"
        status_info["status"] = "unready"

    # 4. Probe LLM
    if LLMService.is_configured():
        status_info["llm"] = "configured"

    if status_info["status"] == "unready":
        return Response(
            content=json.dumps(status_info),
            status_code=503,
            media_type="application/json"
        )
    return status_info


# Register versioned routers endpoints
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(datasets_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(settings_router, prefix=settings.API_V1_STR)
app.include_router(ml_router, prefix=settings.API_V1_STR)
app.include_router(rag_router, prefix=settings.API_V1_STR)
app.include_router(agents_router, prefix=settings.API_V1_STR)

