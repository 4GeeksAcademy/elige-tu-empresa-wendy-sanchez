from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class Country(str, Enum):
    USA = "USA"
    UK = "UK"


class Currency(str, Enum):
    USD = "USD"
    GBP = "GBP"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class SupplierCategory(str, Enum):
    MEDICAL_SUPPLIES = "medical_supplies"
    LABORATORY_SERVICES = "laboratory_services"
    PHARMACEUTICAL = "pharmaceutical"
    CLINICAL_SOFTWARE = "clinical_software"
    IT_INFRASTRUCTURE = "it_infrastructure"
    HR_AND_PAYROLL_SOFTWARE = "hr_and_payroll_software"
    CLEANING_AND_FACILITIES = "cleaning_and_facilities"
    PATIENT_COMMUNICATION = "patient_communication"
    BILLING_AND_CODING_SOFTWARE = "billing_and_coding_software"
    TRAINING_PLATFORMS = "training_platforms"


class ComplianceAgreement(str, Enum):
    BAA = "BAA"
    DPA = "DPA"
    BOTH = "both"


CURRENCY_BY_COUNTRY: dict[Country, Currency] = {
    Country.USA: Currency.USD,
    Country.UK: Currency.GBP,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupplierBase(BaseModel):
    model_config = ConfigDict(use_enum_values=False, str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    country: Country
    categories: list[SupplierCategory] = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    currency: Currency
    status: SupplierStatus = SupplierStatus.ACTIVE
    compliance_agreement: ComplianceAgreement | None = None
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("categories")
    @classmethod
    def reject_duplicate_categories(cls, value: list[SupplierCategory]) -> list[SupplierCategory]:
        if len(set(value)) != len(value):
            raise ValueError("categories no puede contener valores duplicados")
        return value

    @model_validator(mode="after")
    def currency_must_match_country(self) -> "SupplierBase":
        expected = CURRENCY_BY_COUNTRY[self.country]
        if self.currency is not expected:
            raise ValueError(
                f"Un proveedor de '{self.country.value}' debe tener currency "
                f"'{expected.value}', no '{self.currency.value}'"
            )
        return self


class SupplierCreate(SupplierBase):
    """Payload de alta: `updated_at` lo genera el sistema."""


class SupplierReplace(SupplierBase):
    """Payload de reemplazo completo (PUT)."""


class SupplierRateUpdate(BaseModel):
    """Actualización de tarifa: registra un nuevo `updated_at` en el sistema."""

    monthly_rate: float = Field(gt=0)


class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus


class Supplier(SupplierBase):
    """Modelo de respuesta completo: incluye identificador y trazabilidad de tarifa."""

    id: int
    updated_at: datetime
    archived_at: datetime | None = None
    """Momento en que se dejó de trabajar con el proveedor. El registro nunca se borra."""


class SupplierListItem(BaseModel):
    """Modelo de respuesta ligero para listados de proveedores.

    Excluye `notes` (texto libre de hasta 500 caracteres) que no es
    necesario en una vista de listado/tabla. La vista de detalle sigue
    usando `Supplier` completo.
    """
    id: int
    name: str
    country: Country
    categories: list[SupplierCategory]
    monthly_rate: float
    currency: Currency
    status: SupplierStatus
    compliance_agreement: ComplianceAgreement | None = None
    contract_renewal_date: date | None = None
    contact_email: EmailStr | None = None
    updated_at: datetime
    archived_at: datetime | None = None


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class UserCreate(BaseModel):
    """Payload de alta: incluye credenciales y datos opcionales de perfil inicial."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)


class UserUpdate(BaseModel):
    """Payload de actualización de credenciales: `role` sólo lo puede cambiar un admin."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr | None = None
    role: Role | None = None


class User(BaseModel):
    """Modelo persistido en TinyDB: nunca incluye nombre visible ni datos de contacto."""

    id: int
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    role: Role = Role.USER
    created_at: datetime


class UserOut(BaseModel):
    """Modelo de respuesta pública: nunca expone `hashed_password`."""

    id: int
    email: EmailStr
    is_active: bool
    role: Role
    created_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)


class Profile(BaseModel):
    id: int
    user_id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfilePublic(BaseModel):
    """Perfil público: sin claves foráneas internas (`user_id`)."""
    id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class MeResponse(BaseModel):
    email: EmailStr
    role: Role
    profile: ProfilePublic | None = None
    telemetry_user_id: str | None = None


class MessageResponse(BaseModel):
    """Respuesta genérica con un mensaje de texto."""
    message: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ──────────────────────────────────────────────
# Restablecimiento y cambio de contraseña
# ──────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    """Payload para solicitar un restablecimiento de contraseña."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload para restablecer la contraseña con un token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Payload para cambiar la contraseña estando autenticado."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ──────────────────────────────────────────────
# Análisis de incidentes (incidents_analysis.py)
# ──────────────────────────────────────────────


class AnalysisRecordItem(BaseModel):
    """Una fila inválida del CSV con sus razones de rechazo."""
    row: int
    reasons: list[str]


class AnalysisPercentages(BaseModel):
    categories: dict[str, float]
    statuses: dict[str, float]
    countries: dict[str, float]


class AnalysisSummary(BaseModel):
    """Resumen completo del análisis de un CSV de incidentes."""
    total: int
    valid: int
    invalid: int
    invalid_breakdown: dict[str, int]
    category_counts: dict[str, int]
    status_counts: dict[str, int]
    country_counts: dict[str, int]
    score_counts: dict[str, int]
    scored_cases: int
    closed_cases: int
    average_score: float
    percentages: AnalysisPercentages


class AnalysisResponse(BaseModel):
    """Respuesta del análisis de incidentes."""
    source_file: str
    summary: AnalysisSummary


class RootResponse(BaseModel):
    """Endpoint raíz de descubrimiento de la API."""
    service: str
    docs: str
    analyze: str
    analyze_sample: str
    export: str
    suppliers: str
    suppliers_by_country: str
    suppliers_by_category: str


# ─────────────────────────────────────────────────────────────────────
# SQLModel ORM — Inventory tables (Supabase)
# ─────────────────────────────────────────────────────────────────────

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def utc_now_sql() -> datetime:
    return datetime.now(timezone.utc)


class MedicalSupply(SQLModel, table=True):
    """Suministro médico — equivalente a Product del README."""
    __tablename__: str = "medical_supplies"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, nullable=False)
    sku: str = Field(max_length=50, unique=True, nullable=False, index=True)
    category: str = Field(max_length=50, nullable=False)  # ppe, wound_care, diagnostics, medications, consumables
    unit: str = Field(max_length=20, nullable=False)       # box, unit, pack, vial
    country: str = Field(max_length=2, nullable=False)      # US / UK
    expiry_date: date | None = Field(default=None)


