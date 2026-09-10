#!/usr/bin/env python3
"""Seed historical incidents from legacy CSV into the incident manager database.

Usage:
    python scripts/seed_incidents.py                    # uses incidents-healthcore.csv
    python scripts/seed_incidents.py --file <path>      # custom CSV file
    python scripts/seed_incidents.py --db-path <path>   # custom DB path

This script:
  1. Reads the CSV file (legacy analyzer format)
  2. Validates each row using shared CSV-level validation (from incidents_analysis.py)
  3. Transforms valid rows using the CSV → Incident model mapping
  4. Validates transformed data using shared Incident model validation
  5. Inserts valid records into incidents TinyDB (idempotent)
  6. Reports invalid records to console

Idempotency: uses `incident_id` from CSV (stored as csv_incident_id) to prevent duplicates.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

# ── Ensure shared packages are importable ───────────────────────────────
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

SHARED_PYTHON_DIR = PROJECT_ROOT / "packages" / "shared" / "python"
API_DIR = PROJECT_ROOT / "services" / "incidents-api"

for _dir in (str(SHARED_PYTHON_DIR), str(API_DIR)):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from csv_transformer import csv_row_to_incident, get_csv_incident_id
from csv_validation import validate_csv_record

from tinydb import Query as TinyQuery, TinyDB
from tinydb.table import Table

# ── Default paths ────────────────────────────────────────────────────────
DEFAULT_CSV = PROJECT_ROOT / "scripts" / "incidents-healthcore.csv"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "process" / "incidents_db.json"


def parse_args(argv: list[str]) -> tuple[Path, Path]:
    csv_path = DEFAULT_CSV
    db_path = DEFAULT_DB_PATH

    i = 1
    while i < len(argv):
        if argv[i] == "--file" and i + 1 < len(argv):
            csv_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--db-path" and i + 1 < len(argv):
            db_path = Path(argv[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {argv[i]}")
            print(f"Usage: {argv[0]} [--file <csv-path>] [--db-path <db-path>]")
            sys.exit(1)
    return csv_path, db_path


def open_db(db_path: Path) -> TinyDB:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(db_path, indent=2, ensure_ascii=False)


def existing_incident_ids(table: Table) -> set[str]:
    """Collect all CSV incident_ids already stored in the DB (for idempotency)."""
    IncidentQuery = TinyQuery()
    results = table.search(IncidentQuery.csv_incident_id.exists())
    return {doc.get("csv_incident_id", "") for doc in results}


def main(argv: list[str]) -> int:
    csv_path, db_path = parse_args(argv)

    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return 1

    print("=" * 60)
    print("  HEALTHCORE — INCIDENT SEED SCRIPT")
    print(f"  CSV source:  {csv_path.name}")
    print(f"  DB target:   {db_path}")
    print("=" * 60)
    print()

    # ── Read CSV ────────────────────────────────────────────────────────
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    print(f"Total rows in CSV:  {len(rows)}")
    print()

    # ── Connect to DB and check existing records ────────────────────────
    db = open_db(db_path)
    table = db.table("incidents")
    existing_ids = existing_incident_ids(table)
    print(f"Existing seeded records in DB: {len(existing_ids)}")
    print()

    # ── Process each row ───────────────────────────────────────────────
    inserted = 0
    skipped_duplicate = 0
    csv_invalid_counts: Counter[str] = Counter()
    csv_invalid_details: list[tuple[int, list[str]]] = []
    transform_invalid_details: list[tuple[int, list[str]]] = []

    for idx, row in enumerate(rows, start=2):  # 2 = header is row 1
        csv_id = get_csv_incident_id(row)

        # ── Idempotency check ──────────────────────────────────────────
        if csv_id and csv_id in existing_ids:
            skipped_duplicate += 1
            continue

        # ── Step 1: CSV-level validation (from incidents_analysis.py) ───
        csv_errors = validate_csv_record(row)
        if csv_errors:
            csv_invalid_counts.update(csv_errors)
            csv_invalid_details.append((idx, csv_errors))
            continue

        # ── Step 2: Transform CSV → Incident model ─────────────────────
        incident_dict, transform_errors = csv_row_to_incident(row)
        if transform_errors:
            transform_invalid_details.append((idx, transform_errors))
            continue

        # ── Store csv_incident_id for idempotency ──────────────────────
        incident_dict["csv_incident_id"] = csv_id  # type: ignore

        # ── Insert ─────────────────────────────────────────────────────
        table.insert(incident_dict)  # type: ignore
        inserted += 1

    # ── Report ─────────────────────────────────────────────────────────
    print(f"Records inserted:    {inserted}")
    print(f"Skipped (duplicate): {skipped_duplicate}")

    total_invalid = len(csv_invalid_details) + len(transform_invalid_details)
    print(f"Invalid / skipped:   {total_invalid}")
    print()

    if csv_invalid_details:
        print("CSV-LEVEL INVALID RECORDS BREAKDOWN:")
        for error_key, count in sorted(csv_invalid_counts.items()):
            print(f"  ├─ {error_key}: {count}")
        print()

    if transform_invalid_details:
        print("TRANSFORM-LEVEL INVALID RECORDS:")
        for row_num, errs in transform_invalid_details:
            print(f"  Row {row_num}: {errs}")
        print()

    # ── Summary from DB ─────────────────────────────────────────────────
    all_records = table.all()
    print(f"Total records now in DB: {len(all_records)}")

    status_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    branch_counts: Counter[str] = Counter()

    for doc in all_records:
        status_counts[doc.get("status", "unknown")] += 1
        category_counts[doc.get("category", "unknown")] += 1
        branch_counts[doc.get("branch", "unknown")] += 1

    print()
    print("BREAKDOWN BY STATUS (model):")
    for status in ["open", "in_progress", "resolved", "discarded"]:
        count = status_counts.get(status, 0)
        print(f"  ├─ {status}: {count}")

    print()
    print("BREAKDOWN BY CATEGORY (model):")
    for cat in [
        "clinical_equipment", "it_system", "billing_error",
        "compliance_breach", "patient_experience", "staff_issue",
        "facility_issue", "referral_issue", "other",
    ]:
        count = category_counts.get(cat, 0)
        if count:
            print(f"  ├─ {cat}: {count}")

    print()
    print("BREAKDOWN BY BRANCH:")
    for branch, count in sorted(branch_counts.items(), key=lambda x: -x[1]):
        print(f"  ├─ {branch}: {count}")

    print()
    print("=" * 60)

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))