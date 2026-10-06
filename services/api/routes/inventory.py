"""Router de inventario — todos los endpoints bajo /inventory.

Requiere autenticación JWT en todas las operaciones de escritura y lectura
(según requisitos de HealthCore).
"""

from __future__ import annotations

import logging
import json
import csv
import io
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, func, select

from cache import cache
from database import get_db
from models import MedicalSupply, StockPolicy, SupplyConsumption, SupplyDelivery
from inventory_telemetry import CATEGORIES, attach_signals, capture_expiry, dimensions, signal
from telemetry_identity import user_pseudonym, vendor_pseudonym
from schemas import (
    MedicalSupplyCreate,
    MedicalSupplyResponse,
    OrderItem,
    OrderListResponse,
    SupplyConsumptionCreate,
    SupplyConsumptionResponse,
    SupplyDeliveryCreate,
    SupplyDeliveryResponse,
    StockPolicyUpdate,
    DirectStockAttempt,
    StockReconciliation,
)
from security import get_current_user

logger = logging.getLogger(__name__)

def inventory_actor(request: Request, current_user=Depends(get_current_user)):
    request.state.telemetry_user_id = user_pseudonym(current_user.id)


router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(inventory_actor)])

# ── Constantes de caché ──────────────────────────────────────────────
# TTL de 30 segundos para listado de productos: el catálogo de suministros
# cambia con poca frecuencia (altas, bajas), pero los stocks se actualizan
# continuamente con órdenes. 30s es un intercambio aceptable entre frescura
# del stock y reducción de carga en BD. Véase CACHING_REPORT.md.
_INVENTORY_CACHE_TTL = 30
_INVENTORY_CACHE_PREFIX = "inventory:products"

# ── Helpers ────────────────────────────────────────────────────────────


def _compute_current_stock(
    supply_id: int, session: Session, clinic_id: int | None = None
) -> int:
    """Calcula current_stock = SUM(deliveries) - SUM(consumptions) para un supply."""
    total_in = (
        session.exec(
            select(func.coalesce(func.sum(SupplyDelivery.quantity), 0)).where(
                SupplyDelivery.supply_id == supply_id,
                True if clinic_id is None else SupplyDelivery.clinic_id == clinic_id,
            )
        ).one()
        or 0
    )
    total_out = (
        session.exec(
            select(func.coalesce(func.sum(SupplyConsumption.quantity), 0)).where(
                SupplyConsumption.supply_id == supply_id,
                True if clinic_id is None else SupplyConsumption.clinic_id == clinic_id,
            )
        ).one()
        or 0
    )
    return int(total_in) - int(total_out)


def _invalidate_product_cache(trigger: str | None = None) -> None:
    """Invalida toda la caché de productos.

    Se llama tras cualquier operación de escritura que afecte al catálogo
    o los stocks (creación de producto, órdenes de entrada/salida).
    """
    start = time.perf_counter()
    cleared = cache.invalidate(_INVENTORY_CACHE_PREFIX)
    if trigger:
        signal("inventory_cache_invalidated", {"cache_namespace": "inventory:products", "trigger": trigger,
            "entries_cleared": cleared, "duration_ms": round((time.perf_counter() - start) * 1000)})
    if cleared:
        logger.info("Inventory cache invalidated: %d entries cleared", cleared)


# ── Products / MedicalSupply ──────────────────────────────────────────


