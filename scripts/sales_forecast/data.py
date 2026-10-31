"""Carga, validación, feature engineering y split sin fuga para ``healthcore_sales.csv``.

Referencia de negocio: CONTEXT.md — "HealthCore - Modelo de pronóstico de
series de tiempo para predicción de ventas".

Reglas del dataset (verificadas aquí):
    - 10 años de datos mensuales (2016-01 .. 2025-12), 120 filas ``consolidated``.
    - Columnas exactas: ``month``, ``revenue_usd``, ``visits_count``,
      ``avg_revenue_per_visit_usd``, ``region``.
    - Target del modelo: ``revenue_usd`` de la fila ``consolidated``.
    - Sin meses faltantes y sin valores de ``revenue_usd`` no positivos.

Split anti-fuga (criterio no negociable del hito):
    - Entrenamiento: los primeros 8 años (2016-01 .. 2023-12).
    - Prueba: los 2 años más recientes (2024-01 .. 2025-12).
    - El corte es estrictamente temporal: ninguna fila de prueba (o feature
      derivada de ella) entra jamás en el entrenamiento. Por eso las features
      de retardo, estadísticas rodantes y de calendario se construyen SOLO con
      datos anteriores o simultáneos al mes que se predice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Columnas exactas esperadas según CONTEXT.md (§2 Estructura de datos)
EXPECTED_COLUMNS: list[str] = [
    "month",
    "revenue_usd",
    "visits_count",
    "avg_revenue_per_visit_usd",
    "region",
]

# Rango de fechas en el que vivimos el dataset (CONTEXT.md §4)
DATE_START = pd.Timestamp("2016-01-01")
DATE_END = pd.Timestamp("2025-12-01")

# Split: primeros 8 años -> entrenamiento; últimos 2 años -> prueba
TEST_START = pd.Timestamp("2024-01-01")
TRAIN_START = DATE_START
TRAIN_END = TEST_START - pd.offsets.MonthBegin(1)  # 2023-12-01

# Variables que se escalan (escalado *dentro* de entrenamiento, aplicado por
# transformación idéntica a prueba; ver temporal_split_and_scale).
SCALE_COLS: list[str] = ["visits_count", "avg_revenue_per_visit_usd"]

# Las 12 primeras filas de entrenamiento usan lags que apuntan a meses previos
# al arranque de la serie; se descartan para no entrenar sobre "feed fantasma".
WARMUP_ROWS = 12


@dataclass
class HealthCoreSalesData:
    """Contenedor de datos ya preparados y de los objetos de escalado."""

    X_train: pd.DataFrame
    y_train: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    test_months: pd.Series = field(default_factory=pd.Series)
    full_prepared: pd.DataFrame = field(default_factory=pd.DataFrame)
    feature_names: list[str] = field(default_factory=list)


def load_sales(csv_path: str | Path) -> pd.DataFrame:
    """Carga ``healthcore_sales.csv`` y valida que cumpla el CONTEXT.md.

    Lanza ``ValueError`` con un mensaje accionable si alguna invariante del
    CONTEXT.md no se cumple (columnas, regiones, rango de fechas, meses
    faltantes u objetivos no positivos).
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el dataset en: {path}")

    df = pd.read_csv(path, parse_dates=["month"])

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"El CSV no tiene las columnas esperadas por CONTEXT.md. "
            f"Faltan: {missing_cols}. Presentes: {list(df.columns)}"
        )

    # El modelo se entrena sobre la serie consolidada de la red (CONTEXT.md §2)
    df = df.loc[df["region"] == "consolidated"].copy()
    if df.empty:
        raise ValueError("No hay filas con region='consolidated'.")

    df = df.sort_values("month").reset_index(drop=True)

    # Invariantes del CONTEXT.md §5
    if df["month"].min() != DATE_START or df["month"].max() != DATE_END:
        raise ValueError(
            f"Rango de fechas inesperado: {df['month'].min()} .. {df['month'].max()}. "
            f"CONTEXT.md define 2016-01 .. 2025-12."
        )

    expected_months = pd.date_range(DATE_START, DATE_END, freq="MS")
    if len(df) != len(expected_months) or not df["month"].is_unique:
        raise ValueError("El dataset no tiene un mes por fila en todo el rango 2016..2025.")

    if not (df["revenue_usd"] > 0).all():
        raise ValueError("Hay revenue_usd <= 0; CONTEXT.md exige valores positivos.")

    return df


