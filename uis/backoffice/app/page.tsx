import {
  sampleAppointments,
  sampleClaims,
  sampleClinicians,
  sampleLocations,
} from "../../../src/types/models";
import { sortClaimsById } from "../../../src/utils/collections";
import { binarySearchClaimById, findClaimById } from "../../../src/utils/search";
import {
  calculateDenialRate,
  calculateNoShowCost,
  denialRateByPayer,
  generateCMEReport,
  noShowRateByLocation,
} from "../../../src/utils/transformations";

const formatPercent = (value: number): string => `${value.toFixed(2)}%`;

export default function BackofficeHomePage() {
  const denialRate = calculateDenialRate(sampleClaims);
  const payerRates = denialRateByPayer(sampleClaims);
  const locationNoShowRates = noShowRateByLocation(sampleAppointments);

  const selectedLocation = sampleLocations[0];
  const weeklyNoShowCost = calculateNoShowCost(
    sampleAppointments,
    selectedLocation,
    "2025-03-14",
  );

  const sortedClaims = sortClaimsById(sampleClaims, "asc");
  const binaryIndex = binarySearchClaimById(sortedClaims, "CLM-000003");
  const linearClaim = findClaimById(sampleClaims, "CLM-000003");

  const cmeReport = generateCMEReport(sampleClinicians, "2025-06-01");

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-900">Welcome to HealthCore Backoffice</h2>
        <p className="mt-2 text-sm text-slate-600">
          This internal dashboard imports milestone 2 business logic directly from the monorepo
          and renders the computed output in the UI.
        </p>
      </section>

      <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Global denial rate</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{formatPercent(denialRate)}</p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">No-show cost (week)</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">${weeklyNoShowCost.toFixed(2)}</p>
          <p className="mt-1 text-xs text-slate-500">{selectedLocation.name}</p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Linear search</p>
          <p className="mt-2 text-sm font-medium text-slate-900">
            {linearClaim ? `Found claim ${linearClaim.claimId}` : "Claim not found"}
          </p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Binary search index</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{binaryIndex}</p>
        </article>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Denial rate by payer</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {Object.entries(payerRates).map(([payer, rate]) => (
              <li key={payer} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <span>{payer}</span>
                <span className="font-semibold">{formatPercent(rate)}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">No-show rate by location</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-700">
            {Object.entries(locationNoShowRates).map(([locationId, rate]) => (
              <li
                key={locationId}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <span>{locationId}</span>
                <span className="font-semibold">{formatPercent(rate)}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">CME compliance snapshot</h3>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th scope="col" className="px-3 py-2">Clinician</th>
                <th scope="col" className="px-3 py-2">Location</th>
                <th scope="col" className="px-3 py-2">Progress</th>
                <th scope="col" className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {cmeReport.map((entry) => (
                <tr key={entry.clinicianId}>
                  <td className="px-3 py-2 font-medium text-slate-900">{entry.fullName}</td>
                  <td className="px-3 py-2">{entry.locationId}</td>
                  <td className="px-3 py-2">{entry.percentComplete.toFixed(1)}%</td>
                  <td className="px-3 py-2 capitalize">{entry.complianceStatus.replace("_", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
