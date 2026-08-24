#!/usr/bin/env python3
"""HealthCore incidents CSV analyzer (Phase 1)."""

from __future__ import annotations

import csv
import re
import sys
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


def _to_int(value: str) -> int | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def validate_record(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []

    clinic_id = (row.get("clinic_id") or "").strip()
    country = (row.get("country") or "").strip()
    category = (row.get("category") or "").strip()
    description = (row.get("description") or "").strip()
    status = (row.get("status") or "").strip()
    patient_id = (row.get("patient_id") or "").strip()
    score_raw = row.get("satisfaction_score")
    score = _to_int(score_raw if score_raw is not None else "")

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


def analyze_csv(file_path: Path) -> dict[str, Any]:
    invalid_breakdown: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()
    score_counts: Counter[int] = Counter()

    total = 0
    valid = 0

    with file_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
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
            score = _to_int((row.get("satisfaction_score") or ""))

            category_counts[category] += 1
            status_counts[status] += 1
            country_counts[country] += 1

            if status == "CLOSED" and score is not None:
                score_counts[score] += 1

    scored_cases = sum(score_counts.values())
    closed_cases = status_counts.get("CLOSED", 0)
    average_score = (sum(score * count for score, count in score_counts.items()) / scored_cases) if scored_cases else 0.0

    return {
        "total": total,
        "valid": valid,
        "invalid": total - valid,
        "invalid_breakdown": invalid_breakdown,
        "category_counts": category_counts,
        "status_counts": status_counts,
        "country_counts": country_counts,
        "score_counts": score_counts,
        "scored_cases": scored_cases,
        "closed_cases": closed_cases,
        "average_score": average_score,
    }


def _percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return (count / total) * 100


def print_report(file_path: Path, report: dict[str, Any]) -> None:
    print("=" * 60)
    print("  HEALTHCORE - PATIENT INCIDENT REPORT ANALYSIS")
    print(f"  Source file: {file_path.name}")
    print("=" * 60)
    print()

    print(f"TOTAL RECORDS IN FILE .......... {report['total']}")
    print(f"  |- Valid records ................ {report['valid']}")
    print(f"  '- Invalid / incomplete ......... {report['invalid']}")
    print()

    invalid_breakdown = report["invalid_breakdown"]
    print("INVALID RECORDS BREAKDOWN")
    print(f"  |- Invalid or missing clinic_id .. {invalid_breakdown.get('invalid_clinic', 0)}")
    print(f"  |- Country/clinic mismatch ....... {invalid_breakdown.get('country_clinic_mismatch', 0)}")
    print(f"  |- Invalid or missing category ... {invalid_breakdown.get('invalid_category', 0)}")
    print(f"  |- Empty description ............. {invalid_breakdown.get('empty_description', 0)}")
    print(f"  |- Missing patient_id ............ {invalid_breakdown.get('missing_patient_id', 0)}")
    print(f"  |- Closed case, no score ......... {invalid_breakdown.get('closed_no_score', 0)}")
    print(f"  '- Score out of range ............ {invalid_breakdown.get('score_out_of_range', 0)}")
    print()

    valid = report["valid"]
    category_counts = report["category_counts"]
    print("BREAKDOWN BY CATEGORY (valid records)")
    for category in ["APPOINTMENT", "BILLING", "CLINICAL_CARE", "ACCESSIBILITY", "ADMINISTRATIVE"]:
        count = category_counts.get(category, 0)
        print(f"  |- {category:<28} {count:>3}  ({_percent(count, valid):>4.1f}%)")
    print()

    status_counts = report["status_counts"]
    print("BREAKDOWN BY STATUS (valid records)")
    for status in ["OPEN", "CLOSED", "DISCARDED"]:
        count = status_counts.get(status, 0)
        print(f"  |- {status:<28} {count:>3}  ({_percent(count, valid):>4.1f}%)")
    print()

    country_counts = report["country_counts"]
    print("BREAKDOWN BY COUNTRY (valid records) - recomendado")
    for country in ["US", "UK"]:
        count = country_counts.get(country, 0)
        print(f"  |- {country:<28} {count:>3}  ({_percent(count, valid):>4.1f}%)")
    print()

    score_counts = report["score_counts"]
    print("SATISFACTION INDEX (closed cases)")
    print(f"  Scored cases: {report['scored_cases']} of {report['closed_cases']}")
    print(f"  Average score: {report['average_score']:.2f} / 5.00")
    score_labels = {
        1: "Very dissatisfied",
        2: "Dissatisfied",
        3: "Neutral",
        4: "Satisfied",
        5: "Very satisfied",
    }
    for score in [1, 2, 3, 4, 5]:
        count = score_counts.get(score, 0)
        print(f"  |- Score {score} ({score_labels[score]:<17}) ... {count}")
    print()
    print("=" * 60)


def export_results_csv(path: Path, report: dict[str, Any]) -> None:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: str | int | float, percentage: float | None = None) -> None:
        row = {"metric": metric, "value": str(value)}
        if percentage is not None:
            row["percentage"] = f"{percentage:.1f}"
        rows.append(row)

    total = report["total"]
    valid = report["valid"]

    add("total_records", total)
    add("valid_records", valid, _percent(valid, total))
    add("invalid_records", report["invalid"], _percent(report["invalid"], total))

    invalid_breakdown = report["invalid_breakdown"]
    add("invalid.invalid_clinic_id", invalid_breakdown.get("invalid_clinic", 0))
    add("invalid.country_clinic_mismatch", invalid_breakdown.get("country_clinic_mismatch", 0))
    add("invalid.invalid_category", invalid_breakdown.get("invalid_category", 0))
    add("invalid.empty_description", invalid_breakdown.get("empty_description", 0))
    add("invalid.missing_patient_id", invalid_breakdown.get("missing_patient_id", 0))
    add("invalid.closed_no_score", invalid_breakdown.get("closed_no_score", 0))
    add("invalid.score_out_of_range", invalid_breakdown.get("score_out_of_range", 0))

    category_counts = report["category_counts"]
    for category in ["APPOINTMENT", "BILLING", "CLINICAL_CARE", "ACCESSIBILITY", "ADMINISTRATIVE"]:
        count = category_counts.get(category, 0)
        add(f"category.{category}", count, _percent(count, valid))

    status_counts = report["status_counts"]
    for status in ["OPEN", "CLOSED", "DISCARDED"]:
        count = status_counts.get(status, 0)
        add(f"status.{status}", count, _percent(count, valid))

    country_counts = report["country_counts"]
    for country in ["US", "UK"]:
        count = country_counts.get(country, 0)
        add(f"country.{country}", count, _percent(count, valid))

    add("satisfaction.scored_cases", report["scored_cases"])
    add("satisfaction.closed_cases", report["closed_cases"])
    add("satisfaction.average", f"{report['average_score']:.2f}")
    for score in [1, 2, 3, 4, 5]:
        add(f"satisfaction.score_{score}", report["score_counts"].get(score, 0))

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "value", "percentage"])
        writer.writeheader()
        writer.writerows(rows)


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

    avg = round(report["average_score"], 2)
    if avg != 3.58:
        mismatches.append(f"average esperado=3.58 actual={avg:.2f}")

    return (len(mismatches) == 0, mismatches)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: python analyze.py <ruta-al-csv>")
        return 1

    file_path = Path(argv[1])
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: archivo no encontrado: {file_path}")
        return 1

    report = analyze_csv(file_path)
    print_report(file_path, report)

    if file_path.name == "incidents-healthcore.csv":
        ok, mismatches = verify_expected_healthcore_values(report)
        if ok:
            print("VERIFICACION CONTEXT: OK (coincide con valores esperados)")
        else:
            print("VERIFICACION CONTEXT: NO COINCIDE")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
        print()

    try:
        export_answer = input("¿Deseas exportar los resultados a CSV? [s/ n]: ").strip().lower()
    except EOFError:
        export_answer = "n"

    if export_answer in {"s", "si", "sí", "y", "yes"}:
        output_path = Path("results.csv")
        export_results_csv(output_path, report)
        print(f"Resultados exportados en: {output_path.resolve()}")
    else:
        print("Exportación omitida.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
