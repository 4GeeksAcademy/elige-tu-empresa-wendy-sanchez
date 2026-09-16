import { countByCategory, sumBy, averageBy, maxBy, minBy, calculateDenialRate, denialRateByPayer, denialRateByLocation, flagHighDenialPayers, calculateNoShowCost, noShowRateByLocation, flagHighNoShowLocations, generateCMEReport } from "../utils/transformations";
import { Claim, Appointment, Location, Clinician, CMEReport } from "../types/models";

// ---------------------------------------------------------------------------
// Datos de ejemplo
// ---------------------------------------------------------------------------

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
    claimId: "CLM-000003",
    patientId: "HC-G7H8I9",
    locationId: "us-tx-001",
    serviceType: "preventive",
    payerName: "Aetna",
    payerId: "PAY-001",
    submissionDate: "2024-03-10",
    claimAmount: 200,
    status: "denied",
    denialReason: "duplicate_claim",
    resubmitted: false,
  },
];

const sampleAppointments: Appointment[] = [
  {
    appointmentId: "APT-001",
    patientId: "HC-A1B2C3",
    locationId: "us-tx-001",
    serviceType: "primary_care",
    scheduledDate: "2024-01-18",
    scheduledTime: "09:00",
    status: "confirmed",
  },
  {
    appointmentId: "APT-002",
    patientId: "HC-D4E5F6",
    locationId: "us-tx-001",
    serviceType: "specialist",
    scheduledDate: "2024-01-19",
    scheduledTime: "14:30",
    status: "no_show",
  },
  {
    appointmentId: "APT-003",
    patientId: "HC-G7H8I9",
    locationId: "us-fl-001",
    serviceType: "preventive",
    scheduledDate: "2024-01-20",
    scheduledTime: "11:00",
    status: "no_show",
  },
  {
    appointmentId: "APT-004",
    patientId: "HC-A1B2C3",
    locationId: "us-tx-001",
    serviceType: "primary_care",
    scheduledDate: "2024-01-25",
    scheduledTime: "09:00",
    status: "no_show",
  },
];

const sampleLocation: Location = {
  locationId: "us-tx-001",
  name: "TX Clinic",
  city: "Austin",
  stateOrCountry: "TX",
  country: "US",
  phone: "+1-512-555-0100",
  averageConsultationFee: {
    primary_care: 100,
    specialist: 250,
    preventive: 75,
    chronic_disease: 120,
    womens_health: 130,
    paediatric: 90,
    mental_health: 150,
  },
};

const sampleClinicians: Clinician[] = [
  {
    clinicianId: "CLN-000001",
    firstName: "John",
    lastName: "Doe",
    role: "physician",
    locationId: "us-tx-001",
    licenceState: "TX",
    licenceExpiryDate: "2026-06-30",
    cmeHoursRequired: 50,
    cmeHoursLogged: 50,
    cmeYearStartDate: "2024-01-01",
  },
  {
    clinicianId: "CLN-000002",
    firstName: "Jane",
    lastName: "Smith",
    role: "nurse_practitioner",
    locationId: "us-fl-001",
    licenceState: "FL",
    licenceExpiryDate: "2025-03-15",
    cmeHoursRequired: 40,
    cmeHoursLogged: 25,
    cmeYearStartDate: "2024-01-01",
  },
];

// ---------------------------------------------------------------------------
// countByCategory
// ---------------------------------------------------------------------------

