from app.db.repository import BaseRepository
from app.features.reports.models import Report


class ReportRepository(BaseRepository[Report]):
    """Specific repository handling report metadata queries."""

    pass


report_repo = ReportRepository(Report)
