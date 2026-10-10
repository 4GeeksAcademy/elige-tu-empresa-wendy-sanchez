"""Caché en memoria con TTL para la aplicación FastAPI.

Usa un diccionario simple en proceso. No requiere Redis ni dependencias externas.
Estrategia:
  - Almacenamiento: dict[clave, (timestamp_expiracion, valor)]
  - TTL configurable por endpoint
  - Invalidación manual: invalidate() borra claves que coinciden con un prefijo
  - Thread-safe para operaciones de lectura/escritura básicas

Intercambio frescura/rendimiento documentado:
  - Un dato cacheado está potencialmente desactualizado por hasta TTL segundos.
  - Elegimos TTL según la frecuencia de cambio de los datos subyacentes,
    no por comodidad.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger("api.cache")


class MemoryCache:
    """Caché en memoria con TTL.

    Para cada clave almacena una tupla (expires_at, value).
    La expiración se evalúa en el momento de la lectura, no en background.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Retorna el valor si existe y no ha expirado. Si expiró, lo borra."""
        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Almacena un valor con expiración."""
        expires_at = time.monotonic() + ttl_seconds
        self._store[key] = (expires_at, value)

    def age_ms(self, key: str, ttl_seconds: int) -> int:
        entry = self._store.get(key)
        return max(0, round((time.monotonic() - (entry[0] - ttl_seconds)) * 1000)) if entry else 0

    def invalidate(self, prefix: str) -> int:
        """Invalida todas las claves que comiencen con `prefix`.

        Returns:
            Número de claves eliminadas.
        """
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]
        count = len(keys_to_delete)
        if count:
            logger.debug("Cache invalidated: prefix='%s' (%d entries)", prefix, count)
        return count

    def invalidate_all(self) -> int:
        """Invalida toda la caché."""
        count = len(self._store)
        self._store.clear()
        if count:
            logger.debug("Cache fully invalidated (%d entries)", count)
        return count


# ── Instancia singleton ──────────────────────────────────────────────
# Todas las rutas comparten la misma caché.
cache = MemoryCache()


# ── Decorador helper ─────────────────────────────────────────────────


def cached(ttl_seconds: int, key_prefix: str) -> Callable:
    """Decorador para cachear la respuesta de un endpoint.

    Uso:
        @router.get("/products")
        @cached(ttl_seconds=30, key_prefix="inventory:products")
        def list_products(...):
            ...

    La clave de caché se construye como "{key_prefix}:{args_kwargs_hash}".
    Para endpoints con parámetros, la clave incluye los valores serializados.
    """
    from functools import wraps

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Construir clave única: prefijo + args serializados
            cache_key = f"{key_prefix}:{hash(tuple(args))}:{hash(frozenset(kwargs.items()))}"

            existing = cache.get(cache_key)
            if existing is not None:
                logger.debug("Cache HIT: %s", cache_key)
                return existing

            logger.debug("Cache MISS: %s", cache_key)
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            return result

        return wrapper

    return decorator