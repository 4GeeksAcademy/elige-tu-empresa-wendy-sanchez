"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Incident,
  IncidentStatus,
  IncidentCategory,
  IncidentOrigin,
} from "@/types/incident";
import {
  STATUS_LABELS,
  STATUS_COLORS,
  CATEGORY_LABELS,
  BRANCH_LABELS,
  ALL_STATUSES,
  ALL_CATEGORIES,
  ALL_BRANCHES,
  STATUS_OPTIONS,
  API_BASE,
} from "@/lib/incidents";

import { LoadingSpinner, ErrorMessage } from "@/components/ui";

// ── Component ────────────────────────────────────────────────────────────────

export default function IncidentListPanel() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [originFilter, setOriginFilter] = useState<IncidentOrigin | "">("");
  const [branchFilter, setBranchFilter] = useState("");

  // Detail / status update
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);
  const [updatingIds, setUpdatingIds] = useState<Set<number>>(new Set());

  // ── Fetch ─────────────────────────────────────────────────────────────────

  const fetchIncidents = useCallback(async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const data = await fetch(API_BASE).then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      });
      setIncidents(data);
    } catch {
      setFetchError("No se pudieron cargar los incidentes.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  // ── Filtering ──────────────────────────────────────────────────────────────

  const filteredIncidents = useMemo(() => {
    return incidents.filter((inc) => {
      if (statusFilter && inc.status !== statusFilter) return false;
      if (originFilter && inc.origin !== originFilter) return false;
      if (branchFilter && inc.branch !== branchFilter) return false;
      return true;
    });
  }, [incidents, statusFilter, originFilter, branchFilter]);

  // ── Status update ──────────────────────────────────────────────────────────

  const handleStatusChange = useCallback(
    async (incidentId: number, newStatus: IncidentStatus) => {
      setStatusUpdateError(null);
      setUpdatingIds((prev) => new Set(prev).add(incidentId));

      // Optimistic update
      const prevIncidents = [...incidents];
      setIncidents((prev) =>
        prev.map((inc) =>
          inc.id === incidentId ? { ...inc, status: newStatus } : inc,
        )
      );

      try {
        const res = await fetch(
          `${API_BASE}/${incidentId}/status`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus }),
          },
        );

        if (!res.ok) {
          setStatusUpdateError("Error al actualizar el estado. Inténtalo de nuevo.");
          // Rollback
          setIncidents(prevIncidents);
          return;
        }

        // Refresh the updated incident detail
        const updated = await res.json();
        setIncidents((prev) =>
          prev.map((inc) => (inc.id === incidentId ? updated : inc)),
        );
      } catch {
        setStatusUpdateError("Error de conexión. No se pudo actualizar el estado.");
        // Rollback
        setIncidents(prevIncidents);
      } finally {
        setUpdatingIds((prev) => {
          const copy = new Set(prev);
          copy.delete(incidentId);
          return copy;
        });
      }
    },
    [incidents],
  );

  // ── Detail selection ───────────────────────────────────────────────────────

  const viewDetail = (inc: Incident) => {
    setSelectedIncident(selectedIncident?.id === inc.id ? null : inc);
  };

  // ── Format date ────────────────────────────────────────────────────────────

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // ── Loading state ──────────────────────────────────────────────────────────

  if (isLoading) {
    return <LoadingSpinner message="Loading incidents..." />;
  }

  // ── Error state ────────────────────────────────────────────────────────────

  if (fetchError) {
    return (
      <ErrorMessage
        title="Error de conexión"
        message="No se pudieron cargar los incidentes. Inténtalo de nuevo más tarde."
        onRetry={fetchIncidents}
      />
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Incidents</h1>
        <p className="mt-1 text-sm text-slate-500">
          {incidents.length} incident{incidents.length !== 1 ? "s" : ""} registered
        </p>
      </div>

      {/* Status update error toast */}
      {statusUpdateError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span className="font-bold">Status update failed:</span> {statusUpdateError}
          <button
            onClick={() => setStatusUpdateError(null)}
            className="ml-2 font-bold hover:text-red-600"
          >
            &times;
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All statuses</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>

        <select
          value={originFilter}
          onChange={(e) => setOriginFilter(e.target.value as IncidentOrigin | "")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All origins</option>
          <option value="customer">Customer</option>
          <option value="branch">Branch</option>
          <option value="internal">Internal</option>
        </select>

        <select
          value={branchFilter}
          onChange={(e) => setBranchFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All branches</option>
          {ALL_BRANCHES.map((b) => (
            <option key={b} value={b}>
              {BRANCH_LABELS[b]}
            </option>
          ))}
        </select>

        {(statusFilter || originFilter || branchFilter) && (
          <button
            onClick={() => {
              setStatusFilter("");
              setOriginFilter("");
              setBranchFilter("");
            }}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Empty state */}
      {filteredIncidents.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
          <p className="text-sm text-slate-500">
            {incidents.length === 0
              ? "No incidents have been registered yet. Create one from the registration form."
              : "No incidents match the current filters. Try adjusting or clearing them."}
          </p>
        </div>
      )}

      {/* Table */}
      {filteredIncidents.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="px-4 py-3 font-semibold text-slate-600">ID</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Title</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Category</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Status</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Origin</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Branch</th>
                <th className="px-4 py-3 font-semibold text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredIncidents.map((inc) => (
                <tr
                  key={inc.id}
                  onClick={() => viewDetail(inc)}
                  className={`cursor-pointer hover:bg-slate-50 ${
                    selectedIncident?.id === inc.id ? "bg-blue-50" : ""
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    #{inc.id}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 font-medium text-slate-900">
                    {inc.title}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                      {CATEGORY_LABELS[inc.category] || inc.category}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                        STATUS_COLORS[inc.status]
                      }`}
                    >
                      {STATUS_LABELS[inc.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600 capitalize">
                    {inc.origin}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {inc.branch_label}
                  </td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <StatusDropdown
                      currentStatus={inc.status}
                      incidentId={inc.id}
                      isUpdating={updatingIds.has(inc.id)}
                      onChange={handleStatusChange}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail panel */}
      {selectedIncident && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                {selectedIncident.title}
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                #{selectedIncident.id} &middot; {selectedIncident.branch_label}
              </p>
            </div>
            <button
              onClick={() => setSelectedIncident(null)}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
            >
              Close
            </button>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Status
              </p>
              <span
                className={`mt-1 inline-block rounded-full border px-3 py-1 text-sm font-medium ${
                  STATUS_COLORS[selectedIncident.status]
                }`}
              >
                {STATUS_LABELS[selectedIncident.status]}
              </span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Category
              </p>
              <p className="mt-1 text-sm font-medium text-slate-900">
                {CATEGORY_LABELS[selectedIncident.category]}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Origin
              </p>
              <p className="mt-1 text-sm capitalize text-slate-900">
                {selectedIncident.origin}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Branch
              </p>
              <p className="mt-1 text-sm text-slate-900">
                {selectedIncident.branch_label}
              </p>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Description
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
              {selectedIncident.description}
            </p>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Created
              </p>
              <p className="mt-1 text-sm text-slate-700">
                {formatDate(selectedIncident.created_at)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Last Updated
              </p>
              <p className="mt-1 text-sm text-slate-700">
                {formatDate(selectedIncident.updated_at)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Status dropdown ──────────────────────────────────────────────────────────

function StatusDropdown({
  currentStatus,
  incidentId,
  isUpdating,
  onChange,
}: {
  currentStatus: IncidentStatus;
  incidentId: number;
  isUpdating: boolean;
  onChange: (id: number, status: IncidentStatus) => Promise<void>;
}) {
  const statusOpts = STATUS_OPTIONS.find((s) => s.value === currentStatus);
  const allowedTransitions = statusOpts?.transitions ?? [];
  const isFinal = allowedTransitions.length === 0;

  if (isFinal) {
    return (
      <span className="text-xs text-slate-400 italic">Final state</span>
    );
  }

  return (
    <div className="flex gap-1">
      {allowedTransitions.map((target) => (
        <button
          key={target}
          disabled={isUpdating}
          onClick={() => onChange(incidentId, target as IncidentStatus)}
          className={`rounded px-2 py-1 text-xs font-medium transition-colors disabled:opacity-40 ${
            target === "resolved"
              ? "bg-green-100 text-green-700 hover:bg-green-200"
              : target === "discarded"
                ? "bg-slate-100 text-slate-600 hover:bg-slate-200"
                : "bg-blue-100 text-blue-700 hover:bg-blue-200"
          }`}
        >
          {isUpdating ? "..." : statusLabel(target as IncidentStatus)}
        </button>
      ))}
    </div>
  );
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status as IncidentStatus] || status;
}