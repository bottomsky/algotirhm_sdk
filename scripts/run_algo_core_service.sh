#!/usr/bin/env sh
set -eu

if [ -z "${SERVICE_INSTANCE_ID:-}" ]; then
  name="${SERVICE_NAME:-algo-service}"
  if [ -r /proc/sys/kernel/random/uuid ]; then
    uuid="$(cat /proc/sys/kernel/random/uuid)"
  else
    uuid="$(python - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
  fi
  suffix="$(printf '%s' "$uuid" | tr -d '-' | cut -c1-8)"
  export SERVICE_INSTANCE_ID="${name}-${suffix}"
fi

exec python -m algo_core_service.main
