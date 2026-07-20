# Ion Pulse API

Backend API for the bilingual Ion Pulse gaming media platform.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 or newer

## Local development

```bash
cp .env.example .env
uv sync
uv run uvicorn ion_pulse.main:app --reload
```

The API is available at `http://localhost:8000`. OpenAPI documentation is
available at `http://localhost:8000/docs`.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Initial endpoints

- `GET /api/v1/health` — liveness and build information.
- `GET /api/v1/ready` — verifies the database connection.
