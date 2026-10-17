"use client";

import { useCallback, useEffect, useState } from "react";
import { request } from "@/lib/httpClient";

/* ═════════════════════════════════════════════════════════════════════
   REPORTE MENSUAL DE DESEMPEÑO DE INSUMOS POR CLÍNICA
   Dashboard de negocio — orientado a Dra. Okonkwo (CEO) y Claire (Compliance).

   Este dashboard muestra los 4 KPI definidos en CONTEXT.md, calculados
   por el pipeline monthly_clinic_supply_performance:
     1. Costo de insumos por clínica        (total_supply_cost)
     2. Volumen de consumo de insumos       (supply_consumption_count)
     3. Frecuencia de quiebre crítico       (critical_stockout_count)
     4. Conteo de riesgo de vencimiento     (expiry_risk_count)

   El pipeline se ejecuta mensualmente. Los datos aquí presentados
   corresponden al período seleccionado.
   ═════════════════════════════════════════════════════════════════════ */

/* ── Tipos de datos (alineados con la API /reporting) ─────────────── */

interface ClinicKpi {
  clinic_id: string;
  clinic_name?: string;
  country: string;
  total_supply_cost: number;
  supply_consumption_count: number;
  critical_stockout_count: number;
  expiry_risk_count: number;
  currency: string;
}

interface MonthlyKpisResponse {
  month_start: string;
  clinics: ClinicKpi[];
}

