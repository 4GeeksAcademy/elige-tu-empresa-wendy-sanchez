# Migraciones — HealthCore

Directorio de migraciones SQL del monorepo. Cada migración es **idempotente**
(`IF NOT EXISTS` / `ON CONFLICT ... DO NOTHING`) y puede aplicarse tantas veces
como sea necesario.

## Numeración

| Versión | Archivo | Alcance |
| ------- | ------- | ------- |
| `baseline` (0001, implícita) | — (gestionada por `init_supabase_schema()` en `services/api/database.py` y `init_reporting_schema()` en `data/pipelines/database.py`) | Esquema base existente: `telemetry_events`, tablas de inventario, esquema `reporting` con `pipeline_runs`. |
| `job_runs` (0002) | `0002_job_runs.sql` | Tabla de control de ejecuciones nocturnas (Hito 7). |

## Cómo se aplican

El servicio `services/nightly/job_store.py` mantiene un pequeño registro de
migraciones aplicadas en la tabla `schema_migrations` (una fila por versión) y
aplica **solo** las que faltan, en orden. Esto hace que el script nocturno sea
auto-migrante e idempotente: cada arranque garantiza que `job_runs` existe.

Aplicación manual equivalente en producción (PostgreSQL / Supabase):

```bash
psql "$DATABASE_URL" -f data/migrations/0002_job_runs.sql
```

El mismo DDL existe como espejo SQLite dentro de `job_store.py` (usado por
tests y por ejecuciones locales sin PostgreSQL); ambas copias deben mantenerse
en sincronía.

## Nota arquitectónica: `job_runs` ≠ `pipeline_runs`

| Tabla | Capa | Qué registra |
| ----- | ---- | ------------ |
| `job_runs` | Orquestación nocturna (este Hito) | Export CSV, trigger del subprocess del pipeline, lock e idempotencia del script. |
| `reporting.pipeline_runs` | ETL interno (Hito 6) | Fases extract/transform/load, watermark, filas procesadas. |

El script nocturno escribe **únicamente** en `job_runs`. El subprocess del
pipeline escribe en `pipeline_runs` durante su propia ejecución. No se fusionan:
son capas distintas.