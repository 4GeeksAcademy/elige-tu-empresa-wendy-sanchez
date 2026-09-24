# ── HealthCore — UIs Dockerfile (website + backoffice) ──────────────────
# Imagen multi-etapa: instala dependencias de ambos frontends Next.js
# y arranca ambos con recarga en caliente via start.sh.
#
# Los bind mounts en docker-compose.yml sobreescriben /app en runtime,
# por lo que esta imagen solo se usa para el setup de dependencias y
# config base.

FROM node:22-alpine AS base

# ── Build-time args ────────────────────────────────────────────────────
ARG WORKSPACE=/workspace
WORKDIR ${WORKSPACE}

# ── 1. Instalar dependencias del website ───────────────────────────────
FROM base AS deps-website
COPY uis/website/package.json uis/website/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts

# ── 2. Instalar dependencias del backoffice ────────────────────────────
FROM base AS deps-backoffice
COPY uis/backoffice/package.json uis/backoffice/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts

# ── 3. Etapa final ─────────────────────────────────────────────────────
FROM base AS runner

# Replicar la estructura de monorepo dentro del contenedor
COPY --from=deps-website ${WORKSPACE}/node_modules ./uis/website/node_modules
COPY --from=deps-backoffice ${WORKSPACE}/node_modules ./uis/backoffice/node_modules

# Copiar código fuente (los bind mounts del compose lo sobrescriben en dev)
COPY uis/website ./uis/website
COPY uis/backoffice ./uis/backoffice

# Copiar paquetes compartidos si existen
COPY packages/shared ./packages/shared

# Script de arranque
COPY uis/start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

EXPOSE 3000 3001

CMD ["start.sh"]