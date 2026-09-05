import type { Metadata } from "next";

import SuppliersDirectoryClient from "../../components/SuppliersDirectoryClient";
import { loadInitialSuppliers } from "../../lib/suppliersServer";

export const metadata: Metadata = {
  title: "Directorio de proveedores · HealthCore Backoffice",
  description:
    "Registro centralizado de proveedores clínicos, operacionales y tecnológicos de HealthCore.",
};

export const dynamic = "force-dynamic";

export default async function SuppliersPage() {
  const { suppliers, error } = await loadInitialSuppliers();

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-900">Directorio de proveedores</h2>
        <p className="mt-2 text-sm text-slate-600">
          Registro único de proveedores clínicos, operacionales y tecnológicos. Cada cambio de
          tarifa queda sellado con su fecha y hora para las auditorías de cumplimiento. Los
          proveedores nunca se eliminan: se suspenden, para conservar con qué proveedores se
          trabajó en cada período.
        </p>
      </section>

      <div className="mt-6">
        <SuppliersDirectoryClient initialSuppliers={suppliers} initialError={error} />
      </div>
    </main>
  );
}
