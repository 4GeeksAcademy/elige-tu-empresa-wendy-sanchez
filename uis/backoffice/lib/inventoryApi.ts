/** Cliente HTTP para la API de inventario de HealthCore.
 *
 * Centraliza todas las llamadas a los endpoints /inventory del backend.
 * Las peticiones se realizan a través del proxy de Next.js (/api/inventory/*)
 * configurado en next.config.ts para evitar problemas de CORS.
 *
 * Ningún componente debe llamar a fetch directamente.
 * Lee el token JWT de localStorage y lo incluye en cada petición.
 * Gestiona errores 4xx/5xx extrayendo el mensaje del cuerpo de la respuesta.
 */

import { getToken, removeToken } from "./auth";

// ── Tipos ─────────────────────────────────────────────────────────────

export interface MedicalSupply {
  id: number;
  name: string;
  sku: string;
  category: string;
  unit: string;
  country: string;
  current_stock: number;
}

export interface SupplyDeliveryCreate {
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
}

export interface SupplyDeliveryResponse {
  id: number;
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface SupplyConsumptionCreate {
  supply_id: number;
  quantity: number;
  consumption_type: string;
  clinic_id: number;
}

export interface SupplyConsumptionResponse {
  id: number;
  supply_id: number;
  quantity: number;
  consumption_type: string;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface OrderItem {
  id: number;
  type: string; // "delivery" | "consumption"
  supply_id: number;
  supply_name: string;
  supply_sku: string;
  quantity: number;
  detail: string; // vendor_name o consumption_type
  clinic_id: number;
  created_at: string;
  user_uuid: string;
}

export interface OrderListResponse {
  orders: OrderItem[];
}

// ── Constantes ────────────────────────────────────────────────────────

/** Stock mínimo saludable — por debajo de este umbral se marca como "bajo".
 *  Umbral elegido: < 20 unidades o < 10% del lote típico.
 *  Se usa para el código de color en la vista de productos.
 */
const STOCK_LOW_THRESHOLD = 20;

/** Stock crítico — por debajo se marca como "crítico".
 *  Umbral elegido: 0 unidades (sin stock).
 */
const STOCK_CRITICAL_THRESHOLD = 0;

// ── Helpers de clasificación de stock ─────────────────────────────────

export type StockLevel = "healthy" | "low" | "critical";

export function getStockLevel(stock: number): StockLevel {
  if (stock <= STOCK_CRITICAL_THRESHOLD) return "critical";
  if (stock < STOCK_LOW_THRESHOLD) return "low";
  return "healthy";
}

export function getStockLevelLabel(stock: number): string {
  const level = getStockLevel(stock);
  switch (level) {
    case "critical": return "Sin stock";
    case "low": return "Stock bajo";
    case "healthy": return "Disponible";
  }
}

export function getStockLevelColor(stock: number): string {
  const level = getStockLevel(stock);
  switch (level) {
    case "critical": return "text-red-600 bg-red-50 border-red-200";
    case "low": return "text-amber-600 bg-amber-50 border-amber-200";
    case "healthy": return "text-emerald-600 bg-emerald-50 border-emerald-200";
  }
}

// ── Extracción de errores de la API ───────────────────────────────────

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return fallback;
  }

  const detail = (payload as { detail: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = (detail as ValidationIssue[])
      .map((issue) => {
        const field = issue.loc?.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg ?? "valor inválido"}` : issue.msg;
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join(" · ");
    }
  }

  return fallback;
}

// ── Cliente HTTP ──────────────────────────────────────────────────────

/** Desde el navegador, las peticiones pasan por el proxy de Next.js
 *  (/api/inventory/*) configurado en next.config.ts, que reescribe
 *  a http://localhost:8000/inventory/*. Desde el servidor (SSR)
 *  se usa la variable NEXT_PUBLIC_INVENTORY_API_URL.
 */
const API_BASE_URL = typeof window !== "undefined"
  ? ""  // En el navegador, usar ruta relativa → Next.js proxy
  : (process.env.NEXT_PUBLIC_INVENTORY_API_URL ?? "http://127.0.0.1:8000");

function apiPath(endpoint: string): string {
  // Los endpoints ya incluyen /inventory/ (ej: "/inventory/products")
  return typeof window !== "undefined"
    ? `/api${endpoint}`  // → "/api/inventory/products" (coincide con el rewrite)
    : `${API_BASE_URL}${endpoint}`;
}

function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function handle401() {
  if (typeof window !== "undefined") {
    removeToken();
    window.location.href = "/login";
  }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...getAuthHeaders(),
    ...((init?.headers as Record<string, string>) ?? {}),
  };

  const response = await fetch(apiPath(path), {
    ...init,
    headers,
  });

  if (response.status === 401) {
    handle401();
    throw new ApiError("Sesión expirada. Redirigiendo al inicio de sesión...", 401);
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      extractErrorMessage(payload, `La API respondió con estado ${response.status}`),
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// ── Endpoints ─────────────────────────────────────────────────────────

/** Obtiene todos los suministros médicos con su stock actual. GET /inventory/products */
export function fetchProducts(): Promise<MedicalSupply[]> {
  return request<MedicalSupply[]>("/inventory/products");
}

/** Obtiene un suministro por ID con su stock calculado. GET /inventory/products/{id} */
export function fetchProduct(id: number): Promise<MedicalSupply> {
  return request<MedicalSupply>(`/inventory/products/${id}`);
}

/** Registra un nuevo suministro médico. POST /inventory/products */
export function createProduct(payload: {
  name: string;
  sku: string;
  category: string;
  unit: string;
  country: string;
}): Promise<MedicalSupply> {
  return request<MedicalSupply>("/inventory/products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Registra una orden de entrada (entrega de proveedor). POST /inventory/orders/inbound */
export function createInboundOrder(payload: SupplyDeliveryCreate): Promise<SupplyDeliveryResponse> {
  return request<SupplyDeliveryResponse>("/inventory/orders/inbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Registra una orden de salida (consumo clínico). POST /inventory/orders/outbound */
export function createOutboundOrder(payload: SupplyConsumptionCreate): Promise<SupplyConsumptionResponse> {
  return request<SupplyConsumptionResponse>("/inventory/orders/outbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Obtiene el historial completo de órdenes (entradas y salidas). GET /inventory/orders */
export function fetchOrders(): Promise<OrderListResponse> {
  return request<OrderListResponse>("/inventory/orders");
}