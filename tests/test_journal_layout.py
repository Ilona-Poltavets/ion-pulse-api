from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from ion_pulse.api.routes.journal import require_journal_access, save_issue
from ion_pulse.models.publications import JournalIssue
from ion_pulse.schemas.publications import JournalIssueCreate, JournalPage


@pytest.mark.parametrize("role", ["author", "moderator", "content_manager"])
def test_other_roles_cannot_manage_journal(role):
    with pytest.raises(HTTPException) as error:
        require_journal_access(SimpleNamespace(roles=[SimpleNamespace(code=role)]))
    assert error.value.status_code == 403


@pytest.mark.parametrize("role", ["editor", "administrator"])
def test_editor_and_administrator_can_manage_journal(role):
    require_journal_access(SimpleNamespace(roles=[SimpleNamespace(code=role)]))


@pytest.mark.parametrize(
    "changes",
    [
        {"template": "unknown"},
        {"publication_ids": []},
        {"image_url": "javascript:alert(1)"},
        {"image_url": "//untrusted.example/image"},
        {"accent": "red;display:none"},
    ],
)
def test_layout_rejects_invalid_content(changes):
    payload = {"template": "feature", "publication_ids": [uuid4()]} | changes
    with pytest.raises(ValidationError):
        JournalPage(**payload)


@pytest.mark.asyncio
async def test_save_rejects_article_outside_month_without_writing():
    editor_id = uuid4()
    user = SimpleNamespace(id=editor_id, roles=[SimpleNamespace(code="editor")])
    issue = JournalIssue(id=uuid4(), editor_id=editor_id, status="draft")
    session = AsyncMock()
    session.get.return_value = issue
    found = Mock()
    found.all.return_value = []
    session.scalars.return_value = found
    payload = JournalIssueCreate(
        title="Monthly journal",
        period_start=datetime(2026, 8, 1, tzinfo=UTC),
        period_end=datetime(2026, 9, 1, tzinfo=UTC),
        pages=[JournalPage(template="feature", publication_ids=[uuid4()])],
    )
    with pytest.raises(HTTPException) as error:
        await save_issue(issue.id, payload, session, user)
    assert error.value.status_code == 422
    session.commit.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_published_layout_is_immutable():
    editor_id = uuid4()
    user = SimpleNamespace(id=editor_id, roles=[SimpleNamespace(code="editor")])
    issue = JournalIssue(id=uuid4(), editor_id=editor_id, status="published")
    session = AsyncMock()
    session.get.return_value = issue
    payload = JournalIssueCreate(
        title="Monthly journal",
        period_start=datetime(2026, 8, 1, tzinfo=UTC),
        period_end=datetime(2026, 9, 1, tzinfo=UTC),
    )
    with pytest.raises(HTTPException) as error:
        await save_issue(issue.id, payload, session, user)
    assert error.value.status_code == 404
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_preserves_page_order_and_deduplicates_membership():
    editor_id = uuid4()
    first, second = uuid4(), uuid4()
    user = SimpleNamespace(id=editor_id, roles=[SimpleNamespace(code="editor")])
    issue = JournalIssue(id=uuid4(), editor_id=editor_id, status="draft", published_at=None)
    session = AsyncMock()
    session.get.return_value = issue
    found = Mock()
    found.all.return_value = [first, second]
    session.scalars.return_value = found
    session.add_all = Mock()
    payload = JournalIssueCreate(
        title="Monthly journal",
        period_start=datetime(2026, 8, 1, tzinfo=UTC),
        period_end=datetime(2026, 9, 1, tzinfo=UTC),
        pages=[
            JournalPage(template="poster", publication_ids=[second]),
            JournalPage(template="columns", publication_ids=[first, second]),
        ],
    )
    result = await save_issue(issue.id, payload, session, user)
    assert [page.template for page in result.pages] == ["poster", "columns"]
    assert result.pages[1].publication_ids == [first, second]
    memberships = session.add_all.call_args.args[0]
    assert [item.publication_id for item in memberships] == [second, first]
    session.commit.assert_awaited_once()
