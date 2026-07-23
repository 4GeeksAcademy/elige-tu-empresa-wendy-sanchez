"use client";

import { FormEvent, useMemo, useState } from "react";
import { CandidateCreatePayload, CandidateFormValues } from "@/types/candidate";
import { CandidateFormErrors, toCandidatePayload, validateCandidateForm } from "@/lib/validation";

interface CandidateFormProps {
  title: string;
  submitLabel: string;
  initialValues?: CandidateFormValues;
  successMessage: string;
  onSubmit: (payload: CandidateCreatePayload) => Promise<void>;
}

const EMPTY_VALUES: CandidateFormValues = {
  full_name: "",
  email: "",
  phone: "",
  position: "",
  linkedin_url: "",
  cv_url: "",
  experience_years: "",
};

export default function CandidateForm({
  title,
  submitLabel,
  initialValues,
  successMessage,
  onSubmit,
}: CandidateFormProps) {
  const [values, setValues] = useState<CandidateFormValues>(initialValues ?? EMPTY_VALUES);
  const [errors, setErrors] = useState<CandidateFormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const isEditMode = useMemo(() => Boolean(initialValues), [initialValues]);

  function handleInputChange<K extends keyof CandidateFormValues>(field: K, value: CandidateFormValues[K]) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFormMessage(null);
    setFormError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationErrors = validateCandidateForm(values);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    try {
      setSubmitting(true);
      await onSubmit(toCandidatePayload(values));
      setFormMessage(successMessage);

      if (!isEditMode) {
        setValues(EMPTY_VALUES);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar la candidatura.";
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-sky-200 bg-white/80 p-5 shadow-sm">
      <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
      <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit} noValidate>
        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">Nombre completo *</span>
          <input
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.full_name}
            onChange={(event) => handleInputChange("full_name", event.target.value)}
            required
          />
          {errors.full_name ? <span className="text-sm text-red-700">{errors.full_name}</span> : null}
        </label>

        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">Email *</span>
          <input
            type="email"
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.email}
            onChange={(event) => handleInputChange("email", event.target.value)}
            required
          />
          {errors.email ? <span className="text-sm text-red-700">{errors.email}</span> : null}
        </label>

        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">Telefono *</span>
          <input
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.phone}
            onChange={(event) => handleInputChange("phone", event.target.value)}
            required
          />
          {errors.phone ? <span className="text-sm text-red-700">{errors.phone}</span> : null}
        </label>

        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">Puesto *</span>
          <input
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.position}
            onChange={(event) => handleInputChange("position", event.target.value)}
            required
          />
          {errors.position ? <span className="text-sm text-red-700">{errors.position}</span> : null}
        </label>

        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">LinkedIn</span>
          <input
            type="url"
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.linkedin_url}
            onChange={(event) => handleInputChange("linkedin_url", event.target.value)}
            placeholder="https://linkedin.com/in/..."
          />
          {errors.linkedin_url ? <span className="text-sm text-red-700">{errors.linkedin_url}</span> : null}
        </label>

        <label className="grid gap-1">
          <span className="text-sm font-medium text-slate-700">URL CV</span>
          <input
            type="url"
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.cv_url}
            onChange={(event) => handleInputChange("cv_url", event.target.value)}
            placeholder="https://..."
          />
          {errors.cv_url ? <span className="text-sm text-red-700">{errors.cv_url}</span> : null}
        </label>

        <label className="grid gap-1 md:col-span-2">
          <span className="text-sm font-medium text-slate-700">Anos de experiencia *</span>
          <input
            type="number"
            min={0}
            step="0.5"
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none ring-sky-500 focus:ring"
            value={values.experience_years}
            onChange={(event) => handleInputChange("experience_years", event.target.value)}
            required
          />
          {errors.experience_years ? (
            <span className="text-sm text-red-700">{errors.experience_years}</span>
          ) : null}
        </label>

        <div className="md:col-span-2 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Guardando..." : submitLabel}
          </button>

          {formMessage ? <p className="text-sm font-medium text-emerald-700">{formMessage}</p> : null}
          {formError ? <p className="text-sm font-medium text-red-700">{formError}</p> : null}
        </div>
      </form>
    </section>
  );
}
