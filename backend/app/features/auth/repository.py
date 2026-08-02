from app.db.repository import BaseRepository
from app.features.auth.models import User


class UserRepository(BaseRepository[User]):
    """Specific repository handling user query logic."""

    pass


user_repo = UserRepository(User)
