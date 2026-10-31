"""Métricas de evaluación del pronóstico de ventas — HealthCore.

Cuatro métricas, cada una con una historia distinta para Finanzas:

    - ``mse``                  Error cuadrático medio (USD²) y su versión %
                               del ingreso medio. Mide *cuánto* nos
                               equivocamos en promedio.
    - ``psi``                  Population Stability Index. Mide si la
                               distribución de la variable cambió de forma
                               significativa entre entrenamiento y prueba
                               (deriva de población / drift).
    - ``gini``                 Gini predictivo (= 2·C − 1, con C la
                               concordancia). Mide si el modelo *ordena*
                               correctamente los meses (distingue un mes alto
                               de uno bajo), algo que le importa a Sandra para
                               detectar caídas atípicas.
    - ``k2_score``             = R² (coeficiente de determinación). Mide qué
                               fracción de la variabilidad mensual de los
                               ingresos explica el modelo.

¿Por qué un MSE bajo no basta? Un modelo puede "memorizar" el pasado (por
ejemplo copiando el lag_1) y aun así tener MSE pequeño sobre esos mismos
datos: en series temporales el lag_1 es un predictor tan fuerte que el error
bruto puede parecer engañosamente bajo. Por eso:
    - Medimos el error en un bloque de prueba que el modelo NO vio durante el
      entrenamiento (honestidad temporal, ver data.split).
    - Cruzamos el error absoluto (MSE) con métricas de *distribución* (PSI),
      de *ordenamiento* (Gini) y de *varianza explicada* (K2/R²).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Umbrales estándar del PSI (fuente: práctica habitual en modelos de riesgo)
PSI_STABLE = 0.10
PSI_MODERATE = 0.25


def mse(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Error cuadrático medio, en USD²."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean((y_true - y_pred) ** 2))


def rmse(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Raíz del error cuadrático medio, en USD (misma unidad que los ingresos)."""
    return float(np.sqrt(mse(y_true, y_pred)))


def mse_as_pct_of_avg_revenue(
    mse_value: float, y_train: np.ndarray | pd.Series
) -> float:
    """MSE en % del ingreso mensual promedio (para Tom y Sandra, CONTEXT.md §3).

    Devuelve el porcentaje usando la raíz del MSE (misma unidad que el
    ingreso) dividido por el promedio mensual de ingresos.
    """
    avg_revenue = float(np.mean(np.asarray(y_train, dtype=float)))
    if avg_revenue == 0:
        raise ValueError("El promedio de ingresos es 0; no se puede normalizar.")
    return float(np.sqrt(mse_value) / avg_revenue * 100.0)


def mape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Mean Absolute Percentage Error, en % (0-100).

    Es la métrica más fácil de explicar a Finanzas: "en promedio, el pronóstico
    se desvía un X% de lo que realmente se facturó". Se protege contra
    división por cero con un epsilon.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    eps = 1e-9
    ape = np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), eps))
    return float(np.mean(ape) * 100.0)


