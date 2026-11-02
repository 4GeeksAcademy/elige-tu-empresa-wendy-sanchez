"""Comparación visual: modelo con fuga (rolling sin shift) vs corregido (con shift).

Genera una gráfica de doble panel que muestra las predicciones de ambas
versiones contra los valores reales, más una tabla de diferencias.

Uso:
    uv run python scripts/sales_forecast/compare_before_after.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler

from scripts.sales_forecast.data import (
    FEATURES,
    SCALE_COLS,
    TEST_START,
    WARMUP_ROWS,
    load_sales,
    _add_causal_features,
    _fill_missing_values,
    prepare_features,
)
from scripts.sales_forecast.metrics import rmse, k2_score, mape

DATA_CSV = _PROJECT_ROOT / "data" / "raw" / "healthcore_sales.csv"
OUT_PNG = _PROJECT_ROOT / "reports" / "sales_forecast" / "forecast_comparison_before_after.png"


def _add_causal_features_with_fuga(df: pd.DataFrame) -> pd.DataFrame:
    """Versión con fuga: rolling() SIN shift(1) — replica el bug original."""
    df = df.copy()
    df["rev_lag_1"] = df["revenue_usd"].shift(1)
    df["rev_lag_2"] = df["revenue_usd"].shift(2)
    df["rev_lag_12"] = df["revenue_usd"].shift(12)

    # 🔴 FUGA: rolling() sobre revenue_usd directamente, incluye revenue_usd[t]
    df["rev_ma_3"] = df["revenue_usd"].rolling(3, min_periods=1).mean()
    df["rev_min_12"] = df["revenue_usd"].rolling(12, min_periods=1).min()
    df["rev_max_12"] = df["revenue_usd"].rolling(12, min_periods=1).max()
    df["rev_std_12"] = df["revenue_usd"].rolling(12, min_periods=1).std()

    df["month_num"] = df["month"].dt.month
    df["season"] = df["month_num"].map(
        lambda m: 2 if m >= 10 else (0 if m in (7, 8) else 1)
    )
    df["trend_index"] = (
        (df["month"].dt.year - 2016) * 12 + df["month"].dt.month - 1
    ).astype(float)
    return df


def train_and_predict(
    df_full: pd.DataFrame,
    feature_fn,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Entrena XGBoost con la función de features dada y devuelve predicciones."""
    df = feature_fn(df_full.copy())
    train = df.loc[df["month"] < TEST_START].iloc[WARMUP_ROWS:].copy()
    test = df.loc[df["month"] >= TEST_START].copy()

    y_train = train["revenue_usd"].astype(float)
    y_test = test["revenue_usd"].astype(float)

    scaler = StandardScaler()
    scaler.fit(train[SCALE_COLS])
    X_train = train[FEATURES].copy().reset_index(drop=True)
    X_test = test[FEATURES].copy().reset_index(drop=True)
    X_train[SCALE_COLS] = scaler.transform(train[SCALE_COLS])
    X_test[SCALE_COLS] = scaler.transform(test[SCALE_COLS])

    model = XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.03,
        subsample=0.9, colsample_bytree=0.9,
        gamma=0.5, reg_lambda=2.0, reg_alpha=0.5,
        objective="reg:squarederror", random_state=42, tree_method="hist",
        eval_metric="rmse", verbosity=0,
    )
    model.fit(X_train, y_train)
    pred_test = model.predict(X_test)

    r = rmse(y_test.to_numpy(), pred_test)
    k2 = k2_score(y_test.to_numpy(), pred_test)
    return y_test.to_numpy(), pred_test, r, k2


def main() -> int:
    print("=" * 60)
    print("Comparación: modelo con fuga vs corregido (anti-fuga)")
    print("=" * 60)

    df_raw = load_sales(DATA_CSV)
    df_clean = _fill_missing_values(df_raw)

    # --- Modelo con fuga (rolling sin shift) ---
    print("\n[1] Entrenando modelo CON FUGA (rolling sin shift)...")
    real, pred_fuga, rmse_fuga, k2_fuga = train_and_predict(
        df_clean, _add_causal_features_with_fuga
    )

    # --- Modelo corregido (shift(1) antes de rolling) ---
    print("[2] Entrenando modelo CORREGIDO (rolling con shift)...")
    # Usamos prepare_features que internamente llama a _add_causal_features
    def corrected_features(df):
        return prepare_features(df)

    _, pred_corr, rmse_corr, k2_corr = train_and_predict(
        df_clean, corrected_features
    )

    print(f"\n    CON FUGA:   RMSE=${rmse_fuga:,.2f}   R²={k2_fuga:.4f}")
    print(f"    CORREGIDO: RMSE=${rmse_corr:,.2f}   R²={k2_corr:.4f}")
    print(f"    MEJORA:    RMSE −${rmse_fuga - rmse_corr:,.2f}  "
          f"({(rmse_fuga - rmse_corr)/rmse_fuga*100:.2f}%)")

    # --- Gráfico comparativo ---
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Panel superior: ambas predicciones vs real
    ax1.plot(months, real, color="#2c3e50", linewidth=2.0, marker="s",
             markersize=5, label="Ingreso real (prueba)", zorder=5)
    ax1.plot(months, pred_fuga, color="#e74c3c", linewidth=1.5, linestyle="--",
             marker="o", markersize=4, label=f"Con fuga (RMSE=${rmse_fuga:,.0f})",
             alpha=0.8)
    ax1.plot(months, pred_corr, color="#27ae60", linewidth=1.8, linestyle="-",
             marker="^", markersize=4, label=f"Corregido (RMSE=${rmse_corr:,.0f})",
             alpha=0.9)
    ax1.set_ylabel("USD")
    ax1.set_title("Comparación: predicciones con fuga vs corregidas", fontsize=12)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel inferior: diferencias (pred - real) para cada versión
    diff_fuga = pred_fuga - real
    diff_corr = pred_corr - real
    ax2.plot(months, diff_fuga, color="#e74c3c", linewidth=1.5, marker="o",
             markersize=4, label=f"Error con fuga (σ=${np.std(diff_fuga, ddof=1):,.0f})",
             alpha=0.7)
    ax2.plot(months, diff_corr, color="#27ae60", linewidth=1.8, marker="^",
             markersize=4, label=f"Error corregido (σ=${np.std(diff_corr, ddof=1):,.0f})",
             alpha=0.8)
    ax2.axhline(0, color="gray", linewidth=0.8, linestyle=":")
    ax2.set_ylabel("Error (pred − real) USD")
    ax2.set_xlabel("Mes")
    ax2.set_title("Diferencia de errores: el corregido reduce la dispersión", fontsize=10)
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Anotación con métricas
    summary_text = (
        f"Con fuga:   RMSE=${rmse_fuga:,.0f}   R²={k2_fuga:.4f}\n"
        f"Corregido: RMSE=${rmse_corr:,.0f}   R²={k2_corr:.4f}\n"
        f"Mejora:    −${rmse_fuga - rmse_corr:,.0f} ({abs(rmse_fuga - rmse_corr)/rmse_fuga*100:.1f}%)"
    )
    ax2.text(0.99, 0.55, summary_text, transform=ax2.transAxes, ha="right",
             va="top", fontsize=8, family="monospace",
             bbox={"boxstyle": "round", "facecolor": "#fdf2e9", "alpha": 0.9})

    fig.suptitle("HealthCore — Impacto de la corrección anti-fuga en rolling()",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"\n[3] Gráfico guardado: {OUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())