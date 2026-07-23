from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class AuthorApplicationCreate(BaseModel):
    motivation: str = Field(min_length=50, max_length=2000)
    portfolio_url: HttpUrl | None = None


class AuthorApplicationRead(BaseModel):
    id: UUID
    motivation: str
    portfolio_url: HttpUrl | None
    status: str
    created_at: datetime
