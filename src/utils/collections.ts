import { Appointment, AppointmentStatus, Claim } from "../types/models";

export const filterClaims = (
  claims: Claim[],
  filters: Partial<Pick<Claim, "locationId" | "status" | "payerName" | "serviceType">>,
): Claim[] => {
  if (claims.length === 0) {
    return [];
  }

  return claims.filter((claim: Claim) => {
    const locationMatches = filters.locationId === undefined || claim.locationId === filters.locationId;
    const statusMatches = filters.status === undefined || claim.status === filters.status;
    const payerMatches = filters.payerName === undefined || claim.payerName === filters.payerName;
    const serviceMatches = filters.serviceType === undefined || claim.serviceType === filters.serviceType;

    return locationMatches && statusMatches && payerMatches && serviceMatches;
  });
};

export const filterAppointmentsByStatus = (
  appointments: Appointment[],
  statuses: AppointmentStatus[],
): Appointment[] => {
  if (appointments.length === 0 || statuses.length === 0) {
    return [];
  }

  return appointments.filter((appointment: Appointment) => statuses.includes(appointment.status));
};

export const sortClaimsById = (claims: Claim[], direction: "asc" | "desc"): Claim[] => {
  const sortedClaims: Claim[] = [...claims].sort((left: Claim, right: Claim) =>
    left.claimId.localeCompare(right.claimId),
  );

  return direction === "asc" ? sortedClaims : sortedClaims.reverse();
};

export const sortAppointmentsByDate = (
  appointments: Appointment[],
  direction: "asc" | "desc",
): Appointment[] => {
  const sortedAppointments: Appointment[] = [...appointments].sort(
    (left: Appointment, right: Appointment) =>
      new Date(left.scheduledDate).getTime() - new Date(right.scheduledDate).getTime(),
  );

  return direction === "asc" ? sortedAppointments : sortedAppointments.reverse();
};

export const groupClaimsBy = (
  claims: Claim[],
  key: "locationId" | "payerName" | "status" | "serviceType",
): Record<string, Claim[]> => {
  return claims.reduce<Record<string, Claim[]>>((groups: Record<string, Claim[]>, claim: Claim) => {
    const groupKey = claim[key];
    const currentGroup: Claim[] = groups[groupKey] ?? [];
    groups[groupKey] = [...currentGroup, claim];
    return groups;
  }, {});
};
