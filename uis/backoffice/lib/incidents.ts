// ── Constantes compartidas del dominio Incident ─────────────────────────────

import type {
  IncidentStatus,
  IncidentCategory,
  IncidentOrigin,
} from "@/types/incident";

export const API_BASE =
  process.env.NEXT_PUBLIC_INCIDENTS_API_URL || "/api/incidents";

export const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

export const STATUS_COLORS: Record<IncidentStatus, string> = {
  open: "bg-yellow-100 text-yellow-800 border-yellow-300",
  in_progress: "bg-blue-100 text-blue-800 border-blue-300",
  resolved: "bg-green-100 text-green-800 border-green-300",
  discarded: "bg-slate-100 text-slate-600 border-slate-300",
};

export const STATUS_ORDER: IncidentStatus[] = [
  "open",
  "in_progress",
  "resolved",
  "discarded",
];

export const STATUS_OPTIONS: {
  value: IncidentStatus;
  transitions: IncidentStatus[];
}[] = [
  { value: "open", transitions: ["in_progress", "discarded"] },
  { value: "in_progress", transitions: ["resolved", "discarded"] },
  { value: "resolved", transitions: [] },
  { value: "discarded", transitions: [] },
];

export const CATEGORY_LABELS: Record<IncidentCategory, string> = {
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

export const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

export const BRANCH_LABELS: Record<string, string> = {
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

/** Array de { value, label } para usar en <select> */
export const BRANCH_OPTIONS = Object.entries(BRANCH_LABELS).map(
  ([value, label]) => ({ value, label })
);

export const ALL_STATUSES: IncidentStatus[] = [
  "open",
  "in_progress",
  "resolved",
  "discarded",
];

export const ALL_CATEGORIES: IncidentCategory[] = [
  "clinical_equipment",
  "it_system",
  "billing_error",
  "compliance_breach",
  "patient_experience",
  "staff_issue",
  "facility_issue",
  "referral_issue",
  "other",
];

export const ALL_ORIGINS: IncidentOrigin[] = ["customer", "branch", "internal"];

export const ALL_BRANCHES = Object.keys(BRANCH_LABELS);

/** Valor inicial del formulario de incidentes */
export const EMPTY_FORM = {
  title: "",
  description: "",
  category: "" as const,
  status: "open" as const,
  origin: "customer" as const,
  branch: "",
};