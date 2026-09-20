"""Helpers reutilizables para los tests de incidents API."""

from __future__ import annotations


MINIMAL_BODY = {
    "title": "Equipo dañado",
    "description": "El equipo de rayos X presenta una fuga en el panel de control que debe ser revisada.",
    "category": "clinical_equipment",
    "origin": "branch",
    "branch": "austin_north",
}


def seed_incident(
    incidents_table,
    *,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    status: str | None = None,
) -> int:
    """Inserta un incidente directamente en TinyDB y devuelve su doc_id."""
    record = {
        "title": title or MINIMAL_BODY["title"],
        "description": description or MINIMAL_BODY["description"],
        "category": category or MINIMAL_BODY["category"],
        "origin": origin or MINIMAL_BODY["origin"],
        "branch": branch or MINIMAL_BODY["branch"],
        "status": status or "open",
        "created_at": "2025-01-15T10:00:00+00:00",
        "updated_at": "2025-01-15T10:00:00+00:00",
    }
    return incidents_table.insert(record)