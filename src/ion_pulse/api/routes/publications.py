from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.db.session import get_db_session
from ion_pulse.domain.publications import (
    EditorialDecision,
    PublicationStatus,
    resolve_editorial_decision,
)
from ion_pulse.domain.roles import RoleCode
from ion_pulse.models.identity import User
from ion_pulse.models.publications import (
    Category,
    DigestPublication,
    Game,
    Publication,
    PublicationAiReview,
    PublicationComment,
    PublicationEditorialReview,
    PublicationLocalization,
    PublicationRating,
    PublicationRevision,
    TranslationJob,
)
from ion_pulse.schemas.ai_reviews import PublicationAiReviewRead
from ion_pulse.schemas.publications import (
    DigestItemRead,
    DigestItemsUpdate,
    DraftCreate,
    DraftRead,
    DraftUpdate,
    EditorialActionCreate,
    EditorialDecisionCreate,
    JournalCandidateRead,
    LocalizationRead,
    LocalizationUpdate,
    PublicationRevisionRead,
    PublishedPublicationListItem,
    PublishedPublicationRead,
)

router = APIRouter(prefix="/publications")


def to_draft(
    publication: Publication, localization: PublicationLocalization, category: Category
) -> DraftRead:
    return DraftRead(
        id=publication.id,
        category_slug=category.slug,
        content_type=publication.content_type,
        game_id=publication.game_id,
        review_score=publication.review_score,
        source_locale=publication.source_locale,
        status=publication.status,
        scheduled_at=publication.scheduled_at,
        title=localization.title,
        summary=localization.summary,
        body=localization.body,
        created_at=publication.created_at,
    )


def to_revision(revision: PublicationRevision, category: Category) -> PublicationRevisionRead:
    return PublicationRevisionRead(
        revision_number=revision.revision_number,
        category_slug=category.slug,
        content_type=revision.content_type,
        game_id=revision.game_id,
        review_score=revision.review_score,
        title=revision.title,
        summary=revision.summary,
        body=revision.body,
        created_at=revision.created_at,
    )


def to_ai_review(review: PublicationAiReview) -> PublicationAiReviewRead:
    return PublicationAiReviewRead.model_validate(review, from_attributes=True)


def to_localization(localization: PublicationLocalization) -> LocalizationRead:
    return LocalizationRead.model_validate(localization, from_attributes=True)


