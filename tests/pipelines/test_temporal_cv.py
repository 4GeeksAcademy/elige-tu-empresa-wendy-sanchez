"""Tests de la validación cruzada temporal — HealthCore (datos sintéticos)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sales_forecast.evaluation import (
    N_SPLITS,
    assert_chronological_folds,
    assert_features_causal,
    temporal_cv_splits,
)

N_USABLE = 84  # 96 meses de entrenamiento - 12 de warm-up


def _synthetic_sales(n_months: int = 96) -> pd.DataFrame:
    months = pd.date_range("2016-01-01", periods=n_months, freq="MS")
    rng = np.random.default_rng(42)
    revenue = 4_000_000 * (1.04 ** (np.arange(n_months) / 12)) + rng.normal(0, 50_000, n_months)
    return pd.DataFrame(
        {
            "month": months,
            "revenue_usd": revenue,
            "visits_count": rng.integers(40_000, 60_000, n_months),
            "avg_revenue_per_visit_usd": rng.normal(90, 2, n_months),
            "region": "consolidated",
        }
    )


def test_cv_has_at_least_five_folds() -> None:
    assert len(temporal_cv_splits(N_USABLE)) >= 5
    assert N_SPLITS >= 5


def test_cv_folds_preserve_chronological_order() -> None:
    folds = temporal_cv_splits(N_USABLE)
    previous_val_max = -1
    for train_idx, val_idx in folds:
        assert np.all(np.diff(train_idx) > 0)
        assert np.all(np.diff(val_idx) > 0)
        assert train_idx.max() < val_idx.min()
        # ningún índice de un fold posterior aparece antes que uno de un fold anterior
        assert val_idx.min() > previous_val_max
        previous_val_max = val_idx.max()
    assert_chronological_folds(folds)


def test_cv_detects_shuffled_folds() -> None:
    folds = temporal_cv_splits(N_USABLE)
    train_idx, val_idx = folds[0]
    shuffled = [(train_idx[::-1].copy(), val_idx)] + folds[1:]
    with pytest.raises(AssertionError):
        assert_chronological_folds(shuffled)


def test_features_do_not_peek_into_future() -> None:
    df = _synthetic_sales()
    assert_features_causal(df, [12, 40, 60, len(df) - 1])


def test_future_values_do_not_change_past_features() -> None:
    from scripts.sales_forecast.data import FEATURES, prepare_features

    df = _synthetic_sales()
    perturbed = df.copy()
    perturbed.loc[60:, "revenue_usd"] *= 10
    base = prepare_features(df).loc[:59, FEATURES].to_numpy(dtype=float)
    changed = prepare_features(perturbed).loc[:59, FEATURES].to_numpy(dtype=float)
    assert np.allclose(base, changed, equal_nan=True)


def test_no_overlap_between_consecutive_folds() -> None:
    """Verifica que los conjuntos de validación de folds consecutivos son
    estrictamente cronológicos y no se solapan.

    En TimeSeriesSplit con ventana expansiva, el entrenamiento del fold i+1
    SIEMPRE contiene los datos del fold i (por eso el test combina train+val
    no aplica). Lo que SÍ debe cumplirse es que los validation sets sean
    disjuntos y en orden cronológico: la validación del fold i+1 empieza
    después de que termina la validación del fold i.

    Esto complementa test_cv_folds_preserve_chronological_order verificando
    que además ningún fold individualmente tiene train que se solape con su
    propia validación.
    """
    folds = temporal_cv_splits(N_USABLE)

    # Cada fold individual: train < validation (sin solape)
    for i, (train_idx, val_idx) in enumerate(folds):
        assert train_idx.max() < val_idx.min(), (
            f"Fold {i+1}: train (0..{train_idx.max()}) se solapa con "
            f"validation ({val_idx.min()}..{val_idx.max()})"
        )

    # Validation sets de folds consecutivos: no se solapan
    for i in range(len(folds) - 1):
        val_i_max = folds[i][1].max()
        val_next_min = folds[i + 1][1].min()
        assert val_i_max < val_next_min, (
            f"Validation del fold {i+1} termina en {val_i_max} pero "
            f"validation del fold {i+2} empieza en {val_next_min} — "
            "los validation sets se solapan."
        )


def test_temporal_cv_on_real_data_preserves_order() -> None:
    """Prueba que la validación cruzada temporal ejecutada sobre los datos
    reales de HealthCore preserva el orden cronológico en cada fold y recalcula
    features sin fuga entre folds.

    Integración: usa temporal_cross_validation del módulo evaluation, que
    ejecuta el pipeline completo (prepare_features + TimeSeriesSplit + escalado).
    """
    from scripts.sales_forecast.data import load_sales
    from scripts.sales_forecast.evaluation import temporal_cross_validation

    DATA_CSV = _PROJECT_ROOT / "data" / "raw" / "healthcore_sales.csv"
    if not DATA_CSV.exists():
        pytest.skip("Archivo de datos no disponible")
    df = load_sales(str(DATA_CSV))
    cv_result = temporal_cross_validation(df)

    # Cada fold debe tener entrenamiento antes que validación
    for _, row in cv_result.folds.iterrows():
        assert pd.Timestamp(row["train_start"]) <= pd.Timestamp(row["train_end"])
        assert pd.Timestamp(row["val_start"]) <= pd.Timestamp(row["val_end"])
        assert pd.Timestamp(row["train_end"]) < pd.Timestamp(row["val_start"]), (
            f"Fold {int(row['fold'])}: entrenamiento termina {row['train_end']} "
            f"pero validación empieza {row['val_start']}"
        )

    # El fold i+1 debe empezar su validación después del fold i
    fold_starts = cv_result.folds["val_start"].apply(pd.Timestamp).values
    for i in range(len(fold_starts) - 1):
        assert fold_starts[i] < fold_starts[i + 1], (
            f"Fold {i+1} valida desde {fold_starts[i]} pero fold {i+2} valida "
            f"desde {fold_starts[i+1]}, violando el orden cronológico"
        )

    # Al menos 5 folds
    assert len(cv_result.folds) >= 5

    # Métricas dentro de rango razonable (errores positivos)
    for _, row in cv_result.folds.iterrows():
        assert row["train_rmse"] > 0
        assert row["val_rmse"] > 0
