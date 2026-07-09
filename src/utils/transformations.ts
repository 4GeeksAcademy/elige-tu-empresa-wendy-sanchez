import {
  Appointment,
  CMEReport,
  CMEStatus,
  Claim,
  Clinician,
  Location,
} from "../types/models";
import { groupClaimsBy } from "./collections";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

const roundTo = (value: number, decimals: number): number => {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
};

const parseIsoDate = (value: string): Date | null => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const daysBetween = (start: Date, end: Date): number => {
  const utcStart = Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate());
  const utcEnd = Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate());
  return Math.floor((utcEnd - utcStart) / MS_PER_DAY);
};

const getDenialRate = (claims: Claim[]): number => {
  if (claims.length === 0) {
    return 0;
  }

  const deniedCount = claims.filter((claim: Claim) => claim.status === "denied").length;
  return roundTo((deniedCount / claims.length) * 100, 2);
};

export const countByCategory = <T>(items: T[], getCategory: (item: T) => string): Record<string, number> => {
  return items.reduce<Record<string, number>>((accumulator: Record<string, number>, item: T) => {
    const key = getCategory(item);
    accumulator[key] = (accumulator[key] ?? 0) + 1;
    return accumulator;
  }, {});
};

export const sumBy = <T>(items: T[], getValue: (item: T) => number): number => {
  return items.reduce((total: number, item: T) => total + getValue(item), 0);
};

export const averageBy = <T>(items: T[], getValue: (item: T) => number): number | null => {
  if (items.length === 0) {
    return null;
  }

  return roundTo(sumBy(items, getValue) / items.length, 2);
};

export const maxBy = <T>(items: T[], getValue: (item: T) => number): T | null => {
  if (items.length === 0) {
    return null;
  }

  return items.reduce((maxItem: T, currentItem: T) =>
    getValue(currentItem) > getValue(maxItem) ? currentItem : maxItem,
  );
};

export const minBy = <T>(items: T[], getValue: (item: T) => number): T | null => {
  if (items.length === 0) {
    return null;
  }

  return items.reduce((minItem: T, currentItem: T) =>
    getValue(currentItem) < getValue(minItem) ? currentItem : minItem,
  );
};

export const calculateDenialRate = (claims: Claim[]): number => {
  if (claims.length === 0) {
    throw new Error("Cannot calculate denial rate for an empty claims array.");
  }

  return getDenialRate(claims);
};

export const denialRateByPayer = (claims: Claim[]): Record<string, number> => {
  const groupedByPayer = groupClaimsBy(claims, "payerName");

  return Object.entries(groupedByPayer).reduce<Record<string, number>>(
    (rates: Record<string, number>, [payerName, payerClaims]: [string, Claim[]]) => {
      rates[payerName] = getDenialRate(payerClaims);
      return rates;
    },
    {},
  );
};

export const denialRateByLocation = (claims: Claim[]): Record<string, number> => {
  const groupedByLocation = groupClaimsBy(claims, "locationId");

  return Object.entries(groupedByLocation).reduce<Record<string, number>>(
    (rates: Record<string, number>, [locationId, locationClaims]: [string, Claim[]]) => {
      rates[locationId] = getDenialRate(locationClaims);
      return rates;
    },
    {},
  );
};

export const flagHighDenialPayers = (claims: Claim[], threshold: number = 8): string[] => {
  const ratesByPayer = denialRateByPayer(claims);
  return Object.entries(ratesByPayer)
    .filter(([, rate]: [string, number]) => rate > threshold)
    .map(([payerName]: [string, number]) => payerName);
};

export const calculateNoShowCost = (
  appointments: Appointment[],
  location: Location,
  weekEndingDate: string,
): number => {
  const weekEnd = parseIsoDate(weekEndingDate);
  if (!weekEnd) {
    throw new Error("Invalid weekEndingDate. Expected an ISO date string.");
  }

  const weekStart = new Date(weekEnd);
  weekStart.setUTCDate(weekStart.getUTCDate() - 6);

  const lostRevenue = appointments
    .filter((appointment: Appointment) => appointment.locationId === location.locationId)
    .filter((appointment: Appointment) => appointment.status === "no_show")
    .filter((appointment: Appointment) => {
      const scheduled = parseIsoDate(appointment.scheduledDate);
      if (!scheduled) {
        return false;
      }

      return scheduled >= weekStart && scheduled <= weekEnd;
    })
    .reduce((total: number, appointment: Appointment) => {
      const estimatedFee = location.averageConsultationFee[appointment.serviceType] ?? 0;
      return total + estimatedFee;
    }, 0);

  return roundTo(lostRevenue, 2);
};

export const noShowRateByLocation = (appointments: Appointment[]): Record<string, number> => {
  const grouped = appointments.reduce<Record<string, Appointment[]>>(
    (accumulator: Record<string, Appointment[]>, appointment: Appointment) => {
      const key = appointment.locationId;
      const current = accumulator[key] ?? [];
      accumulator[key] = [...current, appointment];
      return accumulator;
    },
    {},
  );

  return Object.entries(grouped).reduce<Record<string, number>>(
    (rates: Record<string, number>, [locationId, locationAppointments]: [string, Appointment[]]) => {
      const noShows = locationAppointments.filter(
        (appointment: Appointment) => appointment.status === "no_show",
      ).length;
      rates[locationId] = roundTo((noShows / locationAppointments.length) * 100, 2);
      return rates;
    },
    {},
  );
};

