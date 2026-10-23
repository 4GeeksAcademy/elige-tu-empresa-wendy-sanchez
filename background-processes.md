# Procesos en segundo plano — Job nocturno de telemetría

> Documento de decisión: por qué un script independiente + crontab + máquina de
> estados en BD, en vez de un scheduler dentro de la API.

---

## 1. Resumen del job

Cada noche (por defecto a las **02:00 UTC**) se ejecuta un proceso **completamente
independiente de la API** que:

1. Exporta los eventos de telemetría del **día anterior** desde `telemetry_events`
   a `data/raw/telemetry_YYYY-MM-DD.csv` **si aún no se ha hecho**.
2. Lanza el pipeline de datos (Hito 6) como **subprocess**.
3. Deja constancia en base de datos (`job_runs`) de qué pasó y cuándo, con la
   máquina de estados `pending → processing → completed | failed`.

El script NO corre en el hilo de FastAPI, no bloquea ningún endpoint, y su
exit code se puede vigilar desde cron (0 = ok / 1 = falló).

---

## 2. Decisión de trigger: **crontab (cron del sistema)**

### Elección

Se usó **crontab del sistema** para disparar el script, no un scheduler dentro
de la aplicación (APScheduler/Celery beat/dramatiq NO forman parte del stack
actual de HealthCore).

Cron expression:

```cron
# todos los días a las 02:00 UTC
0 2 * * *  cd /workspaces/elige-tu-empresa-wendy-sanchez && .venv-nightly/bin/python scripts/nightly_export.py >> /var/log/healthcore/nightly_export.log 2>&1
```

En producción (con `DATABASE_URL` en el entorno o en `services/api/.env`), la
misma línea se simplifica a:

```cron
0 2 * * *  cd /opt/healthcore && /opt/healthcore/.venv/bin/python scripts/nightly_export.py >> /var/log/healthcore/nightly_export.log 2>&1
```

### Justificación (por qué cron y no un scheduler en proceso)

| Criterio | Cómo lo cumple cron |
|---|---|
| **Independencia de la API** | cron es un demonio del SO; no comparte proceso, hilo ni memoria con FastAPI. Cero riesgo de bloquear un endpoint. |
| **Cero deuda de infraestructura** | No añade Celery/Redis/beat al stack. Solo existe ya en cualquier servidor. |
| **Manejo de concurrencia** | cron puede lanzar una segunda instancia si el primero tarda más de 24 h. El **lock de BD (`processing`)** aborta silenciosamente la segunda: cron no tiene que ser perfecto. |
| **Reintentos** | El manejo de reintentos vive en la máquina de estados de BD, no en el scheduler. |
| **Visibilidad** | Logs estándar, exit codes, y `tail`/`journalctl` para depurar. |
| **Idempotencia** | Muchas ejecuciones extra para el mismo día son inofensivas: la 2.ª ya encuentra `completed` y hace noop. |

### 2.1. Instalación del crontab

1. Ver la tabla actual (no romper otras entradas):

   ```bash
   crontab -l > /tmp/healthcore_crontab.txt
   ```

2. Añadir la línea del job nocturno al final (el directorio `/var/log/healthcore`
   debe existir y ser escribible por el usuario que corre el cron). En desarrollo
   se apunta a `.venv-nightly`; en producción a `.venv` del proyecto:

   ```cron
   # HealthCore — job nocturno de telemetría (proceso de segundo plano)
   0 2 * * *  cd /opt/healthcore && /opt/healthcore/.venv/bin/python scripts/nightly_export.py >> /var/log/healthcore/nightly_export.log 2>&1
   ```

3. Cargar la nueva tabla:

   ```bash
   crontab /tmp/healthcore_crontab.txt
   crontab -l | grep nightly_export   # verificar que quedó instalada
   ```

   > Requisitos del usuario cron: acceso de lectura a `scripts/`, `services/`,
   > `data/` y la variable `DATABASE_URL` (o `services/api/.env` con ella). El
   > script crea su propia BD de estado (job_runs) vía `ensure_schema`, así que
   > no hace falta migrar a mano antes de la primera ejecución.

   Prueba manual equivalente a lo que hará cron (idempotente, sin efectos
   residuales si ya se corrió el día):

   ```bash
   TARGET_DATE=2026-10-20 python scripts/nightly_export.py --skip-pipeline --dry-run
   ```

