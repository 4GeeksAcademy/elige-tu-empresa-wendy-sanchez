// ── Tipos del dominio Incident ───────────────────────────────────────────────

export type IncidentStatus = "open" | "in_progress" | "resolved" | "discarded";
export type IncidentCategory =
  | "clinical_equipment" | "it_system" | "billing_error"
  | "compliance_breach" | "patient_experience" | "staff_issue"
  | "facility_issue" | "referral_issue" | "other";
export type IncidentOrigin = "customer" | "branch" | "internal";

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
  branch_label: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentSummary {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_branch: Record<string, number>;
  by_origin: Record<string, number>;
}

export interface IncidentFormState {
  title: string;
  description: string;
  category: IncidentCategory | "";
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
}