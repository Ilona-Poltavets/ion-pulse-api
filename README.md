# Ion Pulse API

Backend API for the bilingual Ion Pulse gaming media platform.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 or newer

## Local development

### PostgreSQL without Docker

Docker is optional. On Ubuntu/Debian, start the system PostgreSQL cluster and
create the development account once:

```bash
sudo pg_ctlcluster 16 main start
sudo -u postgres createuser --pwprompt ion_pulse
sudo -u postgres createdb --owner=ion_pulse ion_pulse
```

Confirm that it is running:

```bash
pg_isready -h localhost -p 5432 -U ion_pulse
```

The default `ION_PULSE_DATABASE_URL` in `.env.example` already points to this
local database. Docker Compose remains an optional isolated development setup.

### Run the API

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
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