### 2.2. Contenedor scheduler dedicado (recomendado en producción)

En despliegues contenedorizados (docker-compose de `services/`), la opción
**recomendada** es un **contenedor scheduler dedicado**, NO un worker dentro del
proceso FastAPI. Un pequeño contenedor que ejecuta el script nocturno como
proceso principal (equivalente a cron, pero empaquetado):

- **Patrón**: imagen del proyecto (ej. `services/Dockerfile`), command que corre
  el script el día en que toca, o un bucle `while true; sleep` que lanza el
  script a las 02:00 UTC y luego espera. Alternativa más limpia: instalar `cron`
  dentro del contenedor y delegar en la misma tabla crontab anterior.
- **Por qué**: hereda red/secretos/BD del compose (misma `DATABASE_URL`), escala
  y se observa igual que el resto (healthchecks, `docker logs`), y **no comparte
  proceso ni hilo con la API**.
- **Cero solapamientos**: el lock atómico de BD sigue aplicando — si el contenedor
  se solapa en el arranque con una corrida previa aún en `processing`, aborta
  silenciosamente.

### 2.3. Qué está PROHIBIDO (requisito explícito del proceso de segundo plano)

- **NUNCA** ejecutar el job nocturno dentro del proceso FastAPI:
  - No **APScheduler**, no `@repeat_every`, no hooks de **lifespan** en el
    servidor de la API.
- Un **worker separado** (por ej. Celery/dramatiq) solo es aceptable si es un
  proceso o contenedor propio que **no comparte el hilo principal de la API**.
  La implementación actual (cron / contenedor scheduler) cumple directamente.

> Nota: no usamos timeouts ciegos de cron (`timeout(1)`) para "evitar
> solapamientos" porque el script **ya se autoprotege** con su propio lock
> atómico; un timeout externo solo añadiría una forma más de dejar el job a
> medias. El único timeout que aplica es el del propio `subprocess.run` del
> pipeline si se configurara.

---

## 3. Arquitectura

```
  cron (02:00 UTC)
        │
        ▼
┌───────────────────────────────┐      ┌──────────────────────────────┐
│  scripts/nightly_export.py    │      │  services/nightly/           │
│  (CLI: flags, JSON, exit)     │ ───► │  nightly_service.py          │
└───────────────────────────────┘      │  (orquestación)              │
                                       └──────────────┬───────────────┘
                                                      │
                                       ┌──────────────▼───────────────┐
                                       │  services/job_runner.py      │
                                       │  CONTROL DE ESTADO + LOCK    │
                                       │  (crear/actualizar/consultar │
                                       │   job_runs, has_* helpers)   │
                                       └──────────────┬───────────────┘
                                                      │
                        ┌─────────────────────────────┴─────────────────────────────┐
                        │                                                           │
                        ▼                                                           ▼
            ┌───────────────────────┐                                ┌──────────────────────────┐
            │  BD: job_runs         │                                │  data/raw/               │
            │  pending→processing→  │                                │  telemetry_YYYY-MM-DD.csv │
            │  completed\|failed     │                                │  (backup, NO input       │
            └───────────────────────┘                                │   del pipeline)          │
                        │                                            └──────────────────────────┘
                        │  subprocess independiente
                        ▼
            ┌───────────────────────┐
            │  python -m data.      │   (Hito 6: pipeline mensual de
            │  pipelines.runner     │    desempeño de insumos)
            └───────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  reporting.pipeline_  │   (capa ETL del Hito 6 — tiene su
            │  runs                 │    propio lock por periodo)
            └───────────────────────┘
```

### 3.1. Capas y por qué `job_runs` ≠ `pipeline_runs`

