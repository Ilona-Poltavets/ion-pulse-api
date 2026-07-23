# ruff: noqa: E501
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.db.session import get_db_session
from ion_pulse.models.identity import User
from ion_pulse.models.publications import Category, Publication, PublicationLocalization
from ion_pulse.schemas.publications import DraftCreate, DraftRead

router = APIRouter(prefix="/publications")


@router.post("/drafts", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: DraftCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    category = await session.scalar(select(Category).where(Category.slug == payload.category_slug))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")
    publication = Publication(author_id=user.id, category_id=category.id, source_locale=payload.source_locale)
    session.add(publication)
    await session.flush()
    localization = PublicationLocalization(
        publication_id=publication.id,
        locale=payload.source_locale,
        title=payload.title,
        summary=payload.summary,
        body=payload.body,
    )
    session.add(localization)
    await session.commit()
    await session.refresh(publication)
    await session.refresh(localization)
    return DraftRead(id=publication.id, category_slug=category.slug, source_locale=publication.source_locale, status=publication.status, title=localization.title, summary=localization.summary, body=localization.body, created_at=publication.created_at)