def require_editorial_access(user: User) -> None:
    allowed_roles = {RoleCode.EDITOR.value, RoleCode.ADMINISTRATOR.value}
    if not allowed_roles.intersection(role.code for role in user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor role required")


def require_digest_access(user: User) -> None:
    allowed_roles = {RoleCode.EDITOR.value, RoleCode.MODERATOR.value, RoleCode.ADMINISTRATOR.value}
    if not allowed_roles.intersection(role.code for role in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor, moderator, or administrator role required for digests",
        )


def require_journal_access(user: User) -> None:
    if not {RoleCode.EDITOR.value, RoleCode.ADMINISTRATOR.value}.intersection(
        role.code for role in user.roles
    ):
        raise HTTPException(status_code=403, detail="Editor or administrator required")


def require_content_type_access(content_type: str, user: User) -> None:
    if content_type == "digest":
        require_digest_access(user)


async def validate_review_metadata(
    content_type: str, game_id: UUID | None, review_score: float | None, session: AsyncSession
) -> None:
    if content_type != "review" and (game_id is not None or review_score is not None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Game and review score are only allowed for reviews",
        )
    if game_id is not None and await session.get(Game, game_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown game")


def to_published(
    publication: Publication,
    localization: PublicationLocalization,
    category: Category,
    author: User,
    requested_locale: str,
) -> PublishedPublicationRead:
    if publication.published_at is None:
        raise ValueError("Published publication must have a published date")
    return PublishedPublicationRead(
        id=publication.id,
        author_id=publication.author_id,
        author_name=author.display_name,
        category_slug=category.slug,
        content_type=publication.content_type,
        game_id=publication.game_id,
        review_score=publication.review_score,
        source_locale=publication.source_locale,
        locale=localization.locale,
        translation_available=localization.locale == requested_locale,
        title=localization.title,
        summary=localization.summary,
        body=localization.body,
        published_at=publication.published_at,
    )


@router.get("/journal-candidates", response_model=list[JournalCandidateRead])
async def list_journal_candidates(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
    locale: str = "ru",
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> list[JournalCandidateRead]:
    require_journal_access(user)
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    now = datetime.now(UTC)
    try:
        week_start = (
            datetime.strptime(month, "%Y-%m").replace(tzinfo=UTC)
            if month
            else now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        )
        week_end = (week_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid month") from exc
    source = aliased(PublicationLocalization)
    requested = aliased(PublicationLocalization)
    rating = (
        select(
            PublicationRating.publication_id,
            func.avg(PublicationRating.value).label("average_rating"),
        )
        .group_by(PublicationRating.publication_id)
        .subquery()
    )
    comments = (
        select(
            PublicationComment.publication_id,
            func.count(PublicationComment.id).label("comment_count"),
        )
        .where(PublicationComment.is_hidden.is_(False))
        .group_by(PublicationComment.publication_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            Publication,
            Category,
            source,
            requested,
            rating.c.average_rating,
            comments.c.comment_count,
        )
        .join(Category, Category.id == Publication.category_id)
        .join(
            source,
            (source.publication_id == Publication.id)
            & (source.locale == Publication.source_locale),
        )
        .outerjoin(
            requested,
            (requested.publication_id == Publication.id)
            & (requested.locale == locale)
            & (requested.translation_status == "ready"),
        )
        .outerjoin(rating, rating.c.publication_id == Publication.id)
        .outerjoin(comments, comments.c.publication_id == Publication.id)
        .where(
            Publication.status == PublicationStatus.PUBLISHED.value,
            Publication.published_at >= week_start,
            Publication.published_at < week_end,
            Publication.content_type != "digest",
        )
        .order_by(
            (
                func.coalesce(rating.c.average_rating, 0)
                + func.coalesce(comments.c.comment_count, 0) * 0.1
            ).desc()
        )
    )
    return [
        JournalCandidateRead(
            id=publication.id,
            category_slug=category.slug,
            title=(localized or original).title,
            summary=(localized or original).summary,
            body=(localized or original).body,
            view_count=publication.view_count,
            published_at=publication.published_at,
            average_rating=float(average_rating or 0),
            comment_count=int(comment_count or 0),
            score=float(average_rating or 0)
            + int(comment_count or 0) * 2
            + publication.view_count * 0.01,
        )
        for publication, category, original, localized, average_rating, comment_count in rows
        if publication.published_at is not None
    ]


@router.get("/feed", response_model=list[PublishedPublicationListItem])
async def list_published_publications(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    locale: str = "ru",
    category_slug: str | None = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PublishedPublicationListItem]:
    """Return the newest published materials in the requested locale.

    A material whose translation is not ready remains visible in its original
    language, matching the behaviour of the individual publication endpoint.
    """
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )

    source_localization = aliased(PublicationLocalization)
    requested_localization = aliased(PublicationLocalization)
    statement = (
        select(Publication, Category, User, source_localization, requested_localization)
        .join(Category, Category.id == Publication.category_id)
        .join(User, User.id == Publication.author_id)
        .join(
            source_localization,
            (source_localization.publication_id == Publication.id)
            & (source_localization.locale == Publication.source_locale),
        )
        .outerjoin(
            requested_localization,
            (requested_localization.publication_id == Publication.id)
            & (requested_localization.locale == locale)
            & (requested_localization.translation_status == "ready"),
        )
        .where(Publication.status == PublicationStatus.PUBLISHED.value)
        .order_by(Publication.published_at.desc())
    )
    if category_slug is not None:
        statement = statement.where(Category.slug == category_slug)
    if search and (search_term := search.strip()):
        pattern = f"%{search_term}%"
        statement = statement.where(
            or_(
                source_localization.title.ilike(pattern),
                source_localization.summary.ilike(pattern),
                requested_localization.title.ilike(pattern),
                requested_localization.summary.ilike(pattern),
            )
        )
    rows = await session.execute(statement.offset(offset).limit(limit))
    result: list[PublishedPublicationListItem] = []
    for publication, category, author, source, requested in rows:
        localized = requested or source
        if publication.published_at is None:
            continue
        result.append(
            PublishedPublicationListItem(
                id=publication.id,
                category_slug=category.slug,
                content_type=publication.content_type,
                game_id=publication.game_id,
                review_score=publication.review_score,
                source_locale=publication.source_locale,
                locale=localized.locale,
                translation_available=localized.locale == locale,
                title=localized.title,
                summary=localized.summary,
                author_name=author.display_name,
                published_at=publication.published_at,
            )
        )
    return result


@router.post("/drafts", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: DraftCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    require_content_type_access(payload.content_type, user)
    category = await session.scalar(select(Category).where(Category.slug == payload.category_slug))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")
    await validate_review_metadata(
        payload.content_type, payload.game_id, payload.review_score, session
    )
    publication = Publication(
        author_id=user.id,
        category_id=category.id,
        game_id=payload.game_id,
        content_type=payload.content_type,
        review_score=payload.review_score,
        source_locale=payload.source_locale,
    )
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
    session.add(
        PublicationRevision(
            publication_id=publication.id,
            author_id=user.id,
            category_id=category.id,
            game_id=payload.game_id,
            content_type=payload.content_type,
            review_score=payload.review_score,
            revision_number=1,
            title=payload.title,
            summary=payload.summary,
            body=payload.body,
        )
    )
    await session.commit()
    await session.refresh(publication)
    await session.refresh(localization)
    return to_draft(publication, localization, category)


async def read_digest_items(
    digest_id: UUID, session: AsyncSession, locale: str
) -> list[DigestItemRead]:
    source_localization = aliased(PublicationLocalization)
    requested_localization = aliased(PublicationLocalization)
    rows = await session.execute(
        select(DigestPublication, Category, source_localization, requested_localization)
        .join(Publication, Publication.id == DigestPublication.publication_id)
        .join(Category, Category.id == Publication.category_id)
        .join(
            source_localization,
            (source_localization.publication_id == Publication.id)
            & (source_localization.locale == Publication.source_locale),
        )
        .outerjoin(
            requested_localization,
            (requested_localization.publication_id == Publication.id)
            & (requested_localization.locale == locale)
            & (requested_localization.translation_status == "ready"),
        )
        .where(DigestPublication.digest_id == digest_id)
        .order_by(DigestPublication.position)
    )
    return [
        DigestItemRead(
            id=item.publication_id,
            category_slug=category.slug,
            title=(localized or source).title,
            summary=(localized or source).summary,
        )
        for item, category, source, localized in rows
    ]


@router.put("/{publication_id}/digest-items", response_model=list[DigestItemRead])
async def replace_digest_items(
    publication_id: str,
    payload: DigestItemsUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DigestItemRead]:
    require_digest_access(user)
    digest = await session.get(Publication, publication_id)
    if (
        digest is None
        or digest.author_id != user.id
        or digest.content_type != "digest"
        or digest.status
        not in {PublicationStatus.DRAFT.value, PublicationStatus.CHANGES_REQUESTED.value}
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Editable digest not found"
        )
    if len(set(payload.publication_ids)) != len(payload.publication_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Digest publications must be unique",
        )
    selected = (
        await session.scalars(
            select(Publication).where(
                Publication.id.in_(payload.publication_ids),
                Publication.status == PublicationStatus.PUBLISHED.value,
                Publication.content_type != "digest",
            )
        )
    ).all()
    if len(selected) != len(payload.publication_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digest items must be published non-digest materials",
        )
    await session.execute(delete(DigestPublication).where(DigestPublication.digest_id == digest.id))
    session.add_all(
        [
            DigestPublication(digest_id=digest.id, publication_id=item_id, position=position)
            for position, item_id in enumerate(payload.publication_ids, start=1)
        ]
    )
    await session.commit()
    return await read_digest_items(digest.id, session, "ru")


@router.get("/{publication_id}/digest-items", response_model=list[DigestItemRead])
async def list_editable_digest_items(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DigestItemRead]:
    require_digest_access(user)
    digest = await session.scalar(
        select(Publication).where(
            Publication.id == publication_id,
            Publication.author_id == user.id,
            Publication.content_type == "digest",
        )
    )
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found")
    return await read_digest_items(digest.id, session, "ru")


@router.get("/published/{publication_id}/digest-items", response_model=list[DigestItemRead])
async def list_digest_items(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    locale: str = "ru",
) -> list[DigestItemRead]:
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    digest = await session.scalar(
        select(Publication).where(
            Publication.id == publication_id,
            Publication.status == PublicationStatus.PUBLISHED.value,
            Publication.content_type == "digest",
        )
    )
    if digest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Published digest not found"
        )
    return await read_digest_items(digest.id, session, locale)


@router.get("/mine", response_model=list[DraftRead])
async def list_my_publications(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DraftRead]:
    rows = await session.execute(
        select(Publication, PublicationLocalization, Category, User)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .join(User, User.id == Publication.author_id)
        .where(
            Publication.author_id == user.id,
            PublicationLocalization.locale == Publication.source_locale,
        )
        .order_by(Publication.updated_at.desc())
    )
    return [
        to_draft(publication, localization, category)
        for publication, localization, category in rows
    ]


@router.get("/{publication_id}/revisions", response_model=list[PublicationRevisionRead])
async def list_publication_revisions(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[PublicationRevisionRead]:
    rows = await session.execute(
        select(PublicationRevision, Category)
        .join(Category, Category.id == PublicationRevision.category_id)
        .join(Publication, Publication.id == PublicationRevision.publication_id)
        .where(
            PublicationRevision.publication_id == publication_id, Publication.author_id == user.id
        )
        .order_by(PublicationRevision.revision_number.desc())
    )
    return [to_revision(revision, category) for revision, category in rows]


@router.get("/{publication_id}/ai-review", response_model=PublicationAiReviewRead | None)
async def get_publication_ai_review(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> PublicationAiReviewRead | None:
    publication = await session.get(Publication, publication_id)
    if publication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    editorial_roles = {RoleCode.EDITOR.value, RoleCode.ADMINISTRATOR.value}
    if publication.author_id != user.id and not editorial_roles.intersection(
        role.code for role in user.roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Publication access required"
        )
    review = await session.scalar(
        select(PublicationAiReview)
        .where(PublicationAiReview.publication_id == publication.id)
        .order_by(PublicationAiReview.source_revision.desc())
    )
    return None if review is None else to_ai_review(review)


@router.get("/{publication_id}/localizations/{locale}", response_model=LocalizationRead)
async def get_localization_for_editor(
    publication_id: str,
    locale: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> LocalizationRead:
    require_editorial_access(user)
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    localization = await session.scalar(
        select(PublicationLocalization).where(
            PublicationLocalization.publication_id == publication_id,
            PublicationLocalization.locale == locale,
        )
    )
    if localization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Localization not found")
    return to_localization(localization)


@router.patch("/{publication_id}/localizations/{locale}", response_model=LocalizationRead)
async def update_localization_by_editor(
    publication_id: str,
    locale: str,
    payload: LocalizationUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> LocalizationRead:
    require_editorial_access(user)
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    publication = await session.get(Publication, publication_id)
    if publication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    if locale == publication.source_locale:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Edit the original through the publication workflow",
        )
    localization = await session.scalar(
        select(PublicationLocalization)
        .where(
            PublicationLocalization.publication_id == publication.id,
            PublicationLocalization.locale == locale,
        )
        .with_for_update()
    )
    if localization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Localization not found")
    localization.title = payload.title
    localization.summary = payload.summary
    localization.body = payload.body
    localization.origin = "human"
    localization.translation_status = "ready"
    await session.commit()
    await session.refresh(localization)
    return to_localization(localization)


@router.get("/published/{publication_id}", response_model=PublishedPublicationRead)
async def get_published_publication(
    publication_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    locale: str = "ru",
) -> PublishedPublicationRead:
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    row = await session.execute(
        select(Publication, PublicationLocalization, Category, User)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .join(User, User.id == Publication.author_id)
        .where(
            Publication.id == publication_id,
            Publication.status == PublicationStatus.PUBLISHED.value,
            PublicationLocalization.locale == locale,
            PublicationLocalization.translation_status == "ready",
        )
    )
    result = row.one_or_none()
    if result is None:
        row = await session.execute(
            select(Publication, PublicationLocalization, Category, User)
            .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
            .join(Category, Category.id == Publication.category_id)
            .join(User, User.id == Publication.author_id)
            .where(
                Publication.id == publication_id,
                Publication.status == PublicationStatus.PUBLISHED.value,
                PublicationLocalization.locale == Publication.source_locale,
            )
        )
        result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Published publication not found"
        )
    publication, localization, category, author = result
    await session.execute(
        update(Publication)
        .where(Publication.id == publication.id)
        .values(view_count=Publication.view_count + 1)
    )
    await session.commit()
    return to_published(publication, localization, category, author, locale)


@router.patch("/{publication_id}/draft", response_model=DraftRead)
async def update_draft(
    publication_id: str,
    payload: DraftUpdate,
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
            Publication.status.in_(
                [PublicationStatus.DRAFT.value, PublicationStatus.CHANGES_REQUESTED.value]
            ),
            PublicationLocalization.locale == Publication.source_locale,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Editable draft not found"
        )
    publication, localization, _ = result
    category = await session.scalar(select(Category).where(Category.slug == payload.category_slug))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")
    require_content_type_access(payload.content_type, user)
    await validate_review_metadata(
        payload.content_type, payload.game_id, payload.review_score, session
    )
    publication.category_id = category.id
    publication.game_id = payload.game_id
    publication.content_type = payload.content_type
    publication.review_score = payload.review_score
    localization.title = payload.title
    localization.summary = payload.summary
    localization.body = payload.body
    localization.source_revision += 1
    session.add(
        PublicationRevision(
            publication_id=publication.id,
            author_id=user.id,
            category_id=category.id,
            game_id=payload.game_id,
            content_type=payload.content_type,
            review_score=payload.review_score,
            revision_number=localization.source_revision,
            title=payload.title,
            summary=payload.summary,
            body=payload.body,
        )
    )
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)


@router.post("/{publication_id}/revisions/{revision_number}/restore", response_model=DraftRead)
async def restore_publication_revision(
    publication_id: str,
    revision_number: int,
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
            Publication.status.in_(
                [PublicationStatus.DRAFT.value, PublicationStatus.CHANGES_REQUESTED.value]
            ),
            PublicationLocalization.locale == Publication.source_locale,
        )
        .with_for_update(of=Publication)
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Editable draft not found"
        )
    publication, localization, _ = result
    revision = await session.scalar(
        select(PublicationRevision).where(
            PublicationRevision.publication_id == publication.id,
            PublicationRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    category = await session.get(Category, revision.category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Revision category not found"
        )
    publication.category_id = category.id
    publication.game_id = revision.game_id
    publication.content_type = revision.content_type
    publication.review_score = revision.review_score
    localization.title = revision.title
    localization.summary = revision.summary
    localization.body = revision.body
    localization.source_revision += 1
    session.add(
        PublicationRevision(
            publication_id=publication.id,
            author_id=user.id,
            category_id=category.id,
            game_id=revision.game_id,
            content_type=revision.content_type,
            review_score=revision.review_score,
            revision_number=localization.source_revision,
            title=revision.title,
            summary=revision.summary,
            body=revision.body,
        )
    )
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)


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
            Publication.status.in_(
                [PublicationStatus.DRAFT.value, PublicationStatus.CHANGES_REQUESTED.value]
            ),
            PublicationLocalization.locale == Publication.source_locale,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    publication, localization, category = result
    require_content_type_access(publication.content_type, user)
    if publication.content_type == "digest":
        has_items = await session.scalar(
            select(DigestPublication.digest_id)
            .where(DigestPublication.digest_id == publication.id)
            .limit(1)
        )
        if has_items is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A digest must contain at least one published material",
            )
    previous_status = publication.status
    publication.status = PublicationStatus.EDITORIAL_REVIEW.value
    session.add(
        PublicationAiReview(
            publication_id=publication.id,
            source_revision=localization.source_revision,
        )
    )
    session.add(
        PublicationEditorialReview(
            publication_id=publication.id,
            reviewer_id=user.id,
            decision="submit",
            from_status=previous_status,
            to_status=publication.status,
            note="Submitted for editorial review",
        )
    )
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)


@router.get("/editorial-queue", response_model=list[DraftRead])
async def list_editorial_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DraftRead]:
    require_editorial_access(user)
    rows = await session.execute(
        select(Publication, PublicationLocalization, Category)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .where(
            Publication.status == PublicationStatus.EDITORIAL_REVIEW.value,
            PublicationLocalization.locale == Publication.source_locale,
        )
        .order_by(Publication.created_at.asc())
    )
    return [
        to_draft(publication, localization, category)
        for publication, localization, category in rows
    ]


@router.post("/{publication_id}/editorial-decision", response_model=DraftRead)
async def make_editorial_decision(
    publication_id: str,
    payload: EditorialDecisionCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    require_editorial_access(user)
    decision = EditorialDecision(payload.decision)
    if decision is EditorialDecision.SCHEDULE and payload.scheduled_at is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Scheduled publication time is required",
        )
    if payload.scheduled_at is not None and payload.scheduled_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Scheduled publication time must be in the future",
        )
    row = await session.execute(
        select(Publication, PublicationLocalization, Category)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .where(
            Publication.id == publication_id,
            Publication.status == PublicationStatus.EDITORIAL_REVIEW.value,
            PublicationLocalization.locale == Publication.source_locale,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Publication awaiting review not found"
        )

    publication, localization, category = result
    previous_status = publication.status
    publication.status = resolve_editorial_decision(decision).value
    publication.scheduled_at = (
        payload.scheduled_at if decision is EditorialDecision.SCHEDULE else None
    )
    if publication.status == PublicationStatus.PUBLISHED.value:
        publication.published_at = datetime.now(UTC)
        session.add(
            TranslationJob(
                publication_id=publication.id,
                target_locale="en" if publication.source_locale == "ru" else "ru",
            )
        )
    session.add(
        PublicationEditorialReview(
            publication_id=publication.id,
            reviewer_id=user.id,
            decision=decision.value,
            from_status=previous_status,
            to_status=publication.status,
            note=payload.note,
        )
    )
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)


