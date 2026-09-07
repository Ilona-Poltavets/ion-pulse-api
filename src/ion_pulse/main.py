from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from ion_pulse.api.router import api_router
from ion_pulse.core.config import get_settings
from ion_pulse.db.session import async_session_factory, engine
from ion_pulse.domain.publications import PublicationStatus
from ion_pulse.models.publications import JournalIssue, Publication


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    application.mount(
        "/uploads",
        StaticFiles(directory=settings.upload_directory, check_dir=False),
        name="uploads",
    )

    @application.get("/sitemap.xml", include_in_schema=False)
    async def sitemap() -> Response:
        async with async_session_factory() as session:
            publications = (
                await session.scalars(
                    select(Publication)
                    .where(Publication.status == PublicationStatus.PUBLISHED.value)
                    .order_by(Publication.published_at.desc())
                )
            ).all()
            issues = (
                await session.scalars(
                    select(JournalIssue)
                    .where(JournalIssue.status == "published")
                    .order_by(JournalIssue.published_at.desc())
                )
            ).all()
        base_url = settings.site_url.rstrip("/")
        entries = [
            f"<url><loc>{escape(base_url)}/</loc></url>",
            f"<url><loc>{escape(base_url)}/journal</loc></url>",
        ]
        entries.extend(
            f"<url><loc>{escape(base_url)}/{locale}/publications/{publication.id}</loc><lastmod>{publication.published_at.date().isoformat()}</lastmod></url>"
            for publication in publications
            if publication.published_at is not None
            for locale in ("ru", "en")
        )
        entries.extend(
            f"<url><loc>{escape(base_url)}/journal/{issue.id}</loc><lastmod>{issue.published_at.date().isoformat()}</lastmod></url>"
            for issue in issues
            if issue.published_at is not None
        )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(entries)
            + "</urlset>"
        )
        return Response(body, media_type="application/xml")

    @application.get("/robots.txt", include_in_schema=False)
    async def robots() -> Response:
        return Response(
            f"User-agent: *\nAllow: /\nSitemap: {settings.site_url.rstrip('/')}/sitemap.xml\n",
            media_type="text/plain",
        )

    return application


app = create_app()