- **`job_runs`** → capa de **ORQUESTACIÓN NOCTURNA** (proceso de segundo plano). Un registro por
  `(job_name, target_date)`. Guarda estado, timestamps, error y metadatos de la
  exportación (filas, ruta del CSV).
- **`reporting.pipeline_runs`** → capa del **pipeline ETL** (Hito 6). Un registro
  por corrida del pipeline motorizado por `run_store.py`, con su propio lock por
  periodo (`has_active_run_for_period`).

NO son duplicados ni la misma cosa: uno orquesta "exportar el día y disparar el
pipeline", el otro registra "una ejecución ETL concreta". El job nocturno delega
en el pipeline; el pipeline persiste *su* estado en su propia tabla.

### 3.2. CSV = backup, no input del pipeline

El CSV es **constancia / backup** de lo exportado. **El script solo lo escribe
si el archivo `telemetry_YYYY-MM-DD.csv` NO existe** (snapshot inmutable): si ya
hay un snapshot del día, se omite la re-exportación (backup no se sobreescribe).
El pipeline (Hito 6) lee de la BD, **nunca** del archivo. No conectamos el
pipeline para consumir `data/raw/telemetry_*.csv`. (El nombre del archivo sigue
la convención del respaldo raw ya existente.)

---

## 4. Convenciones de fecha y hora

- **"Ayer"** = `datetime.now(timezone.utc).date() - timedelta(days=1)`.
- **Override para pruebas**: variable de entorno `TARGET_DATE=YYYY-MM-DD` (o
  flag `--target-date`) para sobrescribir la fecha objetivo sin tocar código.
  No es parte de la corrida normal: se usa en pruebas, reset o reproceso de un
  día concreto.
- El intervalo exportado es `[medianoche_utc(día), medianoche_utc(día+1))` —
  medio abierto, sin solapamientos entre días.
- Todos los timestamps se registran en UTC (`TIMESTAMPTZ` en producción).

---

## 5. Máquina de estados y lock

| Estado | Significado |
|---|---|
| `pending` | Filas **reservadas** antes de trabajar (para idempotencia por día). |
| `processing` | Trabajo **en curso**. Este estado ES el distributed lock. |
| `completed` | Todo terminó bien. |
| `failed` | Error capturado; se guarda `error_message`. |

```
pending ──► processing ──► completed
                │
                └──────► failed ──►(reintento)──► pending
```

- **El lock ES el estado `processing`** mismo — no hay tabla, columna ni flag de
  bloqueo adicional (requisito explícito del proceso de segundo plano). El helper
  `has_processing_lock(job_name, target_date)` permite consultar si el lock está
  tomado (abortar silenciosamente); la TOMA es `mark_processing(...)` (UPDATE
  atómico).
- Toma del lock (atómica): `UPDATE job_runs SET status='processing', started_at=now()
  WHERE job_name=... AND target_date=... AND status='pending'`. Si afecta 1 fila,
  esta instancia ganó; si afecta 0, otra instancia ya corre → **abortar
  silenciosamente** (exit 0, outcome `aborted`).
- Fallo: `mark_failed(...)` transita `processing → failed` y guarda el mensaje de
  la excepción. **Nunca se queda en `processing`** (sin registros zombi).
- Reintento del mismo día tras `failed`: transición explícita
  `reset_failed_to_pending(...)` (atómica, solo desde `failed`, nunca desde
  `processing` — no se puede robar un lock vivo), y luego vuelve a pasar por
  `mark_processing`.
- Idempotencia: si ya existe `completed` para el día (`has_completed_for_date`
  con `(job_name='nightly_export', target_date)`), el script devuelve
  `outcome="noop_export"` sin re-exportar ni re-disparar el pipeline. Solo
  `job_name` sin `target_date` no basta.
- Idempotencia de archivo: aunque la fila no exista (p. ej. día reprocesado
  tras `--force`), si el snapshot `telemetry_YYYY-MM-DD.csv` ya existe, la
  exportación no lo sobreescribe (backup inmutable).

### Outcomes devueltos por `run_nightly(...)`

