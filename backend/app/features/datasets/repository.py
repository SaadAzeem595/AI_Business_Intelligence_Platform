from app.db.repository import BaseRepository
from app.features.datasets.models import Dataset


class DatasetRepository(BaseRepository[Dataset]):
    """Specific repository handling dataset metadata records queries."""

    pass


dataset_repo = DatasetRepository(Dataset)
