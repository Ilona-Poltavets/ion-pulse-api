import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from ion_pulse.core.security import hash_password
from ion_pulse.db.session import async_session_factory
from ion_pulse.domain.roles import RoleCode
from ion_pulse.main import app
from ion_pulse.models.identity import Role, User, UserRole, UserRoleAudit
from ion_pulse.services.translations import TranslatedContent, process_next_translation_job

pytestmark = pytest.mark.integration


def require_integration_database() -> None:
    if os.environ.get("ION_PULSE_RUN_INTEGRATION") != "1":
        pytest.skip("Set ION_PULSE_RUN_INTEGRATION=1 to run PostgreSQL integration tests")


async def create_user_with_role(email: str, password: str, role_code: RoleCode) -> None:
    async with async_session_factory() as session:
        role = await session.scalar(select(Role).where(Role.code == role_code.value))
        assert role is not None

        user = User(
            email=email,
            display_name=f"{role_code.value}_{uuid4().hex[:12]}",
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()


async def remove_test_users(emails: list[str]) -> None:
    async with async_session_factory() as session:
        user_ids = select(User.id).where(User.email.in_(emails))
        await session.execute(
            delete(UserRoleAudit).where(
                UserRoleAudit.user_id.in_(user_ids) | UserRoleAudit.actor_id.in_(user_ids)
            )
        )
        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.commit()


class StaticTranslator:
    async def translate(
        self,
        *,
        title: str,
        summary: str,
        body: str,
        source_locale: str,
        target_locale: str,
    ) -> TranslatedContent:
        assert source_locale == "en"
        assert target_locale == "ru"
        return TranslatedContent(
            title="Внимательный взгляд на игровой дизайн",
            summary="Translated summary for readers.",
            body="Translated body for readers with the same editorial context.",
        )


@pytest.mark.asyncio(loop_scope="module")
async def test_member_becomes_author_after_administrator_approves_application() -> None:
    require_integration_database()
    suffix = uuid4().hex
    member_email = f"member-{suffix}@example.com"
    administrator_email = f"administrator-{suffix}@example.com"
    password = "Integration-pass-2026!"
    await create_user_with_role(administrator_email, password, RoleCode.ADMINISTRATOR)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as member_client:
            register = await member_client.post(
                "/api/v1/auth/register",
                json={
                    "email": member_email,
                    "display_name": f"member_{suffix[:12]}",
                    "password": password,
                },
            )
            assert register.status_code == 201

            application = await member_client.post(
                "/api/v1/author-applications",
                json={
                    "motivation": (
                        "I publish careful game criticism with sources, clear structure, "
                        "and useful context."
                    ),
                },
            )
            assert application.status_code == 201
            application_id = application.json()["id"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as administrator_client:
            login = await administrator_client.post(
                "/api/v1/auth/login",
                json={"email": administrator_email, "password": password},
            )
            assert login.status_code == 200

            decision = await administrator_client.patch(
                f"/api/v1/author-applications/{application_id}",
                json={
                    "status": "approved",
                    "review_note": "Portfolio and motivation meet our author criteria.",
                },
            )
            assert decision.status_code == 200
            assert decision.json()["status"] == "approved"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as approved_member_client:
            login = await approved_member_client.post(
                "/api/v1/auth/login",
                json={"email": member_email, "password": password},
            )
            assert login.status_code == 200
            assert "author" in login.json()["roles"]
    finally:
        await remove_test_users([member_email, administrator_email])


@pytest.mark.asyncio(loop_scope="module")
async def test_member_material_is_published_after_editorial_decision() -> None:
    require_integration_database()
    suffix = uuid4().hex
    member_email = f"member-{suffix}@example.com"
    editor_email = f"editor-{suffix}@example.com"
    password = "Integration-pass-2026!"
    await create_user_with_role(editor_email, password, RoleCode.EDITOR)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as member_client:
            register = await member_client.post(
                "/api/v1/auth/register",
                json={
                    "email": member_email,
                    "display_name": f"member_{suffix[:12]}",
                    "password": password,
                },
            )
            assert register.status_code == 201

            draft = await member_client.post(
                "/api/v1/publications/drafts",
                json={
                    "category_slug": "news",
                    "source_locale": "en",
                    "title": "A focused look at game design",
                    "summary": (
                        "A practical editorial note about the small choices that make "
                        "games memorable."
                    ),
                    "body": (
                        "Good game criticism helps readers understand what a design "
                        "choice achieves "
                        "and where that choice may not serve every player."
                    ),
                },
            )
            assert draft.status_code == 201
            publication_id = draft.json()["id"]

            submitted = await member_client.post(f"/api/v1/publications/{publication_id}/submit")
            assert submitted.status_code == 200
            assert submitted.json()["status"] == "editorial_review"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as editor_client:
            login = await editor_client.post(
                "/api/v1/auth/login", json={"email": editor_email, "password": password}
            )
            assert login.status_code == 200

            queue = await editor_client.get("/api/v1/publications/editorial-queue")
            assert queue.status_code == 200
            assert publication_id in {item["id"] for item in queue.json()}

            decision = await editor_client.post(
                f"/api/v1/publications/{publication_id}/editorial-decision",
                json={"decision": "publish", "note": "Ready for readers."},
            )
            assert decision.status_code == 200
            assert decision.json()["status"] == "published"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as reader_client:
            published = await reader_client.get(
                f"/api/v1/publications/published/{publication_id}?locale=en"
            )
            assert published.status_code == 200
            assert published.json()["title"] == "A focused look at game design"
            assert published.json()["author_name"] == f"member_{suffix[:12]}"
    finally:
        # Editorial decisions are immutable by design. The CI PostgreSQL service is
        # discarded after this test, so the audit trail remains intact during it.
        pass


@pytest.mark.asyncio(loop_scope="module")
async def test_reader_gets_ready_translation_after_worker_processes_published_material() -> None:
    require_integration_database()
    suffix = uuid4().hex
    member_email = f"member-{suffix}@example.com"
    editor_email = f"editor-{suffix}@example.com"
    password = "Integration-pass-2026!"
    await create_user_with_role(editor_email, password, RoleCode.EDITOR)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as member_client:
            register = await member_client.post(
                "/api/v1/auth/register",
                json={
                    "email": member_email,
                    "display_name": f"member_{suffix[:12]}",
                    "password": password,
                },
            )
            assert register.status_code == 201

            draft = await member_client.post(
                "/api/v1/publications/drafts",
                json={
                    "category_slug": "news",
                    "source_locale": "en",
                    "title": "A focused look at game design",
                    "summary": (
                        "A practical editorial note about the small choices that make "
                        "games memorable."
                    ),
                    "body": (
                        "Good game criticism helps readers understand what a design "
                        "choice achieves and where that choice may not serve every player."
                    ),
                },
            )
            assert draft.status_code == 201
            publication_id = draft.json()["id"]

            submitted = await member_client.post(f"/api/v1/publications/{publication_id}/submit")
            assert submitted.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as editor_client:
            login = await editor_client.post(
                "/api/v1/auth/login", json={"email": editor_email, "password": password}
            )
            assert login.status_code == 200

            decision = await editor_client.post(
                f"/api/v1/publications/{publication_id}/editorial-decision",
                json={"decision": "publish", "note": "Ready for readers."},
            )
            assert decision.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as reader_client:
            fallback = await reader_client.get(
                f"/api/v1/publications/published/{publication_id}?locale=ru"
            )
            assert fallback.status_code == 200
            assert fallback.json()["locale"] == "en"
            assert fallback.json()["translation_available"] is False

        async with async_session_factory() as session:
            processed_jobs = 0
            while await process_next_translation_job(session, StaticTranslator()):
                processed_jobs += 1
            assert processed_jobs > 0

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as reader_client:
            translated = await reader_client.get(
                f"/api/v1/publications/published/{publication_id}?locale=ru"
            )
            assert translated.status_code == 200
            assert translated.json()["locale"] == "ru"
            assert translated.json()["translation_available"] is True
            assert translated.json()["title"] == "Внимательный взгляд на игровой дизайн"
    finally:
        # Editorial decisions are immutable by design. The CI PostgreSQL service is
        # discarded after this test, so the audit trail remains intact during it.
        pass


@pytest.mark.asyncio(loop_scope="module")
async def test_moderator_resolves_a_comment_report_and_hides_the_comment() -> None:
    require_integration_database()
    suffix = uuid4().hex
    member_email = f"member-{suffix}@example.com"
    reporter_email = f"reporter-{suffix}@example.com"
    editor_email = f"editor-{suffix}@example.com"
    moderator_email = f"moderator-{suffix}@example.com"
    password = "Integration-pass-2026!"
    await create_user_with_role(editor_email, password, RoleCode.EDITOR)
    await create_user_with_role(moderator_email, password, RoleCode.MODERATOR)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as member_client:
            register = await member_client.post(
                "/api/v1/auth/register",
                json={
                    "email": member_email,
                    "display_name": f"member_{suffix[:12]}",
                    "password": password,
                },
            )
            assert register.status_code == 201

            draft = await member_client.post(
                "/api/v1/publications/drafts",
                json={
                    "category_slug": "news",
                    "source_locale": "en",
                    "title": "Moderation keeps conversations useful",
                    "summary": "A short note on clear and safe community discussions.",
                    "body": (
                        "Thoughtful moderation protects readers and lets useful discussion "
                        "stay visible."
                    ),
                },
            )
            assert draft.status_code == 201
            publication_id = draft.json()["id"]
            assert (
                await member_client.post(f"/api/v1/publications/{publication_id}/submit")
            ).status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as editor_client:
            assert (
                await editor_client.post(
                    "/api/v1/auth/login",
                    json={"email": editor_email, "password": password},
                )
            ).status_code == 200
            decision = await editor_client.post(
                f"/api/v1/publications/{publication_id}/editorial-decision",
                json={"decision": "publish", "note": "Ready for readers."},
            )
            assert decision.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as member_client:
            assert (
                await member_client.post(
                    "/api/v1/auth/login",
                    json={"email": member_email, "password": password},
                )
            ).status_code == 200
            comment = await member_client.post(
                f"/api/v1/publications/{publication_id}/comments",
                json={"body": "This discussion should not be visible to readers."},
            )
            assert comment.status_code == 201
            comment_id = comment.json()["id"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as reporter_client:
            assert (
                await reporter_client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": reporter_email,
                        "display_name": f"reporter_{suffix[:12]}",
                        "password": password,
                    },
                )
            ).status_code == 201
            report = await reporter_client.post(
                f"/api/v1/comments/{comment_id}/reports",
                json={"reason": "This comment needs a moderation review before it is shown."},
            )
            assert report.status_code == 201
            report_id = report.json()["id"]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as moderator_client:
            assert (
                await moderator_client.post(
                    "/api/v1/auth/login",
                    json={"email": moderator_email, "password": password},
                )
            ).status_code == 200
            queue = await moderator_client.get("/api/v1/reports")
            assert queue.status_code == 200
            queued_report = next(item for item in queue.json() if item["id"] == report_id)
            assert (
                queued_report["target_excerpt"]
                == "This discussion should not be visible to readers."
            )

            resolved = await moderator_client.patch(
                f"/api/v1/reports/{report_id}",
                json={"status": "resolved", "review_note": "Comment hidden after review."},
            )
            assert resolved.status_code == 200
            hidden = await moderator_client.patch(
                f"/api/v1/publications/comments/{comment_id}/visibility",
                json={"is_hidden": True},
            )
            assert hidden.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as reader_client:
            visible_comments = await reader_client.get(
                f"/api/v1/publications/{publication_id}/comments"
            )
            assert visible_comments.status_code == 200
            assert visible_comments.json() == []
    finally:
        # Report decisions and moderation actions are immutable audit records.
        # CI discards its database after the integration job.
        pass
