from enum import Enum
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Language(str, Enum):
    ru = "ru"
    en = "en"


class Section(str, Enum):
    games = "games"
    programming = "programming"


class Article(BaseModel):
    id: int
    slug: str
    title: str
    excerpt: str
    body: str
    language: Language
    section: Section
    author: str
    read_minutes: int
    published_at: str
    tags: list[str]
    is_featured: bool = False


class MetaResponse(BaseModel):
    name: str
    languages: list[Language]
    sections: list[Section]


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(
    title="HalfStack API",
    description="Backend API for a bilingual blog about games and programming.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ARTICLES: list[Article] = [
    Article(
        id=1,
        slug="coop-rpg-crossplay-season",
        title="Новый сезон кооперативных RPG делает ставку на кроссплей",
        excerpt="Разработчики синхронизируют прогресс между PC и консолями.",
        body=(
            "Студии активнее тестируют общие серверы до релиза, чтобы игроки "
            "могли переносить прогресс между платформами и играть вместе без "
            "привязки к одной экосистеме."
        ),
        language=Language.ru,
        section=Section.games,
        author="Gaming Desk",
        read_minutes=4,
        published_at="2026-06-01T09:00:00Z",
        tags=["RPG", "crossplay", "PC"],
        is_featured=True,
    ),
    Article(
        id=2,
        slug="indie-live-playtests",
        title="Indie studios move demos into live community playtests",
        excerpt="Small teams are using public testing as an editorial and product tool.",
        body=(
            "Instead of waiting for festivals, indie developers are opening playable "
            "builds earlier and collecting structured feedback from Discord, Steam, "
            "and creator communities."
        ),
        language=Language.en,
        section=Section.games,
        author="Gaming Desk",
        read_minutes=3,
        published_at="2026-06-01T10:30:00Z",
        tags=["indie", "playtests", "Steam"],
    ),
    Article(
        id=3,
        slug="typescript-python-product-speed",
        title="TypeScript и Python остаются главными языками для быстрых продуктов",
        excerpt="Команды выбирают типизацию, понятные API и автоматизацию тестов.",
        body=(
            "Связка TypeScript на фронтенде и Python на бэкенде остается удобной "
            "для быстрых продуктовых команд: меньше ручной синхронизации, проще "
            "описание контрактов и быстрее проверка гипотез."
        ),
        language=Language.ru,
        section=Section.programming,
        author="Dev Desk",
        read_minutes=5,
        published_at="2026-06-01T11:00:00Z",
        tags=["TypeScript", "Python", "API"],
        is_featured=True,
    ),
    Article(
        id=4,
        slug="framework-updates-smaller-bundles",
        title="Framework updates focus on smaller bundles and faster hydration",
        excerpt="Frontend releases keep pushing runtime cost down.",
        body=(
            "Recent framework updates are focusing on compiler output, partial "
            "hydration, and better defaults for route-level code splitting."
        ),
        language=Language.en,
        section=Section.programming,
        author="Dev Desk",
        read_minutes=4,
        published_at="2026-06-01T12:15:00Z",
        tags=["frontend", "performance", "frameworks"],
    ),
]


@app.get("/", response_model=MetaResponse)
def root() -> MetaResponse:
    return MetaResponse(
        name="HalfStack",
        languages=[Language.ru, Language.en],
        sections=[Section.games, Section.programming],
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/meta", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    return root()


@app.get("/api/articles", response_model=list[Article])
def get_articles(
    language: Language | None = Query(default=None),
    section: Section | None = Query(default=None),
    featured: bool | None = Query(default=None),
) -> list[Article]:
    articles = ARTICLES

    if language is not None:
        articles = [article for article in articles if article.language == language]

    if section is not None:
        articles = [article for article in articles if article.section == section]

    if featured is not None:
        articles = [article for article in articles if article.is_featured == featured]

    return articles


@app.get("/api/articles/{slug}", response_model=Article)
def get_article(slug: str) -> Article:
    for article in ARTICLES:
        if article.slug == slug:
            return article

    raise HTTPException(status_code=404, detail="Article not found")
