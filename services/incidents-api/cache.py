"""Caché en memoria con TTL para la Incidents API.

Comparte la misma implementación que services/api/cache.py pero con su
propia instancia singleton para evitar acoplamiento entre servicios.

Estrategia:
  - Almacenamiento: dict[clave, (timestamp_expiracion, valor)]
  - TTL configurable por endpoint
  - Invalidación manual con prefijo
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("incidents-api.cache")


class MemoryCache:
    """Caché en memoria con TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    def invalidate(self, prefix: str) -> int:
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]
        count = len(keys_to_delete)
        if count:
            logger.debug("Cache invalidated: prefix='%s' (%d entries)", prefix, count)
        return count


# ── Instancia singleton ──────────────────────────────────────────────
cache = MemoryCache()