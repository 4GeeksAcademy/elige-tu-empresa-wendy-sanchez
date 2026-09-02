from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path
from typing import Any

VALID_CLINICS: dict[str, str] = {
    "US-TX-01": "US",
    "US-TX-02": "US",
    "US-TX-03": "US",
    "US-FL-01": "US",
    "US-FL-02": "US",
    "US-FL-03": "US",
    "US-GA-01": "US",
    "US-GA-02": "US",
    "US-GA-03": "US",
    "UK-LON-01": "UK",
    "UK-LON-02": "UK",
    "UK-MAN-01": "UK",
}

VALID_CATEGORIES = {
    "APPOINTMENT",
    "BILLING",
    "CLINICAL_CARE",
    "ACCESSIBILITY",
    "ADMINISTRATIVE",
}

VALID_STATUSES = {"OPEN", "CLOSED", "DISCARDED"}

PATIENT_ID_RE = re.compile(r"^PAT-[A-Za-z0-9]{6}$")

REQUIRED_COLUMNS = [
    "incident_id",
    "date",
    "clinic_id",
    "country",
    "category",
    "description",
    "status",
    "patient_id",
    "satisfaction_score",
]


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return (count / total) * 100


def validate_record(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []

    clinic_id = (row.get("clinic_id") or "").strip()
    country = (row.get("country") or "").strip()
    category = (row.get("category") or "").strip()
    description = (row.get("description") or "").strip()
    status = (row.get("status") or "").strip()
    patient_id = (row.get("patient_id") or "").strip()
    score = _to_int(row.get("satisfaction_score"))

    if clinic_id not in VALID_CLINICS:
        reasons.append("invalid_clinic")
    elif country != VALID_CLINICS[clinic_id]:
        reasons.append("country_clinic_mismatch")

    if category not in VALID_CATEGORIES:
        reasons.append("invalid_category")

    if len(description) < 5:
        reasons.append("empty_description")

    if not PATIENT_ID_RE.match(patient_id):
        reasons.append("missing_patient_id")

    if status == "CLOSED" and score is None:
        reasons.append("closed_no_score")

    if score is not None and (score < 1 or score > 5):
        reasons.append("score_out_of_range")

    if status not in VALID_STATUSES:
        reasons.append("invalid_status")

    return reasons


def _validate_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("CSV inválido: no se detectó cabecera")
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(
            "CSV inválido: faltan columnas requeridas: " + ", ".join(missing)
        )


def analyze_csv_text(csv_text: str) -> dict[str, Any]:
    if csv_text.strip() == "":
        raise ValueError("El fichero CSV está vacío")

    reader = csv.DictReader(io.StringIO(csv_text))
    _validate_columns(reader.fieldnames)

    invalid_breakdown: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    score_counts: Counter[int] = Counter()

    total = 0
    valid = 0

    for row in reader:
        total += 1
        reasons = validate_record(row)
        if reasons:
            invalid_breakdown.update(reasons)
            continue

        valid += 1
        category = (row.get("category") or "").strip()
        status = (row.get("status") or "").strip()
        country = (row.get("country") or "").strip()
        score = _to_int(row.get("satisfaction_score"))

        category_counts[category] += 1
        status_counts[status] += 1
        country_counts[country] += 1

        if status == "CLOSED" and score is not None:
            score_counts[score] += 1

    scored_cases = sum(score_counts.values())
    closed_cases = status_counts.get("CLOSED", 0)
    average_score = (
        sum(score * count for score, count in score_counts.items()) / scored_cases
        if scored_cases
        else 0.0
    )

    return {
        "total": total,
        "valid": valid,
        "invalid": total - valid,
        "invalid_breakdown": dict(invalid_breakdown),
        "category_counts": dict(category_counts),
        "status_counts": dict(status_counts),
        "country_counts": dict(country_counts),
        "score_counts": dict(score_counts),
        "scored_cases": scored_cases,
        "closed_cases": closed_cases,
        "average_score": round(average_score, 2),
        "percentages": {
            "categories": {
                k: round(_percent(v, valid), 1)
                for k, v in category_counts.items()
            },
            "statuses": {
                k: round(_percent(v, valid), 1)
                for k, v in status_counts.items()
            },
            "countries": {
                k: round(_percent(v, valid), 1)
                for k, v in country_counts.items()
            },
        },
    }


def analyze_csv_file(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8")
    return analyze_csv_text(text)


def report_to_csv_rows(report: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: str | int | float, percentage: float | None = None) -> None:
        row = {"metric": metric, "value": str(value), "percentage": ""}
        if percentage is not None:
            row["percentage"] = f"{percentage:.1f}"
        rows.append(row)

    total = report["total"]
    valid = report["valid"]

    add("total_records", total)
    add("valid_records", valid, _percent(valid, total))
    add("invalid_records", report["invalid"], _percent(report["invalid"], total))

    invalid = report["invalid_breakdown"]
    add("invalid.invalid_clinic_id", invalid.get("invalid_clinic", 0))
    add("invalid.country_clinic_mismatch", invalid.get("country_clinic_mismatch", 0))
    add("invalid.invalid_category", invalid.get("invalid_category", 0))
    add("invalid.empty_description", invalid.get("empty_description", 0))
    add("invalid.missing_patient_id", invalid.get("missing_patient_id", 0))
    add("invalid.closed_no_score", invalid.get("closed_no_score", 0))
    add("invalid.score_out_of_range", invalid.get("score_out_of_range", 0))

    for category in ["APPOINTMENT", "BILLING", "CLINICAL_CARE", "ACCESSIBILITY", "ADMINISTRATIVE"]:
        count = report["category_counts"].get(category, 0)
        add(f"category.{category}", count, _percent(count, valid))

    for status in ["OPEN", "CLOSED", "DISCARDED"]:
        count = report["status_counts"].get(status, 0)
        add(f"status.{status}", count, _percent(count, valid))

    for country in ["US", "UK"]:
        count = report["country_counts"].get(country, 0)
        add(f"country.{country}", count, _percent(count, valid))

    add("satisfaction.scored_cases", report["scored_cases"])
    add("satisfaction.closed_cases", report["closed_cases"])
    add("satisfaction.average", report["average_score"])
    for score in [1, 2, 3, 4, 5]:
        add(f"satisfaction.score_{score}", report["score_counts"].get(score, 0))

    return rows


def report_to_csv_text(report: dict[str, Any]) -> str:
    rows = report_to_csv_rows(report)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["metric", "value", "percentage"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def verify_expected_healthcore_values(report: dict[str, Any]) -> tuple[bool, list[str]]:
    expected_categories = {
        "APPOINTMENT": 30,
        "BILLING": 20,
        "CLINICAL_CARE": 14,
        "ACCESSIBILITY": 17,
        "ADMINISTRATIVE": 13,
    }
    expected_status = {"OPEN": 28, "CLOSED": 52, "DISCARDED": 14}
    expected_invalid = {
        "invalid_clinic": 1,
        "country_clinic_mismatch": 1,
        "invalid_category": 1,
        "empty_description": 1,
        "missing_patient_id": 1,
        "closed_no_score": 1,
    }
    expected_scores = {1: 3, 2: 5, 3: 12, 4: 23, 5: 9}

    mismatches: list[str] = []

    if report["total"] != 100:
        mismatches.append(f"total esperado=100 actual={report['total']}")
    if report["valid"] != 94:
        mismatches.append(f"valid esperado=94 actual={report['valid']}")
    if report["invalid"] != 6:
        mismatches.append(f"invalid esperado=6 actual={report['invalid']}")

    for key, expected in expected_categories.items():
        actual = report["category_counts"].get(key, 0)
        if actual != expected:
            mismatches.append(f"category {key} esperado={expected} actual={actual}")

    for key, expected in expected_status.items():
        actual = report["status_counts"].get(key, 0)
        if actual != expected:
            mismatches.append(f"status {key} esperado={expected} actual={actual}")

    for key, expected in expected_invalid.items():
        actual = report["invalid_breakdown"].get(key, 0)
        if actual != expected:
            mismatches.append(f"invalid {key} esperado={expected} actual={actual}")

    for key, expected in expected_scores.items():
        actual = report["score_counts"].get(key, 0)
        if actual != expected:
            mismatches.append(f"score {key} esperado={expected} actual={actual}")

    avg = round(float(report["average_score"]), 2)
    if avg != 3.58:
        mismatches.append(f"average esperado=3.58 actual={avg:.2f}")

    return (len(mismatches) == 0, mismatches)