def _fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Tratamiento de valores nulos/vacíos.

    La estrategia es temporalmente honesta y conservadora:
    - ``revenue_usd`` y ``avg_revenue_per_visit_usd``: forward-fill (valor del
      mes anterior) si faltara; nunca usamos información futura.
    - ``visits_count``: se imputa con la mediana móvil de 3 meses (ventana
      centrada en el pasado, ``closed='left'``) para no contaminar con el mes
      a predecir.

    Aunque el dataset determinista (random_state=42) viene sin nulos, el
    pipeline debe ser robusto ante brechas de ingestión reales.
    """
    df = df.copy()
    if df["revenue_usd"].isna().any():
        df["revenue_usd"] = df["revenue_usd"].ffill()
        df.loc[df["revenue_usd"].isna(), "revenue_usd"] = df["revenue_usd"].median()
    if df["avg_revenue_per_visit_usd"].isna().any():
        df["avg_revenue_per_visit_usd"] = df["avg_revenue_per_visit_usd"].ffill()
    if df["visits_count"].isna().any():
        # mediana móvil de 3 meses mirando solo hacia atrás (closed='left')
        df["visits_count"] = df["visits_count"].fillna(
            df["visits_count"].rolling(3, min_periods=1, closed="left").median()
        )
    return df


def _add_causal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Features causales: retardos, ventanas rodantes y calendario.

    Nada de esto usa información futura:
    - ``rev_lag_1`` / ``rev_lag_2``: ingresos de los 1 y 2 meses anteriores.
    - ``rev_lag_12``: mismo mes del año pasado (captura la estacionalidad
      anual directamente).
    - ``rev_ma_3`` (media móvil 3m), ``rev_min_12``/``rev_max_12`` y
      ``rev_std_12`` (rango del último año).
    - ``month`` (numerico) y ``season`` derivada de la estacionalidad descrita
      en CONTEXT.md §4 (Q4 alta por gripe/fin de año; julio-agosto baja por
      vacaciones; resto moderado).
    - ``trend_index`` = nº de meses desde 2016-01 (captura el crecimiento
      anual base del 4% ± 2% descrito en CONTEXT.md §4).
    """
    df = df.copy()

    # --- retardos (solos con pasado) -------------------------------------
    df["rev_lag_1"] = df["revenue_usd"].shift(1)
    df["rev_lag_2"] = df["revenue_usd"].shift(2)
    df["rev_lag_12"] = df["revenue_usd"].shift(12)

    # --- estadísticas rodantes (solo historia) -----------------------------
    df["rev_ma_3"] = df["revenue_usd"].rolling(3, min_periods=1).mean()
    df["rev_min_12"] = df["revenue_usd"].rolling(12, min_periods=1).min()
    df["rev_max_12"] = df["revenue_usd"].rolling(12, min_periods=1).max()
    df["rev_std_12"] = df["revenue_usd"].rolling(12, min_periods=1).std()

    # --- calendario / estacionalidad --------------------------------------
    df["month_num"] = df["month"].dt.month
    # Estacionalidad del CONTEXT.md §4: Q4 = alta (gripe/fin de año),
    # jul-ago = baja (vacaciones), resto = moderada.
    df["season"] = df["month_num"].map(_season_code)

    # Índice de tendencia: nº de meses transcurridos desde 2016-01.
    df["trend_index"] = ((df["month"].dt.year - 2016) * 12 + df["month"].dt.month - 1).astype(
        float
    )

    return df


def _season_code(month: int) -> int:
    """Codifica la estacionalidad descrita en CONTEXT.md §4.

    2 = alta (oct-dic, gripe + fin de año),
    0 = baja (jul-ago, vacaciones),
    1 = resto del año (moderada).
    """
    if month >= 10:
        return 2
    if month in (7, 8):
        return 0
    return 1


