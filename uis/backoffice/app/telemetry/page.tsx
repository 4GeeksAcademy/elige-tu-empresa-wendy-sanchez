"use client";

import { useCallback, useEffect, useState } from "react";

/* ── Types ────────────────────────────────────────────────────────── */

interface Period {
  from: string;
  to: string;
}

interface EventsPerDay {
  date: string;
  event_count: number;
}

interface ErrorRateByType {
  event_type: string;
  total_events: number;
  error_events: number;
  error_rate_pct: number;
}

interface LatencyRow {
  route_template: string;
  method: string;
  count: number;
  mean_ms: number;
  min_ms: number;
  max_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
}

interface EventTypeDist {
  event_type: string;
  count: number;
  percentage: number;
}

interface AuthFailureRate {
  date: string;
  total_attempts: number;
  failed_count: number;
  succeeded_count: number;
  failure_rate_pct: number;
}

interface ReportMetrics {
  events_per_day: EventsPerDay[];
  error_rate_by_type: ErrorRateByType[];
  latency_percentiles_by_route: LatencyRow[];
  event_type_distribution: EventTypeDist[];
  auth_failure_rate: AuthFailureRate[];
}

interface ReportResponse {
  period: Period;
  metrics: ReportMetrics;
}

/* ── Helpers ──────────────────────────────────────────────────────── */

function fmtPct(v: number): string {
  return `${v.toFixed(1)}%`;
}

function fmtMs(v: number): string {
  return `${v.toFixed(1)} ms`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toUTCString().replace(" GMT", " UTC");
}

/** Build a simple inline bar (SVG) – maxWidth px proportional to value / maxValue */
function bar(value: number, maxValue: number, maxWidth = 200, color = "bg-blue-500"): string {
  const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
  return `<div class="flex items-center gap-2">
    <div class="h-4 ${color} rounded" style="width:${Math.max(pct * (maxWidth / 100), 4)}px"></div>
    <span class="text-xs text-slate-500">${value}</span>
  </div>`;
}

/* ── Component ────────────────────────────────────────────────────── */