| `outcome` | `status` de la fila | Significado |
|---|---|---|
| `completed` | `completed` | Export Y pipeline OK. |
| `noop_export` | `completed` | Ya estaba hecho (idempotente). |
| `aborted` | `processing` (de otra instancia) | Otra corrida en curso; aborto silencioso. |
| `failed` | `failed` | Error; queda constancia. |

> Nota: `pending` no es un outcome devuelto por `run_nightly(...)` — es un
> estado RESIDUAL posible en BD si el proceso muere antes de tomar el lock
> (p. ej. `kill -9` entre `create_job_run` y `mark_processing`). No se deja
> registrado como tal: la siguiente ejecución lo retoma vía `mark_processing`
> (pending → processing).

---

## 6. Interfaz CLI de `scripts/nightly_export.py`

```
python scripts/nightly_export.py [flags]

  --skip-pipeline   Solo exporta el CSV, no lanza el pipeline (debug/reset).
  --force           Re-ejecuta aunque ya exista fila completed para el día.
  --target-date D   Día a procesar (YYYY-MM-DD); por defecto 'ayer' UTC.
  --list            Lista las últimas corridas en JSON.
  --dry-run         Muestra la config planeada (sin tocar nada) y sale.
```

Salida estándar: JSON (borrador en UTF-8, indentado). Exit code: `0` si
`completed`/`noop_export`/`aborted`, `1` si `failed`.

Ejemplos manuales:

```bash
# Corrida normal (ayer UTC)
python scripts/nightly_export.py

# Reprocesar un día concreto sin pipeline
TARGET_DATE=2026-10-20 python scripts/nightly_export.py --skip-pipeline

# Ver el historial
python scripts/nightly_export.py --list
```

---

## 7. Uso en el código

```python
from services.nightly import run_nightly

result = run_nightly()          # usa DATABASE_URL, ayer UTC
print(result["outcome"])        # completed | noop_export | aborted | failed
```

Implementación:
- `services/job_runner.py` — **CONTROL DE ESTADO** en `services/` (migración
  idempotente; crear/actualizar/consultar `job_runs`; máquina de estados y lock;
  helpers `has_processing_lock` / `has_completed_for_date`; `mark_failed` ante
  cualquier excepción — nunca queda `processing`; y `log_result` para el log
  normalizado con job + estado).
- `services/nightly/nightly_service.py` — orquestación (export + pipeline +
  registro, manejo de outcomes, logs INFO/ERROR vía `log_result`).
- `scripts/nightly_export.py` — CLI.
- `data/migrations/0002_job_runs.sql` — DDL de producción (Postgres/Supabase).
- `tests/nightly/` — suite de tests (30 pruebas, `pytest` vía `.venv-nightly`).

---

## 8. Pipeline invocado (Hito 6) — ajuste del subprocess

Referencia original del proceso de segundo plano: `python -m data.pipelines.telemetry_kpi_daily.run
--no-prefect`. **Ese módulo no existe** en el repo; el pipeline real del Hito 6
vive en `data/pipelines/runner.py` (pipeline mensual de desempeño de insumos por
clínica) cuyo entrypoint es:

```bash
python -m data.pipelines.runner            # mes anterior, trigger=manual
python -m data.pipelines.runner --trigger scheduled -m 2026-09-01
```

Por eso `_DEFAULT_PIPELINE_CMD = "python -m data.pipelines.runner"` en
`nightly_service.py`. El subprocess se lanza con `capture_output=True`, falla con
`RuntimeError` si el exit code ≠ 0 y **no espera el fin del negocio del pipeline**
(el pipeline persiste su propia corrida en `reporting.pipeline_runs`).

---

## 9. Migración de esquema

La tabla `job_runs` se crea de dos formas (idempotentes):

1. **Producción (Postgres/Supabase)** — `data/migrations/0002_job_runs.sql`
   (`CREATE TABLE IF NOT EXISTS` + índice `(job_name, target_date)` + UNIQUE
   `(job_name, target_date)` para la idempotencia por día).
