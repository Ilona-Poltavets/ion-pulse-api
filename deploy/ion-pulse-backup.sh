#!/usr/bin/env bash
set -Eeuo pipefail

: "${ION_PULSE_DATABASE_URL:?ION_PULSE_DATABASE_URL must be set}"
: "${ION_PULSE_BACKUP_DIR:?ION_PULSE_BACKUP_DIR must be set}"

retention_days="${ION_PULSE_BACKUP_RETENTION_DAYS:-14}"
if ! [[ "$retention_days" =~ ^[0-9]+$ ]]; then
  echo "ION_PULSE_BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
  exit 1
fi

backup_dir="${ION_PULSE_BACKUP_DIR%/}"
database_url="${ION_PULSE_DATABASE_URL/postgresql+asyncpg:/postgresql:}"
timestamp="$(date --utc +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/ion-pulse-$timestamp.dump"

install -d -m 0700 "$backup_dir"
temporary_file="$(mktemp "$backup_dir/.ion-pulse-$timestamp.XXXXXX")"
trap 'rm -f "$temporary_file"' EXIT

pg_dump --format=custom --no-owner --no-privileges --file "$temporary_file" "$database_url"
pg_restore --list "$temporary_file" >/dev/null
chmod 0600 "$temporary_file"
mv "$temporary_file" "$backup_file"
trap - EXIT

find "$backup_dir" -maxdepth 1 -type f -name 'ion-pulse-*.dump' -mtime "+$retention_days" -delete
echo "Created PostgreSQL backup: $backup_file"
