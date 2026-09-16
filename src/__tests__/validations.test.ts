import { validateClaim, validateClinician, isDenialRateAboveThreshold, isNoShowRateAboveThreshold } from "../utils/validations";
import { Claim, Clinician } from "../types/models";

// ---------------------------------------------------------------------------
// Datos válidos de ejemplo
// ---------------------------------------------------------------------------

const validClaim: Claim = {
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
};

const validDeniedClaim: Claim = {
  ...validClaim,
  claimId: "CLM-000002",
  status: "denied",
  denialReason: "coding_error",
};

const validClinician: Clinician = {
  clinicianId: "CLN-000001",
  firstName: "John",
  lastName: "Doe",
  role: "physician",
  locationId: "us-tx-001",
  licenceState: "TX",
  licenceExpiryDate: "2026-06-30",
  cmeHoursRequired: 50,
  cmeHoursLogged: 30,
  cmeYearStartDate: "2024-01-01",
};

// ---------------------------------------------------------------------------
// validateClaim
// ---------------------------------------------------------------------------

describe("validateClaim", () => {
  const knownLocations = ["us-tx-001", "us-fl-001"];

  it("valida un claim correcto", () => {
    const result = validateClaim(validClaim, knownLocations);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("valida un claim denegado con denialReason", () => {
    const result = validateClaim(validDeniedClaim, knownLocations);
    expect(result.valid).toBe(true);
  });

  it("rechaza claimId con formato incorrecto", () => {
    const result = validateClaim({ ...validClaim, claimId: "12345" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("claimId must follow the format CLM-XXXXXX.");
  });

  it("rechaza patientId con formato incorrecto", () => {
    const result = validateClaim({ ...validClaim, patientId: "12345" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain(
      "patientId must follow the format HC- followed by 6 alphanumeric characters.",
    );
  });

  it("rechaza locationId desconocido", () => {
    const result = validateClaim({ ...validClaim, locationId: "unknown" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("locationId is not recognized as a known clinic location.");
  });

  it("rechaza claimAmount <= 0", () => {
    const result = validateClaim({ ...validClaim, claimAmount: 0 }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("claimAmount must be greater than 0.");
  });

  it("rechaza submissionDate inválida", () => {
    const result = validateClaim({ ...validClaim, submissionDate: "not-a-date" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("submissionDate must be a valid ISO 8601 date string.");
  });

  it("rechaza submissionDate futura", () => {
    const result = validateClaim({ ...validClaim, submissionDate: "2099-12-31" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("submissionDate cannot be a future date.");
  });

  it("rechaza claim denegado sin denialReason", () => {
    const result = validateClaim({ ...validClaim, status: "denied" }, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("denialReason is required when status is denied.");
  });

  it("acumula múltiples errores", () => {
    const badClaim: Claim = {
      ...validClaim,
      claimId: "bad",
      patientId: "bad",
      locationId: "nowhere",
      claimAmount: -10,
      submissionDate: "invalid",
    };
    const result = validateClaim(badClaim, knownLocations);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(4);
  });
});

// ---------------------------------------------------------------------------
// validateClinician
// ---------------------------------------------------------------------------

describe("validateClinician", () => {
  it("valida un clínico correcto", () => {
    const result = validateClinician(validClinician);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("rechaza clinicianId con formato incorrecto", () => {
    const result = validateClinician({ ...validClinician, clinicianId: "123" });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("clinicianId must follow the format CLN-XXXXXX.");
  });

  it("rechaza rol inválido", () => {
    const result = validateClinician({ ...validClinician, role: "surgeon" as any });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain(
      "role must be one of: physician, nurse_practitioner, nurse, medical_assistant.",
    );
  });

  it("rechaza cmeHoursRequired negativo", () => {
    const result = validateClinician({ ...validClinician, cmeHoursRequired: -1 });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("cmeHoursRequired must be greater than or equal to 0.");
  });

  it("rechaza cmeHoursLogged negativo", () => {
    const result = validateClinician({ ...validClinician, cmeHoursLogged: -5 });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("cmeHoursLogged must be greater than or equal to 0.");
  });

  it("rechaza licenceExpiryDate inválida", () => {
    const result = validateClinician({ ...validClinician, licenceExpiryDate: "bad-date" });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("licenceExpiryDate must be a valid ISO 8601 date string.");
  });

  it("rechaza cmeYearStartDate inválida", () => {
    const result = validateClinician({ ...validClinician, cmeYearStartDate: "bad-date" });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("cmeYearStartDate must be a valid ISO 8601 date string.");
  });

  it("acumula múltiples errores", () => {
    const badClinician: Clinician = {
      clinicianId: "bad",
      firstName: "John",
      lastName: "Doe",
      role: "unknown" as any,
      locationId: "us-tx-001",
      licenceState: "TX",
      licenceExpiryDate: "bad",
      cmeHoursRequired: -1,
      cmeHoursLogged: -1,
      cmeYearStartDate: "bad",
    };
    const result = validateClinician(badClinician);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThanOrEqual(5);
  });
});

// ---------------------------------------------------------------------------
// isDenialRateAboveThreshold
// ---------------------------------------------------------------------------

describe("isDenialRateAboveThreshold", () => {
  it("devuelve true si la tasa supera el threshold (8% por defecto)", () => {
    expect(isDenialRateAboveThreshold(9)).toBe(true);
  });

  it("devuelve false si la tasa está en el threshold", () => {
    expect(isDenialRateAboveThreshold(8)).toBe(false);
  });

  it("devuelve false si la tasa está por debajo", () => {
    expect(isDenialRateAboveThreshold(5)).toBe(false);
  });

  it("usa el threshold proporcionado", () => {
    expect(isDenialRateAboveThreshold(15, 10)).toBe(true);
    expect(isDenialRateAboveThreshold(10, 15)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isNoShowRateAboveThreshold
// ---------------------------------------------------------------------------

describe("isNoShowRateAboveThreshold", () => {
  it("devuelve true si la tasa supera el threshold (20% por defecto)", () => {
    expect(isNoShowRateAboveThreshold(21)).toBe(true);
  });

  it("devuelve false si la tasa está en el threshold", () => {
    expect(isNoShowRateAboveThreshold(20)).toBe(false);
  });

  it("usa el threshold proporcionado", () => {
    expect(isNoShowRateAboveThreshold(25, 30)).toBe(false);
    expect(isNoShowRateAboveThreshold(30, 25)).toBe(true);
  });
});