2. **Auto-migración** — `job_runner.ensure_schema(engine)` la crea al arrancar si
   no existe (versionada en `schema_migrations`).

Comando manual en producción:

```bash
psql "$DATABASE_URL" -f data/migrations/0002_job_runs.sql
```

---

## 10. Supervisión

### 10.1. Log de ejecución (observabilidad)

El script escribe sus líneas por un **logger estable** (`healthcore.nightly`) que
cualquier proceso puede capturar (cron redirige a archivo; el contenedor
scheduler lo ve en `docker logs`). Reglas:

- **INFO** para eventos normales: inicio (`event=started`), fin
  (`event=finished`), omisión por duplicado (`event=skip_duplicate`), abandono
  por lock tomado (`event=aborted` / `event=aborted_lock`), y detalle interno
  (`event=export_done`, `event=launch_pipeline`, ...).
- **ERROR** para excepciones: `event=failed` con `status=failed` + stack trace
  (`exc_info`).
- **Cada línea** incluye timestamp, **nombre del job** (`job=nightly_export`) y
  **estado resultante** (`status=...`) — formato unificado vía el helper
  `log_result()` de `services/job_runner.py`:

  ```
  2026-10-22 20:17:08,342 [INFO] healthcore.nightly: event=started job=nightly_export status=processing outcome=processing target_date=2026-10-20 ts=2026-10-22T20:17:08.342602+00:00
  2026-10-22 20:17:08,346 [INFO] healthcore.nightly: event=finished job=nightly_export status=completed outcome=completed target_date=2026-10-20 ts=...
  2026-10-22 20:17:08,347 [INFO] healthcore.nightly: event=skip_duplicate job=nightly_export status=completed outcome=noop_export target_date=2026-10-20 ts=...
  2026-10-22 20:17:34,292 [ERROR] healthcore.nightly: event=failed job=nightly_export status=failed outcome=failed target_date=2026-10-20 ts=... + traceback
  ```

  El CLI (`scripts/nightly_export.py`) añade una línea final `event=cli_finished`
  con el outcome del proceso (ERROR si `failed`).

### 10.2. Archivo de log y consulta de BD

- **Log**: `/var/log/healthcore/nightly_export.log` (el cron redirige
  `stdout`/`stderr`; el `logging.basicConfig` imprime a stdout).
- **BD**: consultar el estado:

```sql
SELECT job_name, target_date, status, started_at, finished_at, error_message
  FROM job_runs ORDER BY created_at DESC LIMIT 10;
```

- **Alertas** sugeridas: cualquier fila con `status='failed'` o lasting > 24 h en
  `processing` (este último no debería ocurrir gracias a la máquina de estados).

---

## 11. Hallazgos y soluciones (auditoría del proceso de segundo plano)

Registro de los problemas detectados durante el desarrollo y la auditoría
(30 pruebas automáticas + demostración en vivo con **dos instancias CLI reales**
ejecutándose a la vez), y la solución aplicada en cada caso. La suite completa
sigue en verde (**30/30**, `.venv-nightly/bin/python -m pytest tests/nightly -q`).

### 11.1. Reintento tras fallo: la fila `failed` no podía volver a tomar el lock

- **Hallazgo:** `mark_processing` solo permite la transición `pending→processing`
  (por diseño del lock). Tras un fallo (`processing→failed`), el reintento del
  mismo día no encontraba una fila en `pending` y no podía volver a tomar el
  lock: el día quedaba atascado en `failed`.
- **Solución:** transición atómica `reset_failed_to_pending` que mueve la fila
  `failed → pending`, **solo** desde `failed` (nunca desde `processing`, para no
  robar un lock vivo). El reintento vuelve a pasar por `mark_processing` con
  normalidad.
- **Evidencia:** el demo fuerza un fallo (C5) y deja la fila en `failed` con
  `error_message`; la única fila en `processing` tras el fallo es la que el
  propio demo retiene deliberadamente (C3b), confirmando que **no hay estados
  zombi**.

### 11.2. Módulo de control de estado en el lugar exigido por la especificación

