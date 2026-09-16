import { filterClaims, filterAppointmentsByStatus, sortClaimsById, sortAppointmentsByDate, groupClaimsBy } from "../utils/collections";
import { Claim, Appointment } from "../types/models";

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
    status: "submitted",
    resubmitted: false,
  },
];

const sampleAppointments: Appointment[] = [
  {
    appointmentId: "APT-001",
    patientId: "HC-A1B2C3",
    locationId: "us-tx-001",
    serviceType: "primary_care",
    scheduledDate: "2024-01-20",
    scheduledTime: "09:00",
    status: "confirmed",
  },
  {
    appointmentId: "APT-002",
    patientId: "HC-D4E5F6",
    locationId: "us-fl-001",
    serviceType: "specialist",
    scheduledDate: "2024-02-25",
    scheduledTime: "14:30",
    status: "no_show",
  },
  {
    appointmentId: "APT-003",
    patientId: "HC-G7H8I9",
    locationId: "us-tx-001",
    serviceType: "preventive",
    scheduledDate: "2024-03-15",
    scheduledTime: "11:00",
    status: "completed",
  },
];

// ---------------------------------------------------------------------------
// filterClaims
// ---------------------------------------------------------------------------

describe("filterClaims", () => {
  it("filtra por locationId", () => {
    const result = filterClaims(sampleClaims, { locationId: "us-fl-001" });
    expect(result).toHaveLength(1);
    expect(result[0].claimId).toBe("CLM-000002");
  });

  it("filtra por status", () => {
    const result = filterClaims(sampleClaims, { status: "approved" });
    expect(result).toHaveLength(1);
    expect(result[0].claimId).toBe("CLM-000001");
  });

  it("filtra por payerName", () => {
    const result = filterClaims(sampleClaims, { payerName: "Aetna" });
    expect(result).toHaveLength(2);
  });

  it("filtra por múltiples criterios", () => {
    const result = filterClaims(sampleClaims, { locationId: "us-tx-001", payerName: "Aetna" });
    expect(result).toHaveLength(2);
  });

  it("devuelve array vacío si no hay coincidencias", () => {
    const result = filterClaims(sampleClaims, { payerName: "Unknown" });
    expect(result).toEqual([]);
  });

  it("devuelve array vacío si el array de entrada está vacío", () => {
    const result = filterClaims([], { locationId: "us-tx-001" });
    expect(result).toEqual([]);
  });

  it("devuelve todo si no hay filtros", () => {
    const result = filterClaims(sampleClaims, {});
    expect(result).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// filterAppointmentsByStatus
// ---------------------------------------------------------------------------

describe("filterAppointmentsByStatus", () => {
  it("filtra por un único estado", () => {
    const result = filterAppointmentsByStatus(sampleAppointments, ["no_show"]);
    expect(result).toHaveLength(1);
    expect(result[0].appointmentId).toBe("APT-002");
  });

  it("filtra por múltiples estados", () => {
    const result = filterAppointmentsByStatus(sampleAppointments, ["confirmed", "completed"]);
    expect(result).toHaveLength(2);
  });

  it("devuelve vacío si el array de citas está vacío", () => {
    const result = filterAppointmentsByStatus([], ["confirmed"]);
    expect(result).toEqual([]);
  });

  it("devuelve vacío si el array de estados está vacío", () => {
    const result = filterAppointmentsByStatus(sampleAppointments, []);
    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// sortClaimsById
// ---------------------------------------------------------------------------

describe("sortClaimsById", () => {
  it("ordena ascendente por defecto", () => {
    const result = sortClaimsById(sampleClaims, "asc");
    expect(result[0].claimId).toBe("CLM-000001");
    expect(result[2].claimId).toBe("CLM-000003");
  });

  it("ordena descendente", () => {
    const result = sortClaimsById(sampleClaims, "desc");
    expect(result[0].claimId).toBe("CLM-000003");
    expect(result[2].claimId).toBe("CLM-000001");
  });

  it("no muta el array original", () => {
    const copy = [...sampleClaims];
    sortClaimsById(sampleClaims, "desc");
    expect(sampleClaims).toEqual(copy);
  });
});

// ---------------------------------------------------------------------------
// sortAppointmentsByDate
// ---------------------------------------------------------------------------

describe("sortAppointmentsByDate", () => {
  it("ordena ascendente por scheduledDate", () => {
    const result = sortAppointmentsByDate(sampleAppointments, "asc");
    expect(result[0].scheduledDate).toBe("2024-01-20");
    expect(result[2].scheduledDate).toBe("2024-03-15");
  });

  it("ordena descendente", () => {
    const result = sortAppointmentsByDate(sampleAppointments, "desc");
    expect(result[0].scheduledDate).toBe("2024-03-15");
    expect(result[2].scheduledDate).toBe("2024-01-20");
  });
});

// ---------------------------------------------------------------------------
// groupClaimsBy
// ---------------------------------------------------------------------------

describe("groupClaimsBy", () => {
  it("agrupa por payerName", () => {
    const result = groupClaimsBy(sampleClaims, "payerName");
    expect(Object.keys(result)).toHaveLength(2);
    expect(result["Aetna"]).toHaveLength(2);
    expect(result["BlueCross"]).toHaveLength(1);
  });

  it("agrupa por locationId", () => {
    const result = groupClaimsBy(sampleClaims, "locationId");
    expect(result["us-tx-001"]).toHaveLength(2);
    expect(result["us-fl-001"]).toHaveLength(1);
  });

  it("agrupa por status", () => {
    const result = groupClaimsBy(sampleClaims, "status");
    expect(Object.keys(result)).toHaveLength(3);
  });
});