from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ion_pulse.core.config import get_settings
from ion_pulse.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from ion_pulse.db.session import get_db_session
from ion_pulse.models.identity import User, UserSession
from ion_pulse.schemas.auth import AuthenticatedUser, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth")


def to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=[role.code for role in user.roles],
    )


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_lifetime_hours * 60 * 60,
        path="/",
    )


async def create_session(user: User, session: AsyncSession) -> str:
    settings = get_settings()
    token = create_session_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=settings.session_lifetime_hours),
        )
    )
    await session.commit()
    return token


@router.post("/register", response_model=AuthenticatedUser, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthenticatedUser:
    email = payload.email.lower()
    existing_user = await session.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()
    token = await create_session(user, session)
    set_session_cookie(response, token)
    return to_authenticated_user(user)


@router.post("/login", response_model=AuthenticatedUser)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthenticatedUser:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = await create_session(user, session)
    set_session_cookie(response, token)
    return to_authenticated_user(user)


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthenticatedUser:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_session = await session.scalar(
        select(UserSession)
        .options(selectinload(UserSession.user).selectinload(User.roles))
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    if user_session is None or not user_session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return to_authenticated_user(user_session.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token is not None:
        await session.execute(
            delete(UserSession).where(UserSession.token_hash == hash_session_token(token))
        )
        await session.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
