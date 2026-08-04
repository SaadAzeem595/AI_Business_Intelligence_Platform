import os
import sys
import logging
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)

IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "1"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

class MockUser(BaseModel):
    id: str = "mock-user-uuid-101"
    email: str = "saad@example.com"
    name: str = "Saad Alvi"
    role: str = "Owner"

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db_session),
) -> MockUser:
    """
    Checks active credentials:
    1. First tries X-API-Key authentication.
    2. Then tries JWT token validation.
    3. Falls back to mock user in test/development mode if no credentials provided.
    """
    # 1. API Key Auth
    if x_api_key:
        valid_keys = [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]
        if x_api_key in valid_keys:
            # Map API key to an Analyst role user
            return MockUser(
                id="api-key-client",
                email="api-key-client@platform.com",
                name="API Automation",
                role="Analyst"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key credentials."
        )

    # 2. JWT Auth
    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            username: str = payload.get("sub")
            role: str = payload.get("role", "Viewer")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token validation failed: missing subject."
                )
            return MockUser(id=username, email=username, name=username.split("@")[0].capitalize(), role=role)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}."
            )

    # 3. Fallback for testing/dev ease
    if IS_TESTING:
        return MockUser()
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials are required."
    )

def require_role(allowed_roles: List[str]) -> Depends:
    """Enforces role membership check on endpoints."""
    def dependency(current_user: MockUser = Depends(get_current_user)):
        # Owner bypasses all checks
        if current_user.role == "Owner":
            return current_user
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Unauthorized role access attempt: user={current_user.email} "
                f"role={current_user.role} required={allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: insufficient permission privileges."
            )
        return current_user
    return Depends(dependency)

