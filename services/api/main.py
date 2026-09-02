from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from incidents_analysis import analyze_csv_text, report_to_csv_text
from routes.suppliers import router as suppliers_router

app = FastAPI(title="HealthCore API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suppliers_router)

_last_report: dict | None = None
_last_csv_export: str | None = None
_repo_root = Path(__file__).resolve().parents[2]


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "HealthCore API",
        "docs": "/docs",
        "analyze": "/api/incidents/analyze",
        "analyze_sample": "/api/incidents/analyze/sample",
        "export": "/api/incidents/results/export",
        "suppliers": "/api/suppliers",
        "suppliers_by_country": "/api/suppliers/by-country/{country}",
        "suppliers_by_category": "/api/suppliers/by-category/{category}",
    }


@app.post("/api/incidents/analyze")
async def analyze_incidents(file: UploadFile = File(...)) -> dict:
    if file.filename is None or file.filename.strip() == "":
        raise HTTPException(status_code=400, detail="Debes enviar un fichero CSV")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Formato inválido: el fichero debe ser .csv")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El fichero CSV está vacío")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Codificación inválida: el fichero debe estar en UTF-8",
        ) from exc

    try:
        report = analyze_csv_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    global _last_report
    global _last_csv_export
    _last_report = report
    _last_csv_export = report_to_csv_text(report)

    return {
        "source_file": file.filename,
        "summary": report,
    }


@app.post("/api/incidents/analyze/sample")
def analyze_sample_incidents() -> dict:
    sample_path = _repo_root / "scripts" / "incidents-healthcore.csv"
    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No se encontró el CSV de muestra en scripts/incidents-healthcore.csv",
        )

    try:
        text = sample_path.read_text(encoding="utf-8")
        report = analyze_csv_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    global _last_report
    global _last_csv_export
    _last_report = report
    _last_csv_export = report_to_csv_text(report)

    return {
        "source_file": sample_path.name,
        "summary": report,
    }


@app.get("/api/incidents/results/export")
def export_last_results() -> Response:
    if _last_report is None or _last_csv_export is None:
        raise HTTPException(
            status_code=404,
            detail="No hay resultados para exportar. Ejecuta primero POST /api/incidents/analyze",
        )

    return Response(
        content=_last_csv_export,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
