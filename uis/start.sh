#!/bin/sh
# ── HealthCore — start.sh ──────────────────────────────────────────────
# Arranca ambos frontends Next.js con recarga en caliente.
# Cada uno escucha en un puerto distinto dentro del contenedor.
# Usa SERVICE_* para los puertos, o defaults: 3000 (website), 3001 (backoffice).

set -e

WEBSITE_PORT="${SERVICE_WEBSITE_PORT:-3000}"
BACKOFFICE_PORT="${SERVICE_BACKOFFICE_PORT:-3001}"

echo "→ Arrancando website en puerto ${WEBSITE_PORT}..."
cd /workspace/uis/website && npm run dev -- --port "${WEBSITE_PORT}" &
PID_WEBSITE=$!

echo "→ Arrancando backoffice en puerto ${BACKOFFICE_PORT}..."
cd /workspace/uis/backoffice && npm run dev -- --port "${BACKOFFICE_PORT}" &
PID_BACKOFFICE=$!

# Trap para parar ambos procesos al detener el contenedor
trap 'echo "→ Parando servicios..."; kill $PID_WEBSITE $PID_BACKOFFICE 2>/dev/null; exit 0' SIGTERM SIGINT

echo "✓ Interfaces operativas: website=:${WEBSITE_PORT} backoffice=:${BACKOFFICE_PORT}"
echo "   Esperando cambios (hot-reload activo)..."

# Esperar a que cualquiera de los dos procesos termine
wait