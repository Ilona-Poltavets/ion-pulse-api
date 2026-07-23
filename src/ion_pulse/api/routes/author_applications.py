from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.db.session import get_db_session
from ion_pulse.domain.author_applications import AuthorApplicationStatus
from ion_pulse.domain.roles import RoleCode
from ion_pulse.models.identity import AuthorApplication, User
from ion_pulse.schemas.author_applications import AuthorApplicationCreate, AuthorApplicationRead

router = APIRouter(prefix="/author-applications")


def to_response(application: AuthorApplication) -> AuthorApplicationRead:
    return AuthorApplicationRead.model_validate(application, from_attributes=True)


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
