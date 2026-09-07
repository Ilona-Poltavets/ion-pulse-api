from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.db.session import get_db_session
from ion_pulse.domain.publications import PublicationStatus
from ion_pulse.domain.roles import RoleCode
from ion_pulse.models.identity import User
from ion_pulse.models.publications import (
    Category,
    JournalIssue,
    JournalIssuePublication,
    Publication,
    PublicationLocalization,
)
from ion_pulse.schemas.publications import (
    DigestItemRead,
    JournalCandidateRead,
    JournalIssueCreate,
    JournalIssuePublicationsUpdate,
    JournalIssueRead,
    JournalPage,
)

router = APIRouter(prefix="/journal")


def require_journal_access(user: User) -> None:
    roles = {RoleCode.EDITOR.value, RoleCode.ADMINISTRATOR.value}
    if not roles.intersection(role.code for role in user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Journal role required")


def to_issue(issue: JournalIssue) -> JournalIssueRead:
    return JournalIssueRead.model_validate(issue, from_attributes=True)


@router.get("/issues", response_model=list[JournalIssueRead])
async def list_published_issues(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[JournalIssueRead]:
    issues = (
        await session.scalars(
            select(JournalIssue)
            .where(JournalIssue.status == "published")
            .order_by(JournalIssue.published_at.desc())
        )
    ).all()
    return [to_issue(issue) for issue in issues]


@router.get("/issues/{issue_id}/publications", response_model=list[DigestItemRead])
async def list_issue_publications(
    issue_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    locale: str = "ru",
) -> list[DigestItemRead]:
    if locale not in {"ru", "en"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported locale"
        )
    issue = await session.get(JournalIssue, issue_id)
    if issue is None or issue.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Published issue not found"
        )
    materials = (
        await session.scalars(
            select(JournalIssuePublication)
            .where(JournalIssuePublication.issue_id == issue.id)
            .order_by(JournalIssuePublication.position)
        )
    ).all()
    if materials and all(material.snapshot is not None for material in materials):
        result: list[DigestItemRead] = []
        for material in materials:
            snapshot = material.snapshot
            if snapshot is None:
                continue
            localizations = snapshot.get("localizations")
            source_locale = snapshot.get("source_locale")
            category_slug = snapshot.get("category_slug")
            if (
                not isinstance(localizations, dict)
                or not isinstance(source_locale, str)
                or not isinstance(category_slug, str)
            ):
                break
            localized = localizations.get(locale) or localizations.get(source_locale)
            if not isinstance(localized, dict):
                break
            title = localized.get("title")
            summary = localized.get("summary")
            if not isinstance(title, str) or not isinstance(summary, str):
                break
            result.append(
                DigestItemRead(
                    id=material.publication_id,
                    category_slug=category_slug,
                    title=title,
                    summary=summary,
                )
            )
        if len(result) == len(materials):
            return result
    source = aliased(PublicationLocalization)
    requested = aliased(PublicationLocalization)
    rows = await session.execute(
        select(JournalIssuePublication, Publication, Category, source, requested)
        .join(Publication, Publication.id == JournalIssuePublication.publication_id)
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
        .where(JournalIssuePublication.issue_id == issue.id)
        .order_by(JournalIssuePublication.position)
    )
    return [
        DigestItemRead(
            id=publication.id,
            category_slug=category.slug,
            title=(localized or original).title,
            summary=(localized or original).summary,
        )
        for _, publication, category, original, localized in rows
    ]


def can_manage_issue(issue: JournalIssue, user: User) -> bool:
    return issue.editor_id == user.id or RoleCode.ADMINISTRATOR.value in {
        role.code for role in user.roles
    }


@router.post("/issues", response_model=JournalIssueRead, status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: JournalIssueCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalIssueRead:
    require_journal_access(user)
    issue = JournalIssue(
        editor_id=user.id,
        **payload.model_dump(mode="python", exclude={"pages"}),
        pages=[page.model_dump(mode="json") for page in payload.pages],
    )
    session.add(issue)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="An issue for this period already exists"
        ) from exc
    await session.refresh(issue)
    return to_issue(issue)


@router.put("/issues/{issue_id}/publications", status_code=status.HTTP_204_NO_CONTENT)
async def replace_issue_publications(
    issue_id: UUID,
    payload: JournalIssuePublicationsUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    require_journal_access(user)
    issue = await session.get(JournalIssue, issue_id, with_for_update=True)
    if issue is None or not can_manage_issue(issue, user) or issue.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Editable issue not found"
        )
    if len(set(payload.publication_ids)) != len(payload.publication_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Items must be unique"
        )
    found = (
        await session.scalars(
            select(Publication.id).where(
                Publication.id.in_(payload.publication_ids),
                Publication.status == PublicationStatus.PUBLISHED.value,
            )
        )
    ).all()
    if len(found) != len(payload.publication_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Items must be published"
        )
    issue.pages = []
    await session.execute(
        delete(JournalIssuePublication).where(JournalIssuePublication.issue_id == issue.id)
    )
    session.add_all(
        [
            JournalIssuePublication(issue_id=issue.id, publication_id=item, position=index)
            for index, item in enumerate(payload.publication_ids, 1)
        ]
    )
    await session.commit()


@router.post("/issues/{issue_id}/publish", response_model=JournalIssueRead)
async def publish_issue(
    issue_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalIssueRead:
    require_journal_access(user)
    issue = await session.get(JournalIssue, issue_id, with_for_update=True)
    if issue is None or not can_manage_issue(issue, user) or issue.status != "draft":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft issue not found")
    if (
        await session.scalar(
            select(JournalIssuePublication.issue_id)
            .where(JournalIssuePublication.issue_id == issue.id)
            .limit(1)
        )
        is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Issue must contain publications",
        )
    materials = (
        await session.scalars(
            select(JournalIssuePublication)
            .where(JournalIssuePublication.issue_id == issue.id)
            .order_by(JournalIssuePublication.position)
        )
    ).all()
    if issue.pages:
        layout_ids = {
            str(item)
            for page in issue.pages
            for item in JournalPage.model_validate(page).publication_ids
        }
        if layout_ids != {str(material.publication_id) for material in materials}:
            raise HTTPException(status_code=422, detail="Save the layout before publishing")
    from ion_pulse.api.routes.publications import list_journal_candidates

    candidates = await list_journal_candidates(
        session, user, "ru", issue.period_start.strftime("%Y-%m")
    )
    scores = {item.id: item for item in candidates}
    for material in materials:
        publication = await session.get(Publication, material.publication_id)
        if publication is None or publication.status != "published":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Material missing")
        category = await session.get(Category, publication.category_id)
        localizations = (
            await session.scalars(
                select(PublicationLocalization).where(
                    PublicationLocalization.publication_id == publication.id,
                    PublicationLocalization.translation_status == "ready",
                )
            )
        ).all()
        candidate = scores.get(material.publication_id)
        material.snapshot = {
            "view_count": publication.view_count,
            "comment_count": candidate.comment_count if candidate else 0,
            "score": candidate.score if candidate else 0,
            "category_slug": category.slug if category is not None else "uncategorized",
            "source_locale": publication.source_locale,
            "localizations": {
                localization.locale: {
                    "title": localization.title,
                    "summary": localization.summary,
                    "body": localization.body,
                }
                for localization in localizations
            },
        }
    issue.status = "published"
    issue.published_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(issue)
    return to_issue(issue)


@router.get("/drafts", response_model=list[JournalIssueRead])
async def list_drafts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[JournalIssueRead]:
    require_journal_access(user)
    issues = (
        await session.scalars(
            select(JournalIssue)
            .where(JournalIssue.status == "draft")
            .order_by(JournalIssue.created_at.desc())
        )
    ).all()
    return [to_issue(issue) for issue in issues if can_manage_issue(issue, user)]


@router.put("/issues/{issue_id}", response_model=JournalIssueRead)
async def save_issue(
    issue_id: UUID,
    payload: JournalIssueCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> JournalIssueRead:
    require_journal_access(user)
    issue = await session.get(JournalIssue, issue_id, with_for_update=True)
    if issue is None or issue.status != "draft" or not can_manage_issue(issue, user):
        raise HTTPException(status_code=404, detail="Editable issue not found")
    ids = list(dict.fromkeys(item for page in payload.pages for item in page.publication_ids))
    found = (
        await session.scalars(
            select(Publication.id).where(
                Publication.id.in_(ids),
                Publication.status == "published",
                Publication.published_at >= payload.period_start,
                Publication.published_at < payload.period_end,
            )
        )
    ).all()
    if set(found) != set(ids):
        raise HTTPException(
            status_code=422, detail="Select published articles from the issue month"
        )
    issue.title = payload.title
    issue.period_start = payload.period_start
    issue.period_end = payload.period_end
    issue.pages = [page.model_dump(mode="json") for page in payload.pages]
    await session.execute(
        delete(JournalIssuePublication).where(JournalIssuePublication.issue_id == issue.id)
    )
    session.add_all(
        [
            JournalIssuePublication(issue_id=issue.id, publication_id=item, position=index)
            for index, item in enumerate(ids, 1)
        ]
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="An issue for this period already exists"
        ) from exc
    await session.refresh(issue)
    return to_issue(issue)


@router.get("/issues/{issue_id}/materials", response_model=list[JournalCandidateRead])
async def issue_materials(
    issue_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    locale: str = "ru",
) -> list[JournalCandidateRead]:
    if locale not in {"ru", "en"}:
        raise HTTPException(status_code=422, detail="Unsupported locale")
    issue = await session.get(JournalIssue, issue_id)
    if issue is None or issue.status != "published":
        raise HTTPException(status_code=404, detail="Published issue not found")
    materials = (
        await session.scalars(
            select(JournalIssuePublication)
            .where(JournalIssuePublication.issue_id == issue.id)
            .order_by(JournalIssuePublication.position)
        )
    ).all()
    if any(material.snapshot is None for material in materials):
        legacy = await list_issue_publications(issue_id, session, locale)
        return [
            JournalCandidateRead(
                **item.model_dump(),
                published_at=issue.published_at or issue.period_end,
                average_rating=0,
                comment_count=0,
                score=0,
            )
            for item in legacy
        ]
    result = []
    for material in materials:
        snapshot = material.snapshot or {}
        localized = snapshot.get("localizations", {})
        if not isinstance(localized, dict):
            localized = {}
        content = localized.get(locale) or localized.get(str(snapshot.get("source_locale"))) or {}
        if not isinstance(content, dict):
            content = {}
        result.append(
            JournalCandidateRead(
                id=material.publication_id,
                category_slug=snapshot.get("category_slug", ""),
                title=content.get("title", ""),
                summary=content.get("summary", ""),
                body=content.get("body", ""),
                published_at=issue.published_at,
                view_count=snapshot.get("view_count", 0),
                comment_count=snapshot.get("comment_count", 0),
                average_rating=0,
                score=snapshot.get("score", 0),
            )
        )
    return result
