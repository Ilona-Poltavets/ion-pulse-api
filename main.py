import hashlib
import hmac
import secrets
from enum import Enum
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Language(str, Enum):
    ru = "ru"
    en = "en"


class Section(str, Enum):
    games = "games"
    programming = "programming"


class Role(str, Enum):
    admin = "admin"
    editor_in_chief = "editor_in_chief"
    author = "author"
    reviewer = "reviewer"
    moderator = "moderator"
    user = "user"
    guest = "guest"


ROLE_LABELS: dict[Role, str] = {
    Role.admin: "Администратор",
    Role.editor_in_chief: "Главный редактор",
    Role.author: "Автор",
    Role.reviewer: "Ревьюер",
    Role.moderator: "Модератор",
    Role.user: "Пользователь",
    Role.guest: "Гость",
}

ROLE_PERMISSIONS: dict[Role, list[str]] = {
    Role.admin: [
        "manage_users",
        "manage_roles",
        "manage_site_settings",
        "publish_any_content",
        "delete_any_content",
        "manage_ads",
        "moderate_comments",
        "view_statistics",
    ],
    Role.editor_in_chief: [
        "create_any_article",
        "edit_any_article",
        "publish_content",
        "reject_author_content",
        "manage_categories",
        "manage_tags",
        "assign_author_tasks",
    ],
    Role.author: [
        "write_news",
        "write_reviews",
        "create_quizzes",
        "upload_images",
        "edit_own_content",
    ],
    Role.reviewer: [
        "view_drafts",
        "leave_review_notes",
        "approve_articles",
        "request_revision",
    ],
    Role.moderator: [
        "delete_comments",
        "ban_users",
        "moderate_reports",
        "hide_toxic_content",
    ],
    Role.user: [
        "comment",
        "like_content",
        "save_favorites",
        "take_quizzes",
        "write_reviews_if_allowed",
    ],
    Role.guest: [
        "read_articles",
        "take_open_quizzes",
        "view_reviews",
    ],
}


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


class RoleInfo(BaseModel):
    code: Role
    title: str
    permissions: list[str]


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    role_title: str
    permissions: list[str]


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class AdminOverview(BaseModel):
    users_count: int
    articles_count: int
    roles_count: int
    pending_reviews: int
    reports_count: int


class StoredUser(BaseModel):
    id: int
    username: str
    email: str
    password_hash: str
    role: Role


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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


USERS: list[StoredUser] = [
    StoredUser(
        id=1,
        username="Admin",
        email="admin@halfstack.dev",
        password_hash=hash_password("admin12345"),
        role=Role.admin,
    )
]
TOKENS: dict[str, int] = {}


def to_public_user(user: StoredUser) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        role_title=ROLE_LABELS[user.role],
        permissions=ROLE_PERMISSIONS[user.role],
    )


def find_user_by_email(email: str) -> StoredUser | None:
    normalized_email = email.strip().lower()
    for user in USERS:
        if user.email == normalized_email:
            return user

    return None


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> StoredUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )

    token = authorization.removeprefix("Bearer ").strip()
    user_id = TOKENS.get(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is invalid",
        )

    for user in USERS:
        if user.id == user_id:
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")


def require_admin(current_user: Annotated[StoredUser, Depends(get_current_user)]) -> StoredUser:
    if current_user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role is required",
        )

    return current_user


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


@app.get("/api/roles", response_model=list[RoleInfo])
def get_roles() -> list[RoleInfo]:
    return [
        RoleInfo(code=role, title=ROLE_LABELS[role], permissions=ROLE_PERMISSIONS[role])
        for role in Role
    ]


@app.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> AuthResponse:
    username = payload.username.strip()
    email = payload.email.strip().lower()
    password = payload.password

    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Username must contain at least 2 characters")

    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email is invalid")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters")

    if find_user_by_email(email):
        raise HTTPException(status_code=409, detail="User with this email already exists")

    user = StoredUser(
        id=max(user.id for user in USERS) + 1,
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=Role.user,
    )
    USERS.append(user)

    token = secrets.token_urlsafe(32)
    TOKENS[token] = user.id

    return AuthResponse(token=token, user=to_public_user(user))


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = find_user_by_email(payload.email)

    if not user or not hmac.compare_digest(user.password_hash, hash_password(payload.password)):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = secrets.token_urlsafe(32)
    TOKENS[token] = user.id

    return AuthResponse(token=token, user=to_public_user(user))


@app.get("/api/auth/me", response_model=UserPublic)
def get_me(current_user: Annotated[StoredUser, Depends(get_current_user)]) -> UserPublic:
    return to_public_user(current_user)


@app.get("/api/admin/overview", response_model=AdminOverview)
def get_admin_overview(_: Annotated[StoredUser, Depends(require_admin)]) -> AdminOverview:
    return AdminOverview(
        users_count=len(USERS),
        articles_count=len(ARTICLES),
        roles_count=len(Role),
        pending_reviews=3,
        reports_count=1,
    )


@app.get("/api/admin/users", response_model=list[UserPublic])
def get_admin_users(_: Annotated[StoredUser, Depends(require_admin)]) -> list[UserPublic]:
    return [to_public_user(user) for user in USERS]


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
