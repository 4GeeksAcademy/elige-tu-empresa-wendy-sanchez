"use client";

import { useCallback, useEffect, useState } from "react";

// ── Types ───────────────────────────────────────────────────────────────────

interface SummaryData {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_branch: Record<string, number>;
  by_origin: Record<string, number>;
}

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

const STATUS_ORDER = ["open", "in_progress", "resolved", "discarded"];

const CATEGORY_LABELS: Record<string, string> = {
  clinical_equipment: "Clinical Equipment",
  it_system: "IT System",
  billing_error: "Billing Error",
  compliance_breach: "Compliance Breach",
  patient_experience: "Patient Experience",
  staff_issue: "Staff Issue",
  facility_issue: "Facility Issue",
  referral_issue: "Referral Issue",
  other: "Other",
};

const BRANCH_LABELS: Record<string, string> = {
  central: "Central — Austin Main Clinic",
  austin_north: "Austin — North",
  dallas_uptown: "Dallas Uptown",
  houston_med_center: "Houston Medical Center",
  san_antonio_west: "San Antonio West",
  miami_brickell: "Miami Brickell",
  miami_doral: "Miami Doral",
  orlando_east: "Orlando East",
  tampa_bay: "Tampa Bay",
  atlanta_midtown: "Atlanta Midtown",
  savannah: "Savannah",
  london_city: "London City",
  london_west: "London West End",
  manchester_central: "Manchester Central",
};

const API_BASE = process.env.NEXT_PUBLIC_INCIDENTS_API_URL || "/api/incidents";

// ── Component ────────────────────────────────────────────────────────────────

export default function IncidentSummaryPanel() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetch(`${API_BASE}/summary`).then((r) => {
        if (!r.ok) throw new Error(`API error ${r.status}`);
        return r.json();
      });
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load summary");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // ── Loading ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-slate-500">
            <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span>Loading summary...</span>
          </div>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
          <h2 className="text-lg font-bold">Could not load summary</h2>
          <p className="mt-2 text-sm">{error}</p>
          <p className="mt-2 text-xs text-red-600">
            Ensure the API is running at {API_BASE}
          </p>
          <button
            onClick={fetchSummary}
            className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!summary) return null;

  // ── Helpers ────────────────────────────────────────────────────────────────

  const total = summary.total;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Summary</h1>
        <p className="mt-1 text-sm text-slate-500">
          Aggregated metrics from the incident registry
        </p>
      </div>

      {/* Total */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Total Incidents
        </p>
        <p className="mt-1 text-4xl font-bold text-slate-900">{total}</p>
      </div>

      {/* Grid: Status + Origin */}
      <div className="mb-6 grid gap-6 sm:grid-cols-2">
        {/* By status */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">By Status</h3>
          {STATUS_ORDER.map((s) => {
            const count = summary.by_status[s] || 0;
            const pct = total > 0 ? ((count / total) * 100).toFixed(0) : "0";
            return (
              <div key={s} className="mb-2 last:mb-0">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{STATUS_LABELS[s] || s}</span>
                  <span className="font-semibold text-slate-900">{count}</span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* By origin */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">By Origin</h3>
          <div className="space-y-2">
            {Object.entries(summary.by_origin)
              .sort(([, a], [, b]) => b - a)
              .map(([origin, count]) => (
                <div
                  key={origin}
                  className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
                >
                  <span className="text-sm capitalize text-slate-600">{origin}</span>
                  <span className="text-sm font-bold text-slate-900">{count}</span>
                </div>
              ))}
            {Object.keys(summary.by_origin).length === 0 && (
              <p className="text-sm text-slate-400">No data</p>
            )}
          </div>
        </div>
      </div>

      {/* By category */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">By Category</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(summary.by_category)
            .sort(([, a], [, b]) => b - a)
            .map(([cat, count]) => {
              const pct = total > 0 ? ((count / total) * 100).toFixed(0) : "0";
              return (
                <div
                  key={cat}
                  className="rounded-lg border border-slate-100 bg-slate-50 p-3"
                >
                  <p className="text-xs text-slate-500">
                    {CATEGORY_LABELS[cat] || cat}
                  </p>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="text-xl font-bold text-slate-900">{count}</span>
                    <span className="text-xs text-slate-400">{pct}%</span>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* By branch */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">By Branch</h3>
        {Object.keys(summary.by_branch).length === 0 ? (
          <p className="text-sm text-slate-400">No data</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(summary.by_branch)
              .sort(([, a], [, b]) => b - a)
              .map(([branch, count]) => {
                const pct = total > 0 ? ((count / total) * 100).toFixed(0) : "0";
                return (
                  <div
                    key={branch}
                    className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2"
                  >
                    <span className="text-sm text-slate-600">
                      {BRANCH_LABELS[branch] || branch}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">{count}</span>
                      <div className="h-2 w-12 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-emerald-400"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}