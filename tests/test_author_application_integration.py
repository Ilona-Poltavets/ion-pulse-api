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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
