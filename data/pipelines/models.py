"""Modelos SQLAlchemy para el esquema ``reporting`` del pipeline.

Usamos ``sqlalchemy.orm`` directamente para no arrastrar dependencias de
SQLModel (que se usa en ``services/api/``). El pipeline debe poder
ejecutarse sin cargar toda la pila de la API.
"""

from __future__ import annotations

from datetime import datetime, date as date_type
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, Text, Time
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MonthlyClinicSupplyPerformance(Base):
    """Fila de KPI por clínica y mes — tabla de destino del pipeline.

    La clave única ``(clinic_id, month_start)`` es el pilar de la
    idempotencia: el upsert se apoya en este constraint.
    """

    __tablename__ = "monthly_clinic_supply_performance"
    __table_args__ = {"schema": "reporting"}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    clinic_id: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    month_start: Mapped[date_type] = mapped_column(Date, nullable=False)
    total_supply_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    supply_consumption_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    critical_stockout_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    expiry_risk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<MonthlyClinicSupplyPerformance("
            f"clinic_id={self.clinic_id!r}, "
            f"month_start={self.month_start}, "
            f"cost={self.total_supply_cost})>"
        )


class PipelineRun(Base):
    """Registro de ejecución del pipeline — tabla de auditoría.

    Cada corrida del pipeline inserta una fila aquí. El campo ``status``
    refleja el estado final de Prefect.
    """

    __tablename__ = "pipeline_runs"
    __table_args__ = {"schema": "reporting"}

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    flow_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_source: Mapped[str] = mapped_column(
        Text, nullable=False, default="scheduled"
    )
    recalculation_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    invalidates_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reporting.pipeline_runs.run_id"),
        nullable=True,
    )
    month_start: Mapped[date_type] = mapped_column(Date, nullable=False)
    month_end: Mapped[date_type] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    events_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    events_deduplicated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rows_inserted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rows_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    warning_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prefect_flow_run_id: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineRun(run_id={self.run_id}, "
            f"status={self.status!r}, "
            f"month={self.month_start})>"
        )