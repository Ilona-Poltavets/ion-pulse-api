#!/usr/bin/env bash
set -Eeuo pipefail

environment_file="${1:?Usage: ion-pulse-preflight.sh /etc/ion-pulse/api.env}"

if [[ ! -f "$environment_file" ]]; then
  echo "Environment file not found: $environment_file" >&2
  exit 1
fi

# `uv --env-file` parses dotenv syntax without sourcing the file as shell code.
# Settings validates the production-only invariants without printing any secrets.
uv run --env-file "$environment_file" python -c '
from ion_pulse.core.config import get_settings

settings = get_settings()
if settings.environment != "production":
    raise SystemExit("ION_PULSE_ENVIRONMENT must be production for a release pre-flight")
print(f"Production settings valid for {settings.site_url}")
'

# Fail before a restart if source and the target database disagree about schema.
uv run --env-file "$environment_file" alembic check

echo "Ion Pulse production pre-flight passed"
