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

### Baseline data and administrator

Migrations create the standard roles and categories. To also create or promote
a bootstrap administrator, set `ION_PULSE_BOOTSTRAP_ADMIN_EMAIL` and
`ION_PULSE_BOOTSTRAP_ADMIN_PASSWORD` in `.env`, then run:

```bash
uv run python -m ion_pulse.seeds
```

For a local demo, the seed also creates five accounts and five published,
fully localized materials. All demo accounts use `IonPulseDemo2026!`:
`admin@ion-pulse.local`, `editor@ion-pulse.local`, `author@ion-pulse.local`,
`moderator@ion-pulse.local`, and `player@ion-pulse.local`.

The command is idempotent and never stores a password in source control.
To deliberately reset an existing bootstrap account password, run it once with
`ION_PULSE_BOOTSTRAP_ADMIN_RESET_PASSWORD=true`, then remove that setting.

The API is available at `http://localhost:8000`. OpenAPI documentation is
available at `http://localhost:8000/docs`.

### Password recovery email

For local development recovery links are written to the API log. To deliver
them through SMTP set `ION_PULSE_PASSWORD_RESET_DELIVERY=smtp`,
`ION_PULSE_SMTP_HOST`, `ION_PULSE_SMTP_FROM_EMAIL`, and, when required,
`ION_PULSE_SMTP_USERNAME` / `ION_PULSE_SMTP_PASSWORD`.

### AI editorial review

The worker leaves reviews in the safe manual queue until a provider is configured.
For an OpenAI-compatible chat-completions endpoint set
`ION_PULSE_AI_REVIEW_PROVIDER=openai_compatible` and
`ION_PULSE_AI_REVIEW_API_KEY`; optionally set the base URL and model. The reviewer
stores structured reasons and confidence, and only a `pass` for a verified author
can auto-publish the current revision.

The translation worker uses the same OpenAI-compatible protocol when
`ION_PULSE_TRANSLATION_PROVIDER=openai_compatible` and
`ION_PULSE_TRANSLATION_API_KEY` are set. Without these values source material
remains public and jobs retain the safe retry state instead of inventing a translation.

The API also applies process-local sliding-window limits to registration, sign-in,
password-recovery requests, comments, and reports. Production should additionally
enforce equivalent distributed limits at the edge/load balancer.

### Background work

The worker publishes scheduled materials, then processes AI-review and translation
jobs continuously. Run one worker process beside the API in production; it polls
every 30 seconds when idle (configure `ION_PULSE_WORKER_POLL_SECONDS` as needed):

```bash
uv run python -m ion_pulse.workers.translation
```

## Systemd deployment templates

Templates for both long-running processes are included in `deploy/`:

- `ion-pulse-api.service` starts Uvicorn on the loopback interface. Put a TLS-enabled reverse
  proxy in front of it.
- `ion-pulse-worker.service` runs scheduled publishing and AI jobs.

Before installing, replace `/srv/ion-pulse-api`, `/etc/ion-pulse/api.env`, the `ion-pulse`
user/group, and the `uv` path with values for the target host. The environment file must be
readable only by the service account and contain the production database URL and secrets.
For production, the API refuses to start unless debug is disabled, `ION_PULSE_SITE_URL` uses
HTTPS, `ION_PULSE_SESSION_COOKIE_SECURE=true`, and `ION_PULSE_SESSION_SECRET` is a unique
value of at least 32 characters. A minimal production section in `/etc/ion-pulse/api.env` is:

```dotenv
ION_PULSE_ENVIRONMENT=production
ION_PULSE_DEBUG=false
ION_PULSE_SITE_URL=https://example.com
ION_PULSE_CORS_ORIGINS=["https://example.com"]
ION_PULSE_SESSION_COOKIE_SECURE=true
ION_PULSE_SESSION_SECRET=replace-with-a-unique-random-value-of-at-least-32-characters
```

Then install and start both services:

```bash
sudo install -m 0644 deploy/ion-pulse-api.service /etc/systemd/system/
sudo install -m 0644 deploy/ion-pulse-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ion-pulse-api ion-pulse-worker
```

Before each release, run the pre-flight from the checked-out API directory. It
loads the same protected systemd environment file without printing secrets,
validates all production-only security settings, and fails if the database has
pending Alembic migrations:

```bash
deploy/ion-pulse-preflight.sh /etc/ion-pulse/api.env
```

Confirm the deployment through the reverse proxy with `/api/v1/health` and `/api/v1/ready`.
After each deploy, run the bundled end-to-end smoke check against the public HTTPS origin:

```bash
deploy/ion-pulse-smoke-check.sh https://example.com
```

It checks liveness, database readiness, and both RU/EN public-feed routes through the proxy.

### PostgreSQL backups

The `deploy/ion-pulse-backup.service` and `.timer` templates create a verified
custom-format PostgreSQL dump every day. Add these non-secret settings to
`/etc/ion-pulse/api.env` and create the backup directory for the service account:

```bash
ION_PULSE_BACKUP_DIR=/var/backups/ion-pulse
ION_PULSE_BACKUP_RETENTION_DAYS=14
sudo install -d -o ion-pulse -g ion-pulse -m 0700 /var/backups/ion-pulse
sudo install -m 0644 deploy/ion-pulse-backup.service /etc/systemd/system/
sudo install -m 0644 deploy/ion-pulse-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ion-pulse-backup.timer
sudo systemctl start ion-pulse-backup.service
```

The backup service converts the application's async SQLAlchemy URL to the normal
PostgreSQL URL needed by `pg_dump`, verifies every new dump with `pg_restore --list`,
and only then publishes it under the timestamped filename. Keep the backup directory
outside the deployment directory and copy its encrypted contents to independent storage.

Test restores regularly on a **new disposable database**, never the production one:

```bash
createdb ion_pulse_restore_test
pg_restore --clean --if-exists --no-owner --dbname=ion_pulse_restore_test \
  /var/backups/ion-pulse/ion-pulse-YYYYMMDDTHHMMSSZ.dump
dropdb ion_pulse_restore_test
```

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
