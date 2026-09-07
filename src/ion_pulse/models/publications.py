from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ion_pulse.db.base import Base


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_ru: Mapped[str] = mapped_column(String(120), server_default="")
    name_en: Mapped[str] = mapped_column(String(120), server_default="")
    description_ru: Mapped[str] = mapped_column(String(500), server_default="")
    description_en: Mapped[str] = mapped_column(String(500), server_default="")
    color: Mapped[str] = mapped_column(String(7), server_default="#C7FF5E")
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    is_visible: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Game(Base):
    __tablename__ = "games"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSubscription(Base):
    __tablename__ = "game_subscriptions"

    subscriber_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    game_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    game_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("games.id", ondelete="SET NULL"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(20), server_default="article")
    view_count: Mapped[int] = mapped_column(default=0, server_default="0")
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_locale: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(30), server_default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublicationLocalization(Base):
    __tablename__ = "publication_localizations"
    __table_args__ = (UniqueConstraint("publication_id", "locale"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    locale: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    media_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    media_value: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), server_default="original")
    translation_status: Mapped[str] = mapped_column(String(20), server_default="ready")
    source_revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicationRevision(Base):
    __tablename__ = "publication_revisions"
    __table_args__ = (UniqueConstraint("publication_id", "revision_number"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        index=True,
    )
    author_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    game_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("games.id", ondelete="SET NULL"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(20), server_default="article")
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    revision_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DigestPublication(Base):
    __tablename__ = "digest_publications"
    __table_args__ = (
        UniqueConstraint("digest_id", "publication_id"),
        UniqueConstraint("digest_id", "position"),
    )

    digest_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column()


class JournalIssue(Base):
    __tablename__ = "journal_issues"
    __table_args__ = (UniqueConstraint("period_start", "period_end"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    editor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(240))
    pages: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JournalIssuePublication(Base):
    __tablename__ = "journal_issue_publications"
    __table_args__ = (
        UniqueConstraint("issue_id", "publication_id"),
        UniqueConstraint("issue_id", "position"),
    )

    issue_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("journal_issues.id", ondelete="CASCADE"),
        primary_key=True,
    )
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column()
    snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class PublicationAiReview(Base):
    __tablename__ = "publication_ai_reviews"
    __table_args__ = (UniqueConstraint("publication_id", "source_revision"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    source_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    risk_categories: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    age_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rules_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublicationEditorialReview(Base):
    __tablename__ = "publication_editorial_reviews"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="RESTRICT"),
        index=True,
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranslationJob(Base):
    __tablename__ = "translation_jobs"
    __table_args__ = (UniqueConstraint("publication_id", "target_locale"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        index=True,
    )
    target_locale: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PublicationRating(Base):
    __tablename__ = "publication_ratings"

    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[int] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublicationComment(Base):
    __tablename__ = "publication_comments"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publication_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text)
    is_hidden: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentReport(Base):
    __tablename__ = "content_reports"
    __table_args__ = (UniqueConstraint("reporter_id", "target_type", "target_id"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    reporter_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), index=True)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentModerationAction(Base):
    __tablename__ = "comment_moderation_actions"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    comment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("publication_comments.id", ondelete="RESTRICT"),
        index=True,
    )
    moderator_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
