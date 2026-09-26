"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  Incident,
  IncidentSummary,
  IncidentStatus,
  IncidentCategory,
  IncidentOrigin,
  IncidentFormState,
} from "@/types/incident";
import {
  STATUS_LABELS,
  STATUS_COLORS,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  BRANCH_OPTIONS as VALID_BRANCHES,
  API_BASE,
  EMPTY_FORM,
} from "@/lib/incidents";
import { LoadingSpinner, ErrorMessage } from "@/components/ui";

// ── API helpers ──────────────────────────────────────────────────────────────

async function fetchFromApi<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error("Error de comunicación con el servidor. Inténtalo de nuevo.");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Component ────────────────────────────────────────────────────────────────

export default function IncidentsManagerClient() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [categoryFilter, setCategoryFilter] = useState<IncidentCategory | "">("");
  const [branchFilter, setBranchFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  // Form / detail
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<IncidentFormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // ── Data fetching ─────────────────────────────────────────────────────────

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    setListError(null);
    try {
      const [incidentsData, summaryData] = await Promise.all([
        fetchFromApi<Incident[]>(`${API_BASE}`),
        fetchFromApi<IncidentSummary>(`${API_BASE}/summary`),
      ]);
      setIncidents(incidentsData);
      setSummary(summaryData);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // ── Filtering ──────────────────────────────────────────────────────────────

  const filteredIncidents = useMemo(() => {
    return incidents.filter((inc) => {
      if (statusFilter && inc.status !== statusFilter) return false;
      if (categoryFilter && inc.category !== categoryFilter) return false;
      if (branchFilter && inc.branch !== branchFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (
          !inc.title.toLowerCase().includes(q) &&
          !inc.description.toLowerCase().includes(q)
        )
          return false;
      }
      return true;
    });
  }, [incidents, statusFilter, categoryFilter, branchFilter, searchQuery]);

  // ── Validation ─────────────────────────────────────────────────────────────

  const validateForm = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (form.title.trim().length < 2) errors.title = "Title must be at least 2 characters";
    if (form.title.trim().length > 200) errors.title = "Title must not exceed 200 characters";
    if (form.description.trim().length < 10)
      errors.description = "Description must be at least 10 characters";
    if (form.description.trim().length > 2000)
      errors.description = "Description must not exceed 2000 characters";
    if (!form.category) errors.category = "Category is required";
    if (!form.branch) errors.branch = "Branch is required";
    return errors;
  };

  // ── CRUD operations ────────────────────────────────────────────────────────

  const handleCreate = async () => {
    const errors = validateForm();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsSaving(true);
    try {
      await fetchFromApi(`${API_BASE}`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      setFeedback("Incidente creado correctamente");
      setShowForm(false);
      setForm(EMPTY_FORM);
      await refreshData();
    } catch {
      setFeedback("Error al crear el incidente. Inténtalo de nuevo.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const errors = validateForm();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsSaving(true);
    try {
      await fetchFromApi(`${API_BASE}/${editingId}`, {
        method: "PATCH",
        body: JSON.stringify(form),
      });
      setFeedback("Incidente actualizado correctamente");
      setEditingId(null);
      setSelectedIncident(null);
      setShowForm(false);
      setForm(EMPTY_FORM);
      await refreshData();
    } catch {
      setFeedback("Error al actualizar el incidente. Inténtalo de nuevo.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Estás seguro de eliminar este incidente?")) return;
    try {
      await fetchFromApi(`${API_BASE}/${id}`, { method: "DELETE" });
      setFeedback("Incidente eliminado");
      if (selectedIncident?.id === id) setSelectedIncident(null);
      await refreshData();
    } catch {
      setFeedback("Error al eliminar el incidente. Inténtalo de nuevo.");
    }
  };

  const startEdit = (incident: Incident) => {
    setForm({
      title: incident.title,
      description: incident.description,
      category: incident.category,
      status: incident.status,
      origin: incident.origin,
      branch: incident.branch,
    });
    setEditingId(incident.id);
    setShowForm(true);
    setSelectedIncident(null);
  };

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(true);
    setSelectedIncident(null);
  };

  // ── Format helpers ─────────────────────────────────────────────────────────

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

  const clearFeedback = () => setFeedback(null);

  // ── Render ─────────────────────────────────────────────────────────────────

  if (isLoading && incidents.length === 0) {
    return <LoadingSpinner message="Loading incidents..." />;
  }

  if (listError) {
    return (
      <ErrorMessage
        title="Error de conexión"
        message="No se pudieron cargar los incidentes. Inténtalo de nuevo más tarde."
        onRetry={refreshData}
        retryLabel="Reintentar"
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Feedback toast */}
      {feedback && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{feedback}</span>
          <button onClick={clearFeedback} className="ml-4 font-bold hover:text-emerald-600">
            &times;
          </button>
        </div>
      )}

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Incidents Manager</h1>
          <p className="text-sm text-slate-500">
            Centralized incident registry — HealthCore Digital
          </p>
        </div>
        <button
          onClick={openCreate}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + New Incident
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Total</p>
            <p className="mt-1 text-3xl font-bold text-slate-900">{summary.total}</p>
          </div>
          {(["open", "in_progress", "resolved", "discarded"] as IncidentStatus[]).map(
            (status) => (
              <div
                key={status}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {STATUS_LABELS[status]}
                </p>
                <p className="mt-1 text-3xl font-bold text-slate-900">
                  {summary.by_status[status] || 0}
                </p>
              </div>
            )
          )}
        </div>
      )}

      {/* Category breakdown */}
      {summary && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">By Category</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.by_category).map(([cat, count]) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
              >
                {CATEGORY_LABELS[cat as IncidentCategory] || cat}
                <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-xs font-bold">
                  {count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search by title or description..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | "")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          {(["open", "in_progress", "resolved", "discarded"] as IncidentStatus[]).map(
            (s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            )
          )}
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as IncidentCategory | "")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Categories</option>
          {(
            [
              "clinical_equipment",
              "it_system",
              "billing_error",
              "compliance_breach",
              "patient_experience",
              "staff_issue",
              "facility_issue",
              "referral_issue",
              "other",
            ] as IncidentCategory[]
          ).map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABELS[c]}
            </option>
          ))}
        </select>
        <select
          value={branchFilter}
          onChange={(e) => setBranchFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All Branches</option>
          {VALID_BRANCHES.map((b) => (
            <option key={b.value} value={b.value}>
              {b.label}
            </option>
          ))}
        </select>
        {(statusFilter || categoryFilter || branchFilter || searchQuery) && (
          <button
            onClick={() => {
              setStatusFilter("");
              setCategoryFilter("");
              setBranchFilter("");
              setSearchQuery("");
            }}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Incident list */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="px-4 py-3 font-semibold text-slate-600">ID</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Title</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Category</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Status</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Branch</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Created</th>
              <th className="px-4 py-3 font-semibold text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredIncidents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No incidents found
                </td>
              </tr>
            ) : (
              filteredIncidents.map((inc) => (
                <tr
                  key={inc.id}
                  className={`hover:bg-slate-50 cursor-pointer ${
                    selectedIncident?.id === inc.id ? "bg-blue-50" : ""
                  }`}
                  onClick={() =>
                    setSelectedIncident(
                      selectedIncident?.id === inc.id ? null : inc
                    )
                  }
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
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {inc.branch_label}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {formatDate(inc.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(inc);
                        }}
                        className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(inc.id);
                        }}
                        className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail panel */}
      {selectedIncident && !showForm && (
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
            <div className="flex gap-2">
              <button
                onClick={() => startEdit(selectedIncident)}
                className="rounded-lg border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50"
              >
                Edit
              </button>
              <button
                onClick={() => setSelectedIncident(null)}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
              >
                Close
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
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
              <p className="mt-1 text-sm font-medium text-slate-900">
                {ORIGIN_LABELS[selectedIncident.origin]}
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

      {/* Create / Edit form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">
                {editingId ? "Edit Incident" : "New Incident"}
              </h2>
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                  setForm(EMPTY_FORM);
                  setFormErrors({});
                }}
                className="text-2xl leading-none text-slate-400 hover:text-slate-600"
              >
                &times;
              </button>
            </div>

            {/* Compliance warning */}
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <strong>&#9888; Important:</strong> Do not include any patient-identifiable
              information (name, date of birth, medical record number, contact details).
              This system must comply with HIPAA and UK GDPR regulations.
            </div>

            <div className="space-y-4">
              {/* Title */}
              <div>
                <label className="block text-sm font-medium text-slate-700">Title *</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  placeholder="Brief title of the incident"
                />
                {formErrors.title && (
                  <p className="mt-1 text-xs text-red-600">{formErrors.title}</p>
                )}
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-slate-700">
                  Description *
                </label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={4}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  placeholder="Detailed description — no patient data"
                />
                <div className="mt-1 flex justify-between">
                  {formErrors.description ? (
                    <p className="text-xs text-red-600">{formErrors.description}</p>
                  ) : (
                    <span />
                  )}
                  <span className="text-xs text-slate-400">
                    {form.description.length}/2000
                  </span>
                </div>
              </div>

              {/* Category + Status + Origin */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Category *
                  </label>
                  <select
                    value={form.category}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        category: e.target.value as IncidentCategory,
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="">Select category</option>
                    {(
                      [
                        "clinical_equipment",
                        "it_system",
                        "billing_error",
                        "compliance_breach",
                        "patient_experience",
                        "staff_issue",
                        "facility_issue",
                        "referral_issue",
                        "other",
                      ] as IncidentCategory[]
                    ).map((c) => (
                      <option key={c} value={c}>
                        {CATEGORY_LABELS[c]}
                      </option>
                    ))}
                  </select>
                  {formErrors.category && (
                    <p className="mt-1 text-xs text-red-600">{formErrors.category}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Status
                  </label>
                  <select
                    value={form.status}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        status: e.target.value as IncidentStatus,
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    {(["open", "in_progress", "resolved", "discarded"] as IncidentStatus[]).map(
                      (s) => (
                        <option key={s} value={s}>
                          {STATUS_LABELS[s]}
                        </option>
                      )
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Origin
                  </label>
                  <select
                    value={form.origin}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        origin: e.target.value as IncidentOrigin,
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    {(["customer", "branch", "internal"] as IncidentOrigin[]).map((o) => (
                      <option key={o} value={o}>
                        {ORIGIN_LABELS[o]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Branch */}
              <div>
                <label className="block text-sm font-medium text-slate-700">
                  Branch *
                </label>
                <select
                  value={form.branch}
                  onChange={(e) => setForm({ ...form, branch: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">Select branch</option>
                  {VALID_BRANCHES.map((b) => (
                    <option key={b.value} value={b.value}>
                      {b.label}
                    </option>
                  ))}
                </select>
                {formErrors.branch && (
                  <p className="mt-1 text-xs text-red-600">{formErrors.branch}</p>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                  setForm(EMPTY_FORM);
                  setFormErrors({});
                }}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={editingId ? handleUpdate : handleCreate}
                disabled={isSaving}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {isSaving ? "Saving..." : editingId ? "Update Incident" : "Create Incident"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}