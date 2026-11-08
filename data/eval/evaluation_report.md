# HealthCore — Evaluación técnica del modelo de pronóstico de ventas

**Fecha:** 2026-11-08 18:25 UTC
**Modelo:** XGBoost (regularizado)
**Target:** `revenue_usd` (serie consolidada)
**Split:** 8 años entrenamiento (2016-01..2023-12) / 2 años prueba (2024-01..2025-12)
**Dataset:** `data/raw/healthcore_sales.csv` (10 años, 120 filas mensuales)

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| **Diagnóstico** | **Sobreajuste (overfitting)** |
| RMSE prueba | $154,910 |
| MAPE prueba | 3.47% |
| Gini predictivo | 0.8188 |
| K² (R²) | 0.8104 |
| MSE (% ingreso medio) | 5.52% |
| Ingreso mensual medio (train) | $2,754,918 |
| Ingreso mensual medio (test) | $3,366,658 |

El modelo memoriza el ruido del entrenamiento y no generaliza bien al conjunto de validación.

---

## 2. Validación cruzada temporal (TimeSeriesSplit, 5 folds)

### 2.1 Estrategia

Se implementó `TimeSeriesSplit` de scikit-learn con ventana expansiva y
**validación de 12 meses por fold** (un ciclo estacional completo). Ningún fold
baraja los datos — el orden cronológico se preserva en cada split y se verifica
explícitamente mediante `assert_chronological_folds()`. Las features se
recalculan por fold sobre la serie truncada en el último mes de validación para
evitar fuga de información entre límites de folds (ver `assert_features_causal()`).

### 2.2 Resultados por fold

| Fold | Train (rango) | Val (rango) | n_train | Train MAE | Val MAE | Train RMSE | Val RMSE | Bias (USD) |
|------|--------------|-------------|--------|-----------|---------|------------|----------|-----------|
| 1 | 2017-01..2018-12 | 2019-01..2019-12 | 24 | $1,561.47 | $138,020.23 | $2,441.64 | $152,277.53 | $-128,032.57 |
| 2 | 2017-01..2019-12 | 2020-01..2020-12 | 36 | $2,802.93 | $67,117.39 | $5,321.47 | $85,277.82 | $-13,731.79 |
| 3 | 2017-01..2020-12 | 2021-01..2021-12 | 48 | $2,890.56 | $121,005.41 | $4,438.05 | $137,966.63 | $-111,469.88 |
| 4 | 2017-01..2021-12 | 2022-01..2022-12 | 60 | $3,695.60 | $140,318.63 | $5,359.66 | $171,693.69 | +$78,159.16 |
| 5 | 2017-01..2022-12 | 2023-01..2023-12 | 72 | $4,097.40 | $105,321.93 | $6,076.62 | $132,158.03 | $-67,559.72 |

### 2.3 Métricas agregadas (media ± desv. estándar)

| Métrica | Media | Desv. estándar |
|---------|-------|---------------|
| Train MAE | $3,009.59 | $975.69 |
| Val MAE | $114,356.72 | $29,964.02 |
| Train RMSE | $4,727.49 | $1,403.70 |
| Val RMSE | $135,874.74 | $32,133.66 |

**Brecha media train/val (RMSE):** $131,147.25 (ratio 28.7x)

### 2.4 Interpretación

- **Train RMSE** es sorprendentemente bajo ($4,727.49 ± $1,403.70).
  Esto se debe a que el modelo aprende los patrones de lag, estacionalidad y
  tendencia que son deterministas en el dataset.
- **Val RMSE** ($135,874.74 ± $32,133.66) es
  significativamente más alto, lo que genera una brecha de ~29x.
- Esta brecha es **persistente a través de todos los folds** — no disminuye
  cuando el entrenamiento crece de 24 a 72 meses.
- El **sesgo (bias)** por fold alterna entre sobreestimación y subestimación,
  lo que sugiere que el modelo captura la tendencia general pero se
  desincroniza con la fase estacional en el bloque de validación.

---

## 3. Curva de aprendizaje

### 3.1 Estrategia

La validación de la curva es un bloque fijo: los últimos 12 meses del conjunto
de entrenamiento (año 2023). El entrenamiento crece con ventana expansiva
desde 24 hasta 72 meses (los más recientes antes del bloque de validación).

### 3.2 Datos

