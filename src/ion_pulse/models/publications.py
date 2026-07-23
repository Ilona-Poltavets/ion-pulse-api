# ruff: noqa: E501
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ion_pulse.db.base import Base


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    category_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    source_locale: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(30), server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PublicationLocalization(Base):
    __tablename__ = "publication_localizations"
    __table_args__ = (UniqueConstraint("publication_id", "locale"),)
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    publication_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    locale: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(20), server_default="original")
    source_revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
