"""Pipeline de análisis de telemetría — métricas operacionales.

Cada función es independiente (sin efectos secundarios) y sigue el orden:
  cargar (SQL) → refinar (Pandas) → convertir tipos → agrupar → agregar → servir

Todas reciben start_date/end_date y una engine de SQLAlchemy.
Devuelven list[dict] — directamente serializable a JSON.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text as sa_text


# ── Clasificación de eventos ───────────────────────────────────────────
# Eventos que por su propia naturaleza representan un error o fallo técnico.
# Usados por error_rate_by_type() para marcar cada fila como is_error.
ERROR_EVENT_TYPES = frozenset({
    "api_request_failed",
    "api_dependency_failed",
    "api_retry_exhausted",
    "auth_login_failed",
    "auth_authorization_denied",
    "auth_rate_limit_triggered",
    "auth_token_validation_failed",
    "frontend_error_captured",
    "service_health_check_failed",
    "telemetry_delivery_failed",
    "telemetry_event_dropped",
    "direct_stock_edit_rejected",
    "inventory_order_rejected",
    "inventory_order_validation_failed",
    "inventory_form_validation_failed",
    "backoffice_navigation_error",
})


# ── Helpers ────────────────────────────────────────────────────────────


def _load_events(engine, start: datetime, end: datetime) -> pd.DataFrame:
    """Carga event_type y timestamp de todas las filas en el rango."""
    query = sa_text("""
        SELECT event_type, timestamp
        FROM telemetry_events
        WHERE timestamp >= :start AND timestamp < :end
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start": start, "end": end}).fetchall()
    return pd.DataFrame(rows, columns=["event_type", "timestamp"])


# ── Métrica 1: Volumen de eventos por día ─────────────────────────────


def events_per_day(engine, start_date: datetime, end_date: datetime) -> list[dict]:
    """Volumen de eventos por día en el período.

    Responde: ¿cuántos eventos genera el sistema cada día?
    Dimensión temporal: día calendario en UTC.
    """
    df = _load_events(engine, start_date, end_date)
    if df.empty:
        return []

    # Convertir tipos ANTES de agrupar — requisito no negociable
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["date"] = df["timestamp"].dt.date

    result = (
        df.groupby("date")
        .size()
        .reset_index(name="event_count")
        .sort_values("date")
    )
    result["date"] = result["date"].astype(str)
    return result.to_dict(orient="records")


# ── Métrica 2: Tasa de error por tipo de evento ───────────────────────


def error_rate_by_type(engine, start_date: datetime, end_date: datetime) -> list[dict]:
    """Tasa de error por event_type.

    Clasifica cada evento como error o normal según ERROR_EVENT_TYPES,
    luego agrupa por event_type y calcula total, errores y tasa.
    Responde: ¿qué tipos de evento concentran los fallos del sistema?
    """
    df = _load_events(engine, start_date, end_date)
    if df.empty:
        return []

    # Convertir tipos ANTES de cualquier operación
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Flags derivados: is_error
    df["is_error"] = df["event_type"].isin(ERROR_EVENT_TYPES)

    result = (
        df.groupby("event_type")
        .agg(total_events=("event_type", "count"), error_events=("is_error", "sum"))
        .reset_index()
    )
    result["error_rate_pct"] = (result["error_events"] / result["total_events"] * 100).round(2)
    result = result.sort_values("total_events", ascending=False)
    return result.to_dict(orient="records")


# ── Métrica 3: Percentiles de latencia por ruta ───────────────────────


def latency_percentiles_by_route(
    engine, start_date: datetime, end_date: datetime
) -> list[dict]:
    """Percentiles de latencia (P50, P95, P99) por ruta y método.

    Extrae exclusivamente eventos api_latency_recorded.
    Las dimensiones route_template y method se obtienen del JSONB tags.
    Responde: ¿qué rutas son las más lentas y cómo se distribuye su latencia?
    """
    query = sa_text("""
        SELECT
            tags ->> 'route_template'  AS route_template,
            tags ->> 'method'          AS method,
            CAST(tags ->> 'duration_ms' AS NUMERIC) AS duration_ms,
            timestamp
        FROM telemetry_events
        WHERE event_type = 'api_latency_recorded'
          AND timestamp >= :start AND timestamp < :end
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start": start_date, "end": end_date}).fetchall()

    df = pd.DataFrame(
        rows, columns=["route_template", "method", "duration_ms", "timestamp"]
    )
    if df.empty:
        return []

    # Convertir tipos
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # duration_ms llega como Decimal desde PostgreSQL → convertir a float64
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")

    # Refinar: descartar filas con dimensiones nulas (tags sin campo esperado)
    df = df.dropna(subset=["route_template", "method", "duration_ms"])

    # Agrupar por ruta y método, agregar estadísticos de latencia
    result = (
        df.groupby(["route_template", "method"])
        .agg(
            count=("duration_ms", "count"),
            mean_ms=("duration_ms", "mean"),
            min_ms=("duration_ms", "min"),
            max_ms=("duration_ms", "max"),
            p50_ms=("duration_ms", lambda x: x.quantile(0.50)),
            p95_ms=("duration_ms", lambda x: x.quantile(0.95)),
            p99_ms=("duration_ms", lambda x: x.quantile(0.99)),
        )
        .reset_index()
    )
    for col in ["mean_ms", "min_ms", "max_ms", "p50_ms", "p95_ms", "p99_ms"]:
        result[col] = result[col].round(1)
    result = result.sort_values("count", ascending=False)
    return result.to_dict(orient="records")


# ── Métrica 4: Distribución de tipos de evento (bonus) ────────────────


def event_type_distribution(
    engine, start_date: datetime, end_date: datetime
) -> list[dict]:
    """Distribución porcentual de event_type sobre el total del período.

    Responde: ¿qué tipos de evento dominan el tráfico del sistema?
    """
    df = _load_events(engine, start_date, end_date)
    if df.empty:
        return []

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    result = (
        df.groupby("event_type")
        .agg(count=("event_type", "count"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    total = result["count"].sum()
    result["percentage"] = (result["count"] / total * 100).round(2)
    return result.to_dict(orient="records")


# ── Pipeline completo ─────────────────────────────────────────────────


def run_all(engine, start_date: datetime, end_date: datetime) -> dict:
    """Ejecuta todas las métricas del pipeline y devuelve un dict agrupado.

    Esta es la función que el endpoint llama. Cada métrica se computa
    de forma independiente para mantener la separación de responsabilidades
    y facilitar la depuración individual.
    """
    return {
        "events_per_day": events_per_day(engine, start_date, end_date),
        "error_rate_by_type": error_rate_by_type(engine, start_date, end_date),
        "latency_percentiles_by_route": latency_percentiles_by_route(
            engine, start_date, end_date
        ),
        "event_type_distribution": event_type_distribution(
            engine, start_date, end_date
        ),
    }