| n_train | Train RMSE | Val RMSE | Train MAE | Val MAE |
|---------|-----------|---------|-----------|---------|
| 24 | $7,722.39 | $149,398.51 | $3,585.01 | $121,711.67 |
| 30 | $6,614.79 | $140,932.72 | $3,507.98 | $112,965.12 |
| 36 | $6,723.70 | $144,782.61 | $3,340.46 | $122,016.10 |
| 42 | $5,931.18 | $128,601.13 | $3,120.50 | $99,481.90 |
| 48 | $6,193.87 | $129,347.68 | $3,568.75 | $99,554.43 |
| 54 | $6,602.74 | $133,616.06 | $3,956.01 | $110,236.24 |
| 60 | $6,889.10 | $136,683.69 | $4,366.40 | $114,343.08 |
| 66 | $5,870.49 | $132,338.66 | $3,567.52 | $106,476.97 |
| 72 | $6,076.62 | $132,158.03 | $4,097.40 | $105,321.93 |

### 3.3 Análisis visual

Las imágenes están en:
- `data/eval/learning_curve_rmse.png`
- `data/eval/learning_curve_mae.png`

### 3.4 Interpretación de la curva

**Patrón observado:**
- **Train RMSE** es consistentemente bajo (~$7,722 → ~$6,077)
  a lo largo de todos los tamaños de entrenamiento. El modelo ajusta casi
  perfectamente los datos de entrenamiento.
- **Val RMSE** se mantiene alto y estable (~$132,158) sin
  importar cuántos meses de entrenamiento se añadan.
- Las dos curvas **NO convergen**. La brecha al final es de
  $126,081 (22x).

**Diagnóstico según criterio del ticket:**
- Ambas curvas **NO** convergen en un error alto → descartamos underfitting.
- Hay una **brecha amplia y persistente** entre entrenamiento (bajo) y
  validación (alto) que no se cierra al aumentar los datos → **overfitting**.

---

## 4. MAE vs RMSE — justificación

### 4.1 ¿Qué error es más costoso para HealthCore?

Según el CONTEXT.md (§§3-4):

> Sandra (CEO) necesita distinguir con confianza entre un mes de temporada baja
> normal (ej. agosto) y una caída atípica que amerite atención.
>
> Los ingresos oscilan entre ~$2M y ~$4M mensuales con:
> - **Q4 (oct-dic):** alza del 15-20% por temporada de gripe
> - **Jul-Ago:** caída del 12-18% por vacaciones
> - **Resto:** ±5% alrededor de la tendencia

**RMSE** es la métrica que mejor refleja el costo de negocio porque:

1. **Penaliza errores grandes de forma cuadrática.** Un error de $300K en un
   mes pico de Q4 (donde se concentra el 15-20% del ingreso anual) es
   desproporcionadamente más costoso que tres errores de $100K cada uno.
   Sandra necesita confianza en que el modelo no confundirá un mes pico con
   uno normal — un error así puede llevar a decisiones erróneas de capacidad
   clínica, contratación de personal temporal y compra de insumos.

2. **Sobreestimar es más costoso que subestimar** en el contexto de HealthCore.
   Si el modelo predice $4M cuando el ingreso real es $3.5M (sobreestimación),
   la clínica puede comprometer compras de insumos y contrataciones que no
   podrá sostener. Si predice $3.5M cuando son $4M (subestimación), deja
   capacidad ociosa pero no arriesga la liquidez. RMSE, al penalizar errores
   grandes sin distinción de signo, fuerza al modelo a minimizar errores
   severos en cualquier dirección.

3. **Tom (Revenue Cycle) y Sandra** necesitan que el MSE se reporte también
   como porcentaje del ingreso mensual promedio (CONTEXT.md §3), lo que
   confirma que el error absoluto en USD es la métrica primaria para la
   junta directiva.

**MAE** se reporta como complemento por su interpretabilidad directa:
"en promedio, el error absoluto es de $114357 por mes" (donde
114357 es el promedio de los MAE de validación de los 5 folds).

---

## 5. Diagnóstico final

### 5.1 Clasificación: **Sobreajuste (overfitting)**

**Evidencia que lo respalda:**

| Evidencia | Valor | Implicación |
|-----------|-------|-------------|
| Gap train/val RMSE (CV) | $131,147.25 (28.7x) | Brecha grande y persistente |
| Gap train/val RMSE (curva, n=72) | $126,081.41 (21.7x) | No converge al aumentar datos |
| Train RMSE estable bajo | ~$4,727 | El modelo memoriza el training set |
| Val RMSE estable alto | ~$135,875 | No mejora con más datos |
| Walk-forward RMSE 2024 | $134,459 | Error real fuera de muestra |
| Walk-forward RMSE 2025 | $136,268 | Error real fuera de muestra |

