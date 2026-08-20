# Ion Pulse: release checklist

Use this checklist on the production host. It deliberately contains no secret
values; keep those only in `/etc/ion-pulse/api.env`, readable by the service
account.

## Before the maintenance window

- [ ] The deployed API revision and the `ion-pulse-web` revision have passed
  their respective CI checks.
- [ ] A PostgreSQL 16+ database, a non-root `ion-pulse` service account, and
  `/srv/ion-pulse-api` / `/srv/ion-pulse-web` are present.
- [ ] `/etc/ion-pulse/api.env` is mode `0600` and contains a unique session
  secret, production HTTPS site URL, secure cookie flag, database URL, and CORS
  origin. Configure SMTP and AI providers there only when they are ready.
- [ ] DNS points the public hostname to this host and a valid TLS certificate
  is available.

## Deploy

1. Install API dependencies and apply schema changes:

   ```bash
   cd /srv/ion-pulse-api
   uv sync --frozen
   uv run --env-file /etc/ion-pulse/api.env alembic upgrade head
   deploy/ion-pulse-preflight.sh /etc/ion-pulse/api.env
   ```

2. Build the same-origin web bundle without `VITE_API_URL`:

   ```bash
   cd /srv/ion-pulse-web
   npm ci
   npm run build
   ```

3. Install the provided API, worker, backup service/timer, Nginx server, and
   rate-limit templates. Replace all documented path, account, hostname and TLS
   placeholders before enabling them. Validate Nginx first:

   ```bash
   sudo nginx -t
   sudo systemctl daemon-reload
   sudo systemctl restart ion-pulse-api ion-pulse-worker
   sudo systemctl enable --now ion-pulse-backup.timer
   sudo systemctl reload nginx
   ```

## Verify and retain

- [ ] `systemctl status ion-pulse-api ion-pulse-worker` reports both services
  active with no restart loop.
- [ ] `systemctl start ion-pulse-backup.service` creates a verified dump;
  copy encrypted backups to independent storage.
- [ ] Run the public check from a network that reaches the TLS hostname:

  ```bash
  /srv/ion-pulse-api/deploy/ion-pulse-smoke-check.sh https://example.com
  ```

- [ ] Verify registration, login, author submission, editor publication, EN/RU
  reading, comment/report moderation and password recovery using a disposable
  account.
- [ ] Restore the newest backup into a new disposable database before declaring
  the release complete.

## Roll back

Keep the prior API/web revision and its release note available. If the smoke
check fails after a deploy, stop the new services, restore the previous code,
and restart them. Do not run an Alembic downgrade against production without a
tested restore plan: restore the verified database backup instead when schema
rollback is required.
