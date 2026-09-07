from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class DraftCreate(BaseModel):
    category_slug: str = Field(min_length=1, max_length=80)
    content_type: str = Field(default="article", pattern="^(article|review|news|guide|digest)$")
    game_id: UUID | None = None
    review_score: float | None = Field(default=None, ge=0, le=10)
    source_locale: str = Field(pattern="^(ru|en)$")
    title: str = Field(min_length=5, max_length=240)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=50)


class DraftRead(BaseModel):
    id: UUID
    category_slug: str
    content_type: str
    game_id: UUID | None
    review_score: float | None
    source_locale: str
    status: str
    scheduled_at: datetime | None
    title: str
    summary: str
    body: str
    created_at: datetime


class PublicationRevisionRead(BaseModel):
    revision_number: int
    category_slug: str
    content_type: str
    game_id: UUID | None
    review_score: float | None
    title: str
    summary: str
    body: str
    created_at: datetime


class PublishedPublicationRead(BaseModel):
    id: UUID
    author_id: UUID
    author_name: str
    category_slug: str
    content_type: str
    game_id: UUID | None
    review_score: float | None
    source_locale: str
    locale: str
    translation_available: bool
    title: str
    summary: str
    body: str
    published_at: datetime


class PublishedPublicationListItem(BaseModel):
    id: UUID
    category_slug: str
    content_type: str
    game_id: UUID | None
    review_score: float | None
    source_locale: str
    locale: str
    translation_available: bool
    title: str
    summary: str
    author_name: str
    published_at: datetime


class EditorialDecisionCreate(BaseModel):
    decision: str = Field(pattern="^(schedule|publish|reject|request_changes)$")
    note: str = Field(min_length=1, max_length=1000)
    scheduled_at: AwareDatetime | None = None


class EditorialActionCreate(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class DraftUpdate(BaseModel):
    category_slug: str = Field(min_length=1, max_length=80)
    content_type: str = Field(pattern="^(article|review|news|guide|digest)$")
    game_id: UUID | None = None
    review_score: float | None = Field(default=None, ge=0, le=10)
    title: str = Field(min_length=5, max_length=240)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=50)


class LocalizationRead(BaseModel):
    locale: str
    origin: str
    translation_status: str
    source_revision: int
    title: str
    summary: str
    body: str


class LocalizationUpdate(BaseModel):
    title: str = Field(min_length=5, max_length=240)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=50)


class DigestItemsUpdate(BaseModel):
    publication_ids: list[UUID] = Field(min_length=1, max_length=20)


class DigestItemRead(BaseModel):
    id: UUID
    category_slug: str
    title: str
    summary: str


class JournalCandidateRead(DigestItemRead):
    body: str = ""
    view_count: int = 0
    published_at: datetime
    average_rating: float
    comment_count: int
    score: float


class JournalPage(BaseModel):
    template: Literal[
        "cover",
        "title",
        "contents",
        "feature",
        "columns",
        "interview",
        "photo",
        "briefs",
        "infographic",
        "poster",
        "finale",
    ]
    publication_ids: list[UUID] = Field(default_factory=list, max_length=12)
    heading: str = Field(default="", max_length=240)
    text: str = Field(default="", max_length=20000)
    image_url: str = Field(default="", max_length=2000, pattern=r"^(https://[^\s]+|/[^/][^\s]*|)$")
    accent: str = Field(default="#c5ef58", pattern=r"^#[0-9a-fA-F]{6}$")
    image_width: int = Field(default=100, ge=20, le=100)
    image_height: int = Field(default=38, ge=15, le=100)
    image_position: Literal["full", "left", "right", "background"] = "full"
    text_x: int = Field(default=8, ge=0, le=80)
    text_y: int = Field(default=58, ge=0, le=85)
    text_width: int = Field(default=84, ge=20, le=100)
    text_size: int = Field(default=38, ge=12, le=96)
    continuation: bool = False

    @model_validator(mode="after")
    def require_material_for_content_page(self) -> "JournalPage":
        if self.template not in {"cover", "title", "finale"} and not self.publication_ids:
            raise ValueError("Journal content pages require at least one publication")
        return self


class JournalIssueCreate(BaseModel):
    title: str = Field(min_length=5, max_length=240)
    pages: list[JournalPage] = Field(default_factory=list, max_length=100)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def validate_period(self) -> "JournalIssueCreate":
        if self.period_end <= self.period_start:
            raise ValueError("Journal period end must be after its start")
        return self


class JournalIssueRead(JournalIssueCreate):
    id: UUID
    status: str
    published_at: datetime | None


class JournalIssuePublicationsUpdate(BaseModel):
    publication_ids: list[UUID] = Field(min_length=1, max_length=50)
