"""Idempotent baseline data seeding.

Run after migrations with ``uv run python -m ion_pulse.seeds``. An administrator
is created only when both bootstrap email and password are configured.
"""

# ruff: noqa: E501, RUF001

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ion_pulse.core.config import get_settings
from ion_pulse.core.security import hash_password
from ion_pulse.db.session import async_session_factory, engine
from ion_pulse.domain.roles import RoleCode
from ion_pulse.models.identity import Role, User, UserRole
from ion_pulse.models.publications import (
    Category,
    JournalIssue,
    JournalIssuePublication,
    Publication,
    PublicationLocalization,
)

BASE_CATEGORIES = (
    (
        "reviews",
        "Game reviews",
        "Ревью игр",
        "In-depth impressions and game analysis",
        "Подробные впечатления и разборы игр",
        "#C7FF5E",
        1,
    ),
    (
        "news",
        "Gaming news",
        "Игровые новости",
        "Games industry events and announcements",
        "События и анонсы игровой индустрии",
        "#A68BFF",
        2,
    ),
    (
        "guides",
        "Guides",
        "Гайды",
        "Practical advice for players",
        "Практические советы для игроков",
        "#72DDF7",
        3,
    ),
    (
        "esports",
        "Esports",
        "Киберспорт",
        "Tournaments, teams and competitive gaming",
        "Турниры, команды и соревновательная сцена",
        "#FFB86B",
        4,
    ),
)

# Development-only fixtures. They make a fresh local installation immediately
# useful for checking the feed, localization and role-specific workspaces.
DEMO_PASSWORD = "IonPulseDemo2026!"
DEMO_USERS = (
    ("admin@ion-pulse.local", "Ion Admin", (RoleCode.ADMINISTRATOR,)),
    ("content@ion-pulse.local", "Casey Content", (RoleCode.CONTENT_MANAGER,)),
    ("editor@ion-pulse.local", "Maya Editor", (RoleCode.EDITOR,)),
    ("author@ion-pulse.local", "Alex North", (RoleCode.AUTHOR,)),
    ("moderator@ion-pulse.local", "Sam Guard", (RoleCode.MODERATOR,)),
    ("player@ion-pulse.local", "Jamie Player", ()),
)

DEMO_JOURNAL_PERIOD_START = datetime(2026, 7, 1, tzinfo=UTC)
DEMO_JOURNAL_PERIOD_END = datetime(2026, 8, 1, tzinfo=UTC)
DEMO_JOURNAL_TITLE = "ISSUE 00 — JULY 2026"
DEMO_PUBLICATIONS = (
    (
        "reviews",
        "author@ion-pulse.local",
        "ru",
        "review",
        4.5,
        "Почему игры с короткой петлёй остаются с нами надолго",
        "Разбираем, как ритм, ясная цель и маленькие открытия превращают один вечер в привычку.",
        "У хорошей игровой петли есть редкое свойство: она уважает время игрока. Каждое действие даёт понятный результат, а следующая цель появляется раньше, чем исчезает любопытство.",
        "Why short-loop games stay with us",
        "A look at how rhythm, clear goals, and small discoveries turn one evening into a lasting habit.",
        "A great game loop respects the player's time. Every action has a clear result, and the next goal appears before curiosity fades.",
    ),
    (
        "news",
        "editor@ion-pulse.local",
        "en",
        "news",
        None,
        "Небольшие студии снова выбирают смелые механики",
        "Независимые команды показывают, что ясная идея важнее размера производственного бюджета.",
        "Новые анонсы недели объединяет одно: авторы не пытаются понравиться всем сразу. Они строят игры вокруг одной сильной механики и дают ей достаточно пространства.",
        "Small studios are choosing bold mechanics again",
        "This week's announcements show that a clear idea matters more than production scale.",
        "This week's announcements share one trait: their creators are not trying to please everyone. They build around one strong mechanic and give it room to breathe.",
    ),
    (
        "guides",
        "author@ion-pulse.local",
        "ru",
        "guide",
        None,
        "Гайд без спойлеров: как вернуться в большую RPG",
        "Три простых шага помогут продолжить приключение, даже если последний сейв был полгода назад.",
        "Не начинайте сначала. Откройте журнал заданий, выберите одну короткую цель и дайте себе двадцать минут на знакомство с миром. Контекст вернётся быстрее, чем кажется.",
        "A spoiler-free guide to returning to a big RPG",
        "Three simple steps for picking up an adventure after a long break.",
        "Do not restart. Open your quest journal, choose one short goal, and give yourself twenty minutes to reconnect with the world. Context returns faster than you expect.",
    ),
    (
        "esports",
        "editor@ion-pulse.local",
        "en",
        "article",
        None,
        "Команда недели: дисциплина вместо идеального старта",
        "Победа в серии получилась не эффектной, а очень точной — и потому особенно убедительной.",
        "Команда уступила первый раунд, но не изменила план. Спокойные решения в середине карты позволили ей забрать инициативу и довести матч до победы.",
        "Team of the week: discipline over a perfect start",
        "The series win was not flashy. It was precise — and that made it convincing.",
        "The team lost the opening round but did not abandon its plan. Calm mid-map decisions let it reclaim initiative and close the match.",
    ),
    (
        "reviews",
        "author@ion-pulse.local",
        "en",
        "review",
        4.0,
        "Инди-головоломка, которая умеет вовремя остановиться",
        "Короткая, атмосферная и внимательная к игроку история о поиске закономерностей.",
        "Игра не растягивает одну идею на десятки комнат. Она знакомит с правилом, просит применить его несколькими способами и вовремя предлагает следующую мысль.",
        "The indie puzzle game that knows when to stop",
        "A short, atmospheric story about noticing patterns — and respecting the player.",
        "The game does not stretch one idea across dozens of rooms. It introduces a rule, asks you to apply it a few ways, then moves on at exactly the right time.",
    ),
)


