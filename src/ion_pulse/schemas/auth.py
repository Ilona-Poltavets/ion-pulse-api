from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    roles: list[str]


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