### 5.2 Causa raíz

El **`rev_lag_12`** y **`visits_count`** suman ~93%
de la importancia del modelo:

| `visits_count` | 48.94% |
| `rev_lag_12` | 43.95% |
| `trend_index` | 1.72% |
| `rev_min_12` | 1.09% |
| `rev_std_12` | 0.96% |
| `avg_revenue_per_visit_usd` | 0.89% |
| `season` | 0.84% |
| `month_num` | 0.53% |
| `rev_max_12` | 0.37% |
| `rev_lag_1` | 0.34% |
| `rev_lag_2` | 0.20% |
| `rev_ma_3` | 0.18% |

El modelo depende casi exclusivamente de:
1. **`visits_count`** (48.9%) — que es un componente directo del
   target (`revenue ≈ visits × price_per_visit`) y, aunque documentado como
   riesgo, crea un atajo de memorización.
2. **`rev_lag_12`** (44.0%) — el ingreso del mismo mes del año anterior,
   que captura la estacionalidad anual pero también arrastra el ruido de ese mes.

El resto de features (tendencia, estacionalidad, rodantes) tienen importancia
residual. El modelo básicamente "recuerda" el valor del año anterior y lo
corrige con el volumen de visitas actual — lo que explica por qué:
- Train error es bajísimo (el modelo tiene el `visits_count` del mes t,
  que casi determina `revenue_usd[t]`)
- Val error es alto (cuando `visits_count` y `rev_lag_12` no bastan para
  predecir un bloque futuro completo)

Adicionalmente, el **`rev_lag_12`** domina la predicción pero arrastra el
crecimiento interanual (4% ± 2%) como un offset fijo, no aprendido. Si el
crecimiento de 2024 es diferente del de 2023, el modelo falla
sistemáticamente.

### 5.3 Acción correctiva específica

**Problema:** el modelo tiene 2 features dominantes que crean un atajo de
memorización (`visits_count` como componente del target, `rev_lag_12` como
casi-copia del target con lag). El resto de features causales (tendencia,
estacionalidad, rodantes) quedan infrautilizadas.

**Acción correctiva (priorizada):**

1. **Eliminar `visits_count` y `avg_revenue_per_visit_usd` como features**
   (o reemplazarlas por predicciones de modelos auxiliares). Esto fuerza al
   modelo a aprender la dinámica temporal real de los ingresos a partir
   exclusivamente de lags, rodantes y calendario. Como documenta el
   propio `train_sales_forecast.py`, estas dos variables suman ~50%
   de la importancia y son componentes directos del target.

2. **Incrementar regularización L1 (`reg_alpha`) de 0.5 a 2.0** para que
   el modelo no pueda depender excesivamente de una sola feature. Si
   `reg_alpha=2.0`, el costo de usar `rev_lag_12` como predictor único se
   incrementa, forzando al modelo a distribuir el peso entre las features
   de tendencia (`trend_index`), estacionalidad (`season`, `month_num`) y
   las estadísticas rodantes (`rev_ma_3`, `rev_min_12`, `rev_max_12`,
   `rev_std_12`).

3. **Reducir `max_depth` de 4 a 3** para limitar interacciones complejas
   que el modelo no necesita con ~84 filas de entrenamiento efectivo.

**No se recomienda** aumentar la cantidad de datos como primera acción: la
curva de aprendizaje muestra que el error de validación no mejora al aumentar
el entrenamiento de 24 a 72 meses. El problema no es la cantidad de datos,
sino la arquitectura de features que permite la memorización.

---

## 6. Pruebas ejecutadas

### 6.1 Suite de tests completa

La suite de tests del pipeline de evaluación se ejecuta con:

```bash
uv run python -m pytest tests/pipelines/ -v
```

**Total: 64 tests · 64 pasaron · 0 fallaron**
**Ejecutado:** 2026-11-08 18:25 UTC

### 6.2 Tests de validación cruzada temporal (`test_temporal_cv.py`)

