"use client";

import { FormEvent, useMemo, useState } from "react";

type AnalysisSummary = {
  total: number;
  valid: number;
  invalid: number;
  invalid_breakdown: Record<string, number>;
  category_counts: Record<string, number>;
  status_counts: Record<string, number>;
  country_counts: Record<string, number>;
  score_counts: Record<string, number>;
  scored_cases: number;
  closed_cases: number;
  average_score: number;
  percentages: {
    categories: Record<string, number>;
    statuses: Record<string, number>;
    countries: Record<string, number>;
  };
};

type AnalysisResponse = {
  source_file: string;
  summary: AnalysisSummary;
};

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

const API_BASE = "";

export default function IncidentsAnalyzerClient() {
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AnalysisResponse | null>(null);

  const hasInvalidRecords = useMemo(() => {
    if (!response) {
      return false;
    }
    return response.summary.invalid > 0;
  }, [response]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!file) {
      setError("Selecciona un fichero CSV antes de analizar.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/incidents/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "No se pudo analizar el fichero");
      }

      const payload = (await res.json()) as AnalysisResponse;
      setResponse(payload);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "Error inesperado";
      setResponse(null);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const onDownloadCsv = async () => {
    setError(null);
    setIsDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/api/incidents/results/export`);
      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "No se pudo descargar el CSV");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "results.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      const message = downloadError instanceof Error ? downloadError.message : "Error inesperado";
      setError(message);
    } finally {
      setIsDownloading(false);
    }
  };

  const onLoadSample = async () => {
    setError(null);
    setIsLoadingSample(true);
    try {
      const res = await fetch(`${API_BASE}/api/incidents/analyze/sample`, {
        method: "POST",
      });

      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "No se pudo cargar la muestra");
      }

      const payload = (await res.json()) as AnalysisResponse;
      setResponse(payload);
    } catch (sampleError) {
      const message = sampleError instanceof Error ? sampleError.message : "Error inesperado";
      setResponse(null);
      setError(message);
    } finally {
      setIsLoadingSample(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-900">Incident Report Analyzer</h2>
        <p className="mt-2 text-sm text-slate-600">
          Carga un CSV con la estructura de HealthCore para validar registros y generar el resumen
          de incidencias.
        </p>

        <form className="mt-5 space-y-4" onSubmit={onSubmit}>
          <label
            className="block rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4"
            htmlFor="incidentsCsv"
          >
            <span className="block text-sm font-medium text-slate-700">CSV de incidentes</span>
            <input
              id="incidentsCsv"
              name="incidentsCsv"
              type="file"
              accept=".csv,text/csv"
              className="mt-2 block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-white"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <span className="mt-2 block text-xs text-slate-500">
              Campos esperados: incident_id, date, clinic_id, country, category, description,
              status, patient_id, satisfaction_score.
            </span>
          </label>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting ? "Analizando..." : "Analizar CSV"}
            </button>
            <button
              className="rounded-lg border border-cyan-300 bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-900 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoadingSample}
              onClick={onLoadSample}
              type="button"
            >
              {isLoadingSample ? "Cargando muestra..." : "Usar CSV de muestra (100 filas)"}
            </button>
            <button
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!response || isDownloading}
              onClick={onDownloadCsv}
              type="button"
            >
              {isDownloading ? "Descargando..." : "Descargar resultados CSV"}
            </button>
          </div>
        </form>

        {error ? (
          <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
      </section>

      {response ? (
        <section className="mt-6 space-y-6">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">Métricas generales</h3>
            <p className="mt-1 text-sm text-slate-500">Archivo analizado: {response.source_file}</p>
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
                <li key={key} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                  <span>{label}</span>
                  <span className="font-semibold">{response.summary.invalid_breakdown[key] ?? 0}</span>
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
              <h3 className="text-lg font-semibold text-slate-900">Índice de satisfacción</h3>
              <p className="mt-2 text-sm text-slate-700">
                Casos puntuados: <strong>{response.summary.scored_cases}</strong> de{" "}
                <strong>{response.summary.closed_cases}</strong>
              </p>
              <p className="mt-1 text-sm text-slate-700">
                Promedio: <strong>{response.summary.average_score.toFixed(2)} / 5.00</strong>
              </p>
              <ul className="mt-4 space-y-2 text-sm text-slate-700">
                {SCORE_ORDER.map((score) => (
                  <li key={score} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span>Score {score}</span>
                    <span className="font-semibold">{response.summary.score_counts[score] ?? 0}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>
        </section>
      ) : null}
    </main>
  );
}
