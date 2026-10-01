"use client";

import type { IncidentCategory, IncidentFormState } from "@/types/incident";
import {
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  BRANCH_OPTIONS as BRANCHES,
  ALL_CATEGORIES,
  ALL_ORIGINS,
} from "@/lib/incidents";

interface Props {
  form: IncidentFormState;
  editingId: number | null;
  isSaving: boolean;
  formErrors: Record<string, string>;
  onChange: (form: IncidentFormState) => void;
  onSave: () => void;
  onCancel: () => void;
}

export default function IncidentFormPanel({
  form,
  editingId,
  isSaving,
  formErrors,
  onChange,
  onSave,
  onCancel,
}: Props) {
  const updateField = <K extends keyof IncidentFormState>(
    key: K,
    value: IncidentFormState[K],
  ) => {
    onChange({ ...form, [key]: value });
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        {editingId ? "Edit Incident" : "New Incident"}
      </h3>
      <p className="mb-4 text-sm text-slate-500">
        {editingId
          ? "Update the incident details below."
          : "Fill in the details to register a new incident."}
      </p>

      <div className="space-y-4">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => updateField("title", e.target.value)}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              formErrors.title
                ? "border-red-400"
                : "border-slate-300 focus:border-blue-500"
            }`}
            maxLength={200}
          />
          {formErrors.title && (
            <p className="mt-1 text-xs text-red-600">{formErrors.title}</p>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            rows={4}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              formErrors.description
                ? "border-red-400"
                : "border-slate-300 focus:border-blue-500"
            }`}
            maxLength={2000}
          />
          {formErrors.description && (
            <p className="mt-1 text-xs text-red-600">
              {formErrors.description}
            </p>
          )}
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Category <span className="text-red-500">*</span>
          </label>
          <select
            value={form.category}
            onChange={(e) =>
              updateField("category", e.target.value as IncidentCategory)
            }
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              formErrors.category
                ? "border-red-400"
                : "border-slate-300 focus:border-blue-500"
            }`}
          >
            <option value="">Select category</option>
            {ALL_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {CATEGORY_LABELS[cat]}
              </option>
            ))}
          </select>
          {formErrors.category && (
            <p className="mt-1 text-xs text-red-600">{formErrors.category}</p>
          )}
        </div>

        {/* Origin */}
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Origin
          </label>
          <select
            value={form.origin}
            onChange={(e) => updateField("origin", e.target.value as IncidentFormState["origin"])}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            {ALL_ORIGINS.map((origin) => (
              <option key={origin} value={origin}>
                {ORIGIN_LABELS[origin]}
              </option>
            ))}
          </select>
        </div>

        {/* Branch */}
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Branch <span className="text-red-500">*</span>
          </label>
          <select
            value={form.branch}
            onChange={(e) => updateField("branch", e.target.value)}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              formErrors.branch
                ? "border-red-400"
                : "border-slate-300 focus:border-blue-500"
            }`}
          >
            <option value="">Select branch</option>
            {BRANCHES.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
          {formErrors.branch && (
            <p className="mt-1 text-xs text-red-600">{formErrors.branch}</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={onSave}
            disabled={isSaving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSaving
              ? "Saving..."
              : editingId
                ? "Update Incident"
                : "Create Incident"}
          </button>
          <button
            onClick={onCancel}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}