async def change_archive_status(
    publication_id: str,
    payload: EditorialActionCreate,
    session: AsyncSession,
    user: User,
    *,
    from_status: PublicationStatus,
    to_status: PublicationStatus,
    decision: str,
) -> DraftRead:
    require_editorial_access(user)
    row = await session.execute(
        select(Publication, PublicationLocalization, Category)
        .join(PublicationLocalization, PublicationLocalization.publication_id == Publication.id)
        .join(Category, Category.id == Publication.category_id)
        .where(
            Publication.id == publication_id,
            Publication.status == from_status.value,
            PublicationLocalization.locale == Publication.source_locale,
        )
        .with_for_update(of=Publication)
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    publication, localization, category = result
    publication.status = to_status.value
    session.add(
        PublicationEditorialReview(
            publication_id=publication.id,
            reviewer_id=user.id,
            decision=decision,
            from_status=from_status.value,
            to_status=to_status.value,
            note=payload.note,
        )
    )
    await session.commit()
    await session.refresh(publication)
    return to_draft(publication, localization, category)


@router.post("/{publication_id}/archive", response_model=DraftRead)
async def archive_publication(
    publication_id: str,
    payload: EditorialActionCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    return await change_archive_status(
        publication_id,
        payload,
        session,
        user,
        from_status=PublicationStatus.PUBLISHED,
        to_status=PublicationStatus.ARCHIVED,
        decision="archive",
    )


@router.post("/{publication_id}/unarchive", response_model=DraftRead)
async def unarchive_publication(
    publication_id: str,
    payload: EditorialActionCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DraftRead:
    return await change_archive_status(
        publication_id,
        payload,
        session,
        user,
        from_status=PublicationStatus.ARCHIVED,
        to_status=PublicationStatus.PUBLISHED,
        decision="unarchive",
    )
