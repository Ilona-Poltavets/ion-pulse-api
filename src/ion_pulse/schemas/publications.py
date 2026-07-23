from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DraftCreate(BaseModel):
    category_slug: str = Field(pattern="^(reviews|news|guides|esports)$")
    source_locale: str = Field(pattern="^(ru|en)$")
    title: str = Field(min_length=5, max_length=240)
    summary: str = Field(min_length=20, max_length=500)
    body: str = Field(min_length=50)


class DraftRead(BaseModel):
    id: UUID
    category_slug: str
    source_locale: str
    status: str
    title: str
    summary: str
    body: str
    created_at: datetime
