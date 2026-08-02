from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    role: str = "Owner"
    avatarUrl: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LoginInput(BaseModel):
    username: EmailStr  # Maps to OAuth2 standard username field parameter
    password: str


class SignupInput(UserCreate):
    pass


class Token(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: UserResponse