export default function TelemetryReportPage() {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = useCallback(async (start?: string, end?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (start) params.set("start_date", start);
      if (end) params.set("end_date", end);
      const qs = params.toString();
      const res = await fetch(`/api/telemetry/report${qs ? `?${qs}` : ""}`);
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      setReport(await res.json() as ReportResponse);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  /* ── Helpers for bar colors ────────────────────────────────────── */

  const maxEvents = Math.max(...(report?.metrics.events_per_day ?? []).map((r) => r.event_count), 1);
  const maxErrors = Math.max(...(report?.metrics.error_rate_by_type ?? []).map((r) => r.total_events), 1);
  const maxDist = Math.max(...(report?.metrics.event_type_distribution ?? []).map((r) => r.count), 1);
  const maxAuth = Math.max(...(report?.metrics.auth_failure_rate ?? []).map((r) => r.total_attempts), 1);

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <h2 className="text-2xl font-bold text-slate-900">Telemetry — Operational Report</h2>
      <p className="mt-1 text-sm text-slate-500">
        Technical dashboard for engineering team. All metrics computed from raw telemetry events.
      </p>

      {/* ── Period Selector ──────────────────────────────────────── */}
      <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold text-slate-600">From:</label>
          <input
            type="datetime-local"
            id="start-input"
            className="rounded border border-slate-300 px-2 py-1 text-xs"
          />
          <label className="text-xs font-semibold text-slate-600">To:</label>
          <input
            type="datetime-local"
            id="end-input"
            className="rounded border border-slate-300 px-2 py-1 text-xs"
          />
          <button
            className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700"
            onClick={() => {
              const s = (document.getElementById("start-input") as HTMLInputElement)?.value;
              const e = (document.getElementById("end-input") as HTMLInputElement)?.value;
              fetchReport(s ? `${s}:00Z` : undefined, e ? `${e}:00Z` : undefined);
            }}
          >
            Update
          </button>
          <button
            className="rounded bg-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-300"
            onClick={() => fetchReport()}
          >
            Last 7 days
          </button>
        </div>
      </section>

      {/* ── Loading / Error ──────────────────────────────────────── */}
      {loading && (
        <section className="mt-6 animate-pulse rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading report…
        </section>
      )}

      {error && (
        <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <strong>Error:</strong> {error}
        </section>
      )}

      {!loading && !error && !report && (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No data available for the selected period.
        </section>
      )}

      {!loading && report && (
        <>
          {/* ── Period banner ──────────────────────────────────────── */}
          <section className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            <strong>Period:</strong> {formatDate(report.period.from)} → {formatDate(report.period.to)}
          </section>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">

            {/* ── 1. Events per day ──────────────────────────────── */}
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">Events per day</h3>
              {report.metrics.events_per_day.length === 0 && <p className="mt-2 text-xs text-slate-500">No events in period.</p>}
              {report.metrics.events_per_day.length > 0 && (
                <div className="mt-3 space-y-1">
                  {report.metrics.events_per_day.map((row) => (
                    <div key={row.date} className="flex items-center gap-2 text-xs">
                      <span className="w-24 shrink-0 font-medium text-slate-700">{row.date}</span>
                      <div className="h-3 rounded bg-blue-500" style={{ width: `${Math.max((row.event_count / maxEvents) * 200, 3)}px` }} />
                      <span className="text-slate-500">{row.event_count}</span>
                    </div>
                  ))}
                </div>
              )}
            </article>

            {/* ── 2. Error rate by type ──────────────────────────── */}
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">Error rate by type</h3>
              {report.metrics.error_rate_by_type.length === 0 && <p className="mt-2 text-xs text-slate-500">No data.</p>}
              {report.metrics.error_rate_by_type.length > 0 && (
                <div className="mt-3 max-h-64 overflow-y-auto space-y-1">
                  {report.metrics.error_rate_by_type.map((row) => (
                    <div key={row.event_type} className="flex items-center gap-1 text-xs">
                      <span className="w-40 shrink-0 truncate font-medium text-slate-700" title={row.event_type}>{row.event_type}</span>
                      <div className="h-3 rounded" style={{ width: `${Math.max((row.total_events / maxErrors) * 200, 3)}px`, backgroundColor: row.error_rate_pct > 50 ? "#ef4444" : row.error_rate_pct > 0 ? "#f59e0b" : "#22c55e" }} />
                      <span className="text-slate-500">{row.total_events}</span>
                      <span className="text-slate-400">|</span>
                      <span className={row.error_rate_pct > 50 ? "text-red-500" : row.error_rate_pct > 0 ? "text-amber-500" : "text-green-500"}>{fmtPct(row.error_rate_pct)}</span>
                    </div>
                  ))}
                </div>
              )}
            </article>

            {/* ── 3. Latency percentiles by route ────────────────── */}
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">Latency percentiles by route</h3>
              {report.metrics.latency_percentiles_by_route.length === 0 && <p className="mt-2 text-xs text-slate-500">No latency data in period.</p>}
              {report.metrics.latency_percentiles_by_route.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-xs text-slate-700">
                    <thead>
                      <tr className="text-left text-slate-500">
                        <th className="px-1 py-1">Route</th>
                        <th className="px-1 py-1">Method</th>
                        <th className="px-1 py-1 text-right">Count</th>
                        <th className="px-1 py-1 text-right">Mean</th>
                        <th className="px-1 py-1 text-right">P50</th>
                        <th className="px-1 py-1 text-right">P95</th>
                        <th className="px-1 py-1 text-right">P99</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.metrics.latency_percentiles_by_route.map((row) => (
                        <tr key={`${row.route_template}-${row.method}`} className="border-t border-slate-100">
                          <td className="px-1 py-1 font-mono text-xs truncate max-w-36" title={row.route_template}>{row.route_template}</td>
                          <td className="px-1 py-1 font-mono text-xs">{row.method}</td>
                          <td className="px-1 py-1 text-right text-slate-500">{row.count}</td>
                          <td className="px-1 py-1 text-right">{fmtMs(row.mean_ms)}</td>
                          <td className="px-1 py-1 text-right">{fmtMs(row.p50_ms)}</td>
                          <td className="px-1 py-1 text-right">{fmtMs(row.p95_ms)}</td>
                          <td className="px-1 py-1 text-right">{fmtMs(row.p99_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>

            {/* ── 4. Event type distribution ─────────────────────── */}
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">Event type distribution</h3>
              {report.metrics.event_type_distribution.length === 0 && <p className="mt-2 text-xs text-slate-500">No data.</p>}
              {report.metrics.event_type_distribution.length > 0 && (
                <div className="mt-3 max-h-64 overflow-y-auto space-y-1">
                  {report.metrics.event_type_distribution.map((row) => (
                    <div key={row.event_type} className="flex items-center gap-1 text-xs">
                      <span className="w-40 shrink-0 truncate text-slate-700" title={row.event_type}>{row.event_type}</span>
                      <div className="h-3 rounded bg-violet-500" style={{ width: `${Math.max((row.count / maxDist) * 200, 3)}px` }} />
                      <span className="text-slate-500">{fmtPct(row.percentage)}</span>
                    </div>
                  ))}
                </div>
              )}
            </article>

            {/* ── 5. Auth failure rate ───────────────────────────── */}
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-semibold text-slate-900">Auth failure rate by day</h3>
              {report.metrics.auth_failure_rate.length === 0 && <p className="mt-2 text-xs text-slate-500">No auth events in period.</p>}
              {report.metrics.auth_failure_rate.length > 0 && (
                <div className="mt-3 space-y-1">
                  {report.metrics.auth_failure_rate.map((row) => (
                    <div key={row.date} className="flex items-center gap-1 text-xs">
                      <span className="w-24 shrink-0 font-medium text-slate-700">{row.date}</span>
                      <div className="flex items-center gap-1">
                        <div className="h-3 rounded bg-red-500" style={{ width: `${Math.max((row.failed_count / maxAuth) * 200, 2)}px` }} />
                        <div className="h-3 rounded bg-green-500" style={{ width: `${Math.max((row.succeeded_count / maxAuth) * 200, 2)}px` }} />
                      </div>
                      <span className={row.failure_rate_pct > 50 ? "text-red-500" : "text-slate-500"}>
                        {fmtPct(row.failure_rate_pct)}
                      </span>
                      <span className="text-slate-400">({row.failed_count}f / {row.succeeded_count}s)</span>
                    </div>
                  ))}
                </div>
              )}
            </article>

          </div>
        </>
      )}
    </main>
  );
}