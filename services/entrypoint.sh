#!/bin/sh
# ── HealthCore — entrypoint.sh ─────────────────────────────────────────
# Arranca el servicio FastAPI correspondiente según SERVICE_NAME.
# SERVICE_NAME puede ser "api" (puerto 8000) o "incidents-api" (puerto 8010).
# El puerto se sobreescribe con la variable PORT si está definida.

set -e

SERVICE_NAME="${SERVICE_NAME:-api}"

case "${SERVICE_NAME}" in
  api)
    APP_DIR="/workspace/services/api"
    APP_MODULE="main:app"
    DEFAULT_PORT=8000
    ;;
  incidents-api)
    APP_DIR="/workspace/services/incidents-api"
    APP_MODULE="main:app"
    DEFAULT_PORT=8010
    ;;
  *)
    echo "ERROR: SERVICE_NAME desconocido: ${SERVICE_NAME}"
    echo "Valores válidos: api, incidents-api"
    exit 1
    ;;
esac

PORT="${PORT:-${DEFAULT_PORT}}"

echo "→ Arrancando ${SERVICE_NAME} en puerto ${PORT} (reload activo)..."
cd "${APP_DIR}"

exec uvicorn \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --reload \
    --reload-dir /workspace/services \
    "${APP_MODULE}"