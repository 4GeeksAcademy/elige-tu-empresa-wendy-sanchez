"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import {
  fetchProducts,
  fetchProduct,
  createOutboundOrder,
  getStockLevel,
  getStockLevelLabel,
  getStockLevelColor,
  ApiError,
  type MedicalSupply,
} from "@/lib/inventoryApi";

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

const CONSUMPTION_TYPES = [
  { value: "clinical_use", label: "Uso clínico (consumido en atención al paciente)" },
  { value: "expiry_waste", label: "Caducado (desechado por vencimiento)" },
];

export default function OutboundOrderPage() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const preselectedSupplyId = searchParams.get("supply_id");

  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [selectedSupply, setSelectedSupply] = useState<MedicalSupply | null>(null);
  const [supplyId, setSupplyId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [consumptionType, setConsumptionType] = useState<string>("");
  const [clinicId, setClinicId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingSupplies, setLoadingSupplies] = useState(true);
  const [loadingStock, setLoadingStock] = useState(false);

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
      const found = supplies.find((s) => s.id === Number(preselectedSupplyId));
      if (found) {
        setSupplyId(preselectedSupplyId);
        setSelectedSupply(found);
      }
    }
  }, [preselectedSupplyId, supplies]);

  // Cuando cambia el suministro seleccionado, obtener su stock actualizado
  useEffect(() => {
    const id = Number(supplyId);
    if (!id) {
      setSelectedSupply(null);
      return;
    }

    // Buscar en la lista local primero (stock actualizado del listado)
    const local = supplies.find((s) => s.id === id);
    if (local) {
      setSelectedSupply(local);
    }

    // Luego obtener el stock fresco desde la API
    const loadStock = async () => {
      setLoadingStock(true);
      try {
        const fresh = await fetchProduct(id);
        setSelectedSupply(fresh);
      } catch {
        // Si falla, conservamos el local
      } finally {
        setLoadingStock(false);
      }
    };
    void loadStock();
  }, [supplyId, supplies]);

  if (!user) return null;

  // Validación cliente: cantidad > stock disponible
  const quantityNum = Number(quantity);
  const exceedsStock =
    selectedSupply !== null && quantityNum > 0 && quantityNum > selectedSupply.current_stock;

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
    if (!consumptionType) {
      setError("Debes seleccionar el tipo de consumo.");
      return;
    }
    if (!clinicIdNum) {
      setError("Debes seleccionar una clínica.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createOutboundOrder({
        supply_id: supplyIdNum,
        quantity: quantityNum,
        consumption_type: consumptionType,
        clinic_id: clinicIdNum,
      });

      const supplyName =
        selectedSupply?.name ?? supplies.find((s) => s.id === supplyIdNum)?.name ?? `ID ${supplyIdNum}`;
      const typeLabel =
        result.consumption_type === "clinical_use"
          ? "uso clínico"
          : "desecho por caducidad";
      setSuccess(
        `Salida registrada correctamente: ${quantityNum} unidades de "${supplyName}" (tipo: ${typeLabel}, clínica #${result.clinic_id}).`,
      );
      // Limpiar formulario
      setQuantity("");
      setConsumptionType("");
      setClinicId("");
      setSupplyId("");
      setSelectedSupply(null);
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
        <h2 className="text-2xl font-bold text-slate-900">Registrar salida de suministros</h2>
        <p className="mt-1 text-sm text-slate-600">
          Registra el consumo clínico o desecho de un suministro en una clínica HealthCore.
          Cada salida reduce el stock disponible.
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
                  {s.name} ({s.sku}) — Stock: {s.current_stock}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Stock disponible (reactivo) */}
        {selectedSupply && (
          <div className="rounded-lg border bg-slate-50 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">
                Stock disponible de <strong>{selectedSupply.name}</strong>
              </p>
              {loadingStock && (
                <span className="text-xs text-slate-400">Actualizando...</span>
              )}
            </div>
            <p
              className={`mt-1 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${getStockLevelColor(selectedSupply.current_stock)}`}
            >
              {selectedSupply.current_stock} unidades
              <span className="text-xs font-normal opacity-70">
                ({getStockLevelLabel(selectedSupply.current_stock)})
              </span>
            </p>
          </div>
        )}

        {/* Cantidad */}
        <div>
          <label htmlFor="quantity" className="block text-sm font-medium text-slate-700">
            Cantidad a retirar *
          </label>
          <input
            id="quantity"
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className={`mt-1 block w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-1 ${
              exceedsStock
                ? "border-red-400 focus:border-red-500 focus:ring-red-500"
                : "border-slate-300 focus:border-sky-500 focus:ring-sky-500"
            }`}
            placeholder="Ej: 10"
            required
          />
          {exceedsStock && (
            <p className="mt-1 text-xs text-red-600">
              ⚠️ La cantidad solicitada ({quantityNum}) supera el stock disponible (
              {selectedSupply?.current_stock}). La API rechazará esta operación.
            </p>
          )}
          {selectedSupply && quantityNum > 0 && !exceedsStock && (
            <p className="mt-1 text-xs text-emerald-600">
              ✓ Stock suficiente ({selectedSupply.current_stock} disponibles).
            </p>
          )}
        </div>

        {/* Tipo de consumo */}
        <div>
          <label htmlFor="consumptionType" className="block text-sm font-medium text-slate-700">
            Tipo de consumo *
          </label>
          <select
            id="consumptionType"
            value={consumptionType}
            onChange={(e) => setConsumptionType(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
            required
          >
            <option value="">— Selecciona un tipo —</option>
            {CONSUMPTION_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>
                {ct.label}
              </option>
            ))}
          </select>
        </div>

        {/* Clínica */}
        <div>
          <label htmlFor="clinic" className="block text-sm font-medium text-slate-700">
            Clínica donde ocurre el consumo *
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
        <div className="flex items-center justify-between pt-2">
          {exceedsStock && (
            <p className="text-xs text-amber-600">
              ⚠️ La cantidad supera el stock. Corrige antes de enviar.
            </p>
          )}
          <button
            type="submit"
            disabled={submitting || loadingSupplies || exceedsStock}
            className="rounded-lg bg-amber-700 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Registrando..." : "Registrar salida"}
          </button>
        </div>
      </form>
    </main>
  );
}