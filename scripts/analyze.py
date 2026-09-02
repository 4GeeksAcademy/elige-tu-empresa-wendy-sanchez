#!/usr/bin/env python3
"""HealthCore incidents CSV analyzer (Phase 1)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
API_DIR = CURRENT_DIR.parent / "services" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from incidents_analysis import (  # noqa: E402
    analyze_csv_file,
    report_to_csv_rows,
    verify_expected_healthcore_values,
)


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
    rows = report_to_csv_rows(report)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "value", "percentage"])
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: python analyze.py <ruta-al-csv>")
        return 1

    file_path = Path(argv[1])
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: archivo no encontrado: {file_path}")
        return 1

    report = analyze_csv_file(file_path)
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
