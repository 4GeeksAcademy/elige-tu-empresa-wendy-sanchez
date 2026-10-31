"""Selección y entrenamiento del modelo de pronóstico — HealthCore.

¿Por qué XGBoost y no Random Forest aquí? No asumimos que uno es "mejor"
porque sí; el argumento es específico de este caso:

    1. Tamaño de datos:  ~84 filas de entrenamiento efectivo (96 meses de
       2016-01..2023-12 menos 12 de warm-up). Es un
       dataset *pequeño* y de series temporales, con un patrón mixto:
       tendencia de crecimiento (4% ± 2% anual), estacionalidad fuerte
       (Q4 alta, jul-ago baja) y ruido moderado. Random Forest promedia árboles
       independientes y en muestras pequeñas tiende a quedarse con la "forma
       dominante" (la tendencia), suavizando en exceso los picos mensuales.

    2. Ajuste fino a la estacionalidad:  XGBoost entrena cada árbol
       (potencial de profundidad 4-6) sobre los *residuales* del anterior
       (gradient boosting), así puede captar el patrón estacional mensual
       (lag_12, season) que un bosque aleatorio promedia de forma más burda.

    3. ¿Explicabilidad?  Ambos son árboles, ambos soportan feature importance.
       La diferencia técnica (boosting vs bagging) no cambia la explicabilidad
       en este caso: el requisito real es poder decirle a Finanzas *qué*
       predice (ingreso consolidado mensual) y *por qué* (lags, estacionalidad,
       tendencia), y ambos lo permiten igual. XGBoost se queda por su mejor
       ajuste a la estacionalidad con pocos datos y por su soporte nativo de
       regularización (gamma, l1, l2) que reduce el sobreajuste en series
       cortas.

    4. Tiempo de cómputo:  con ~84 filas y 12 features el coste es
       despreciable en ambos; no es un factor decisivo aquí, pero confirma que
       la *capacidad* extra de XGBoost no penaliza el flujo.

    Validación temporal honesta (no k-fold aleatorio, que rompería el orden
    cronológico y filtraría el futuro):  *walk-forward*. Se entrena con los
    meses anteriores a cada año de prueba y se evalúa solo ese año, repitiendo
    con ventana expandente. Esto imita exactamente lo que hará el modelo en
    producción (predecir el futuro nunca visto) y evita el optimismo de un
    MSE medido sobre datos ya vistos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from .data import HealthCoreSalesData

# Configuración del modelo (regularizada para serie corta)
XGB_PARAMS: dict = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.03,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "gamma": 0.5,          # regularización: mín. reducción de pérdida por split
    "reg_lambda": 2.0,     # regularización L2
    "reg_alpha": 0.5,      # regularización L1
    "objective": "reg:squarederror",
    "random_state": 42,
    "tree_method": "hist",  # eficiente y determinista
    "eval_metric": "rmse",
    "verbosity": 0,
}


@dataclass
class ForecastResult:
    """Resultado de entrenamiento + predicción fuera de muestra."""

    model: XGBRegressor
    y_train_pred: np.ndarray
    y_test_pred: np.ndarray
    test_months: pd.Series
    test_real: np.ndarray
    metrics: dict[str, float]
    feature_importance: dict[str, float]
    walk_forward_rmse_by_year: dict[str, float]


def train_sales_model(data: HealthCoreSalesData) -> ForecastResult:
    """Entrena XGBoost con los datos preparados y devuelve el pronóstico.

    - Se entrena SOLO con los 8 primeros años (X_train/y_train).
    - Se predice SOLO sobre los 2 últimos años (X_test/y_test).
    - Antes del eval final se hace una validación *walk-forward* (año a año)
      para estimar el error de forma honesta y detectar sobreajuste.
    """
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(data.X_train, data.y_train)

    y_train_pred = model.predict(data.X_train)
    y_test_pred = model.predict(data.X_test)

    from .metrics import metrics_table

    metrics = metrics_table(
        y_train_true=data.y_train.to_numpy(),
        y_train_pred=y_train_pred,
        y_test_true=data.y_test.to_numpy(),
        y_test_pred=y_test_pred,
    )

    # Importancia de features (para explicar a Finanzas qué impulsa la
    # predicción, sin caja negra)
    importance = model.feature_importances_
    feature_importance = dict(
        zip(data.feature_names, np.round(importance * 100.0, 2))
    )

    walk_forward_rmse = _walk_forward_validation(data)

    return ForecastResult(
        model=model,
        y_train_pred=y_train_pred,
        y_test_pred=y_test_pred,
        test_months=data.test_months,
        test_real=np.asarray(data.y_test.to_numpy(), dtype=float),
        metrics=metrics,
        feature_importance=feature_importance,
        walk_forward_rmse_by_year=walk_forward_rmse,
    )


def _walk_forward_validation(data: HealthCoreSalesData) -> dict[str, float]:
    """Validación temporal expandente: error por cada año de prueba.

    Para cada año (2024 y 2025) se reentrena XGBoost desde cero usando SOLO
    los meses anteriores a ese año (la misma política anti-fuga del flujo
    principal, incluido el descarte de las primeras ``WARMUP_ROWS`` filas y el
    escalado ajustado con el entrenamiento de ese fold). Luego se predice el
    año retenido y se calcula el RMSE sobre sus valores reales.

    Devuelve ``{año: RMSE_usd}``.
    """
    from sklearn.preprocessing import StandardScaler

    from .data import FEATURES, SCALE_COLS, WARMUP_ROWS
    from .metrics import rmse

    df = data.full_prepared
    result: dict[str, float] = {}

    for year in (2024, 2025):
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-01")

        train_df = df.loc[df["month"] < year_start].copy()
        test_df = df.loc[(df["month"] >= year_start) & (df["month"] <= year_end)].copy()

        if train_df.empty or test_df.empty:
            continue

        # Misma política anti-fuga que el split principal
        train_df = train_df.iloc[WARMUP_ROWS:].copy()

        y_tr = train_df["revenue_usd"].astype(float)
        y_te = test_df["revenue_usd"].astype(float)

        scaler = StandardScaler()
        scaler.fit(train_df[SCALE_COLS])
        X_tr = train_df[FEATURES].copy()
        X_te = test_df[FEATURES].copy()
        X_tr[SCALE_COLS] = scaler.transform(train_df[SCALE_COLS])
        X_te[SCALE_COLS] = scaler.transform(test_df[SCALE_COLS])

        m = XGBRegressor(**XGB_PARAMS)
        m.fit(X_tr, y_tr)
        pred = m.predict(X_te)
        result[str(year)] = float(rmse(y_te.to_numpy(), pred))

    return result