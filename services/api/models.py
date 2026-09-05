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
    """Modelo de respuesta: incluye identificador y trazabilidad de tarifa."""

    id: int
    updated_at: datetime
    archived_at: datetime | None = None
    """Momento en que se dejó de trabajar con el proveedor. El registro nunca se borra."""


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


class MeResponse(BaseModel):
    email: EmailStr
    role: Role
    profile: Profile | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
