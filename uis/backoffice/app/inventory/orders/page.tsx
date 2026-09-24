"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import {
  fetchOrders,
  type OrderListResponse,
  type OrderItem,
} from "@/lib/inventoryApi";

/** Traduce el tipo de orden a español legible */
function orderTypeLabel(type: string): string {
  switch (type) {
    case "delivery":
      return "Entrada (entrega)";
    case "consumption":
      return "Salida (consumo)";
    default:
      return type;
  }
}

/** Color de la fila según el tipo de orden */
function orderTypeColor(type: string): string {
  switch (type) {
    case "delivery":
      return "border-l-4 border-l-emerald-500";
    case "consumption":
      return "border-l-4 border-l-amber-500";
    default:
      return "border-l-4 border-l-slate-300";
  }
}

function orderTypeBadgeColor(type: string): string {
  switch (type) {
    case "delivery":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "consumption":
      return "bg-amber-100 text-amber-800 border-amber-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

/** Formato legible de fecha */
function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function OrdersHistoryPage() {
  const { user } = useAuth();
  const [data, setData] = useState<OrderListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchOrders();
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadOrders();
    }
  }, [user, loadOrders]);

  if (!user) return null;

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-600 border-t-transparent" />
          <p className="ml-3 text-sm text-slate-500">Cargando historial de órdenes...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Error al cargar el historial</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
        </div>
      </main>
    );
  }

  const orders = data?.orders ?? [];

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Encabezado */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Historial de órdenes</h2>
            <p className="mt-1 text-sm text-slate-600">
              Todas las entradas (entregas de proveedores) y salidas (consumos clínicos)
              registradas en el sistema. Vista de solo lectura.
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            {orders.length} órdenes
          </span>
        </div>
      </section>

      {/* Lista de órdenes */}
      <section className="mt-6 space-y-3">
        {orders.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
            <p className="text-sm text-slate-500">No hay órdenes registradas.</p>
          </div>
        )}

        {orders.map((order) => (
          <OrderCard key={`${order.type}-${order.id}`} order={order} />
        ))}
      </section>
    </main>
  );
}

function OrderCard({ order }: { order: OrderItem }) {
  const typeLabel = orderTypeLabel(order.type);
  const typeColor = orderTypeColor(order.type);
  const badgeColor = orderTypeBadgeColor(order.type);

  return (
    <article
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${typeColor}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Info principal */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeColor}`}
            >
              {typeLabel}
            </span>
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-500">
              #{order.type === "delivery" ? "DEL" : "CON"}-{order.id}
            </code>
          </div>

          <h3 className="mt-2 text-base font-semibold text-slate-900">
            {order.supply_name}
          </h3>

          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            <div>
              <span className="text-slate-500">SKU:</span>{" "}
              <code className="font-mono text-slate-700">{order.supply_sku}</code>
            </div>
            <div>
              <span className="text-slate-500">Cantidad:</span>{" "}
              <span className="font-medium text-slate-900">{order.quantity}</span>
            </div>
            <div>
              <span className="text-slate-500">Detalle:</span>{" "}
              <span className="text-slate-700">{order.detail}</span>
            </div>
            <div>
              <span className="text-slate-500">Clínica:</span>{" "}
              <span className="text-slate-700">#{order.clinic_id}</span>
            </div>
          </div>
        </div>

        {/* Meta (fecha, usuario) */}
        <div className="flex shrink-0 flex-col items-end gap-1 text-xs text-slate-400">
          <time dateTime={order.created_at}>{formatDate(order.created_at)}</time>
          <span>
            Creado por: <code className="font-mono text-slate-500">{order.user_uuid}</code>
          </span>
        </div>
      </div>
    </article>
  );
}