async def seed() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        roles = {role.code: role for role in (await session.scalars(select(Role))).all()}
        for code in RoleCode:
            if code.value not in roles:
                role = Role(code=code.value, name=code.value.replace("_", " ").title())
                session.add(role)
                roles[code.value] = role
        for slug, name_en, name_ru, desc_en, desc_ru, color, order in BASE_CATEGORIES:
            category = await session.scalar(select(Category).where(Category.slug == slug))
            if category is None:
                session.add(
                    Category(
                        slug=slug,
                        name_en=name_en,
                        name_ru=name_ru,
                        description_en=desc_en,
                        description_ru=desc_ru,
                        color=color,
                        sort_order=order,
                    )
                )
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            email = settings.bootstrap_admin_email.lower()
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    display_name=settings.bootstrap_admin_display_name,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                )
                session.add(user)
                await session.flush()
            elif settings.bootstrap_admin_reset_password:
                user.password_hash = hash_password(settings.bootstrap_admin_password)
            await session.flush()
            administrator = roles[RoleCode.ADMINISTRATOR.value]
            existing_role = await session.get(
                UserRole, {"user_id": user.id, "role_id": administrator.id}
            )
            if existing_role is None:
                session.add(UserRole(user_id=user.id, role_id=administrator.id))
        await session.flush()

        for email, display_name, role_codes in DEMO_USERS:
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(DEMO_PASSWORD),
                )
                session.add(user)
                await session.flush()
            for role_code in role_codes:
                role = roles[role_code.value]
                if await session.get(UserRole, {"user_id": user.id, "role_id": role.id}) is None:
                    session.add(UserRole(user_id=user.id, role_id=role.id))

        await session.flush()
        categories = {
            category.slug: category for category in (await session.scalars(select(Category))).all()
        }
        categories_by_id = {category.id: category for category in categories.values()}
        users = {user.email: user for user in (await session.scalars(select(User))).all()}
        for index, item in enumerate(DEMO_PUBLICATIONS):
            (
                category_slug,
                author_email,
                source_locale,
                content_type,
                review_score,
                title_ru,
                summary_ru,
                body_ru,
                title_en,
                summary_en,
                body_en,
            ) = item
            existing = await session.scalar(
                select(PublicationLocalization).where(
                    PublicationLocalization.title
                    == (title_ru if source_locale == "ru" else title_en)
                )
            )
            if existing is not None:
                continue
            publication = Publication(
                author_id=users[author_email].id,
                category_id=categories[category_slug].id,
                source_locale=source_locale,
                content_type=content_type,
                review_score=review_score,
                status="published",
                published_at=datetime.now(UTC) - timedelta(days=index),
            )
            session.add(publication)
            await session.flush()
            session.add_all(
                (
                    PublicationLocalization(
                        publication_id=publication.id,
                        locale="ru",
                        title=title_ru,
                        summary=summary_ru,
                        body=body_ru,
                        origin="original" if source_locale == "ru" else "translation",
                        translation_status="ready",
                        source_revision=1,
                    ),
                    PublicationLocalization(
                        publication_id=publication.id,
                        locale="en",
                        title=title_en,
                        summary=summary_en,
                        body=body_en,
                        origin="original" if source_locale == "en" else "translation",
                        translation_status="ready",
                        source_revision=1,
                    ),
                )
            )

        await session.flush()
        issue = await session.scalar(
            select(JournalIssue).where(
                JournalIssue.period_start == DEMO_JOURNAL_PERIOD_START,
                JournalIssue.period_end == DEMO_JOURNAL_PERIOD_END,
            )
        )
        if issue is None:
            issue = JournalIssue(
                editor_id=users["editor@ion-pulse.local"].id,
                title=DEMO_JOURNAL_TITLE,
                period_start=DEMO_JOURNAL_PERIOD_START,
                period_end=DEMO_JOURNAL_PERIOD_END,
                status="published",
                published_at=datetime(2026, 8, 1, 9, tzinfo=UTC),
            )
            session.add(issue)
            await session.flush()
            materials = (
                await session.scalars(
                    select(Publication)
                    .where(Publication.status == "published")
                    .order_by(Publication.published_at.desc())
                    .limit(5)
                )
            ).all()
            for position, publication in enumerate(materials, 1):
                category = categories_by_id[publication.category_id]
                localizations = (
                    await session.scalars(
                        select(PublicationLocalization).where(
                            PublicationLocalization.publication_id == publication.id,
                            PublicationLocalization.translation_status == "ready",
                        )
                    )
                ).all()
                session.add(
                    JournalIssuePublication(
                        issue_id=issue.id,
                        publication_id=publication.id,
                        position=position,
                        snapshot={
                            "category_slug": category.slug,
                            "source_locale": publication.source_locale,
                            "localizations": {
                                localization.locale: {
                                    "title": localization.title,
                                    "summary": localization.summary,
                                    "body": localization.body,
                                }
                                for localization in localizations
                            },
                        },
                    )
                )
        await session.commit()


async def main() -> None:
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
