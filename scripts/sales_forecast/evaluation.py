"""Evaluación bias/varianza del modelo de pronóstico — HealthCore.

Referencia: CONTEXT.md — "HealthCore - Modelo de pronóstico de series de tiempo
para predicción de ventas". Target: ``revenue_usd`` (fila ``consolidated``).

Todo se calcula SOLO sobre los 8 años de entrenamiento (2016-01..2023-12); el
conjunto de prueba 2024-2025 no se toca.

Garantías anti-fuga:
    - ``TimeSeriesSplit`` nunca baraja: los índices de cada fold son crecientes
      y todos los de validación son posteriores a los de entrenamiento.
    - Las features se recalculan por fold sobre la serie cruda truncada en el
      último mes de validación, y ``assert_features_causal`` comprueba que el
      valor de cada feature en el mes t es idéntico con y sin los meses futuros.
    - El ``StandardScaler`` se ajusta con el entrenamiento de cada fold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from .data import FEATURES, SCALE_COLS, TEST_START, WARMUP_ROWS, prepare_features
from .metrics import rmse
from .model import XGB_PARAMS

N_SPLITS = 5
VALIDATION_MONTHS = 12  # cada fold valida un año completo (ciclo estacional)


def mae(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Error absoluto medio en USD."""
    diff = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(diff)))