class SupplyDelivery(SQLModel, table=True):
    """Entrega de proveedor — equivalente a InboundOrder del README."""
    __tablename__: str = "supply_deliveries"

    id: Optional[int] = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="medical_supplies.id", nullable=False, index=True)
    quantity: int = Field(nullable=False)
    vendor_name: str = Field(max_length=200, nullable=False)
    clinic_id: int = Field(nullable=False)  # 1–12; no FK
    created_at: datetime = Field(default_factory=utc_now_sql, nullable=False)
    user_uuid: str = Field(max_length=36, nullable=False)  # UUID del usuario en TinyDB


class SupplyConsumption(SQLModel, table=True):
    """Consumo clínico — equivalente a OutboundOrder del README."""
    __tablename__: str = "supply_consumptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="medical_supplies.id", nullable=False, index=True)
    quantity: int = Field(nullable=False)
    consumption_type: str = Field(max_length=20, nullable=False)  # clinical_use / expiry_waste
    department: str | None = Field(default=None, max_length=32)
    clinic_id: int = Field(nullable=False)  # 1–12; no FK
    created_at: datetime = Field(default_factory=utc_now_sql, nullable=False)
    user_uuid: str = Field(max_length=36, nullable=False)  # UUID del usuario en TinyDB


class StockPolicy(SQLModel, table=True):
    supply_id: int = Field(foreign_key="medical_supplies.id", primary_key=True)
    clinic_id: int = Field(primary_key=True)
    minimum_quantity: int
    version: str = Field(max_length=32)


class InventoryAlertState(SQLModel, table=True):
    key: str = Field(primary_key=True, max_length=160)


# ─────────────────────────────────────────────────────────────────────
# Telemetry storage (Supabase — immutable, write-only)
# ─────────────────────────────────────────────────────────────────────


class TelemetryEventDB(SQLModel, table=True):
    """Telemetry event — immutable fact stored in Supabase.

    Maps 1:1 from the TelemetryEvent Pydantic model.
    - Write-only: never updated or deleted after insertion.
    - The `tags` column stores the `properties` dict from the envelope
      (only allowlist keys) as JSONB for GIN-indexed queries.
    - `event_id` is the UUID from the producer, used for idempotency.
    """
    __tablename__: str = "telemetry_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(max_length=36, nullable=False, unique=True, index=True)
    """UUID v4 from the producer — idempotency key."""
    timestamp: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    """ISO 8601 with timezone — post-commit for write events."""
    session_id: str = Field(max_length=128, nullable=False)
    """Opaque session pseudonym."""
    user_id: str = Field(max_length=128, nullable=False)
    """HMAC pseudonym of the internal user ID."""
    event_type: str = Field(max_length=64, nullable=False, index=True)
    """Registered event type in snake_case (entidad_accion)."""
    schema_version: str = Field(max_length=16, nullable=False)
    """Semantic version of the event contract."""
    request_id: str = Field(max_length=128, nullable=False)
    """Correlation ID propagated frontend→proxy→API→logs."""
    tags: dict | None = Field(default=None)
    """Properties payload — only allowlist keys, enables GIN-indexed queries on PostgreSQL."""
    created_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        default_factory=utc_now_sql,
        nullable=False,
    )
    """Server-side insertion timestamp (not the event timestamp)."""