describe("countByCategory", () => {
  it("cuenta claims por status", () => {
    const result = countByCategory(sampleClaims, (c: Claim) => c.status);
    expect(result).toEqual({ approved: 1, denied: 2 });
  });

  it("devuelve vacío para array vacío", () => {
    const result = countByCategory([], (c: Claim) => c.status);
    expect(result).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// sumBy
// ---------------------------------------------------------------------------

describe("sumBy", () => {
  it("suma claimAmount", () => {
    const result = sumBy(sampleClaims, (c: Claim) => c.claimAmount);
    expect(result).toBe(700);
  });

  it("devuelve 0 para array vacío", () => {
    const result = sumBy([], (c: Claim) => c.claimAmount);
    expect(result).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// averageBy
// ---------------------------------------------------------------------------

describe("averageBy", () => {
  it("calcula el promedio de claimAmount", () => {
    const result = averageBy(sampleClaims, (c: Claim) => c.claimAmount);
    expect(result).toBe(233.33);
  });

  it("devuelve null para array vacío", () => {
    const result = averageBy([], (c: Claim) => c.claimAmount);
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// maxBy
// ---------------------------------------------------------------------------

describe("maxBy", () => {
  it("encuentra el claim de mayor monto", () => {
    const result = maxBy(sampleClaims, (c: Claim) => c.claimAmount);
    expect(result).not.toBeNull();
    expect(result!.claimAmount).toBe(350);
    expect(result!.claimId).toBe("CLM-000002");
  });

  it("devuelve null para array vacío", () => {
    const result = maxBy([], (c: Claim) => c.claimAmount);
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// minBy
// ---------------------------------------------------------------------------

describe("minBy", () => {
  it("encuentra el claim de menor monto", () => {
    const result = minBy(sampleClaims, (c: Claim) => c.claimAmount);
    expect(result).not.toBeNull();
    expect(result!.claimAmount).toBe(150);
    expect(result!.claimId).toBe("CLM-000001");
  });

  it("devuelve null para array vacío", () => {
    const result = minBy([], (c: Claim) => c.claimAmount);
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// calculateDenialRate
// ---------------------------------------------------------------------------

describe("calculateDenialRate", () => {
  it("calcula la tasa de denegación correctamente", () => {
    const result = calculateDenialRate(sampleClaims);
    expect(result).toBe(66.67);
  });

  it("lanza error para array vacío", () => {
    expect(() => calculateDenialRate([])).toThrow("Cannot calculate denial rate for an empty claims array.");
  });
});

// ---------------------------------------------------------------------------
// denialRateByPayer
// ---------------------------------------------------------------------------

describe("denialRateByPayer", () => {
  it("calcula tasa por pagador", () => {
    const result = denialRateByPayer(sampleClaims);
    expect(result["Aetna"]).toBe(50);   // 1 denied out of 2
    expect(result["BlueCross"]).toBe(100); // 1 denied out of 1
  });
});

// ---------------------------------------------------------------------------
// denialRateByLocation
// ---------------------------------------------------------------------------

describe("denialRateByLocation", () => {
  it("calcula tasa por ubicación", () => {
    const result = denialRateByLocation(sampleClaims);
    expect(result["us-tx-001"]).toBe(50);  // 1 denied out of 2
    expect(result["us-fl-001"]).toBe(100); // 1 denied out of 1
  });
});

// ---------------------------------------------------------------------------
// flagHighDenialPayers
// ---------------------------------------------------------------------------

describe("flagHighDenialPayers", () => {
  it("identifica pagadores con alta tasa de denegación (>8% por defecto)", () => {
    const result = flagHighDenialPayers(sampleClaims);
    expect(result).toContain("Aetna");
    expect(result).toContain("BlueCross");
  });

  it("usa el threshold proporcionado", () => {
    const result = flagHighDenialPayers(sampleClaims, 60);
    expect(result).toContain("BlueCross");
    expect(result).not.toContain("Aetna");
  });
});

// ---------------------------------------------------------------------------
// calculateNoShowCost
// ---------------------------------------------------------------------------

describe("calculateNoShowCost", () => {
  it("calcula el costo de no-show para una semana", () => {
    // Semana del 18 al 24 de enero de 2024 (viernes a jueves)
    // APT-002: no_show, us-tx-001, specialist → $250
    // APT-003: no_show, us-fl-001 → filtered out (different location)
    // APT-004: no_show, us-tx-001, but scheduled 2024-01-25 → outside week
    const result = calculateNoShowCost(sampleAppointments, sampleLocation, "2024-01-24");
    expect(result).toBe(250);
  });

  it("lanza error para fecha inválida", () => {
    expect(() => calculateNoShowCost(sampleAppointments, sampleLocation, "invalid-date")).toThrow(
      "Invalid weekEndingDate"
    );
  });
});

// ---------------------------------------------------------------------------
// noShowRateByLocation
// ---------------------------------------------------------------------------

describe("noShowRateByLocation", () => {
  it("calcula tasa de no-show por ubicación", () => {
    const result = noShowRateByLocation(sampleAppointments);
    expect(result["us-tx-001"]).toBeCloseTo(66.67, 1);  // 2 no-shows out of 3
    expect(result["us-fl-001"]).toBe(100);               // 1 no-show out of 1
  });
});

// ---------------------------------------------------------------------------
// flagHighNoShowLocations
// ---------------------------------------------------------------------------

describe("flagHighNoShowLocations", () => {
  it("identifica ubicaciones con alta tasa de no-show (>20% por defecto)", () => {
    const result = flagHighNoShowLocations(sampleAppointments);
    expect(result).toContain("us-tx-001");
    expect(result).toContain("us-fl-001");
  });

  it("usa el threshold proporcionado", () => {
    const result = flagHighNoShowLocations(sampleAppointments, 80);
    expect(result).not.toContain("us-tx-001");
    expect(result).toContain("us-fl-001");
  });
});

// ---------------------------------------------------------------------------
// generateCMEReport
// ---------------------------------------------------------------------------

describe("generateCMEReport", () => {
  it("genera reporte completo para todos los clínicos", () => {
    const asOfDate = "2024-06-30";
    const reports = generateCMEReport(sampleClinicians, asOfDate);
    expect(reports).toHaveLength(2);
  });

  it("marca como complete al clínico con horas requeridas cumplidas", () => {
    const asOfDate = "2024-06-30";
    const reports = generateCMEReport(sampleClinicians, asOfDate);
    const john = reports.find((r: CMEReport) => r.clinicianId === "CLN-000001");
    expect(john).toBeDefined();
    expect(john!.complianceStatus).toBe("complete");
  });

  it("asigna on_track cuando el clínico va al día", () => {
    const asOfDate = "2024-01-15";
    const reports = generateCMEReport(sampleClinicians, asOfDate);
    const jane = reports.find((r: CMEReport) => r.clinicianId === "CLN-000002");
    expect(jane).toBeDefined();
    expect(jane!.complianceStatus).toBe("on_track");
  });
});