import pytest
import asyncio
from app.core.database import async_engine
from app.db.base import Base

# Import all models to ensure they register on Base.metadata
try:
    from app.features.auth.models import User
    from app.features.projects.models import Project
    from app.features.datasets.models import Dataset
    from app.features.reports.models import Report, ReportSchedule
except ImportError:
    pass

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes the database schema for the entire pytest session."""
    async def create_tables():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    # Run synchronously during fixture setup
    asyncio.run(create_tables())
    yield
