#!/usr/bin/env bash
set -Eeuo pipefail

base_url="${1:?Usage: ion-pulse-smoke-check.sh https://public-host}"
base_url="${base_url%/}"

request() {
  curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "$1"
}

health="$(request "$base_url/api/v1/health")"
ready="$(request "$base_url/api/v1/ready")"
request "$base_url/api/v1/publications/feed?locale=ru&limit=1" >/dev/null
request "$base_url/api/v1/publications/feed?locale=en&limit=1" >/dev/null

if [[ "$health" != *'"status":"ok"'* ]]; then
  echo "Unexpected health response" >&2
  exit 1
fi
if [[ "$ready" != *'"status":"ready"'* || "$ready" != *'"database":"ok"'* ]]; then
  echo "Unexpected readiness response" >&2
  exit 1
fi

echo "Ion Pulse smoke check passed for $base_url"