@router.get("/products", response_model=list[MedicalSupplyResponse])
def list_products(
    response: Response,
    session: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> list[MedicalSupplyResponse]:
    """Lista todos los suministros médicos con su current_stock calculado.

    Cacheado: TTL 30s. Se invalida al crear/modificar productos o registrar
    órdenes de entrada/salida.
    """
    cache_key = f"{_INVENTORY_CACHE_PREFIX}:list"
    cached = cache.get(cache_key)
    signal("inventory_cache_served", {"route_template": "/inventory/products", "cache_result": "hit" if cached is not None else "miss",
        "cache_age_ms": cache.age_ms(cache_key, _INVENTORY_CACHE_TTL) if cached is not None else 0, "status_code": 200})
    if cached is not None:
        return cached

    logger.debug("Cache MISS: recomputing product list")
    supplies = session.exec(select(MedicalSupply)).all()
    result: list[MedicalSupplyResponse] = []
    events = []
    for s in supplies:
        stock = _compute_current_stock(s.id, session)
        events.extend(capture_expiry(s, session, _compute_current_stock))
        result.append(
            MedicalSupplyResponse(
                id=s.id,
                name=s.name,
                sku=s.sku,
                category=s.category,
                unit=s.unit,
                country=s.country,
                current_stock=stock,
                expiry_date=s.expiry_date,
            )
        )

    attach_signals(response, events)
    cache.set(cache_key, result, _INVENTORY_CACHE_TTL)
    return result


@router.post("/products", response_model=MedicalSupplyResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: MedicalSupplyCreate,
    response: Response,
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
        expiry_date=payload.expiry_date,
    )
    session.add(supply)
    session.commit()
    session.refresh(supply)

    _invalidate_product_cache("product_created")

    attach_signals(response, [signal("inventory_product_created", {
        "product_id": supply.id, "product_category": CATEGORIES.get(supply.category, ""),
        "country": supply.country, "unit_category": supply.unit,
    })])

    return MedicalSupplyResponse(
        id=supply.id,
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=0,
        expiry_date=supply.expiry_date,
    )


@router.get("/products/{supply_id}", response_model=MedicalSupplyResponse)
def get_product(
    supply_id: int,
    response: Response,
    clinic_id: int | None = None,
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

    if clinic_id is not None and not 1 <= clinic_id <= 12:
        raise HTTPException(status_code=422, detail="Invalid clinic")
    stock = _compute_current_stock(supply.id, session, clinic_id)
    events = capture_expiry(supply, session, _compute_current_stock)
    attach_signals(response, events)
    return MedicalSupplyResponse(
        id=supply.id,
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=stock,
        expiry_date=supply.expiry_date,
    )


# ── Orders — Inbound (SupplyDelivery) ─────────────────────────────────


@router.post(
    "/orders/inbound",
    response_model=SupplyDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    payload: SupplyDeliveryCreate,
    response: Response,
    session: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SupplyDeliveryResponse:
    """Registra una entrega de proveedor (incrementa stock)."""
    supply = session.get(MedicalSupply, payload.supply_id)
    if supply is None:
        signal("inventory_order_validation_failed", {"operation": "inbound", "field_name": "supply_id", "validation_code": "unknown_supply"})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply with id {payload.supply_id} not found",
        )

    previous = session.exec(select(SupplyDelivery).where(SupplyDelivery.supply_id == payload.supply_id,
        SupplyDelivery.clinic_id == payload.clinic_id, SupplyDelivery.quantity == payload.quantity,
        SupplyDelivery.vendor_name == payload.vendor_name, SupplyDelivery.user_uuid == str(current_user.id),
        SupplyDelivery.created_at >= datetime.now(timezone.utc) - timedelta(seconds=60))).first()
    if previous:
        signal("inventory_order_duplicate_suspected", {"clinic_id": payload.clinic_id, "country": "US" if payload.clinic_id <= 9 else "UK",
            "operation": "inbound", "duplicate_reason": "same_operation_window", "window_seconds": 60})
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

    _invalidate_product_cache("inbound_order_created")

    events = [signal("inbound_order_created", {
        **dimensions(supply, payload.clinic_id, payload.quantity), "vendor_ref": vendor_pseudonym(payload.vendor_name),
    })]
    events.extend(capture_expiry(supply, session, _compute_current_stock))
    attach_signals(response, events)

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
    response: Response,
    session: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SupplyConsumptionResponse:
    """Registra un consumo clínico (reduce stock).

    Rechaza la operación si resultara en stock negativo (HTTP 400).
    """
    supply = session.exec(select(MedicalSupply).where(MedicalSupply.id == payload.supply_id).with_for_update()).first()
    if supply is None:
        signal("inventory_order_validation_failed", {"operation": "outbound", "field_name": "supply_id", "validation_code": "unknown_supply"})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supply with id {payload.supply_id} not found",
        )

    # Calcular stock disponible antes de registrar
    available = _compute_current_stock(payload.supply_id, session, payload.clinic_id)
    if available < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock for supply '{supply.name}'. "
                f"Available: {available}, requested: {payload.quantity}."
            ),
            headers={"X-Telemetry-Events": json.dumps([signal("inventory_order_rejected", {
                **dimensions(supply, payload.clinic_id, payload.quantity), "operation": "outbound", "rejection_code": "insufficient_stock",
            })])},
        )

    previous = session.exec(select(SupplyConsumption).where(SupplyConsumption.supply_id == payload.supply_id,
        SupplyConsumption.clinic_id == payload.clinic_id, SupplyConsumption.quantity == payload.quantity,
        SupplyConsumption.department == payload.department, SupplyConsumption.consumption_type == payload.consumption_type,
        SupplyConsumption.user_uuid == str(current_user.id), SupplyConsumption.created_at >= datetime.now(timezone.utc) - timedelta(seconds=60))).first()
    if previous:
        signal("inventory_order_duplicate_suspected", {"clinic_id": payload.clinic_id, "country": "US" if payload.clinic_id <= 9 else "UK",
            "operation": "outbound", "duplicate_reason": "same_operation_window", "window_seconds": 60})
    consumption = SupplyConsumption(
        supply_id=payload.supply_id,
        quantity=payload.quantity,
        consumption_type=payload.consumption_type,
        department=payload.department,
        clinic_id=payload.clinic_id,
        user_uuid=str(current_user.id),
    )
    session.add(consumption)
    session.commit()
    session.refresh(consumption)

    _invalidate_product_cache("outbound_order_created")

    events = [signal("outbound_order_created", {
        **dimensions(supply, payload.clinic_id, payload.quantity), "department": payload.department,
        "consumption_type": payload.consumption_type,
    })]
    try:
        policy = session.get(StockPolicy, (payload.supply_id, payload.clinic_id))
    except Exception:
        session.rollback()
        logger.warning("Telemetry signal dropped: stock_policy_read")
        policy = None
    remaining = available - payload.quantity
    if policy and available >= policy.minimum_quantity > remaining:
        events.append(signal("stock_threshold_triggered", {
            **dimensions(supply, payload.clinic_id, remaining), "threshold_quantity": policy.minimum_quantity,
            "threshold_version": policy.version,
        }))
    attach_signals(response, events)

    return SupplyConsumptionResponse(
        id=consumption.id,
        supply_id=consumption.supply_id,
        quantity=consumption.quantity,
        consumption_type=consumption.consumption_type,
        clinic_id=consumption.clinic_id,
        created_at=consumption.created_at,
        user_uuid=consumption.user_uuid,
        department=consumption.department,
    )


