export const SUPPLIER_COUNTRIES = ["USA", "UK"] as const;
export type SupplierCountry = (typeof SUPPLIER_COUNTRIES)[number];

export const SUPPLIER_CURRENCIES = ["USD", "GBP"] as const;
export type SupplierCurrency = (typeof SUPPLIER_CURRENCIES)[number];

export const SUPPLIER_STATUSES = ["active", "suspended"] as const;
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number];

export const SUPPLIER_CATEGORIES = [
  "medical_supplies",
  "laboratory_services",
  "pharmaceutical",
  "clinical_software",
  "it_infrastructure",
  "hr_and_payroll_software",
  "cleaning_and_facilities",
  "patient_communication",
  "billing_and_coding_software",
  "training_platforms",
] as const;
export type SupplierCategory = (typeof SUPPLIER_CATEGORIES)[number];

export const COMPLIANCE_AGREEMENTS = ["BAA", "DPA", "both"] as const;
export type ComplianceAgreement = (typeof COMPLIANCE_AGREEMENTS)[number];

export const CURRENCY_BY_COUNTRY: Record<SupplierCountry, SupplierCurrency> = {
  USA: "USD",
  UK: "GBP",
};

export interface Supplier {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: SupplierCurrency;
  updated_at: string;
  archived_at: string | null;
  status: SupplierStatus;
  compliance_agreement: ComplianceAgreement | null;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
}

export interface SupplierCreatePayload {
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: SupplierCurrency;
  status: SupplierStatus;
  compliance_agreement: ComplianceAgreement | null;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
}

export interface SupplierFilters {
  country?: SupplierCountry | "";
  category?: SupplierCategory | "";
}

export const CATEGORY_LABELS: Record<SupplierCategory, string> = {
  medical_supplies: "Medical supplies",
  laboratory_services: "Laboratory services",
  pharmaceutical: "Pharmaceutical",
  clinical_software: "Clinical software",
  it_infrastructure: "IT infrastructure",
  hr_and_payroll_software: "HR & payroll software",
  cleaning_and_facilities: "Cleaning & facilities",
  patient_communication: "Patient communication",
  billing_and_coding_software: "Billing & coding software",
  training_platforms: "Training platforms",
};
