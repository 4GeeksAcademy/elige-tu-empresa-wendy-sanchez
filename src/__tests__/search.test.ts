import { findClaimById, findClinicianById, binarySearchClaimById } from "../utils/search";
import { Claim, Clinician } from "../types/models";

const sampleClaims: Claim[] = [
  {
    claimId: "CLM-000001",
    patientId: "HC-A1B2C3",
    locationId: "us-tx-001",
    serviceType: "primary_care",
    payerName: "Aetna",
    payerId: "PAY-001",
    submissionDate: "2024-01-15",
    claimAmount: 150,
    status: "approved",
    resubmitted: false,
  },
  {
    claimId: "CLM-000002",
    patientId: "HC-D4E5F6",
    locationId: "us-fl-001",
    serviceType: "specialist",
    payerName: "BlueCross",
    payerId: "PAY-002",
    submissionDate: "2024-02-20",
    claimAmount: 350,
    status: "denied",
    denialReason: "coding_error",
    resubmitted: true,
  },
  {
    claimId: "CLM-000005",
    patientId: "HC-G7H8I9",
    locationId: "us-tx-001",
    serviceType: "preventive",
    payerName: "Aetna",
    payerId: "PAY-001",
    submissionDate: "2024-03-10",
    claimAmount: 200,
    status: "submitted",
    resubmitted: false,
  },
];

const sampleClinicians: Clinician[] = [
  {
    clinicianId: "CLN-000001",
    firstName: "John",
    lastName: "Doe",
    role: "physician",
    locationId: "us-tx-001",
    licenceState: "TX",
    licenceExpiryDate: "2025-06-30",
    cmeHoursRequired: 50,
    cmeHoursLogged: 40,
    cmeYearStartDate: "2024-01-01",
  },
  {
    clinicianId: "CLN-000002",
    firstName: "Jane",
    lastName: "Smith",
    role: "nurse_practitioner",
    locationId: "us-fl-001",
    licenceState: "FL",
    licenceExpiryDate: "2026-03-15",
    cmeHoursRequired: 40,
    cmeHoursLogged: 42,
    cmeYearStartDate: "2024-01-01",
  },
];

// ---------------------------------------------------------------------------
// findClaimById (lineal)
// ---------------------------------------------------------------------------

describe("findClaimById", () => {
  it("encuentra un claim existente", () => {
    const result = findClaimById(sampleClaims, "CLM-000002");
    expect(result).not.toBeNull();
    expect(result!.claimId).toBe("CLM-000002");
  });

  it("devuelve null si el claim no existe", () => {
    const result = findClaimById(sampleClaims, "CLM-999999");
    expect(result).toBeNull();
  });

  it("devuelve null para array vacío", () => {
    const result = findClaimById([], "CLM-000001");
    expect(result).toBeNull();
  });

  it("encuentra el primer elemento", () => {
    const result = findClaimById(sampleClaims, "CLM-000001");
    expect(result).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// findClinicianById
// ---------------------------------------------------------------------------

describe("findClinicianById", () => {
  it("encuentra un clínico existente", () => {
    const result = findClinicianById(sampleClinicians, "CLN-000001");
    expect(result).not.toBeNull();
    expect(result!.firstName).toBe("John");
  });

  it("devuelve null si el clínico no existe", () => {
    const result = findClinicianById(sampleClinicians, "CLN-999999");
    expect(result).toBeNull();
  });

  it("devuelve null para array vacío", () => {
    const result = findClinicianById([], "CLN-000001");
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// binarySearchClaimById (requiere array ordenado por claimId)
// ---------------------------------------------------------------------------

describe("binarySearchClaimById", () => {
  it("encuentra un claim en la primera posición", () => {
    const result = binarySearchClaimById(sampleClaims, "CLM-000001");
    expect(result).toBe(0);
  });

  it("encuentra un claim en una posición intermedia", () => {
    const result = binarySearchClaimById(sampleClaims, "CLM-000002");
    expect(result).toBe(1);
  });

  it("encuentra un claim en la última posición", () => {
    const result = binarySearchClaimById(sampleClaims, "CLM-000005");
    expect(result).toBe(2);
  });

  it("devuelve -1 si no encuentra el claim", () => {
    const result = binarySearchClaimById(sampleClaims, "CLM-999999");
    expect(result).toBe(-1);
  });

  it("devuelve -1 para array vacío", () => {
    const result = binarySearchClaimById([], "CLM-000001");
    expect(result).toBe(-1);
  });

  it("funciona con un solo elemento existente", () => {
    const result = binarySearchClaimById([sampleClaims[0]], "CLM-000001");
    expect(result).toBe(0);
  });

  it("funciona con un solo elemento inexistente", () => {
    const result = binarySearchClaimById([sampleClaims[0]], "CLM-999999");
    expect(result).toBe(-1);
  });
});