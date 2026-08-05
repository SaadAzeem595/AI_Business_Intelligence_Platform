import logging
import json
from fastapi import APIRouter, Depends, status, Form, HTTPException
from pydantic import EmailStr
from jose import jwt, JWTError

from app.core.config import settings
from app.core.dependencies import get_current_user, MockUser
from app.features.auth.schemas import Token, UserResponse
from app.features.auth.service import AuthService

logger = logging.getLogger("audit_log")
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    username: EmailStr = Form(...),
    password: str = Form(...),
) -> Token:
    """Login endpoint returning access and refresh JWT tokens and audit logging success."""
    # For a real enterprise platform, role defaults to Executive/Analyst/Viewer based on username patterns
    role = "Owner"
    if "admin" in username.lower():
        role = "Admin"
    elif "executive" in username.lower():
        role = "Executive"
    elif "analyst" in username.lower():
        role = "Analyst"
    elif "viewer" in username.lower():
        role = "Viewer"

    access_token = AuthService.create_access_token(subject=username, role=role)
    refresh_token = AuthService.create_refresh_token(subject=username, role=role)
    
    user_data = UserResponse(
        id=f"user-{username.split('@')[0]}",
        email=username,
        name=username.split("@")[0].capitalize(),
        role=role,
    )
    
    # Audit log
    logger.info(json.dumps({
        "event_type": "user_login",
        "user_email": username,
        "role": role,
        "status": "success",
        "message": f"User {username} logged in successfully."
    }))
    
    token_resp = Token(accessToken=access_token, refreshToken=refresh_token, user=user_data)
    return token_resp


@router.post("/register", response_model=Token)
async def register(
    email: EmailStr = Form(...),
    password: str = Form(...),
    name: str = Form(None),
) -> Token:
    """Registration endpoint generating credentials and logging audit event."""
    role = "Analyst"  # Default role for register
    if "admin" in email.lower():
        role = "Admin"
        
    access_token = AuthService.create_access_token(subject=email, role=role)
    refresh_token = AuthService.create_refresh_token(subject=email, role=role)
    
    user_data = UserResponse(
        id=f"user-{email.split('@')[0]}",
        email=email,
        name=name or email.split("@")[0].capitalize(),
        role=role,
    )
    
    # Audit log
    logger.info(json.dumps({
        "event_type": "user_register",
        "user_email": email,
        "role": role,
        "status": "success",
        "message": f"User {email} registered successfully."
    }))
    
    return Token(accessToken=access_token, refreshToken=refresh_token, user=user_data)


@router.post("/refresh", response_model=Token)
async def refresh(
    refreshToken: str = Form(...),
) -> Token:
    """Refreshes the active session access token using a valid refresh token."""
    try:
        payload = jwt.decode(
            refreshToken, settings.SECRET_KEY, algorithms=["HS256"]
        )
        username: str = payload.get("sub")
        role: str = payload.get("role", "Viewer")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload."
            )
            
        access_token = AuthService.create_access_token(subject=username, role=role)
        new_refresh_token = AuthService.create_refresh_token(subject=username, role=role)
        user_data = UserResponse(
            id=f"user-{username.split('@')[0]}",
            email=username,
            name=username.split("@")[0].capitalize(),
            role=role,
        )
        
        # Audit log
        logger.info(json.dumps({
            "event_type": "token_refresh",
            "user_email": username,
            "status": "success",
            "message": "Token refreshed successfully."
        }))
        
        return Token(accessToken=access_token, refreshToken=new_refresh_token, user=user_data)
    except JWTError as e:
        logger.warning(json.dumps({
            "event_type": "token_refresh_failed",
            "status": "failed",
            "error": str(e)
        }))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}."
        )


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
async def logout(current_user: MockUser = Depends(get_current_user)) -> dict:
    """Terminates active session parameters."""
    logger.info(json.dumps({
        "event_type": "user_logout",
        "user_email": current_user.email,
        "status": "success",
        "message": f"User {current_user.email} logged out successfully."
    }))
    return {"status": "success"}

