"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import {
  fetchProducts,
  createInboundOrder,
  type MedicalSupply,
} from "@/lib/inventoryApi";
import { ApiError } from "@/lib/httpClient";

// ── Clínicas HealthCore ───────────────────────────────────────────────

const CLINICS = [
  { id: 1, name: "Austin Central", country: "US" },
  { id: 2, name: "Austin North", country: "US" },
  { id: 3, name: "Dallas", country: "US" },
  { id: 4, name: "Houston", country: "US" },
  { id: 5, name: "San Antonio", country: "US" },
  { id: 6, name: "Miami", country: "US" },
  { id: 7, name: "Orlando", country: "US" },
  { id: 8, name: "Atlanta Downtown", country: "US" },
  { id: 9, name: "Atlanta Perimeter", country: "US" },
  { id: 10, name: "London City", country: "UK" },
  { id: 11, name: "London North", country: "UK" },
  { id: 12, name: "Manchester", country: "UK" },
];

export default function InboundOrderPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const preselectedSupplyId = searchParams.get("supply_id");

  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [supplyId, setSupplyId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [vendorName, setVendorName] = useState<string>("");
  const [clinicId, setClinicId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingSupplies, setLoadingSupplies] = useState(true);

  // Cargar lista de suministros
  const loadSupplies = useCallback(async () => {
    setLoadingSupplies(true);
    try {
      const data = await fetchProducts();
      setSupplies(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al cargar suministros");
    } finally {
      setLoadingSupplies(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSupplies();
    }
  }, [user, loadSupplies]);

  // Pre-seleccionar suministro si viene por query param
  useEffect(() => {
    if (preselectedSupplyId && supplies.length > 0) {
      const exists = supplies.some((s) => s.id === Number(preselectedSupplyId));
      if (exists) {
        setSupplyId(preselectedSupplyId);
      }
    }
  }, [preselectedSupplyId, supplies]);

  if (!user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccess(null);
    setError(null);

    const supplyIdNum = Number(supplyId);
    const quantityNum = Number(quantity);
    const clinicIdNum = Number(clinicId);

    if (!supplyIdNum) {
      setError("Debes seleccionar un suministro.");
      return;
    }
    if (!quantityNum || quantityNum <= 0) {
      setError("La cantidad debe ser un número positivo.");
      return;
    }
    if (!vendorName.trim()) {
      setError("Debes indicar el nombre del proveedor.");
      return;
    }
    if (!clinicIdNum) {
      setError("Debes seleccionar una clínica.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createInboundOrder({
        supply_id: supplyIdNum,
        quantity: quantityNum,
        vendor_name: vendorName.trim(),
        clinic_id: clinicIdNum,
      });

      const supplyName = supplies.find((s) => s.id === supplyIdNum)?.name ?? `ID ${supplyIdNum}`;
      setSuccess(
        `Entrada registrada correctamente: ${quantityNum} unidades de "${supplyName}" (proveedor: ${result.vendor_name}, clínica #${result.clinic_id}).`,
      );
      // Limpiar formulario
      setQuantity("");
      setVendorName("");
      setClinicId("");
      setSupplyId("");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Error inesperado al registrar la orden.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Encabezado */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-slate-900">Registrar entrada de suministros</h2>
        <p className="mt-1 text-sm text-slate-600">
          Registra la recepción de un envío de proveedor en una clínica HealthCore.
          Cada entrada incrementa el stock del suministro seleccionado.
        </p>
      </section>

      {/* Feedback */}
      {success && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-800">✅ {success}</p>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Error</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Formulario */}
      <form
        onSubmit={handleSubmit}
        className="mt-6 space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        {/* Suministro */}
        <div>
          <label htmlFor="supply" className="block text-sm font-medium text-slate-700">
            Suministro *
          </label>
          {loadingSupplies ? (
            <p className="mt-1 text-sm text-slate-400">Cargando suministros...</p>
          ) : (
            <select
              id="supply"
              value={supplyId}
              onChange={(e) => setSupplyId(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-50"
              required
            >
              <option value="">— Selecciona un suministro —</option>
              {supplies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.sku})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Cantidad */}
        <div>
          <label htmlFor="quantity" className="block text-sm font-medium text-slate-700">
            Cantidad recibida *
          </label>
          <input
            id="quantity"
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            placeholder="Ej: 50"
            required
          />
        </div>

        {/* Proveedor */}
        <div>
          <label htmlFor="vendor" className="block text-sm font-medium text-slate-700">
            Nombre del proveedor *
          </label>
          <input
            id="vendor"
            type="text"
            value={vendorName}
            onChange={(e) => setVendorName(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            placeholder="Ej: MedLine Industries"
            required
          />
        </div>

        {/* Clínica */}
        <div>
          <label htmlFor="clinic" className="block text-sm font-medium text-slate-700">
            Clínica receptora *
          </label>
          <select
            id="clinic"
            value={clinicId}
            onChange={(e) => setClinicId(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            required
          >
            <option value="">— Selecciona una clínica —</option>
            {CLINICS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.country})
              </option>
            ))}
          </select>
        </div>

        {/* Botón */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={submitting || loadingSupplies}
            className="rounded-lg bg-sky-700 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Registrando..." : "Registrar entrada"}
          </button>
        </div>
      </form>
    </main>
  );
}