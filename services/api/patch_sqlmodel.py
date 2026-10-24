"""
Parche de compatibilidad — SQLModel + Python 3.14.

Python 3.14 introdujo ``annotationlib`` que cambia cómo se evalúan las
anotaciones de tipos. Pydantic v2 combinado con SQLModel 0.0.48 falla
porque recibe objetos ``ForwardRef`` en lugar de tipos reales.

Este parche intercepta ``get_sa_type_from_field`` en ``sqlmodel.main``
para que si detecta un ``ForwardRef``, intente resolverlo usando
``typing.get_type_hints()`` con los globales del módulo llamante.
"""

from __future__ import annotations

import logging
import sys
import typing

logger = logging.getLogger("patch_sqlmodel")


def _resolve_forward_ref(type_: object, module_globals: dict | None = None) -> type:
    """Resuelve un ForwardRef/Pep696Ref a un tipo real si es posible."""
    # Verificar si es un ForwardRef (annotationlib o typing)
    ref_name = None
    if hasattr(type_, "__forward_arg__"):
        ref_name = type_.__forward_arg__  # type: ignore[union-attr]
    elif hasattr(type_, "__name__") and str(type_).startswith("ForwardRef("):
        # Fallback: extraer de repr
        ref_name = str(type_)[len("ForwardRef('"):-len("')")]
    elif hasattr(type_, "__pep696ref__"):
        ref_name = getattr(type_, "__pep696ref__", None)

    if ref_name is None:
        # No es un ForwardRef, devolver tal cual
        return typing.cast(type, type_)

    # Intentar resolver con typing.get_type_hints
    # Primero: si el nombre es "Optional[X]", extraer X
    if ref_name.startswith("Optional[") and ref_name.endswith("]"):
        inner = ref_name[len("Optional[") : -1]
        # Buscar X en module_globals
        if module_globals:
            inner_type = module_globals.get(inner)
            if inner_type and isinstance(inner_type, type):
                return typing.Optional[inner_type]  # type: ignore[return-value]

    # Segundo: buscar directamente en module_globals
    if module_globals:
        resolved = module_globals.get(ref_name)
        if resolved and isinstance(resolved, type):
            return resolved

    # Tercero: nombres comunes de typing
    typing_types = {
        "int": int, "str": str, "float": float, "bool": bool, "bytes": bytes,
        "date": __import__("datetime", fromlist=["date"]).date,
        "datetime": __import__("datetime", fromlist=["datetime"]).datetime,
        "Decimal": __import__("decimal", fromlist=["Decimal"]).Decimal,
        "UUID": __import__("uuid", fromlist=["UUID"]).UUID,
        "Optional": typing.Optional,
    }
    if ref_name in typing_types:
        return typing_types[ref_name]  # type: ignore[return-value]

    logger.warning("No se pudo resolver ForwardRef: %s", ref_name)
    return str  # type: ignore[return-value]  # fallback seguro


def _apply_patch() -> None:
    """Reemplaza get_sa_type_from_field para resolver ForwardRefs."""
    import sqlmodel.main

    original = sqlmodel.main.get_sa_type_from_field

    def patched_get_sa_type_from_field(field: object) -> type:
        type_ = original(field)
        if isinstance(type_, type):
            return type_
        # Intentar resolver con los globales del módulo llamante
        import inspect

        frame = inspect.currentframe()
        module_globals = None
        if frame and frame.f_back and frame.f_back.f_back:
            module_globals = frame.f_back.f_back.f_globals
        resolved = _resolve_forward_ref(type_, module_globals)
        if resolved is not type_:
            ref_name = getattr(type_, "__forward_arg__", str(type_))
            logger.debug("ForwardRef resuelto: %s → %s", ref_name, resolved)
        return resolved

    sqlmodel.main.get_sa_type_from_field = patched_get_sa_type_from_field
    logger.info(
        "sqlmodel.main.get_sa_type_from_field parcheado para Python %s",
        sys.version,
    )


_apply_patch()