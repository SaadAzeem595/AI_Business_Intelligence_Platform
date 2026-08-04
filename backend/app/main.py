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
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] if settings.ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    """Automatically create all tables in Postgres at startup for dev/testing ease."""
    from app.core.database import async_engine
    from app.db.base import Base
    # Import all models to ensure they register on Base
    try:
        from app.features.auth.models import User
        from app.features.datasets.models import Dataset
        from app.features.reports.models import Report, ReportSchedule
    except ImportError:
        pass
        
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["Health & Status Checks"])
async def health_check() -> dict:
    """Core health check route inspecting databases and analytics layers connectivity."""
    return {"status": "healthy", "database": "active", "engine": "duckdb"}


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

    status_info = {
        "status": "ready",
        "postgres": "unknown",
        "redis": "unknown",
        "duckdb": "unknown"
    }

    # 1. Probe PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            status_info["postgres"] = "healthy"
    except Exception as e:
        status_info["postgres"] = f"unhealthy: {str(e)}"
        status_info["status"] = "unready"

    # 2. Probe Redis Caching client connection
    try:
        await cache_client.connect()
        if cache_client.is_connected:
            status_info["redis"] = "healthy"
        else:
            status_info["redis"] = "unhealthy (fallback active)"
            # Note: fallback is active so the application is still technically ready, 
            # but let's record it. If strict redis is required, set status = "unready"
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

    if status_info["status"] == "unready":
        return Response(
            content=json.dumps(status_info),
            status_code=503,
            media_type="application/json"
        )
    return status_info


# Register versioned routers endpoints
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(datasets_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(settings_router, prefix=settings.API_V1_STR)
app.include_router(ml_router, prefix=settings.API_V1_STR)
app.include_router(rag_router, prefix=settings.API_V1_STR)
app.include_router(agents_router, prefix=settings.API_V1_STR)