- **Hallazgo:** el control de estado se implementó inicialmente en
  `services/nightly/job_store.py`; la especificación del proceso de segundo plano exige que el
  módulo viva en `services/job_runner.py`.
- **Solución:** se movió el módulo a `services/job_runner.py` y se actualizaron
  los imports de `nightly_service.py`, `scripts/nightly_export.py`, los tests y
  la documentación; el módulo antiguo se eliminó.

### 11.3. Formato de log estable y punto único de emisión

- **Hallazgo:** la primera versión emitía los logs con un logger de módulo
  (heredaba el nivel WARNING por defecto, haciendo fallar los tests `caplog`) y
  el bloque `except` usaba un `logger.exception` crudo que duplicaba formato y
  violaba la especificación de observabilidad (§6).
- **Solución:** se creó el logger estable `healthcore.nightly` (`_JOB_LOGGER`) y
  todo pasa por el helper `log_result()` con formato normalizado
  (`event=... job=... status=... outcome=... target_date=... ts=...`). El manejo
  de errores usa `log_result(..., exc_info=True)` en lugar de
  `logger.exception`, garantizando una sola fuente de verdad (ver §10.1).

### 11.4. Pipeline real invocado (Hito 6)

- **Hallazgo:** la referencia original
  `python -m data.pipelines.telemetry_kpi_daily.run` **no existe** en el repo; el
  pipeline real del Hito 6 es `python -m data.pipelines.runner`.
- **Solución:** `_DEFAULT_PIPELINE_CMD = "python -m data.pipelines.runner"` (ver
  §8).

### 11.5. Concurrencia real verificada en vivo

- **Hallazgo a validar:** el lock atómico de BD (`processing`) debe garantizar
  que dos instancias simultáneas del CLI no dupliquen el trabajo.
- **Solución/verificación:** `scripts/_audit_hito7_demo.py` lanza **dos procesos
  CLI reales** a la vez contra una BD SQLite compartida. Resultado observado: una
  instancia obtiene `outcome=completed` y la otra `aborted` (si ve la fila en
  `processing`) o `noop_export` (si ya la ve `completed`) — en ambos casos
  **exactamente una** instancia hace el trabajo.
- El demo es **reproducible** (limpia su BD y el CSV residual de `data/raw/`,
  `exit=0`) y cubre los **10 criterios de aceptación**: independencia de
  FastAPI, máquina de estados con `target_date`, lock = `processing`, idempotencia
  por `(job_name, target_date)`, fallo → `failed` sin zombis, export CSV con
  nombre y contenido, `job_runs` ≠ `pipeline_runs`, logs con timestamp+job+estado,

### 11.6. Humo en vivo contra Supabase (ramas Postgres y SQLite)

- **Hallazgo:** toda la suite y la demo de auditoría verifican la **rama SQLite**
  (dev/tests). La rama **Postgres** (`BIGSERIAL`, `now()`, `UNIQUE`, `CHECK
  status`) nunca se había ejecutado contra un Postgres real.
- **Solución/verificación (2026-10-22):** corrida real contra Supabase
  (`--skip-pipeline --target-date 2026-10-10`): OUTCOME `completed`, 12 filas
  exportadas a `data/raw/telemetry_2026-10-10.csv`, fila en `job_runs` con
  `status=completed` y `exported_rows=12`. Segunda corrida → `noop_export`
  (idempotencia sobre Postgres real). La rama Postgres funciona.
- **Hallazgo derivado (menor):** `schema_migrations` quedó con **count 0** en
  Postgres: `_ensure_schema_postgres` crea las tablas con DDL hardcodeado pero,
  a diferencia de `_ensure_schema_sqlite`, **no inserta la versión** en
  `schema_migrations`. Como `CREATE TABLE IF NOT EXISTS` es idempotente, el
  comportamiento es correcto, pero la tabla de versiones queda vacía y no hay
  trazabilidad de qué se aplicó. Pendiente de decidir si se documenta
  explícitamente o se alinea el registro de versiones entre ambas ramas.
  disparo externo (cron/contenedor) y override de `TARGET_DATE`.