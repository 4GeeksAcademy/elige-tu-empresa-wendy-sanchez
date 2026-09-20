"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import {
  fetchProducts,
  getStockLevelColor,
  getStockLevelLabel,
  type MedicalSupply,
} from "@/lib/inventoryApi";

// ── Mapa de categorías para etiquetas legibles ────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  ppe: "EPI",
  wound_care: "Cura de heridas",
  diagnostics: "Diagnóstico",
  medications: "Medicamentos",
  consumables: "Consumibles",
};

const UNIT_LABELS: Record<string, string> = {
  box: "caja",
  unit: "unidad",
  pack: "pack",
  vial: "vial",
};

export default function InventoryProductsPage() {
  const { user } = useAuth();
  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProducts();
      setSupplies(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadProducts();
    }
  }, [user, loadProducts]);

  if (!user) return null;

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-600 border-t-transparent" />
          <p className="ml-3 text-sm text-slate-500">Cargando suministros...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Error al cargar el inventario</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Encabezado */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Inventario de suministros</h2>
            <p className="mt-1 text-sm text-slate-600">
              Stock actual de todos los suministros médicos en la red HealthCore.
              El stock se calcula automáticamente como la diferencia entre entradas y salidas.
            </p>
          </div>
        </div>
      </section>

      {/* Tabla de productos */}
      <section className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Suministro
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  SKU
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Categoría
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Unidad
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  País
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Stock actual
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {supplies.map((supply) => {
                const stockColor = getStockLevelColor(supply.current_stock);
                const stockLabel = getStockLevelLabel(supply.current_stock);
                const catLabel = CATEGORY_LABELS[supply.category] ?? supply.category;
                const unitLabel = UNIT_LABELS[supply.unit] ?? supply.unit;

                return (
                  <tr key={supply.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-slate-900">{supply.name}</p>
                    </td>
                    <td className="px-4 py-3">
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-600">
                        {supply.sku}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-slate-600">{catLabel}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-slate-600">{unitLabel}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-slate-600">{supply.country}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${stockColor}`}
                      >
                        {supply.current_stock}
                        <span className="font-normal opacity-70">{unitLabel}</span>
                      </span>
                      <p className="mt-0.5 text-[11px] text-slate-400">{stockLabel}</p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex gap-1">
                        <Link
                          href={`/inventory/orders/inbound?supply_id=${supply.id}`}
                          className="rounded-md bg-sky-50 px-2.5 py-1.5 text-xs font-medium text-sky-700 hover:bg-sky-100 border border-sky-200"
                        >
                          + Entrada
                        </Link>
                        <Link
                          href={`/inventory/orders/outbound?supply_id=${supply.id}`}
                          className="rounded-md bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 border border-amber-200"
                        >
                          - Salida
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {supplies.length === 0 && (
          <div className="px-4 py-12 text-center">
            <p className="text-sm text-slate-500">No hay suministros registrados.</p>
          </div>
        )}
      </section>
    </main>
  );
}