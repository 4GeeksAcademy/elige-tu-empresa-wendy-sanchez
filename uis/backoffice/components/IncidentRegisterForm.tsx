"use client";

import { useState, useCallback } from "react";

// ── Types ───────────────────────────────────────────────────────────────────

type IncidentStatus = "open" | "in_progress" | "resolved" | "discarded";
type IncidentCategory =
  | "clinical_equipment" | "it_system" | "billing_error"
  | "compliance_breach" | "patient_experience" | "staff_issue"
  | "facility_issue" | "referral_issue" | "other";
type IncidentOrigin = "customer" | "branch" | "internal";

const CATEGORY_LABELS: Record<IncidentCategory, string> = {
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

const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

const BRANCHES = [
  { value: "central", label: "Central — Austin Main Clinic" },
  { value: "austin_north", label: "Austin — North" },
  { value: "dallas_uptown", label: "Dallas Uptown" },
  { value: "houston_med_center", label: "Houston Medical Center" },
  { value: "san_antonio_west", label: "San Antonio West" },
  { value: "miami_brickell", label: "Miami Brickell" },
  { value: "miami_doral", label: "Miami Doral" },
  { value: "orlando_east", label: "Orlando East" },
  { value: "tampa_bay", label: "Tampa Bay" },
  { value: "atlanta_midtown", label: "Atlanta Midtown" },
  { value: "savannah", label: "Savannah" },
  { value: "london_city", label: "London City" },
  { value: "london_west", label: "London West End" },
  { value: "manchester_central", label: "Manchester Central" },
];

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as IncidentCategory[];
const ALL_ORIGINS = Object.keys(ORIGIN_LABELS) as IncidentOrigin[];
const ALL_STATUSES = Object.keys(STATUS_LABELS) as IncidentStatus[];

const API_BASE = process.env.NEXT_PUBLIC_INCIDENTS_API_URL || "/api/incidents";

// ── Form state ───────────────────────────────────────────────────────────────

interface FormState {
  title: string;
  description: string;
  category: IncidentCategory | "";
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
}

const EMPTY_FORM: FormState = {
  title: "",
  description: "",
  category: "",
  status: "open",
  origin: "customer",
  branch: "",
};

// ── Field errors ────────────────────────────────────────────────────────────

interface FieldError {
  field: string;
  message: string;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function IncidentRegisterForm() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── Client-side validation ─────────────────────────────────────────────────

  const validate = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    const t = form.title.trim();
    if (t.length < 2) errors.title = "Title must be at least 2 characters.";
    if (t.length > 200) errors.title = "Title must not exceed 200 characters.";
    const d = form.description.trim();
    if (d.length < 10) errors.description = "Description must be at least 10 characters.";
    if (d.length > 2000) errors.description = "Description must not exceed 2000 characters.";
    if (!form.category) errors.category = "Please select a category.";
    if (!form.branch) errors.branch = "Please select a branch.";
    return errors;
  };

  // ── Submit handler ────────────────────────────────────────────────────────

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setServerError(null);
      setSuccessMessage(null);

      const clientErrors = validate();
      setFieldErrors(clientErrors);
      if (Object.keys(clientErrors).length > 0) return;

      setIsSubmitting(true);

      try {
        const res = await fetch(API_BASE, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => null);
          // Handle structured validation errors from API
          const details: FieldError[] = body?.detail;
          if (Array.isArray(details)) {
            const mapped: Record<string, string> = {};
            for (const d of details) {
              if (d.field && d.message) {
                mapped[d.field] = d.message;
              }
            }
            if (Object.keys(mapped).length > 0) {
              setFieldErrors(mapped);
              return;
            }
          }
          // Fallback generic error
          const genericMsg =
            res.status === 422
              ? "Some fields are invalid. Please check the form and try again."
              : res.status === 400
                ? "Invalid request. Please check the data and try again."
                : "Something went wrong. Please try again later.";
          setServerError(genericMsg);
          return;
        }

        // Success
        setForm(EMPTY_FORM);
        setFieldErrors({});
        setSuccessMessage("Incident registered successfully.");
      } catch {
        setServerError("Error de conexión. Inténtalo de nuevo más tarde.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [form],
  );

  // ── Helpers ───────────────────────────────────────────────────────────────

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Clear field error on change
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const copy = { ...prev };
        delete copy[key];
        return copy;
      });
    }
  };

  const isBranchOrigin = form.origin === "branch";

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Register Incident</h1>
        <p className="mt-1 text-sm text-slate-500">
          Submit a new incident to the centralized registry.
        </p>
      </div>

      {/* Success banner */}
      {successMessage && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span className="text-lg">&#10003;</span>
          <span>{successMessage}</span>
          <button
            onClick={() => setSuccessMessage(null)}
            className="ml-auto font-bold hover:text-emerald-600"
          >
            &times;
          </button>
        </div>
      )}

      {/* Server error banner */}
      {serverError && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span className="font-bold">Error:</span> {serverError}
          <button
            onClick={() => setServerError(null)}
            className="ml-2 font-bold hover:text-red-600"
          >
            &times;
          </button>
        </div>
      )}

      {/* Compliance warning */}
      <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
        <strong>&#9888; Important:</strong> Do not include any patient-identifiable
        information (name, date of birth, medical record number, contact details).
        This system must comply with HIPAA and UK GDPR regulations.
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {/* ── Title ── */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-700">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            id="title"
            type="text"
            value={form.title}
            onChange={(e) => updateField("title", e.target.value)}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              fieldErrors.title
                ? "border-red-400 focus:border-red-500"
                : "border-slate-300 focus:border-blue-500"
            }`}
            placeholder="Brief title of the incident"
            maxLength={200}
          />
          {fieldErrors.title && (
            <p className="mt-1 text-xs text-red-600">{fieldErrors.title}</p>
          )}
        </div>

        {/* ── Description ── */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700">
            Description <span className="text-red-500">*</span>
          </label>
          <textarea
            id="description"
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            rows={5}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              fieldErrors.description
                ? "border-red-400 focus:border-red-500"
                : "border-slate-300 focus:border-blue-500"
            }`}
            placeholder="Detailed description — no patient data"
            maxLength={2000}
          />
          <div className="mt-1 flex justify-between">
            {fieldErrors.description ? (
              <p className="text-xs text-red-600">{fieldErrors.description}</p>
            ) : (
              <span />
            )}
            <span className="text-xs text-slate-400">{form.description.length}/2000</span>
          </div>
        </div>

        {/* ── Category + Origin ── */}
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-slate-700">
              Category <span className="text-red-500">*</span>
            </label>
            <select
              id="category"
              value={form.category}
              onChange={(e) =>
                updateField("category", e.target.value as IncidentCategory)
              }
              className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
                fieldErrors.category
                  ? "border-red-400 focus:border-red-500"
                  : "border-slate-300 focus:border-blue-500"
              }`}
            >
              <option value="">Select category</option>
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
            {fieldErrors.category && (
              <p className="mt-1 text-xs text-red-600">{fieldErrors.category}</p>
            )}
          </div>

          <div>
            <label htmlFor="origin" className="block text-sm font-medium text-slate-700">
              Origin <span className="text-red-500">*</span>
            </label>
            <select
              id="origin"
              value={form.origin}
              onChange={(e) =>
                updateField("origin", e.target.value as IncidentOrigin)
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              {ALL_ORIGINS.map((o) => (
                <option key={o} value={o}>
                  {ORIGIN_LABELS[o]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* ── Status ── */}
        <div>
          <label htmlFor="status" className="block text-sm font-medium text-slate-700">
            Initial Status
          </label>
          <select
            id="status"
            value={form.status}
            onChange={(e) => updateField("status", e.target.value as IncidentStatus)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </div>

        {/* ── Branch ── */}
        <div
          className={`rounded-xl border-2 p-4 transition-colors ${
            isBranchOrigin
              ? "border-blue-300 bg-blue-50/50"
              : "border-transparent bg-transparent"
          }`}
        >
          <label htmlFor="branch" className="block text-sm font-medium text-slate-700">
            Branch / Clinic <span className="text-red-500">*</span>
          </label>
          {isBranchOrigin && (
            <p className="mb-2 text-xs font-medium text-blue-700">
              &#9888; You are reporting from a specific branch. Confirm the location below.
            </p>
          )}
          <select
            id="branch"
            value={form.branch}
            onChange={(e) => updateField("branch", e.target.value)}
            className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${
              fieldErrors.branch
                ? "border-red-400 focus:border-red-500"
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
          {fieldErrors.branch && (
            <p className="mt-1 text-xs text-red-600">{fieldErrors.branch}</p>
          )}
        </div>

        {/* ── Submit ── */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting && (
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                />
              </svg>
            )}
            {isSubmitting ? "Submitting..." : "Register Incident"}
          </button>
          {isSubmitting && (
            <span className="text-xs text-slate-400">Please wait...</span>
          )}
        </div>
      </form>
    </div>
  );
}