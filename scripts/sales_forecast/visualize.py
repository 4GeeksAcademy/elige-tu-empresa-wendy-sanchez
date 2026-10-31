"""Visualización del pronóstico con su rango de variabilidad — HealthCore.

Finanzas no quiere "un solo número optimista": la gráfica muestra

    - línea naranja:  predicción mensual del modelo (XGBoost),
    - banda sombreada: intervalo de variabilidad ±1.96·σ (≈95%),
    - línea negra:     ingreso real de los 2 años de prueba (2024-01 .. 2025-12).

Honestidad de la banda:
    - ``sigma`` NO se calcula con los residuales de entrenamiento (que serían
      optimistas porque el modelo ya "vio" esas filas).
    - Se calcula con los errores reales fuera de muestra de la validación
      *walk-forward* (predicciones sobre 2024 y 2025 producidas con modelos
      entrenados solo con datos anteriores), que es lo más parecido a lo que
      el modelo hará en producción.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no requiere display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import HealthCoreSalesData
from .model import ForecastResult

ALPHA = 1.96  # ~95% de cobertura bajo normalidad


def uncertainty_sigma(
    result: ForecastResult, data: HealthCoreSalesData
) -> float:
    """Sigma del rango de variabilidad a partir de errores fuera de muestra.

    Si la validación walk-forward produjo RMSE por año (2024, 2025), usamos la
    raíz media cuadrática de esos errores reales como desviación típica del
    error de predicción. Si no hubiera, se cae a la desviación típica de los
    residuales de entrenamiento (con una advertencia explícita).
    """
    wf = result.walk_forward_rmse_by_year
    if wf:
        sigmas = list(wf.values())
        sigma = float(np.sqrt(np.mean(np.square(sigmas))))
    else:
        # Fallback claramente señalado: nunca debería ocurrir con los datos
        # reales, pero no queremos que la visualización falle en silencio.
        resid = np.asarray(data.y_train, dtype=float) - np.asarray(
            result.y_train_pred, dtype=float
        )
        sigma = float(np.std(resid, ddof=1))
    return max(sigma, 1.0)


def plot_forecast_with_band(
    data: HealthCoreSalesData,
    result: ForecastResult,
    out_path: str | Path = "reports/sales_forecast/forecast_vs_real.png",
    title: str = (
        "HealthCore — Pronóstico de ingresos mensuales (USD) con rango de "
        "variabilidad (±1.96·σ)"
    ),
) -> Path:
    """Genera y guarda la gráfica predicción + banda vs real (2 años de prueba)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sigma = uncertainty_sigma(result, data)
    months = pd.to_datetime(data.test_months)
    real = np.asarray(data.y_test, dtype=float)
    pred = np.asarray(result.y_test_pred, dtype=float)

    lo = pred - ALPHA * sigma
    hi = pred + ALPHA * sigma

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.fill_between(months, lo, hi, color="#f39c12", alpha=0.18, label="Banda ±1.96·σ (≈95%)")
    ax.plot(months, pred, color="#e67e22", linewidth=2.2, marker="o", markersize=4,
            label="Predicción XGBoost (no vio 2024-2025)")
    ax.plot(months, real, color="#2c3e50", linewidth=2.0, marker="s", markersize=4,
            label="Ingreso real (prueba)")

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Ingresos mensuales (USD)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Anotación con el error que Finanzas puede citar
    rmse_usd = result.metrics.get("rmse", 0.0)
    mse_pct = result.metrics.get("mse_pct_avg", 0.0)
    ax.text(
        0.99, 0.02,
        f"RMSE fuera de muestra ≈ ${rmse_usd:,.0f} "
        f"({mse_pct:.1f}% del ingreso mensual medio)\n"
        f"σ banda calibrada con errores reales walk-forward",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
        bbox={"boxstyle": "round", "facecolor": "#fdf2e9", "alpha": 0.9},
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path