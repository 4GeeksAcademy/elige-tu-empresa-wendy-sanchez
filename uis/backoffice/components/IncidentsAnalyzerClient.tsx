"use client";

import dynamic from "next/dynamic";
import { FormEvent, useMemo, useState } from "react";

// ── Lazy-loaded component ────────────────────────────────────────────
// AnalysisResultsPanel es un componente pesado (tablas, desgloses, listas)
// que solo se muestra DESPUÉS de que el usuario analiza un CSV.
// Diferir su carga reduce el JS inicial y mejora el LCP.
const AnalysisResultsPanel = dynamic(
  () => import("@/components/AnalysisResultsPanel"),
  {
    ssr: false,
  },
);

export type AnalysisSummary = {
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

export type AnalysisResponse = {
  source_file: string;
  summary: AnalysisSummary;
};

const API_BASE = "";

export default function IncidentsAnalyzerClient() {
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AnalysisResponse | null>(null);

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
        throw new Error("No se pudo analizar el fichero. Inténtalo de nuevo.");
      }

      const payload = (await res.json()) as AnalysisResponse;
      setResponse(payload);
    } catch {
      setResponse(null);
      setError("No se pudo analizar el fichero. Inténtalo de nuevo.");
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
        throw new Error("No se pudo descargar el CSV. Inténtalo de nuevo.");
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
    } catch {
      setError("No se pudo descargar el CSV. Inténtalo de nuevo.");
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
        throw new Error("No se pudo cargar la muestra. Inténtalo de nuevo.");
      }

      const payload = (await res.json()) as AnalysisResponse;
      setResponse(payload);
    } catch {
      setResponse(null);
      setError("No se pudo cargar la muestra. Inténtalo de nuevo.");
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
        <AnalysisResultsPanel
          response={response}
          onDownloadCsv={onDownloadCsv}
          isDownloading={isDownloading}
        />
      ) : null}
    </main>
  );
}
