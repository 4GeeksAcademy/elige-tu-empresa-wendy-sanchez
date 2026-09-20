"""Router de inventario — todos los endpoints bajo /inventory.

Requiere autenticación JWT en todas las operaciones de escritura y lectura
(según requisitos de HealthCore).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from database import get_db
from models import MedicalSupply, SupplyConsumption, SupplyDelivery
from schemas import (
    MedicalSupplyCreate,
    MedicalSupplyResponse,
    OrderItem,
    OrderListResponse,
    SupplyConsumptionCreate,
    SupplyConsumptionResponse,
    SupplyDeliveryCreate,
    SupplyDeliveryResponse,
)
from security import get_current_user

router = APIRouter(prefix="/inventory", tags=["inventory"])


# ── Helpers ────────────────────────────────────────────────────────────


def _compute_current_stock(
    supply_id: int, session: Session
) -> int:
    """Calcula current_stock = SUM(deliveries) - SUM(consumptions) para un supply."""
    total_in = (
        session.exec(
            select(func.coalesce(func.sum(SupplyDelivery.quantity), 0)).where(
                SupplyDelivery.supply_id == supply_id
            )
        ).one()
        or 0
    )
    total_out = (
        session.exec(
            select(func.coalesce(func.sum(SupplyConsumption.quantity), 0)).where(
                SupplyConsumption.supply_id == supply_id
            )
        ).one()
        or 0
    )
    return int(total_in) - int(total_out)


# ── Products / MedicalSupply ──────────────────────────────────────────


@router.get("/products", response_model=list[MedicalSupplyResponse])
def list_products(
    session: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> list[MedicalSupplyResponse]:
    """Lista todos los suministros médicos con su current_stock calculado."""
    supplies = session.exec(select(MedicalSupply)).all()
    result: list[MedicalSupplyResponse] = []
    for s in supplies:
        stock = _compute_current_stock(s.id, session)
        result.append(
            MedicalSupplyResponse(
                id=s.id,
                name=s.name,
                sku=s.sku,
                category=s.category,
                unit=s.unit,
                country=s.country,
                current_stock=stock,
            )
        )
    return result


@router.post("/products", response_model=MedicalSupplyResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: MedicalSupplyCreate,
    session: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> MedicalSupplyResponse:
    """Crea un nuevo suministro médico. El stock inicial es siempre 0."""
    # Verificar que no exista un SKU duplicado
    existing = session.exec(
        select(MedicalSupply).where(MedicalSupply.sku == payload.sku)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un suministro con el SKU '{payload.sku}'",
        )

    supply = MedicalSupply(
        name=payload.name,
        sku=payload.sku,
        category=payload.category,
        unit=payload.unit,
        country=payload.country,
    )
    session.add(supply)
    session.commit()
    session.refresh(supply)

    return MedicalSupplyResponse(
        id=supply.id,
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=0,
    )


@router.get("/products/{supply_id}", response_model=MedicalSupplyResponse)
def get_product(
    supply_id: int,
    session: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> MedicalSupplyResponse:
    """Obtiene un suministro por ID con su stock actual calculado."""
    supply = session.get(MedicalSupply, supply_id)
    if supply is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply with id {supply_id} not found",
        )

    stock = _compute_current_stock(supply.id, session)
    return MedicalSupplyResponse(
        id=supply.id,
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=stock,
    )


# ── Orders — Inbound (SupplyDelivery) ─────────────────────────────────


@router.post(
    "/orders/inbound",
    response_model=SupplyDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    payload: SupplyDeliveryCreate,
    session: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SupplyDeliveryResponse:
    """Registra una entrega de proveedor (incrementa stock)."""
    supply = session.get(MedicalSupply, payload.supply_id)
    if supply is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply with id {payload.supply_id} not found",
        )

    delivery = SupplyDelivery(
        supply_id=payload.supply_id,
        quantity=payload.quantity,
        vendor_name=payload.vendor_name,
        clinic_id=payload.clinic_id,
        user_uuid=str(current_user.id),
    )
    session.add(delivery)
    session.commit()
    session.refresh(delivery)

    return SupplyDeliveryResponse(
        id=delivery.id,
        supply_id=delivery.supply_id,
        quantity=delivery.quantity,
        vendor_name=delivery.vendor_name,
        clinic_id=delivery.clinic_id,
        created_at=delivery.created_at,
        user_uuid=delivery.user_uuid,
    )


# ── Orders — Outbound (SupplyConsumption) ─────────────────────────────


@router.post(
    "/orders/outbound",
    response_model=SupplyConsumptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound_order(
    payload: SupplyConsumptionCreate,
    session: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SupplyConsumptionResponse:
    """Registra un consumo clínico (reduce stock).

    Rechaza la operación si resultara en stock negativo (HTTP 400).
    """
    supply = session.get(MedicalSupply, payload.supply_id)
    if supply is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply with id {payload.supply_id} not found",
        )

    # Calcular stock disponible antes de registrar
    available = _compute_current_stock(payload.supply_id, session)
    if available < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock for supply '{supply.name}'. "
                f"Available: {available}, requested: {payload.quantity}."
            ),
        )

    consumption = SupplyConsumption(
        supply_id=payload.supply_id,
        quantity=payload.quantity,
        consumption_type=payload.consumption_type,
        clinic_id=payload.clinic_id,
        user_uuid=str(current_user.id),
    )
    session.add(consumption)
    session.commit()
    session.refresh(consumption)

    return SupplyConsumptionResponse(
        id=consumption.id,
        supply_id=consumption.supply_id,
        quantity=consumption.quantity,
        consumption_type=consumption.consumption_type,
        clinic_id=consumption.clinic_id,
        created_at=consumption.created_at,
        user_uuid=consumption.user_uuid,
    )


# ── List all orders ───────────────────────────────────────────────────


@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    session: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> OrderListResponse:
    """Lista todas las entregas y consumos con datos del suministro."""
    items: list[OrderItem] = []

    # Delivery orders
    deliveries = session.exec(
        select(SupplyDelivery, MedicalSupply)
        .join(MedicalSupply, SupplyDelivery.supply_id == MedicalSupply.id)
        .order_by(SupplyDelivery.created_at.desc())
    ).all()

    for delivery, supply in deliveries:
        items.append(
            OrderItem(
                id=delivery.id,
                type="delivery",
                supply_id=delivery.supply_id,
                supply_name=supply.name,
                supply_sku=supply.sku,
                quantity=delivery.quantity,
                detail=delivery.vendor_name,
                clinic_id=delivery.clinic_id,
                created_at=delivery.created_at,
                user_uuid=delivery.user_uuid,
            )
        )

    # Consumption orders
    consumptions = session.exec(
        select(SupplyConsumption, MedicalSupply)
        .join(MedicalSupply, SupplyConsumption.supply_id == MedicalSupply.id)
        .order_by(SupplyConsumption.created_at.desc())
    ).all()

    for consumption, supply in consumptions:
        items.append(
            OrderItem(
                id=consumption.id,
                type="consumption",
                supply_id=consumption.supply_id,
                supply_name=supply.name,
                supply_sku=supply.sku,
                quantity=consumption.quantity,
                detail=consumption.consumption_type,
                clinic_id=consumption.clinic_id,
                created_at=consumption.created_at,
                user_uuid=consumption.user_uuid,
            )
        )

    # Sort combined by created_at descending
    items.sort(key=lambda o: o.created_at, reverse=True)

    return OrderListResponse(orders=items)