#!/usr/bin/env sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$repo_root"

# .env is loaded by algo_core_service.main via algo_sdk.
src_path="$repo_root/src"
if [ -z "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$src_path"
else
  case ":$PYTHONPATH:" in
    *":$src_path:"*) ;;
    *) export PYTHONPATH="$src_path:$PYTHONPATH" ;;
  esac
fi

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

if [ -x "$repo_root/.venv/bin/python" ]; then
  exec "$repo_root/.venv/bin/python" -m algo_core_service.main
fi
exec python -m algo_core_service.main
