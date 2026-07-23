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


def to_draft(publication: Publication, localization: PublicationLocalization, category: Category) -> DraftRead:
    return DraftRead(
        id=publication.id,
        category_slug=category.slug,
        source_locale=publication.source_locale,
        status=publication.status,
        title=localization.title,
        summary=localization.summary,
        body=localization.body,
        created_at=publication.created_at,
    )


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
    return to_draft(publication, localization, category)


@router.get("/mine", response_model=list[DraftRead])
async def list_my_publications(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DraftRead]:
    rows = await session.execute(
        select(Publication, PublicationLocalization, Category)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .where(
            Publication.author_id == user.id,
            PublicationLocalization.locale == Publication.source_locale,
        )
        .order_by(Publication.updated_at.desc())
    )
    return [to_draft(publication, localization, category) for publication, localization, category in rows]


@router.post("/{publication_id}/submit", response_model=DraftRead)
async def submit_draft(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    row = await session.execute(
        select(Publication, PublicationLocalization, Category)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .where(
            Publication.id == publication_id,
            Publication.author_id == user.id,
            Publication.status == "draft",
            PublicationLocalization.locale == Publication.source_locale,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    publication, localization, category = result
    publication.status = "submitted"
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)
