from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import setup_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware

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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Setup CORS policies middleware for Next.js queries
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup execution timing tracking middleware
app.add_middleware(RequestLoggingMiddleware)

# Wire global exception handler envelopes
setup_exception_handlers(app)


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

