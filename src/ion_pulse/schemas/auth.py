from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ValidatorFunctionWrapHandler, WrapValidator

from ion_pulse.core.config import get_settings


def validate_account_email(value: object, handler: ValidatorFunctionWrapHandler) -> str:
    # The seed uses reserved addresses that EmailStr intentionally rejects.
    # Keep the exception confined to known demo identities outside deployed environments.
    if isinstance(value, str) and get_settings().environment in {"local", "test"}:
        normalized = value.strip().lower()
        demo_names = {"admin", "editor", "content", "author", "moderator", "player"}
        if normalized in {f"{name}@ion-pulse.local" for name in demo_names}:
            return normalized
    return str(handler(value))


AccountEmail = Annotated[EmailStr, WrapValidator(validate_account_email)]


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: AccountEmail
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=12, max_length=128)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: AccountEmail
    display_name: str
    roles: list[str]


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class AccountDeletionRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=1000)
