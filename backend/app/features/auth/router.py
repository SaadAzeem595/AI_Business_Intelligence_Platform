from fastapi import APIRouter, Depends, status, Form
from pydantic import EmailStr

from app.core.dependencies import get_current_user, MockUser
from app.features.auth.schemas import Token, UserResponse
from app.features.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    username: EmailStr = Form(...),
    password: str = Form(...),
) -> Token:
    """Mock login endpoint returning JWT tokens and current user metadata profiles."""
    access_token = AuthService.create_access_token(subject=username)
    user_data = UserResponse(
        id="mock-user-uuid-101",
        email=username,
        name="Saad Alvi",
        role="Owner",
    )
    return Token(accessToken=access_token, user=user_data)


@router.post("/register", response_model=Token)
async def register(
    email: EmailStr = Form(...),
    password: str = Form(...),
    name: str = Form(None),
) -> Token:
    """Mock registration endpoint returning JWT credentials."""
    access_token = AuthService.create_access_token(subject=email)
    user_data = UserResponse(
        id="mock-user-uuid-101",
        email=email,
        name=name or "Saad Alvi",
        role="Owner",
    )
    return Token(accessToken=access_token, user=user_data)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: MockUser = Depends(get_current_user)) -> UserResponse:
    """Fetches active validated profile payloads."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
    )


@router.post("/logout")
async def logout() -> dict:
    """Terminates active session parameters."""
    return {"status": "success"}
