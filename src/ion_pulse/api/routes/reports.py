from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ion_pulse.api.routes.auth import get_current_user
from ion_pulse.api.routes.comments import require_moderation_access
from ion_pulse.db.session import get_db_session
from ion_pulse.domain.publications import PublicationStatus
from ion_pulse.models.identity import User
from ion_pulse.models.publications import (
    ContentReport,
    Publication,
    PublicationComment,
    PublicationLocalization,
)
from ion_pulse.schemas.reports import ContentReportRead, ReportCreate, ReportReview
from ion_pulse.services.rate_limits import enforce_rate_limit

router = APIRouter()


async def to_report(report: ContentReport, session: AsyncSession) -> ContentReportRead:
    target_author_id = None
    target_excerpt = None
    if report.target_type == "publication":
        publication = await session.get(Publication, report.target_id)
        if publication is not None:
            target_author_id = publication.author_id
            localization = await session.scalar(
                select(PublicationLocalization).where(
                    PublicationLocalization.publication_id == publication.id,
                    PublicationLocalization.locale == publication.source_locale,
                )
            )
            if localization is not None:
                target_excerpt = localization.title
    else:
        comment = await session.get(PublicationComment, report.target_id)
        if comment is not None:
            target_author_id = comment.author_id
            target_excerpt = comment.body[:240]
    return ContentReportRead(
        **ContentReportRead.model_validate(report, from_attributes=True).model_dump(
            exclude={"target_author_id", "target_excerpt"}
        ),
        target_author_id=target_author_id,
        target_excerpt=target_excerpt,
    )


async def create_report(
    *,
    target_type: str,
    target_id: str,
    payload: ReportCreate,
    session: AsyncSession,
    user: User,
) -> ContentReportRead:
    if target_type == "publication":
        publication = await session.get(Publication, target_id)
        if publication is None or publication.status != PublicationStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Published publication not found"
            )
    else:
        comment = await session.get(PublicationComment, target_id)
        if comment is None or comment.is_hidden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Visible comment not found"
            )
    existing = await session.scalar(
        select(ContentReport).where(
            ContentReport.reporter_id == user.id,
            ContentReport.target_type == target_type,
            ContentReport.target_id == target_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report already submitted")
    report = ContentReport(
        reporter_id=user.id,
        target_type=target_type,
        target_id=target_id,
        reason=payload.reason,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return await to_report(report, session)


@router.post(
    "/publications/{publication_id}/reports",
    response_model=ContentReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def report_publication(
    publication_id: str,
    payload: ReportCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ContentReportRead:
    enforce_rate_limit("report", str(user.id), limit=10, window_seconds=3600)
    return await create_report(
        target_type="publication",
        target_id=publication_id,
        payload=payload,
        session=session,
        user=user,
    )


@router.post(
    "/comments/{comment_id}/reports",
    response_model=ContentReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def report_comment(
    comment_id: str,
    payload: ReportCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ContentReportRead:
    enforce_rate_limit("report", str(user.id), limit=10, window_seconds=3600)
    return await create_report(
        target_type="comment",
        target_id=comment_id,
        payload=payload,
        session=session,
        user=user,
    )


@router.get("/reports", response_model=list[ContentReportRead])
async def list_open_reports(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ContentReportRead]:
    require_moderation_access(user)
    reports = (
        await session.scalars(
            select(ContentReport)
            .where(ContentReport.status == "open")
            .order_by(ContentReport.created_at)
        )
    ).all()
    return [await to_report(report, session) for report in reports]


@router.patch("/reports/{report_id}", response_model=ContentReportRead)
async def review_report(
    report_id: str,
    payload: ReportReview,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ContentReportRead:
    require_moderation_access(user)
    report = await session.get(ContentReport, report_id)
    if report is None or report.status != "open":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Open report not found")
    report.status = payload.status
    report.review_note = payload.review_note
    report.reviewed_by_user_id = user.id
    report.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(report)
    return await to_report(report, session)
