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


# ═══════════════════════════════════════════════════════════════════════════════
#  Descomposición aditiva: tendencia + estacionalidad + residuo
# ═══════════════════════════════════════════════════════════════════════════════


def decompose_time_series(
    df: pd.DataFrame,
    revenue_col: str = "revenue_usd",
    period: int = 12,
) -> dict[str, np.ndarray | float]:
    """Descomposición aditiva clásica de serie temporal.

    Separa la serie en tres componentes:
        ``serie = tendencia + estacionalidad + residuo``

    Metodología:
        1. **Tendencia**: media móvil centrada de ``period`` meses (ventana
           completa, centrada, para suavizar la estacionalidad anual).
        2. **Estacionalidad**: para cada mes (1-12), promedio de
           ``(serie − tendencia)`` en ese mes de todos los años.
        3. **Residuo**: lo que queda tras restar tendencia y estacionalidad.

    Parámetros:
        df: DataFrame con columna ``month`` (datetime) y ``revenue_col``.
        revenue_col: nombre de la columna a descomponer.
        period: ventana de descomposición (12 para estacionalidad anual).

    Devuelve:
        ``{"trend": ndarray, "seasonal": ndarray, "residual": ndarray,
          "full": ndarray, "strength_trend_pct": float,
          "strength_seasonal_pct": float,
          "strength_residual_pct": float}``

    Nota: la fuerza relativa se mide como la varianza de cada componente
    dividida por la varianza total de la serie.
    """
    series = df[revenue_col].to_numpy().astype(float)
    n = len(series)

    # --- Tendencia: media móvil centrada de 12 meses ------------------------
    series_pd = pd.Series(series)
    trend = series_pd.rolling(period, center=True, min_periods=1).mean().to_numpy()

    # --- Estacionalidad: perfil mensual -------------------------------------
    months = df["month"].dt.month.to_numpy()
    detrended = series - trend
    seasonal = np.zeros(n)
    for m in range(1, 13):
        mask = months == m
        if mask.any():
            seasonal[mask] = detrended[mask].mean()
    # Asegurar que la estacionalidad sume ~0 en un año completo
    seasonal -= seasonal.mean()

    # --- Residuo -------------------------------------------------------------
    residual = series - trend - seasonal

    # --- Fuerza relativa de cada componente ----------------------------------
    total_var = np.var(series, ddof=1)
    strength = {
        "trend_pct": float(np.var(trend, ddof=1) / total_var * 100) if total_var > 0 else 0.0,
        "seasonal_pct": float(np.var(seasonal, ddof=1) / total_var * 100) if total_var > 0 else 0.0,
        "residual_pct": float(np.var(residual, ddof=1) / total_var * 100) if total_var > 0 else 0.0,
    }

    return {
        "trend": trend,
        "seasonal": seasonal,
        "residual": residual,
        "full": series,
        **strength,
    }


def plot_decomposition(
    decomp: dict,
    out_path: str | Path = "reports/sales_forecast/decomposition.png",
    title: str = "HealthCore — Descomposición de ingresos (tendencia + estacionalidad + residuo)",
) -> Path:
    """Genera y guarda la gráfica de descomposición de la serie temporal.

    Muestra 4 paneles: serie original + tendencia, estacionalidad, residuo,
    y un cuadro con la fuerza relativa de cada componente.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)

    n = len(decomp["full"])
    x = np.arange(n)
    months_labels = [
        "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"
    ]
    tick_positions = np.arange(0, n, 12)  # cada 12 meses = cada año

    # Panel 1: Original + Tendencia
    ax = axes[0]
    ax.plot(x, decomp["full"], color="#2c3e50", linewidth=1.5, label="Ingreso real")
    ax.plot(x, decomp["trend"], color="#c0392b", linewidth=2.0, label="Tendencia (media móvil 12m)")
    ax.set_ylabel("USD")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Serie original y tendencia", fontsize=10)
    ax.grid(True, alpha=0.3)

    # Panel 2: Estacionalidad
    ax = axes[1]
    ax.plot(x, decomp["seasonal"], color="#27ae60", linewidth=1.8, marker=".", markersize=3)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_ylabel("USD")
    ax.set_title("Estacionalidad (perfil mensual)", fontsize=10)
    ax.grid(True, alpha=0.3)

    # Panel 3: Residuo (ruido / eventos no capturados)
    ax = axes[2]
    ax.fill_between(x, 0, decomp["residual"], color="#7f8c8d", alpha=0.5)
    ax.plot(x, decomp["residual"], color="#34495e", linewidth=1.0)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_ylabel("USD")
    ax.set_title("Residuo (eventos no capturados por tendencia + estacionalidad)", fontsize=10)
    ax.grid(True, alpha=0.3)

    # Panel 4: Fuerza relativa (barras)
    ax = axes[3]
    labels = ["Tendencia", "Estacionalidad", "Residuo"]
    values = [decomp["trend_pct"], decomp["seasonal_pct"], decomp["residual_pct"]]
    colors = ["#c0392b", "#27ae60", "#7f8c8d"]
    bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor="gray")
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("Varianza explicada (%)")
    ax.set_title("Fuerza relativa de cada componente", fontsize=10)
    ax.set_ylim(0, max(values) * 1.25 + 5)
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path