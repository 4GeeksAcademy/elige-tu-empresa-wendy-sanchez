"""Carga inicial del Directorio de Proveedores de HealthCore en TinyDB.

Ejecuta con: uv run seed
"""

from __future__ import annotations

from tinydb import Query

from database import get_db_path, get_suppliers_table
from models import SupplierCreate, utc_now

SUPPLIERS_SEED: list[dict] = [
    {
        "name": "McKesson Medical Supplies",
        "country": "USA",
        "categories": ["medical_supplies"],
        "monthly_rate": 4200.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contract_renewal_date": "2025-06-30",
        "contact_email": "accounts@mckesson.com",
        "notes": "Proveedor principal de material clínico para las 9 clínicas de USA.",
    },
    {
        "name": "NHS Supply Chain",
        "country": "UK",
        "categories": ["medical_supplies"],
        "monthly_rate": 2800.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contact_email": "enquiries@supplychain.nhs.uk",
    },
    {
        "name": "Quest Diagnostics",
        "country": "USA",
        "categories": ["laboratory_services"],
        "monthly_rate": 3100.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contract_renewal_date": "2025-12-15",
        "contact_email": "business@questdiagnostics.com",
        "notes": "Procesamiento de laboratorio para clínicas de Texas y Florida.",
    },
    {
        "name": "Synnovis UK",
        "country": "UK",
        "categories": ["laboratory_services"],
        "monthly_rate": 1950.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contact_email": "contracts@synnovis.co.uk",
    },
    {
        "name": "Epic Systems",
        "country": "USA",
        "categories": ["clinical_software"],
        "monthly_rate": 8500.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contract_renewal_date": "2026-01-01",
        "contact_email": "enterprise@epic.com",
        "notes": "EHR principal para las clínicas de USA. Contrato de largo plazo.",
    },
    {
        "name": "EMIS Health",
        "country": "UK",
        "categories": ["clinical_software"],
        "monthly_rate": 3400.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contract_renewal_date": "2025-09-01",
        "contact_email": "accounts@emishealth.com",
        "notes": "EHR para las clínicas de Londres y Manchester.",
    },
    {
        "name": "Availity",
        "country": "USA",
        "categories": ["billing_and_coding_software"],
        "monthly_rate": 1200.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contact_email": "enterprise@availity.com",
        "notes": "Plataforma de verificación de elegibilidad y envío de claims.",
    },
    {
        "name": "Twilio",
        "country": "USA",
        "categories": ["patient_communication"],
        "monthly_rate": 680.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contract_renewal_date": "2025-10-31",
        "contact_email": "healthcare@twilio.com",
        "notes": "SMS y email automatizados para recordatorios de citas.",
    },
    {
        "name": "AWS Healthcare",
        "country": "USA",
        "categories": ["it_infrastructure"],
        "monthly_rate": 5600.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contact_email": "aws-health@amazon.com",
        "notes": "Infraestructura cloud principal. BAA firmado y auditado anualmente.",
    },
    {
        "name": "Microsoft Azure UK",
        "country": "UK",
        "categories": ["it_infrastructure"],
        "monthly_rate": 2100.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contact_email": "enterprise@microsoft.com",
    },
    {
        "name": "Workday",
        "country": "USA",
        "categories": ["hr_and_payroll_software"],
        "monthly_rate": 2400.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": None,
        "contract_renewal_date": "2025-08-15",
        "contact_email": "enterprise@workday.com",
        "notes": "HRIS para toda la plantilla de USA. No maneja PHI.",
    },
    {
        "name": "Sage Payroll UK",
        "country": "UK",
        "categories": ["hr_and_payroll_software"],
        "monthly_rate": 890.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contact_email": "business@sage.co.uk",
    },
    {
        "name": "ServiceMaster Clean",
        "country": "USA",
        "categories": ["cleaning_and_facilities"],
        "monthly_rate": 3800.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": None,
        "contact_email": "healthcare@servicemaster.com",
        "notes": "Limpieza clínica para las 9 ubicaciones de USA.",
    },
    {
        "name": "Healthstream LMS",
        "country": "USA",
        "categories": ["training_platforms"],
        "monthly_rate": 1100.0,
        "currency": "USD",
        "status": "suspended",
        "compliance_agreement": "BAA",
        "contact_email": "enterprise@healthstream.com",
        "notes": "Suspendido. Diane está evaluando reemplazarlo por una solución interna.",
    },
    {
        "name": "Nuffield Health Supplies",
        "country": "UK",
        "categories": ["medical_supplies", "cleaning_and_facilities"],
        "monthly_rate": 1650.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contact_email": "procurement@nuffieldhealth.com",
    },
]


# ─────────────────────────────────────────────────────────────────────
# Seed de inventario (Supabase) — suministros, entregas y consumos
# ─────────────────────────────────────────────────────────────────────

SUPPLIES_SEED: list[dict] = [
    {
        "name": "Guantes de nitrilo (caja de 100)",
        "sku": "HCR-PPE-001",
        "category": "ppe",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Mascarilla quirúrgica (pack de 50)",
        "sku": "HCR-PPE-002",
        "category": "ppe",
        "unit": "pack",
        "country": "UK",
    },
    {
        "name": "Apósito adhesivo para heridas",
        "sku": "HCR-WND-001",
        "category": "wound_care",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Test rápido de estreptococo",
        "sku": "HCR-DIAG-001",
        "category": "diagnostics",
        "unit": "unit",
        "country": "US",
    },
    {
        "name": "Tiras reactivas glucemia (50)",
        "sku": "HCR-DIAG-002",
        "category": "diagnostics",
        "unit": "box",
        "country": "UK",
    },
    {
        "name": "Solución salina 0,9% 500ml",
        "sku": "HCR-MED-001",
        "category": "medications",
        "unit": "vial",
        "country": "US",
    },
]

