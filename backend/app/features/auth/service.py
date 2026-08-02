from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from jose import jwt

from app.core.config import settings


class AuthService:
    """Orchestrates access token creation and payload validation checks."""

    @staticmethod
    def create_access_token(subject: str, role: str = "Owner") -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode = {"sub": subject, "role": role, "exp": expire}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def create_refresh_token(subject: str, role: str = "Owner") -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
        to_encode = {"sub": subject, "role": role, "exp": expire}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