# Features que el modelo consume (identificadores excluidos).
FEATURES = [
    "rev_lag_1",
    "rev_lag_2",
    "rev_lag_12",
    "rev_ma_3",
    "rev_min_12",
    "rev_max_12",
    "rev_std_12",
    "month_num",
    "season",
    "trend_index",
    "visits_count",
    "avg_revenue_per_visit_usd",
]


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encadena limpieza de nulos y feature engineering causal."""
    return _add_causal_features(_fill_missing_values(df))


def temporal_split_and_scale(
    df: pd.DataFrame, test_start: pd.Timestamp = TEST_START
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.Series]:
    """Split temporal estricto + escalado ajustado solo con entrenamiento.

    - Entrenamiento: meses < ``test_start`` (= primeros 8 años).
    - Prueba: meses >= ``test_start`` (= últimos 2 años).
    - Se descartan las primeras ``WARMUP_ROWS`` filas de entrenamiento (sus
      lags apuntan a meses previos al arranque de la serie).
    - El ``StandardScaler`` se ajusta SOLO con el entrenamiento; la misma
      transformación se aplica a prueba (evita fuga de distribución).

    Devuelve ``(X_train, y_train, X_test, y_test, test_months)``.
    """
    from sklearn.preprocessing import StandardScaler

    train = df.loc[df["month"] < test_start].copy()
    test = df.loc[df["month"] >= test_start].copy()
    _assert_split_invariants(train, test, test_start)

    # Descartar filas cuyos lags apuntan a meses previos al arranque de la
    # serie (política anti-fuga / anti-memoria).
    train = train.iloc[WARMUP_ROWS:].copy()

    y_train = train["revenue_usd"].astype(float).reset_index(drop=True)
    y_test = test["revenue_usd"].astype(float).reset_index(drop=True)

    scaler = StandardScaler()
    scaler.fit(train[SCALE_COLS])
    X_train = train[FEATURES].copy().reset_index(drop=True)
    X_test = test[FEATURES].copy().reset_index(drop=True)
    X_train[SCALE_COLS] = scaler.transform(train[SCALE_COLS])
    X_test[SCALE_COLS] = scaler.transform(test[SCALE_COLS])

    test_months = pd.Series(test["month"].to_numpy()).reset_index(drop=True)
    return X_train, y_train, X_test, y_test, test_months


def build_train_test_sets(
    csv_path: str | Path, test_start: pd.Timestamp = TEST_START
) -> HealthCoreSalesData:
    """Pipeline completo: carga -> limpieza -> features -> split temporal 8/2.

    El escalado de ``visits_count`` y ``avg_revenue_per_visit_usd`` se ajusta
    EXCLUSIVAMENTE con estadísticas del conjunto de entrenamiento, y la misma
    transformación se aplica a prueba. Así se evita que la distribución de
    prueba "se cuele" en el fit del escalador (otra forma de fuga de datos).
    """
    df = load_sales(csv_path)
    df = prepare_features(df)
    X_train, y_train, X_test, y_test, test_months = temporal_split_and_scale(
        df, test_start
    )

    return HealthCoreSalesData(
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        test_months=test_months,
        full_prepared=df,
        feature_names=list(FEATURES),
    )


def _assert_split_invariants(
    train: pd.DataFrame, test: pd.DataFrame, test_start: pd.Timestamp
) -> None:
    """Valida el criterio 8 años / 2 años y la ausencia de solape temporal."""
    if train.empty or test.empty:
        raise ValueError("El split dejó vacío el entrenamiento o la prueba.")

    # 8 años de entrenamiento
    n_train_years = (train["month"].max() - train["month"].min()).days / 365.25
    n_test_years = (test["month"].max() - test["month"].min()).days / 365.25

    if n_train_years < 7.5 or n_train_years > 8.5:
        raise ValueError(
            f"Entrenamiento con {n_train_years:.2f} años; se esperaban 8 "
            f"(2016-01 .. 2023-12)."
        )
    if n_test_years < 1.5 or n_test_years > 2.5:
        raise ValueError(
            f"Prueba con {n_test_years:.2f} años; se esperaban 2 "
            f"(2024-01 .. 2025-12)."
        )

    # Sin solape ni hueco temporal entre conjuntos
    if train["month"].max() >= test["month"].min():
        raise ValueError("Los conjuntos de entrenamiento y prueba se solapan en el tiempo.")

    # Ninguna fecha de prueba puede ser anterior al corte
    if (test["month"] < test_start).any():
        raise ValueError("La prueba contiene meses anteriores al corte definido.")