@router.put("/products/{supply_id}/policy", response_model=MedicalSupplyResponse)
def update_stock_policy(supply_id: int, payload: StockPolicyUpdate, session: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    supply = session.get(MedicalSupply, supply_id)
    if supply is None:
        raise HTTPException(status_code=404, detail="Unknown supply")
    policy = session.get(StockPolicy, (supply_id, payload.clinic_id))
    if policy is None:
        policy = StockPolicy(supply_id=supply_id, clinic_id=payload.clinic_id, minimum_quantity=payload.minimum_quantity, version=uuid4().hex)
    else:
        policy.minimum_quantity = payload.minimum_quantity
        policy.version = uuid4().hex
    if "expiry_date" in payload.model_fields_set:
        supply.expiry_date = payload.expiry_date
    session.add(policy)
    session.add(supply)
    session.commit()
    session.refresh(supply)
    _invalidate_product_cache()
    return MedicalSupplyResponse(**supply.model_dump(), current_stock=_compute_current_stock(supply_id, session))


@router.patch("/products/{supply_id}/stock", response_model=dict)
@router.put("/products/{supply_id}/stock", response_model=dict)
def reject_direct_stock(supply_id: int, payload: DirectStockAttempt, session: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    supply = session.get(MedicalSupply, supply_id)
    if supply is None:
        raise HTTPException(status_code=404, detail="Unknown supply")
    event = signal("direct_stock_edit_rejected", {
        **dimensions(supply, payload.clinic_id, payload.quantity), "rejection_code": "direct_edit_not_allowed", "source_surface": "api",
    })
    raise HTTPException(status_code=403, detail="Stock changes require an order", headers={"X-Telemetry-Events": json.dumps([event])})


# ── List all orders ───────────────────────────────────────────────────


@router.post("/snapshots", response_model=dict)
def record_stock_snapshot(session: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    count = 0
    for supply in session.exec(select(MedicalSupply)).all():
        for clinic_id in range(1, 13):
            quantity = _compute_current_stock(supply.id, session, clinic_id)
            signal("inventory_stock_snapshot_recorded", {**dimensions(supply, clinic_id, quantity), "snapshot_date": datetime.now(timezone.utc).date().isoformat()})
            count += 1
    return {"captured": count}


@router.post("/products/{supply_id}/reconcile", response_model=dict)
def reconcile_stock(supply_id: int, payload: StockReconciliation, session: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    supply = session.get(MedicalSupply, supply_id)
    if supply is None:
        raise HTTPException(status_code=404, detail="Unknown supply")
    ledger = _compute_current_stock(supply_id, session, payload.clinic_id)
    variance = payload.counted_quantity - ledger
    if variance:
        props = dimensions(supply, payload.clinic_id, ledger)
        props.pop("quantity")
        signal("inventory_stock_reconciliation_flagged", {**props, "ledger_quantity": ledger,
            "counted_quantity": payload.counted_quantity, "variance_quantity": variance})
    return {"ledger_quantity": ledger, "counted_quantity": payload.counted_quantity, "variance_quantity": variance}


@router.get("/orders/export", response_class=Response)
def export_history(country_scope: str = "both", period_bucket: str = "month", session: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    if country_scope not in {"US", "UK", "both"} or period_bucket not in {"day", "week", "month", "quarter", "custom"}:
        raise HTTPException(status_code=422, detail="Invalid export scope")
    days = {"day": 1, "week": 7, "month": 30, "quarter": 90}
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days.get(period_bucket, 36500))
    rows = []
    for model, operation in ((SupplyDelivery, "inbound"), (SupplyConsumption, "outbound")):
        for order in session.exec(select(model)).all():
            country = "US" if order.clinic_id <= 9 else "UK"
            if order.created_at.replace(tzinfo=None) >= cutoff and country_scope in {"both", country}:
                rows.append([operation, order.supply_id, order.clinic_id, order.quantity, getattr(order, "department", None) or "", order.created_at.isoformat()])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["operation", "product_id", "clinic_id", "quantity", "department", "created_at"])
    writer.writerows(rows)
    bucket = "0" if not rows else "1_100" if len(rows) <= 100 else "101_1000" if len(rows) <= 1000 else "1001_plus"
    signal("inventory_order_history_exported", {"country_scope": country_scope, "period_bucket": period_bucket, "row_count_bucket": bucket, "export_format": "csv"})
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory-orders.csv"})


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