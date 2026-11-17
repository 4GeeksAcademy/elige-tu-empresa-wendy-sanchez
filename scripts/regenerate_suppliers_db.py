"""Seed regenerator for suppliers_db.json.
Works with Python 3.12 (avoids SQLModel 3.14 incompatibility).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SUPPLIERS_SEED = [
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
        "contract_renewal_date": None,
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
        "contract_renewal_date": None,
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
        "name": "Stericycle Biohazard Disposal",
        "country": "USA",
        "categories": ["waste_management"],
        "monthly_rate": 1800.0,
        "currency": "USD",
        "status": "active",
        "compliance_agreement": "BAA",
        "contract_renewal_date": "2025-08-15",
        "contact_email": "compliance@stericycle.com",
        "notes": "Gestión de residuos biopeligrosos.",
    },
    {
        "name": "Veolia UK Clinical Waste",
        "country": "UK",
        "categories": ["waste_management"],
        "monthly_rate": 1200.0,
        "currency": "GBP",
        "status": "active",
        "compliance_agreement": "DPA",
        "contract_renewal_date": None,
        "contact_email": "healthcare@veolia.co.uk",
        "notes": "Recogida de residuos clínicos en clínicas del Reino Unido.",
    },
]

USERS_SEED = [
    {
        "email": "admin@healthcore.com",
        "hashed_password": "$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5GzOqZwGqyJ9RqZz3vZnVCOe",
        "is_active": True,
        "role": "admin",
        "created_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "email": "test@healthcore.com",
        "hashed_password": "$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5GzOqZwGqyJ9RqZz3vZnVCOe",
        "is_active": True,
        "role": "user",
        "created_at": "2026-01-01T00:00:00+00:00",
    },
]

PROFILES_SEED = [
    {"user_id": 1, "name": "Admin HealthCore", "phone": "+1-555-0000", "address": None},
    {"user_id": 2, "name": "Test User", "phone": "+1-555-0100", "address": None},
]


def main():
    db_path = Path(__file__).resolve().parents[1] / "data" / "process" / "suppliers_db.json"
    os.makedirs(db_path.parent, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    data = {
        "_default": {},  # TinyDB uses _default table
        "suppliers": {},
        "users": {},
        "profiles": {},
    }

    # Suppliers
    for i, s in enumerate(SUPPLIERS_SEED, 1):
        entry = dict(s)
        entry["created_at"] = now
        entry["updated_at"] = now
        entry["deleted_at"] = None
        data["suppliers"][str(i)] = entry

    # Users
    for i, u in enumerate(USERS_SEED, 1):
        data["users"][str(i)] = dict(u)

    # Profiles
    for i, p in enumerate(PROFILES_SEED, 1):
        data["profiles"][str(i)] = dict(p)

    db_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"✅ Base de datos regenerada en: {db_path}")
    print(f"   - {len(SUPPLIERS_SEED)} proveedores")
    print(f"   - {len(USERS_SEED)} usuarios")
    print(f"   - {len(PROFILES_SEED)} perfiles")


if __name__ == "__main__":
    main()