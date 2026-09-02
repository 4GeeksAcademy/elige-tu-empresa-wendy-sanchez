from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from tinydb import Query as TinyQuery

from database import get_suppliers_table
from models import (
    Country,
    Supplier,
    SupplierCategory,
    SupplierCreate,
    SupplierRateUpdate,
    SupplierReplace,
    SupplierStatus,
    SupplierStatusUpdate,
    utc_now,
)

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])

SupplierQuery = TinyQuery()


def _to_supplier(doc_id: int, record: dict) -> Supplier:
    return Supplier(id=doc_id, **record)


def _read_all() -> list[Supplier]:
    return [_to_supplier(doc.doc_id, dict(doc)) for doc in get_suppliers_table().all()]


def _read_one(supplier_id: int) -> Supplier:
    doc = get_suppliers_table().get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe ningún proveedor con id {supplier_id}",
        )
    return _to_supplier(doc.doc_id, dict(doc))


@router.get("", response_model=list[Supplier])
def list_suppliers(
    country: Country | None = Query(default=None, description="Filtra por país del contrato"),
    category: SupplierCategory | None = Query(default=None, description="Filtra por categoría"),
    supplier_status: SupplierStatus | None = Query(
        default=None, alias="status", description="Filtra por estado"
    ),
) -> list[Supplier]:
    suppliers = _read_all()
    if country is not None:
        suppliers = [item for item in suppliers if item.country is country]
    if category is not None:
        suppliers = [item for item in suppliers if category in item.categories]
    if supplier_status is not None:
        suppliers = [item for item in suppliers if item.status is supplier_status]
    return suppliers


@router.get("/by-country/{country}", response_model=list[Supplier])
def list_suppliers_by_country(country: Country) -> list[Supplier]:
    return [item for item in _read_all() if item.country is country]


@router.get("/by-category/{category}", response_model=list[Supplier])
def list_suppliers_by_category(category: SupplierCategory) -> list[Supplier]:
    return [item for item in _read_all() if category in item.categories]


@router.get("/{supplier_id}", response_model=Supplier)
def get_supplier(supplier_id: int) -> Supplier:
    return _read_one(supplier_id)


@router.post("", response_model=Supplier, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate) -> Supplier:
    table = get_suppliers_table()
    if table.get(SupplierQuery.name.test(lambda value: value.lower() == payload.name.lower())):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un proveedor registrado con el nombre '{payload.name}'",
        )

    record = payload.model_dump(mode="json")
    record["updated_at"] = utc_now().isoformat()
    record["archived_at"] = None
    doc_id = table.insert(record)
    return _to_supplier(doc_id, record)


@router.put("/{supplier_id}", response_model=Supplier)
def replace_supplier(supplier_id: int, payload: SupplierReplace) -> Supplier:
    current = _read_one(supplier_id)
    record = payload.model_dump(mode="json")
    rate_changed = payload.monthly_rate != current.monthly_rate
    record["updated_at"] = (
        utc_now().isoformat() if rate_changed else current.updated_at.isoformat()
    )
    record["archived_at"] = current.archived_at.isoformat() if current.archived_at else None
    get_suppliers_table().update(record, doc_ids=[supplier_id])
    return _to_supplier(supplier_id, record)


@router.patch("/{supplier_id}/rate", response_model=Supplier)
def update_supplier_rate(supplier_id: int, payload: SupplierRateUpdate) -> Supplier:
    _read_one(supplier_id)
    changes = {"monthly_rate": payload.monthly_rate, "updated_at": utc_now().isoformat()}
    get_suppliers_table().update(changes, doc_ids=[supplier_id])
    return _read_one(supplier_id)


@router.patch("/{supplier_id}/status", response_model=Supplier)
def update_supplier_status(supplier_id: int, payload: SupplierStatusUpdate) -> Supplier:
    _read_one(supplier_id)
    changes: dict[str, object] = {"status": payload.status.value}
    if payload.status is SupplierStatus.ACTIVE:
        changes["archived_at"] = None
    get_suppliers_table().update(changes, doc_ids=[supplier_id])
    return _read_one(supplier_id)


@router.delete("/{supplier_id}", response_model=Supplier)
def archive_supplier(supplier_id: int) -> Supplier:
    """Baja lógica: el CONTEXT exige conservar el histórico, así que se archiva con su fecha."""
    _read_one(supplier_id)
    get_suppliers_table().update(
        {"status": SupplierStatus.SUSPENDED.value, "archived_at": utc_now().isoformat()},
        doc_ids=[supplier_id],
    )
    return _read_one(supplier_id)
