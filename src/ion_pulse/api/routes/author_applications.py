# ruff: noqa: E501
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.db.session import get_db_session
from ion_pulse.domain.author_applications import AuthorApplicationStatus
from ion_pulse.domain.roles import RoleCode
from ion_pulse.models.identity import AuthorApplication, Role, User, UserRole
from ion_pulse.schemas.author_applications import (
    AuthorApplicationCreate,
    AuthorApplicationDecision,
    AuthorApplicationRead,
)

router = APIRouter(prefix="/author-applications")


def to_response(application: AuthorApplication) -> AuthorApplicationRead:
    return AuthorApplicationRead.model_validate(application, from_attributes=True)


def require_administrator(user: User) -> None:
    if RoleCode.ADMINISTRATOR.value not in {role.code for role in user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")


@router.get("/me", response_model=AuthorApplicationRead | None)
async def get_my_application(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AuthorApplicationRead | None:
    application = await session.scalar(
        select(AuthorApplication)
        .where(AuthorApplication.user_id == user.id)
        .order_by(AuthorApplication.created_at.desc())
    )
    return None if application is None else to_response(application)


@router.post("", response_model=AuthorApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: AuthorApplicationCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AuthorApplicationRead:
    if RoleCode.AUTHOR.value in {role.code for role in user.roles}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already an author",
        )
    application = await session.scalar(
        select(AuthorApplication).where(
            AuthorApplication.user_id == user.id,
            AuthorApplication.status == AuthorApplicationStatus.SUBMITTED.value,
        )
    )
    if application is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application already submitted",
        )
    application = AuthorApplication(
        user_id=user.id,
        motivation=payload.motivation,
        portfolio_url=None if payload.portfolio_url is None else str(payload.portfolio_url),
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return to_response(application)


@router.get("", response_model=list[AuthorApplicationRead])
async def list_submitted_applications(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AuthorApplicationRead]:
    require_administrator(user)
    applications = (await session.scalars(select(AuthorApplication).where(AuthorApplication.status == AuthorApplicationStatus.SUBMITTED.value))).all()
    return [to_response(application) for application in applications]


@router.patch("/{application_id}", response_model=AuthorApplicationRead)
async def decide_application(
    application_id: str,
    payload: AuthorApplicationDecision,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> AuthorApplicationRead:
    require_administrator(user)
    application = await session.get(AuthorApplication, application_id)
    if application is None or application.status != AuthorApplicationStatus.SUBMITTED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submitted application not found")
    application.status = payload.status
    application.review_note = payload.review_note
    application.reviewed_at = datetime.now(UTC)
    application.reviewed_by_user_id = user.id
    if payload.status == AuthorApplicationStatus.APPROVED.value:
        role = await session.scalar(select(Role).where(Role.code == RoleCode.AUTHOR.value))
        if role is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Author role missing")
        existing = await session.get(UserRole, {"user_id": application.user_id, "role_id": role.id})
        if existing is None:
            session.add(UserRole(user_id=application.user_id, role_id=role.id))
    await session.commit()
    await session.refresh(application)
    return to_response(application)