DELIVERIES_SEED: list[dict] = [
    {
        "supply_sku": "HCR-PPE-001",
        "quantity": 50,
        "vendor_name": "MedLine Industries",
        "clinic_id": 1,
    },
    {
        "supply_sku": "HCR-PPE-001",
        "quantity": 30,
        "vendor_name": "Bound Tree Medical",
        "clinic_id": 2,
    },
    {
        "supply_sku": "HCR-PPE-002",
        "quantity": 20,
        "vendor_name": "Cardinal Health UK",
        "clinic_id": 10,
    },
    {
        "supply_sku": "HCR-DIAG-001",
        "quantity": 100,
        "vendor_name": "MedLine Industries",
        "clinic_id": 1,
    },
]

CONSUMPTIONS_SEED: list[dict] = [
    {
        "supply_sku": "HCR-PPE-001",
        "quantity": 10,
        "consumption_type": "clinical_use",
        "clinic_id": 1,
    },
    {
        "supply_sku": "HCR-PPE-001",
        "quantity": 5,
        "consumption_type": "expiry_waste",
        "clinic_id": 2,
    },
    {
        "supply_sku": "HCR-PPE-002",
        "quantity": 8,
        "consumption_type": "clinical_use",
        "clinic_id": 10,
    },
]


def seed_suppliers() -> tuple[int, int]:
    """Inserta los proveedores que aún no existan. Devuelve (insertados, omitidos)."""
    table = get_suppliers_table()
    supplier_query = Query()
    inserted = 0
    skipped = 0

    for raw_supplier in SUPPLIERS_SEED:
        supplier = SupplierCreate.model_validate(raw_supplier)
        already_exists = table.contains(
            supplier_query.name.test(lambda value, name=supplier.name: value.lower() == name.lower())
        )
        if already_exists:
            skipped += 1
            continue

        record = supplier.model_dump(mode="json")
        record["updated_at"] = utc_now().isoformat()
        table.insert(record)
        inserted += 1

    return inserted, skipped


def seed_inventory() -> dict[str, int]:
    """Siembra las tablas de inventario en Supabase.

    Crea suministros si no existen por SKU, y luego registra entregas y
    consumos referenciando los IDs de los suministros ya creados.
    Usa '1' como user_uuid por defecto (primer usuario admin de TinyDB).

    Returns: dict con conteo de creados.
    """
    from sqlmodel import Session, select

    from database import get_sql_engine, init_supabase_schema
    from models import MedicalSupply, SupplyConsumption, SupplyDelivery

    # Crear las tablas en Supabase antes de insertar datos
    init_supabase_schema()

    engine = get_sql_engine()
    counts: dict[str, int] = {"supplies": 0, "deliveries": 0, "consumptions": 0}

    default_user_uuid = "1"

    with Session(engine) as session:
        # ── Supplies (solo si no existen por SKU) ──────────────
        for raw in SUPPLIES_SEED:
            existing = session.exec(
                select(MedicalSupply).where(MedicalSupply.sku == raw["sku"])
            ).first()
            if existing:
                continue
            supply = MedicalSupply(**raw)
            session.add(supply)
            session.flush()  # obtiene el ID sin commit
            counts["supplies"] += 1

        # Diccionario sku → id
        sku_to_id: dict[str, int] = {}
        all_supplies = session.exec(select(MedicalSupply)).all()
        for s in all_supplies:
            sku_to_id[s.sku] = s.id

        # ── Deliveries ─────────────────────────────────────────
        for raw in DELIVERIES_SEED:
            supply_id = sku_to_id.get(raw["supply_sku"])
            if supply_id is None:
                continue
            delivery = SupplyDelivery(
                supply_id=supply_id,
                quantity=raw["quantity"],
                vendor_name=raw["vendor_name"],
                clinic_id=raw["clinic_id"],
                user_uuid=default_user_uuid,
            )
            session.add(delivery)
            counts["deliveries"] += 1

        # ── Consumptions ───────────────────────────────────────
        for raw in CONSUMPTIONS_SEED:
            supply_id = sku_to_id.get(raw["supply_sku"])
            if supply_id is None:
                continue
            consumption = SupplyConsumption(
                supply_id=supply_id,
                quantity=raw["quantity"],
                consumption_type=raw["consumption_type"],
                clinic_id=raw["clinic_id"],
                user_uuid=default_user_uuid,
            )
            session.add(consumption)
            counts["consumptions"] += 1

        session.commit()

    return counts


def main() -> None:
    inserted, skipped = seed_suppliers()
    total = len(get_suppliers_table())

    print(f"Base de datos TinyDB: {get_db_path()}")
    print(f"Proveedores insertados: {inserted}")
    print(f"Proveedores omitidos (ya existían): {skipped}")
    print(f"Total en el directorio: {total}")

    inv_counts = seed_inventory()
    print(f"\n--- Inventario (Supabase) ---")
    print(f"Suministros creados: {inv_counts['supplies']}")
    print(f"Entregas registradas: {inv_counts['deliveries']}")
    print(f"Consumos registrados: {inv_counts['consumptions']}")


if __name__ == "__main__":
    main()
