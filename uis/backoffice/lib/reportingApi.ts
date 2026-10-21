/** Cliente HTTP para la API de Reporting de HealthCore.
 *
 * Centraliza todas las llamadas a los endpoints /reporting del backend.
 * Las peticiones se realizan a través del proxy de Next.js (/api/reporting/*)
 * configurado en next.config.ts para evitar problemas de CORS.
 *
 * La capa HTTP (request<T>, jsonRequest, extractErrorMessage) está delegada
 * en ./httpClient.ts, el cliente HTTP único del backoffice.
 *
 * @module reportingApi
 */

import { request } from "./httpClient";

// ── Tipos ─────────────────────────────────────────────────────────────

export interface ClinicKpi {
  clinic_id: string;
  clinic_name?: string;
  country: string;
  total_supply_cost: number;
  supply_consumption_count: number;
  critical_stockout_count: number;
  expiry_risk_count: number;
  currency: string;
}

export interface MonthlyKpisResponse {
  month_start: string;
  clinics: ClinicKpi[];
}

export interface PipelineRunOut {
  run_id: string;
  flow_name: string;
  status: string;
  current_phase?: string | null;
  checkpoint?: string | null;
  trigger_source: string;
  month_start?: string | null;
  month_end?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  events_read: number;
  events_valid: number;
  events_rejected: number;
  events_deduplicated: number;
  rows_inserted: number;
  rows_updated: number;
  warning_count: number;
  error_message?: string | null;
}

export interface PipelineRunTriggerOut {
  run_id: string;
  status: string;
  message: string;
  month_start?: string | null;
  month_end?: string | null;
}

// ── Funciones de acceso ──────────────────────────────────────────────

/**
 * Obtiene los KPI mensuales de desempeño de insumos por clínica.
 *
 * @param monthStart  Opcional: primer día del mes (YYYY-MM-DD).
 *                    Por defecto: último periodo disponible.
 * @returns           Promesa con la respuesta tipada.
 */
export async function fetchMonthlyKpis(
  monthStart?: string,
): Promise<MonthlyKpisResponse> {
  const params = new URLSearchParams();
  if (monthStart) {
    params.set("month_start", monthStart);
  }
  const qs = params.toString();
  const url = `/api/reporting/monthly-clinic-supply-performance${qs ? `?${qs}` : ""}`;
  return request<MonthlyKpisResponse>(url);
}

/**
 * Obtiene la última ejecución del pipeline.
 *
 * @returns Promesa con la respuesta tipada o un mensaje si no hay datos.
 */
export async function fetchLatestRun(): Promise<PipelineRunOut | { message: string; run: null }> {
  return request<PipelineRunOut | { message: string; run: null }>(
    "/api/reporting/pipeline-runs/latest",
  );
}