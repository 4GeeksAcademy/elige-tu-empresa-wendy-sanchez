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
