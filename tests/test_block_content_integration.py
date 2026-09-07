import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ion_pulse.api.routes.publications import create_draft, list_my_publications
from ion_pulse.db.session import engine
from ion_pulse.models.identity import User
from ion_pulse.models.publications import Category, PublicationRevision
from ion_pulse.schemas.publications import DraftCreate


@pytest.mark.integration
@pytest.mark.asyncio
async def test_block_content_survives_save_reload_and_revision():
    if os.environ.get("ION_PULSE_RUN_INTEGRATION") != "1":
        pytest.skip("Set ION_PULSE_RUN_INTEGRATION=1 for local database verification")
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            ) as session:
                user = await session.scalar(select(User).limit(1))
                category = await session.scalar(select(Category).limit(1))
                if user is None or category is None:
                    pytest.skip("Requires seeded user and category")
                body = (
                    '<!-- ion-pulse:blocks --><h2 data-align="center">Monthly story</h2>'
                    "<p>A story with <strong>bold text</strong> and a clear structure.</p>"
                    "<blockquote><p>Words worth remembering.</p></blockquote>"
                    '<img src="https://example.com/photo.png" alt="A landscape">'
                )
                draft = await create_draft(
                    DraftCreate(
                        category_slug=category.slug,
                        source_locale="ru",
                        title="Block editor integration verification",
                        summary="Verifying preservation of formatted content.",
                        body=body,
                    ),
                    session,
                    user,
                )
                assert draft.body == body
                reloaded = next(
                    item
                    for item in await list_my_publications(session, user)
                    if item.id == draft.id
                )
                assert reloaded.body == body
                revision = await session.scalar(
                    select(PublicationRevision).where(
                        PublicationRevision.publication_id == draft.id
                    )
                )
                assert revision is not None and revision.body == body
        finally:
            await transaction.rollback()
