-- ============================================================================
-- Migración 0002 — job_runs (Hito 7 · Job nocturno de exportación de telemetría)
--
-- Capa: ORQUESTACIÓN NOCTURNA (este proyecto → scripts/nightly_export.py +
--       services/nightly).
-- Registra: export CSV diario, trigger del subprocess del pipeline, lock e
--           idempotencia del script nocturno.
--
-- CAPA DISTINTA de `reporting.pipeline_runs` (ETL interno del Hito 6): NO es un
-- duplicado. `pipeline_runs` registra fases extract/transform/load, watermark y
-- filas procesadas del pipeline mensual, y lo escribe EL SUBPROCESS del pipeline
-- durante su propia ejecución. El script nocturno solo escribe en `job_runs`.
--
-- Máquina de estados canónica:
--
--     pending -> processing -> completed
--                      \-> failed
--
-- El estado `processing` de esta fila ES el distributed lock del script:
-- no existe tabla, columna ni flag de bloqueo aparte. Una instancia que
-- encuentre una fila `processing` FRESCA para (job_name, target_date) aborta
-- silenciosamente. Al terminar —bien o mal— la fila pasa a `completed`/`failed`,
-- lo que libera el lock.
--
-- Idempotencia por día: UNIQUE(job_name, target_date) + índice para consultas.
-- ============================================================================

CREATE TABLE IF NOT EXISTS job_runs (
    id            BIGSERIAL    PRIMARY KEY,
    job_name      VARCHAR(64)  NOT NULL,
    target_date   DATE         NOT NULL,
    status        VARCHAR(16)  NOT NULL DEFAULT 'pending',
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    error_message TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    -- Campos de resultado (v1): dejan constancia de "qué pasó" y cuándo.
    exported_rows INTEGER,
    csv_path      TEXT,
    CONSTRAINT uq_job_runs_job_target UNIQUE (job_name, target_date),
    CONSTRAINT chk_job_runs_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    )
);

-- Índice para consultas de idempotencia eficientes por (job_name, target_date).
CREATE INDEX IF NOT EXISTS idx_job_runs_job_target
    ON job_runs (job_name, target_date);