def psi(expected: np.ndarray | pd.Series, actual: np.ndarray | pd.Series, bins: int = 5) -> float:
    """Population Stability Index entre dos distribuciones.

    PSI = sum((A_i - E_i) * ln(A_i / E_i)) sobre ``bins`` intervalos
    equiprobables construidos con la distribución *esperada* (entrenamiento).

    Nota sobre ``bins``: el estándar de industria usa 10 bandas cuando hay
    miles de observaciones. Aquí el conjunto de prueba tiene solo 24 meses, y
    el tramo de crecimiento interanual solo 12 puntos: con 10 bins casi cada
    banda tendría 1 observación y el PSI se inflaría por ruido de muestreo, no
    por drift real. Usamos 5 bins (≈5 puntos de prueba por banda), que es lo
    que la muestra soporta honestamente.

    Interpretación estándar:
        PSI < 0.10   -> sin cambio significativo (estable).
        0.10-0.25    -> cambio moderado (revisable).
        PSI > 0.25   -> cambio importante (la población cambió; el modelo
                        podría estar prediciendo una realidad distinta).

    En este caso se aplica sobre la distribución de ``revenue_usd`` mensual
    entre entrenamiento y prueba, para detectar si el nivel de ingresos se
    desplazó (crecimiento) o si la mezcla cambió de forma abrupta. Limitación
    honesta: el CSV provisto solo trae la serie ``consolidated``, por lo que
    no podemos calcular el PSI sobre la proporción US/UK a partir de este
    archivo (CONTEXT.md §3 lo menciona como caso de uso ideal).
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    if len(expected) == 0 or len(actual) == 0:
        raise ValueError("PSI requiere distribuciones no vacías.")

    # Cortes equiprobables sobre la distribución esperada (entrenamiento)
    eps = 1e-6
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    cutoffs = np.quantile(expected, quantiles)
    cutoffs[0] = -np.inf
    cutoffs[-1] = np.inf
    # Evitar cortes idénticos (deflación) colapsando duplicados
    cutoffs = np.unique(cutoffs)

    exp_counts, _ = np.histogram(expected, bins=cutoffs)
    act_counts, _ = np.histogram(actual, bins=cutoffs)

    exp_pct = exp_counts / max(len(expected), 1)
    act_pct = act_counts / max(len(actual), 1)

    # Epsilon en el denominador para evitar ln(0); exp_share 0 -> contribución 0
    exp_pct_safe = np.where(exp_pct == 0, eps, exp_pct)
    act_pct_safe = np.where(act_pct == 0, eps, act_pct)

    contributions = (exp_pct - act_pct_safe) * np.log(
        exp_pct_safe / np.maximum(act_pct_safe, eps)
    )
    contributions[exp_pct == 0] = 0.0
    return float(np.sum(contributions))


def psi_growth_adjusted(
    expected: pd.Series | np.ndarray,
    actual: pd.Series | np.ndarray,
    periods_per_year: int = 12,
    bins: int = 5,
) -> float:
    """PSI estabilizado del *crecimiento*, no del *nivel* de ingresos.

    En series de ingresos con crecimiento estructural (CONTEXT.md §4: +4%±2%
    anual), comparar el nivel bruto entre 2016-2023 y 2024-2025 da un PSI muy
    alto por diseño: la media de prueba es ~20% mayor que la de entrenamiento
    por la simple marcha del negocio, no por un cambio de población o mezcla.

    La forma correcta de medir *drift* en ese caso es sobre la **tasa de
    crecimiento interanual** (log-revenue − log-revenue de 12 meses antes).
    Así se comparan "cómo crece" los años de entreno vs los de prueba, no
    "cuánto ingresa" cada bloque. Un PSI bajo aquí significa que el patrón de
    crecimiento se mantuvo estable.

    Devuelve ``NaN`` si no hay suficientes puntos (menos de 2 años).
    """
    exp_g = _log_growth(expected, periods_per_year)
    act_g = _log_growth(actual, periods_per_year)
    if len(exp_g) < 2 or len(act_g) < 2:
        return float("nan")
    return psi(exp_g, act_g, bins=bins)


def _log_growth(values: pd.Series | np.ndarray, periods_per_year: int) -> np.ndarray:
    """Log-crecimiento interanual (log de revenue t − log de revenue t-k)."""
    arr = np.asarray(values, dtype=float)
    if len(arr) <= periods_per_year:
        return np.array([])
    return np.log(arr[periods_per_year:]) - np.log(np.maximum(arr[:-periods_per_year], 1e-9))


def gini_predictive(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """Gini predictivo = 2·C − 1, donde C es la concordancia (C-statistic).

    C = probabilidad de que, ante dos meses A y B con ingreso real distinto,
    el modelo asigne mayor predicción al mes que realmente tuvo MAYOR ingreso.

        Gini = 0 -> el modelo no ordena mejor que el azar.
        Gini = 1 -> ordenamiento perfecto (toda caída alta/baja bien ubicada).
        Gini ~ 0.5+ -> capacidad de discriminación útil (típico en
                       modelos de riesgo/segmentación).

    Para Sandra (CONTEXT.md §3): un Gini alto significa que el modelo distingue
    con confianza un mes de temporada baja "normal" (jul-ago) de una caída
    atípica que amerite atención.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_true)
    if n < 2:
        raise ValueError("Gini requiere al menos 2 observaciones.")

    concordant = 0.0
    discordant = 0.0
    treshold_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            # Diferencia real entre dos meses
            delta_real = y_true[i] - y_true[j]
            if delta_real == 0:
                continue
            treshold_pairs += 1
            delta_pred = y_pred[i] - y_pred[j]
            if delta_real > 0 and delta_pred > 0:
                concordant += 1.0
            elif delta_real > 0 and delta_pred < 0:
                discordant += 1.0
            elif delta_real < 0 and delta_pred < 0:
                concordant += 1.0
            elif delta_real < 0 and delta_pred > 0:
                discordant += 1.0
            else:
                concordant += 0.5
                discordant += 0.5
    if treshold_pairs == 0:
        return 0.0
    c = concordant / treshold_pairs
    return float(2.0 * c - 1.0)


def k2_score(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    """K2 Score = R² (coeficiente de determinación).

    Fracción de la variabilidad mensual de los ingresos que el modelo explica
    respecto a la media del periodo:

        R² = 1 − SSE / SST = 1 − (MSE·n) / Σ(y − ybar)²

    Interpretación para Finanzas (no caja negra):
        R² = 0.80  -> el modelo explica el 80% de la varianza del ingreso
                      mensual; el 20% restante queda sin explicar (ruido,
                      eventos puntuales).

    Nota de terminología: en esta implementación "K2" se mapea al coeficiente
    de determinación R², la métrica canónica de bondad de ajuste para
    regresión (sklearn ``r2_score``), que es la que responde "¿qué fracción de
    la variabilidad captura el modelo?" exigida en el hito.
    """
    from sklearn.metrics import r2_score

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(r2_score(y_true, y_pred))


def metrics_table(
    y_train_true: np.ndarray | pd.Series,
    y_train_pred: np.ndarray | pd.Series,
    y_test_true: np.ndarray | pd.Series,
    y_test_pred: np.ndarray | pd.Series,
) -> dict[str, float]:
    """Agrupa las 4 métricas (MSE, PSI, Gini, K2) sobre el conjunto de prueba.

    El PSI compara la distribución del target **en entrenamiento frente a la
    de prueba** (drift de la variable que Finanzas observa):
        psi(expected=distribución entrenamiento, actual=distribución prueba).
    """
    mse_value = mse(y_test_true, y_test_pred)
    psi_value = psi(y_train_true, y_test_true)
    psi_growth_value = psi_growth_adjusted(y_train_true, y_test_true)
    gini_value = gini_predictive(y_test_true, y_test_pred)
    k2 = k2_score(y_test_true, y_test_pred)

    return {
        "mse": mse_value,
        "rmse": rmse(y_test_true, y_test_pred),
        "mse_pct_avg": mse_as_pct_of_avg_revenue(mse_value, y_train_true),
        "mape_pct": mape(y_test_true, y_test_pred),
        "psi": psi_value,
        "psi_growth_adjusted": psi_growth_value,
        "gini": gini_value,
        "k2": k2,
    }