def temporal_cv_splits(
    n_samples: int, n_splits: int = N_SPLITS, test_size: int = VALIDATION_MONTHS
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Folds de ``TimeSeriesSplit`` (ventana expansiva, sin barajar)."""
    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
    return list(splitter.split(np.arange(n_samples)))


def assert_chronological_folds(folds: list[tuple[np.ndarray, np.ndarray]]) -> None:
    """Lanza ``AssertionError`` si algún fold mezcla o baraja el orden temporal."""
    previous_val_max = -1
    for i, (train_idx, val_idx) in enumerate(folds):
        assert np.all(np.diff(train_idx) > 0), f"fold {i}: train no está ordenado"
        assert np.all(np.diff(val_idx) > 0), f"fold {i}: validación no está ordenada"
        assert train_idx.max() < val_idx.min(), f"fold {i}: train se solapa con validación"
        assert val_idx.min() > previous_val_max, (
            f"fold {i}: validación empieza antes de que termine la del fold anterior"
        )
        previous_val_max = val_idx.max()


def assert_features_causal(
    df_raw: pd.DataFrame, cutoff_positions: list[int], atol: float = 1e-9
) -> None:
    """Verifica que las features no miran al futuro.

    Para cada posición de corte ``c``, las features calculadas con solo las
    filas ``[0, c]`` deben ser idénticas a las calculadas con la serie completa
    en esas mismas filas. Si un lag/rolling usara datos posteriores, diferirían.
    """
    full = prepare_features(df_raw).reset_index(drop=True)
    for c in cutoff_positions:
        truncated = prepare_features(df_raw.iloc[: c + 1]).reset_index(drop=True)
        a = full.loc[: c, FEATURES].to_numpy(dtype=float)
        b = truncated[FEATURES].to_numpy(dtype=float)
        if not np.allclose(a, b, atol=atol, equal_nan=True):
            raise AssertionError(f"Fuga de información: features difieren en el corte {c}")


def _fit_predict(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    params: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Ajusta escalador y modelo con ``train_df``; predice train y validación."""
    scale_cols = [c for c in SCALE_COLS if c in features]
    x_tr = train_df[features].copy()
    x_va = val_df[features].copy()
    if scale_cols:
        scaler = StandardScaler().fit(train_df[scale_cols])
        x_tr[scale_cols] = scaler.transform(train_df[scale_cols])
        x_va[scale_cols] = scaler.transform(val_df[scale_cols])
    model = XGBRegressor(**params)
    model.fit(x_tr, train_df["revenue_usd"].astype(float))
    return model.predict(x_tr), model.predict(x_va)


def _train_portion(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Serie cruda restringida a 2016-01..2023-12 (sin tocar la prueba)."""
    return df_raw.loc[df_raw["month"] < TEST_START].reset_index(drop=True)


@dataclass
class CVResult:
    """Métricas por fold de la validación cruzada temporal."""

    folds: pd.DataFrame

    def summary(self) -> dict[str, tuple[float, float]]:
        cols = ["train_mae", "val_mae", "train_rmse", "val_rmse"]
        return {c: (float(self.folds[c].mean()), float(self.folds[c].std(ddof=1))) for c in cols}


def temporal_cross_validation(
    df_raw: pd.DataFrame,
    features: list[str] | None = None,
    params: dict | None = None,
    n_splits: int = N_SPLITS,
) -> CVResult:
    """Validación cruzada temporal con features recalculadas por fold."""
    features = features or FEATURES
    params = params or XGB_PARAMS
    raw = _train_portion(df_raw)
    # Los índices del split se definen sobre las filas útiles (tras el warm-up).
    n_usable = len(raw) - WARMUP_ROWS
    folds = temporal_cv_splits(n_usable, n_splits)
    assert_chronological_folds(folds)
    assert_features_causal(
        raw, [WARMUP_ROWS + int(v.min()) for _, v in folds] + [len(raw) - 1]
    )

    rows = []
    for k, (tr_idx, va_idx) in enumerate(folds, start=1):
        last_val = WARMUP_ROWS + int(va_idx.max())
        prepared = prepare_features(raw.iloc[: last_val + 1]).iloc[WARMUP_ROWS:]
        prepared = prepared.reset_index(drop=True)
        tr, va = prepared.iloc[tr_idx], prepared.iloc[va_idx]
        p_tr, p_va = _fit_predict(tr, va, features, params)
        y_tr, y_va = tr["revenue_usd"].to_numpy(), va["revenue_usd"].to_numpy()
        rows.append(
            {
                "fold": k,
                "train_start": tr["month"].min().strftime("%Y-%m"),
                "train_end": tr["month"].max().strftime("%Y-%m"),
                "val_start": va["month"].min().strftime("%Y-%m"),
                "val_end": va["month"].max().strftime("%Y-%m"),
                "n_train": len(tr),
                "train_mae": mae(y_tr, p_tr),
                "val_mae": mae(y_va, p_va),
                "train_rmse": float(rmse(y_tr, p_tr)),
                "val_rmse": float(rmse(y_va, p_va)),
                # Sesgo con signo: >0 = el modelo sobreestima ingresos
                "val_bias_usd": float(np.mean(p_va - y_va)),
            }
        )
    return CVResult(folds=pd.DataFrame(rows))


def learning_curve(
    df_raw: pd.DataFrame,
    features: list[str] | None = None,
    params: dict | None = None,
    min_train_months: int = 24,
    step: int = 6,
    holdout_months: int = VALIDATION_MONTHS,
) -> pd.DataFrame:
    """Error de entrenamiento y validación vs. tamaño del entrenamiento.

    La validación es un bloque fijo (los últimos ``holdout_months`` del
    entrenamiento, 2023) para que las curvas sean comparables; el entrenamiento
    crece con ventana expansiva terminando justo antes de ese bloque.
    """
    features = features or FEATURES
    params = params or XGB_PARAMS
    raw = _train_portion(df_raw)
    prepared = prepare_features(raw).iloc[WARMUP_ROWS:].reset_index(drop=True)
    val = prepared.iloc[-holdout_months:]
    pool = prepared.iloc[:-holdout_months]

    rows = []
    for n in range(min_train_months, len(pool) + 1, step):
        tr = pool.iloc[len(pool) - n :]  # los n meses más recientes antes del holdout
        p_tr, p_va = _fit_predict(tr, val, features, params)
        y_tr, y_va = tr["revenue_usd"].to_numpy(), val["revenue_usd"].to_numpy()
        rows.append(
            {
                "n_train": n,
                "train_rmse": float(rmse(y_tr, p_tr)),
                "val_rmse": float(rmse(y_va, p_va)),
                "train_mae": mae(y_tr, p_tr),
                "val_mae": mae(y_va, p_va),
            }
        )
    return pd.DataFrame(rows)


def plot_learning_curve(curve: pd.DataFrame, out_path: str, metric: str = "rmse") -> None:
    """Guarda la curva de aprendizaje (error train vs. validación) en PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(curve["n_train"], curve[f"train_{metric}"], "o-", label=f"Entrenamiento ({metric.upper()})")
    ax.plot(curve["n_train"], curve[f"val_{metric}"], "s-", label=f"Validación 2023 ({metric.upper()})")
    ax.set_xlabel("Meses de entrenamiento")
    ax.set_ylabel(f"{metric.upper()} de revenue_usd (USD)")
    ax.set_title("HealthCore — curva de aprendizaje (revenue_usd, consolidated)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
