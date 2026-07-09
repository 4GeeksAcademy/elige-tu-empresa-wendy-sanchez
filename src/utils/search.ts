import { Claim, Clinician } from "../types/models";

export const findClaimById = (claims: Claim[], claimId: string): Claim | null => {
  for (const claim of claims) {
    if (claim.claimId === claimId) {
      return claim;
    }
  }

  return null;
};

export const findClinicianById = (
  clinicians: Clinician[],
  clinicianId: string,
): Clinician | null => {
  for (const clinician of clinicians) {
    if (clinician.clinicianId === clinicianId) {
      return clinician;
    }
  }

  return null;
};

export const binarySearchClaimById = (sortedClaims: Claim[], targetId: string): number => {
  if (sortedClaims.length === 0) {
    return -1;
  }

  let left = 0;
  let right = sortedClaims.length - 1;

  while (left <= right) {
    const middle = Math.floor((left + right) / 2);
    const middleId = sortedClaims[middle].claimId;
    const compareResult = middleId.localeCompare(targetId);

    if (compareResult === 0) {
      return middle;
    }

    if (compareResult < 0) {
      left = middle + 1;
    } else {
      right = middle - 1;
    }
  }

  return -1;
};
