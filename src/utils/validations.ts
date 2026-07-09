import { Claim, ClaimStatus, Clinician } from "../types/models";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

const HC_PATIENT_ID_REGEX = /^HC-[A-Za-z0-9]{6}$/;
const CLAIM_ID_REGEX = /^CLM-\d{6}$/;
const CLINICIAN_ID_REGEX = /^CLN-\d{6}$/;
const ISO_DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const CLINICIAN_ROLES = new Set(["physician", "nurse_practitioner", "nurse", "medical_assistant"]);

const isValidIsoDate = (value: string): boolean => {
  if (!ISO_DATE_REGEX.test(value)) {
    return false;
  }

  const date = new Date(value);
  return !Number.isNaN(date.getTime());
};

const isFutureDate = (value: string): boolean => {
  const date = new Date(value);
  const today = new Date();
  today.setHours(23, 59, 59, 999);
  return date > today;
};

const hasDeniedStatus = (status: ClaimStatus): boolean => status === "denied";

export const validateClaim = (claim: Claim, knownLocationIds: string[]): ValidationResult => {
  const errors: string[] = [];

  if (!CLAIM_ID_REGEX.test(claim.claimId)) {
    errors.push("claimId must follow the format CLM-XXXXXX.");
  }

  if (!HC_PATIENT_ID_REGEX.test(claim.patientId)) {
    errors.push("patientId must follow the format HC- followed by 6 alphanumeric characters.");
  }

  if (!knownLocationIds.includes(claim.locationId)) {
    errors.push("locationId is not recognized as a known clinic location.");
  }

  if (claim.claimAmount <= 0) {
    errors.push("claimAmount must be greater than 0.");
  }

  if (!isValidIsoDate(claim.submissionDate)) {
    errors.push("submissionDate must be a valid ISO 8601 date string.");
  } else if (isFutureDate(claim.submissionDate)) {
    errors.push("submissionDate cannot be a future date.");
  }

  if (hasDeniedStatus(claim.status) && !claim.denialReason) {
    errors.push("denialReason is required when status is denied.");
  }

  return {
    valid: errors.length === 0,
    errors,
  };
};

export const validateClinician = (clinician: Clinician): ValidationResult => {
  const errors: string[] = [];

  if (!CLINICIAN_ID_REGEX.test(clinician.clinicianId)) {
    errors.push("clinicianId must follow the format CLN-XXXXXX.");
  }

  if (!CLINICIAN_ROLES.has(clinician.role)) {
    errors.push("role must be one of: physician, nurse_practitioner, nurse, medical_assistant.");
  }

  if (clinician.cmeHoursRequired < 0) {
    errors.push("cmeHoursRequired must be greater than or equal to 0.");
  }

  if (clinician.cmeHoursLogged < 0) {
    errors.push("cmeHoursLogged must be greater than or equal to 0.");
  }

  if (!isValidIsoDate(clinician.licenceExpiryDate)) {
    errors.push("licenceExpiryDate must be a valid ISO 8601 date string.");
  }

  if (!isValidIsoDate(clinician.cmeYearStartDate)) {
    errors.push("cmeYearStartDate must be a valid ISO 8601 date string.");
  }

  return {
    valid: errors.length === 0,
    errors,
  };
};

export const isDenialRateAboveThreshold = (rate: number, threshold: number = 8): boolean => {
  return rate > threshold;
};

export const isNoShowRateAboveThreshold = (rate: number, threshold: number = 20): boolean => {
  return rate > threshold;
};
