"use client";

import type { AnalysisResponse } from "./IncidentsAnalyzerClient";

const CATEGORY_ORDER = [
  "APPOINTMENT",
  "BILLING",
  "CLINICAL_CARE",
  "ACCESSIBILITY",
  "ADMINISTRATIVE",
] as const;

const STATUS_ORDER = ["OPEN", "CLOSED", "DISCARDED"] as const;
const COUNTRY_ORDER = ["US", "UK"] as const;
const SCORE_ORDER = ["1", "2", "3", "4", "5"] as const;

const INVALID_LABELS: Array<{ key: string; label: string }> = [
  { key: "invalid_clinic", label: "clinic_id faltante o inválido" },
  { key: "country_clinic_mismatch", label: "Incompatibilidad país/clínica" },
  { key: "invalid_category", label: "category faltante o inválida" },
  { key: "empty_description", label: "description vacía o demasiado corta" },
  { key: "missing_patient_id", label: "Falta patient_id" },
  { key: "closed_no_score", label: "status=CLOSED sin satisfaction_score" },
  { key: "score_out_of_range", label: "satisfaction_score fuera de rango" },
];

interface Props {
  response: AnalysisResponse;
  onDownloadCsv: () => void;
  isDownloading: boolean;
}

export default function AnalysisResultsPanel({
  response,
  onDownloadCsv,
  isDownloading,
}: Props) {
  const hasInvalidRecords = response.summary.invalid > 0;

  return (
    <section className="mt-6 space-y-6">
      <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Métricas generales</h3>
            <p className="mt-1 text-sm text-slate-500">
              Archivo analizado: {response.source_file}
            </p>
          </div>
          <button
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isDownloading}
            onClick={onDownloadCsv}
            type="button"
          >
            {isDownloading ? "Descargando..." : "Descargar resultados CSV"}
          </button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Total</p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{response.summary.total}</p>
          </div>
          <div className="rounded-lg bg-emerald-50 p-3">
            <p className="text-xs uppercase tracking-wide text-emerald-700">Válidos</p>
            <p className="mt-1 text-2xl font-bold text-emerald-900">{response.summary.valid}</p>
          </div>
          <div className="rounded-lg bg-amber-50 p-3">
            <p className="text-xs uppercase tracking-wide text-amber-700">Inválidos</p>
            <p className="mt-1 text-2xl font-bold text-amber-900">{response.summary.invalid}</p>
          </div>
        </div>
      </article>

      <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">Registros inválidos</h3>
        <p
          className={`mt-2 rounded-lg px-3 py-2 text-sm ${
            hasInvalidRecords
              ? "border border-amber-200 bg-amber-50 text-amber-900"
              : "border border-emerald-200 bg-emerald-50 text-emerald-900"
          }`}
        >
          {hasInvalidRecords
            ? `Se detectaron ${response.summary.invalid} registros inválidos o incompletos.`
            : "No se detectaron registros inválidos."}
        </p>
        <ul className="mt-4 space-y-2 text-sm text-slate-700">
          {INVALID_LABELS.map(({ key, label }) => (
            <li
              key={key}
              className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
            >
              <span>{label}</span>
              <span className="font-semibold">
                {response.summary.invalid_breakdown[key] ?? 0}
              </span>
            </li>
          ))}
        </ul>
      </article>

      <div className="grid gap-6 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Desglose por categoría</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {CATEGORY_ORDER.map((category) => (
              <li
                key={category}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <span>{category}</span>
                <span className="font-semibold">
                  {response.summary.category_counts[category] ?? 0} (
                  {response.summary.percentages.categories[category] ?? 0}%)
                </span>
              </li>
            ))}
          </ul>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Desglose por estado</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {STATUS_ORDER.map((status) => (
              <li
                key={status}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <span>{status}</span>
                <span className="font-semibold">
                  {response.summary.status_counts[status] ?? 0} (
                  {response.summary.percentages.statuses[status] ?? 0}%)
                </span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Desglose por país</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {COUNTRY_ORDER.map((country) => (
              <li
                key={country}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <span>{country}</span>
                <span className="font-semibold">
                  {response.summary.country_counts[country] ?? 0} (
                  {response.summary.percentages.countries[country] ?? 0}%)
                </span>
              </li>
            ))}
          </ul>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Distribución de scores</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {SCORE_ORDER.map((score) => (
              <li
                key={score}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <span>Score {score}</span>
                <span className="font-semibold">
                  {response.summary.score_counts[score] ?? 0}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center justify-between rounded-lg bg-blue-50 px-3 py-2 text-sm">
            <span className="font-medium text-blue-700">Casos puntuados</span>
            <span className="font-bold text-blue-900">{response.summary.scored_cases}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-blue-50 px-3 py-2 text-sm">
            <span className="font-medium text-blue-700">Casos cerrados</span>
            <span className="font-bold text-blue-900">{response.summary.closed_cases}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-indigo-50 px-3 py-2 text-sm">
            <span className="font-medium text-indigo-700">Puntuación media</span>
            <span className="font-bold text-indigo-900">
              {response.summary.average_score.toFixed(2)}
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}