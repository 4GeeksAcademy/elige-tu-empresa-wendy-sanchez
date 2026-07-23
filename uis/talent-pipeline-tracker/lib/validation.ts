import { CandidateCreatePayload, CandidateFormValues } from "@/types/candidate";

export type CandidateFormErrors = Partial<Record<keyof CandidateFormValues, string>>;

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function isValidUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateCandidateForm(values: CandidateFormValues): CandidateFormErrors {
  const errors: CandidateFormErrors = {};

  if (!values.full_name.trim()) {
    errors.full_name = "El nombre completo es obligatorio.";
  }

  if (!values.email.trim()) {
    errors.email = "El email es obligatorio.";
  } else if (!isValidEmail(values.email.trim())) {
    errors.email = "Ingresa un email valido.";
  }

  if (!values.phone.trim()) {
    errors.phone = "El telefono es obligatorio.";
  }

  if (!values.position.trim()) {
    errors.position = "El puesto es obligatorio.";
  }

  if (!values.experience_years.trim()) {
    errors.experience_years = "Los anos de experiencia son obligatorios.";
  } else {
    const years = Number(values.experience_years);
    if (Number.isNaN(years) || years < 0) {
      errors.experience_years = "Ingresa un numero valido mayor o igual a 0.";
    }
  }

  if (values.linkedin_url.trim() && !isValidUrl(values.linkedin_url.trim())) {
    errors.linkedin_url = "Ingresa una URL valida (http o https).";
  }

  if (values.cv_url.trim() && !isValidUrl(values.cv_url.trim())) {
    errors.cv_url = "Ingresa una URL valida (http o https).";
  }

  return errors;
}

export function toCandidatePayload(values: CandidateFormValues): CandidateCreatePayload {
  return {
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    phone: values.phone.trim(),
    position: values.position.trim(),
    linkedin_url: values.linkedin_url.trim() ? values.linkedin_url.trim() : null,
    cv_url: values.cv_url.trim() ? values.cv_url.trim() : null,
    experience_years: Number(values.experience_years),
  };
}

export function validateNoteContent(value: string): string | null {
  if (!value.trim()) {
    return "La nota no puede estar vacia.";
  }

  return null;
}
