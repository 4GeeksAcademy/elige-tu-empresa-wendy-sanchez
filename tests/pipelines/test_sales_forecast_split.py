"""Tests del split temporal 8/2 y anti-fuga del modelo de ventas — HealthCore.

Valida el criterio no negociable del hito:
    1. La prueba son exactamente los 2 años más recientes (2024-2025).
    2. El entrenamiento son los 8 primeros años (2016-2023) sin solape.
    3. No hay fuga de datos entre conjuntos: ninguna fecha de prueba aparece
       en entrenamiento, y las features de lag no filtran el futuro.
    4. El escalador se ajusta solo con el entrenamiento.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Asegurar que el proyecto raíz está en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sales_forecast.data import (
    FEATURES,
    TEST_START,
    WARMUP_ROWS,
    build_train_test_sets,
    load_sales,
    prepare_features,
    temporal_split_and_scale,
)

DATA_CSV = _PROJECT_ROOT / "data" / "raw" / "healthcore_sales.csv"

REQUIRED_TEST_MONTHS = {"2024-01", "2024-12", "2025-01", "2025-12"}
REQUIRED_TRAIN_MONTHS = {"2016-01", "2016-12", "2023-01", "2023-12"}


@pytest.fixture(scope="module")
def data():
    return build_train_test_sets(DATA_CSV)


class TestSplitTemporalSinFuga:
    """Regla de oro: el modelo no ve los años de prueba durante el entreno."""

    def test_prueba_es_2_anios_recientes(self, data) -> None:
        """La prueba debe contener exactamente 24 meses: 2024-01 .. 2025-12."""
        months = pd.to_datetime(data.test_months)
        assert len(months) == 24
        assert months.min() == pd.Timestamp("2024-01-01")
        assert months.max() == pd.Timestamp("2025-12-01")
        assert set(months.dt.strftime("%Y-%m")) >= REQUIRED_TEST_MONTHS

    def test_entrenamiento_es_8_anios(self, data) -> None:
        """El entrenamiento debe cubrir 2016-01 .. 2023-12 y tener ~8 años."""
        # `data` no conserva el mes de train; lo verificamos desde la fuente.
        raw = load_sales(DATA_CSV)
        train_months = raw.loc[raw["month"] < TEST_START, "month"]
        assert train_months.min() == pd.Timestamp("2016-01-01")
        assert train_months.max() == pd.Timestamp("2023-12-01")
        assert set(train_months.dt.strftime("%Y-%m")) >= REQUIRED_TRAIN_MONTHS
        n_train_years = (train_months.max() - train_months.min()).days / 365.25
        assert 7.5 <= n_train_years <= 8.5

        # Regla 8 años / 2 años: 96 vs 24 meses
        assert len(train_months) == 96
        assert len(pd.to_datetime(data.test_months)) == 24

    def test_no_hay_solape_temporal(self, data) -> None:
        """Ninguna fecha de prueba puede existir en el entrenamiento."""
        raw = load_sales(DATA_CSV)
        train_months = set(raw.loc[raw["month"] < TEST_START, "month"])
        test_months = set(pd.to_datetime(data.test_months))
        overlap = train_months & test_months
        assert not overlap, f"Fuga temporal: {len(overlap)} meses compartidos"

    def test_corte_es_estrictamente_cronologico(self, data) -> None:
        """Todas las fechas de prueba son posteriores a todas las de entreno."""
        raw = load_sales(DATA_CSV)
        train_max = raw.loc[raw["month"] < TEST_START, "month"].max()
        test_min = pd.to_datetime(data.test_months).min()
        assert train_max < test_min

    def test_no_hay_fuga_en_features_de_lag(self, data) -> None:
        """Un mes de prueba NO puede ser fuente de features de un mes de entreno.

        Criterio: cada feature de lag usa solo el pasado del mismo mes. La
        prueba recorre las features de retardo manualmente: ``rev_lag_1`` en el
        mes t debe ser ``revenue_usd`` del mes t-1 (nunca futuro), y
        ``rev_lag_12`` en t debe ser ``revenue_usd`` del mes t-12.
        """
        raw = load_sales(DATA_CSV)
        prepared = prepare_features(raw).sort_values("month").reset_index(drop=True)

        # Lag 1: solo la primera fila no tiene pasado inmediato (2016-01).
        assert prepared["rev_lag_1"].iloc[0] is None or pd.isna(prepared["rev_lag_1"].iloc[0])
        np.testing.assert_allclose(
            prepared["rev_lag_1"].iloc[1:].to_numpy(),
            prepared["revenue_usd"].shift(1).iloc[1:].to_numpy(),
        )

        # Lag 12: las primeras 12 filas (2016) no tienen el mismo mes del año
        # anterior -> NaN (warm-up genuino). A partir de 2017 el lag_12 debe
        # coincidir exactamente con revenue_usd de 12 meses antes.
        assert prepared["rev_lag_12"].iloc[:12].isna().all()
        np.testing.assert_allclose(
            prepared["rev_lag_12"].iloc[12:].to_numpy(),
            prepared["revenue_usd"].shift(12).iloc[12:].to_numpy(),
        )

        # El pipeline descarta esas WARMUP_ROWS filas de entreno (política
        # anti-memoria) y las features de prueba se calculan solo con historia.
        assert WARMUP_ROWS == 12
        assert "rev_lag_1" in FEATURES and "rev_lag_12" in FEATURES

    def test_escalado_ajustado_solo_con_entrenamiento(self, data) -> None:
        """El StandardScaler no debe ver la distribución de prueba.

        Aserción numérica fuerte (no tautológica): reconstruimos la media/std
        del entrenamiento *crudo* y verificamos que la transformación aplicada
        es exactamente ``(x - mu_train) / sd_train`` con ``ddof=0``. Si el
        scaler se hubiera ajustado con train+test, tanto la reconstrucción de
        train como la de test fallarían.

        Nota: comprobar que ``mean(X_train escalado) == 0`` sería una
        tautología (siempre se cumple por construcción) y no demuestra nada.
        Este test se validó con un *mutation test*: al inyectar
        ``scaler.fit(concat(train, test))`` en ``data.py`` el test falla.
        """
        from scripts.sales_forecast.data import SCALE_COLS

        raw = prepare_features(load_sales(DATA_CSV))
        train_crud = raw.loc[raw["month"] < TEST_START].iloc[WARMUP_ROWS:]
        test_crud = raw.loc[raw["month"] >= TEST_START]

        for col in SCALE_COLS:
            mu_train = float(train_crud[col].mean())
            sd_train = float(train_crud[col].std(ddof=0))

            # (1) Reconstrucción exacta con estadísticas SOLO de entrenamiento
            expected_train = (train_crud[col].to_numpy() - mu_train) / sd_train
            np.testing.assert_allclose(
                data.X_train[col].to_numpy(), expected_train, rtol=1e-9, atol=1e-9,
                err_msg=f"{col}: el escalado de train no usa (x-mu_train)/sd_train",
            )
            expected_test = (test_crud[col].to_numpy() - mu_train) / sd_train
            np.testing.assert_allclose(
                data.X_test[col].to_numpy(), expected_test, rtol=1e-9, atol=1e-9,
                err_msg=f"{col}: el escalado de test no usa estadísticas de train (fuga)",
            )

            # (2) Discriminante de fuga: comparar contra las DOS hipótesis.
            #   - Hipótesis correcta: scaler ajustado SOLO con train -> la media
            #     de test escalado debe igualar (mu_test - mu_train)/sd_train.
            #   - Hipótesis de fuga: scaler ajustado con train+test -> la media
            #     de test escalado sería (mu_test - mu_all)/sd_all.
            # Exigimos que coincida con la primera y se DISTANCIE de la segunda.
            mean_scaled_test = float(data.X_test[col].mean())

            mu_all = float(pd.concat([train_crud[col], test_crud[col]]).mean())
            sd_all = float(pd.concat([train_crud[col], test_crud[col]]).std(ddof=0))
            expected_no_leak = (float(test_crud[col].mean()) - mu_train) / sd_train
            expected_leak = (float(test_crud[col].mean()) - mu_all) / sd_all

            assert abs(mean_scaled_test - expected_no_leak) < 1e-9, (
                f"{col}: la media de test escalado ({mean_scaled_test:.6f}) no "
                f"coincide con la esperada usando SOLO train ({expected_no_leak:.6f})"
            )
            assert abs(mean_scaled_test - expected_leak) > 1e-6, (
                f"{col}: la media de test escalado coincide con la hipótesis de "
                f"fuga (scaler ajustado con train+test); hay fuga de distribución"
            )


class TestDatasetCoincideConContexto:
    """Invariantes del CONTEXT.md §5."""

    def test_columnas_esperadas(self) -> None:
        raw = load_sales(DATA_CSV)
        assert list(raw.columns) == [
            "month",
            "revenue_usd",
            "visits_count",
            "avg_revenue_per_visit_usd",
            "region",
        ]

    def test_solo_serie_consolidada(self) -> None:
        raw = load_sales(DATA_CSV)
        assert set(raw["region"].unique()) == {"consolidated"}

    def test_120_meses_sin_huecos(self) -> None:
        raw = load_sales(DATA_CSV)
        assert len(raw) == 120
        assert raw["month"].is_monotonic_increasing

    def test_revenue_positivo(self) -> None:
        raw = load_sales(DATA_CSV)
        assert (raw["revenue_usd"] > 0).all()

    def test_target_es_revenue_usd(self) -> None:
        data = build_train_test_sets(DATA_CSV)
        assert data.y_train.name == "revenue_usd" or "revenue_usd" in data.X_train.columns
        # En este hito el target se extrae de la columna revenue_usd
        raw = load_sales(DATA_CSV)
        assert (raw["revenue_usd"] > 0).all()


class TestNombresDeFeatures:
    """Blinda la semántica de los nombres de features (evita nombres engañosos).

    Regresión de auditoría: ``rev_ma_12`` era en realidad un *máximo* rodante
    (``ma`` sugiere "moving average") y ``rev_mi_12`` un mínimo. Se renombraron
    a ``rev_max_12`` / ``rev_min_12``. Este test impide reintroducir el error.
    """

    def test_min_y_max_coinciden_con_pandas(self) -> None:
        from scripts.sales_forecast.data import prepare_features

        prepared = prepare_features(load_sales(DATA_CSV)).sort_values("month").reset_index(drop=True)

        np.testing.assert_allclose(
            prepared["rev_min_12"].to_numpy(),
            prepared["revenue_usd"].rolling(12, min_periods=1).min().to_numpy(),
        )
        np.testing.assert_allclose(
            prepared["rev_max_12"].to_numpy(),
            prepared["revenue_usd"].rolling(12, min_periods=1).max().to_numpy(),
        )
        # Y que el "max" es efectivamente >= que el "min" en todo momento.
        assert (prepared["rev_max_12"] >= prepared["rev_min_12"]).all()

    def test_no_hay_features_con_nombre_engañoso_ni_codigo_muerto(self) -> None:
        from scripts.sales_forecast.data import prepare_features

        prepared = prepare_features(load_sales(DATA_CSV))
        # Nombres antiguos (media rodante disfrazada de máximo) prohibidos.
        assert "rev_ma_12" not in prepared.columns
        assert "rev_mi_12" not in prepared.columns
        # ``year_num`` se calculaba pero nunca fue feature (código muerto): fuera.
        assert "year_num" not in prepared.columns
        # Todas las features declaradas existen realmente en el dataframe.
        missing = [f for f in FEATURES if f not in prepared.columns]
        assert not missing, f"Features declaradas inexistentes: {missing}"


class TestEntrenamientoYPrediccion:
    """Prueba funcional mínima: entrena y predice sin fuga aparente."""

    def test_prediccion_fuera_de_muestra_tiene_24_meses(self, data) -> None:
        from scripts.sales_forecast.model import train_sales_model

        result = train_sales_model(data)
        assert len(result.y_test_pred) == 24
        # La predicción debe ser finita y del mismo orden de magnitud que el
        # ingreso real de prueba.
        assert np.isfinite(result.y_test_pred).all()
        mean_real = float(np.mean(result.test_real))
        mean_pred = float(np.mean(result.y_test_pred))
        # Tolerancia generosa: el modelo no debe dispararse fuera de rango
        assert abs(mean_pred / mean_real - 1.0) < 0.5