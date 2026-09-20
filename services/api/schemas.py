"""Schemas Pydantic de request y response para el módulo de inventario.

Totalmente separados de los modelos ORM (SQLModel). Nunca se devuelve
un objeto ORM directamente desde un endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── MedicalSupply ─────────────────────────────────────────────────────


class MedicalSupplyCreate(BaseModel):
    """Payload para crear un nuevo suministro médico."""
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=50)
    unit: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=2, max_length=2)

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        v = v.upper()
        if v not in ("US", "UK"):
            raise ValueError("country must be 'US' or 'UK'")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"ppe", "wound_care", "diagnostics", "medications", "consumables"}
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}")
        return v

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        allowed = {"box", "unit", "pack", "vial"}
        if v not in allowed:
            raise ValueError(f"unit must be one of {allowed}")
        return v


class MedicalSupplyResponse(BaseModel):
    """Respuesta pública de un suministro con su stock calculado."""
    id: int
    name: str
    sku: str
    category: str
    unit: str
    country: str
    current_stock: int = 0


# ── SupplyDelivery ────────────────────────────────────────────────────


class SupplyDeliveryCreate(BaseModel):
    """Payload para registrar una entrega de proveedor (inbound order)."""
    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    vendor_name: str = Field(min_length=1, max_length=200)
    clinic_id: int = Field(ge=1, le=12)


class SupplyDeliveryResponse(BaseModel):
    """Respuesta de una orden de entrada."""
    id: int
    supply_id: int
    quantity: int
    vendor_name: str
    clinic_id: int
    created_at: datetime
    user_uuid: str


# ── SupplyConsumption ─────────────────────────────────────────────────


class SupplyConsumptionCreate(BaseModel):
    """Payload para registrar un consumo clínico (outbound order)."""
    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    consumption_type: str = Field(min_length=1, max_length=20)
    clinic_id: int = Field(ge=1, le=12)

    @field_validator("consumption_type")
    @classmethod
    def validate_consumption_type(cls, v: str) -> str:
        allowed = {"clinical_use", "expiry_waste"}
        if v not in allowed:
            raise ValueError(f"consumption_type must be one of {allowed}")
        return v


class SupplyConsumptionResponse(BaseModel):
    """Respuesta de una orden de salida."""
    id: int
    supply_id: int
    quantity: int
    consumption_type: str
    clinic_id: int
    created_at: datetime
    user_uuid: str


# ── Order listing ─────────────────────────────────────────────────────


class OrderItem(BaseModel):
    """Elemento individual en la lista combinada de órdenes."""
    id: int
    type: str  # "delivery" | "consumption"
    supply_id: int
    supply_name: str
    supply_sku: str
    quantity: int
    detail: str  # vendor_name o consumption_type según el tipo
    clinic_id: int
    created_at: datetime
    user_uuid: str


class OrderListResponse(BaseModel):
    orders: list[OrderItem]