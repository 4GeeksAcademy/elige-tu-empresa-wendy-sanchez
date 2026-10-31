#!/usr/bin/env python
"""HealthCore — Entrenamiento y evaluación del modelo de pronóstico de ventas.

Uso:
    uv run python scripts/train_sales_forecast.py

Pipeline (alineado con CONTEXT.md §6):
    1. Carga `data/raw/healthcore_sales.csv` y validación contra CONTEXT.md.
    2. Limpieza de nulos y features causales (lags, rodantes, calendario).
    3. Split temporal 8 años (2016-2023) / 2 años (2024-2025) sin fuga.
    4. Entrenamiento XGBoost (justificación en scripts/sales_forecast/model.py).
    5. Métricas sobre prueba: MSE, PSI, Gini, K2 (R²).
    6. Visualización con banda de variabilidad calibrada walk-forward.
    7. Exporta `reports/sales_forecast/metrics.json` (para Finanzas/Dashboard).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Asegurar que el proyecto raíz está en sys.path (permite importar el paquete)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sales_forecast.data import build_train_test_sets, load_sales
from scripts.sales_forecast.metrics import metrics_table
from scripts.sales_forecast.model import train_sales_model
from scripts.sales_forecast.visualize import plot_forecast_with_band

DATA_CSV = _PROJECT_ROOT / "data" / "raw" / "healthcore_sales.csv"
REPORT_DIR = _PROJECT_ROOT / "reports" / "sales_forecast"
METRICS_JSON = REPORT_DIR / "metrics.json"
PLOT_PNG = REPORT_DIR / "forecast_vs_real.png"


def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def main() -> int:
    print("=" * 78)
    print("HealthCore — Pronóstico de ingresos mensuales (predicción de ventas)")
    print("=" * 78)

    # 1. Carga y validación contra CONTEXT.md
    df_raw = load_sales(DATA_CSV)
    print(f"\n[1] Dataset cargado: {DATA_CSV}")
    print(f"    Filas consolidated: {len(df_raw)}")
    print(f"    Rango: {df_raw['month'].min().date()} .. {df_raw['month'].max().date()}")

    # 2+3. Features + split temporal 8/2
    data = build_train_test_sets(DATA_CSV)
    print("\n[2/3] Split temporal sin fuga")
    print(f"    Entrenamiento: {len(data.y_train)} meses (2016-01 .. 2023-12, "
          f"warm-up excluido)")
    print(f"    Prueba:        {len(data.y_test)} meses (2024-01 .. 2025-12)")
    print(f"    Features:      {len(data.feature_names)}")

    # 4. Entrenamiento (XGBoost)
    print("\n[4] Entrenando XGBoost (regularizado, random_state=42)...")
    result = train_sales_model(data)

    print("\n    Validación walk-forward (año a año, modelo retirado del futuro):")
    for year, rmse_ in result.walk_forward_rmse_by_year.items():
        print(f"      {year}: RMSE fuera de muestra = {_fmt_usd(rmse_)}")

    # 5. Métricas sobre el conjunto de prueba
    m = result.metrics
    print("\n[5] Métricas sobre el conjunto de prueba (2024-2025, no visto):")
    print(f"    MSE            = {m['mse']:,.0f} USD²")
    print(f"    RMSE           = {m['rmse']:,.0f} USD")
    print(f"    MSE como % del ingreso mensual medio = {m['mse_pct_avg']:.2f}%")
    print(f"    MAPE           = {m['mape_pct']:.2f}%")
    print(f"    PSI            = {m['psi']:.4f}")
    print(f"    PSI (crecimiento ajustado) = {m['psi_growth_adjusted']:.4f}")
    print(f"    Gini predictivo= {m['gini']:.4f}")
    print(f"    K2 (R²)        = {m['k2']:.4f}")

    # 6. Visualización con banda de variabilidad
    print("\n[6] Generando visualización con rango de variabilidad...")
    plot_path = plot_forecast_with_band(data, result, PLOT_PNG)
    print(f"    Guardada: {plot_path}")

    # 7. Exportar métricas consolidado (para Finanzas / dashboard)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "project": "HealthCore Sales Forecast",
        "target": "revenue_usd",
        "split": {"train": "2016-01..2023-12", "test": "2024-01..2025-12"},
        "n_train": int(len(data.y_train)),
        "n_test": int(len(data.y_test)),
        "model": "XGBoost (regularizado)",
        "metrics_test": {
            "mse_usd2": round(m["mse"], 2),
            "rmse_usd": round(m["rmse"], 2),
            "mse_pct_avg_monthly_revenue": round(m["mse_pct_avg"], 4),
            "mape_pct": round(m["mape_pct"], 4),
            "psi": round(m["psi"], 6),
            "psi_growth_adjusted": round(m["psi_growth_adjusted"], 6),
            "gini": round(m["gini"], 6),
            "k2": round(m["k2"], 6),
        },
        "walk_forward_rmse_by_year_usd": {
            k: round(v, 2) for k, v in result.walk_forward_rmse_by_year.items()
        },
        "feature_importance_pct": {
            k: float(v) for k, v in sorted(
                result.feature_importance.items(), key=lambda kv: -kv[1]
            )
        },
        "plot": str(plot_path.relative_to(_PROJECT_ROOT)),
    }
    METRICS_JSON.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[7] Métricas exportadas: {METRICS_JSON}")

    # Re-cálculo de la tabla métrica por separado para legibilidad
    print("\n" + "=" * 78)
    print("Resumen para Finanzas (las 4 métricas exigidas)")
    print("=" * 78)
    print(f"  MSE            : {m['mse']:,.0f} USD²")
    print(f"  MSE (% ingreso medio mensual): {m['mse_pct_avg']:.2f}%")
    print(f"  MAPE           : {m['mape_pct']:.2f}%")
    print(f"  PSI            : {m['psi']:.4f}")
    print(f"  PSI (crecimiento ajustado): {m['psi_growth_adjusted']:.4f}")
    print(f"  Gini           : {m['gini']:.4f}")
    print(f"  K2 (R²)        : {m['k2']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())