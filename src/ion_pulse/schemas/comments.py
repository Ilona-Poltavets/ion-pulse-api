from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CommentCreate(BaseModel):
    body: str = Field(default="", max_length=5000)
    parent_id: UUID | None = None
    media_kind: str | None = Field(default=None, pattern="^(gif|sticker)$")
    media_value: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_content(self) -> "CommentCreate":
        self.body = self.body.strip()
        if not self.body and not self.media_kind:
            raise ValueError("Comment text or media is required")
        if (self.media_kind is None) != (self.media_value is None):
            raise ValueError("Comment media kind and value must be provided together")
        if self.media_kind == "gif":
            parsed = urlparse(self.media_value or "")
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("GIF must use a valid HTTP or HTTPS URL")
        if self.media_kind == "sticker" and len(self.media_value or "") > 120:
            raise ValueError("Sticker value is too long")
        return self


class CommentRead(BaseModel):
    id: UUID
    author_id: UUID
    parent_id: UUID | None
    body: str
    media_kind: str | None
    media_value: str | None
    created_at: datetime


class CommentVisibilityUpdate(BaseModel):
    is_hidden: bool


class ModeratedCommentRead(CommentRead):
    publication_id: UUID
    is_hidden: bool