| Test | Estado | Lo que verifica |
|------|--------|-----------------|
| `test_cv_has_at_least_five_folds` | ✅ | N_SPLITS ≥ 5 |
| `test_cv_folds_preserve_chronological_order` | ✅ | train ordenado, val ordenado, train_max < val_min, folds consecutivos sin solape |
| `test_cv_detects_shuffled_folds` | ✅ | Si se invierten índices, `assert_chronological_folds()` lanza error |
| `test_features_do_not_peek_into_future` | ✅ | Features con datos truncados son idénticas a features con datos completos |
| `test_future_values_do_not_change_past_features` | ✅ | Multiplicar revenue futuro ×10 no altera features pasadas |
| `test_no_overlap_between_consecutive_folds` | ✅ | train < val en cada fold; validation sets de folds consecutivos son disjuntos |
| `test_temporal_cv_on_real_data_preserves_order` | ✅ | Integración: pipeline real preserva orden cronológico y métricas en rango |

### 6.3 Tests de split y anti-fuga (`test_sales_forecast_split.py`)

| Clase de test | Cant. | Lo que verifica |
|---------------|-------|-----------------|
| `TestSplitTemporalSinFuga` | 6 | Split 8/2 años, sin solape, corte cronológico estricto, lags sin fuga, escalado solo con train |
| `TestDatasetCoincideConContexto` | 5 | Columnas esperadas, solo consolidated, 120 meses sin huecos, revenue > 0, target correcto |
| `TestNombresDeFeatures` | 2 | Features coinciden con pandas shift(1)+rolling(), sin nombres engañosos |
| `TestCausalidadAntiFugaRodantes` | 5 | Ninguna rolling feature (ma_3, min_12, max_12, std_12) incluye revenue_usd[t]; primera fila es NaN |
| `TestEntrenamientoYPrediccion` | 1 | Predicción fuera de muestra produce 24 meses (2024-2025) |

### 6.4 Tests adicionales del pipeline (`test_pipeline.py`)

| Clase de test | Cant. | Lo que verifica |
|---------------|-------|-----------------|
| `TestParseCost` | 7 | Parseo de costos desde eventos (tags, keys numéricas, inválidos) |
| `TestSafeInt` | 6 | Conversión segura a entero (None, floats, strings no numéricos) |
| `TestValidateEvent` | 6 | Validación de campos requeridos (clinic_id, country, tags) |
| `TestDeduplicateEvents` | 5 | Deduplicación por event_id (sin duplicados, todos duplicados, lista vacía) |
| `TestAggregateKpis` | 7 | Agregación de KPIs por clínica (costos, tipos de evento) |
| `TestVerifyKpis` | 7 | Verificación de advertencias (costos negativos, moneda-país inconsistente) |

### 6.5 Resumen de CI

| Aspecto | Detalle |
|---------|---------|
| **Comando CI** | `uv run python -m pytest tests/pipelines/ -v` |
| **Tests totales** | 64 |
| **Pasaron** | ✅ 64 |
| **Fallaron** | ❌ 0 |
| **Estado** | ✅ **TODOS LOS TESTS PASAN** |

---

## 7. Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `data/eval/learning_curve_rmse.png` | Curva de aprendizaje (RMSE) |
| `data/eval/learning_curve_mae.png` | Curva de aprendizaje (MAE) |
| `data/eval/evaluation_report.md` | Este reporte |
| `scripts/run_model_evaluation.py` | Script de evaluación |
| `tests/pipelines/test_temporal_cv.py` | Tests de validación cruzada temporal |

---

## 8. Decisión de paso a staging

| Criterio | Estado | Observación |
|----------|--------|-------------|
| Split temporal correcto (8/2) | ✅ | Verificado |
| Features sin fuga de futuro | ✅ | `assert_features_causal()` pasa |
| Validación cruzada temporal | ✅ | 5 folds cronológicos, métricas reportadas |
| Curva de aprendizaje generada | ✅ | Evidencia de overfitting |
| MAE y RMSE calculados y justificados | ✅ | RMSE > MAE para contexto HealthCore |
| Suite completa de tests pasa | ✅ | 64/64 tests pasan |
| Diagnóstico con acción correctiva | ⚠️ | Overfitting detectado — ver §5.3 |

**Veredicto: NO APROBADO para staging sin las correcciones de §5.3.**

El modelo NO es inútil — su MAPE de 3.47% sobre el conjunto de prueba
es respetable — pero el análisis de sesgo/varianza revela overfitting. La
arquitectura de features permite que el modelo memorice en lugar de generalizar.
Las correcciones propuestas son específicas (eliminar `visits_count`, aumentar
`reg_alpha` a 2.0, reducir `max_depth` a 3) y atacan la causa raíz directamente.