interface PipelineRunOut {
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

/* ── Utilerías de presentación ────────────────────────────────────── */

function formatCurrency(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function formatPeriod(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const months = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
  ];
  return `${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function formatDateShort(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });
}

function clinicFlag(country: string): string {
  switch (country.toUpperCase()) {
    case "US":
      return "🇺🇸";
    case "UK":
      return "🇬🇧";
    default:
      return "🌍";
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-700 border-green-300";
    case "running":
    case "in_progress":
      return "bg-blue-100 text-blue-700 border-blue-300";
    case "failed":
      return "bg-red-100 text-red-700 border-red-300";
    default:
      return "bg-slate-100 text-slate-600 border-slate-300";
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "Completado";
    case "running":
      return "Ejecutando";
    case "failed":
      return "Fallido";
    default:
      return status;
  }
}

/* ── Umbrales para semáforo visual ────────────────────────────────── */

function severityClass(kpiId: string, value: number): string {
  switch (kpiId) {
    case "critical_stockout_count":
      if (value >= 10) return "text-red-600 font-bold";
      if (value >= 3) return "text-amber-600";
      return "text-green-600";
    case "expiry_risk_count":
      if (value >= 20) return "text-red-600 font-bold";
      if (value >= 5) return "text-amber-600";
      return "text-green-600";
    default:
      return "text-slate-700";
  }
}

function severityDot(kpiId: string, value: number): string {
  switch (kpiId) {
    case "critical_stockout_count":
      if (value >= 10) return "🔴";
      if (value >= 3) return "🟠";
      return "🟢";
    case "expiry_risk_count":
      if (value >= 20) return "🔴";
      if (value >= 5) return "🟠";
      return "🟢";
    default:
      return "";
  }
}

/* ── Componente principal ─────────────────────────────────────────── */

export default function ReportingDashboardPage() {
  const [kpis, setKpis] = useState<MonthlyKpisResponse | null>(null);
  const [latestRun, setLatestRun] = useState<PipelineRunOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState<string>("");

  const fetchKpis = useCallback(async (monthStart?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (monthStart) params.set("month_start", monthStart);
      const qs = params.toString();
      const url = `/api/reporting/monthly-clinic-supply-performance${qs ? `?${qs}` : ""}`;
      const data = await request<MonthlyKpisResponse>(url);
      setKpis(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchLatestRun = useCallback(async () => {
    try {
      const data = await request<PipelineRunOut | { message: string; run: null }>(
        "/api/reporting/pipeline-runs/latest",
      );
      if (data && "run_id" in data) {
        setLatestRun(data as PipelineRunOut);
      }
    } catch {
      // No crítico; se ignora silenciosamente
    }
  }, []);

  useEffect(() => {
    fetchKpis();
    fetchLatestRun();
  }, [fetchKpis, fetchLatestRun]);

  /* ── Indicadores agregados ─────────────────────────────────────── */

  const totalClinics = kpis?.clinics.length ?? 0;
  const usClinics = kpis?.clinics.filter((c) => c.country === "US") ?? [];
  const ukClinics = kpis?.clinics.filter((c) => c.country === "UK") ?? [];

  const totalCost = kpis?.clinics.reduce((s, c) => s + c.total_supply_cost, 0) ?? 0;
  const totalConsumption = kpis?.clinics.reduce((s, c) => s + c.supply_consumption_count, 0) ?? 0;
  const totalStockouts = kpis?.clinics.reduce((s, c) => s + c.critical_stockout_count, 0) ?? 0;
  const totalExpiryRisk = kpis?.clinics.reduce((s, c) => s + c.expiry_risk_count, 0) ?? 0;

  const anyRedAlert = kpis?.clinics.some((c) => c.critical_stockout_count >= 10 || c.expiry_risk_count >= 20) ?? false;

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

      {/* ── Encabezado ──────────────────────────────────────────────── */}
      <header className="mb-2">
        <h1 className="text-2xl font-bold text-slate-900">
          Reporte Mensual de Desempeño de Insumos por Clínica
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Panel ejecutivo de indicadores de suministro clínico.
          Consolida los 4 KPI definidos en el modelo de negocio de HealthCore.
        </p>
      </header>

      {/* ── Selector de período y estado del pipeline ──────────────── */}
      <section className="mt-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold text-slate-600">
            Período:
          </label>
          <input
            type="month"
            id="month-input"
            className="rounded border border-slate-300 px-2 py-1 text-xs"
            defaultValue={kpis?.month_start?.slice(0, 7) ?? ""}
          />
          <button
            className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700"
            onClick={() => {
              const val = (document.getElementById("month-input") as HTMLInputElement)?.value;
              fetchKpis(val ? `${val}-01` : undefined);
            }}
          >
            Consultar
          </button>
          <button
            className="rounded bg-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-300"
            onClick={() => fetchKpis()}
          >
            Último período
          </button>

          {/* ── Badge del pipeline ────────────────────────────────── */}
          {latestRun && (
            <span className="ml-auto text-xs text-slate-400">
              Pipeline:
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(latestRun.status)}`}
              >
                {statusLabel(latestRun.status)}
              </span>
              {latestRun.finished_at && (
                <span className="ml-1 text-slate-400">
                  · {formatDateShort(latestRun.finished_at)}
                </span>
              )}
            </span>
          )}
        </div>
      </section>

      {/* ── Estados: carga, error, sin datos ──────────────────────── */}
      {loading && (
        <section className="mt-6 animate-pulse rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Cargando reporte del período…
        </section>
      )}

      {error && (
        <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <strong>Error al cargar el reporte:</strong> {error}
          <p className="mt-1 text-xs text-red-500">
            Verifique que el pipeline se haya ejecutado para el período solicitado
            o contacte al administrador del sistema.
          </p>
        </section>
      )}

      {!loading && !error && !kpis && (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No hay datos disponibles para el período seleccionado.
          Ejecute el pipeline mensual para generar el reporte.
        </section>
      )}

      {!loading && kpis && (
        <>
          {/* ═══════════════════════════════════════════════════════════
             BANNER DEL PERÍODO
             ═══════════════════════════════════════════════════════════ */}
          <section className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded bg-blue-100 px-3 py-1 text-sm font-bold text-blue-800">
                📅 {formatPeriod(kpis.month_start)}
              </span>
              <span className="text-xs text-slate-500">
                {totalClinics} clínica{totalClinics !== 1 ? "s" : ""} reportada{totalClinics !== 1 ? "s" : ""}
                {usClinics.length > 0 && ` · ${usClinics.length} 🇺🇸`}
                {ukClinics.length > 0 && ` · ${ukClinics.length} 🇬🇧`}
              </span>
            </div>
            {anyRedAlert && (
              <div className="mt-2 flex items-center gap-2 rounded bg-red-50 p-2 text-xs text-red-700">
                <span>⚠️</span>
                <span>
                  <strong>Atención:</strong> Una o más clínicas presentan
                  indicadores en nivel crítico. Revise "Quiebre de stock" y
                  "Riesgo de vencimiento" más abajo.
                </span>
              </div>
            )}
          </section>

          {/* ═══════════════════════════════════════════════════════════
             TARJETAS DE LOS 4 KPI — VISIÓN EJECUTIVA
             ═══════════════════════════════════════════════════════════ */}
          <section className="mt-6">
            <h2 className="text-lg font-semibold text-slate-900">
              Indicadores Clave del Período
            </h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* KPI 1: Costo de insumos */}
              <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                  Costo de insumos por clínica
                </h3>
                <p className="mt-1 text-2xl font-bold text-slate-900">
                  {formatCurrency(totalCost, "USD")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Suma del valor monetario de todos los insumos consumidos
                  (medicamentos, EPP, equipos) durante el período.
                </p>
              </article>

              {/* KPI 2: Volumen de consumo */}
              <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                  Volumen de consumo de insumos
                </h3>
                <p className="mt-1 text-2xl font-bold text-slate-900">
                  {totalConsumption.toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Número total de unidades de insumo consumidas por todas las
                  clínicas. Ayuda a identificar patrones de demanda.
                </p>
              </article>

              {/* KPI 3: Quiebre crítico */}
              <article className={`rounded-2xl border ${totalStockouts >= 10 ? "border-red-300" : "border-slate-200"} bg-white p-4 shadow-sm`}>
                <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                  Frecuencia de quiebre crítico de stock
                </h3>
                <p className={`mt-1 text-2xl font-bold ${totalStockouts >= 10 ? "text-red-600" : totalStockouts >= 3 ? "text-amber-600" : "text-slate-900"}`}>
                  {severityDot("critical_stockout_count", totalStockouts)} {totalStockouts.toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Cantidad de veces que un insumo esencial llegó a nivel crítico.
                  Este indicador es prioritario para Compliance.
                </p>
              </article>

              {/* KPI 4: Riesgo de vencimiento */}
              <article className={`rounded-2xl border ${totalExpiryRisk >= 20 ? "border-red-300" : "border-slate-200"} bg-white p-4 shadow-sm`}>
                <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                  Conteo de riesgo de vencimiento
                </h3>
                <p className={`mt-1 text-2xl font-bold ${totalExpiryRisk >= 20 ? "text-red-600" : totalExpiryRisk >= 5 ? "text-amber-600" : "text-slate-900"}`}>
                  {severityDot("expiry_risk_count", totalExpiryRisk)} {totalExpiryRisk.toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Insumos próximos a vencer sin rotación. Impacta directamente
                  en pérdidas financieras y desperdicio.
                </p>
              </article>
            </div>
          </section>

          {/* ═══════════════════════════════════════════════════════════
             TABLA DETALLADA POR CLÍNICA
             ═══════════════════════════════════════════════════════════ */}
          <section className="mt-8 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-slate-100 text-left text-xs text-slate-600 uppercase tracking-wider">
                  <th className="px-4 py-3 font-semibold">Clínica</th>
                  <th className="px-4 py-3 font-semibold">País</th>
                  <th className="px-4 py-3 font-semibold text-right" title="Costo de insumos por clínica">
                    Costo insumos
                  </th>
                  <th className="px-4 py-3 font-semibold text-right" title="Volumen de consumo de insumos">
                    Consumo
                  </th>
                  <th className="px-4 py-3 font-semibold text-right" title="Frecuencia de quiebre crítico de stock">
                    Quiebres ⚠️
                  </th>
                  <th className="px-4 py-3 font-semibold text-right" title="Conteo de riesgo de vencimiento">
                    Vencimiento 📅
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {kpis.clinics.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No hay datos de clínicas para este período.
                    </td>
                  </tr>
                )}
                {kpis.clinics.map((clinic: ClinicKpi) => (
                  <tr
                    key={clinic.clinic_id}
                    className="hover:bg-slate-50"
                  >
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {clinic.clinic_name || clinic.clinic_id}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {clinicFlag(clinic.country)} {clinic.country}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {formatCurrency(clinic.total_supply_cost, clinic.currency)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {clinic.supply_consumption_count.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 text-right ${severityClass("critical_stockout_count", clinic.critical_stockout_count)}`}>
                      {clinic.critical_stockout_count}
                      {clinic.critical_stockout_count >= 10 ? " 🔴" : clinic.critical_stockout_count >= 3 ? " 🟠" : ""}
                    </td>
                    <td className={`px-4 py-3 text-right ${severityClass("expiry_risk_count", clinic.expiry_risk_count)}`}>
                      {clinic.expiry_risk_count}
                      {clinic.expiry_risk_count >= 20 ? " 🔴" : clinic.expiry_risk_count >= 5 ? " 🟠" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
              {kpis.clinics.length > 1 && (
                <tfoot>
                  <tr className="bg-slate-50 font-semibold">
                    <td className="px-4 py-3 text-slate-700">Total</td>
                    <td className="px-4 py-3 text-slate-500">
                      {totalClinics} clínica{totalClinics !== 1 ? "s" : ""}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {formatCurrency(totalCost, "USD")}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {totalConsumption.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 text-right ${severityClass("critical_stockout_count", totalStockouts)}`}>
                      {severityDot("critical_stockout_count", totalStockouts)} {totalStockouts.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 text-right ${severityClass("expiry_risk_count", totalExpiryRisk)}`}>
                      {severityDot("expiry_risk_count", totalExpiryRisk)} {totalExpiryRisk.toLocaleString()}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </section>

          {/* ═══════════════════════════════════════════════════════════
             TARJETAS INDIVIDUALES POR CLÍNICA
             ═══════════════════════════════════════════════════════════ */}
          {kpis.clinics.length > 0 && (
            <section className="mt-8">
              <h2 className="text-lg font-semibold text-slate-900">
                Detalle por Clínica
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Vista complementaria con semáforo visual por KPI.
              </p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {kpis.clinics.map((clinic: ClinicKpi) => (
                  <article
                    key={`card-${clinic.clinic_id}`}
                    className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-slate-900">
                        {clinic.clinic_name || clinic.clinic_id}
                      </h3>
                      <span className="text-lg">
                        {clinicFlag(clinic.country)}
                      </span>
                    </div>

                    <dl className="mt-2 space-y-2 text-xs">
                      <div className="flex items-center justify-between py-1">
                        <dt className="text-slate-500" title="Costo de insumos por clínica">
                          Costo de insumos
                        </dt>
                        <dd className="text-slate-700 font-semibold">
                          {formatCurrency(clinic.total_supply_cost, clinic.currency)}
                        </dd>
                      </div>

                      <div className="flex items-center justify-between py-1">
                        <dt className="text-slate-500" title="Volumen de consumo de insumos">
                          Volumen de consumo
                        </dt>
                        <dd className="text-slate-700 font-semibold">
                          {clinic.supply_consumption_count.toLocaleString()}
                        </dd>
                      </div>

                      <div className="flex items-center justify-between py-1">
                        <dt className="text-slate-500" title="Frecuencia de quiebre crítico de stock">
                          Quiebre crítico de stock
                        </dt>
                        <dd className={`font-semibold ${severityClass("critical_stockout_count", clinic.critical_stockout_count)}`}>
                          {severityDot("critical_stockout_count", clinic.critical_stockout_count)} {clinic.critical_stockout_count.toLocaleString()}
                        </dd>
                      </div>

                      <div className="flex items-center justify-between py-1">
                        <dt className="text-slate-500" title="Conteo de riesgo de vencimiento">
                          Riesgo de vencimiento
                        </dt>
                        <dd className={`font-semibold ${severityClass("expiry_risk_count", clinic.expiry_risk_count)}`}>
                          {severityDot("expiry_risk_count", clinic.expiry_risk_count)} {clinic.expiry_risk_count.toLocaleString()}
                        </dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* ═══════════════════════════════════════════════════════════
             LEYENDA DE INDICADORES
             ═══════════════════════════════════════════════════════════ */}
          <section className="mt-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <details className="text-xs text-slate-500">
              <summary className="font-semibold text-slate-700 cursor-pointer">
                📊 Acerca de este reporte
              </summary>
              <div className="mt-2 space-y-2">
                <p>
                  Este panel presenta los <strong>4 indicadores clave de desempeño (KPI)</strong> del
                  modelo de suministro clínico de HealthCore, calculados mensualmente por el pipeline
                  <code>monthly_clinic_supply_performance</code>.
                </p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>
                    <strong>Costo de insumos por clínica</strong> —
                    Valor monetario total de los insumos consumidos (medicamentos, EPP, consumibles, equipos).
                  </li>
                  <li>
                    <strong>Volumen de consumo de insumos</strong> —
                    Cantidad de unidades de insumo utilizadas por las clínicas en el período.
                  </li>
                  <li>
                    <strong>Frecuencia de quiebre crítico de stock</strong> —
                    Veces que un insumo alcanzó nivel de desabastecimiento crítico.
                    <span className="text-red-500"> 🔴 Alto (≥10)</span> · 🟠 Medio (3–9) · 🟢 Bajo (0–2)
                  </li>
                  <li>
                    <strong>Conteo de riesgo de vencimiento</strong> —
                    Insumos próximos a expirar sin haber sido rotados.
                    <span className="text-red-500"> 🔴 Alto (≥20)</span> · 🟠 Medio (5–19) · 🟢 Bajo (0–4)
                  </li>
                </ul>
                <p className="mt-1">
                  <strong>Nota:</strong> Los datos se actualizan una vez al mes tras la ejecución del pipeline.
                  Para solicitar un recalculo, contacte al equipo de datos.
                </p>
              </div>
            </details>
          </section>
        </>
      )}
    </main>
  );
}