export const flagHighNoShowLocations = (
  appointments: Appointment[],
  threshold: number = 20,
): string[] => {
  const ratesByLocation = noShowRateByLocation(appointments);
  return Object.entries(ratesByLocation)
    .filter(([, rate]: [string, number]) => rate > threshold)
    .map(([locationId]: [string, number]) => locationId);
};

const calculateCycleEndDate = (cmeYearStartDate: string): Date | null => {
  const cycleStart = parseIsoDate(cmeYearStartDate);
  if (!cycleStart) {
    return null;
  }

  const cycleEnd = new Date(cycleStart);
  cycleEnd.setUTCFullYear(cycleEnd.getUTCFullYear() + 1);
  cycleEnd.setUTCDate(cycleEnd.getUTCDate() - 1);
  return cycleEnd;
};

const calculateYearProgress = (cycleStart: Date, cycleEnd: Date, asOfDate: Date): number => {
  if (asOfDate <= cycleStart) {
    return 0;
  }

  if (asOfDate >= cycleEnd) {
    return 100;
  }

  const totalDays = Math.max(1, daysBetween(cycleStart, cycleEnd) + 1);
  const elapsedDays = Math.max(0, daysBetween(cycleStart, asOfDate) + 1);
  return roundTo((elapsedDays / totalDays) * 100, 1);
};

const resolveCmeStatus = (
  percentComplete: number,
  yearProgress: number,
  hoursLogged: number,
  hoursRequired: number,
  cycleEnded: boolean,
): CMEStatus => {
  if (hoursLogged >= hoursRequired) {
    return "complete";
  }

  if (cycleEnded && hoursLogged < hoursRequired) {
    return "overdue";
  }

  if (!cycleEnded && percentComplete + 15 < yearProgress) {
    return "at_risk";
  }

  return "on_track";
};

export const generateCMEReport = (clinicians: Clinician[], asOfDate: string): CMEReport[] => {
  const asOf = parseIsoDate(asOfDate);
  if (!asOf) {
    throw new Error("Invalid asOfDate. Expected an ISO date string.");
  }

  return clinicians.map((clinician: Clinician) => {
    const cycleStart = parseIsoDate(clinician.cmeYearStartDate);
    const cycleEnd = calculateCycleEndDate(clinician.cmeYearStartDate);
    const licenceExpiry = parseIsoDate(clinician.licenceExpiryDate);

    if (!cycleStart || !cycleEnd || !licenceExpiry) {
      throw new Error(`Invalid date data for clinician ${clinician.clinicianId}.`);
    }

    const hoursRemaining = Math.max(0, clinician.cmeHoursRequired - clinician.cmeHoursLogged);
    const percentComplete =
      clinician.cmeHoursRequired === 0
        ? 100
        : roundTo((clinician.cmeHoursLogged / clinician.cmeHoursRequired) * 100, 1);
    const daysRemainingInCycle = daysBetween(asOf, cycleEnd);
    const yearProgress = calculateYearProgress(cycleStart, cycleEnd, asOf);
    const complianceStatus = resolveCmeStatus(
      percentComplete,
      yearProgress,
      clinician.cmeHoursLogged,
      clinician.cmeHoursRequired,
      asOf > cycleEnd,
    );

    return {
      clinicianId: clinician.clinicianId,
      fullName: `${clinician.firstName} ${clinician.lastName}`,
      role: clinician.role,
      locationId: clinician.locationId,
      hoursRequired: clinician.cmeHoursRequired,
      hoursLogged: clinician.cmeHoursLogged,
      hoursRemaining,
      percentComplete,
      daysRemainingInCycle,
      complianceStatus,
      licenceExpiryDate: clinician.licenceExpiryDate,
      licenceDaysRemaining: daysBetween(asOf, licenceExpiry),
    };
  });
};

export const getCliniciansAtRisk = (clinicians: Clinician[], asOfDate: string): Clinician[] => {
  const report = generateCMEReport(clinicians, asOfDate);
  const atRiskIds = new Set(
    report
      .filter((entry: CMEReport) => entry.complianceStatus === "at_risk" || entry.complianceStatus === "overdue")
      .map((entry: CMEReport) => entry.clinicianId),
  );

  return clinicians.filter((clinician: Clinician) => atRiskIds.has(clinician.clinicianId));
};

export const getCliniciansWithExpiringLicences = (
  clinicians: Clinician[],
  asOfDate: string,
  daysThreshold: number = 90,
): Clinician[] => {
  const asOf = parseIsoDate(asOfDate);
  if (!asOf) {
    throw new Error("Invalid asOfDate. Expected an ISO date string.");
  }

  return clinicians.filter((clinician: Clinician) => {
    const expiry = parseIsoDate(clinician.licenceExpiryDate);
    if (!expiry) {
      return false;
    }

    const daysRemaining = daysBetween(asOf, expiry);
    return daysRemaining >= 0 && daysRemaining <= daysThreshold;
  });
};
