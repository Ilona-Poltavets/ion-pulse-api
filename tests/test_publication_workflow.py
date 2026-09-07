from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from ion_pulse.api.routes.publications import get_published_publication
from ion_pulse.domain.publications import (
    EditorialDecision,
    PublicationStatus,
    resolve_editorial_decision,
    translation_target_locale,
)
from ion_pulse.models.identity import User
from ion_pulse.models.publications import Category, Publication, PublicationLocalization


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        (EditorialDecision.SCHEDULE, PublicationStatus.SCHEDULED),
        (EditorialDecision.PUBLISH, PublicationStatus.PUBLISHED),
        (EditorialDecision.REJECT, PublicationStatus.REJECTED),
        (EditorialDecision.REQUEST_CHANGES, PublicationStatus.CHANGES_REQUESTED),
    ],
)
def test_editorial_decision_resolves_to_expected_publication_status(
    decision: EditorialDecision,
    expected_status: PublicationStatus,
) -> None:
    assert resolve_editorial_decision(decision) is expected_status


def test_unknown_editorial_decision_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported editorial decision"):
        resolve_editorial_decision("archive")


def test_archived_status_is_part_of_the_publication_lifecycle() -> None:
    assert PublicationStatus.ARCHIVED.value == "archived"


@pytest.mark.parametrize(("source", "target"), [("ru", "en"), ("en", "ru")])
def test_translation_target_is_the_other_supported_locale(source: str, target: str) -> None:
    assert translation_target_locale(source).value == target


@pytest.mark.asyncio
async def test_published_publication_with_ready_requested_locale_includes_author() -> None:
    """The normal (non-fallback) localization path must produce a complete response."""
    publication = Publication(
        id=uuid4(),
        author_id=uuid4(),
        category_id=uuid4(),
        source_locale="ru",
        status=PublicationStatus.PUBLISHED.value,
        content_type="article",
        published_at=datetime.now(UTC),
    )
    localization = PublicationLocalization(
        publication_id=publication.id,
        locale="en",
        title="English title",
        summary="English summary",
        body="English body",
        translation_status="ready",
    )
    category = Category(id=publication.category_id, slug="news")
    author = User(id=publication.author_id, email="author@example.test", display_name="Author")

    async def execute(statement: object) -> Mock:
        # Mirror SQLAlchemy's result shape for exactly the entities selected by
        # the endpoint. The old query selected only three entities.
        if not hasattr(statement, "column_descriptions"):
            return Mock()
        selected = len(statement.column_descriptions)  # type: ignore[attr-defined]
        row = Mock()
        row.one_or_none.return_value = (publication, localization, category, author)[:selected]
        return row

    session = AsyncMock()
    session.execute.side_effect = execute

    result = await get_published_publication(str(publication.id), session, "en")

    assert result.author_name == "Author"
    assert result.title == "English title"
