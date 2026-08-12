from app.db.repository import BaseRepository
from app.features.projects.models import Project


class ProjectRepository(BaseRepository[Project]):
    """Specific repository handling projects metadata database records queries."""
    pass


project_repo = ProjectRepository(Project)
